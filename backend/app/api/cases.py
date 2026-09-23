"""Cases router — endpoints for case management and manual document ingestion."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.db import get_db
from app.services.corpus_service import ingest_manual_text
from app.services.graph.builder import build_graph_for_case, get_graph_for_case
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


class BuildGraphResponse(BaseModel):
    case_id: str = Field(..., description="Case identifier")
    nodes: int = Field(..., description="Number of unique nodes in the graph")
    edges_created: int = Field(..., description="Number of new edges created")
    edges_updated: int = Field(..., description="Number of existing edges updated/aggregated")


class CaseGraphResponse(BaseModel):
    nodes: list[dict[str, Any]] = Field(..., description="List of graph nodes with attributes")
    edges: list[dict[str, Any]] = Field(..., description="List of graph edges with weights and provenance")


@router.post(
    "/{case_id}/build-graph",
    summary="Construct relationship graph for a case",
    response_model=BuildGraphResponse,
    status_code=status.HTTP_200_OK,
)
async def build_case_graph_endpoint(case_id: str) -> dict[str, Any]:
    """Build the relationship graph for a case from extracted entities and judgment evidence."""
    db = get_db()
    case = db.cases.find_one({"case_id": case_id})
    has_entities = db.entities.find_one({"case_id": case_id}) is not None
    if not case and not has_entities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    try:
        res = build_graph_for_case(case_id=case_id, database=db)
        return res
    except Exception as err:
        logger.error("Error building graph for case %s: %s", case_id, err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build graph: {str(err)}",
        ) from err


@router.get(
    "/{case_id}/graph",
    summary="Retrieve full relationship graph for a case",
    response_model=CaseGraphResponse,
    status_code=status.HTTP_200_OK,
)
async def get_case_graph_endpoint(case_id: str) -> dict[str, Any]:
    """Retrieve full relationship graph (nodes and edges with provenance and weights) for a case."""
    db = get_db()
    case = db.cases.find_one({"case_id": case_id})
    has_entities = db.entities.find_one({"case_id": case_id}) is not None
    if not case and not has_entities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    try:
        res = get_graph_for_case(case_id=case_id, database=db)
        return res
    except Exception as err:
        logger.error("Error fetching graph for case %s: %s", case_id, err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch graph: {str(err)}",
        ) from err


class CaseAnalysisResponse(BaseModel):
    status: str = Field(..., description="'ok' or 'insufficient_data'")
    case_id: str = Field(..., description="Case identifier")
    reason: str | None = Field(None, description="Explanation when status is insufficient_data")
    ranked_individuals: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Ranked key individuals with centrality metrics and reasoning trails",
    )
    communities: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Louvain communities detected in the network",
    )
    flags: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Rule-based pattern flags with reasoning trails",
    )
    trail: dict[str, Any] | None = Field(
        None,
        description="Graph summary metadata, normalization formula, and legal disclaimer",
    )


@router.get(
    "/{case_id}/analysis",
    summary="Analyze relationship graph: centrality ranking, Louvain communities, and pattern flags",
    response_model=CaseAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
async def get_case_analysis_endpoint(case_id: str) -> dict[str, Any]:
    """Calculate deterministic centrality rankings, Louvain communities, and pattern flags for a case graph.

    Idempotent and strictly evidence-backed:
    - Ranks only verified or plausible PERSON entities using neutral terminology
    - Generates complete reasoning trail (input_refs, evidence, reasoning, result, confidence, source)
    - Returns structured 'insufficient_data' if graph is smaller than minimum thresholds
    """
    from datetime import UTC, datetime

    from app.services.analytics import (
        detect_louvain_communities,
        detect_pattern_flags,
        is_valid_person_entity,
        rank_key_individuals,
    )
    from app.services.analytics.centrality import (
        MIN_GRAPH_EDGES,
        MIN_GRAPH_NODES,
        MIN_PERSON_NODES,
    )
    from app.services.graph.networkx_loader import load_case_graph

    db = get_db()
    case = db.cases.find_one({"case_id": case_id})
    has_entities = db.entities.find_one({"case_id": case_id}) is not None
    if not case and not has_entities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    try:
        G = load_case_graph(case_id=case_id, database=db)
        num_nodes = G.number_of_nodes()
        num_edges = G.number_of_edges()
        person_nodes = [
            n for n, d in G.nodes(data=True)
            if is_valid_person_entity(n, d)
        ]

        # Minimum data guardrails
        if num_nodes < MIN_GRAPH_NODES or num_edges < MIN_GRAPH_EDGES:
            return {
                "status": "insufficient_data",
                "case_id": case_id,
                "reason": (
                    f"Graph has {num_nodes} node(s) and {num_edges} edge(s). "
                    f"Minimum required: {MIN_GRAPH_NODES} nodes and {MIN_GRAPH_EDGES} edges."
                ),
                "ranked_individuals": [],
                "communities": [],
                "flags": [],
            }

        if len(person_nodes) < MIN_PERSON_NODES:
            return {
                "status": "insufficient_data",
                "case_id": case_id,
                "reason": (
                    f"Graph contains {len(person_nodes)} valid PERSON entities. "
                    f"Minimum required for centrality ranking: {MIN_PERSON_NODES} person."
                ),
                "ranked_individuals": [],
                "communities": [],
                "flags": [],
            }

        communities = detect_louvain_communities(G)
        ranked_individuals = rank_key_individuals(
            G=G,
            case_id=case_id,
            communities=communities,
        )
        flags = detect_pattern_flags(
            G=G,
            case_id=case_id,
            database=db,
        )

        # Idempotently persist detected flags into MongoDB `flags` collection
        now_utc = datetime.now(UTC)
        for flag_item in flags:
            flag_id = flag_item["flag_id"]
            existing_flag = db.flags.find_one({"id": flag_id})
            persisted_status = (
                existing_flag.get("verification_status")
                if existing_flag and existing_flag.get("verification_status")
                else "unverified"
            )
            flag_item["verification_status"] = persisted_status
            db.flags.update_one(
                {"id": flag_id},
                {
                    "$set": {
                        "id": flag_id,
                        "case_id": case_id,
                        "flag_type": flag_item["flag_type"],
                        "description": flag_item["description"],
                        "severity": flag_item["severity"],
                        "provenance": {
                            "tier": "primary",
                            "source_ref": case_id,
                            "method": "graph_pattern_detector",
                            "confidence": flag_item["trail"]["confidence"],
                            "extracted_at": now_utc,
                        },
                        "verification_status": persisted_status,
                        "updated_at": now_utc,
                        "metadata": {
                            "entity_id": flag_item["entity_id"],
                            "canonical_name": flag_item["canonical_name"],
                            "trail": flag_item["trail"],
                        },
                    },
                    "$setOnInsert": {
                        "created_at": now_utc,
                    },
                },
                upsert=True,
            )

        trail = {
            "graph_summary": {
                "total_nodes": num_nodes,
                "total_edges": num_edges,
                "person_nodes": len(person_nodes),
                "communities_count": len(communities),
            },
            "formula": "combined_score = round(0.50 * degree_norm + 0.20 * betweenness_norm + 0.30 * pagerank_norm, 4)",
            "insufficient_data_thresholds": {
                "min_nodes": MIN_GRAPH_NODES,
                "min_edges": MIN_GRAPH_EDGES,
                "min_person_nodes": MIN_PERSON_NODES,
            },
            "legal_notice": (
                "Network metrics describe structural relationships in the analyzed corpus. "
                "They do not establish guilt, intent, or legal responsibility."
            ),
        }

        return {
            "status": "ok",
            "case_id": case_id,
            "ranked_individuals": ranked_individuals,
            "communities": communities,
            "flags": flags,
            "trail": trail,
        }

    except Exception as err:
        logger.error("Analysis calculation failed for case %s: %s", case_id, err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis calculation failed: {str(err)}",
        ) from err


class SimulationRequest(BaseModel):
    exclude_node_ids: list[str] = Field(
        default_factory=list,
        description="List of node/entity IDs to exclude in this what-if scenario.",
    )


@router.post(
    "/{case_id}/simulate",
    summary="Run what-if scenario simulation excluding specified nodes",
    response_description="Recalculated centrality rankings, Louvain communities, pattern flags, and impact comparison.",
)
async def simulate_case_what_if_endpoint(
    case_id: str,
    payload: SimulationRequest,
) -> dict[str, Any]:
    """Execute in-memory what-if scenario simulation on a case network graph.

    Removes only the requested node IDs from an in-memory graph copy and recalculates
    deterministic centrality rankings, Louvain communities, and structural pattern flags
    using the exact same Task 5.1 analytics functions.

    Guarantees:
    - Never modifies the stored MongoDB database or graph collections.
    - Operates purely in-memory on a graph copy.
    - Handles invalid case IDs (404), unknown nodes, empty exclusions, and tiny/disconnected fallback.
    - Returns comprehensive before/after comparison metrics.
    """
    from app.services.analytics import (
        detect_louvain_communities,
        detect_pattern_flags,
        is_valid_person_entity,
        rank_key_individuals,
    )
    from app.services.analytics.centrality import (
        MIN_GRAPH_EDGES,
        MIN_GRAPH_NODES,
        MIN_PERSON_NODES,
    )
    from app.services.graph.networkx_loader import load_case_graph

    db = get_db()
    case = db.cases.find_one({"case_id": case_id})
    has_entities = db.entities.find_one({"case_id": case_id}) is not None
    if not case and not has_entities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    try:
        G_orig = load_case_graph(case_id=case_id, database=db)
        num_orig_nodes = G_orig.number_of_nodes()
        num_orig_edges = G_orig.number_of_edges()
        person_nodes_orig = [
            n for n, d in G_orig.nodes(data=True)
            if is_valid_person_entity(n, d)
        ]

        # Check original graph baseline
        if num_orig_nodes < MIN_GRAPH_NODES or num_orig_edges < MIN_GRAPH_EDGES:
            return {
                "status": "insufficient_data",
                "case_id": case_id,
                "reason": (
                    f"Original graph has {num_orig_nodes} node(s) and {num_orig_edges} edge(s). "
                    f"Minimum required: {MIN_GRAPH_NODES} nodes and {MIN_GRAPH_EDGES} edges."
                ),
                "excluded_node_ids": payload.exclude_node_ids or [],
                "original_top_individuals": [],
                "simulated_top_individuals": [],
                "communities": [],
                "flags": [],
                "changed": False,
            }

        # Baseline analytics
        orig_communities = detect_louvain_communities(G_orig)
        orig_ranked = rank_key_individuals(
            G=G_orig,
            case_id=case_id,
            communities=orig_communities,
        )

        # Make in-memory copy for simulation (never touches MongoDB)
        G_sim = G_orig.copy()

        requested_exclusions = payload.exclude_node_ids or []
        actually_removed = [nid for nid in requested_exclusions if G_sim.has_node(nid)]
        unknown_nodes = [nid for nid in requested_exclusions if not G_sim.has_node(nid)]

        for nid in actually_removed:
            G_sim.remove_node(nid)

        sim_nodes_count = G_sim.number_of_nodes()
        sim_edges_count = G_sim.number_of_edges()
        sim_person_nodes = [
            n for n, d in G_sim.nodes(data=True)
            if is_valid_person_entity(n, d)
        ]

        # Handle post-exclusion insufficient data
        if sim_nodes_count < MIN_GRAPH_NODES or sim_edges_count < MIN_GRAPH_EDGES:
            return {
                "status": "insufficient_data",
                "case_id": case_id,
                "reason": (
                    f"Simulated graph has {sim_nodes_count} node(s) and {sim_edges_count} edge(s) remaining after exclusion. "
                    f"Minimum required: {MIN_GRAPH_NODES} nodes and {MIN_GRAPH_EDGES} edges."
                ),
                "excluded_node_ids": requested_exclusions,
                "actually_removed_node_ids": actually_removed,
                "unknown_node_ids": unknown_nodes,
                "original_top_individuals": orig_ranked[:10],
                "simulated_top_individuals": [],
                "communities": [],
                "flags": [],
                "changed": len(actually_removed) > 0,
                "impact_summary": {
                    "requested_exclusions_count": len(requested_exclusions),
                    "removed_nodes_count": len(actually_removed),
                    "remaining_nodes": sim_nodes_count,
                    "remaining_edges": sim_edges_count,
                    "remaining_person_nodes": len(sim_person_nodes),
                },
            }

        if len(sim_person_nodes) < MIN_PERSON_NODES:
            return {
                "status": "insufficient_data",
                "case_id": case_id,
                "reason": (
                    f"Simulated graph has {len(sim_person_nodes)} valid PERSON entities remaining. "
                    f"Minimum required: {MIN_PERSON_NODES} person."
                ),
                "excluded_node_ids": requested_exclusions,
                "actually_removed_node_ids": actually_removed,
                "unknown_node_ids": unknown_nodes,
                "original_top_individuals": orig_ranked[:10],
                "simulated_top_individuals": [],
                "communities": [],
                "flags": [],
                "changed": len(actually_removed) > 0,
            }

        # Run exact Task 5.1 analytics on simulated graph
        sim_communities = detect_louvain_communities(G_sim)
        sim_ranked = rank_key_individuals(
            G=G_sim,
            case_id=case_id,
            communities=sim_communities,
        )
        # In-memory flags detection (strictly without writing to MongoDB)
        sim_flags = detect_pattern_flags(
            G=G_sim,
            case_id=case_id,
            database=db,
        )

        orig_top_ids = [r["entity_id"] for r in orig_ranked[:10]]
        sim_top_ids = [r["entity_id"] for r in sim_ranked[:10]]
        orig_top_scores = {r["entity_id"]: r["combined_score"] for r in orig_ranked[:10]}
        sim_top_scores = {r["entity_id"]: r["combined_score"] for r in sim_ranked[:10]}

        rankings_changed = (orig_top_ids != sim_top_ids) or any(
            abs(orig_top_scores.get(eid, 0.0) - sim_top_scores.get(eid, 0.0)) > 0.0001
            for eid in sim_top_ids
        )
        communities_changed = len(orig_communities) != len(sim_communities) or (
            [c["member_ids"] for c in orig_communities] != [c["member_ids"] for c in sim_communities]
        )
        changed = bool(actually_removed) and (rankings_changed or communities_changed)

        impact_summary = {
            "requested_exclusions_count": len(requested_exclusions),
            "removed_nodes_count": len(actually_removed),
            "original_nodes": num_orig_nodes,
            "simulated_nodes": sim_nodes_count,
            "original_edges": num_orig_edges,
            "simulated_edges": sim_edges_count,
            "original_communities_count": len(orig_communities),
            "simulated_communities_count": len(sim_communities),
            "rankings_changed": rankings_changed,
            "communities_changed": communities_changed,
        }

        return {
            "status": "ok",
            "case_id": case_id,
            "excluded_node_ids": requested_exclusions,
            "actually_removed_node_ids": actually_removed,
            "unknown_node_ids": unknown_nodes,
            "original_top_individuals": orig_ranked[:10],
            "simulated_top_individuals": sim_ranked[:10],
            "communities": sim_communities,
            "flags": sim_flags,
            "changed": changed,
            "impact_summary": impact_summary,
            "trail": {
                "method": "in_memory_what_if_simulation",
                "db_modified": False,
                "formula": "combined_score = round(0.50 * degree_norm + 0.20 * betweenness_norm + 0.30 * pagerank_norm, 4)",
                "legal_notice": (
                    "Simulation recalculates structural network metrics on a hypothetical subgraph. "
                    "It does not establish guilt, intent, or legal responsibility."
                ),
            },
        }

    except Exception as err:
        logger.error("Simulation failed for case %s: %s", case_id, err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {str(err)}",
        ) from err


class FlagVerificationRequest(BaseModel):
    verification_status: str | None = Field(None, description="'confirmed', 'rejected', or 'unverified'")
    status: str | None = Field(None, description="Alternative alias for verification_status")
    notes: str | None = Field(None, description="Optional analyst verification notes")
    analyst_id: str | None = Field(None, description="Analyst identifier")


@router.patch(
    "/{case_id}/flags/{flag_id}/verify",
    summary="Confirm or reject a pattern flag",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def patch_flag_verification_endpoint(
    case_id: str,
    flag_id: str,
    payload: FlagVerificationRequest,
) -> dict[str, Any]:
    """Update verification status of a pattern flag ('confirmed', 'rejected', 'unverified').

    Persists directly to MongoDB `flags` collection and appends to `audit_log`.
    """
    from datetime import UTC, datetime

    db = get_db()
    flag = db.flags.find_one({"$or": [{"id": flag_id}, {"flag_id": flag_id}]})
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flag not found with ID: {flag_id}",
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

    db.flags.update_one(
        {"$or": [{"id": flag_id}, {"flag_id": flag_id}]},
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

    db.audit_log.insert_one({
        "case_id": case_id,
        "actor": actor,
        "action": f"{target_status}_flag",
        "timestamp": now_utc,
        "input_summary": {
            "flag_id": flag_id,
            "case_id": case_id,
            "new_status": target_status,
            "notes": payload.notes,
        },
        "result_summary": f"Flag '{flag_id}' ({flag.get('flag_type')}) marked as {target_status}",
        "entity_type": "flag",
        "entity_id": flag_id,
        "verification_status": target_status,
    })

    return {
        "status": "ok",
        "flag_id": flag_id,
        "case_id": case_id,
        "verification_status": target_status,
        "updated_at": now_utc.isoformat(),
    }




