"""Corpus router — API endpoints for curated judgment corpus ingestion and browsing."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.core.db import get_db
from app.services.corpus_service import load_curated_corpus
from app.services.extraction.service import extract_all_corpus_documents

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/extract-all",
    summary="Run entity extraction across all documents in the corpus",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def extract_all_corpus_endpoint(
    enable_gemini_fallback: bool = Query(
        default=True,
        description="Whether to permit Gemini fallback if yield is low or Hindi text is detected",
    ),
) -> dict[str, Any]:
    """Execute entity extraction across all eligible documents in the corpus safely and idempotently."""
    try:
        result = extract_all_corpus_documents(
            enable_gemini_fallback=enable_gemini_fallback,
        )
        return result
    except Exception as exc:
        logger.exception("Batch corpus extraction failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch corpus extraction encountered an error: {str(exc)}",
        ) from exc


@router.post(
    "/load",
    summary="Load curated criminal judgment corpus into MongoDB",
    status_code=status.HTTP_200_OK,
)
async def load_corpus_endpoint() -> dict[str, Any]:
    """Ingest the 20 audited curated judgments into MongoDB with boilerplate removal.

    Idempotent: updates existing documents by stable ID without duplicating records.
    """
    try:
        result = load_curated_corpus()
        return result
    except Exception as err:
        logger.error("Corpus loading encountered an error: %s", err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load curated corpus due to an internal server error.",
        ) from err


@router.get(
    "",
    summary="Browse ingested corpus documents",
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/",
    summary="Browse ingested corpus documents",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_corpus(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    verification_status: str | None = Query(None, description="Filter by verification status"),
    case_id: str | None = Query(None, description="Filter by case ID"),
) -> dict[str, Any]:
    """Return lightweight paginated metadata for ingested corpus documents."""
    try:
        db = get_db()
        filter_query: dict[str, Any] = {}
        if verification_status:
            filter_query["verification_status"] = verification_status
        if case_id:
            filter_query["case_id"] = case_id

        total = db.documents.count_documents(filter_query)
        skip = (page - 1) * limit

        cursor = (
            db.documents.find(
                filter_query,
                projection={
                    "id": 1,
                    "case_id": 1,
                    "title": 1,
                    "court": 1,
                    "date": 1,
                    "source_ref": 1,
                    "verification_status": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "cleaning_metadata.retention_ratio": 1,
                    "segmentation_metadata.section_name": 1,
                    "_id": 0,
                },
            )
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        items = list(cursor)
        return {
            "items": items,
            "page": page,
            "limit": limit,
            "total": total,
        }
    except Exception as err:
        logger.error("Error retrieving corpus list: %s", err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve corpus list.",
        ) from err


@router.get(
    "/{doc_id}",
    summary="Get full document by ID",
    status_code=status.HTTP_200_OK,
)
async def get_corpus_document(doc_id: str) -> dict[str, Any]:
    """Retrieve full document details, including cleaned text, extraction segment, and provenance."""
    try:
        db = get_db()
        doc = db.documents.find_one(
            {"$or": [{"id": doc_id}, {"source_ref": doc_id}]},
            projection={"_id": 0},
        )
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{doc_id}' not found.",
            )
        return doc
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Error fetching document %s: %s", doc_id, err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document.",
        ) from err
