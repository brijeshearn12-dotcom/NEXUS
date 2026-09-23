"""NetworkX graph loader for NEXUS criminal network graphs.

Provides in-memory NetworkX graph representation from MongoDB for downstream analytics.
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from app.core.db import get_db

logger = logging.getLogger(__name__)


def load_case_graph(case_id: str, database: Any | None = None) -> nx.Graph:
    """Convert the stored MongoDB graph for a case into a NetworkX Graph.

    Args:
        case_id: Case identifier to load.
        database: Optional MongoDB database instance.

    Returns:
        nx.Graph populated with nodes (and entity attributes) and edges (with weights and types).
    """
    db = database if database is not None else get_db()
    g = nx.Graph()

    # Load entities for this case
    entities_cursor = db.entities.find({"case_id": case_id})
    for ent in entities_cursor:
        node_id = ent.get("id")
        if not node_id:
            continue
        g.add_node(
            node_id,
            name=ent.get("name", ""),
            entity_type=ent.get("entity_type", "UNKNOWN"),
            verification_status=ent.get("verification_status", "unverified"),
            aliases=ent.get("aliases", []),
            case_id=case_id,
        )

    # Load edges for this case (either case_id matches or case_id in case_ids)
    edges_cursor = db.edges.find({
        "$or": [
            {"case_id": case_id},
            {"case_ids": case_id},
        ]
    })

    for edge in edges_cursor:
        src = edge.get("source_entity_id")
        tgt = edge.get("target_entity_id")
        if not src or not tgt:
            continue

        # Ensure nodes exist even if cross-case or alias-canonical
        if not g.has_node(src):
            ent_doc = db.entities.find_one({"id": src})
            if ent_doc:
                g.add_node(
                    src,
                    name=ent_doc.get("name", src),
                    entity_type=ent_doc.get("entity_type", "UNKNOWN"),
                    verification_status=ent_doc.get("verification_status", "unverified"),
                    aliases=ent_doc.get("aliases", []),
                    case_id=ent_doc.get("case_id", case_id),
                )
            else:
                g.add_node(src, id=src, name=src, entity_type="UNKNOWN")
        if not g.has_node(tgt):
            ent_doc = db.entities.find_one({"id": tgt})
            if ent_doc:
                g.add_node(
                    tgt,
                    name=ent_doc.get("name", tgt),
                    entity_type=ent_doc.get("entity_type", "UNKNOWN"),
                    verification_status=ent_doc.get("verification_status", "unverified"),
                    aliases=ent_doc.get("aliases", []),
                    case_id=ent_doc.get("case_id", case_id),
                )
            else:
                g.add_node(tgt, id=tgt, name=tgt, entity_type="UNKNOWN")

        weight = float(edge.get("weight", 1.0))
        edge_type = edge.get("edge_type", edge.get("relationship_type", "associated_with"))
        edge_id = edge.get("edge_id", edge.get("id"))
        verification_status = edge.get("verification_status", "unverified")
        prov = edge.get("provenance", {})
        evidence = edge.get("evidence", "")
        document_ids = edge.get("document_ids", [])
        case_ids = edge.get("case_ids", [case_id])

        if g.has_edge(src, tgt):
            existing_w = g[src][tgt].get("weight", 1.0)
            g[src][tgt]["weight"] = round(existing_w + weight, 2)
            if evidence and not g[src][tgt].get("evidence"):
                g[src][tgt]["evidence"] = evidence
        else:
            g.add_edge(
                src,
                tgt,
                edge_id=edge_id,
                edge_type=edge_type,
                weight=weight,
                verification_status=verification_status,
                provenance=prov,
                evidence=evidence,
                document_ids=document_ids,
                case_ids=case_ids,
            )

    logger.info(
        "Loaded case %s into NetworkX graph: %d nodes, %d edges",
        case_id,
        g.number_of_nodes(),
        g.number_of_edges(),
    )
    return g
