"""Cases router — endpoints for case management and manual document ingestion."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.db import get_db
from app.services.corpus_service import ingest_manual_text
from app.services.resolution.alias_resolver import resolve_case_aliases

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_INGEST_TEXT_LENGTH = 5_000_000  # ~5MB character safety limit


class ManualIngestRequest(BaseModel):
    text: str = Field(..., description="Pasted judgment text content")
    title: str | None = Field(None, description="Optional title for the document")
    source_ref: str | None = Field(None, description="Optional source reference or identifier")


@router.get(
    "",
    summary="List cases",
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/",
    summary="List cases",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_cases() -> dict[str, Any]:
    """List cases present in the database."""
    try:
        db = get_db()
        cases = list(db.cases.find({}, projection={"_id": 0}))
        return {"items": cases, "total": len(cases)}
    except Exception as err:
        logger.error("Error listing cases: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list cases.",
        ) from err


@router.post(
    "/{case_id}/ingest",
    summary="Ingest manual judgment text under a case",
    status_code=status.HTTP_201_CREATED,
)
async def ingest_case_document(
    case_id: str,
    payload: ManualIngestRequest,
) -> dict[str, Any]:
    """Clean, segment, and ingest manually provided judgment text under a specific case ID."""
    raw_text = payload.text.strip() if payload.text else ""

    # Validation: empty text check -> 400
    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Judgment text is required and cannot be empty.",
        )

    # Validation: oversized payload check -> 413
    if len(payload.text) > MAX_INGEST_TEXT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"Payload too large. Maximum document text length is {MAX_INGEST_TEXT_LENGTH} characters."
            ),
        )

    try:
        doc = ingest_manual_text(
            case_id=case_id,
            text=payload.text,
            title=payload.title,
            source_ref=payload.source_ref,
        )
        return {
            "status": "created",
            "message": "Document successfully cleaned and ingested.",
            "document": doc.model_dump(by_alias=True),
        }
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        ) from val_err
    except Exception as err:
        logger.error("Failed to ingest document for case %s: %s", case_id, err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest document due to an internal server error.",
        ) from err


class AliasResolutionResponse(BaseModel):
    case_id: str = Field(..., description="ID of the resolved case")
    entities_checked: int = Field(..., description="Number of entities examined")
    candidate_pairs: int = Field(..., description="Number of candidate pairs evaluated after blocking")
    merges_created: int = Field(..., description="Number of additive merges created/stored")
    merges_skipped: int = Field(..., description="Number of candidate pairs skipped due to guardrails or threshold")


@router.post(
    "/{case_id}/resolve",
    summary="Resolve entity aliases within a case",
    response_model=AliasResolutionResponse,
    status_code=status.HTTP_200_OK,
)
async def resolve_case_entities(
    case_id: str,
    threshold: float = Query(
        default=0.85,
        ge=0.5,
        le=1.0,
        description="Conservative similarity threshold for entity merges",
    ),
) -> dict[str, Any]:
    """Execute conservative entity alias resolution for a case.

    Idempotent: merges are recorded additively in `entity_merges` without duplicating records
    or deleting original entities.
    """
    db = get_db()
    case = db.cases.find_one({"case_id": case_id})
    has_entities = db.entities.find_one({"case_id": case_id}) is not None
    if not case and not has_entities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    try:
        stats = resolve_case_aliases(case_id=case_id, threshold=threshold, database=db)
        return stats
    except Exception as err:
        logger.error("Alias resolution error for case %s: %s", case_id, err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Alias resolution failed: {str(err)}",
        ) from err

