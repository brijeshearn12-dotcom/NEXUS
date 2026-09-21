"""Entities router — Query and inspect accepted entities in NEXUS."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.core.db import get_collection

router = APIRouter()


@router.get("/", response_model=dict[str, Any], status_code=status.HTTP_200_OK)
async def list_entities(
    case_id: str | None = Query(default=None, description="Filter by case ID"),
    document_id: str | None = Query(default=None, description="Filter by document ID"),
    entity_type: str | None = Query(default=None, description="Filter by entity type"),
    verification_status: str | None = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List extracted entities with optional filtering by case, document, type, or status."""
    db_entities = get_collection("entities")
    query_filter: dict[str, Any] = {}

    if case_id:
        query_filter["case_id"] = case_id
    if document_id:
        query_filter["document_id"] = document_id
    if entity_type:
        query_filter["entity_type"] = entity_type.upper()
    if verification_status:
        query_filter["verification_status"] = verification_status.lower()

    total = db_entities.count_documents(query_filter)
    cursor = db_entities.find(query_filter, {"_id": 0}).skip(skip).limit(limit)
    items = list(cursor)

    return {
        "total": total,
        "limit": limit,
        "skip": skip,
        "items": items,
    }


@router.get("/{entity_id}", response_model=dict[str, Any], status_code=status.HTTP_200_OK)
async def get_entity(entity_id: str) -> dict[str, Any]:
    """Retrieve a single entity by its unique ID."""
    db_entities = get_collection("entities")
    entity = db_entities.find_one({"id": entity_id}, {"_id": 0})
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found with ID: {entity_id}",
        )
    return entity
