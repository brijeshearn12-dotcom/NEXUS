"""Canonical Flag model for NEXUS criminal network analysis."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.models.base import NexusBaseModel
from app.models.enums import VerificationStatus
from app.models.provenance import Provenance


class Flag(NexusBaseModel):
    """Pattern flag or analytical alert with provenance and verification status."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique string identifier for the flag",
    )
    case_id: str = Field(
        ...,
        description="ID of the case this flag is associated with",
    )
    flag_type: str = Field(
        ...,
        description="Type of analytical flag (e.g. communication_burst, high_betweenness_broker, shell_company_flow)",
    )
    description: str = Field(
        ...,
        description="Detailed description of the flagged finding or pattern",
    )
    severity: str = Field(
        ...,
        description="Severity level (e.g. low, medium, high, critical)",
    )
    provenance: Provenance = Field(
        ...,
        description="Provenance of what model/algorithm or heuristic generated this flag",
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.UNVERIFIED,
        description="Verification state: unverified, confirmed, or rejected",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the flag was generated",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional extensible metadata for the flag finding",
    )
