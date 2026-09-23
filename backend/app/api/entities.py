"""Entities router — Query and inspect accepted entities in NEXUS."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.db import get_collection

router = APIRouter()


@router.get("", response_model=dict[str, Any], status_code=status.HTTP_200_OK)
@router.get("/", response_model=dict[str, Any], status_code=status.HTTP_200_OK, include_in_schema=False)
async def list_entities(
    case_id: str | None = Query(default=None, description="Filter by case ID"),
    document_id: str | None = Query(default=None, description="Filter by document ID"),
    entity_type: str | None = Query(default=None, description="Filter by entity type"),
    verification_status: str | None = Query(default=None, description="Filter by status"),
    method: str | None = Query(default=None, description="Filter by provenance method"),
    q: str | None = Query(default=None, description="Search by entity name or alias"),
    limit: int = Query(default=50, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List extracted entities with optional filtering by case, document, type, status, method, or name query."""
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
    if method:
        query_filter["provenance.method"] = method
    if q and q.strip():
        safe_q = re.escape(q.strip())
        query_filter["$or"] = [
            {"name": {"$regex": safe_q, "$options": "i"}},
            {"aliases": {"$regex": safe_q, "$options": "i"}},
        ]

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


class EntityVerificationRequest(BaseModel):
    verification_status: str | None = Field(
        None,
        description="Target status: 'confirmed', 'rejected', or 'unverified'",
    )
    status: str | None = Field(
        None,
        description="Alternative alias for verification_status",
    )
    notes: str | None = Field(None, description="Optional verification notes from analyst")
    analyst_id: str | None = Field(None, description="Analyst identifier")


@router.get("/{entity_id}/verify", response_model=dict[str, Any], status_code=status.HTTP_200_OK)
async def get_entity_verification_status(entity_id: str) -> dict[str, Any]:
    """Retrieve current verification state for an entity."""
    db_entities = get_collection("entities")
    entity = db_entities.find_one({"id": entity_id}, {"_id": 0})
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found with ID: {entity_id}",
        )
    return {
        "id": entity_id,
        "entity_id": entity_id,
        "name": entity.get("name"),
        "entity_type": entity.get("entity_type"),
        "verification_status": entity.get("verification_status", "unverified"),
        "updated_at": entity.get("updated_at"),
        "case_id": entity.get("case_id"),
        "provenance": entity.get("provenance"),
    }


@router.patch("/{entity_id}/verify", response_model=dict[str, Any], status_code=status.HTTP_200_OK)
@router.patch("/{entity_id}", response_model=dict[str, Any], status_code=status.HTTP_200_OK)
async def patch_entity_verification(
    entity_id: str,
    payload: EntityVerificationRequest,
) -> dict[str, Any]:
    """Update verification status of an entity ('confirmed', 'rejected', 'unverified').

    Persists directly to MongoDB `entities` and appends an immutable entry to `audit_log`.
    """
    from datetime import UTC, datetime

    db_entities = get_collection("entities")
    db_audit = get_collection("audit_log")

    entity = db_entities.find_one({"id": entity_id})
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found with ID: {entity_id}",
        )

    raw_status = payload.verification_status or payload.status
    if not raw_status:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'verification_status' or 'status' is required.",
        )

    target_status = raw_status.strip().lower()
    if target_status not in {"confirmed", "rejected", "unverified"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification status '{target_status}'. Must be 'confirmed', 'rejected', or 'unverified'.",
        )

    now_utc = datetime.now(UTC)
    actor = payload.analyst_id or "analyst_human"

    db_entities.update_one(
        {"id": entity_id},
        {
            "$set": {
                "verification_status": target_status,
                "updated_at": now_utc,
                "metadata.verification_notes": payload.notes or "",
                "metadata.verified_by": actor,
                "metadata.verified_at": now_utc.isoformat(),
            }
        },
    )

    # Immutable audit trail
    db_audit.insert_one({
        "case_id": entity.get("case_id", "unknown"),
        "actor": actor,
        "action": f"{target_status}_entity",
        "timestamp": now_utc,
        "input_summary": {
            "entity_id": entity_id,
            "entity_name": entity.get("name"),
            "old_status": entity.get("verification_status", "unverified"),
            "new_status": target_status,
            "notes": payload.notes,
        },
        "result_summary": f"Entity '{entity.get('name')}' marked as {target_status}",
        "entity_type": "entity",
        "entity_id": entity_id,
        "verification_status": target_status,
    })

    updated = db_entities.find_one({"id": entity_id}, {"_id": 0})
    return {
        "status": "ok",
        "id": entity_id,
        "name": updated.get("name"),
        "verification_status": target_status,
        "updated_at": now_utc.isoformat(),
        "entity": updated,
    }
