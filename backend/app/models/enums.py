"""Canonical enums for the NEXUS system."""

from __future__ import annotations

from enum import Enum


class VerificationStatus(str, Enum):
    """Canonical verification status for all provenance-aware NEXUS models.

    Allowed values:
    - unverified
    - confirmed
    - rejected
    """

    UNVERIFIED = "unverified"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ProvenanceTier(str, Enum):
    """Trust/source tier for provenance."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    SYNTHETIC = "synthetic"


class ProvenanceMethod(str, Enum):
    """Method by which data or relationships were obtained."""

    DIRECT_TEXT = "direct_text"
    API = "api"
    PDF_EXTRACTION = "pdf_extraction"
    MANUAL = "manual"
    MODEL_EXTRACTION = "model_extraction"
    DERIVED = "derived"
