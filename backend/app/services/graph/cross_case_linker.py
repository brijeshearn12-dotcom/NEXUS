"""Cross-case entity linking service for NEXUS relationship graphs.

Discovers relationships across distinct cases where Task 4.1 entity alias resolution
has linked entities to the same canonical identity.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.db import get_db

logger = logging.getLogger(__name__)


def build_alias_canonical_map(database: Any | None = None) -> dict[str, str]:
    """Build a mapping of alias_entity_id -> canonical_entity_id.

    Traverses chains transitively if any alias links to another alias.
    """
    db = database if database is not None else get_db()
    merges = list(db.entity_merges.find({}))

    alias_map: dict[str, str] = {}
    for m in merges:
        canon_id = m.get("canonical_entity_id")
        alias_id = m.get("alias_entity_id")
        if canon_id and alias_id and canon_id != alias_id:
            alias_map[alias_id] = canon_id

    # Resolve transitive merges (e.g. C -> B and B -> A implies C -> A)
    changed = True
    while changed:
        changed = False
        for alias_id, canon_id in list(alias_map.items()):
            if canon_id in alias_map:
                alias_map[alias_id] = alias_map[canon_id]
                changed = True

    return alias_map


def find_cross_case_canonical_entities(database: Any | None = None) -> dict[str, set[str]]:
    """Find canonical entities that appear in more than one case.

    Returns:
        Mapping of canonical_entity_id -> set of case_ids where mentions exist.
    """
    db = database if database is not None else get_db()
    alias_map = build_alias_canonical_map(db)

    canonical_to_cases: dict[str, set[str]] = {}
    entities = list(db.entities.find({}, {"id": 1, "case_id": 1}))

    for ent in entities:
        ent_id = ent.get("id")
        case_id = ent.get("case_id")
        if not ent_id or not case_id:
            continue
        canon_id = alias_map.get(ent_id, ent_id)
        if canon_id not in canonical_to_cases:
            canonical_to_cases[canon_id] = set()
        canonical_to_cases[canon_id].add(case_id)

    # Filter only those present in >= 2 cases
    return {
        canon_id: cases
        for canon_id, cases in canonical_to_cases.items()
        if len(cases) >= 2
    }
