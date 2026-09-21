"""Canonical Case model for NEXUS criminal network analysis."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.models.base import NexusBaseModel
from app.models.enums import VerificationStatus
from app.models.provenance import Provenance


class Case(NexusBaseModel):
    """Investigation case container holding documents, entities, and edges."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique string identifier for the case",
    )
    case_id: str = Field(
        ...,
        description="Canonical human-readable or system case reference identifier",
    )
    title: str = Field(
        ...,
        description="Title or caption of the criminal case",
    )
    description: str | None = Field(
        default=None,
        description="Summary or scope of the investigation",
    )
    provenance: Provenance = Field(
        ...,
        description="Source provenance for the case definition",
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
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional case metadata (e.g. court, jurisdiction, FIR numbers)",
    )
