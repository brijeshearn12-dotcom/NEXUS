# NEXUS × SIH26183 — Roadmap

Phase 0 is the current priority. Phases marked **MVP** are on the critical path to the minimum convincing product
defined in [project-plan.md](project-plan.md#mvp-definition). Dates are TBD; sizes are rough effort estimates
(S ≈ days, M ≈ 1–2 weeks, L ≈ several weeks) and will be revised once owners are assigned.

| Phase | Name | MVP | Size | Status |
|---|---|---|---|---|
| 0 | Submission | — | S | **CURRENT PRIORITY** |
| 1 | Blockchain foundation | ✔ | M | Planned |
| 2 | Trace engine | ✔ | M | Planned |
| 3 | Wallet intelligence | ✔ (roles + labels) | M | Planned |
| 4 | VASP attribution | ✔ | M | Planned |
| 5 | Fraud / laundering typologies | partial | M | Planned |
| 6 | Risk engine | ✔ (basic) | S | Planned |
| 7 | ML-assisted intelligence | — | L | Planned (after data exists) |
| 8 | Investigator dashboard | ✔ | M | Planned |
| 9 | Reporting | ✔ | S | Planned |
| 10 | Cross-complaint intelligence | — | M | Planned |
| 11 | Real-time alerting | — | M | Planned |
| 12 | Integrations | — | L | Planned (subject to access) |

---

## Phase 0 — Submission · CURRENT PRIORITY

**Goal:** PPT + GitHub + SIH submission.
**Tasks:** finalise PPT · finalise repository · README · architecture diagram · roadmap · project screenshots
(TBD — blockchain views do not exist yet) · repository cleanup · submission package · verify PS details · submit.
**Deliverable:** submitted deck; repository with honest status. **Exit:** portal submission confirmed.
Checklist: [submission-checklist.md](submission-checklist.md).

## Phase 1 — Blockchain foundation · MVP

**Tasks:** common transaction schema · wallet input · chain validation · synthetic scenario loader · first live
adapter (see MVP recommendation) · Bitcoin adapter · EVM adapter · TRON adapter · transaction ingestion ·
normalisation · transaction timeline.
**Deliverable:** wallet → transaction dataset (common schema, with provenance).
**Exit:** `demo_scenario_v1` and one live chain load into a case; every transfer has provenance.

## Phase 2 — Trace engine · MVP

**Tasks:** multi-hop traversal · hop limit · time window · value threshold · direction filter · path reconstruction ·
transaction graph (existing graph engine, new node / edge types).
**Deliverable:** wallet → complete trace graph. **Exit:** planted paths in the synthetic scenario are reconstructed.

## Phase 3 — Wallet intelligence · MVP (roles + labels)

**Tasks:** wallet profiling · wallet roles · deposit-wallet detection · hot-wallet detection · intermediary detection ·
chain-specific clustering · known labels (with source and date).
**Deliverable:** wallet intelligence layer. **Exit:** planted roles and clusters recovered; every role lists signals.

## Phase 4 — VASP attribution · MVP

**Tasks:** VASP registry · known wallet labels · deposit / hot-wallet relationship · multi-signal scoring ·
confidence · explanation · evidence path.
**Deliverable:** potential VASP lead engine. **Exit:** correct lead on the synthetic scenario; single-signal cases
produce no lead.

## Phase 5 — Fraud / laundering typologies

**Tasks:** layering · fan-in · fan-out · fragmentation · consolidation · peel chains · rapid movement · mixer
interaction · bridge interaction · cross-chain movement.
**Deliverable:** pattern detection engine (rule-based, existing flag + reasoning-trail mechanism).
**MVP subset:** fan-out, fan-in, rapid movement, mixer interaction.

## Phase 6 — Risk engine · MVP (basic)

**Tasks:** risk factors · scoring framework · severity levels · explanation · investigation priority.
**Deliverable:** explainable risk (factors always shown). Weights documented; not presented as validated.

## Phase 7 — ML-assisted intelligence

Only after sufficient structured data / features exist.
**Tasks:** feature engineering · dataset creation · labelled / synthetic data · baseline model · anomaly detection ·
typology classification · evaluation · explainability.
**Rule:** start with simple, explainable baselines; no claims before held-out evaluation.

## Phase 8 — Investigator dashboard · MVP

**Tasks:** case dashboard · wallet page · graph explorer · transaction timeline · VASP leads · risk panel · evidence
panel · alerts · confirm / reject · audit log. Reuses the existing Next.js workspace, Cytoscape.js graph, inspector,
reasoning trail and audit views.

## Phase 9 — Reporting · MVP

**Tasks:** investigation report · graph export · evidence appendix · transaction table · VASP findings · audit history
· PDF generation (existing ReportLab engine).

## Phase 10 — Cross-complaint intelligence

**Tasks:** complaint model · wallet-to-complaint mapping · shared-wallet detection · shared infrastructure ·
cross-case graph · investigator review. Reuses the existing cross-case matcher's corroboration and review flow.
Requires a legitimate complaint dataset; synthetic complaints until then.

## Phase 11 — Real-time alerting

**Tasks:** transaction event ingestion · event queue · pattern engine · risk update · alert generation ·
notification UI. No real-time performance is claimed until measured.

## Phase 12 — Integrations

**Investigate / design:** NCRP · SAHYOG · blockchain APIs · node providers · VASP intelligence · external threat
intelligence. **Rule:** no integration is claimed until it is available and tested.
