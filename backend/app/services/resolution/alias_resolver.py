"""Deterministic Entity Alias Resolution for NEXUS Task 4.1.

Provides conservative, high-precision entity alias resolution:
- Normalizes names (lowercase, whitespace collapse, punctuation normalization, honorific stripping)
- Compares strictly compatible entity types
- Implements token-prefix blocking within the same case (no unrestricted all-against-all)
- Evaluates string similarity using RapidFuzz (ratio and token_sort_ratio)
- Enforces conservative thresholds and strict given-name/numeric guardrails
- Stores additive, auditable, reversible merge decisions in `entity_merges`
- Never deletes original entities from the `entities` collection
- Ensures idempotent execution across repeated runs
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from rapidfuzz import fuzz

from app.core.db import get_db
from app.models.audit import AuditLogEntry
from app.models.entity_merge import EntityMerge
from app.models.enums import VerificationStatus

logger = logging.getLogger(__name__)

# Common Indian and legal honorific prefixes to strip during alias matching
HONORIFIC_PREFIXES = re.compile(
    r"^(?:mr\.?|ms\.?|mrs\.?|shri\.?|smt\.?|sri\.?|dr\.?|late\.?|md\.?|mohd\.?)\b[\s.]*",
    re.IGNORECASE,
)

# Legal stopwords ignored when creating blocking keys
LEGAL_STOPWORDS = {
    "v",
    "vs",
    "versus",
    "state",
    "of",
    "and",
    "the",
    "in",
    "anr",
    "ors",
    "appeal",
    "criminal",
    "crl",
}

DEFAULT_SIMILARITY_THRESHOLD = 0.85


def normalize_alias_name(name: str) -> str:
    """Normalize entity name for alias comparison.

    Rules:
    1. Strip possessive 's / ’s
    2. Lowercase
    3. Normalize punctuation characters to space
    4. Collapse repeated whitespace and strip
    5. Strip common honorific titles (e.g. Mr., Dr., Shri, Smt.)
    """
    if not name:
        return ""

    # 1. Remove possessive 's
    cleaned = re.sub(r"['’]s\b", "", name, flags=re.IGNORECASE)

    # 2. Lowercase
    cleaned = cleaned.lower()

    # 3. Normalize punctuation to whitespace
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)

    # 4. Collapse repeated whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 5. Strip honorifics
    cleaned = HONORIFIC_PREFIXES.sub("", cleaned).strip()

    return cleaned


def are_types_compatible(type_a: str, type_b: str) -> bool:
    """Determine whether two entity types are compatible for resolution.

    - Identical types are always compatible.
    - PERSON and ACCUSED are cross-compatible (accused individuals are persons).
    - Other distinct types (e.g. PERSON vs LOCATION, VEHICLE vs PHONE) are strictly incompatible.
    """
    ta = type_a.upper().strip() if type_a else "UNKNOWN"
    tb = type_b.upper().strip() if type_b else "UNKNOWN"

    if ta == tb:
        return True
    if {ta, tb} == {"PERSON", "ACCUSED"}:
        return True
    return False


def get_blocking_keys(normalized_name: str) -> set[str]:
    """Generate deterministic blocking keys from tokens of a normalized name.

    Tokens shorter than 3 characters use their full text; tokens of 3+ characters
    use their 3-character prefix. Legal stopwords are omitted.
    """
    tokens = [t for t in normalized_name.split() if t not in LEGAL_STOPWORDS]
    keys: set[str] = set()
    for token in tokens:
        if len(token) >= 3:
            keys.add(token[:3])
        elif len(token) >= 1:
            keys.add(token)
    return keys


def check_initials_match(tokens_a: list[str], tokens_b: list[str]) -> bool:
    """Check if one token sequence represents an initial abbreviation of the other.

    Examples:
    - ["r", "kumar"] and ["rajesh", "kumar"] -> True
    - ["a", "k", "sharma"] and ["anil", "kumar", "sharma"] -> True
    - ["s", "kumar"] and ["rajesh", "kumar"] -> False (initial mismatch)
    - ["rajesh", "kumar"] and ["suresh", "kumar"] -> False (neither is an initial)
    """
    if not tokens_a or not tokens_b:
        return False

    # Filter out stopwords
    t_a = [t for t in tokens_a if t not in LEGAL_STOPWORDS]
    t_b = [t for t in tokens_b if t not in LEGAL_STOPWORDS]

    if not t_a or not t_b:
        return False

    # Case 1: Same token count
    if len(t_a) == len(t_b) and len(t_a) >= 2:
        has_initial = False
        has_full_match = False
        for p in range(len(t_a)):
            token1, token2 = t_a[p], t_b[p]
            if token1 == token2:
                if len(token1) >= 3:
                    has_full_match = True
                continue
            elif len(token1) == 1 and token2.startswith(token1):
                has_initial = True
            elif len(token2) == 1 and token1.startswith(token2):
                has_initial = True
            else:
                return False
        return has_initial and has_full_match

    # Case 2: First + Last name vs First + Middle + Last name with initial
    # e.g. ["a", "sharma"] vs ["anil", "kumar", "sharma"]
    len_a = len(t_a)
    len_b = len(t_b)
    if abs(len_a - len_b) == 1 and min(len_a, len_b) >= 2:
        short_tokens = t_a if len(t_a) < len(t_b) else t_b
        long_tokens = t_b if len(t_a) < len(t_b) else t_a

        # Last tokens must match identically (e.g. surname)
        if short_tokens[-1] != long_tokens[-1] or len(short_tokens[-1]) < 3:
            return False

        # First token initial match
        s_first = short_tokens[0]
        l_first = long_tokens[0]
        if (len(s_first) == 1 and l_first.startswith(s_first)) or s_first == l_first:
            return True

    return False


def compute_similarity(name_a: str, name_b: str) -> tuple[float, str]:
    """Compute deterministic similarity score and resolution method.

    Returns:
        (similarity_score, method) where similarity_score is in [0.0, 1.0].
    """
    norm_a = normalize_alias_name(name_a)
    norm_b = normalize_alias_name(name_b)

    if not norm_a or not norm_b:
        return 0.0, "empty_name"

    # Exact match after normalization
    if norm_a == norm_b:
        return 1.0, "exact_match"

    tokens_a = norm_a.split()
    tokens_b = norm_b.split()

    # Numeric consistency guardrail:
    # If numbers/digits are present in either or both names, they must match exactly.
    # Prevents false merges between citations, FIR numbers, case numbers, or numbered actors.
    nums_a = re.findall(r"\d+", norm_a)
    nums_b = re.findall(r"\d+", norm_b)
    if (nums_a or nums_b) and nums_a != nums_b:
        return 0.0, "numeric_mismatch"

    # Initials matching
    if check_initials_match(tokens_a, tokens_b):
        return 0.92, "initials_match"

    # Guardrail for multi-word names: different given names sharing common surname
    # E.g. "Kaish Ahmad" vs "Atiq Ahmad" or "Rajesh Kumar" vs "Suresh Kumar"
    if len(tokens_a) >= 2 and len(tokens_b) >= 2:
        first_a, first_b = tokens_a[0], tokens_b[0]
        if len(first_a) >= 3 and len(first_b) >= 3:
            first_ratio = fuzz.ratio(first_a, first_b)
            if first_ratio < 70.0:
                return 0.0, "different_given_names"

    # Single-token guardrail: single short tokens (< 4 chars) require exact match
    if (len(tokens_a) == 1 and len(tokens_a[0]) < 4) or (len(tokens_b) == 1 and len(tokens_b[0]) < 4):
        return 0.0, "short_single_token"

    # RapidFuzz similarity
    ratio = fuzz.ratio(norm_a, norm_b)
    token_sort = fuzz.token_sort_ratio(norm_a, norm_b)

    max_score = max(ratio, token_sort)
    normalized_score = round(max_score / 100.0, 4)

    method = "rapidfuzz_token_sort" if token_sort >= ratio else "rapidfuzz_ratio"
    return normalized_score, method


def select_canonical_entity(
    entity_a: dict[str, Any],
    entity_b: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Deterministically select canonical vs alias entity.

    Criteria:
    1. Longest / most complete name (e.g. 'Rajesh Kumar' over 'R. Kumar')
    2. Higher confidence score
    3. Greater number of known aliases / occurrences
    4. Deterministic string tie-breaker on entity ID
    """
    name_a = entity_a.get("name", "")
    name_b = entity_b.get("name", "")

    # Score length / completeness
    len_a = len(name_a)
    len_b = len(name_b)

    # Score confidence
    conf_a = float(entity_a.get("provenance", {}).get("confidence", 0.85))
    conf_b = float(entity_b.get("provenance", {}).get("confidence", 0.85))

    # Score occurrences / aliases count
    meta_a = entity_a.get("metadata", {})
    meta_b = entity_b.get("metadata", {})
    occ_a = meta_a.get("occurrence_count", 1) + len(entity_a.get("aliases", []))
    occ_b = meta_b.get("occurrence_count", 1) + len(entity_b.get("aliases", []))

    # Weight comparison
    rank_a = (len_a, conf_a, occ_a, entity_a.get("id", ""))
    rank_b = (len_b, conf_b, occ_b, entity_b.get("id", ""))

    if rank_a >= rank_b:
        return entity_a, entity_b
    return entity_b, entity_a


def generate_stable_merge_id(case_id: str, canonical_id: str, alias_id: str) -> str:
    """Generate a deterministic, immutable merge ID for idempotency."""
    pair_str = f"{case_id}:{canonical_id}:{alias_id}"
    digest = hashlib.sha256(pair_str.encode("utf-8")).hexdigest()[:16]
    return f"merge_{case_id}_{digest}"


def resolve_case_aliases(
    case_id: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    database: Any | None = None,
) -> dict[str, Any]:
    """Execute conservative alias resolution for all entities within a case.

    Steps:
    1. Load entities for the case from MongoDB
    2. Partition entities by compatible entity type families
    3. Construct token-prefix blocks (preventing all-against-all comparison)
    4. Evaluate candidate pairs using deterministic and RapidFuzz rules
    5. Save additive, idempotent merge decisions to `entity_merges` collection
    6. Return resolution statistics dictionary

    Returns:
        dict with keys: case_id, entities_checked, candidate_pairs, merges_created, merges_skipped
    """
    db = database if database is not None else get_db()
    entities_col = db.entities
    merges_col = db.entity_merges
    audit_col = db.audit_log

    # 1. Load entities for the case
    cursor = entities_col.find({"case_id": case_id})
    entities = list(cursor)
    entities_checked = len(entities)

    if entities_checked == 0:
        return {
            "case_id": case_id,
            "entities_checked": 0,
            "candidate_pairs": 0,
            "merges_created": 0,
            "merges_skipped": 0,
        }

    # 2. Group by type compatibility family
    # PERSON and ACCUSED share family 'PERSON'; other types are separated
    type_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ent_lookup: dict[str, dict[str, Any]] = {}

    for ent in entities:
        ent_id = ent.get("id", "")
        if not ent_id:
            continue
        ent_lookup[ent_id] = ent
        etype = ent.get("entity_type", "UNKNOWN").upper().strip()
        family = "PERSON" if etype in {"PERSON", "ACCUSED"} else etype
        type_groups[family].append(ent)

    # 3. Blocking: construct candidate pairs within type families
    candidate_pair_ids: set[tuple[str, str]] = set()

    for _family, members in type_groups.items():
        blocks: dict[str, list[str]] = defaultdict(list)
        for ent in members:
            eid = ent["id"]
            norm = normalize_alias_name(ent.get("name", ""))
            if not norm:
                continue
            for b_key in get_blocking_keys(norm):
                blocks[b_key].append(eid)

        # Generate candidate pairs within each block
        for _b_key, member_ids in blocks.items():
            if len(member_ids) < 2:
                continue
            for i in range(len(member_ids)):
                for j in range(i + 1, len(member_ids)):
                    id1, id2 = member_ids[i], member_ids[j]
                    if id1 != id2:
                        pair = (id1, id2) if id1 < id2 else (id2, id1)
                        candidate_pair_ids.add(pair)

    candidate_pairs_count = len(candidate_pair_ids)
    merges_created = 0
    merges_skipped = 0
    now_utc = datetime.now(UTC)

    # 4. Evaluate each candidate pair
    for id1, id2 in candidate_pair_ids:
        e1 = ent_lookup[id1]
        e2 = ent_lookup[id2]

        # Check type compatibility
        if not are_types_compatible(e1.get("entity_type", ""), e2.get("entity_type", "")):
            merges_skipped += 1
            continue

        name1 = e1.get("name", "")
        name2 = e2.get("name", "")

        sim_score, method = compute_similarity(name1, name2)

        if sim_score >= threshold:
            # Safe merge decision
            canonical_ent, alias_ent = select_canonical_entity(e1, e2)
            canonical_id = canonical_ent["id"]
            alias_id = alias_ent["id"]

            merge_id = generate_stable_merge_id(case_id, canonical_id, alias_id)

            # Extract source references
            src_refs: set[str] = set()
            for ent in (e1, e2):
                if ent.get("document_id"):
                    src_refs.add(ent["document_id"])
                prov_ref = ent.get("provenance", {}).get("source_ref")
                if prov_ref:
                    src_refs.add(prov_ref)

            # Overall confidence
            conf1 = float(e1.get("provenance", {}).get("confidence", 0.85))
            conf2 = float(e2.get("provenance", {}).get("confidence", 0.85))
            pair_confidence = round(min(conf1, conf2) * sim_score, 4)

            merge_record = EntityMerge(
                merge_id=merge_id,
                canonical_entity_id=canonical_id,
                alias_entity_id=alias_id,
                case_id=case_id,
                similarity_score=sim_score,
                confidence=pair_confidence,
                method=method,
                verification_status=VerificationStatus.UNVERIFIED,
                created_at=now_utc,
                source_refs=sorted(list(src_refs)),
            )

            # Idempotent storage: upsert record by stable merge_id
            merges_col.update_one(
                {"merge_id": merge_id},
                {"$set": merge_record.model_dump(by_alias=True)},
                upsert=True,
            )
            merges_created += 1
        else:
            merges_skipped += 1

    # 5. Immutable Audit Log Entry
    audit_entry = AuditLogEntry(
        case_id=case_id,
        actor="alias_resolver",
        action="resolve_case_aliases",
        timestamp=now_utc,
        input_summary={
            "case_id": case_id,
            "threshold": threshold,
            "entities_checked": entities_checked,
        },
        result_summary=(
            f"Resolved aliases for case {case_id}: {merges_created} merges created, "
            f"{merges_skipped} skipped out of {candidate_pairs_count} candidate pairs."
        ),
    )
    audit_col.insert_one(audit_entry.model_dump(by_alias=True))

    logger.info(
        "Alias resolution for case %s complete: %d merges created, %d skipped across %d pairs.",
        case_id,
        merges_created,
        merges_skipped,
        candidate_pairs_count,
    )

    return {
        "case_id": case_id,
        "entities_checked": entities_checked,
        "candidate_pairs": candidate_pairs_count,
        "merges_created": merges_created,
        "merges_skipped": merges_skipped,
    }
