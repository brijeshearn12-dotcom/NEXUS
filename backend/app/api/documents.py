"""Documents router — Query, inspect, and extract entities from corpus documents."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.core.db import get_collection
from app.services.extraction.service import extract_and_store_document

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/{id}/extract",
    summary="Extract entities from a specific document",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def extract_document_endpoint(
    id: str,
    enable_gemini_fallback: bool = Query(
        default=True,
        description="Whether to permit Gemini fallback if yield is low or Hindi text is detected",
    ),
) -> dict[str, Any]:
    """Retrieve document from MongoDB, run extraction pipeline, upsert entities, and log audit."""
    if not id or not id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document ID must not be empty.",
        )

    clean_id = id.strip()
    try:
        result = extract_and_store_document(
            document_id=clean_id,
            enable_gemini_fallback=enable_gemini_fallback,
        )
        return result
    except ValueError as val_err:
        err_msg = str(val_err)
        if "not found" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            ) from val_err
        elif "empty text" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err_msg,
            ) from val_err
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err_msg,
            ) from val_err
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Extraction failed on document %s: %s", clean_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction pipeline encountered an internal error: {str(exc)}",
        ) from exc


@router.get(
    "",
    summary="List corpus documents with extraction status",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/",
    summary="List corpus documents with extraction status",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_documents_endpoint(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    case_id: str | None = Query(None, description="Filter by case ID"),
    extraction_status: str | None = Query(
        None, description="Filter by status: 'extracted' or 'pending'"
    ),
) -> dict[str, Any]:
    """Return paginated list of documents with metadata and real entity counts."""
    db_docs = get_collection("documents")
    db_entities = get_collection("entities")

    filter_query: dict[str, Any] = {}
    if case_id:
        filter_query["case_id"] = case_id

    total = db_docs.count_documents(filter_query)
    skip = (page - 1) * limit

    cursor = (
        db_docs.find(
            filter_query,
            projection={
                "id": 1,
                "case_id": 1,
                "title": 1,
                "court": 1,
                "date": 1,
                "source_ref": 1,
                "source_url": 1,
                "text": 1,
                "verification_status": 1,
                "created_at": 1,
                "updated_at": 1,
                "_id": 0,
            },
        )
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )

    items = []
    for doc in cursor:
        doc_id = doc["id"]
        text = doc.get("text", "")
        text_len = len(text)
        entities_count = db_entities.count_documents({"document_id": doc_id})
        status_val = "extracted" if entities_count > 0 else "pending"

        if extraction_status and status_val != extraction_status.lower():
            continue

        item = {
            "id": doc_id,
            "case_id": doc.get("case_id"),
            "title": doc.get("title", f"Document {doc_id}"),
            "court": doc.get("court"),
            "date": doc.get("date"),
            "source_ref": doc.get("source_ref"),
            "source_url": doc.get("source_url"),
            "text_length": text_len,
            "entities_count": entities_count,
            "extraction_status": status_val,
            "verification_status": doc.get("verification_status", "unverified"),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
        }
        items.append(item)

    return {
        "items": items,
        "page": page,
        "limit": limit,
        "total": total,
    }


@router.get(
    "/{id}",
    summary="Get document details by ID",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def get_document_endpoint(id: str) -> dict[str, Any]:
    """Retrieve full document details with cleaned text, metadata, and entity count."""
    db_docs = get_collection("documents")
    db_entities = get_collection("entities")

    doc = db_docs.find_one(
        {"$or": [{"id": id}, {"source_ref": id}]},
        projection={"_id": 0},
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{id}' not found.",
        )

    doc_id = doc["id"]
    entities_count = db_entities.count_documents({"document_id": doc_id})
    doc["entities_count"] = entities_count
    doc["extraction_status"] = "extracted" if entities_count > 0 else "pending"
    return doc
