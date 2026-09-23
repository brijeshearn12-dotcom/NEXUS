# NEXUS Task 6.1 — Interactive Graph, Reasoning Trail & Human-in-the-Loop Verification

## 1. Overview
NEXUS Task 6.1 delivers the complete interactive relationship graph experience, surfacing evidence-backed criminal network analytics and enabling human-in-the-loop (HITL) verification that persists in MongoDB.

Judges and analysts can:
1. **Search Entities**: Debounced instant search across entities, accused, aliases, and organizations with zoom and focus on target nodes.
2. **Interactive Graph Canvas**: Real Cytoscape.js canvas powered by `/api/cases/{case_id}/graph` and enriched by `/api/cases/{case_id}/analysis`.
3. **Visual Encoding**:
   - **Node Sizing**: Scales with Task 5.1 combined centrality score ($24\text{px}$ to $56\text{px}$).
   - **Node Color**: Standardized entity type tokens (Person/Accused: `#EF4444`, Organization: `#8B5CF6`, Location: `#06B6D4`, Vehicle: `#10B981`, Phone: `#14B8A6`, Lawyer: `#F59E0B`, Judge: `#6B7280`, Other: `#3B82F6`).
   - **Node Borders**: Confirmed ($3.5\text{px}$ solid green), Unverified ($2.5\text{px}$ solid amber), Rejected ($2\text{px}$ dashed slate with $45\%$ opacity).
   - **Edge Styling**: Primary evidence ($1.5\text{px}-6\text{px}$ solid), Synthetic/Inferred relationships (dashed `[6, 4]`).
4. **Side-Panel Entity Inspector**: Click any node to inspect evidence, connected neighbors, centrality metrics, and provenance.
5. **Deterministic 6-Step Reasoning Trail**:
   $$\text{INPUT} \longrightarrow \text{EVIDENCE} \longrightarrow \text{REASONING} \longrightarrow \text{RESULT} \longrightarrow \text{CONFIDENCE} \longrightarrow \text{SOURCE}$$
6. **Human-in-the-Loop (HITL) Verification**:
   - Confirm or reject entities via `PATCH /api/entities/{id}/verify`.
   - Confirm or reject pattern flags via `PATCH /api/cases/{case_id}/flags/{flag_id}/verify`.
   - Rejected entities are never deleted from the network; their status is updated and visually muted.
   - All verification decisions are recorded in `audit_log` with actor, timestamp, and rationale.
7. **Persistence Verification**: Refreshing or reloading the page immediately queries MongoDB and reflects the saved verification statuses.

---

## 2. Real Demonstration Case
- **Case ID**: `case_100478559`
- **Corpus Title**: *Balakarupasamy vs State Represented By on 13 August, 2019* (Madras High Court)
- **Topological Stats**: 225 nodes, 196 edges, 57 ranked individuals, 11 Louvain communities, 14 automated pattern flags.
- **Route**: `/cases/case_100478559/graph`

---

## 3. API Endpoints
| Endpoint | Method | Description |
|---|---|---|
| `/api/cases/{case_id}/graph` | `GET` | Case nodes and edges with provenance and verification status |
| `/api/cases/{case_id}/analysis` | `GET` | Centrality rankings, Louvain communities, pattern flags, and reasoning trails |
| `/api/entities/{entity_id}/verify` | `GET` | Inspect current verification status and provenance for an entity |
| `/api/entities/{entity_id}/verify` | `PATCH` | Update verification status (`confirmed`, `rejected`, `unverified`) with audit trail |
| `/api/cases/{case_id}/flags/{flag_id}/verify` | `PATCH` | Update pattern flag verification status with audit trail |
| `/api/validate/confirm` | `POST` | Global confirmation endpoint for entities, edges, and flags |
| `/api/validate/reject` | `POST` | Global rejection endpoint for entities, edges, and flags |

---

## 4. Verification & Testing
- **Frontend Typecheck & Build**:
  - `npm run typecheck`: 0 errors
  - `npm run lint`: 0 warnings, 0 errors
  - `npm run build`: Next.js 14 production build succeeded; `/cases/[id]/graph` optimized as dynamic client component.
- **Backend Test Suite**:
  - 121 existing unit and integration tests passed (`test_analytics.py`, `test_validation_and_simulation.py`, etc.).
  - New test suite `test_verification_hitl.py` passed (2/2 tests verifying entity and flag lifecycles and MongoDB audit logs).
  - End-to-end live check verified entity verification and flag persistence across MongoDB reloads.
