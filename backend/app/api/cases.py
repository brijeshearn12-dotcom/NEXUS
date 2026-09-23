"""Cases router — endpoints for case management and manual document ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status
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


class CaseExtractionResponse(BaseModel):
    case_id: str = Field(..., description="Case identifier")
    status: str = Field(..., description="'ok' or 'failed'")
    documents_count: int = Field(..., description="Number of documents associated with case")
    entities_extracted: int = Field(..., description="Total entities extracted")
    already_extracted: bool = Field(..., description="True if entities already existed in database")
    message: str = Field(..., description="Readable status message")


@router.post(
    "/{case_id}/extract",
    summary="Extract entities across all documents for a case",
    response_model=CaseExtractionResponse,
    status_code=status.HTTP_200_OK,
)
async def extract_case_endpoint(
    case_id: str,
    enable_gemini_fallback: bool = Query(default=True, description="Enable Gemini LLM fallback"),
) -> dict[str, Any]:
    """Execute entity extraction for all documents in a case.
    
    Idempotent: If entities already exist, reports already_extracted=True without duplicating data.
    Logs authoritative audit events in `db.audit_log`.
    """
    from datetime import UTC, datetime
    from app.services.extraction.service import extract_and_store_document

    db = get_db()
    case = db.cases.find_one({"case_id": case_id})
    docs = list(db.documents.find({"case_id": case_id}, {"id": 1, "_id": 0}))

    if not case and not docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    existing_entities_count = db.entities.count_documents({"case_id": case_id})
    now_utc = datetime.now(UTC)

    if existing_entities_count > 0:
        db.audit_log.insert_one({
            "case_id": case_id,
            "actor": "analyst_guided_flow",
            "action": "extraction_verified_existing",
            "timestamp": now_utc,
            "input_summary": {"case_id": case_id, "documents_count": len(docs)},
            "result_summary": f"Case entities already present ({existing_entities_count} entities).",
            "entity_type": "case_entities",
            "entity_id": case_id,
            "verification_status": "unverified",
        })
        return {
            "case_id": case_id,
            "status": "ok",
            "documents_count": len(docs),
            "entities_extracted": existing_entities_count,
            "already_extracted": True,
            "message": f"Case already has {existing_entities_count} extracted entities.",
        }

    # Extract all documents for case
    total_extracted = 0
    db.audit_log.insert_one({
        "case_id": case_id,
        "actor": "analyst_guided_flow",
        "action": "extraction_started",
        "timestamp": now_utc,
        "input_summary": {"case_id": case_id, "documents_count": len(docs)},
        "result_summary": f"Started entity extraction across {len(docs)} document(s)",
        "entity_type": "case_entities",
        "entity_id": case_id,
        "verification_status": "unverified",
    })

    for d in docs:
        try:
            res = extract_and_store_document(
                document_id=d["id"],
                enable_gemini_fallback=enable_gemini_fallback,
            )
            total_extracted += res.get("entities_extracted", 0)
        except Exception as exc:
            logger.warning("Extraction error for doc %s in case %s: %s", d["id"], case_id, exc)

    completion_time = datetime.now(UTC)
    db.audit_log.insert_one({
        "case_id": case_id,
        "actor": "analyst_guided_flow",
        "action": "extraction_completed",
        "timestamp": completion_time,
        "input_summary": {"case_id": case_id, "documents_count": len(docs)},
        "result_summary": f"Entity extraction completed: {total_extracted} entities extracted",
        "entity_type": "case_entities",
        "entity_id": case_id,
        "verification_status": "unverified",
    })

    return {
        "case_id": case_id,
        "status": "ok",
        "documents_count": len(docs),
        "entities_extracted": total_extracted,
        "already_extracted": False,
        "message": f"Extracted {total_extracted} entities from {len(docs)} documents.",
    }


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

        # Authoritative audit log entry for network analysis
        db.audit_log.insert_one({
            "case_id": case_id,
            "actor": "analytics_engine",
            "action": "network_analysis_completed",
            "timestamp": now_utc,
            "input_summary": {
                "case_id": case_id,
                "nodes": num_nodes,
                "edges": num_edges,
                "person_nodes": len(person_nodes),
            },
            "result_summary": (
                f"Network analysis completed: {len(ranked_individuals)} ranked key individuals, "
                f"{len(communities)} Louvain communities, {len(flags)} pattern flags."
            ),
            "entity_type": "case_analysis",
            "entity_id": case_id,
            "verification_status": "unverified",
        })

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

        # Authoritative audit log entry for what-if simulation
        now_sim = datetime.now(UTC)
        db.audit_log.insert_one({
            "case_id": case_id,
            "actor": "analyst_simulation",
            "action": "what_if_simulation_executed",
            "timestamp": now_sim,
            "input_summary": {
                "case_id": case_id,
                "excluded_node_ids": requested_exclusions,
            },
            "result_summary": (
                f"Simulated removal of {len(actually_removed)} node(s). "
                f"Impact: {sim_nodes_count} remaining nodes, {sim_edges_count} edges, "
                f"changed={changed}."
            ),
            "entity_type": "simulation",
            "entity_id": case_id,
            "verification_status": "unverified",
        })

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


class AuditTrailItem(BaseModel):
    id: str = Field(..., description="Unique audit event ID")
    case_id: str | None = Field(None, description="Case identifier")
    actor: str = Field(..., description="System service or analyst ID")
    action: str = Field(..., description="Canonical action type")
    timestamp: str = Field(..., description="ISO 8601 event timestamp")
    result_summary: str | None = Field(None, description="Human-readable event summary")
    entity_type: str | None = Field(None, description="Target entity type")
    entity_id: str | None = Field(None, description="Target entity or flag ID")
    verification_status: str | None = Field(None, description="Verification status if applicable")
    input_summary: dict[str, Any] | None = Field(None, description="Input parameters")


class AuditTrailResponse(BaseModel):
    case_id: str
    total: int
    items: list[dict[str, Any]]


@router.get(
    "/{case_id}/audit",
    summary="Retrieve read-only audit trail for a case",
    response_model=AuditTrailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_case_audit_trail_endpoint(
    case_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """Retrieve chronological, read-only audit log events for this case.

    Includes authoritative records for:
    - Entity extraction (started, completed, verified)
    - Alias resolution
    - Relationship graph construction
    - Network analysis calculations
    - Analyst verification decisions (confirm, reject)
    - What-If simulations executed

    Strictly read-only: no frontend modification, editing, or deletion is permitted.
    """
    db = get_db()
    query = {"$or": [{"case_id": case_id}, {"case_id": "corpus_batch"}]}
    cursor = db.audit_log.find(query).sort("timestamp", -1).limit(limit)

    items = []
    for doc in cursor:
        doc_id = str(doc.pop("_id", ""))
        ts = doc.get("timestamp")
        if hasattr(ts, "isoformat"):
            doc["timestamp"] = ts.isoformat()
        elif ts is None:
            doc["timestamp"] = ""
        items.append({"id": doc_id, **doc})

    return {
        "case_id": case_id,
        "total": len(items),
        "items": items,
    }


class SyntheticGenerateRequest(BaseModel):
    cdr_count: int = Field(default=5, ge=1, le=50, description="Number of synthetic CDR edges to generate")
    transaction_count: int = Field(default=5, ge=1, le=50, description="Number of synthetic transaction edges to generate")


@router.post(
    "/{case_id}/synthetic/generate",
    summary="Generate synthetic CDR and financial transaction relationships",
    status_code=status.HTTP_200_OK,
)
async def generate_case_synthetic_endpoint(
    case_id: str,
    payload: SyntheticGenerateRequest | None = None,
) -> dict[str, Any]:
    """Generate synthetic CDR and Transaction edges connecting existing entities in this case.

    STRICT CONSTRAINTS:
    - Never invents new entities. Operates strictly on existing case entities from MongoDB.
    - Explicitly marks all edges with tier='synthetic', method='faker', and source_ref='synthetic-demo'.
    - Logs an authoritative record in the case audit trail.
    - Demonstrates multi-modal graph analysis without falsifying real-world evidence.
    """
    from app.services.synthetic import generate_case_synthetic_bridge

    db = get_db()
    req = payload or SyntheticGenerateRequest()
    try:
        result = generate_case_synthetic_bridge(
            case_id=case_id,
            cdr_count=req.cdr_count,
            transaction_count=req.transaction_count,
            database=db,
        )
        return result
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        ) from val_err
    except Exception as err:
        logger.error("Failed to generate synthetic data for case %s: %s", case_id, err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Synthetic generation failed: {str(err)}",
        ) from err


@router.delete(
    "/{case_id}/synthetic",
    summary="Clear all synthetic demonstration relationships for a case",
    status_code=status.HTTP_200_OK,
)
async def clear_case_synthetic_endpoint(case_id: str) -> dict[str, Any]:
    """Remove all synthetic demonstration relationships from the case to restore pure evidentiary baseline."""
    from app.services.synthetic import clear_case_synthetic_bridge

    db = get_db()
    try:
        result = clear_case_synthetic_bridge(case_id=case_id, database=db)
        return result
    except Exception as err:
        logger.error("Failed to clear synthetic data for case %s: %s", case_id, err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear synthetic data: {str(err)}",
        ) from err


@router.get(
    "/{case_id}/synthetic/summary",
    summary="Get summary of synthetic vs real edges for a case",
    status_code=status.HTTP_200_OK,
)
async def get_case_synthetic_summary_endpoint(case_id: str) -> dict[str, Any]:
    """Retrieve counts and breakdown of synthetic CDR and transaction edges."""
    from app.services.synthetic import get_case_synthetic_summary

    db = get_db()
    return get_case_synthetic_summary(case_id=case_id, database=db)


@router.get(
    "/{case_id}/report",
    summary="Download Investigation Dossier PDF",
    response_class=Response,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/{case_id}/report",
    summary="Generate and Download Investigation Dossier PDF",
    response_class=Response,
    status_code=status.HTTP_200_OK,
)
async def get_case_investigation_report_pdf(case_id: str) -> Response:
    """Generate and download a comprehensive, professional Law Enforcement Investigation Dossier in PDF format."""
    from app.services.report_generator import generate_case_pdf_report

    db = get_db()
    case = db.cases.find_one({"case_id": case_id}) or db.cases.find_one({"id": case_id})
    has_entities = db.entities.find_one({"case_id": case_id}) is not None

    if not case and not has_entities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    try:
        pdf_bytes = generate_case_pdf_report(case_id=case_id, database=db)
        filename = f"NEXUS_Investigation_Dossier_{case_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "application/pdf",
                "X-Report-Case-ID": case_id,
            },
        )
    except Exception as err:
        logger.error("Failed to generate PDF report for case %s: %s", case_id, err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF report: {str(err)}",
        ) from err





