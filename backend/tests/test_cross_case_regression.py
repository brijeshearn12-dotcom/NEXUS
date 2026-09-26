"""Regression: cross-case matching must not change any per-case result.

Runs the existing per-case pipeline (alias resolution, graph build, analysis), snapshots
entities, entity merges, edges, flags, graphs, centrality rankings, Louvain communities and
pattern flags, then runs cross-case matching plus analyst decisions and checks that every
per-case result is identical.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.cross_case.matcher import CROSS_CASE_COLLECTION
from app.services.graph.builder import build_graph_for_case
from app.services.resolution.alias_resolver import resolve_case_aliases
from tests.cross_case_support import diff_snapshots, isolated_db, snapshot_per_case_state  # noqa: F401
from tests.test_cross_case_matching import FILLER, seed_judgment

client = TestClient(app)

CASE_TEXTS = {
    "101": (
        "Case Crime No. 45/2022 was registered at Police Station Kotwali, District Lucknow. The accused"
        " Ramesh Yadav met Suresh Pal Singh and Dinesh Kumar Tiwari at the grain market. R. Yadav then"
        " drove the car UP 32 AB 1234 with Dinesh Kumar Tiwari. Mahesh Chand Gupta financed the purchase"
        " of the car for Suresh Pal Singh." + FILLER * 2,
        [("Ramesh Yadav", True), ("R. Yadav", True), ("Suresh Pal Singh", True),
         ("Dinesh Kumar Tiwari", True), ("Mahesh Chand Gupta", False)],
    ),
    "202": (
        "The applicant Ramesh Yadav seeks bail in Case Crime No. 45/2022, Police Station Kotwali,"
        " District Lucknow. Suresh Pal Singh and Om Prakash Verma were arrested with him near the"
        " toll plaza. Om Prakash Verma carried the cash for Suresh Pal Singh." + FILLER,
        [("Ramesh Yadav", True), ("Suresh Pal Singh", True), ("Om Prakash Verma", True)],
    ),
    "303": (
        "The applicant Harish Chandra Joshi and the co-accused Pawan Kumar Saini are alleged to have"
        " cheated depositors. Pawan Kumar Saini opened the accounts for Harish Chandra Joshi, and"
        " Neeraj Kumar Bhatt certified them." + FILLER,
        [("Harish Chandra Joshi", True), ("Pawan Kumar Saini", True), ("Neeraj Kumar Bhatt", False)],
    ),
}


def test_cross_case_matching_leaves_per_case_results_unchanged(isolated_db, monkeypatch):
    case_ids = [seed_judgment(isolated_db, tid, text, people) for tid, (text, people) in CASE_TEXTS.items()]

    # Existing per-case pipeline
    for case_id in case_ids:
        resolve_case_aliases(case_id=case_id, database=isolated_db)
        build_graph_for_case(case_id=case_id, database=isolated_db)
    analysis_before = {c: client.get(f"/api/cases/{c}/analysis").json() for c in case_ids}
    assert isolated_db.entity_merges.count_documents({}) >= 1, "fixture should include a within-case merge"
    assert isolated_db.edges.count_documents({}) > 0
    collections_before = set(isolated_db.list_collection_names())
    before = snapshot_per_case_state(isolated_db, case_ids)
    # The baseline must be non-trivial, otherwise "unchanged" would prove nothing.
    assert all(before["per_case"][c]["centrality_ranking"] for c in case_ids)
    assert all(before["per_case"][c]["edges"] for c in case_ids)
    assert any(before["per_case"][c]["communities"] for c in case_ids)
    assert any(analysis_before[c].get("ranked_individuals") for c in case_ids)

    # Cross-case matching and analyst decisions
    monkeypatch.setattr(settings, "enable_cross_case", True)
    run = client.post("/api/cross-case/run").json()
    assert run["proposals_created"] >= 1
    links = client.get("/api/cross-case/links").json()["items"]
    client.patch(f"/api/cross-case/links/{links[0]['link_id']}/verify", json={"status": "confirmed"})
    if len(links) > 1:
        client.patch(f"/api/cross-case/links/{links[1]['link_id']}/verify", json={"status": "rejected"})
    client.post("/api/cross-case/run")

    after = snapshot_per_case_state(isolated_db, case_ids)
    assert diff_snapshots(before, after) == []
    assert set(isolated_db.list_collection_names()) - collections_before == {CROSS_CASE_COLLECTION}

    for case_id in case_ids:
        again = client.get(f"/api/cases/{case_id}/analysis").json()
        for key in ("ranked_individuals", "communities", "flags"):
            assert _strip_volatile(again.get(key)) == _strip_volatile(analysis_before[case_id].get(key)), (
                f"{case_id}: {key} changed after cross-case matching"
            )


def _strip_volatile(value):
    """Drop timestamps so two analysis responses can be compared value-for-value."""
    if isinstance(value, dict):
        return {k: _strip_volatile(v) for k, v in value.items() if k not in {"created_at", "updated_at", "timestamp"}}
    if isinstance(value, list):
        return [_strip_volatile(v) for v in value]
    return value
