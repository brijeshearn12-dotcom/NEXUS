"""Canonical Entity model for NEXUS."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.models.base import NexusBaseModel
from app.models.enums import VerificationStatus
from app.models.provenance import Provenance


class Entity(NexusBaseModel):
    """Named entity (e.g. accused person, organization, location) with provenance tracking."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique string identifier for the entity",
    )
    case_id: str = Field(
        ...,
        description="ID of the case this entity is associated with",
    )
    document_id: str | None = Field(
        default=None,
        description="ID of the source document this entity was extracted from",
    )
    name: str = Field(
        ...,
        description="Canonical or resolved name of the entity",
    )
    entity_type: str = Field(
        ...,
        description="Type of entity (e.g. person, organization, location, unknown)",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Known aliases, nick-names, or alternative spellings",
    )
    provenance: Provenance = Field(
        ...,
        description="Provenance of how and where this entity was extracted",
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.UNVERIFIED,
        description="Verification state: unverified, confirmed, or rejected",
    )
    evidence_snippet: str | None = Field(
        default=None,
        description="Exact context snippet from source document validating this entity",
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
        description="Optional additional attributes (e.g. legal role, charges)",
    )
