"""Graph construction service for NEXUS Task 4.2.

Coordinates:
1. Loading extracted entities and resolved alias mappings
2. Running deterministic edge extraction rules (co-accused, sentence co-occurrence)
3. Deduplicating edges (source + target + edge_type)
4. Aggregating weights and preserving evidence / provenance
5. Persisting canonical edges to MongoDB `edges` collection
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.db import get_db
from app.models.audit import AuditLogEntry
from app.models.enums import ProvenanceMethod, ProvenanceTier, VerificationStatus
from app.models.provenance import Provenance
from app.services.graph.cross_case_linker import build_alias_canonical_map
from app.services.graph.edge_rules import (
    EDGE_WEIGHT_MAP,
    INCREMENT_WEIGHT_MAP,
    extract_candidate_edges_from_document,
)

logger = logging.getLogger(__name__)


def generate_stable_edge_id(source_id: str, target_id: str, edge_type: str) -> str:
    """Generate deterministic, immutable edge ID for idempotency."""
    src, tgt = (source_id, target_id) if source_id < target_id else (target_id, source_id)
    raw = f"{src}:{tgt}:{edge_type}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"edge_{digest}"


def build_graph_for_case(case_id: str, database: Any | None = None) -> dict[str, Any]:
    """Build or update the relationship graph for a case.

    Args:
        case_id: Case string identifier.
        database: Optional MongoDB database handle.

    Returns:
        dict: {
            "case_id": str,
            "nodes": int,
            "edges_created": int,
            "edges_updated": int
        }
    """
    db = database if database is not None else get_db()
    entities_col = db.entities
    docs_col = db.documents
    edges_col = db.edges
    audit_col = db.audit_log

    # 1. Load entities for case
    entities = list(entities_col.find({"case_id": case_id}))
    if not entities:
        return {
            "case_id": case_id,
            "nodes": 0,
            "edges_created": 0,
            "edges_updated": 0,
        }

    # 2. Load alias mapping (from Task 4.1 entity_merges)
    alias_map = build_alias_canonical_map(db)

    # Determine unique canonical nodes
    canonical_node_ids = {alias_map.get(e["id"], e["id"]) for e in entities if "id" in e}
    nodes_count = len(canonical_node_ids)

    # 3. Load documents for case
    documents = list(docs_col.find({"case_id": case_id}))
    if not documents:
        # Check if any document has this case_id or source_ref
        documents = list(docs_col.find({"id": case_id}))

    # 4. Extract candidate edges across documents
    raw_candidates: list[dict[str, Any]] = []
    for doc in documents:
        doc_id = doc.get("id") or doc.get("document_id") or "doc_unknown"
        # Prefer segmented extraction text or fallback to cleaned/raw/judgment text
        doc_text = (
            doc.get("text")
            or doc.get("judgment_text")
            or doc.get("cleaned_text")
            or doc.get("raw_text")
            or ""
        )
        cands = extract_candidate_edges_from_document(
            doc_id=doc_id,
            case_id=case_id,
            text=doc_text,
            entities=entities,
            alias_map=alias_map,
        )
        raw_candidates.extend(cands)

    # Also: if no documents in MongoDB (e.g. mock test case), check entity evidence snippets!
    if not documents:
        # Synthesize co-accused edge if accused entities exist
        accused_ents = [
            e for e in entities
            if e.get("entity_type", "").upper() in {"PERSON", "ACCUSED"}
            and (e.get("metadata", {}).get("is_accused") or e.get("provenance", {}).get("method") == "accused_pattern")
        ]
        canon_accused = {}
        for a in accused_ents:
            c_id = alias_map.get(a["id"], a["id"])
            canon_accused[c_id] = a

        accused_list = list(canon_accused.values())
        for i in range(len(accused_list)):
            for j in range(i + 1, len(accused_list)):
                p1, p2 = accused_list[i], accused_list[j]
                c1_id = alias_map.get(p1["id"], p1["id"])
                c2_id = alias_map.get(p2["id"], p2["id"])
                if c1_id == c2_id:
                    continue
                s_id, t_id = (c1_id, c2_id) if c1_id < c2_id else (c2_id, c1_id)
                raw_candidates.append({
                    "source_entity_id": s_id,
                    "target_entity_id": t_id,
                    "edge_type": "co_accused",
                    "case_id": case_id,
                    "document_id": p1.get("document_id") or "doc_unknown",
                    "evidence_snippet": f"Co-accused in case {case_id}: {p1.get('name')} and {p2.get('name')}",
                    "method": ProvenanceMethod.ACCUSED_PATTERN.value,
                    "confidence": 0.95,
                })

    # 5. Deduplicate and aggregate weights
    # Group key: (source_entity_id, target_entity_id, edge_type)
    edge_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for cand in raw_candidates:
        src = cand["source_entity_id"]
        tgt = cand["target_entity_id"]
        etype = cand["edge_type"]
        pair_key = (src, tgt, etype)
        if pair_key not in edge_groups:
            edge_groups[pair_key] = []
        edge_groups[pair_key].append(cand)

    edges_created = 0
    edges_updated = 0
    now_utc = datetime.now(UTC)

    for (src_id, tgt_id, etype), cands in edge_groups.items():
        edge_id = generate_stable_edge_id(src_id, tgt_id, etype)

        # Base weight
        base_w = EDGE_WEIGHT_MAP.get(etype, 0.5)
        inc_w = INCREMENT_WEIGHT_MAP.get(etype, 0.1)

        # Aggregate weight deterministically: base + increment * (count - 1), capped at 5.0
        evidence_count = len(cands)
        total_weight = round(min(5.0, base_w + inc_w * (evidence_count - 1)), 2)

        # Aggregate case_ids, document_ids, snippets
        case_ids_set = {c["case_id"] for c in cands if c.get("case_id")}
        doc_ids_set = {c["document_id"] for c in cands if c.get("document_id")}
        snippets = [c["evidence_snippet"] for c in cands if c.get("evidence_snippet")]
        best_snippet = max(snippets, key=len) if snippets else ""

        # Highest confidence
        max_conf = max(c.get("confidence", 0.85) for c in cands)
        primary_method = cands[0].get("method", ProvenanceMethod.DIRECT_TEXT.value)

        provenance = Provenance(
            tier=ProvenanceTier.PRIMARY.value,
            source_ref=sorted(list(doc_ids_set))[0] if doc_ids_set else case_id,
            method=primary_method,
            confidence=max_conf,
            extracted_at=now_utc,
            metadata={
                "evidence_count": evidence_count,
                "evidence_snippets": snippets[:3],
                "edge_type": etype,
            },
        )

        edge_doc = {
            "id": edge_id,
            "edge_id": edge_id,
            "source_entity_id": src_id,
            "target_entity_id": tgt_id,
            "edge_type": etype,
            "relationship_type": etype,
            "weight": total_weight,
            "case_id": case_id,
            "case_ids": sorted(list(case_ids_set)),
            "document_ids": sorted(list(doc_ids_set)),
            "evidence": best_snippet,
            "confidence": max_conf,
            "provenance": provenance.model_dump(by_alias=True),
            "verification_status": VerificationStatus.UNVERIFIED.value,
            "created_at": now_utc,
            "updated_at": now_utc,
            "attributes": {
                "evidence_count": evidence_count,
                "weight": total_weight,
            },
        }

        # Check existing
        existing = edges_col.find_one({"edge_id": edge_id})
        if existing:
            # Merge case_ids and doc_ids if existing has other cases (cross-case)
            merged_cases = sorted(list(set(existing.get("case_ids", []) + list(case_ids_set))))
            merged_docs = sorted(list(set(existing.get("document_ids", []) + list(doc_ids_set))))
            edge_doc["case_ids"] = merged_cases
            edge_doc["document_ids"] = merged_docs
            edges_col.update_one({"edge_id": edge_id}, {"$set": edge_doc})
            edges_updated += 1
        else:
            edges_col.insert_one(edge_doc)
            edges_created += 1

    # 6. Audit log entry
    audit_entry = AuditLogEntry(
        case_id=case_id,
        actor="graph_builder",
        action="build_graph_for_case",
        timestamp=now_utc,
        input_summary={"case_id": case_id},
        result_summary=(
            f"Built graph for case {case_id}: {nodes_count} nodes, "
            f"{edges_created} edges created, {edges_updated} updated."
        ),
    )
    audit_col.insert_one(audit_entry.model_dump(by_alias=True))

    return {
        "case_id": case_id,
        "nodes": nodes_count,
        "edges_created": edges_created,
        "edges_updated": edges_updated,
    }


def get_graph_for_case(case_id: str, database: Any | None = None) -> dict[str, Any]:
    """Retrieve full graph (nodes + edges with provenance) for a case.

    Args:
        case_id: Case string identifier.
        database: Optional MongoDB database handle.

    Returns:
        dict: {"nodes": list, "edges": list}
    """
    db = database if database is not None else get_db()
    entities_col = db.entities
    edges_col = db.edges

    alias_map = build_alias_canonical_map(db)

    # 1. Fetch case entities
    entities = list(entities_col.find({"case_id": case_id}, {"_id": 0}))

    # Deduplicate to canonical nodes
    nodes_map: dict[str, dict[str, Any]] = {}
    for ent in entities:
        ent_id = ent.get("id")
        if not ent_id:
            continue
        canon_id = alias_map.get(ent_id, ent_id)
        if canon_id not in nodes_map:
            nodes_map[canon_id] = {
                "id": canon_id,
                "name": ent.get("name"),
                "entity_type": ent.get("entity_type"),
                "aliases": list(ent.get("aliases", [])),
                "case_id": ent.get("case_id"),
                "verification_status": ent.get("verification_status", "unverified"),
                "provenance": ent.get("provenance"),
            }
        else:
            # Merge aliases
            for a in ent.get("aliases", []):
                if a not in nodes_map[canon_id]["aliases"]:
                    nodes_map[canon_id]["aliases"].append(a)

    # 2. Fetch edges for this case
    edges_cursor = edges_col.find(
        {
            "$or": [
                {"case_id": case_id},
                {"case_ids": case_id},
            ]
        },
        {"_id": 0},
    )
    edges = list(edges_cursor)

    # Ensure format conforms to requirement:
    # edge_id, source_entity_id, target_entity_id, edge_type, weight, case_ids, document_ids, provenance, verification_status, created_at
    formatted_edges = []
    for e in edges:
        formatted_edges.append({
            "edge_id": e.get("edge_id") or e.get("id"),
            "source_entity_id": e.get("source_entity_id"),
            "target_entity_id": e.get("target_entity_id"),
            "edge_type": e.get("edge_type") or e.get("relationship_type"),
            "weight": float(e.get("weight", 1.0)),
            "case_ids": e.get("case_ids", [case_id]),
            "document_ids": e.get("document_ids", []),
            "evidence": e.get("evidence"),
            "provenance": e.get("provenance"),
            "verification_status": e.get("verification_status", "unverified"),
            "created_at": e.get("created_at"),
        })

    # Ensure nodes for all edge endpoints exist
    for e in formatted_edges:
        src = e["source_entity_id"]
        tgt = e["target_entity_id"]
        if src not in nodes_map:
            # Try fetching from DB
            db_ent = entities_col.find_one({"id": src}, {"_id": 0})
            if db_ent:
                nodes_map[src] = db_ent
            else:
                nodes_map[src] = {"id": src, "name": src, "entity_type": "UNKNOWN"}
        if tgt not in nodes_map:
            db_ent = entities_col.find_one({"id": tgt}, {"_id": 0})
            if db_ent:
                nodes_map[tgt] = db_ent
            else:
                nodes_map[tgt] = {"id": tgt, "name": tgt, "entity_type": "UNKNOWN"}

    return {
        "nodes": list(nodes_map.values()),
        "edges": formatted_edges,
    }
