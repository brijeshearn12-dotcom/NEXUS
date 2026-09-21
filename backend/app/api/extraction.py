"""Extraction API endpoints for NEXUS Day 3.

Endpoints:
- POST /api/extraction/run: Run entity extraction on a single document (or small batch)
- POST /api/extraction/run-batch: Run entity extraction on a specified list of document IDs
- POST /api/extraction/run-all: Idempotent extraction across all documents in the corpus
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.db import get_collection
from app.services.extraction.service import extract_and_store_document

logger = logging.getLogger(__name__)

router = APIRouter()


class ExtractionRunRequest(BaseModel):
    document_id: str | None = Field(default=None, description="Single document ID to process")
    document_ids: list[str] | None = Field(default=None, description="Batch of document IDs to process")
    enable_gemini_fallback: bool = Field(
        default=True,
        description="Whether to permit Gemini fallback if yield is low or Hindi text is detected",
    )


class BatchExtractionResponse(BaseModel):
    total_requested: int
    processed: int
    failed: int
    total_entities_extracted: int
    by_method: dict[str, int]
    failures: list[dict[str, str]]
    results: list[dict[str, Any]]


@router.post("/run", response_model=dict[str, Any], status_code=status.HTTP_200_OK)
async def run_extraction(request: ExtractionRunRequest) -> dict[str, Any]:
    """Execute the extraction pipeline on a specific document (or batch if document_ids provided).

    Retrieves cleaned/segmented judgment, executes deterministic extraction + spaCy + legal filter
    + accused extractor + fallback, upserts entities to MongoDB, and returns extraction statistics.
    """
    if request.document_ids:
        # Batch delegation
        batch_res = await run_extraction_batch(request)
        return batch_res.model_dump(by_alias=True)

    if not request.document_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either 'document_id' or 'document_ids' must be specified in the request body.",
        )

    try:
        result = extract_and_store_document(
            document_id=request.document_id,
            enable_gemini_fallback=request.enable_gemini_fallback,
        )
        return result
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        ) from val_err
    except Exception as exc:
        logger.exception("Extraction failed for document %s: %s", request.document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction pipeline encountered an internal error: {str(exc)}",
        ) from exc


@router.post("/run-batch", response_model=BatchExtractionResponse, status_code=status.HTTP_200_OK)
async def run_extraction_batch(request: ExtractionRunRequest) -> BatchExtractionResponse:
    """Run extraction across a specific list of document IDs safely and independently."""
    doc_ids = request.document_ids or ([request.document_id] if request.document_id else [])
    if not doc_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No document IDs provided for batch extraction.",
        )

    processed = 0
    failed = 0
    total_entities = 0
    by_method: dict[str, int] = {
        "regex_phone": 0,
        "regex_vehicle": 0,
        "regex_fir": 0,
        "regex_case_number": 0,
        "spacy_ner": 0,
        "accused_pattern": 0,
        "gemini_fallback": 0,
    }
    failures: list[dict[str, str]] = []
    results: list[dict[str, Any]] = []

    for doc_id in doc_ids:
        try:
            res = extract_and_store_document(
                document_id=doc_id,
                enable_gemini_fallback=request.enable_gemini_fallback,
            )
            processed += 1
            total_entities += res["entities_extracted"]
            for method, count in res["by_method"].items():
                by_method[method] = by_method.get(method, 0) + count
            results.append(
                {
                    "document_id": doc_id,
                    "case_id": res.get("case_id"),
                    "entities_extracted": res["entities_extracted"],
                    "by_method": res["by_method"],
                    "gemini_used": res["gemini_used"],
                }
            )
        except Exception as err:
            failed += 1
            logger.warning("Batch extraction item failed for doc %s: %s", doc_id, err)
            failures.append({"document_id": doc_id, "error": str(err)})

    return BatchExtractionResponse(
        total_requested=len(doc_ids),
        processed=processed,
        failed=failed,
        total_entities_extracted=total_entities,
        by_method=by_method,
        failures=failures,
        results=results,
    )


@router.post("/run-all", response_model=BatchExtractionResponse, status_code=status.HTTP_200_OK)
async def run_extraction_all(enable_gemini_fallback: bool = True) -> BatchExtractionResponse:
    """Discover all corpus documents in MongoDB and execute extraction idempotently."""
    db_docs = get_collection("documents")
    cursor = db_docs.find({}, {"id": 1})
    all_doc_ids = [doc["id"] for doc in cursor if "id" in doc]

    if not all_doc_ids:
        return BatchExtractionResponse(
            total_requested=0,
            processed=0,
            failed=0,
            total_entities_extracted=0,
            by_method={},
            failures=[],
            results=[],
        )

    batch_req = ExtractionRunRequest(
        document_ids=all_doc_ids,
        enable_gemini_fallback=enable_gemini_fallback,
    )
    return await run_extraction_batch(batch_req)
