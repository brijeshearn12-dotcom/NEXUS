"""Synthetic Bridge service coordinating CDR and Transaction generation for NEXUS.

Enforces:
1. Real entity requirement: connects strictly existing extracted entities from MongoDB.
2. Distinct provenance labeling: tier="synthetic", method="faker", source_ref="synthetic-demo".
3. Audit logging in db.audit_log.
4. Clean teardown/clear capability so analysts can return to baseline evidence at any time.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.db import get_db
from app.services.synthetic.cdr_generator import generate_synthetic_cdr
from app.services.synthetic.transaction_generator import generate_synthetic_transactions

logger = logging.getLogger(__name__)


def generate_case_synthetic_bridge(
    case_id: str,
    cdr_count: int = 5,
    transaction_count: int = 5,
    database: Any | None = None,
) -> dict[str, Any]:
    """Generate and store synthetic CDR and Transaction edges for existing entities in a case.

    Args:
        case_id: Identifier of target case.
        cdr_count: Number of synthetic CDR edges (default 5).
        transaction_count: Number of synthetic transaction edges (default 5).
        database: Optional PyMongo database instance.

    Returns:
        dict: Operation status, counts of created edges, and edge summary.
    """
    db = database if database is not None else get_db()

    # 1. Fetch real extracted entities for this case
    entities = list(db.entities.find({"case_id": case_id}, {"_id": 0}))

    if len(entities) < 2:
        raise ValueError(
            f"Case '{case_id}' has {len(entities)} entity/entities. "
            "At least 2 extracted entities are required to generate synthetic demonstration relationships."
        )

    # 2. Generate synthetic edges using real entity IDs
    cdr_edges = generate_synthetic_cdr(case_id, entities, count=cdr_count)
    txn_edges = generate_synthetic_transactions(case_id, entities, count=transaction_count)
    all_new_edges = cdr_edges + txn_edges

    if all_new_edges:
        # 3. Store into db.edges
        db.edges.insert_many([dict(e) for e in all_new_edges])

    # 4. Authoritative audit log entry
    now_utc = datetime.now(UTC)
    db.audit_log.insert_one({
        "case_id": case_id,
        "actor": "system_synthetic_bridge",
        "action": "synthetic_data_generated",
        "timestamp": now_utc,
        "result_summary": (
            f"Generated {len(cdr_edges)} synthetic CDR edges and {len(txn_edges)} synthetic "
            f"transaction edges between existing real entities."
        ),
        "entity_type": "edge_bridge",
        "input_summary": {
            "cdr_count": cdr_count,
            "transaction_count": transaction_count,
            "total_entities_available": len(entities),
        },
    })

    return {
        "status": "ok",
        "case_id": case_id,
        "cdr_count": len(cdr_edges),
        "transaction_count": len(txn_edges),
        "total_generated": len(all_new_edges),
        "message": (
            f"Successfully generated {len(all_new_edges)} synthetic relationships. "
            "Notice: These are demonstration records generated via Faker and are explicitly marked as synthetic."
        ),
    }


def clear_case_synthetic_bridge(
    case_id: str,
    database: Any | None = None,
) -> dict[str, Any]:
    """Remove all synthetic demonstration edges for a case to restore pure evidentiary baseline.

    Args:
        case_id: Target case identifier.
        database: Optional PyMongo database instance.

    Returns:
        dict: Status and count of removed edges.
    """
    db = database if database is not None else get_db()

    query = {
        "$and": [
            {"$or": [{"case_id": case_id}, {"case_ids": case_id}]},
            {
                "$or": [
                    {"provenance.tier": "synthetic"},
                    {"relationship_type": {"$regex": "^SYNTHETIC_", "$options": "i"}},
                    {"edge_type": {"$regex": "^SYNTHETIC_", "$options": "i"}},
                ]
            },
        ]
    }

    result = db.edges.delete_many(query)
    deleted_count = result.deleted_count

    # Authoritative audit log
    now_utc = datetime.now(UTC)
    db.audit_log.insert_one({
        "case_id": case_id,
        "actor": "system_synthetic_bridge",
        "action": "synthetic_data_cleared",
        "timestamp": now_utc,
        "result_summary": f"Cleared {deleted_count} synthetic demonstration edges for case {case_id}.",
        "entity_type": "edge_bridge",
    })

    return {
        "status": "ok",
        "case_id": case_id,
        "deleted_count": deleted_count,
        "message": f"Successfully removed {deleted_count} synthetic demonstration relationships.",
    }


def get_case_synthetic_summary(
    case_id: str,
    database: Any | None = None,
) -> dict[str, Any]:
    """Retrieve statistical breakdown of synthetic vs real edges for a case."""
    db = database if database is not None else get_db()

    case_filter = {"$or": [{"case_id": case_id}, {"case_ids": case_id}]}
    total_edges = db.edges.count_documents(case_filter)

    synthetic_cdr_count = db.edges.count_documents({
        "$and": [
            case_filter,
            {"$or": [{"edge_type": "SYNTHETIC_CDR"}, {"relationship_type": "SYNTHETIC_CDR"}]},
        ]
    })
    synthetic_txn_count = db.edges.count_documents({
        "$and": [
            case_filter,
            {"$or": [{"edge_type": "SYNTHETIC_TRANSACTION"}, {"relationship_type": "SYNTHETIC_TRANSACTION"}]},
        ]
    })
    total_synthetic = db.edges.count_documents({
        "$and": [
            case_filter,
            {
                "$or": [
                    {"provenance.tier": "synthetic"},
                    {"relationship_type": {"$regex": "^SYNTHETIC_", "$options": "i"}},
                    {"edge_type": {"$regex": "^SYNTHETIC_", "$options": "i"}},
                ]
            },
        ]
    })

    return {
        "case_id": case_id,
        "total_edges": total_edges,
        "synthetic_edges": total_synthetic,
        "primary_edges": max(0, total_edges - total_synthetic),
        "synthetic_cdr_count": synthetic_cdr_count,
        "synthetic_transaction_count": synthetic_txn_count,
        "has_synthetic_data": total_synthetic > 0,
    }
