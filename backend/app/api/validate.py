"""Validate router — Noordin Top network validation harness."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

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
        return run_noordin_validation(top_k=top_k)
    except Exception as exc:
        logger.error("Noordin validation execution failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation execution failed: {str(exc)}",
        ) from exc
