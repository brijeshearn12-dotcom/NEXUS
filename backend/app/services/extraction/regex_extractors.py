"""Deterministic regex extractors for Indian legal judgments.

Extracts:
- Indian phone numbers (regex_phone)
- Indian vehicle registration plates with state/UT plausibility checks (regex_vehicle)
- FIR numbers (regex_fir)
- Indian legal case numbers (regex_case_number)
"""

from __future__ import annotations

import re
from typing import Any

# Valid 2-letter codes for Indian States, Union Territories, and Bharat Series (BH)
VALID_INDIAN_STATE_CODES = {
    "AN",  # Andaman and Nicobar Islands
    "AP",  # Andhra Pradesh
    "AR",  # Arunachal Pradesh
    "AS",  # Assam
    "BR",  # Bihar
    "CG",  # Chhattisgarh
    "CH",  # Chandigarh
    "DD",  # Daman and Diu
    "DL",  # Delhi
    "DN",  # Dadra and Nagar Haveli
    "GA",  # Goa
    "GJ",  # Gujarat
    "HP",  # Himachal Pradesh
    "HR",  # Haryana
    "JH",  # Jharkhand
    "JK",  # Jammu and Kashmir
    "KA",  # Karnataka
    "KL",  # Kerala
    "LA",  # Ladakh
    "LD",  # Lakshadweep
    "MH",  # Maharashtra
    "ML",  # Meghalaya
    "MN",  # Manipur
    "MP",  # Madhya Pradesh
    "MZ",  # Mizoram
    "NL",  # Nagaland
    "OD",  # Odisha
    "OR",  # Odisha (historical)
    "PB",  # Punjab
    "PY",  # Puducherry
    "RJ",  # Rajasthan
    "SK",  # Sikkim
    "TN",  # Tamil Nadu
    "TR",  # Tripura
    "TS",  # Telangana
    "UA",  # Uttarakhand (historical)
    "UK",  # Uttarakhand
    "UP",  # Uttar Pradesh
    "WB",  # West Bengal
    "BH",  # Bharat series
}


def make_evidence_snippet(text: str, start: int, end: int, window: int = 50) -> str:
    """Create a contextual evidence snippet from the source text around the match."""
    snippet_start = max(0, start - window)
    snippet_end = min(len(text), end + window)

    left_ellipsis = "..." if snippet_start > 0 else ""
    right_ellipsis = "..." if snippet_end < len(text) else ""

    raw_snippet = text[snippet_start:snippet_end]
    # Clean excessive newlines/tabs within snippet for readability while preserving chars
    cleaned = re.sub(r"\s+", " ", raw_snippet).strip()
    return f"{left_ellipsis}{cleaned}{right_ellipsis}"


# ── 7.1 Indian Phone Numbers ──────────────────────────────────────────────────
# Indian mobile numbers: 10 digits starting with 6, 7, 8, or 9
# Prefixes: +91, 91, 0, or bare 10-digits
# Negative lookahead/behind to prevent matching within serial numbers, pincodes, or currency
PHONE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9/.-])(?:\+91[\s.-]?|91[\s.-]|0)?([6-9]\d{9})(?![0-9])"
)

# Context words indicating telephone / mobile records
PHONE_CONTEXT_WORDS = {
    "phone",
    "mobile",
    "cell",
    "sim",
    "call",
    "calling",
    "contact",
    "cdr",
    "telephone",
    "subscriber",
    "handset",
    "imei",
    "tower",
    "sms",
    "dial",
    "dialed",
    "outgoing",
    "incoming",
    "number",
}


def extract_phone_numbers(text: str) -> list[dict[str, Any]]:
    """Extract Indian mobile phone numbers with normalization and evidence snippet."""
    results: list[dict[str, Any]] = []

    for match in PHONE_PATTERN.finditer(text):
        full_match = match.group(0)
        ten_digits = match.group(1)

        # Context exclusion checks: avoid pincodes, act sections, years, rupee amounts
        pre_context = text[max(0, match.start() - 40) : match.start()].lower()
        post_context = text[match.end() : min(len(text), match.end() + 40)].lower()
        combined_context = f"{pre_context} {post_context}"

        # If preceding text indicates currency, section, or IPC/CrPC, skip false match
        if re.search(r"\b(?:rs\.?|inr|rupees|section|sec\.?|u/s|art\.?|article)\s*$", pre_context):
            continue

        # Check if the 10-digit number is just an act reference or repeated digit sequence
        if len(set(ten_digits)) <= 2:  # e.g. 9999999999 or 8888888888
            continue

        normalized = f"+91{ten_digits}"
        snippet = make_evidence_snippet(text, match.start(), match.end())

        results.append(
            {
                "name": normalized,
                "entity_type": "PHONE",
                "canonical_name": normalized,
                "original_match": full_match.strip(),
                "start_char": match.start(),
                "end_char": match.end(),
                "evidence_snippet": snippet,
                "method": "regex_phone",
                "confidence": 0.95 if any(w in combined_context for w in PHONE_CONTEXT_WORDS) else 0.85,
                "metadata": {
                    "raw_match": full_match.strip(),
                    "ten_digits": ten_digits,
                    "has_telecom_context": any(w in combined_context for w in PHONE_CONTEXT_WORDS),
                },
            }
        )

    return results


# ── 7.2 Indian Vehicle Registration Plates ───────────────────────────────────
# Format: [State Code 2-letters] [RTO 1-2 digits] [Series 1-3 letters (optional)] [Number 4 digits]
# E.g. MH12AB1234, MH-12-AB-1234, DL01CA1234, KA 01 MN 1234
VEHICLE_PATTERN = re.compile(
    r"\b([A-Z]{2})[\s.-]?(\d{1,2})[\s.-]?([A-Z]{1,3})?[\s.-]?(\d{4})\b",
    re.IGNORECASE,
)


def extract_vehicles(text: str) -> list[dict[str, Any]]:
    """Extract Indian vehicle registration numbers validating state/UT code."""
    results: list[dict[str, Any]] = []

    for match in VEHICLE_PATTERN.finditer(text):
        state_code = match.group(1).upper()
        rto_code = match.group(2)
        series = (match.group(3) or "").upper()
        number = match.group(4)

        if state_code not in VALID_INDIAN_STATE_CODES:
            continue

        # Prevent false positives like dates or section fragments
        # e.g., "IN 20 1990" or "NO 01 2020"
        if series == "" and int(number) in range(1950, 2030):
            # Probably a date/year pattern e.g., "UP 12 2019" -> skip
            continue

        # Padded RTO number to 2 digits
        rto_padded = rto_code.zfill(2)
        normalized = f"{state_code}{rto_padded}{series}{number}"
        original_match = match.group(0).strip()
        snippet = make_evidence_snippet(text, match.start(), match.end())

        results.append(
            {
                "name": normalized,
                "entity_type": "VEHICLE",
                "canonical_name": normalized,
                "original_match": original_match,
                "start_char": match.start(),
                "end_char": match.end(),
                "evidence_snippet": snippet,
                "method": "regex_vehicle",
                "confidence": 0.92,
                "metadata": {
                    "state_code": state_code,
                    "rto_code": rto_padded,
                    "series": series,
                    "number": number,
                    "original_match": original_match,
                },
            }
        )

    return results


# ── 7.3 FIR Numbers ───────────────────────────────────────────────────────────
# Formats:
# FIR No. 123/2022
# FIR No 123 of 2022
# F.I.R. No. 123/2022
# Crime No. 123/2022
# Cr. No. 123/2022
FIR_PATTERN = re.compile(
    r"\b(?:F\.?\s*I\.?\s*R\.?|Crime|Cr\.)\s*(?:No\.?|Number)?\s*(\d+(?:[/-]\d+)?)\s*(?:of|/)\s*(\d{4}|\d{2})\b",
    re.IGNORECASE,
)

# Secondary pattern without explicit 'of / year': e.g., "FIR No. 123/2020" or "Crime No. 45"
FIR_FALLBACK_PATTERN = re.compile(
    r"\b(?:F\.?\s*I\.?\s*R\.?|Crime|Cr\.)\s*(?:No\.?|Number)\s*[:.-]?\s*([A-Za-z0-9/_-]+)\b",
    re.IGNORECASE,
)


def extract_fir_numbers(text: str) -> list[dict[str, Any]]:
    """Extract First Information Report (FIR) and Crime Numbers."""
    results: list[dict[str, Any]] = []
    seen_spans: set[tuple[int, int]] = set()

    # Primary matches with year
    for match in FIR_PATTERN.finditer(text):
        full_match = match.group(0).strip()
        case_num = match.group(1).strip()
        year = match.group(2).strip()
        if len(year) == 2:
            year = f"20{year}" if int(year) < 50 else f"19{year}"

        prefix = "FIR" if "fir" in full_match.lower() else "Crime"
        normalized = f"{prefix} No. {case_num}/{year}"
        snippet = make_evidence_snippet(text, match.start(), match.end())

        seen_spans.add((match.start(), match.end()))
        results.append(
            {
                "name": normalized,
                "entity_type": "FIR",
                "canonical_name": normalized,
                "original_match": full_match,
                "start_char": match.start(),
                "end_char": match.end(),
                "evidence_snippet": snippet,
                "method": "regex_fir",
                "confidence": 0.95,
                "metadata": {
                    "fir_number": case_num,
                    "year": year,
                    "original_match": full_match,
                },
            }
        )

    # Fallback matches without explicit 'of year'
    for match in FIR_FALLBACK_PATTERN.finditer(text):
        span = (match.start(), match.end())
        if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
            continue

        val = match.group(1).strip()
        # Avoid matching generic words
        if val.lower() in {"nil", "unknown", "none", "not"}:
            continue

        full_match = match.group(0).strip()
        snippet = make_evidence_snippet(text, match.start(), match.end())
        normalized = re.sub(r"\s+", " ", full_match)

        results.append(
            {
                "name": normalized,
                "entity_type": "FIR",
                "canonical_name": normalized,
                "original_match": full_match,
                "start_char": match.start(),
                "end_char": match.end(),
                "evidence_snippet": snippet,
                "method": "regex_fir",
                "confidence": 0.90,
                "metadata": {
                    "original_match": full_match,
                },
            }
        )

    return results


# ── 7.4 Case Numbers ──────────────────────────────────────────────────────────
# Formats:
# Criminal Appeal No. 123 of 2022
# Criminal Appeal No.123/2022
# Sessions Case No. 45 of 2021
# Special Leave Petition (Criminal) No. 789 of 2020
# SLP (Crl.) No. ...
# Writ Petition (Crl.) No. ...
# Bail Application No. ...
# Crl.A. No. ...
# C.C. No. ...
CASE_NUMBER_PATTERNS = [
    # Criminal Appeal / Crl.A.
    re.compile(
        r"\b(?:Criminal\s+Appeal|Crl\.?\s*A\.?)\s*(?:No\.?|Nos\.?)?\s*(\d+[\w/-]*)\s*(?:of|/)\s*(\d{4})\b",
        re.IGNORECASE,
    ),
    # Sessions Case / S.C. No.
    re.compile(
        r"\b(?:Sessions\s+Case|S\.?\s*C\.?)\s*(?:No\.?|Nos\.?)?\s*(\d+[\w/-]*)\s*(?:of|/)\s*(\d{4})\b",
        re.IGNORECASE,
    ),
    # Special Leave Petition / SLP (Crl.)
    re.compile(
        r"\b(?:Special\s+Leave\s+Petition|SLP)\s*\((?:Criminal|Crl\.?)\)\s*(?:No\.?|Nos\.?)?\s*(\d+[\w/-]*)\s*(?:of|/)\s*(\d{4})\b",
        re.IGNORECASE,
    ),
    # Writ Petition (Crl) / W.P.(Crl)
    re.compile(
        r"\b(?:Writ\s+Petition|W\.?\s*P\.?)\s*\((?:Criminal|Crl\.?)\)\s*(?:No\.?|Nos\.?)?\s*(\d+[\w/-]*)\s*(?:of|/)\s*(\d{4})\b",
        re.IGNORECASE,
    ),
    # Bail Application
    re.compile(
        r"\b(?:Bail\s+Appln\.?|Bail\s+Application)\s*(?:No\.?|Nos\.?)?\s*(\d+[\w/-]*)\s*(?:of|/)\s*(\d{4})\b",
        re.IGNORECASE,
    ),
    # Calendar Case / C.C. No.
    re.compile(
        r"\b(?:Calendar\s+Case|C\.?\s*C\.?)\s*(?:No\.?|Nos\.?)?\s*(\d+[\w/-]*)\s*(?:of|/)\s*(\d{4})\b",
        re.IGNORECASE,
    ),
]


def extract_case_numbers(text: str) -> list[dict[str, Any]]:
    """Extract standard Indian court case numbers with evidence snippets."""
    results: list[dict[str, Any]] = []
    seen_spans: set[tuple[int, int]] = set()

    for pattern in CASE_NUMBER_PATTERNS:
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if any(s[0] <= span[0] and span[1] <= s[1] for s in seen_spans):
                continue
            seen_spans.add(span)

            full_match = match.group(0).strip()
            # Normalize whitespace
            normalized = re.sub(r"\s+", " ", full_match)
            snippet = make_evidence_snippet(text, match.start(), match.end())

            results.append(
                {
                    "name": normalized,
                    "entity_type": "CASE_NUMBER",
                    "canonical_name": normalized,
                    "original_match": full_match,
                    "start_char": match.start(),
                    "end_char": match.end(),
                    "evidence_snippet": snippet,
                    "method": "regex_case_number",
                    "confidence": 0.95,
                    "metadata": {
                        "case_number": match.group(1),
                        "year": match.group(2),
                        "original_match": full_match,
                    },
                }
            )

    return results


def extract_all_regex(text: str) -> list[dict[str, Any]]:
    """Convenience function running all deterministic regex extractors."""
    extracted: list[dict[str, Any]] = []
    extracted.extend(extract_phone_numbers(text))
    extracted.extend(extract_vehicles(text))
    extracted.extend(extract_fir_numbers(text))
    extracted.extend(extract_case_numbers(text))
    return extracted
