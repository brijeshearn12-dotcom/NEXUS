"""Gemini LLM fallback extraction service for NEXUS.

Invoked ONLY under strict conditions:
- Condition A (Low Yield): deterministic pipeline extracts fewer entities than configured threshold
- Condition B (Devanagari/Hindi): passage contains Devanagari text untreatable by English spaCy

Design:
- Uses existing app.core.config.settings.gemini_api_key
- Direct HTTP call to Google Gemini 2.0 Flash REST endpoint
- Extraction-only prompt forbidding relationship inference or hallucination
- Pydantic response validation and verbatim source-text verification
- Safe graceful degradation: failures or missing keys never crash the pipeline
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.services.extraction.regex_extractors import make_evidence_snippet

logger = logging.getLogger(__name__)

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
)

# Devanagari Unicode range: \u0900 to \u097F
DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")

EXTRACTION_SYSTEM_PROMPT = """You are a strict, objective information extraction system for Indian court records.
Your task is ONLY to extract explicit named entities directly mentioned in the provided text.

Strict Rules:
1. Extract ONLY entities explicitly present in the text: PERSON, ORGANIZATION, LOCATION, VEHICLE, PHONE, FIR, CASE_NUMBER.
2. Do NOT infer criminal guilt, involvement, conspiracy, or innocence.
3. Do NOT infer or generate relationships between entities.
4. Do NOT invent, assume, or hallucinate names, titles, or evidence.
5. Do NOT use outside knowledge.
6. The evidence field MUST be an EXACT, verbatim quotation from the provided text showing where the entity appears.
7. Omit any uncertain or ambiguous entities.

Return a JSON array of objects with the exact schema:
[
  {
    "name": "Canonical Name",
    "entity_type": "PERSON | ORGANIZATION | LOCATION | VEHICLE | PHONE | FIR | CASE_NUMBER",
    "evidence": "Exact verbatim excerpt from text"
  }
]
"""


class GeminiEntityCandidate(BaseModel):
    name: str = Field(..., description="Canonical entity name")
    entity_type: str = Field(..., description="Entity taxonomy type")
    evidence: str = Field(..., description="Verbatim quote from the text")


class GeminiExtractionResponse(BaseModel):
    entities: list[GeminiEntityCandidate] = Field(default_factory=list)


def check_devanagari_presence(text: str, min_chars: int = 20) -> bool:
    """Check whether text contains substantial Devanagari (Hindi) script."""
    matches = DEVANAGARI_REGEX.findall(text)
    return len(matches) >= min_chars


def should_trigger_fallback(
    text: str,
    deterministic_entities: list[dict[str, Any]],
    min_entities_per_1000_chars: float | None = None,
) -> tuple[bool, str | None]:
    """Evaluate whether the Gemini fallback extractor should be triggered.

    Conditions:
    - Condition A (Low Yield): text >= 300 chars, yield < threshold (default 0.5 per 1,000 chars)
    - Condition B (Devanagari text): >= 20 Devanagari characters detected

    Returns:
        (should_trigger, reason_code)
    """
    # Condition B: Devanagari / Hindi presence
    if check_devanagari_presence(text):
        return True, "condition_b_devanagari_text"

    # Condition A: Low deterministic extraction yield
    threshold = (
        min_entities_per_1000_chars
        if min_entities_per_1000_chars is not None
        else settings.low_yield_min_entities_per_1000_chars
    )

    text_len = len(text)
    if text_len >= 300:
        yield_rate = len(deterministic_entities) / (text_len / 1000.0)
        if yield_rate < threshold:
            return True, f"condition_a_low_yield:{yield_rate:.2f}<{threshold:.2f}"

    return False, None


def call_gemini_api(
    prompt: str,
    api_key: str,
    client: httpx.Client | None = None,
    timeout_sec: float = 30.0,
) -> str | None:
    """Call Google Gemini 2.0 Flash REST API synchronously with safe error handling."""
    if not api_key:
        logger.info("Gemini fallback skipped: GEMINI_API_KEY is not configured.")
        return None

    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
        },
    }

    own_client = client is None
    http_client = client or httpx.Client(timeout=timeout_sec)
    try:
        response = http_client.post(GEMINI_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            logger.warning("Gemini returned empty candidates list.")
            return None

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            logger.warning("Gemini response contained no parts.")
            return None

        return parts[0].get("text", "")
    except httpx.HTTPStatusError as err:
        logger.warning(
            "Gemini API returned HTTP status error %s: %s",
            err.response.status_code,
            err.response.text[:200],
        )
        return None
    except Exception as err:
        logger.warning("Gemini API call encountered an error: %s", type(err).__name__)
        return None
    finally:
        if own_client:
            http_client.close()


def parse_and_validate_gemini_json(
    raw_response: str,
    source_text: str,
) -> list[dict[str, Any]]:
    """Parse Gemini's JSON output, validate schema, and enforce exact source-text evidence."""
    if not raw_response or not raw_response.strip():
        return []

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        logger.warning("Gemini output was not valid JSON.")
        return []

    # Handle both top-level list and {"entities": [...]} object wrapper
    entity_list: list[Any] = []
    if isinstance(parsed, list):
        entity_list = parsed
    elif isinstance(parsed, dict):
        if "entities" in parsed and isinstance(parsed["entities"], list):
            entity_list = parsed["entities"]
        else:
            # Maybe single entity or dict of entities
            entity_list = [parsed]

    validated_entities: list[dict[str, Any]] = []

    for item in entity_list:
        if not isinstance(item, dict):
            continue
        try:
            cand = GeminiEntityCandidate(**item)
        except ValidationError:
            continue

        clean_name = cand.name.strip()
        if len(clean_name) <= 1:
            continue

        # Strict Evidence Verification:
        # Check if the evidence snippet is an actual substring of source_text
        evidence = cand.evidence.strip()
        start_char = -1
        end_char = -1

        if evidence and evidence in source_text:
            start_char = source_text.index(evidence)
            end_char = start_char + len(evidence)
            final_snippet = make_evidence_snippet(source_text, start_char, end_char)
        elif clean_name in source_text:
            # Name exists in text, create genuine evidence snippet from text
            start_char = source_text.index(clean_name)
            end_char = start_char + len(clean_name)
            final_snippet = make_evidence_snippet(source_text, start_char, end_char)
        else:
            # Name does not even appear in source text -> reject hallucinated entity
            logger.debug("Rejected Gemini entity not present in source text: %s", clean_name)
            continue

        validated_entities.append(
            {
                "name": clean_name,
                "entity_type": cand.entity_type.upper(),
                "canonical_name": clean_name,
                "start_char": start_char,
                "end_char": end_char,
                "evidence_snippet": final_snippet,
                "method": "gemini_fallback",
                "confidence": 0.80,
                "metadata": {
                    "source": "gemini_2.0_flash",
                    "provided_evidence": cand.evidence,
                },
            }
        )

    return validated_entities


def extract_with_gemini_fallback(
    text: str,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Run extraction via Gemini 2.0 Flash with prompt-level safety and retry on malformed JSON."""
    key = api_key if api_key is not None else settings.gemini_api_key
    if not key:
        logger.info("LLM fallback disabled: GEMINI_API_KEY is not set.")
        return []

    prompt = (
        f"{EXTRACTION_SYSTEM_PROMPT}\n\n"
        f"--- INPUT TEXT ---\n"
        f"{text[:12000]}\n"
        f"--- END INPUT TEXT ---\n\n"
        f"Extract all explicit entities as a JSON array:"
    )

    # Attempt 1
    raw_text = call_gemini_api(prompt, api_key=key, client=client)
    if not raw_text:
        return []

    entities = parse_and_validate_gemini_json(raw_text, text)
    if entities:
        return entities

    # Attempt 2: retry with explicit JSON correction instruction if attempt 1 returned text but 0 valid entities
    logger.info("Retrying Gemini fallback with strict JSON instruction...")
    retry_prompt = (
        f"{prompt}\n\n"
        f"IMPORTANT: Output ONLY a valid JSON list. Example: [{{'name': 'X', 'entity_type': 'PERSON', 'evidence': '...'}}]"
    )
    raw_text_retry = call_gemini_api(retry_prompt, api_key=key, client=client)
    if not raw_text_retry:
        return []

    return parse_and_validate_gemini_json(raw_text_retry, text)
