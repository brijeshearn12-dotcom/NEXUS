"""verify_provenance_integrity.py — Automated MongoDB data integrity and provenance verification.

SIH26189GREEN | AI-Powered Criminal Network Analysis System
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Ensure backend directory is in sys.path
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.db import get_db  # noqa: E402


def verify_provenance_integrity(database: Any | None = None) -> tuple[int, int, int]:
    """Execute rigorous MongoDB data-integrity checks across all stored entities and edges.

    Checks:
    - Missing provenance field
    - Empty provenance object
    - Missing or empty source_ref
    - Missing confidence score or confidence outside [0.0, 1.0]
    - Missing extraction/creation method

    Returns:
        tuple[int, int, int]: (invalid_entity_count, invalid_edge_count, total_invalid)
    """
    db = database if database is not None else get_db()

    # 1. Invalid entity provenance query
    invalid_entity_filter = {
        "$or": [
            {"provenance": {"$exists": False}},
            {"provenance": None},
            {"provenance": {}},
            {"provenance.source_ref": {"$exists": False}},
            {"provenance.source_ref": None},
            {"provenance.source_ref": ""},
            {"provenance.confidence": {"$exists": False}},
            {"provenance.confidence": None},
            {"provenance.confidence": {"$lt": 0.0}},
            {"provenance.confidence": {"$gt": 1.0}},
            {"provenance.method": {"$exists": False}},
            {"provenance.method": None},
            {"provenance.method": ""},
        ]
    }
    missing_entities = db.entities.count_documents(invalid_entity_filter)

    # 2. Invalid edge provenance query
    invalid_edge_filter = {
        "$or": [
            {"provenance": {"$exists": False}},
            {"provenance": None},
            {"provenance": {}},
            {"provenance.source_ref": {"$exists": False}},
            {"provenance.source_ref": None},
            {"provenance.source_ref": ""},
            {"provenance.confidence": {"$exists": False}},
            {"provenance.confidence": None},
            {"provenance.confidence": {"$lt": 0.0}},
            {"provenance.confidence": {"$gt": 1.0}},
            {"provenance.method": {"$exists": False}},
            {"provenance.method": None},
            {"provenance.method": ""},
        ]
    }
    missing_edges = db.edges.count_documents(invalid_edge_filter)

    total_invalid = missing_entities + missing_edges

    return missing_entities, missing_edges, total_invalid


def main() -> int:
    """Run integrity check and print exact formatted report."""
    db = get_db()
    total_entities = db.entities.count_documents({})
    total_edges = db.edges.count_documents({})

    missing_entities, missing_edges, total_invalid = verify_provenance_integrity(db)

    print("==================================================")
    print("NEXUS PROVENANCE & DATA INTEGRITY VERIFICATION")
    print(f"Total entities inspected: {total_entities}")
    print(f"Total edges inspected:    {total_edges}")
    print("--------------------------------------------------")
    print(f"Missing entity provenance: {missing_entities}")
    print(f"Missing edge provenance: {missing_edges}")
    print(f"TOTAL INVALID PROVENANCE: {total_invalid}")
    print("==================================================")

    if total_invalid == 0:
        print("RESULT: PROVENANCE INTEGRITY 100% VERIFIED")
        return 0
    else:
        print(f"CRITICAL: Found {total_invalid} records with missing/invalid provenance!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
