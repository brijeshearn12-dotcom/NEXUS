# NEXUS Task 6.2 — Panels, Audit Trail, What-If Control & Guided Analysis Flow

## 1. Overview & Architecture
Task 6.2 transforms the NEXUS platform into a single, cohesive, judge-ready criminal intelligence workbench. It bridges entity extraction, alias resolution, relationship network construction, deterministic graph analytics, scenario disruption simulation, and human verification into one unified guided experience.

```text
User opens a case
        ↓
    Clicks "Analyse Case"
        ↓
 ┌─────────────────────────────────────────────────────────────────┐
 │ 1. POST /api/cases/{id}/extract      (Extract entities)         │
 │ 2. POST /api/cases/{id}/resolve      (Resolve aliases)          │
 │ 3. POST /api/cases/{id}/build-graph  (Construct NetworkX graph) │
 │ 4. GET  /api/cases/{id}/analysis     (Calculate centrality/flags)│
 └─────────────────────────────────────────────────────────────────┘
        ↓
 Unified Command-Center Workbench:
 ┌──────────────────────────────────┬──────────────────────────────┐
 │  Interactive Cytoscape Canvas    │  Entity Inspector (HITL)     │
 │  What-If Scenario Simulation     │  Key Individuals Panel       │
 │  Validation Benchmark Badge      │  Flagged Patterns Panel      │
 │  Graph Search & Filtering        │  Read-Only Audit Trail       │
 └──────────────────────────────────┴──────────────────────────────┘
```

---

## 2. Guided-Flow Orchestration ("Analyse" Pipeline)
The guided flow replaces manual multi-step API calls with a single frontend-orchestrated pipeline (`GuidedFlowModal.tsx`):
1. **Extraction** (`POST /api/cases/{case_id}/extract`): Discovers case documents, applies deterministic regex + spaCy NER + Hindi fallback, and records extraction events in `audit_log`. Idempotent: reports `already_extracted=True` if entities already exist.
2. **Alias Resolution** (`POST /api/cases/{case_id}/resolve`): Merges cross-document entity aliases with conservative thresholding (`0.85`), preventing over-clustering.
3. **Graph Construction** (`POST /api/cases/{case_id}/build-graph`): Rebuilds the NetworkX relationship graph and co-occurrence edge weights.
4. **Network Analysis** (`GET /api/cases/{case_id}/analysis`): Computes degree, betweenness, PageRank, combined centrality scores, Louvain communities, pattern flags, and 6-step reasoning trails.

### Live Progress & Failure Handling
- Progress UI updates each step status (`✓ Complete`, `Running…`, `✕ Failed`) only when the corresponding backend endpoint returns 200.
- If any step fails (e.g. backend stopped midway), the pipeline halts immediately, marks the failed step, reports the error message, and enables the **"Retry Pipeline"** action without swallowing errors or leaving corrupt states.

---

## 3. Authoritative Audit Logging
Every action in NEXUS produces an immutable, authoritative event stored in MongoDB `audit_log`:
- `extraction_started` & `extraction_completed`
- `resolve_case_aliases`
- `build_graph_for_case`
- `network_analysis_completed`
- `confirmed_entity` / `rejected_entity`
- `confirmed_flag` / `rejected_flag`
- `what_if_simulation_executed`

### Read-Only Audit Trail Panel (`AuditTrailPanel.tsx`)
- Endpoint: `GET /api/cases/{case_id}/audit`
- Displays a reverse-chronological timeline with timestamps, action badges, actor attribution, and result summaries.
- Click any entry to inspect JSON input parameters and target IDs.
- Strictly read-only: no editing, deletion, or clearing is permitted.

---

## 4. Key Individuals Panel (`KeyIndividualsPanel.tsx`)
- Driven directly by Task 5.1 `ranked_individuals` from `/api/cases/{case_id}/analysis`.
- Displays Rank, Name, Entity Type, Combined Centrality Score ($0.50 \cdot \text{deg} + 0.20 \cdot \text{bet} + 0.30 \cdot \text{PR}$), Degree, Betweenness, PageRank, Community ID, Confidence, and Verification Status.
- **Neutral Language**: Labeled strictly as "Key Individual" based on graph centrality; never labels individuals as "ringleader", "mastermind", or "criminal" without judicial record proof.
- **Interactivity**: Clicking any individual focuses the node on the Cytoscape graph canvas and toggles its 6-step deterministic Reasoning Trail.

---

## 5. Flagged Patterns Panel (`FlaggedPatternsPanel.tsx`)
- Surfaces rule-based structural network flags: Bridge Nodes, High-Density Clusters, Cross-Case Recurrence.
- Displays severity, description, target entity, and expandable topological reasoning trail.
- Integrates Human-in-the-Loop (HITL) `Confirm` / `Reject` controls persisting directly to MongoDB `flags` via `PATCH /api/cases/{case_id}/flags/{flag_id}/verify`.

---

## 6. Academic Validation Benchmark Badge (`ValidationBadge.tsx`)
- Live endpoint: `GET /api/validate`
- Validates the NEXUS analytics pipeline against the documented Noordin Top covert terrorist network dataset.
- Real score: **"4 of top 5 match documented figures"** ($80\%$ precision on top-5 centrality).
- Interactive popup displays ground truth literature (Roberts & Everton 2011; ICG Asia Report No. 114; Everton 2012), top-k tested ($k=5$), match count ($4$), and dataset limitations.
- Honest disclaimer: *"Measures agreement with documented network figures; does not establish legal guilt, responsibility, or intent."*

---

## 7. What-If Scenario Disruption Simulation (`WhatIfControl.tsx`)
- Endpoint: `POST /api/cases/{case_id}/simulate`
- Operates strictly in-memory on a subgraph copy; **never modifies or deletes the stored MongoDB graph**.
- Workflow:
  1. Select any central entity on the graph or Key Individuals list.
  2. Click **"Simulate Removal"**.
  3. Backend recalculates centrality, Louvain communities, and flags with the entity removed.
  4. Cytoscape canvas reacts immediately: removes the excluded node and connected edges, adjusting remaining node sizes.
  5. UI enters **What-If Simulation Active** mode with a clear amber warning banner.
  6. Side-by-side Before/After comparison table highlights ranking changes and score deltas.
  7. Clicking **"Exit Simulation"** or refreshing the page immediately restores the real baseline graph.

---

## 8. Verification & Test Evidence
- **TypeScript**: `npm run typecheck` &rarr; `0 errors`.
- **ESLint**: `npm run lint` &rarr; `0 warnings, 0 errors`.
- **Next.js Production Build**: `npm run build` &rarr; Route `/cases/[id]/graph` compiled successfully ($146\text{ kB}$ bundle, $248\text{ kB}$ first load).
- **Backend Test Suite**: `pytest` &rarr; 15 passed across `test_guided_flow_and_audit.py`, `test_verification_hitl.py`, and `test_validation_and_simulation.py`.
- **Real Case E2E Run**:
  - Target Case: `case_100478559` (Madras High Court)
  - Guided flow executed: Extract (225 entities verified) &rarr; Resolve (17 merges) &rarr; Build Graph (211 nodes) &rarr; Analysis (57 ranked individuals, 10 communities, 14 flags).
  - Selected Central Node `Rajasthan` removed in simulation: ranking changed, top-3 shifted from `[Rajasthan, Tamil Nadu, Mr.KA.Ramakrishnan]` to `[Tamil Nadu, Mr.KA.Ramakrishnan, Khotkar]`.
  - Stored MongoDB graph remained 100% intact ($216$ nodes preserved).
  - Audit trail verified: 15 authoritative events recorded with exact UTC timestamps and actor IDs.

---

## 9. Known Limitations & Constraints
- Dark network and legal corpus extraction reflects the text available in court judgments; unmentioned conspirators cannot be inferred without evidence.
- Simulation is temporary in-memory UI state; browser refresh intentionally restores the real database state.
