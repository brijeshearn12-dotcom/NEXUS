# NEXUS Core — Prototype Engine

This document describes what is **implemented today** in this repository. It is the engine that the SIH26183
blockchain layer reuses (see [architecture.md](architecture.md)). The prototype was built and tested on its original
dataset — curated Indian court judgments — so the domain-specific parts (judgment extraction, legal-role filtering,
the curated corpus) belong to the prototype, not to the SIH26183 solution.

> The previous README described this prototype in more promotional terms (for example hawala / shell-company
> typologies and "court-ready" dossiers). Those claims were not backed by the code and are not repeated here; the
> earlier text remains available in the git history.

---

## What the engine does

| Component | Implementation | Code |
|---|---|---|
| Provenance model | Every entity, edge and document carries `tier` (primary / secondary / synthetic), `source_ref`, `method` (e.g. `direct_text`, `api`, `derived`), `confidence`, `extracted_at` and free-form `metadata` | `backend/app/models/provenance.py` |
| Graph construction | Case graph built from extracted entities and rule-based edges, stored in MongoDB, loaded into NetworkX | `backend/app/services/graph/` |
| Centrality | Degree, betweenness and PageRank, combined into a ranking with a per-node reasoning trail | `backend/app/services/analytics/centrality.py`, `key_individuals.py` |
| Communities | Louvain community detection (NetworkX) | `backend/app/services/analytics/community.py` |
| Pattern flags | Bridge nodes (articulation points / high-betweenness brokers), cross-case recurrence, density anomalies — each with a reasoning trail | `backend/app/services/analytics/pattern_flags.py` |
| What-if simulation | Remove nodes, recompute the graph and rankings, compare with the original; non-destructive | `POST /api/cases/{case_id}/simulate` |
| Human verification | Confirm / reject entities and flags; decisions persisted | `PATCH /api/cases/{case_id}/flags/{flag_id}/verify`, `/api/validate/confirm`, `/api/validate/reject` |
| Audit trail | Append-only MongoDB collection of analyst decisions (not cryptographically tamper-evident) | `GET /api/cases/{case_id}/audit` |
| Reports | PDF investigation report (ReportLab) | `backend/app/services/report_generator.py` |
| Cross-case matching | Corroboration-gated candidate links between cases, reviewed by an analyst; off unless `ENABLE_CROSS_CASE=true` | `backend/app/services/graph/cross_case_linker.py`, `/api/cross-case/*` |
| Synthetic data | Faker-based synthetic call and financial-transaction edges, explicitly labelled `tier: synthetic` | `backend/app/services/synthetic/` |
| Case triage | Deterministic priority statuses (`Needs Verification`, `Needs Analysis`, `Ready`, `Insufficient Data`) | `GET /api/cases/priority` |
| Extraction (prototype domain) | Regex + spaCy (`en_core_web_sm`) + legal-role filtering; optional Gemini (`gemini-2.0-flash`) fallback, off without a key | `backend/app/services/extraction/` |
| Investigator UI | Next.js 14 + Tailwind CSS; Cytoscape.js graph with inspector, reasoning trail, what-if, audit | `frontend/app/` |

Operational properties verified in the prototype phase (details in
[task-9-demo-readiness-audit.md](task-9-demo-readiness-audit.md)): runs rule-based with no LLM keys and no outbound
network; request-size and input-length limits; internal errors are not echoed in API responses.

---

## API endpoints (existing)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health`, `/health/db` | Liveness and database checks |
| GET | `/api/corpus/stats` | Corpus-level counts |
| GET | `/api/cases`, `/api/cases/priority` | Case list and triage queue |
| POST | `/api/cases/{case_id}/ingest` | Ingest text for a case |
| POST | `/api/cases/{case_id}/extract` · `/resolve` · `/build-graph` | Pipeline steps |
| GET | `/api/cases/{case_id}/graph` | Nodes and edges for visualisation |
| GET | `/api/cases/{case_id}/analysis` | Rankings, communities, flags, reasoning trails |
| POST | `/api/cases/{case_id}/simulate` | What-if simulation |
| PATCH | `/api/cases/{case_id}/flags/{flag_id}/verify` | Confirm / reject a flag |
| GET | `/api/cases/{case_id}/audit` | Audit trail |
| POST / GET / DELETE | `/api/cases/{case_id}/synthetic/*` | Synthetic data generation, summary, clearing |
| GET | `/api/report/{case_id}/pdf` | PDF report |
| GET / PATCH | `/api/entities`, `/api/entities/{entity_id}/verify` | Entities and verification |
| GET / POST / PATCH | `/api/cross-case/*` | Cross-case links (feature-flagged) |
| GET | `/api/validate` | Benchmark harness (prototype) |

Interactive documentation is served at `/docs` when the backend runs.

---

## Running locally

Prerequisites: Python 3.11+ and Node.js 18+. MongoDB is optional for a demo — the offline script below uses an
in-memory database.

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
cd ..
copy .env.example .env          # Linux/macOS: cp .env.example .env ; then set MONGODB_URI
uvicorn app.main:app --reload --port 8000 --app-dir backend
```

```bash
# frontend
cd frontend
npm install
npm run dev                     # reads NEXT_PUBLIC_API_URL (default http://localhost:8000)
```

**Offline demo (no database, no API keys, no network):**

```bash
python scripts/offline_demo_backend.py        # serves the real API on http://127.0.0.1:8765
```

Then start the frontend with `NEXT_PUBLIC_API_URL=http://127.0.0.1:8765`.

## Configuration

Settings are read from the root `.env` (`backend/app/core/config.py`); `.env.example` lists the keys with
placeholders only. Relevant keys: `MONGODB_URI`, `CORS_ORIGINS`, `NEXT_PUBLIC_API_URL`, `GEMINI_API_KEY` (optional),
`ENABLE_CROSS_CASE` (default `false`). Never commit real values.

## Tests

```bash
pytest backend/tests
```

Some tests need a reachable MongoDB and are reported as environment failures without one (see the demo-readiness
audit for the exact list).
