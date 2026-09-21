"""Conservative judgment-text boilerplate stripper for Indian criminal judgments.

Preserves narrative facts, paragraph ordering, accused identifiers, dates,
locations, evidence, charges, and findings while stripping HTML tags, court
page headers/footers, repetitive coram/appearance lines, and OCR artifacts.
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from typing import Any

CLEANING_VERSION = "1.0.0"
CLEANING_METHOD = "deterministic_boilerplate_removal"

# Patterns for court header/footer repetition, URLs, and page numbers
_RE_PAGE_NUMBERS = re.compile(
    r"(?mi)^\s*(?:Page\s+(?:No\.?\s*)?\d+(?:\s*(?:/|of)\s*\d+)?|\d+\s+of\s+\d+|\[\s*Page\s*\d+\s*\])\s*$"
)
_RE_COURT_URLS = re.compile(
    r"(?mi)^\s*(?:https?://(?:www\.)?(?:mhc\.tn\.gov\.in/judis|judis\.nic\.in|indiankanoon\.org|sci\.gov\.in|ecourts\.gov\.in)\S*|www\.\S+)\s*$"
)
_RE_PAGE_DIVIDERS = re.compile(r"(?mi)^\s*(?:_{3,}|-{3,}|\={3,}|\*{3,})\s*$")

# Date / Coram / Bench header block lines
_RE_CORAM_HEADERS = re.compile(
    r"(?mi)^\s*(?:CORAM\s*:\s*|BEFORE\s+THE\s+(?:HON'BLE|MADURAI|HIGH\s+COURT|SUPREME\s+COURT)[^\n]*)$"
)
_RE_RESERVED_DELIVERED = re.compile(
    r"(?mi)^\s*(?:RESERVED\s+ON|DELIVERED\s+ON|PRONOUNCED\s+ON|DATED)\s*:\s*[\d\.\-\/\w\s]+$"
)

# Indian Kanoon header metadata lines
_RE_IK_METADATA = re.compile(
    r"(?mi)^\s*(?:Author\s*:\s*[^<\n]+|Bench\s*:\s*[^<\n]+|Equivalent\s+citations\s*:\s*[^<\n]+)\s*$"
)

# Counsel / Appearance block lines (conservatively matching line-starts only)
_RE_COUNSEL_BLOCKS = re.compile(
    r"(?mi)^\s*(?:For\s+(?:the\s+)?(?:Appellant|Respondent|Petitioner|Accused|State|Revisionist|Applicant|Defendants?)(?:\([sS]\))?\s*:\s*.*|"
    r"Counsel\s+for\s+(?:the\s+)?(?:Appellant|Respondent|Petitioner|Accused|State|Revisionist|Applicant|Defendants?)(?:\([sS]\))?\s*:\s*.*|"
    r"Advocate\s+for\s+(?:the\s+)?(?:Appellant|Respondent|Petitioner|Accused|State)(?:\([sS]\))?\s*:\s*.*|"
    r"Appearance\s*:\s*.*|"
    r"Appearing\s+for\s+(?:the\s+)?(?:Appellant|Respondent|Petitioner|State|Accused)\s*:\s*.*|"
    r"(?:Mr\.|Ms\.|Mrs\.|Dr\.)\s+[A-Z][a-zA-Z\.\s]+,\s*(?:learned\s+)?(?:Senior\s+)?(?:Advocate|Counsel|Public\s+Prosecutor|Addl\.\s*Public\s+Prosecutor|Spl\.\s*P\.P\.)\s+for\s+.*)$"
)

# Standalone judge signature / closing metadata
_RE_CLOSING_SIGNATURES = re.compile(
    r"(?mi)^\s*(?:Sd/-\s*(?:Judge|Registrar|Court\s+Master)?|\(\s*[A-Z]\.[A-Z]\.[A-Z]?\.,\s*J\.\s*\)\s*(?:\(\s*[A-Z]\.[A-Z]\.[A-Z]?\.,\s*J\.\s*\))?)\s*$"
)


def clean_judgment_text(raw_text: str) -> tuple[str, dict[str, Any]]:
    """Clean legal judgment text conservatively while capturing detailed metadata.

    Args:
        raw_text: The original judgment text (may contain HTML, OCR lines, etc.)

    Returns:
        tuple of (cleaned_text, metadata_dict)
    """
    original_length = len(raw_text)
    if not raw_text or not raw_text.strip():
        empty_meta = {
            "original_length": original_length,
            "cleaned_length": 0,
            "removed_length": original_length,
            "retention_ratio": 0.0,
            "cleaning_version": CLEANING_VERSION,
            "cleaning_method": CLEANING_METHOD,
            "cleaned_at": datetime.now(UTC).isoformat(),
            "warnings": ["Input text was empty or whitespace only"],
        }
        return "", empty_meta

    # 1. Unescape HTML entities (&amp;, &nbsp;, &#39;, etc.)
    text = html.unescape(raw_text)

    # 2. Convert block HTML tags to newlines to preserve structural spacing
    text = re.sub(r"<(?:p|br|div|tr|h[1-6]|pre|blockquote)[^>]*>", "\n", text, flags=re.IGNORECASE)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # 3. Normalize page breaks and form feed characters
    text = text.replace("\x0c", "\n").replace("\f", "\n").replace("\r\n", "\n").replace("\r", "\n")

    # 4. Remove court URLs, repeated page dividers, and page numbers
    text = _RE_PAGE_DIVIDERS.sub("", text)
    text = _RE_COURT_URLS.sub("", text)
    text = _RE_PAGE_NUMBERS.sub("", text)

    # 5. Remove Coram / Bench / Reserved date headers
    text = _RE_CORAM_HEADERS.sub("", text)
    text = _RE_RESERVED_DELIVERED.sub("", text)
    text = _RE_IK_METADATA.sub("", text)

    # 6. Remove standalone appearance / counsel blocks
    text = _RE_COUNSEL_BLOCKS.sub("", text)

    # 7. Remove closing signature lines
    text = _RE_CLOSING_SIGNATURES.sub("", text)

    # 8. Clean line-by-line whitespace
    cleaned_lines: list[str] = []
    for line in text.split("\n"):
        # Collapse multiple horizontal tabs/spaces to single space
        normalized_line = re.sub(r"[ \t]+", " ", line).strip()
        cleaned_lines.append(normalized_line)

    # 9. Collapse multiple empty lines into at most double newline (paragraph boundary)
    intermediate = "\n".join(cleaned_lines)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", intermediate).strip()

    cleaned_length = len(cleaned_text)
    removed_length = original_length - cleaned_length
    retention_ratio = round(cleaned_length / original_length, 4) if original_length > 0 else 1.0

    warnings: list[str] = []
    if retention_ratio < 0.20:
        warnings.append(
            f"Retention ratio unusually low ({retention_ratio:.2%}): verify text is not over-cleaned"
        )
    elif retention_ratio > 0.99 and original_length > 500:
        warnings.append(
            f"Retention ratio very high ({retention_ratio:.2%}): minimal boilerplate detected"
        )

    metadata: dict[str, Any] = {
        "original_length": original_length,
        "cleaned_length": cleaned_length,
        "removed_length": removed_length,
        "retention_ratio": retention_ratio,
        "cleaning_version": CLEANING_VERSION,
        "cleaning_method": CLEANING_METHOD,
        "cleaned_at": datetime.now(UTC).isoformat(),
        "warnings": warnings,
    }

    return cleaned_text, metadata


def clean(original_text: str) -> str:
    """Convenience functional wrapper returning cleaned text directly."""
    cleaned, _ = clean_judgment_text(original_text)
    return cleaned
