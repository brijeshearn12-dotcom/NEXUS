"""Pure, deterministic safeguards for cross-case candidate matching.

Nothing in this module touches the database. Each function encodes one safety rule:

1. Near-duplicate guard   — one judgment indexed under several titles is ONE judgment.
2. Citation filter        — names that only occur inside cited precedents are not participants;
                            a name used as a cited case's name is a precedent throughout that
                            judgment (parties in the judgment's own title are exempt).
3. Legal-role / witness   — judges, counsel and witnesses are not matched (reuses the existing
                            legal-role filter; adds coram/signature/appearance-roster formats and
                            a conservative witness-context check). Lower-case words and one-word
                            fragments of longer names are not name mentions at all.
4. Strict name rule       — exact normalized name or a clear initials match only (no fuzzy scores).
5. Identifier keys        — FIR/Crime number counts only together with its police station
                            (FIR numbers restart at every station each year); vehicles; phones
                            only when extracted in a telecom context.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from typing import Any

from app.services.extraction.legal_role_filter import is_legal_role
from app.services.extraction.regex_extractors import (
    extract_fir_numbers,
    extract_phone_numbers,
    extract_vehicles,
    make_evidence_snippet,
)
from app.services.resolution.alias_resolver import check_initials_match, normalize_alias_name

MATCHER_VERSION = "cross-case-mvp-1.0"

NEAR_DUPLICATE_JACCARD = 0.80
SHINGLE_WORDS = 8
CITATION_WINDOW_CHARS = 90
WITNESS_WINDOW_CHARS = 40
POLICE_STATION_WINDOW_CHARS = 400
PASSAGE_WINDOW_CHARS = 160

# ── 1. Near-duplicate guard ──────────────────────────────────────────────────

_WORD_RE = re.compile(r"\w+")


def text_shingles(text: str, size: int = SHINGLE_WORDS) -> set[str]:
    """Hashed word shingles used to compare two judgment texts."""
    words = _WORD_RE.findall((text or "").lower())
    if not words:
        return set()
    if len(words) < size:
        return {hashlib.sha1(" ".join(words).encode("utf-8")).hexdigest()[:16]}
    return {
        hashlib.sha1(" ".join(words[i : i + size]).encode("utf-8")).hexdigest()[:16]
        for i in range(len(words) - size + 1)
    }


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def group_near_duplicate_documents(
    documents: Iterable[dict[str, Any]],
    threshold: float = NEAR_DUPLICATE_JACCARD,
) -> dict[str, Any]:
    """Group documents whose texts are near-identical copies of the same judgment.

    Returns:
        {
          "representative_of": {document_id: representative_document_id},
          "duplicate_groups": [{"representative", "members", "min_similarity"}]  (size > 1 only)
        }
    The representative of a group is its lexicographically smallest document ID, so the
    choice is deterministic across runs.
    """
    docs = sorted((d for d in documents if d.get("id")), key=lambda d: d["id"])
    ids = [d["id"] for d in docs]
    shingles = {d["id"]: text_shingles(d.get("text") or "") for d in docs}
    parent = {doc_id: doc_id for doc_id in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    pair_similarity: dict[tuple[str, str], float] = {}
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            sa, sb = shingles[a], shingles[b]
            if not sa or not sb:
                continue
            # Upper bound on Jaccard: skip pairs whose sizes alone rule out a duplicate.
            if min(len(sa), len(sb)) / max(len(sa), len(sb)) < threshold:
                continue
            sim = jaccard_similarity(sa, sb)
            if sim >= threshold:
                pair_similarity[(a, b)] = round(sim, 4)
                ra, rb = find(a), find(b)
                if ra != rb:
                    keep, drop = (ra, rb) if ra < rb else (rb, ra)
                    parent[drop] = keep

    representative_of = {doc_id: find(doc_id) for doc_id in ids}
    members_by_rep: dict[str, list[str]] = {}
    for doc_id, rep in representative_of.items():
        members_by_rep.setdefault(rep, []).append(doc_id)

    duplicate_groups = []
    for rep, members in sorted(members_by_rep.items()):
        if len(members) < 2:
            continue
        member_set = set(members)
        sims = [s for (a, b), s in pair_similarity.items() if a in member_set and b in member_set]
        duplicate_groups.append(
            {
                "representative": rep,
                "members": sorted(members),
                "min_similarity": min(sims) if sims else None,
            }
        )

    return {"representative_of": representative_of, "duplicate_groups": duplicate_groups}


# ── 2. Citation / legal-role / witness context ───────────────────────────────

CITATION_CONTEXT_PATTERN = re.compile(
    r"\b(?:v\.|vs\.?|versus)\s"  # party separator in a case title: "X v. Y", "X vs. Y"
    r"|\(\d{4}\)\s*\d+\s*SCC\b"  # (2018) 8 SCC 271
    r"|\bSCC\s*On\s*Line\b"
    r"|\bAIR\s*\d{4}\b"
    r"|\(supra\)"
    r"|\bSCR\b"
    r"|\bCri\.?\s*L\.?\s*J\b"
    r"|\breported\s+in\b"
    r"|\bin\s+the\s+case\s+of\b"
    r"|\b(?:reliance|relied)\s+(?:on|upon)\b",
    re.IGNORECASE,
)

WITNESS_CONTEXT_PATTERN = re.compile(
    r"\b[PDC]\.?\s?W\.?\s?-?\s?\d{1,3}\b"  # PW-1, P.W.1, DW 2, CW-3
    r"|\b(?:prosecution|defence|defense|independent|eye)[\s-]?witness(?:es)?\b",
    re.IGNORECASE,
)


_HONORIFIC = r"(?:mr|mrs|ms|miss|sri|shri|smt|km|dr)\.?"

# Judge and counsel contexts in the formats Indian judgments actually use, which the per-case
# legal-role filter does not recognise: "HON'BLE X, J.", "(X,J.)", "Mr X, learned AGA-I",
# "assisted by Mr X", "Ms X and Mr Y, learned counsels", "Counsel for Applicant :- X, Y".
# Applied only by cross-case matching; the per-case extraction pipeline is unchanged.
COURT_ROLE_BEFORE_PATTERN = re.compile(
    r"\bhon(?:'|’|\s*)ble\s+(?:" + _HONORIFIC + r"\s+)?(?:(?:the\s+)?(?:chief\s+)?justice\s+)?$"
    r"|\bassisted\s+by\s+(?:" + _HONORIFIC + r"\s+)?$"
    r"|\bcounsel\s+for\s+(?:the\s+)?[a-z .()]{1,40}?\s*:-?\s*(?:[^\n,;:]{1,40},\s*){0,4}(?:" + _HONORIFIC + r"\s+)?$",
    re.IGNORECASE,
)
COURT_ROLE_AFTER_PATTERN = re.compile(
    r"^\s*,\s*(?:the\s+)?learned\b"
    r"|^\s*,\s*(?:(?:senior|designated)\s+)?(?:advocate|counsel)\b"
    r"|^\s+and\s+" + _HONORIFIC + r"\s+[a-z][\w.]*(?:\s+[a-z][\w.]*){0,3}\s*,\s*learned\b",
    re.IGNORECASE,
)
JUDGE_SUFFIX_PATTERN = re.compile(r"^\s*,\s*(?:J|CJ|CJI)\.?(?!\w)")  # "Yadav, J." / "(Yadav,J.)"
COURT_ROLE_WINDOW_CHARS = 120

# Words that may directly precede a one-word name without making it part of a longer name.
_NAME_PREFIX_WORDS = {
    "mr", "mrs", "ms", "miss", "sri", "shri", "smt", "km", "kumari", "dr", "late", "mp", "mla",
    "accused", "co-accused", "appellant", "applicant", "informant", "complainant", "deceased",
    "victim", "the",
}
_WORD_BEFORE = re.compile(r"([^\W\d_][\w'’.-]*)[ \t]+$")
_WORD_AFTER = re.compile(r"^[ \t]+([^\W\d_][\w'’-]*)")


def _same_line_before(text: str, start: int, window: int) -> str:
    before = text[max(0, start - window) : start]
    return before[before.rfind("\n") + 1 :]


def _same_line_after(text: str, end: int, window: int) -> str:
    after = text[end : end + window]
    cut = after.find("\n")
    return after if cut < 0 else after[:cut]


def is_court_role_context(text: str, start: int, end: int, window: int = COURT_ROLE_WINDOW_CHARS) -> bool:
    """True when a mention is a judge or counsel in a coram line, signature or appearance roster."""
    before = _same_line_before(text, start, window)
    after = _same_line_after(text, end, window)
    return bool(
        COURT_ROLE_BEFORE_PATTERN.search(before)
        or COURT_ROLE_AFTER_PATTERN.search(after)
        or JUDGE_SUFFIX_PATTERN.search(after)
    )


def is_capitalized_mention(span: str) -> bool:
    """Proper-noun check: every word starts with a capital (Title Case or ALL CAPS headers).

    Stops ordinary words that spaCy mislabelled as PERSON (e.g. "barbaric") from counting.
    """
    for token in span.split():
        first = next((ch for ch in token if ch.isalpha()), None)
        if first is not None and not first.isupper():
            return False
    return True


def is_part_of_longer_name(text: str, start: int, end: int) -> bool:
    """True when a one-word mention is glued to another capitalised name word on the same line.

    "Yadav" inside "Abhishek Yadav" or "SHEKHAR KUMAR YADAV" is not a mention of a person
    called "Yadav".
    """
    before = _WORD_BEFORE.search(text[max(0, start - 40) : start])
    if before:
        word = before.group(1)
        core = word.replace(".", "").lower()
        sentence_end = word.endswith(".") and len(core) > 4  # "Court." ends a sentence; "Mohd." does not
        if word[0].isupper() and core not in _NAME_PREFIX_WORDS and not sentence_end:
            return True
    after = _WORD_AFTER.search(text[end : end + 40])
    return bool(after and after.group(1)[0].isupper())


def is_citation_context(text: str, start: int, end: int, window: int = CITATION_WINDOW_CHARS) -> bool:
    """True when a mention sits inside a case-law citation (a cited precedent's party name)."""
    return bool(CITATION_CONTEXT_PATTERN.search(text[max(0, start - window) : min(len(text), end + window)]))


def is_witness_context(text: str, start: int, end: int, window: int = WITNESS_WINDOW_CHARS) -> bool:
    """True when a mention is immediately qualified as a witness (e.g. 'PW-5 ...', '... an eye-witness')."""
    return bool(WITNESS_CONTEXT_PATTERN.search(text[max(0, start - window) : min(len(text), end + window)]))


def find_name_mentions(text: str, name: str) -> list[tuple[int, int]]:
    """All case-insensitive, whole-word occurrences of a name (flexible whitespace)."""
    pattern = _name_pattern(name)
    if not text or not pattern:
        return []
    return [(m.start(), m.end()) for m in re.finditer(pattern, text, flags=re.IGNORECASE)]


def _name_pattern(name: str) -> str | None:
    tokens = [t for t in re.split(r"\s+", (name or "").strip()) if t]
    if not tokens:
        return None
    return r"(?<!\w)" + r"\s+".join(re.escape(t) for t in tokens) + r"(?!\w)"


def is_cited_case_name(text: str, name: str, own_title: str | None = None) -> bool:
    """True when the judgment uses this name as the name of a cited case.

    "P. Krishna Mohan Reddy v. State of A.P.", "State of A.P. v. Pellakuru Krishna Mohan
    Reddy" or "P. Krishna Mohan Reddy (supra)" make the name a precedent throughout that
    judgment, so later bare references ("the principles of P. Krishna Mohan Reddy") are not
    participant mentions either. Parties named in the judgment's own title are exempt.
    """
    pattern = _name_pattern(name)
    if not text or not pattern:
        return False
    if own_title and re.search(pattern, own_title, flags=re.IGNORECASE):
        return False
    as_petitioner = pattern + r"(?:['’]s)?\s*,?\s*(?:\bv\.|\bvs\b\.?|\bversus\b|\(\s*supra\s*\))"
    as_respondent = r"(?:\bv\.|\bvs\b\.?|\bversus\b)\s+(?:[\w.&'’-]+\s+){0,4}?" + pattern
    return bool(
        re.search(as_petitioner, text, flags=re.IGNORECASE)
        or re.search(as_respondent, text, flags=re.IGNORECASE)
    )


def classify_mentions(
    text: str, name: str, own_title: str | None = None
) -> dict[str, list[tuple[int, int]]]:
    """Split a name's mentions into participant / citation / legal_role / witness / not_a_name.

    `own_title` is the judgment's own title; its parties are never treated as precedents.
    """
    result: dict[str, list[tuple[int, int]]] = {
        "participant": [],
        "citation": [],
        "legal_role": [],
        "witness": [],
        "not_a_name": [],
    }
    single_word = len(normalize_alias_name(name).split()) == 1
    cited_case = is_cited_case_name(text, name, own_title)
    for start, end in find_name_mentions(text, name):
        if not is_capitalized_mention(text[start:end]) or (
            single_word and is_part_of_longer_name(text, start, end)
        ):
            result["not_a_name"].append((start, end))
            continue
        if cited_case or is_citation_context(text, start, end):
            result["citation"].append((start, end))
            continue
        legal, _reason = is_legal_role(name, text, start, end)
        if legal or is_court_role_context(text, start, end):
            result["legal_role"].append((start, end))
            continue
        if is_witness_context(text, start, end):
            result["witness"].append((start, end))
            continue
        result["participant"].append((start, end))
    return result


# ── 3. Strict name rule ──────────────────────────────────────────────────────


def normalized_tokens(name: str) -> list[str]:
    return normalize_alias_name(name).split()


def is_matchable_person_name(name: str) -> bool:
    """Reject forms that must never be matched across cases.

    Case-local identifiers such as "A-1" or "Accused No. 2" mean different people in
    different judgments, and bare initials carry no identity.
    """
    norm = normalize_alias_name(name)
    if not norm or any(ch.isdigit() for ch in norm):
        return False
    tokens = norm.split()
    if not tokens or all(len(t) == 1 for t in tokens):
        return False
    return max(len(t) for t in tokens) >= 3


def strict_name_match(name_a: str, name_b: str) -> tuple[bool, str, float]:
    """Exact normalized name, or a clear initials match. No fuzzy similarity is accepted.

    Returns (matched, basis, similarity).
    """
    norm_a = normalize_alias_name(name_a)
    norm_b = normalize_alias_name(name_b)
    if not norm_a or not norm_b:
        return False, "empty_name", 0.0
    if norm_a == norm_b:
        return True, "exact_normalized_name", 1.0
    if check_initials_match(norm_a.split(), norm_b.split()):
        return True, "initials_match", 0.92
    return False, "no_strict_match", 0.0


# ── 4. Identifier keys (FIR + police station, vehicles, phones) ──────────────

POLICE_STATION_PATTERN = re.compile(
    r"(?:\bPolice\s+Station|\bP\.?\s?S\.?(?=[\s:,\-–]+[A-Z])|\bThana)"
    r"\s*[:,\-–]?\s*(?:of\s+)?"
    r"([A-Z][A-Za-z]+(?:[ \t]+[A-Z][A-Za-z]+){0,2})"
)
_STATION_STOP_TOKENS = {
    "district", "distt", "dist", "police", "station", "under", "in", "at", "case", "crime",
    "fir", "registered", "u", "of", "the", "and", "for", "on", "vide", "no",
}


def normalize_police_station(raw: str) -> str | None:
    tokens: list[str] = []
    for tok in re.split(r"\s+", (raw or "").strip()):
        low = tok.lower().strip(".,;:")
        if not low or low in _STATION_STOP_TOKENS:
            break
        tokens.append(low)
    return " ".join(tokens[:2]) or None


def make_passage(text: str, start: int, end: int, window: int = PASSAGE_WINDOW_CHARS) -> str:
    """Verbatim passage around a span (whitespace collapsed, ellipses at cut edges)."""
    return make_evidence_snippet(text, start, end, window=window)


def extract_fir_station_keys(
    text: str, window: int = POLICE_STATION_WINDOW_CHARS
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """FIR/Crime numbers paired with the nearest police station named within `window` chars.

    Returns (keys, unresolved) where keys maps "<number>/<year>@<station>" to its evidence and
    unresolved lists FIR numbers for which no police station could be read (never used as
    corroboration).
    """
    stations = [
        (m.start(), m.end(), normalize_police_station(m.group(1)))
        for m in POLICE_STATION_PATTERN.finditer(text or "")
    ]
    keys: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, Any]] = []
    for fir in extract_fir_numbers(text or ""):
        meta = fir.get("metadata", {})
        number, year = meta.get("fir_number"), meta.get("year")
        if not number or not year:
            continue  # matches without a year are not identifiers
        start, end = fir["start_char"], fir["end_char"]
        best: tuple[int, int, int, str] | None = None
        for ps_start, ps_end, station in stations:
            if not station or ps_end < start - window or ps_start > end + window:
                continue
            if ps_end <= start:
                distance = start - ps_end
            elif ps_start >= end:
                distance = ps_start - end
            else:
                distance = 0
            if best is None or distance < best[0]:
                best = (distance, ps_start, ps_end, station)
        number_key = f"{str(number).strip()}/{year}"
        if best is None:
            unresolved.append({"fir": number_key, "start_char": start, "end_char": end})
            continue
        key = f"{number_key}@{best[3]}"
        if key not in keys:
            keys[key] = {
                "fir": number_key,
                "police_station": best[3],
                "start_char": start,
                "end_char": end,
                "passage": make_passage(text, min(start, best[1]), max(end, best[2])),
            }
    return keys, unresolved


def extract_vehicle_keys(text: str) -> dict[str, dict[str, Any]]:
    """Normalized vehicle registrations with the first passage mentioning each."""
    keys: dict[str, dict[str, Any]] = {}
    for v in extract_vehicles(text or ""):
        if is_citation_context(text, v["start_char"], v["end_char"]):
            continue
        keys.setdefault(
            v["name"],
            {"start_char": v["start_char"], "end_char": v["end_char"],
             "passage": make_passage(text, v["start_char"], v["end_char"])},
        )
    return keys


def extract_phone_keys(text: str) -> dict[str, dict[str, Any]]:
    """Normalized phone numbers, only when the extractor saw a telecom context around them."""
    keys: dict[str, dict[str, Any]] = {}
    for p in extract_phone_numbers(text or ""):
        if not p.get("metadata", {}).get("has_telecom_context"):
            continue
        keys.setdefault(
            p["name"],
            {"start_char": p["start_char"], "end_char": p["end_char"],
             "passage": make_passage(text, p["start_char"], p["end_char"])},
        )
    return keys
