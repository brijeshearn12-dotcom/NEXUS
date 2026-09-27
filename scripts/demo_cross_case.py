"""Real-corpus demonstration of cross-case candidate matching — on an ISOLATED database.

Usage (from the repository root, with the backend virtualenv active):
    python scripts/demo_cross_case.py [--out report.json]

Never touches the production database: all reads and writes go to an isolated test
database (in-memory by default; see backend/tests/cross_case_support.py).

Steps
 1. Load the curated Indian Kanoon corpus with the existing corpus loader.
 2. Run the existing extraction on every judgment (Gemini fallback disabled).
 3. Run the existing per-case alias resolution and graph build; snapshot per-case analysis.
 4. Enable ENABLE_CROSS_CASE in-process and run the matcher through the API.
 5. Show the proposals with evidence from both judgments; an analyst confirms one
    Allahabad proposal through the API; show the resulting audit-trail entries.
 6. Negative checks: cited-precedent trap and duplicate judgments.
 7. Re-snapshot per-case analysis and compare with step 3.
 8. Controls (after the regression comparison): two clearly labelled SYNTHETIC judgments
    that cite the same FIR number — one at a different police station, one at the same.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
warnings.filterwarnings("ignore")

from app.core import db as core_db  # noqa: E402
from tests.cross_case_support import (  # noqa: E402
    close_isolated_client,
    diff_snapshots,
    open_isolated_client,
    snapshot_per_case_state,
)

ALLAHABAD_PAIR = {"case_141720225", "case_31981506"}  # used only to REPORT, never to match
SYNTHETIC_CONTROL_TEXT = (
    "SYNTHETIC CONTROL DOCUMENT - NOT A REAL JUDGMENT. Created only to test the matcher. "
    "The applicant Kaish Ahmad seeks bail in connection with Case Crime No. 114/2023, "
    "Police Station {station}, District {district}. The applicant was arrested on 12.03.2023 "
    "and the investigation is stated to be complete."
)


def _short(text: str | None, limit: int = 320) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _names(link: dict[str, Any]) -> set[str]:
    out = set()
    for side in (link["side_a"], link["side_b"]):
        out.add(str(side.get("entity_name", "")).lower())
        out.add(str(side.get("matched_name_form", "")).lower())
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", help="Optional path for a JSON report")
    args = parser.parse_args()

    client, real = open_isolated_client()
    core_db._client = client
    db = client.test_database
    print(f"Isolated database: {client.test_db_name} ({'real test server' if real else 'in-memory mongomock'})")

    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.main import app
    from app.services.corpus_service import load_curated_corpus
    from app.services.cross_case.safeguards import classify_mentions, extract_fir_station_keys
    from app.services.extraction.service import extract_and_store_document
    from app.services.graph.builder import build_graph_for_case
    from app.services.resolution.alias_resolver import resolve_case_aliases

    api = TestClient(app)
    report: dict[str, Any] = {"database": client.test_db_name}
    checks: dict[str, bool] = {}

    try:
        # 1-3. Existing pipeline on the real corpus -----------------------------------------
        t0 = time.perf_counter()
        loaded = load_curated_corpus()
        print(f"\n[1] Corpus loaded: {loaded.get('inserted', loaded.get('total', ''))} "
              f"documents ({time.perf_counter() - t0:.1f}s)")
        documents = sorted(db.documents.find({}, {"_id": 0, "id": 1, "case_id": 1, "title": 1}),
                           key=lambda d: d["id"])
        t1 = time.perf_counter()
        for doc in documents:
            res = extract_and_store_document(doc["id"], enable_gemini_fallback=False)
            print(f"    extracted {res['entities_extracted']:4d} entities  {doc['id']:15s} {doc['title'][:55]}")
        print(f"[2] Existing extraction done ({time.perf_counter() - t1:.1f}s, Gemini disabled)")
        case_ids = sorted({d["case_id"] for d in documents})
        for case_id in case_ids:
            resolve_case_aliases(case_id=case_id, database=db)
            build_graph_for_case(case_id=case_id, database=db)
        before = snapshot_per_case_state(db, case_ids)
        print(f"[3] Per-case resolution + graphs built for {len(case_ids)} cases; per-case analysis snapshotted")

        # 4. Cross-case matching through the API ------------------------------------------
        settings.enable_cross_case = True
        run = api.post("/api/cross-case/run").json()
        report["run_summary"] = run
        print("\n[4] Cross-case matching run")
        for key in ("documents_considered", "distinct_judgments", "entities_skipped_as_duplicate_copies",
                    "person_candidates", "excluded_person_entities", "candidate_pairs_evaluated",
                    "strict_name_matches", "rejected_name_only",
                    "rejected_single_token_without_identifier", "proposals_found"):
            print(f"    {key}: {run.get(key)}")
        for group in run.get("duplicate_groups", []):
            print(f"    duplicate group -> kept {group['representative']}; copies ignored: "
                  f"{[m for m in group['members'] if m != group['representative']]} "
                  f"(min text similarity {group['min_similarity']})")
        for ex in run.get("rejected_examples", []):
            print(f"    NOT proposed ({ex['reason']}): '{ex['name_a']}' {ex['case_a']} / "
                  f"'{ex['name_b']}' {ex['case_b']}")

        links = api.get("/api/cross-case/links").json()["items"]
        report["proposals"] = links
        print(f"\n[5] {len(links)} candidate match(es):")
        for link in links:
            a, b = link["side_a"], link["side_b"]
            print(f"    [{link['match_strength']:8s} {link['match_score']:2d} pts] {a['entity_name']} "
                  f"({a['case_id']}) <-> {b['entity_name']} ({b['case_id']}) | "
                  f"{', '.join(sorted({c['kind'] for c in link['corroboration']}))}")

        allahabad = [l for l in links if {l["side_a"]["case_id"], l["side_b"]["case_id"]} == ALLAHABAD_PAIR]
        checks["allahabad_pair_proposed"] = bool(allahabad)
        checks["allahabad_evidence_from_both_judgments"] = bool(allahabad) and all(
            l["side_a"]["evidence_passage"] and l["side_b"]["evidence_passage"]
            and l["side_a"]["document_id"] != l["side_b"]["document_id"] for l in allahabad
        )
        chosen = None
        if allahabad:
            kaish = [l for l in allahabad if "kaish ahmad" in _names(l)]
            chosen = (kaish or sorted(allahabad, key=lambda l: -l["match_score"]))[0]
            a, b = chosen["side_a"], chosen["side_b"]
            print(f"\n    Allahabad proposal selected for the demo: {a['entity_name']} <-> {b['entity_name']}")
            print(f"    A: {a['document_title']}\n       {a['source_url']}\n       \"{_short(a['evidence_passage'])}\"")
            print(f"    B: {b['document_title']}\n       {b['source_url']}\n       \"{_short(b['evidence_passage'])}\"")
            print("    Why linked:")
            for reason in chosen["reasons"]:
                print(f"      - {reason}")

            verdict = api.patch(
                f"/api/cross-case/links/{chosen['link_id']}/verify",
                json={"status": "confirmed", "analyst_id": "demo_analyst",
                      "notes": "Both orders arise from Case Crime No. 114/2023, P.S. Dhoomanganj."},
            )
            confirmed = verdict.json()
            checks["analyst_confirmed"] = verdict.status_code == 200 and confirmed.get("status") == "confirmed"
            print(f"\n    Analyst decision -> HTTP {verdict.status_code}, status={confirmed.get('status')}, "
                  f"reviewed_by={confirmed.get('reviewed_by')}")
            audit_hits = []
            for case_id in (a["case_id"], b["case_id"]):
                trail = api.get(f"/api/cases/{case_id}/audit", params={"limit": 500}).json()["items"]
                audit_hits += [(case_id, e["action"], e.get("actor")) for e in trail
                               if e.get("entity_id") == chosen["link_id"]]
            report["audit_entries_for_demo_link"] = audit_hits
            checks["decision_in_audit_trail"] = sum(1 for _, act, _ in audit_hits
                                                    if act == "cross_case_match_confirmed") == 2
            for case_id, action, actor in audit_hits:
                print(f"    audit[{case_id}]: {action} by {actor}")

        # 6. Negative checks -------------------------------------------------------------
        print("\n[6] Negative checks")
        trap = [l for l in links if any("krishna mohan reddy" in n for n in _names(l))]
        checks["precedent_trap_not_proposed"] = not trap
        for doc_id in ("doc_31981506", "doc_141720225"):
            doc = db.documents.find_one({"id": doc_id}, {"text": 1, "title": 1})
            mentions = classify_mentions(doc["text"], "Krishna Mohan Reddy", own_title=doc["title"])
            print(f"    '{'Krishna Mohan Reddy'}' in {doc_id}: {len(mentions['citation'])} citation mention(s), "
                  f"{len(mentions['participant'])} participant mention(s)")
        ap_entities = list(db.entities.find({"case_id": "case_165285253", "name": {"$regex": "Krishna Mohan Reddy"}},
                                            {"_id": 0, "name": 1}))
        print(f"    same name as a real party in case_165285253: {[e['name'] for e in ap_entities]}")
        print(f"    proposals involving 'Krishna Mohan Reddy': {len(trap)}  -> "
              f"{'OK (not proposed)' if not trap else 'FAIL'}")

        members = {m: g["representative"] for g in run.get("duplicate_groups", []) for m in g["members"]}
        copies = {m for m, rep in members.items() if m != rep}
        dup_violations = [l for l in links if l["side_a"]["document_id"] in copies or l["side_b"]["document_id"] in copies
                          or (members.get(l["side_a"]["document_id"]) is not None
                              and members.get(l["side_a"]["document_id"]) == members.get(l["side_b"]["document_id"]))]
        sajjan = any(len(g["members"]) == 6 for g in run.get("duplicate_groups", []))
        checks["duplicate_judgments_collapsed"] = sajjan and not dup_violations
        print(f"    Sajjan Kumar copies collapsed into one judgment: {sajjan}; proposals using duplicate "
              f"copies: {len(dup_violations)}")

        # 7. Regression -------------------------------------------------------------------
        after = snapshot_per_case_state(db, case_ids)
        differences = diff_snapshots(before, after)
        checks["per_case_analysis_unchanged"] = not differences
        report["per_case_differences"] = differences
        print(f"\n[7] Per-case entities, merges, edges, flags, graphs, centrality, communities and pattern "
              f"flags for {len(case_ids)} cases unchanged: {not differences}")
        for difference in differences:
            print(f"    DIFF: {difference}")

        # 8. Synthetic FIR/police-station controls ---------------------------------------
        print("\n[8] Synthetic controls (clearly labelled, isolated database only)")
        controls = {}
        for label, station, district in (("different_station", "Kotwali", "Lucknow"),
                                         ("same_station", "Dhoomanganj", "Prayagraj")):
            case_id = f"case_synthetic_control_{label}"
            text = SYNTHETIC_CONTROL_TEXT.format(station=station, district=district)
            fir_keys, _ = extract_fir_station_keys(text)
            ingest = api.post(f"/api/cases/{case_id}/ingest",
                              json={"text": text, "title": f"SYNTHETIC CONTROL ({label})",
                                    "source_ref": "synthetic-control"}).json()
            doc_id = ingest.get("document_id") or ingest.get("id") or ingest.get("document", {}).get("id")
            extract_and_store_document(doc_id, enable_gemini_fallback=False)
            resolve_case_aliases(case_id=case_id, database=db)
            build_graph_for_case(case_id=case_id, database=db)
            rerun = api.post("/api/cross-case/run").json()
            involving = [l for l in api.get("/api/cross-case/links", params={"case_id": case_id}).json()["items"]]
            name_only = [e for e in rerun.get("rejected_examples", []) if case_id in (e["case_a"], e["case_b"])]
            controls[label] = {"fir_keys": sorted(fir_keys), "proposals": len(involving),
                               "rejected_name_matches": name_only}
            print(f"    {label}: FIR keys {sorted(fir_keys)} -> proposals involving control: {len(involving)}; "
                  f"name matches rejected for lack of corroboration: {len(name_only)}")
            if involving:
                for link in involving:
                    print(f"       proposed: {link['side_a']['entity_name']} ({link['side_a']['case_id']}) <-> "
                          f"{link['side_b']['entity_name']} ({link['side_b']['case_id']}) via "
                          f"{[c['value'] for c in link['corroboration']]}")
        report["synthetic_controls"] = controls
        checks["same_fir_different_station_not_matched"] = controls["different_station"]["proposals"] == 0
        checks["same_fir_same_station_matched (positive control)"] = controls["same_station"]["proposals"] > 0

        print("\nCHECKS")
        for name, ok in checks.items():
            print(f"    {'PASS' if ok else 'FAIL'}  {name}")
        report["checks"] = checks
        if args.out:
            Path(args.out).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
            print(f"\nReport written to {args.out}")
        return 0 if all(checks.values()) else 1
    finally:
        close_isolated_client(client, real)


if __name__ == "__main__":
    raise SystemExit(main())
