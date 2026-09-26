# Day 9 + Sections 9–13 — Demo Readiness Audit (member1)

**Branch:** `member1` (from `main` @ `fbcb828`) · **Date:** 2026-09-27 · **Author:** member1 work session

This is an evidence log, not a status claim. Every item is **PASS** (tested here), **FAIL**
(tested, broken), **PARTIAL**, or **NOT VERIFIED** (could not be tested with the access available).
Production access (MongoDB URI, Render dashboard, production env vars) was **not** available, so
nothing was deployed or written to production. Production was only observed through public,
read-only GET endpoints.

---

## 1. Task 8.2 — Security & UI hardening (commit `872a2e8`)

| Item | Result | Evidence |
|---|---|---|
| Secrets in tree / full git history | PASS | Plan's grep + wider patterns over all 22 commits on all branches: no real credential; `.env` files git-ignored; `render.yaml` keeps `MONGODB_URI` dashboard-only |
| Input limits on text endpoints | PASS | 8 MB body → 413 (incl. chunked), URL > 2048 → 414, notes/IDs/queries length-limited → 422; `tests/test_security_hardening.py` (10 tests) |
| No internal detail in 500s | PASS | 13 handlers return a safe message; full error still logged |
| P0: Reasoning Trail crashed the page | FIXED | Panel rendered API lists/objects as React children; now normalised (verified in browser) |
| P1: pattern-flag IDs collided | FIXED | IDs were truncated to the case prefix → flags overwrote each other; now unique per entity (`test_flag_ids_are_unique_per_entity_within_a_case`) |
| Cytoscape `notify` console error | FIXED | Reproduced on `main`; CoSE now `animate: "end"`, layouts/animations stopped before destroy |
| Audit times shown as local time | FIXED | Naive UTC timestamps now parsed as UTC |
| "Tamper-evident and immutable" UI wording | FIXED | Replaced with an accurate description (append-only, not cryptographically tamper-evident) |
| Empty / error / backend-down states | PASS | All pages checked at 1366×768 and 768×1024; error + no infinite spinner when backend is down |
| Rule-based path with zero LLM | PASS | All 20 judgments, no keys, network blocked: 8,213 entities, 0 crashes, 0 outbound attempts |
| Provenance on every relevant record | PASS (isolated DB) | Full pipeline on 20 judgments: 0 invalid across 8,213 entities, 36,490 edges, 838 flags, 639 merges, 20 documents; 10 synthetic edges all labelled |
| Two consecutive clean regression passes | PASS* | Both passes identical: backend 155 passed / 1 skipped / 3 env-failures (same as `main`), E2E demo flow 26/26 on two real cases, frontend tsc/lint/build OK |

\* The 3 failing backend tests fail identically on `main`: two need a reachable MongoDB for
`/health/db`, one needs a pre-seeded database. They are **NOT VERIFIED** here, not passed.

---

## 2. Day 9.1 — Production deployment & pre-computation

| Item | Status | Evidence |
|---|---|---|
| Backend start command matches plan | PASS | `render.yaml`: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check `/health` |
| Frontend production build | PASS (local) | `next build` succeeds on member1; production uses Render (`npm run build` / `npm run start`), not Vercel |
| Production backend / DB / frontend reachable | PASS (read-only) | 2026-09-27: `/health` 200, `/health/db` 200 "connected", frontend 200 |
| Production runs the member1 fixes | **NOT DONE** | Production runs `main`; member1 is not merged/deployed (leader merges; push blocked by GitHub 403) |
| Production DB seeded & graphs pre-computed | **PARTIAL** | Read-only `/api/cases/priority`: 20 cases, entities extracted for all, **graphs built for only 5** (`case_100478559`, `105611814`, `105576387`, `141720225`, `112621805`); 15 cases have 0 edges |
| Analysis pre-computed/stored | N/A by design | Analysis is computed on request from the stored graph (in-process NetworkX): ~0.1–0.2 s for demo-size cases, ~3 s for the largest case (local, in-memory DB) |
| Env vars | PARTIAL | Code reads `NEXT_PUBLIC_API_URL` (plan says `NEXT_PUBLIC_API_BASE_URL`) and `INDIAN_KANOON_API_TOKEN`/`_KEY`; `GEMINI_API_KEY`/`GROQ_API_KEY` are not in `render.yaml` — dashboard values NOT VERIFIED |
| Zero live-API dependency at demo time | PASS (local) / NOT VERIFIED (prod) | Only external call site used by the app is the Gemini fallback (conditional). Indian Kanoon is only called by `scripts/fetch_corpus.py`; geocoding module has no callers; Groq is config-only. With network blocked the full demo flow passes (E2E 26/26). None of the 20 curated judgments triggers the LLM fallback; when forced (Devanagari text, dummy key) the call is blocked and extraction still completes rule-based |

**Remaining for production (needs access):**
1. Leader merges member1 → `main` → Render auto-deploys.
2. Build graphs for the demo cases that lack them (UI "Analyse Case" or the API), ideally all 20; large
   Delhi HC cases take ~40 s each to build (measured on the in-memory DB).
3. Open each demo case once after deploy so flags are re-persisted with the new unique IDs. Old
   truncated-ID flag documents (2 per case) will remain in `flags` and inflate/deflate counts until
   the team decides to remove them — a production data decision, not made here.
4. Re-run the E2E flow against production URLs and re-capture backups (§3).

---

## 3. Day 9.2 — Fallback mode & backups

| Item | Status | Evidence |
|---|---|---|
| External AI unavailable | PASS | LLM failure falls back to the rule-based result (tested with network blocked) |
| Backend unavailable / venue network down | PASS (tooling) | `scripts/offline_demo_backend.py` runs the real API offline on a laptop from the committed corpus (in-memory DB, network blocked, 4 demo cases pre-computed in ~9 s); frontend pointed at it with `NEXT_PUBLIC_API_URL` |
| Slow backend / Render cold start | PARTIAL | UI shows a clear "may be waking up — please retry" error, not an infinite spinner; no automatic retry. Mitigation: open `/health` a few minutes before presenting |
| Empty / malformed cached data | PASS | Empty case shows an explicit empty state; unknown case shows a 404 banner with Retry |
| Backup screenshots | PARTIAL | 12 real screenshots via `scripts/capture_demo_screens.mjs` from the local member1 build (0 console errors), saved outside the repo in `Documents/NEXUS-demo-backups/member1-872a2e8-offline-local/`. **Must be re-captured from production** after deploy |
| Backup video recording | NOT DONE | Manual task |
| Phone-hotspot test | NOT DONE | Manual task |

---

## 4. Section 9 — Final demo preparation (the core journey)

Tested end-to-end on the local member1 build with real judgments (browser + `e2e_demo_flow` script):

| Step | Status |
|---|---|
| 1. Open NEXUS / Command Center | PASS |
| 2. Select a real case (`case_100478559`, Madras HC) | PASS |
| 3. Entities / relationships shown | PASS (211 nodes / 180 edges) |
| 4. Provenance / evidence visible | PASS (inspector: tier, method, source document, verbatim evidence) |
| 5. Graph analytics | PASS (57 ranked, 14 flags, 11 communities) |
| 6. Select a high-ranked individual | PASS mechanically — **but see data-quality issue below** |
| 7. Reasoning Trail | PASS on member1 (it **crashes on `main`/production**) |
| 8. What-If / simulate removal | PASS (real recomputation: 224/225 nodes, 166/180 edges, rankings changed, #1 changed) |
| 9. Graph / ranking changes shown | PASS (original vs simulated tables; exit restores the graph) |
| 10. Confirm / reject | PASS (persists after reload; audit entry with correct time; targets exactly one flag) |
| Report download | PASS (valid PDF) |

**Data-quality issue (P1, demo-critical, not fixed — needs a team decision):** the key-individual
ranking includes names from **cited precedents**, place names and counsel. On `case_100478559` the
top five are "Rajasthan", "Mr.KA.Ramakrishnan" (counsel), "Tamil Nadu", "Khotkar", "Mohd" — all
from citations such as *Mohd. Aman v. State of Rajasthan, (1997) 10 SCC 44*. The same pattern
appears on the Allahabad cases (fragments like "Yadav", "Ahmad"). The Reasoning Trail's own evidence
panel shows the citation context, so this is visible on stage. Options: (a) pick a demo case whose
top ranks are clean and rehearse on it; (b) port a citation-context filter into the per-case
pipeline (a core-pipeline change at freeze time — risky); (c) keep the case and explain the
limitation. Not changed here.

---

## 5. Section 10 — 48-hour freeze

**Must still be fixed / done**
- Deploy member1's P0/P1 fixes (Reasoning Trail crash is live in production).
- Decide on the key-individual data-quality issue (§4).
- Pre-compute graphs for every case that may be shown; re-capture backups from production.
- Record the backup video; hotspot test; timed rehearsal.

**Must not be introduced now**: no new features, no pipeline rewrites, no new libraries beyond what
member1 already uses (`mongomock` is test/offline tooling only).

---

## 6. Section 11 — Definition of Done

| Area | Status | Evidence |
|---|---|---|
| Technical | PARTIAL | Core journey, APIs, rule-based path, error handling, tests and build pass locally; 3 DB-dependent tests NOT VERIFIED; production deploy of fixes NOT DONE |
| Product | PARTIAL | Reasoning trail, human-in-the-loop and What-If work on member1; ranking quality undermines "key individual" credibility on the demo case |
| Demo | PARTIAL | Full journey runs without developer intervention locally, 0 console errors; production still has the trail crash; video not recorded |
| Security | PASS | No secrets in repo/history; input limits; no internal detail in errors. (No authentication — out of scope per plan) |
| Deployment | PARTIAL | Production up and connected; only 5/20 cases pre-computed; fixes not deployed |

---

## 7. Section 12 — Emergency scope-cut readiness

The real corpus and the P0 core (extraction → resolution → graph → centrality → provenance →
reasoning trail → human verification → What-If) all work locally. If time runs short: keep the
core demo on the pre-computed cases, drop Command-Center extras before anything in the core, and do
not merge the separate cross-case feature branch unless it has been reviewed and tested on `main`.
Stabilise (deploy fixes, pre-compute, rehearse) rather than add features.

---

## 8. Section 13 — Judge-facing claims

| Claim | Verdict | Basis |
|---|---|---|
| NLP + graph analytics on Indian criminal judgment text | SUPPORTED | 20 Indian Kanoon judgments (14 distinct — 6 copies of one Delhi HC judgment, 2 of one Bombay HC judgment) |
| Provenance-first design | SUPPORTED | 0 records missing provenance (§1); provenance shown in the UI |
| Human verification (confirm/reject) | SUPPORTED | Entities and flags; persists; audit-logged |
| Explainable reasoning | SUPPORTED on member1 | Trail per ranking/flag; crashes on current production |
| What-If simulation | SUPPORTED | Real recomputation, non-destructive |
| spaCy / rule-based extraction | SUPPORTED | regex + spaCy `en_core_web_sm` + legal-role filter |
| Optional LLM fallback | PARTIALLY SUPPORTED | Gemini fallback implemented and degrades safely; never triggered by the curated corpus; **Groq not implemented** |
| NetworkX analytics | SUPPORTED | degree, betweenness, PageRank, NetworkX Louvain, articulation points, density |
| Real Indian judgments | SUPPORTED | see first row (count distinct judgments honestly) |
| Synthetic data clearly labelled | SUPPORTED | `tier: synthetic`, SYNTHETIC_* edge types, UI legend; 0 mislabelled |
| Rule-based operation with zero LLM | SUPPORTED | 20/20 judgments, 0 outbound calls |
| Validated against the Noordin network | PARTIALLY SUPPORTED | Harness uses a hand-entered **19-person, 21-edge subset** of the 79-person published network; "4 of top 5" is measured on that subset |
| Extraction accuracy figures (e.g. F1 84%) | NOT VERIFIED | Reported in earlier docs; not reproduced here |
| Cross-case candidate matching | NOT ON member1/main | Lives only on `feature/cross-case-match-proposals` (not merged, not deployed) |
| Tamper-proof / immutable audit, blockchain, authentication | NOT SUPPORTED | Audit log is a normal MongoDB collection; no auth |
