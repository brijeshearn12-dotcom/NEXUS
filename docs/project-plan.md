# NEXUS × SIH26183 — Project Plan

Master engineering document: MVP definition, demo scenario, differentiators, task tracker and the post-submission
plan. Phases are described in [roadmap.md](roadmap.md). Owners are **UNASSIGNED** until the team provides names.

---

## MVP definition

The smallest convincing NEXUS for SIH26183. Everything else is an enhancement.

| # | MVP capability | Acceptance criteria | Builds on |
|---|---|---|---|
| 1 | Enter wallet | Address + chain + complaint reference accepted; invalid formats rejected with a clear message | New (intake) |
| 2 | Select chain | `synthetic` + one live chain | New (adapters) |
| 3 | Retrieve / load transaction data | Transfers in the common schema, each with provenance | New + existing provenance model |
| 4 | Trace multiple hops | Bounded by hops / window / value; planted paths reconstructed | New (trace engine) |
| 5 | Build graph | Wallets and transfers stored and shown in the graph view | **Existing** graph engine + Cytoscape.js |
| 6 | Identify wallet roles | Suspect, intermediary, deposit, hot, mixer — each with signals | New (resolution) + existing bridge analysis |
| 7 | Show potential VASP endpoint | Lead with ≥ 2 corroborating signals and confidence; single signal → no lead | New (attribution) |
| 8 | Show evidence path | Every hop lists tx hash, time, amount; reasoning trail per lead | **Existing** reasoning-trail mechanism |
| 9 | Generate explainable risk | Level + contributing factors shown | New (risk framework) |
| 10 | Investigator dashboard | Case view with graph, trace path, leads, risk, evidence | **Existing** workspace, extended |
| 11 | Confirm / reject lead | Decision persisted and written to the audit trail | **Existing** verification + audit |
| 12 | Generate report | PDF with path, evidence, lead, risk, decision, audit history | **Existing** ReportLab engine, extended |

**Recommendation (TBD — team decision):** build the MVP end-to-end on the synthetic scenario first (needed for the
demo and for validation), then add **one** account-based live adapter — Ethereum / EVM via a permitted explorer API,
because the deposit-address clustering heuristic is defined for Ethereum and the API documentation is mature —
followed by TRON and Bitcoin.

---

## Demo scenario

**All data is synthetic** ([`data/synthetic/demo_scenario_v1.json`](../data/synthetic/demo_scenario_v1.json)). It
matches the illustration on slide 2 of the SIH deck.

1. A victim reports a suspect wallet after paying **5,000 USDT (synthetic)**.
2. NEXUS traces the outflows: the suspect wallet **fans out** to two intermediaries (2,500 USDT each).
3. One intermediary forwards to a layering wallet W3; the other sends most funds to W3 and a small amount to a
   **mixer** (flagged, not followed). W3 **consolidates** (fan-in).
4. W3 sends 4,400 USDT to a **deposit address**, which **sweeps** to an **exchange hot wallet** that belongs to a
   labelled cluster — four hops within about 38 minutes (**rapid movement**).
5. NEXUS proposes a **POTENTIAL VASP LEAD — Exchange X (synthetic label)** with signals *known label · deposit →
   hot-wallet sweep · cluster membership*, confidence **medium**, risk **high** (VASP proximity · layering · rapid
   movement · mixer exposure), and the full evidence path.
6. The investigator inspects the evidence, confirms or rejects the lead (audit-logged) and generates the PDF report.

The same file holds the planted ground truth (expected path, roles, cluster, lead and patterns) used by the
validation plan.

---

## Product differentiators

1. Evidence-traceable attribution
2. Multi-hop fund tracing
3. Multi-chain architecture
4. Wallet clustering
5. VASP intelligence
6. Fraud / laundering typology detection
7. Explainable risk
8. Human-in-the-loop verification
9. Cross-complaint intelligence
10. Audit-ready reporting

**Central differentiator:** NEXUS does not merely show where money moved. It explains **where, why, how, with what
evidence — and what the investigator should review.**

---

## Task tracker

Priorities: **P0** critical · **P1** important · **P2** enhancement.
Statuses: BACKLOG · TODO · IN PROGRESS · BLOCKED · DONE.

| ID | Task | Phase | Priority | Status | Owner | Dependency | Deliverable |
|---|---|---|---|---|---|---|---|
| T0-01 | Final 6-slide SIH26183 deck on the official template | 0 | P0 | DONE | UNASSIGNED | — | PPTX |
| T0-02 | Render and visually check all six slides; fix issues | 0 | P0 | DONE | UNASSIGNED | T0-01 | Checked renders |
| T0-03 | Export PDF with working reference links | 0 | P0 | DONE | UNASSIGNED | T0-01 | PDF |
| T0-04 | Verify PS ID, title, organisation, theme, category against the official PS | 0 | P0 | DONE | UNASSIGNED | — | Verified slide 1 |
| T0-05 | Rewrite README for SIH26183 with honest status | 0 | P0 | IN PROGRESS | UNASSIGNED | — | README.md |
| T0-06 | Architecture, methodology, alignment, API design docs | 0 | P0 | IN PROGRESS | UNASSIGNED | — | docs/*.md |
| T0-07 | Roadmap, project plan, submission checklist | 0 | P0 | IN PROGRESS | UNASSIGNED | — | docs/*.md |
| T0-08 | Review and merge the documentation branch into `main` | 0 | P0 | TODO | UNASSIGNED | T0-05..07 | Updated GitHub repository |
| T0-09 | Confirm a submission slot is open for SIH26183 on the portal | 0 | P0 | TODO | UNASSIGNED | — | Confirmation |
| T0-10 | Verify the submission deadline | 0 | P0 | TODO | UNASSIGNED | — | Date / time |
| T0-11 | Decide the "Live Demo" entry on slide 1 (current live app shows the prototype's original dataset) | 0 | P1 | TODO | UNASSIGNED | — | Slide 1 decision |
| T0-12 | Upload and submit the deck | 0 | P0 | TODO | UNASSIGNED | T0-08..11 | Submission receipt |
| T0-13 | Tidy internal notes that still reference the earlier PS (`brain.md`, `design.md`, `memory.md`) | 0 | P2 | TODO | UNASSIGNED | — | Updated notes |
| T0-14 | Blockchain screenshots for README | 0 | P2 | BLOCKED | UNASSIGNED | T8-* | Screenshots |
| T1-01 | Define the common transaction schema (Pydantic) | 1 | P0 | TODO | UNASSIGNED | — | `Transfer` model |
| T1-02 | Wallet intake endpoint + chain format validation | 1 | P0 | TODO | UNASSIGNED | T1-01 | `POST /api/cases/{id}/wallets` |
| T1-03 | Synthetic scenario loader (`demo_scenario_v1`) | 1 | P0 | TODO | UNASSIGNED | T1-01 | Scenario in a case |
| T1-04 | Adapter interface + caching | 1 | P0 | TODO | UNASSIGNED | T1-01 | Adapter base class |
| T1-05 | First live adapter (recommended: EVM) | 1 | P0 | TODO | UNASSIGNED | T1-04 | Adapter + tests |
| T1-06 | TRON adapter | 1 | P1 | BACKLOG | UNASSIGNED | T1-04 | Adapter + tests |
| T1-07 | Bitcoin (UTXO) adapter | 1 | P1 | BACKLOG | UNASSIGNED | T1-04 | Adapter + tests |
| T1-08 | Token-transfer decoding (e.g. USDT) | 1 | P0 | TODO | UNASSIGNED | T1-05 | Normalised token transfers |
| T1-09 | Transaction timeline for a wallet | 1 | P1 | TODO | UNASSIGNED | T1-03 | Timeline data |
| T2-01 | Bounded multi-hop traversal (hops, window, value, direction) | 2 | P0 | TODO | UNASSIGNED | T1-03 | Trace service |
| T2-02 | Path reconstruction with per-hop evidence | 2 | P0 | TODO | UNASSIGNED | T2-01 | Paths |
| T2-03 | Wallet / transfer node and edge types in the graph engine | 2 | P0 | TODO | UNASSIGNED | T2-01 | Graph in the existing view |
| T2-04 | Mixer / bridge stop-and-flag rule | 2 | P1 | TODO | UNASSIGNED | T2-01 | Flags |
| T2-05 | Trace tests on planted paths | 2 | P0 | TODO | UNASSIGNED | T2-02 | pytest |
| T3-01 | Wallet profile (counts, in / out, counterparties) | 3 | P1 | TODO | UNASSIGNED | T1-03 | `GET /api/wallets/...` |
| T3-02 | Role classification with signals | 3 | P0 | TODO | UNASSIGNED | T2-03 | Roles |
| T3-03 | Label store with source and date | 3 | P0 | TODO | UNASSIGNED | — | Label collection |
| T3-04 | Deposit-sweep clustering (account model) | 3 | P0 | TODO | UNASSIGNED | T3-03 | Clusters |
| T3-05 | Common-input clustering (UTXO only) | 3 | P2 | BACKLOG | UNASSIGNED | T1-07 | Clusters |
| T4-01 | VASP registry (synthetic first) | 4 | P0 | TODO | UNASSIGNED | T3-03 | Registry |
| T4-02 | Multi-signal lead scoring + confidence rules | 4 | P0 | TODO | UNASSIGNED | T3-02, T3-04 | Leads |
| T4-03 | Lead reasoning trail + evidence path | 4 | P0 | TODO | UNASSIGNED | T4-02 | Explanations |
| T4-04 | Lead confirm / reject endpoint → audit trail | 4 | P0 | TODO | UNASSIGNED | T4-02 | `PATCH .../leads/{id}/verify` |
| T4-05 | Safeguard tests (single signal → no lead) | 4 | P0 | TODO | UNASSIGNED | T4-02 | pytest |
| T5-01 | Fan-out / fan-in / layering rules | 5 | P0 | TODO | UNASSIGNED | T2-03 | Flags |
| T5-02 | Rapid-movement rule | 5 | P0 | TODO | UNASSIGNED | T2-02 | Flags |
| T5-03 | Mixer / bridge interaction rules | 5 | P1 | TODO | UNASSIGNED | T3-03 | Flags |
| T5-04 | Peel-chain rule | 5 | P2 | BACKLOG | UNASSIGNED | T2-02 | Flags |
| T5-05 | Cross-chain movement (linked traces) | 5 | P2 | BACKLOG | UNASSIGNED | T1-06 | Linked traces |
| T6-01 | Risk factors, weights and severity mapping (documented) | 6 | P0 | TODO | UNASSIGNED | T4-02, T5-01 | Risk service |
| T6-02 | Risk panel with contributing factors | 6 | P1 | TODO | UNASSIGNED | T6-01 | UI |
| T7-01 | Feature engineering on the common schema | 7 | P2 | BACKLOG | UNASSIGNED | T2-*, T5-* | Features |
| T7-02 | Dataset (synthetic + licensed public labelled data) | 7 | P2 | BACKLOG | UNASSIGNED | T7-01 | Dataset |
| T7-03 | Explainable baseline model + held-out evaluation | 7 | P2 | BACKLOG | UNASSIGNED | T7-02 | Evaluation report |
| T8-01 | Wallet page | 8 | P0 | TODO | UNASSIGNED | T3-01 | UI |
| T8-02 | Trace-path view on the graph | 8 | P0 | TODO | UNASSIGNED | T2-02 | UI |
| T8-03 | VASP lead review panel (confirm / reject) | 8 | P0 | TODO | UNASSIGNED | T4-04 | UI |
| T8-04 | Evidence panel (tx hash, time, amount, hop, source) | 8 | P0 | TODO | UNASSIGNED | T4-03 | UI |
| T8-05 | Transaction timeline view | 8 | P1 | TODO | UNASSIGNED | T1-09 | UI |
| T9-01 | Report sections: path, evidence appendix, transaction table, leads, risk, audit | 9 | P0 | TODO | UNASSIGNED | T4-*, T6-01 | PDF |
| T9-02 | Graph export | 9 | P2 | BACKLOG | UNASSIGNED | T2-03 | Export |
| T10-01 | Complaint model + wallet-to-complaint mapping (synthetic complaints) | 10 | P1 | BACKLOG | UNASSIGNED | T1-02 | Model |
| T10-02 | Shared-wallet / shared-infrastructure detection via the cross-case review flow | 10 | P1 | BACKLOG | UNASSIGNED | T10-01 | Proposals |
| T11-01 | Trace-on-intake alerts | 11 | P1 | BACKLOG | UNASSIGNED | T2-01 | Alerts |
| T11-02 | Event ingestion + queue + notification UI | 11 | P2 | BACKLOG | UNASSIGNED | T11-01 | Alert pipeline |
| T12-01 | Integration study: NCRP / SAHYOG access, chain API terms, VASP intelligence sources | 12 | P1 | BACKLOG | UNASSIGNED | — | Study note |
| TX-01 | Validation harness on planted ground truth (paths, clusters, leads, safeguards, timings) | 2–6 | P0 | TODO | UNASSIGNED | T2-05, T4-05 | Validation report |
| TX-02 | Access control before any real case data | — | P1 | BACKLOG | UNASSIGNED | — | Auth |

---

## Future feature plan (beyond the MVP)

- Remaining typologies (peel chains, cross-chain linked traces, unusual velocity).
- Additional chains through adapters.
- ML-assisted typology and anomaly detection (Phase 7), only with evaluation.
- Cross-complaint intelligence on legitimate complaint data (Phase 10).
- Event-driven real-time alerting (Phase 11).
- Integrations with NCRP / SAHYOG and data providers, subject to official access (Phase 12).
- Idea (unscoped): a standardised VASP information-request export built from a confirmed lead.

---

## Post-submission engineering plan

Sequenced sprints; durations TBD once owners are known.

| Sprint | Goal | Tasks |
|---|---|---|
| 1 | Synthetic end-to-end trace | T1-01..04, T2-01..05 |
| 2 | Roles, labels, first leads | T3-02..04, T4-01..05 |
| 3 | Patterns, risk, workspace, report | T5-01..03, T6-01..02, T8-01..04, T9-01 |
| 4 | First live chain + validation | T1-05, T1-08, TX-01 |
