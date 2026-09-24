"""production_smoke_test.py — Safe, non-destructive smoke tests for NEXUS production deployment.

SIH26189GREEN | AI-Powered Criminal Network Analysis System

Verifies:
1. Backend /health & /health/db
2. Corpus stats & Case Priority queue (/api/corpus/stats, /api/cases/priority)
3. Live Case Retrieval & Graph endpoints (/api/cases, /api/cases/{id}/graph)
4. Case Analysis & Reasoning Trail (/api/cases/{id}/analysis)
5. Validation Benchmark (/api/validate)
6. Report PDF generation (/api/cases/{id}/report)
7. Frontend Routes (/ and /command-center)

SAFETY RULE:
This script is completely read-only. It never modifies, seeds, or deletes production data.
"""

from __future__ import annotations

import os
import sys
import httpx

TEST_BASE_URL = os.environ.get("TEST_BASE_URL", "").rstrip("/")
BACKEND_URL = os.environ.get("BACKEND_URL", TEST_BASE_URL or "https://nexus-backend-obb9.onrender.com").rstrip("/")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://nexus-frontend-qtak.onrender.com").rstrip("/")

def run_smoke_test() -> bool:
    print("=" * 65)
    print("NEXUS PRODUCTION SMOKE TEST")
    print(f"Backend:  {BACKEND_URL}")
    print(f"Frontend: {FRONTEND_URL}")
    print("=" * 65)

    results: dict[str, bool] = {}

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        # 1. Health check
        try:
            r = client.get(f"{BACKEND_URL}/health")
            ok = r.status_code == 200 and r.json().get("status") == "ok"
            results["Health"] = ok
            print(f"[{'PASS' if ok else 'FAIL'}] Backend /health: HTTP {r.status_code} - {r.text.strip()}")
        except Exception as e:
            results["Health"] = False
            print(f"[FAIL] Backend /health: Exception {e}")

        # 2. DB Health check
        try:
            r = client.get(f"{BACKEND_URL}/health/db")
            data = r.json() if r.status_code == 200 else {}
            ok = r.status_code == 200 and data.get("status") == "ok" and data.get("database") == "connected"
            results["DB Health"] = ok
            print(f"[{'PASS' if ok else 'FAIL'}] Backend /health/db: HTTP {r.status_code} - {r.text.strip()}")
        except Exception as e:
            results["DB Health"] = False
            print(f"[FAIL] Backend /health/db: Exception {e}")

        # 3. Corpus Stats
        try:
            r = client.get(f"{BACKEND_URL}/api/corpus/stats")
            data = r.json() if r.status_code == 200 else {}
            ok = r.status_code == 200 and "documents" in data and "cases" in data
            results["Corpus Stats"] = ok
            print(f"[{'PASS' if ok else 'FAIL'}] Corpus Stats: HTTP {r.status_code} - docs={data.get('documents')}, cases={data.get('cases')}, entities={data.get('entities')}, edges={data.get('edges')}, validation={data.get('validation_score')}")
        except Exception as e:
            results["Corpus Stats"] = False
            print(f"[FAIL] Corpus Stats: Exception {e}")

        # 4. Case Priority Queue
        case_id_for_testing = None
        try:
            r = client.get(f"{BACKEND_URL}/api/cases/priority")
            data = r.json() if r.status_code == 200 else {}
            items = data.get("items", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            ok = r.status_code == 200 and len(items) > 0
            results["Case Priority Queue"] = ok
            if ok:
                case_id_for_testing = items[0].get("case_id")
            print(f"[{'PASS' if ok else 'FAIL'}] Case Priority Queue: HTTP {r.status_code} - {len(items)} cases found (first: {case_id_for_testing})")
        except Exception as e:
            results["Case Priority Queue"] = False
            print(f"[FAIL] Case Priority Queue: Exception {e}")

        # 5. Case Graph
        if case_id_for_testing:
            try:
                r = client.get(f"{BACKEND_URL}/api/cases/{case_id_for_testing}/graph")
                data = r.json() if r.status_code == 200 else {}
                ok = r.status_code == 200 and "nodes" in data and "edges" in data
                results["Case Graph"] = ok
                print(f"[{'PASS' if ok else 'FAIL'}] Case Graph ({case_id_for_testing}): HTTP {r.status_code} - nodes={len(data.get('nodes', []))}, edges={len(data.get('edges', []))}")
            except Exception as e:
                results["Case Graph"] = False
                print(f"[FAIL] Case Graph: Exception {e}")

            # 6. Case Analysis
            try:
                r = client.get(f"{BACKEND_URL}/api/cases/{case_id_for_testing}/analysis")
                data = r.json() if r.status_code == 200 else {}
                ranked = data.get("ranked_individuals", [])
                ok = r.status_code == 200 and data.get("status") == "ok" and len(ranked) > 0
                results["Case Analysis"] = ok
                print(f"[{'PASS' if ok else 'FAIL'}] Case Analysis ({case_id_for_testing}): HTTP {r.status_code} - status={data.get('status')}, ranked_individuals={len(ranked)}, communities={len(data.get('communities', []))}, flags={len(data.get('flags', []))}")
            except Exception as e:
                results["Case Analysis"] = False
                print(f"[FAIL] Case Analysis: Exception {e}")

            # 7. Report PDF
            try:
                r = client.get(f"{BACKEND_URL}/api/cases/{case_id_for_testing}/report")
                ok = r.status_code == 200 and r.headers.get("content-type") == "application/pdf" and len(r.content) > 500
                results["Report Generation"] = ok
                print(f"[{'PASS' if ok else 'FAIL'}] Report Generation ({case_id_for_testing}): HTTP {r.status_code} - PDF bytes={len(r.content)}")
            except Exception as e:
                results["Report Generation"] = False
                print(f"[FAIL] Report Generation: Exception {e}")

        # 8. Validation API
        try:
            r = client.get(f"{BACKEND_URL}/api/validate")
            data = r.json() if r.status_code == 200 else {}
            ok = r.status_code == 200 and ("dataset" in data or "benchmark" in data or "score" in data)
            results["Validation"] = ok
            print(f"[{'PASS' if ok else 'FAIL'}] Validation API: HTTP {r.status_code} - score={data.get('score')} ({data.get('dataset', 'benchmark')})")
        except Exception as e:
            results["Validation"] = False
            print(f"[FAIL] Validation API: Exception {e}")

        # 9. Frontend Landing Page
        try:
            r = client.get(f"{FRONTEND_URL}/")
            ok = r.status_code == 200 and "<!DOCTYPE html>" in r.text
            results["Frontend Landing"] = ok
            print(f"[{'PASS' if ok else 'FAIL'}] Frontend Landing: HTTP {r.status_code}")
        except Exception as e:
            results["Frontend Landing"] = False
            print(f"[FAIL] Frontend Landing: Exception {e}")

        # 10. Frontend Command Center Page
        try:
            r = client.get(f"{FRONTEND_URL}/command-center")
            ok = r.status_code == 200 and "<!DOCTYPE html>" in r.text
            results["Frontend Command Center"] = ok
            print(f"[{'PASS' if ok else 'FAIL'}] Frontend Command Center: HTTP {r.status_code}")
        except Exception as e:
            results["Frontend Command Center"] = False
            print(f"[FAIL] Frontend Command Center: Exception {e}")

    print("\n" + "=" * 65)
    print("PRODUCTION SMOKE TEST SUMMARY")
    print("=" * 65)
    for test_name, passed in results.items():
        print(f"{test_name:<28}: {'PASS' if passed else 'FAIL'}")
    print("=" * 65)

    all_passed = all(results.values())
    return all_passed

if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
