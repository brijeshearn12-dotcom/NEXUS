"""Deterministic fact-section segmenter for legal criminal judgments.

Identifies substantive factual narratives (e.g. Prosecution Case, Facts of the Case,
Factual Background, Allegations, Evidence) for targeted entity and network extraction.
Falls back conservatively to full cleaned text if no reliable heading is detected.
"""

from __future__ import annotations

import re
from typing import Any

# Ordered list of factual section headings (specific to general)
FACT_HEADING_PATTERNS = [
    r"facts\s+of\s+the\s+case",
    r"case\s+of\s+the\s+prosecution",
    r"prosecution\s+case",
    r"prosecution\s+story",
    r"factual\s+background",
    r"factual\s+matrix",
    r"brief\s+facts",
    r"summary\s+of\s+allegations",
    r"allegations\b",
    r"prosecution\s+evidence",
    r"investigation\b",
    r"occurrence\b",
    r"background\s+facts",
    r"facts\b",
    r"background\b",
]

# Section boundary patterns where factual narration typically transitions
BOUNDARY_PATTERNS = [
    r"submissions(?:\s+(?:of|by|on\s+behalf\s+of|advanced)[^\n\r]*)?",
    r"arguments(?:\s+(?:of|by|on\s+behalf\s+of|advanced)[^\n\r]*)?",
    r"contentions(?:\s+(?:of|by|on\s+behalf\s+of|raised)[^\n\r]*)?",
    r"points?\s+for\s+(?:determination|consideration)[^\n\r]*",
    r"charges(?:\s+framed)?[^\n\r]*",
    r"findings(?:\s+of\s+the\s+court)?[^\n\r]*",
    r"discussion(?:\s+and\s+findings)?[^\n\r]*",
    r"consideration\b[^\n\r]*",
    r"analysis\b[^\n\r]*",
    r"decision\b[^\n\r]*",
    r"conclusion\b[^\n\r]*",
    r"(?:final\s+)?order\b[^\n\r]*",
]


def segment_facts(cleaned_text: str) -> dict[str, Any]:
    """Segment the primary factual narration from a cleaned judgment.

    Args:
        cleaned_text: The boilerplate-stripped text of the judgment.

    Returns:
        dict containing:
            - section_name: Heading found or 'full_text_fallback'
            - start_position: Character start index in cleaned_text
            - end_position: Character end index in cleaned_text
            - text: Segmented fact narrative text
            - confidence: Float confidence score (0.0 - 1.0)
            - method: 'heading_match' or 'fallback'
    """
    if not cleaned_text or not cleaned_text.strip():
        return {
            "section_name": "empty",
            "start_position": 0,
            "end_position": 0,
            "text": "",
            "confidence": 0.0,
            "method": "empty_input",
        }

    best_match: tuple[int, str, int] | None = None

    for pattern in FACT_HEADING_PATTERNS:
        # Check standalone heading line: e.g. "FACTS OF THE CASE:", "1. Prosecution Case:"
        regex_standalone = re.compile(
            rf"(?mi)^(?:\d+[\.\)]\s*)?({pattern})[\s\:\-\.]*$", re.IGNORECASE
        )
        match = regex_standalone.search(cleaned_text)
        if not match:
            # Check paragraph starter: e.g. "The case of the prosecution is that..."
            regex_inline = re.compile(
                rf"(?mi)^(?:\d+[\.\)]\s*)?({pattern}\s+(?:is|was|states|alleges|commences)\b)",
                re.IGNORECASE,
            )
            match = regex_inline.search(cleaned_text)

        if match:
            best_match = (match.start(), match.group(1), match.end())
            break

    # Fallback if no reliable heading is detected
    if not best_match:
        return {
            "section_name": "full_text_fallback",
            "start_position": 0,
            "end_position": len(cleaned_text),
            "text": cleaned_text,
            "confidence": 0.50,
            "method": "fallback",
        }

    start_idx, heading_text, content_start = best_match

    # Find the nearest subsequent boundary heading that starts after the fact heading
    min_narrative_offset = content_start + 20
    earliest_boundary = len(cleaned_text)

    for boundary_pat in BOUNDARY_PATTERNS:
        b_regex = re.compile(rf"(?mi)^(?:\d+[\.\)]\s*)?({boundary_pat})[\s\:\-\.]*$", re.IGNORECASE)
        for m in b_regex.finditer(cleaned_text, min_narrative_offset):
            line = m.group(0).strip()
            if len(line) <= 120:
                if m.start() < earliest_boundary:
                    earliest_boundary = m.start()

    end_idx = earliest_boundary
    extracted_section_text = cleaned_text[start_idx:end_idx].strip()

    return {
        "section_name": heading_text.strip(),
        "start_position": start_idx,
        "end_position": end_idx,
        "text": extracted_section_text,
        "confidence": 0.85,
        "method": "heading_match",
    }
