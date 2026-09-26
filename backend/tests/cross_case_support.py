"""Test/demo support for cross-case matching: an isolated database and per-case snapshots.

Isolation: every database lookup made through `app.core.db` (whatever database name is
requested) is redirected to ONE dedicated test database, so tests and demos can never read
or write the production database.

  * Default: an in-memory MongoDB (mongomock) — nothing leaves the process.
  * Optional: set NEXUS_TEST_MONGODB_URI to use a real MongoDB server. The database name
    (NEXUS_TEST_DB_NAME, default "nexus_cross_case_test") must end with "_test" and differ
    from the production database name; only that database is ever dropped.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import pytest

from app.core import db as core_db

DEFAULT_TEST_DB_NAME = "nexus_cross_case_test"


class IsolatedMongoClient:
    """Client proxy that pins every database lookup to a single test database."""

    def __init__(self, client: Any, db_name: str) -> None:
        self._client = client
        self._db_name = db_name

    def __getitem__(self, _requested_name: str) -> Any:
        return self._client[self._db_name]

    def get_database(self, *args: Any, **kwargs: Any) -> Any:
        return self._client[self._db_name]

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._client, attr)

    @property
    def test_db_name(self) -> str:
        return self._db_name

    @property
    def test_database(self) -> Any:
        return self._client[self._db_name]


def open_isolated_client() -> tuple[IsolatedMongoClient, Any | None]:
    """Return (isolated_client, real_client_or_None)."""
    name = os.environ.get("NEXUS_TEST_DB_NAME", DEFAULT_TEST_DB_NAME).strip()
    if not name.endswith("_test") or name == core_db.DB_NAME:
        raise RuntimeError(
            "Refusing to run: the test database name must end with '_test' and must differ "
            f"from the production database name ({core_db.DB_NAME})."
        )
    uri = os.environ.get("NEXUS_TEST_MONGODB_URI", "").strip()
    if uri:
        from pymongo import MongoClient

        real = MongoClient(uri, serverSelectionTimeoutMS=5000)
        real.drop_database(name)  # only the dedicated *_test database
        return IsolatedMongoClient(real, name), real

    import mongomock

    return IsolatedMongoClient(mongomock.MongoClient(), name), None


def close_isolated_client(client: IsolatedMongoClient, real: Any | None) -> None:
    if real is not None:
        real.drop_database(client.test_db_name)
        real.close()


@pytest.fixture
def isolated_db(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Yield the isolated test database; app code calling get_db() is redirected to it."""
    client, real = open_isolated_client()
    monkeypatch.setattr(core_db, "_client", client)
    try:
        yield client.test_database
    finally:
        close_isolated_client(client, real)


# ── Per-case state snapshots (regression checks) ─────────────────────────────


def _digest(docs: list[dict[str, Any]]) -> str:
    canonical = sorted(json.dumps(d, sort_keys=True, default=str) for d in docs)
    return hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest()


def snapshot_per_case_state(db: Any, case_ids: list[str]) -> dict[str, Any]:
    """Fingerprint stored per-case data and recompute per-case analytics (read-only)."""
    from app.services.analytics import (
        detect_louvain_communities,
        detect_pattern_flags,
        rank_key_individuals,
    )
    from app.services.graph.networkx_loader import load_case_graph

    collections = {}
    for name in ("entities", "entity_merges", "edges", "flags", "documents", "cases"):
        docs = list(db[name].find({}, {"_id": 0}))
        collections[name] = {"count": len(docs), "sha256": _digest(docs)}

    per_case: dict[str, Any] = {}
    for case_id in sorted(case_ids):
        graph = load_case_graph(case_id=case_id, database=db)
        communities = detect_louvain_communities(graph)
        ranked = rank_key_individuals(G=graph, case_id=case_id, communities=communities)
        flags = detect_pattern_flags(G=graph, case_id=case_id, database=db)
        per_case[case_id] = {
            "nodes": sorted(graph.nodes()),
            "edges": sorted(tuple(sorted(e)) for e in graph.edges()),
            "centrality_ranking": [(r["entity_id"], r["rank"], r["combined_score"]) for r in ranked],
            "communities": [c["member_ids"] for c in communities],
            "pattern_flags": sorted((f["flag_id"], f["flag_type"], f["severity"]) for f in flags),
        }
    return {"collections": collections, "per_case": per_case}


def diff_snapshots(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Human-readable list of differences (empty list means unchanged)."""
    differences: list[str] = []
    for name, info in before["collections"].items():
        if after["collections"].get(name) != info:
            differences.append(f"collection '{name}' changed: {info} -> {after['collections'].get(name)}")
    for case_id, state in before["per_case"].items():
        other = after["per_case"].get(case_id)
        for key, value in state.items():
            if other is None or other.get(key) != value:
                differences.append(f"{case_id}: {key} changed")
    return differences
