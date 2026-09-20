"""Provenance model — canonical provenance fields for entities and edges."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    source_doc_id: str = Field(..., description="MongoDB ObjectId string of the source document")
    source_text: str = Field(
        ..., description="Exact quoted text from which this item was extracted"
    )
    page: int | None = Field(
        None, description="Page number within the source document, if available"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence (0.0-1.0)")
    method: Literal["regex", "spacy", "llm", "manual"] = Field(
        ..., description="Extraction method used"
    )
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    validated_by: str | None = Field(None, description="Analyst identifier who validated this item")
    validated_at: datetime | None = Field(None)
