"""Cross-case candidate matching (MVP).

NEXUS proposes. The investigator verifies.

Reads (never writes) the per-case pipeline outputs — `documents`, `entities` and the
within-case `entity_merges` — and writes ONLY to:
  * `cross_case_links` : candidate matches awaiting analyst review
  * `audit_log`        : proposal, run and review events

It never writes to `entities`, `entity_merges`, `edges` or `flags`, so per-case graphs,
rankings, communities and flags are unaffected by cross-case matching.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.core.db import get_db
from app.models.audit import AuditLogEntry
from app.models.cross_case_link import (
    CROSS_CASE_DISCLAIMER,
    CorroborationItem,
    CrossCaseLink,
    CrossCaseLinkStatus,
    CrossCaseReviewEvent,
    CrossCaseSide,
)
from app.services.analytics.centrality import is_valid_person_entity
from app.services.cross_case.safeguards import (
    MATCHER_VERSION,
    classify_mentions,
    extract_fir_station_keys,
    extract_phone_keys,
    extract_vehicle_keys,
    group_near_duplicate_documents,
    is_matchable_person_name,
    make_passage,
    strict_name_match,
)
from app.services.graph.cross_case_linker import build_alias_canonical_map
from app.services.resolution.alias_resolver import get_blocking_keys, normalize_alias_name

logger = logging.getLogger(__name__)

CROSS_CASE_COLLECTION = "cross_case_links"
PERSON_TYPES = ("ACCUSED", "PERSON")
AUDIT_ACTOR = "cross_case_matcher"

# Heuristic ranking points (NOT probabilities). Documented in each link's score_breakdown.
NAME_POINTS = {"exact_normalized_name": 3, "initials_match": 2}
FIR_POINTS = 3
VEHICLE_POINTS = 2
PHONE_POINTS = 3
SHARED_PARTICIPANT_POINTS = 1
MAX_SCORED_SHARED_PARTICIPANTS = 3
MAX_LISTED_SHARED_PARTICIPANTS = 5
MAX_REJECTED_EXAMPLES = 10

REVIEW_STATUSES = {s.value for s in CrossCaseLinkStatus}
_AUDIT_STATUS = {"proposed": "unverified", "confirmed": "confirmed", "rejected": "rejected"}


def ensure_cross_case_indexes(database: Any) -> None:
    """Idempotent indexes; the unique link_id index prevents duplicate proposals."""
    col = database[CROSS_CASE_COLLECTION]
    try:
        col.create_index("link_id", unique=True)
        col.create_index("status")
        col.create_index("side_a.case_id")
        col.create_index("side_b.case_id")
    except Exception as exc:  # pragma: no cover - index creation must never block matching
        logger.warning("Cross-case index verification encountered an issue: %s", exc)


def _stable_link_id(side_a_key: str, side_b_key: str) -> str:
    digest = hashlib.sha256(f"{side_a_key}|{side_b_key}".encode()).hexdigest()[:20]
    return f"ccl_{digest}"


def _audit(
    db: Any,
    case_id: str,
    action: str,
    actor: str,
    input_summary: dict[str, Any],
    result_summary: str,
    link_id: str | None = None,
    status: str | None = None,
) -> None:
    entry = AuditLogEntry(
        case_id=case_id,
        actor=actor,
        action=action,
        timestamp=datetime.now(UTC),
        input_summary=input_summary,
        result_summary=result_summary,
        entity_type="cross_case_link" if link_id else "cross_case_matching",
        entity_id=link_id,
        verification_status=_AUDIT_STATUS.get(status) if status else None,
    )
    db.audit_log.insert_one(entry.model_dump(by_alias=True))


# ── Candidate building ───────────────────────────────────────────────────────


def _build_person_candidates(
    document: dict[str, Any], members_by_canonical: dict[str, list[dict[str, Any]]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Per-judgment person candidates that are real participants (not citations/roles/witnesses)."""
    text = document.get("text") or ""
    candidates: list[dict[str, Any]] = []
    excluded = {
        "citation_only": 0,
        "legal_role_or_witness_only": 0,
        "no_proper_name_mention": 0,
        "not_matchable": 0,
    }

    for canonical_id in sorted(members_by_canonical):
        members = members_by_canonical[canonical_id]
        canonical = next((m for m in members if m.get("id") == canonical_id), members[0])
        node_view = {"entity_type": canonical.get("entity_type", ""), "name": canonical.get("name", "")}
        if not is_valid_person_entity(canonical_id, node_view):
            excluded["not_matchable"] += 1
            continue

        name_forms: list[str] = []
        for member in members:
            for form in [member.get("name", "")] + list(member.get("aliases") or []):
                form = (form or "").strip()
                if form and form not in name_forms and is_matchable_person_name(form):
                    name_forms.append(form)
        if not name_forms:
            excluded["not_matchable"] += 1
            continue

        participant_spans: list[tuple[int, int, str]] = []
        citation_count = 0
        other_count = 0
        for form in name_forms:
            mentions = classify_mentions(text, form, own_title=document.get("title"))
            participant_spans.extend((s, e, form) for s, e in mentions["participant"])
            citation_count += len(mentions["citation"])
            other_count += len(mentions["legal_role"]) + len(mentions["witness"])

        if not participant_spans:
            if citation_count:
                excluded["citation_only"] += 1
            elif other_count:
                excluded["legal_role_or_witness_only"] += 1
            else:
                # Only lower-case words ("barbaric") or fragments of longer names ("Yadav").
                excluded["no_proper_name_mention"] += 1
            continue

        participant_spans = sorted(set(participant_spans))
        candidates.append(
            {
                "document_id": document["id"],
                "case_id": canonical.get("case_id") or document.get("case_id"),
                "entity_id": canonical_id,
                "entity_name": canonical.get("name", ""),
                "entity_type": canonical.get("entity_type", ""),
                "name_forms": name_forms,
                "norm_names": sorted({normalize_alias_name(f) for f in name_forms}),
                "participant_spans": participant_spans,
                "citation_count": citation_count,
                "is_accused": any((m.get("metadata") or {}).get("is_accused") for m in members),
                "extraction_evidence_snippet": canonical.get("evidence_snippet"),
                "extraction_provenance": canonical.get("provenance"),
            }
        )
    return candidates, excluded


def _first_span_for(candidate: dict[str, Any], form: str) -> tuple[int, int]:
    for start, end, span_form in candidate["participant_spans"]:
        if span_form == form:
            return start, end
    start, end, _ = candidate["participant_spans"][0]
    return start, end


def _side(document: dict[str, Any], candidate: dict[str, Any], form: str) -> CrossCaseSide:
    text = document.get("text") or ""
    start, end = _first_span_for(candidate, form)
    return CrossCaseSide(
        case_id=candidate["case_id"],
        document_id=document["id"],
        document_title=document.get("title"),
        source_url=document.get("source_url"),
        court=document.get("court"),
        date=document.get("date"),
        entity_id=candidate["entity_id"],
        entity_name=candidate["entity_name"],
        entity_type=candidate["entity_type"],
        matched_name_form=form,
        is_accused_in_case=bool(candidate["is_accused"]),
        participant_mention_count=len(candidate["participant_spans"]),
        citation_mention_count=candidate["citation_count"],
        evidence_passage=make_passage(text, start, end),
        evidence_start_char=start,
        evidence_end_char=end,
        extraction_evidence_snippet=candidate.get("extraction_evidence_snippet"),
        extraction_provenance=candidate.get("extraction_provenance"),
    )


def _other_people(names: set[str], own_names: set[str]) -> list[str]:
    """Shared participants that are clearly other people, one entry per person.

    A name whose words contain, or are contained in, the matched person's name ("m p atiq
    ahmad" vs "atiq ahmad") is that person again and cannot corroborate them; among the rest,
    such variants are collapsed to the shortest form so no one is counted twice.
    """
    own_tokens = [set(n.split()) for n in own_names]
    others = [n for n in names if not any(set(n.split()) <= t or t <= set(n.split()) for t in own_tokens)]
    distinct = [n for n in others if not any(o != n and set(o.split()) < set(n.split()) for o in others)]
    return sorted(distinct)


# ── Matching run ─────────────────────────────────────────────────────────────


def run_cross_case_matching(database: Any | None = None) -> dict[str, Any]:
    """Discover candidate cross-case matches from the stored corpus and per-case entities."""
    db = database if database is not None else get_db()
    col = db[CROSS_CASE_COLLECTION]
    ensure_cross_case_indexes(db)
    run_started = datetime.now(UTC)

    documents = list(
        db.documents.find(
            {},
            {"_id": 0, "id": 1, "case_id": 1, "title": 1, "text": 1, "source_url": 1, "court": 1, "date": 1},
        )
    )
    docs_by_id = {d["id"]: d for d in documents if d.get("id")}
    duplicates = group_near_duplicate_documents(documents)
    representative_of = duplicates["representative_of"]

    # Existing within-case merges (read-only) collapse per-case aliases before matching.
    alias_map = build_alias_canonical_map(db)
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    skipped_duplicate_entities = 0
    for ent in db.entities.find({"entity_type": {"$in": list(PERSON_TYPES)}}, {"_id": 0}):
        doc_id = ent.get("document_id")
        if not doc_id or doc_id not in docs_by_id:
            continue
        if representative_of.get(doc_id, doc_id) != doc_id:
            skipped_duplicate_entities += 1  # a copy of another judgment: represented by that one
            continue
        grouped[doc_id][alias_map.get(ent["id"], ent["id"])].append(ent)

    candidates_by_doc: dict[str, list[dict[str, Any]]] = {}
    participants_by_doc: dict[str, dict[str, tuple[int, int]]] = {}
    exclusion_totals = {
        "citation_only": 0,
        "legal_role_or_witness_only": 0,
        "no_proper_name_mention": 0,
        "not_matchable": 0,
    }
    for doc_id in sorted(grouped):
        cands, excluded = _build_person_candidates(docs_by_id[doc_id], grouped[doc_id])
        for key, count in excluded.items():
            exclusion_totals[key] += count
        candidates_by_doc[doc_id] = cands
        people: dict[str, tuple[int, int]] = {}
        for cand in cands:
            for form in cand["name_forms"]:
                norm = normalize_alias_name(form)
                if len(norm.split()) >= 2 and norm not in people:
                    people[norm] = _first_span_for(cand, form)
        participants_by_doc[doc_id] = people

    identifiers: dict[str, dict[str, Any]] = {}
    for doc_id in candidates_by_doc:
        text = docs_by_id[doc_id].get("text") or ""
        fir_keys, fir_unresolved = extract_fir_station_keys(text)
        identifiers[doc_id] = {
            "fir": fir_keys,
            "fir_without_station": fir_unresolved,
            "vehicle": extract_vehicle_keys(text),
            "phone": extract_phone_keys(text),
        }

    # Blocking: only compare candidates that share a name-token prefix.
    blocks: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for doc_id, cands in candidates_by_doc.items():
        for idx, cand in enumerate(cands):
            keys: set[str] = set()
            for norm in cand["norm_names"]:
                keys |= get_blocking_keys(norm)
            for key in keys:
                blocks[key].append((doc_id, idx))

    pairs: set[tuple[tuple[str, int], tuple[str, int]]] = set()
    for members in blocks.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                left, right = members[i], members[j]
                if left[0] == right[0]:
                    continue
                if docs_by_id[left[0]].get("case_id") == docs_by_id[right[0]].get("case_id"):
                    continue  # same case: handled by per-case resolution, not cross-case
                pairs.add((left, right) if left < right else (right, left))

    stats = {
        "candidate_pairs_evaluated": len(pairs),
        "strict_name_matches": 0,
        "rejected_name_only": 0,
        "rejected_single_token_without_identifier": 0,
    }
    rejected_examples: list[dict[str, Any]] = []
    proposals: list[CrossCaseLink] = []

    for left_ref, right_ref in sorted(pairs):
        cand_l = candidates_by_doc[left_ref[0]][left_ref[1]]
        cand_r = candidates_by_doc[right_ref[0]][right_ref[1]]

        best: tuple[float, str, str, str] | None = None
        for form_l in cand_l["name_forms"]:
            for form_r in cand_r["name_forms"]:
                matched, basis, similarity = strict_name_match(form_l, form_r)
                if matched and (best is None or similarity > best[0]):
                    best = (similarity, basis, form_l, form_r)
        if best is None:
            continue
        stats["strict_name_matches"] += 1
        similarity, basis, form_l, form_r = best

        # Orient deterministically: side A is the lexicographically smaller (case, entity).
        key_l = f"{cand_l['case_id']}:{cand_l['entity_id']}"
        key_r = f"{cand_r['case_id']}:{cand_r['entity_id']}"
        if key_r < key_l:
            cand_l, cand_r, form_l, form_r, key_l, key_r = cand_r, cand_l, form_r, form_l, key_r, key_l
        doc_a = docs_by_id[cand_l["document_id"]]
        doc_b = docs_by_id[cand_r["document_id"]]
        ids_a, ids_b = identifiers[doc_a["id"]], identifiers[doc_b["id"]]

        corroboration: list[CorroborationItem] = []
        breakdown = [f"+{NAME_POINTS[basis]} {basis.replace('_', ' ')}"]
        score = NAME_POINTS[basis]

        for key in sorted(set(ids_a["fir"]) & set(ids_b["fir"])):
            info = ids_a["fir"][key]
            corroboration.append(
                CorroborationItem(
                    kind="fir_police_station",
                    value=key,
                    description=(
                        f"Same FIR/Crime No. {info['fir']} at police station "
                        f"{info['police_station'].title()} is cited in both judgments"
                    ),
                    evidence_a=ids_a["fir"][key]["passage"],
                    evidence_b=ids_b["fir"][key]["passage"],
                )
            )
            score += FIR_POINTS
            breakdown.append(f"+{FIR_POINTS} same FIR {info['fir']} @ {info['police_station'].title()}")
        for key in sorted(set(ids_a["vehicle"]) & set(ids_b["vehicle"])):
            corroboration.append(
                CorroborationItem(
                    kind="vehicle",
                    value=key,
                    description=f"Same vehicle registration {key} appears in both judgments",
                    evidence_a=ids_a["vehicle"][key]["passage"],
                    evidence_b=ids_b["vehicle"][key]["passage"],
                )
            )
            score += VEHICLE_POINTS
            breakdown.append(f"+{VEHICLE_POINTS} same vehicle {key}")
        for key in sorted(set(ids_a["phone"]) & set(ids_b["phone"])):
            corroboration.append(
                CorroborationItem(
                    kind="phone",
                    value=key,
                    description=f"Same phone number {key} appears (telecom context) in both judgments",
                    evidence_a=ids_a["phone"][key]["passage"],
                    evidence_b=ids_b["phone"][key]["passage"],
                )
            )
            score += PHONE_POINTS
            breakdown.append(f"+{PHONE_POINTS} same phone {key}")
        identifier_count = len(corroboration)

        single_token = min(len(normalize_alias_name(form_l).split()), len(normalize_alias_name(form_r).split())) < 2
        if not single_token:
            own_names = set(cand_l["norm_names"]) | set(cand_r["norm_names"])
            people_a, people_b = participants_by_doc[doc_a["id"]], participants_by_doc[doc_b["id"]]
            shared = _other_people(set(people_a) & set(people_b), own_names)
            for person in shared[:MAX_LISTED_SHARED_PARTICIPANTS]:
                corroboration.append(
                    CorroborationItem(
                        kind="shared_participant",
                        value=person,
                        description=f"{person.title()} is also named (outside citations) in both judgments",
                        evidence_a=make_passage(doc_a.get("text") or "", *people_a[person]),
                        evidence_b=make_passage(doc_b.get("text") or "", *people_b[person]),
                    )
                )
            scored = min(len(shared), MAX_SCORED_SHARED_PARTICIPANTS)
            if scored:
                score += scored * SHARED_PARTICIPANT_POINTS
                breakdown.append(
                    f"+{scored * SHARED_PARTICIPANT_POINTS} shared participants "
                    f"({len(shared)} found, max {MAX_SCORED_SHARED_PARTICIPANTS} scored)"
                )

        rejection: str | None = None
        if single_token and identifier_count == 0:
            # Shared participants are never enough for a one-word name such as "Ashraf".
            rejection = "single_word_name_without_identifier"
            stats["rejected_single_token_without_identifier"] += 1
        elif not corroboration:
            rejection = "name_only_no_corroboration"  # a name alone is never enough
            stats["rejected_name_only"] += 1
        if rejection:
            if len(rejected_examples) < MAX_REJECTED_EXAMPLES:
                rejected_examples.append(
                    {
                        "reason": rejection,
                        "name_a": form_l,
                        "case_a": cand_l["case_id"],
                        "name_b": form_r,
                        "case_b": cand_r["case_id"],
                        "name_match_basis": basis,
                    }
                )
            continue

        side_a = _side(doc_a, cand_l, form_l)
        side_b = _side(doc_b, cand_r, form_r)
        reasons = [
            f"Name match ({basis.replace('_', ' ')}): '{form_l}' in {side_a.case_id} and "
            f"'{form_r}' in {side_b.case_id}.",
            f"Both are named outside case-law citations and judge/counsel/witness contexts "
            f"({side_a.participant_mention_count} and {side_b.participant_mention_count} mentions).",
            "The two judgments are distinct documents, not copies of the same judgment.",
        ]
        reasons.extend(item.description + "." for item in corroboration)
        for side in (side_a, side_b):
            if side.is_accused_in_case:
                reasons.append(f"Marked as accused by the per-case pipeline in {side.case_id}.")

        proposals.append(
            CrossCaseLink(
                link_id=_stable_link_id(key_l, key_r),
                side_a=side_a,
                side_b=side_b,
                name_match_basis=basis,
                name_similarity=similarity,
                corroboration=corroboration,
                match_strength="strong" if identifier_count else "moderate",
                match_score=score,
                score_breakdown=breakdown,
                reasons=reasons,
                matcher_version=MATCHER_VERSION,
            )
        )

    created, refreshed, kept_reviewed = 0, 0, 0
    for link in proposals:
        existing = col.find_one({"link_id": link.link_id}, {"_id": 0})
        now = datetime.now(UTC)
        if existing is None:
            col.insert_one(link.model_dump(by_alias=True))
            created += 1
            for side, other in ((link.side_a, link.side_b), (link.side_b, link.side_a)):
                _audit(
                    db,
                    case_id=side.case_id,
                    action="cross_case_match_proposed",
                    actor=AUDIT_ACTOR,
                    input_summary={
                        "link_id": link.link_id,
                        "entity_name": side.entity_name,
                        "other_case_id": other.case_id,
                        "other_entity_name": other.entity_name,
                        "match_strength": link.match_strength,
                        "corroboration": [c.kind for c in link.corroboration],
                    },
                    result_summary=(
                        f"Candidate match proposed: {side.entity_name} ({side.case_id}) and "
                        f"{other.entity_name} ({other.case_id}). Awaiting analyst review. "
                        f"{CROSS_CASE_DISCLAIMER}"
                    ),
                    link_id=link.link_id,
                    status="proposed",
                )
        elif existing.get("status", "proposed") == "proposed":
            fresh = link.model_dump(by_alias=True)
            refresh = {k: fresh[k] for k in (
                "side_a", "side_b", "name_match_basis", "name_similarity", "corroboration",
                "match_strength", "match_score", "score_breakdown", "reasons", "matcher_version",
            )}
            refresh.update({"updated_at": now, "last_matched_at": now})
            col.update_one({"link_id": link.link_id}, {"$set": refresh})
            refreshed += 1
        else:
            # Reviewed decisions and the evidence they were based on are never overwritten.
            col.update_one({"link_id": link.link_id}, {"$set": {"last_matched_at": now}})
            kept_reviewed += 1

    not_rediscovered = col.count_documents({"last_matched_at": {"$lt": run_started}})
    duplicate_groups = [
        {
            **group,
            "titles": {m: docs_by_id[m].get("title") for m in group["members"] if m in docs_by_id},
        }
        for group in duplicates["duplicate_groups"]
    ]
    summary = {
        "status": "ok",
        "matcher_version": MATCHER_VERSION,
        "documents_considered": len(docs_by_id),
        "distinct_judgments": len(set(representative_of.values())),
        "duplicate_groups": duplicate_groups,
        "entities_skipped_as_duplicate_copies": skipped_duplicate_entities,
        "person_candidates": sum(len(c) for c in candidates_by_doc.values()),
        "excluded_person_entities": exclusion_totals,
        **stats,
        "rejected_examples": rejected_examples,
        "proposals_found": len(proposals),
        "proposals_created": created,
        "proposals_refreshed": refreshed,
        "reviewed_proposals_kept_unchanged": kept_reviewed,
        "proposals_not_rediscovered": not_rediscovered,
        "proposals_total": col.count_documents({}),
    }
    _audit(
        db,
        case_id="corpus_batch",
        action="cross_case_matching_run",
        actor=AUDIT_ACTOR,
        input_summary={
            "documents_considered": summary["documents_considered"],
            "distinct_judgments": summary["distinct_judgments"],
            "matcher_version": MATCHER_VERSION,
        },
        result_summary=(
            f"Cross-case matching run: {len(proposals)} candidate matches found "
            f"({created} new, {refreshed} refreshed, {kept_reviewed} already reviewed); "
            f"{len(duplicate_groups)} duplicate-judgment group(s) collapsed."
        ),
    )
    return summary


# ── Review and queries ───────────────────────────────────────────────────────


def review_cross_case_link(
    link_id: str,
    status: str,
    notes: str | None = None,
    analyst_id: str | None = None,
    database: Any | None = None,
) -> dict[str, Any]:
    """Record an analyst decision (confirmed / rejected / back to proposed) with audit entries."""
    target = (status or "").strip().lower()
    if target not in REVIEW_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(REVIEW_STATUSES))}.")

    db = database if database is not None else get_db()
    col = db[CROSS_CASE_COLLECTION]
    link = col.find_one({"link_id": link_id}, {"_id": 0})
    if link is None:
        raise LookupError(f"Cross-case link not found: {link_id}")

    actor = (analyst_id or "").strip() or "analyst_human"
    previous = link.get("status", "proposed")
    now = datetime.now(UTC)
    event = CrossCaseReviewEvent(
        status=target, previous_status=previous, analyst_id=actor, notes=notes, timestamp=now
    )
    col.update_one(
        {"link_id": link_id},
        {
            "$set": {
                "status": target,
                "analyst_notes": notes,
                "reviewed_by": actor,
                "reviewed_at": now,
                "updated_at": now,
            },
            "$push": {"review_history": event.model_dump(by_alias=True)},
        },
    )

    side_a, side_b = link["side_a"], link["side_b"]
    action = "cross_case_match_reset_to_proposed" if target == "proposed" else f"cross_case_match_{target}"
    for side, other in ((side_a, side_b), (side_b, side_a)):
        _audit(
            db,
            case_id=side["case_id"],
            action=action,
            actor=actor,
            input_summary={
                "link_id": link_id,
                "entity_name": side["entity_name"],
                "other_case_id": other["case_id"],
                "other_entity_name": other["entity_name"],
                "previous_status": previous,
                "new_status": target,
                "notes": notes,
            },
            result_summary=(
                f"Analyst marked candidate match {side['entity_name']} ({side['case_id']}) / "
                f"{other['entity_name']} ({other['case_id']}) as {target}."
            ),
            link_id=link_id,
            status=target,
        )

    return col.find_one({"link_id": link_id}, {"_id": 0})


def list_cross_case_links(
    status: str | None = None,
    case_id: str | None = None,
    database: Any | None = None,
) -> list[dict[str, Any]]:
    db = database if database is not None else get_db()
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if case_id:
        query["$or"] = [{"side_a.case_id": case_id}, {"side_b.case_id": case_id}]
    items = list(db[CROSS_CASE_COLLECTION].find(query, {"_id": 0}))
    items.sort(
        key=lambda x: (
            -int(x.get("match_score", 0)),
            x.get("side_a", {}).get("case_id", ""),
            str(x.get("side_a", {}).get("entity_name", "")).lower(),
            x.get("link_id", ""),
        )
    )
    return items


def get_cross_case_link(link_id: str, database: Any | None = None) -> dict[str, Any] | None:
    db = database if database is not None else get_db()
    return db[CROSS_CASE_COLLECTION].find_one({"link_id": link_id}, {"_id": 0})
