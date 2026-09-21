"""Cases router — endpoints for case management and manual document ingestion."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.db import get_db
from app.services.corpus_service import ingest_manual_text

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
