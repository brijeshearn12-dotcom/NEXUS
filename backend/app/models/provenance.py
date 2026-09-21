"""Canonical Provenance model for NEXUS."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.models.base import NexusBaseModel
from app.models.enums import ProvenanceMethod, ProvenanceTier


class Provenance(NexusBaseModel):
    """Provenance tracking for all extracted or curated entities, edges, and documents."""

    tier: str = Field(
        default=ProvenanceTier.PRIMARY.value,
        description="Trust/source tier (e.g. primary, secondary, synthetic)",
    )
    source_ref: str = Field(
        ...,
        description="Identifier for the source (judgment document ID, URL, dataset reference)",
    )
    method: str = Field(
        default=ProvenanceMethod.DIRECT_TEXT.value,
        description="Method used to obtain the data (e.g. direct_text, api, pdf_extraction, manual, model_extraction, derived)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score strictly between 0.0 and 1.0",
    )
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when provenance was captured",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional extensible metadata for provenance context",
    )
