"""Dedicated accused-reference extractor for Indian criminal judgments.

Detects:
- Accused identifiers: A-1, A-2, A1, A.1, accused No. 1, accused no. 2, Accused 1
- Multi-accused ranges: Accused Nos. 1 and 2, accused Nos. 2 to 4
- Explicit name mappings: "A-1 Rajesh Kumar", "Accused No. 1, namely Rajesh Kumar", "A-1 (Rajesh Kumar)"

Principles:
- NEVER guess or infer a person's name.
- If explicit name mapping is present, extract name with accused_id.
- If no name is reliably mapped, retain the accused identifier with name=None / identifier.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.extraction.regex_extractors import make_evidence_snippet

# Verbs / particles that immediately following an accused identifier indicate an action, NOT a name
NON_NAME_VERBS_PREPOSITIONS = {
    "was",
    "is",
    "are",
    "were",
    "did",
    "had",
    "have",
    "has",
    "stated",
    "pleaded",
    "filed",
    "who",
    "whom",
    "which",
    "being",
    "and",
    "or",
    "died",
    "surrendered",
    "absconded",
    "confessed",
    "denied",
    "admitted",
    "produced",
    "arrested",
    "alleged",
    "along",
    "with",
    "referred",
    "held",
    "deposed",
    "further",
    "namely",
    "herein",
    "therein",
    "thereafter",
    "before",
    "after",
    "under",
    "upon",
    "against",
    "by",
    "at",
    "in",
    "on",
    "from",
    "to",
    "came",
    "went",
    "entered",
    "attacked",
    "assaulted",
    "fired",
    "stabbed",
    "escaped",
    "standing",
    "facing",
    "convicted",
    "acquitted",
    "sentenced",
    "appealed",
    "during",
    "while",
    "since",
    "until",
    "between",
    "both",
    "all",
    "either",
    "neither",
    "each",
    "every",
    "none",
    "not",
    "no",
    "yes",
    "said",
    "aforesaid",
    "above",
    "below",
    "having",
    "taking",
    "giving",
    "making",
    "doing",
    "going",
    "seeing",
    "knowing",
    "finding",
    "hearing",
    "then",
    "now",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "appellant",
    "respondent",
    "petitioner",
    "accused",
    "victim",
    "witness",
    "complainant",
    "police",
    "state",
    "court",
    "judge",
    "counsel",
    "advocate",
    "bench",
    "order",
    "charge",
    "section",
}

# Explicit mapping pattern:
# e.g., A-1 Rajesh Kumar | A-1, Rajesh Kumar | A-1, namely Rajesh Kumar | A-1 (Rajesh Kumar) | Accused No. 1 Rajesh Kumar | A-1 Balakarupasamy
EXPLICIT_ACCUSED_NAME_PATTERN = re.compile(
    r"\b(?:(?:[Aa]ccused\s+)?A[-.\s]?(\d{1,2})|[Aa]ccused(?:[\s-]+(?:[Nn]o\.?|[Nn]umber))?[\s-]*(\d{1,2}))"
    r"(?:[\s,–-]+(?:namely,?\s+|alias\s+|@\s+)?|\s*\(\s*)"
    r"([A-Z][a-zA-Z'.]+(?:\s+[A-Z][a-zA-Z'.]+){0,4})"
    r"(?:\s*\))?",
)

# Accused identifier pattern without explicit name
ACCUSED_SINGLE_PATTERN = re.compile(
    r"\b(?:(?:[Aa]ccused\s+)?A[-.\s]?(\d{1,2})|[Aa]ccused(?:[\s-]+(?:[Nn]o\.?|[Nn]umber))?[\s-]*(\d{1,2}))\b"
)

# Multi-accused "and" pattern: e.g. Accused Nos. 1 and 2, A-1 and A-2
ACCUSED_AND_PATTERN = re.compile(
    r"\b(?:(?:[Aa]ccused\s+)?(?:[Nn]os?\.?|[Nn]umbers?\.?)|A[-.\s]?)\s*(\d{1,2})\s*(?:and|&)\s*(\d{1,2})\b"
)

# Multi-accused range pattern: e.g. Accused Nos. 2 to 4, A-2 to A-4
ACCUSED_RANGE_PATTERN = re.compile(
    r"\b(?:(?:[Aa]ccused\s+)?(?:[Nn]os?\.?|[Nn]umbers?\.?)|A[-.\s]?)\s*(\d{1,2})\s*(?:to|-)\s*(\d{1,2})\b"
)

# Co-accused named pattern: e.g. co-accused Suresh Kumar | co-accused Balakarupasamy
CO_ACCUSED_NAME_PATTERN = re.compile(
    r"\b(?:co[- ]accused)\s+(?:namely,?\s+)?([A-Z][a-zA-Z'.]+(?:\s+[A-Z][a-zA-Z'.]+){0,3})\b"
)


def clean_mapped_name(raw_name: str) -> str | None:
    """Validate and clean an extracted candidate person name mapped to an accused."""
    tokens = raw_name.strip().split()
    if not tokens:
        return None

    # Check if first token is a non-name verb/preposition
    if tokens[0].lower() in NON_NAME_VERBS_PREPOSITIONS:
        return None

    # Filter out tokens that are clearly verbs or stop words
    valid_tokens: list[str] = []
    for token in tokens:
        clean_token = token.strip("(),.-'\"")
        if clean_token.lower() in NON_NAME_VERBS_PREPOSITIONS:
            break
        if clean_token and (clean_token[0].isupper() or clean_token.lower() in {"al", "bin", "de", "da"}):
            valid_tokens.append(clean_token)
        else:
            break

    if len(valid_tokens) >= 1:
        # Avoid single generic words like "The", "State"
        candidate = " ".join(valid_tokens)
        if candidate.lower() in {"state", "appellant", "respondent", "police", "court"}:
            return None
        return candidate
    return None


def extract_accused_entities(text: str) -> list[dict[str, Any]]:
    """Extract accused designations and name mappings from legal judgment text."""
    results: list[dict[str, Any]] = []
    seen_spans: set[tuple[int, int]] = set()
    mapped_accused_ids: dict[str, str] = {}  # e.g., "A-1" -> "Rajesh Kumar"

    # Step 1: Detect explicit name mappings (e.g. "A-1 Rajesh Kumar")
    for match in EXPLICIT_ACCUSED_NAME_PATTERN.finditer(text):
        num = match.group(1) or match.group(2)
        raw_name = match.group(3)
        accused_id = f"A-{num}"

        valid_name = clean_mapped_name(raw_name)
        if valid_name:
            mapped_accused_ids[accused_id] = valid_name
            span = (match.start(), match.end())
            seen_spans.add(span)
            snippet = make_evidence_snippet(text, match.start(), match.end())

            results.append(
                {
                    "name": valid_name,
                    "entity_type": "PERSON",
                    "canonical_name": valid_name,
                    "accused_id": accused_id,
                    "original_match": match.group(0).strip(),
                    "start_char": match.start(),
                    "end_char": match.end(),
                    "evidence_snippet": snippet,
                    "method": "accused_pattern",
                    "confidence": 0.95,
                    "metadata": {
                        "accused_id": accused_id,
                        "is_accused": True,
                        "named": True,
                        "raw_match": match.group(0).strip(),
                    },
                }
            )

    # Step 1b: Co-accused named references (e.g. "co-accused Suresh Kumar")
    for match in CO_ACCUSED_NAME_PATTERN.finditer(text):
        raw_name = match.group(1)
        valid_name = clean_mapped_name(raw_name)
        if valid_name:
            span = (match.start(), match.end())
            if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                continue
            seen_spans.add(span)
            snippet = make_evidence_snippet(text, match.start(), match.end())
            results.append(
                {
                    "name": valid_name,
                    "entity_type": "PERSON",
                    "canonical_name": valid_name,
                    "accused_id": None,
                    "original_match": match.group(0).strip(),
                    "start_char": match.start(),
                    "end_char": match.end(),
                    "evidence_snippet": snippet,
                    "method": "accused_pattern",
                    "confidence": 0.92,
                    "metadata": {
                        "is_accused": True,
                        "named": True,
                        "raw_match": match.group(0).strip(),
                    },
                }
            )

    # Step 2: Multi-accused ranges (e.g., "Accused Nos. 2 to 4")
    for match in ACCUSED_RANGE_PATTERN.finditer(text):
        span = (match.start(), match.end())
        if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
            continue
        seen_spans.add(span)

        start_num = int(match.group(1))
        end_num = int(match.group(2))
        snippet = make_evidence_snippet(text, match.start(), match.end())

        if 1 <= start_num < end_num <= 50:
            for n in range(start_num, end_num + 1):
                accused_id = f"A-{n}"
                resolved_name = mapped_accused_ids.get(accused_id)
                entity_name = resolved_name if resolved_name else accused_id
                entity_type = "PERSON" if resolved_name else "ACCUSED"

                results.append(
                    {
                        "name": entity_name,
                        "entity_type": entity_type,
                        "canonical_name": entity_name,
                        "accused_id": accused_id,
                        "original_match": match.group(0).strip(),
                        "start_char": match.start(),
                        "end_char": match.end(),
                        "evidence_snippet": snippet,
                        "method": "accused_pattern",
                        "confidence": 0.90,
                        "metadata": {
                            "accused_id": accused_id,
                            "is_accused": True,
                            "named": bool(resolved_name),
                            "range_parent": match.group(0).strip(),
                        },
                    }
                )

    # Step 3: Multi-accused "and" (e.g., "Accused Nos. 1 and 2")
    for match in ACCUSED_AND_PATTERN.finditer(text):
        span = (match.start(), match.end())
        if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
            continue
        seen_spans.add(span)

        n1, n2 = int(match.group(1)), int(match.group(2))
        snippet = make_evidence_snippet(text, match.start(), match.end())

        for n in (n1, n2):
            accused_id = f"A-{n}"
            resolved_name = mapped_accused_ids.get(accused_id)
            entity_name = resolved_name if resolved_name else accused_id
            entity_type = "PERSON" if resolved_name else "ACCUSED"

            results.append(
                {
                    "name": entity_name,
                    "entity_type": entity_type,
                    "canonical_name": entity_name,
                    "accused_id": accused_id,
                    "original_match": match.group(0).strip(),
                    "start_char": match.start(),
                    "end_char": match.end(),
                    "evidence_snippet": snippet,
                    "method": "accused_pattern",
                    "confidence": 0.90,
                    "metadata": {
                        "accused_id": accused_id,
                        "is_accused": True,
                        "named": bool(resolved_name),
                    },
                }
            )

    # Step 4: Standalone accused identifiers (e.g., "A-1", "accused No. 1")
    for match in ACCUSED_SINGLE_PATTERN.finditer(text):
        span = (match.start(), match.end())
        if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
            continue
        seen_spans.add(span)

        num = match.group(1) or match.group(2)
        accused_id = f"A-{num}"
        resolved_name = mapped_accused_ids.get(accused_id)
        entity_name = resolved_name if resolved_name else accused_id
        entity_type = "PERSON" if resolved_name else "ACCUSED"
        snippet = make_evidence_snippet(text, match.start(), match.end())

        results.append(
            {
                "name": entity_name,
                "entity_type": entity_type,
                "canonical_name": entity_name,
                "accused_id": accused_id,
                "original_match": match.group(0).strip(),
                "start_char": match.start(),
                "end_char": match.end(),
                "evidence_snippet": snippet,
                "method": "accused_pattern",
                "confidence": 0.90,
                "metadata": {
                    "accused_id": accused_id,
                    "is_accused": True,
                    "named": bool(resolved_name),
                },
            }
        )

    return results
