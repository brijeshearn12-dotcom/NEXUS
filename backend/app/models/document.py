"""Canonical Document model for NEXUS."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.models.base import NexusBaseModel
from app.models.enums import VerificationStatus
from app.models.provenance import Provenance


class Document(NexusBaseModel):
    """Cleaned judgment document model with source provenance and verification status."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique string identifier for the document",
    )
    case_id: str = Field(
        ...,
        description="ID of the case this document belongs to",
    )
    title: str = Field(
        ...,
        description="Title of the judgment or legal document",
    )
    text: str = Field(
        ...,
        description="Cleaned judgment or document text content",
    )
    source_ref: str = Field(
        ...,
        description="Original source reference (e.g. tid, file name, URL)",
    )
    provenance: Provenance = Field(
        ...,
        description="Source provenance details",
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
    court: str | None = Field(
        default=None,
        description="Originating court if known (e.g. Supreme Court of India, Madras High Court)",
    )
    date: str | None = Field(
        default=None,
        description="Judgment or document date string (YYYY-MM-DD if available)",
    )
    source_url: str | None = Field(
        default=None,
        description="Public URL for the source judgment",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional corpus manifest or domain metadata",
    )
