"""Canonical Edge model for NEXUS criminal network graphs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.models.base import NexusBaseModel
from app.models.enums import VerificationStatus
from app.models.provenance import Provenance


class Edge(NexusBaseModel):
    """Directed or undirected relationship between entities with provenance and verification."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique string identifier for the edge",
    )
    case_id: str = Field(
        ...,
        description="ID of the case this relationship belongs to",
    )
    source_entity_id: str = Field(
        ...,
        description="ID of the source entity",
    )
    target_entity_id: str = Field(
        ...,
        description="ID of the target entity",
    )
    relationship_type: str = Field(
        ...,
        description="Type of relationship (e.g. co_accused, communicated_with, financed, instructed)",
    )
    provenance: Provenance = Field(
        ...,
        description="Provenance of how and where this relationship was discovered",
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.UNVERIFIED,
        description="Verification state: unverified, confirmed, or rejected",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last update timestamp",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional relationship-specific confidence score (0.0-1.0)",
    )
    evidence: str | None = Field(
        default=None,
        description="Optional supporting textual or documentary evidence snippet",
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional extensible relationship attributes",
    )
