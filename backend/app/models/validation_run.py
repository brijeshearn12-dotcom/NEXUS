"""Canonical ValidationRun model for NEXUS ground-truth evaluation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.models.base import NexusBaseModel
from app.models.enums import VerificationStatus
from app.models.provenance import Provenance


class ValidationRun(NexusBaseModel):
    """Validation run tracking performance against benchmark ground truth (e.g. Noordin Top)."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique string identifier for the validation run",
    )
    case_id: str | None = Field(
        default=None,
        description="Optional case ID if benchmark relates to a specific case",
    )
    dataset_ref: str = Field(
        ...,
        description="Dataset reference identifier (e.g. noordin_top_edges.csv)",
    )
    validation_type: str = Field(
        ...,
        description="Type of validation (e.g. ground_truth_comparison, edge_recall, entity_f1)",
    )
    status: str = Field(
        default="pending",
        description="Execution status of validation run (e.g. pending, running, completed, failed)",
    )
    provenance: Provenance = Field(
        ...,
        description="Provenance of benchmark dataset and evaluation configuration",
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.UNVERIFIED,
        description="Verification state: unverified, confirmed, or rejected",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when validation run was initiated",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Timestamp when validation run completed",
    )
    result_summary: dict[str, Any] | str | None = Field(
        default=None,
        description="Summary metrics or evaluation results (e.g. precision, recall, f1)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional detailed configuration or benchmark metadata",
    )
