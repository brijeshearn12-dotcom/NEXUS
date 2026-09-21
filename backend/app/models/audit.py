"""Canonical AuditLogEntry model for NEXUS verification and provenance audit trail."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.models.base import NexusBaseModel
from app.models.enums import VerificationStatus
from app.models.provenance import Provenance


class AuditLogEntry(NexusBaseModel):
    """Provenance and verification audit log record.

    Tracks all user and system modifications to graph entities, relationships,
    and verification states without storing full judgment text or secrets.
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique string identifier for the audit record",
    )
    case_id: str = Field(
        ...,
        description="Case ID associated with the audited action",
    )
    actor: str = Field(
        ...,
        description="User, analyst, or automated agent performing the action (e.g. analyst_42, system_extractor)",
    )
    action: str = Field(
        ...,
        description="Action performed (e.g. confirm_entity, reject_edge, update_verification_status)",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the action took place",
    )
    input_summary: str | dict[str, Any] = Field(
        ...,
        description="Concise summary of input data/payload (no sensitive keys or large documents)",
    )
    result_summary: str | dict[str, Any] = Field(
        ...,
        description="Concise summary of action outcome or state transition",
    )
    entity_type: str | None = Field(
        default=None,
        description="Optional entity or target object type (e.g. person, edge, flag)",
    )
    entity_id: str | None = Field(
        default=None,
        description="Optional target entity/edge/flag string identifier",
    )
    provenance: Provenance | None = Field(
        default=None,
        description="Optional provenance snapshot for the audited item",
    )
    verification_status: VerificationStatus | None = Field(
        default=None,
        description="Optional verification status involved in the action",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional contextual audit metadata",
    )
