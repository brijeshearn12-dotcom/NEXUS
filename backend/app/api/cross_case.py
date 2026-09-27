"""Cross-case candidate matches API (behind the ENABLE_CROSS_CASE feature flag).

NEXUS proposes. The investigator verifies. Candidate matches never merge identities and
never change per-case graphs, rankings or flags.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.db import get_db
from app.models.cross_case_link import CROSS_CASE_DISCLAIMER
from app.services.cross_case.matcher import (
    get_cross_case_link,
    list_cross_case_links,
    review_cross_case_link,
    run_cross_case_matching,
)
from app.services.cross_case.safeguards import MATCHER_VERSION

logger = logging.getLogger(__name__)

router = APIRouter()

PRINCIPLE = "NEXUS proposes. The investigator verifies."


def _require_enabled() -> None:
    if not settings.enable_cross_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cross-case matching is disabled on this server (set ENABLE_CROSS_CASE=true to enable).",
        )


class CrossCaseReviewRequest(BaseModel):
    status: str | None = Field(None, description="'confirmed', 'rejected' or 'proposed'")
    verification_status: str | None = Field(None, description="Alias for status")
    notes: str | None = Field(None, description="Optional analyst notes")
    analyst_id: str | None = Field(None, description="Analyst identifier")


@router.get("/status", summary="Cross-case matching feature status")
async def cross_case_status() -> dict[str, Any]:
    return {
        "enabled": bool(settings.enable_cross_case),
        "matcher_version": MATCHER_VERSION,
        "principle": PRINCIPLE,
        "disclaimer": CROSS_CASE_DISCLAIMER,
    }


@router.post("/run", summary="Find candidate cross-case matches across the corpus")
async def run_matching() -> dict[str, Any]:
    _require_enabled()
    try:
        return run_cross_case_matching(database=get_db())
    except Exception as err:
        logger.error("Cross-case matching failed: %s", err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cross-case matching failed: {type(err).__name__}",
        ) from err


@router.get("/links", summary="List candidate cross-case matches")
async def list_links(
    status_filter: str | None = Query(default=None, alias="status"),
    case_id: str | None = Query(default=None),
) -> dict[str, Any]:
    _require_enabled()
    items = list_cross_case_links(status=status_filter, case_id=case_id, database=get_db())
    return {"total": len(items), "principle": PRINCIPLE, "items": items}


@router.get("/links/{link_id}", summary="Get one candidate cross-case match")
async def get_link(link_id: str) -> dict[str, Any]:
    _require_enabled()
    link = get_cross_case_link(link_id, database=get_db())
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Cross-case link not found: {link_id}")
    return link


@router.get("/cases/{case_id}", summary="Candidate cross-case matches involving a case")
async def links_for_case(case_id: str) -> dict[str, Any]:
    _require_enabled()
    items = list_cross_case_links(case_id=case_id, database=get_db())
    return {"case_id": case_id, "total": len(items), "principle": PRINCIPLE, "items": items}


@router.patch("/links/{link_id}/verify", summary="Confirm or reject a candidate cross-case match")
async def verify_link(link_id: str, payload: CrossCaseReviewRequest) -> dict[str, Any]:
    _require_enabled()
    target = payload.status or payload.verification_status
    if not target:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field 'status' (or 'verification_status') is required.",
        )
    try:
        return review_cross_case_link(
            link_id=link_id,
            status=target,
            notes=payload.notes,
            analyst_id=payload.analyst_id,
            database=get_db(),
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except LookupError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
