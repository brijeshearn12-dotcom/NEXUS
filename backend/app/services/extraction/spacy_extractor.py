"""spaCy NER extraction service for NEXUS legal entity extraction.

Uses en_core_web_sm to extract:
- PERSON -> PERSON
- ORG    -> ORGANIZATION
- GPE    -> LOCATION

Features:
- Process-level model singleton caching
- Clear diagnostic errors if model is unavailable
- Precise character offset preservation
- Contextual evidence snippet generation
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.extraction.regex_extractors import make_evidence_snippet

logger = logging.getLogger(__name__)

# Singleton spaCy NLP pipeline instance
_SPACY_NLP: Any | None = None

# Entity taxonomy mapping from spaCy to NEXUS canonical taxonomy
SPACY_TAXONOMY_MAP = {
    "PERSON": "PERSON",
    "ORG": "ORGANIZATION",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "FAC": "LOCATION",
}


def get_spacy_nlp() -> Any:
    """Return the cached spaCy en_core_web_sm model instance.

    Loads once per process. Raises RuntimeError with clear installation steps
    if the model is missing.
    """
    global _SPACY_NLP
    if _SPACY_NLP is not None:
        return _SPACY_NLP

    try:
        import spacy

        logger.info("Loading spaCy model 'en_core_web_sm'...")
        _SPACY_NLP = spacy.load("en_core_web_sm")
        logger.info("spaCy 'en_core_web_sm' successfully loaded.")
        return _SPACY_NLP
    except ImportError as err:
        raise RuntimeError(
            "spaCy is not installed in the active environment. "
            "Install it via: pip install spacy>=3.8.0"
        ) from err
    except OSError as err:
        try:
            logger.info("en_core_web_sm not found, attempting auto-download via spacy.cli.download...")
            from spacy.cli import download
            download("en_core_web_sm")
            _SPACY_NLP = spacy.load("en_core_web_sm")
            return _SPACY_NLP
        except Exception:
            raise RuntimeError(
                "The spaCy language model 'en_core_web_sm' was not found on this system. "
                "Please download it by executing: python -m spacy download en_core_web_sm"
            ) from err


def extract_spacy_entities(
    text: str,
    nlp: Any | None = None,
) -> list[dict[str, Any]]:
    """Extract PERSON, ORG, and GPE entities from text using spaCy NER.

    Args:
        text: Input cleaned legal judgment or fact text.
        nlp: Optional pre-loaded spaCy model instance.

    Returns:
        List of raw extracted entity candidate dictionaries with provenance metadata.
    """
    if not text or not text.strip():
        return []

    pipeline = nlp or get_spacy_nlp()

    # Limit text length per document if necessary to avoid memory issues with huge docs
    # spaCy default max_length is 1,000,000 chars; adjust if needed
    if len(text) > pipeline.max_length:
        pipeline.max_length = len(text) + 10000

    doc = pipeline(text)
    entities: list[dict[str, Any]] = []

    for ent in doc.ents:
        mapped_type = SPACY_TAXONOMY_MAP.get(ent.label_)
        if not mapped_type:
            continue

        name = ent.text.strip()
        # Discard empty, single-character, or purely numeric tokens
        if len(name) <= 1 or name.isdigit():
            continue

        # Create snippet from surrounding text
        snippet = make_evidence_snippet(text, ent.start_char, ent.end_char)

        entities.append(
            {
                "name": name,
                "entity_type": mapped_type,
                "canonical_name": name,
                "start_char": ent.start_char,
                "end_char": ent.end_char,
                "evidence_snippet": snippet,
                "method": "spacy_ner",
                "confidence": 0.85,
                "metadata": {
                    "raw_spacy_label": ent.label_,
                    "token_count": len(ent),
                    "start_token": ent.start,
                    "end_token": ent.end,
                },
            }
        )

    return entities
