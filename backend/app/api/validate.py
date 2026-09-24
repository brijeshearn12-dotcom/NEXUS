"""Validate router — Noordin Top network validation harness."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.services.validation.noordin_loader import run_noordin_validation

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    summary="Execute Noordin Top dark network validation harness",
    response_description="Empirical agreement between NEXUS graph analytics and documented academic ground truth.",
)
@router.get(
    "/",
    summary="Execute Noordin Top dark network validation harness",
    include_in_schema=False,
)
async def validate_noordin_endpoint(
    top_k: int = Query(
        default=5,
        ge=1,
        le=50,
        description="Top-K cutoff for measuring agreement with documented key network figures.",
    ),
) -> dict[str, Any]:
    """Validate NEXUS Task 5.1 graph analytics pipeline against the documented Noordin Top dark network dataset.

    Reuses the exact same centrality, community detection, and combined ranking algorithms
    without modifying formulas or weights.
    Returns:
    - Dataset provenance and academic references (Roberts & Everton / ICG Report No. 114)
    - Documented ground-truth key figures
    - Ranking results, matched figures, and empirical agreement score
    - Louvain communities and centrality distributions
    - Documented validation limitations and legal notice
    """
    try:
        res = run_noordin_validation(top_k=top_k)
        if res.get("status") == "ok":
            try:
                from datetime import UTC, datetime

                from app.core.db import get_db

                db = get_db()
                db.validation_runs.insert_one({
                    "dataset": "noordin_top",
                    "top_k": res["top_k"],
                    "matches": res["matches"],
                    "score": f"{res['matches']}/{res['top_k']}",
                    "score_str": res["score"],
                    "score_percentage": res.get("score_percentage", 0.0),
                    "created_at": datetime.now(UTC),
                })
            except Exception as db_err:
                logger.warning("Could not persist validation run to db: %s", db_err)
        return res
    except Exception as exc:
        logger.error("Noordin validation execution failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation execution failed: {str(exc)}",
        ) from exc


class ActionValidationRequest(BaseModel):
    entity_id: str | None = None
    flag_id: str | None = None
    edge_id: str | None = None
    case_id: str | None = None
    notes: str | None = None
    analyst_id: str | None = None


@router.post("/confirm", summary="Confirm entity, edge, or flag verification")
async def confirm_item(payload: ActionValidationRequest) -> dict[str, Any]:
    """Approve/confirm an unverified entity, edge, or pattern flag."""
    return await _process_action(payload, "confirmed")


@router.post("/reject", summary="Reject entity, edge, or flag verification")
async def reject_item(payload: ActionValidationRequest) -> dict[str, Any]:
    """Reject an unverified entity, edge, or pattern flag."""
    return await _process_action(payload, "rejected")


async def _process_action(payload: ActionValidationRequest, new_status: str) -> dict[str, Any]:
    from datetime import UTC, datetime

    from app.core.db import get_db

    db = get_db()
    now_utc = datetime.now(UTC)
    actor = payload.analyst_id or "analyst_human"

    if payload.entity_id:
        ent = db.entities.find_one({"id": payload.entity_id})
        if not ent:
            raise HTTPException(status_code=404, detail=f"Entity '{payload.entity_id}' not found.")
        db.entities.update_one(
            {"id": payload.entity_id},
            {"$set": {"verification_status": new_status, "updated_at": now_utc}},
        )
        db.audit_log.insert_one({
            "case_id": ent.get("case_id", "unknown"),
            "actor": actor,
            "action": f"{new_status}_entity",
            "timestamp": now_utc,
            "entity_type": "entity",
            "entity_id": payload.entity_id,
            "verification_status": new_status,
        })
        return {"status": "ok", "target_type": "entity", "id": payload.entity_id, "verification_status": new_status}

    if payload.flag_id:
        flag = db.flags.find_one({"id": payload.flag_id})
        if not flag:
            raise HTTPException(status_code=404, detail=f"Flag '{payload.flag_id}' not found.")
        db.flags.update_one(
            {"id": payload.flag_id},
            {"$set": {"verification_status": new_status, "updated_at": now_utc}},
        )
        db.audit_log.insert_one({
            "case_id": flag.get("case_id", payload.case_id or "unknown"),
            "actor": actor,
            "action": f"{new_status}_flag",
            "timestamp": now_utc,
            "entity_type": "flag",
            "entity_id": payload.flag_id,
            "verification_status": new_status,
        })
        return {"status": "ok", "target_type": "flag", "id": payload.flag_id, "verification_status": new_status}

    if payload.edge_id:
        edge = db.edges.find_one({"id": payload.edge_id})
        if not edge:
            raise HTTPException(status_code=404, detail=f"Edge '{payload.edge_id}' not found.")
        db.edges.update_one(
            {"id": payload.edge_id},
            {"$set": {"verification_status": new_status, "updated_at": now_utc}},
        )
        db.audit_log.insert_one({
            "case_id": edge.get("case_id", "unknown"),
            "actor": actor,
            "action": f"{new_status}_edge",
            "timestamp": now_utc,
            "entity_type": "edge",
            "entity_id": payload.edge_id,
            "verification_status": new_status,
        })
        return {"status": "ok", "target_type": "edge", "id": payload.edge_id, "verification_status": new_status}

    raise HTTPException(status_code=422, detail="Provide at least one of entity_id, flag_id, or edge_id.")

