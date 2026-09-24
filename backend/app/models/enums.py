"""Canonical enums for the NEXUS system."""

from __future__ import annotations

from enum import StrEnum


class VerificationStatus(StrEnum):
    """Canonical verification status for all provenance-aware NEXUS models.

    Allowed values:
    - unverified
    - confirmed
    - rejected
    """

    UNVERIFIED = "unverified"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ProvenanceTier(StrEnum):
    """Trust/source tier for provenance."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    SYNTHETIC = "synthetic"


class ProvenanceMethod(StrEnum):
    """Method by which data or relationships were obtained."""

    DIRECT_TEXT = "direct_text"
    API = "api"
    PDF_EXTRACTION = "pdf_extraction"
    MANUAL = "manual"
    MODEL_EXTRACTION = "model_extraction"
    DERIVED = "derived"
    REGEX_PHONE = "regex_phone"
    REGEX_VEHICLE = "regex_vehicle"
    REGEX_FIR = "regex_fir"
    REGEX_CASE_NUMBER = "regex_case_number"
    SPACY_NER = "spacy_ner"
    ACCUSED_PATTERN = "accused_pattern"
    GEMINI_FALLBACK = "gemini_fallback"
