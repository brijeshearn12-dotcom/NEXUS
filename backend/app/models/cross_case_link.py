"""CrossCaseLink model — an analyst-reviewable CANDIDATE match between two judgments.

A cross-case link is a proposal, never an identity merge. It is stored in its own
`cross_case_links` collection and is never written to `entity_merges`, `entities`,
`edges` or `flags`, so per-case graphs, rankings and flags are unaffected by it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.models.base import NexusBaseModel

CROSS_CASE_DISCLAIMER = (
    "Candidate match proposed for analyst review. It does not establish identity, "
    "involvement or guilt."
)
CROSS_CASE_SCORE_NOTE = (
    "Heuristic points used only to order candidates. Not a probability and not a "
    "measure of identity."
)


class CrossCaseLinkStatus(StrEnum):
    """Review state of a candidate cross-case match."""

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class CrossCaseSide(NexusBaseModel):
    """One side of a candidate match: the source judgment and the matched entity in it."""

    case_id: str = Field(..., description="Case containing the matched entity")
    document_id: str = Field(..., description="Source judgment document ID")
    document_title: str | None = Field(default=None, description="Source judgment title")
    source_url: str | None = Field(default=None, description="Public link to the source judgment")
    court: str | None = Field(default=None, description="Court that issued the judgment")
    date: str | None = Field(default=None, description="Judgment date")
    entity_id: str = Field(..., description="Canonical (per-case) entity ID of the matched person")
    entity_name: str = Field(..., description="Canonical entity name within its case")
    entity_type: str = Field(..., description="Entity type (PERSON / ACCUSED)")
    matched_name_form: str = Field(..., description="Name form that satisfied the strict name rule")
    is_accused_in_case: bool = Field(
        default=False, description="Whether the per-case pipeline marked this entity as accused"
    )
    participant_mention_count: int = Field(
        ..., description="Mentions outside citation, legal-role and witness contexts"
    )
    citation_mention_count: int = Field(
        default=0, description="Mentions ignored because they sit inside a case-law citation"
    )
    evidence_passage: str = Field(..., description="Verbatim passage from the judgment")
    evidence_start_char: int = Field(..., description="Start offset of the mention in the judgment text")
    evidence_end_char: int = Field(..., description="End offset of the mention in the judgment text")
    extraction_evidence_snippet: str | None = Field(
        default=None, description="Evidence snippet recorded by the existing extraction pipeline"
    )
    extraction_provenance: dict[str, Any] | None = Field(
        default=None, description="The entity's existing provenance record (reused as-is)"
    )


class CorroborationItem(NexusBaseModel):
    """A reason, beyond the name, for proposing the match."""

    kind: str = Field(
        ...,
        description="fir_police_station | vehicle | phone | shared_participant",
    )
    value: str = Field(..., description="Normalized matching value")
    description: str = Field(..., description="Human-readable explanation")
    evidence_a: str | None = Field(default=None, description="Supporting passage from judgment A")
    evidence_b: str | None = Field(default=None, description="Supporting passage from judgment B")


class CrossCaseReviewEvent(NexusBaseModel):
    """One analyst decision on a candidate match."""

    status: str
    previous_status: str
    analyst_id: str
    notes: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CrossCaseLink(NexusBaseModel):
    """Candidate cross-case match between an entity in judgment A and one in judgment B."""

    link_id: str = Field(..., description="Stable, deterministic identifier for the candidate pair")
    status: CrossCaseLinkStatus = Field(default=CrossCaseLinkStatus.PROPOSED)
    side_a: CrossCaseSide
    side_b: CrossCaseSide
    name_match_basis: str = Field(..., description="exact_normalized_name | initials_match")
    name_similarity: float = Field(..., ge=0.0, le=1.0)
    corroboration: list[CorroborationItem] = Field(default_factory=list)
    match_strength: str = Field(..., description="strong (shared identifier) | moderate (shared participants)")
    match_score: int = Field(..., ge=0, description=CROSS_CASE_SCORE_NOTE)
    score_breakdown: list[str] = Field(default_factory=list)
    score_note: str = Field(default=CROSS_CASE_SCORE_NOTE)
    reasons: list[str] = Field(default_factory=list, description="Why this candidate was proposed")
    disclaimer: str = Field(default=CROSS_CASE_DISCLAIMER)
    matcher_version: str
    analyst_notes: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_history: list[CrossCaseReviewEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_matched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
