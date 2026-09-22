"""Canonical EntityMerge model for NEXUS entity alias resolution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import Field

from app.models.base import NexusBaseModel
from app.models.enums import VerificationStatus


class EntityMerge(NexusBaseModel):
    """Additive, auditable record of an entity merge/alias relationship.

    Never deletes original entities; provides an explicit, reversible linkage.
    """

    merge_id: str = Field(
        default_factory=lambda: f"merge_{uuid.uuid4().hex[:16]}",
        description="Unique string identifier for the merge record",
    )
    canonical_entity_id: str = Field(
        ...,
        description="ID of the canonical entity (surviving/primary representation)",
    )
    alias_entity_id: str = Field(
        ...,
        description="ID of the alias entity linked to canonical",
    )
    case_id: str = Field(
        ...,
        description="Case ID within which the resolution occurred",
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity score strictly between 0.0 and 1.0",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score strictly between 0.0 and 1.0",
    )
    method: str = Field(
        ...,
        description="Method used for alias resolution (e.g. exact_match, initials_match, rapidfuzz)",
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.UNVERIFIED,
        description="Verification state: unverified, confirmed, or rejected",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Creation timestamp",
    )
    source_refs: list[str] = Field(
        default_factory=list,
        description="References to source documents or extraction provenance",
    )
