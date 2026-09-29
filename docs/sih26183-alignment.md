# SIH26183 — Problem Statement Alignment

**PS 26183** — Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges from Victim-Reported Suspect Wallet
Addresses through Automated Blockchain Analytics · Ministry of Home Affairs · Indian Cyber Crime Coordination Centre
(I4C), CIS Division · Software · Blockchain & Cybersecurity. Source: *SIH 2026 Software & Hardware Problem
Statements*, PS 26183.

**Status legend:** **EXISTING** — implemented in the NEXUS core today · **PLANNED** — SIH26183 extension, designed
not built · **ACCESS** — depends on official access or data we do not have.

## Required system behaviour

| PS asks the system to… | NEXUS response | Status | Roadmap phase |
|---|---|---|---|
| Ingest wallet addresses reported through cybercrime complaint systems | Wallet intake with chain validation and complaint reference; manual / file intake first | PLANNED | 1 |
| Automatically perform blockchain tracing | Bounded multi-hop trace engine with path reconstruction | PLANNED | 2 |
| Identify associated exchanges or VASPs (nearest VASP receiving direct deposits) | Multi-signal *potential VASP lead* with confidence and evidence path | PLANNED | 4 |
| Detect fund-movement patterns | Rule-based typology engine (layering, fan-in/out, peel chains, rapid movement, mixer / bridge) | PLANNED | 5 |
| Generate actionable intelligence for investigators | Leads + risk + reasoning trail + confirm / reject in the workspace | Core EXISTING, blockchain content PLANNED | 4–8 |

## Key features listed in the PS

| PS feature | NEXUS response | Status |
|---|---|---|
| Blockchain transaction graph analysis | Existing graph engine and NetworkX analytics applied to wallet / transfer graphs | Core EXISTING, adaptation PLANNED |
| Clustering of exchange wallets | Chain-specific clustering (UTXO common-input; account-model deposit-sweep patterns) | PLANNED |
| Detection of intermediary laundering wallets | Role classification + existing bridge / broker (articulation, betweenness) analysis | Core EXISTING, roles PLANNED |
| Identification of cross-chain fund movement | Bridge interactions flagged; investigator-triggered trace on the destination chain | PLANNED |
| Integration with SAHYOG and NCRP | Integration hooks designed; built only with official access | ACCESS |
| Automated alert generation | Trace-on-intake and movement alerts | PLANNED |
| Risk categorisation of wallets | Explainable risk framework (factors → Low / Medium / High) | PLANNED |
| Support multiple blockchain ecosystems | Adapter architecture (Bitcoin, Ethereum / EVM, TRON first) over one common schema | PLANNED |
| Real-time tracing capability | Trace on intake; event-driven alerting in a later phase. No real-time performance is claimed until measured | PLANNED |
| Automated investigative recommendations | Leads with signals, confidence and risk — always for investigator review | PLANNED |
| Analytics dashboards for LEAs | Existing investigator workspace and command centre, extended with wallet, trace and lead views | Core EXISTING, blockchain views PLANNED |

## Expected solution items

| PS expected solution | NEXUS response | Status |
|---|---|---|
| Automated VASP identification | Potential VASP lead engine (never an automatic verdict) | PLANNED |
| Tracing of suspect wallets | Trace engine | PLANNED |
| Cross-chain transaction analytics | Bridge detection + linked traces | PLANNED |
| Fund-flow visualisation | Existing Cytoscape.js graph + planned trace-path view | Core EXISTING, path view PLANNED |
| Integration with LEA systems | API-first backend; integrations with access | ACCESS |
| Standardised investigation reports | Existing ReportLab PDF engine extended with blockchain sections | Core EXISTING, sections PLANNED |
| API integrations · scalable blockchain indexing | Adapter layer, caching, bounded traces | PLANNED |
| AI/ML-assisted risk detection · automated pattern recognition for fraud typologies | Rule-based typologies first; ML only after labelled data (Phase 7) | PLANNED |
| Reduce response time · improve freezing of proceeds · coordination with VASPs · stronger digital evidence | Targeted outcomes; **not yet measured** | — |

## What NEXUS adds beyond the PS

- **Evidence on every edge:** each lead links to transaction hashes, amounts, times, hops and label sources.
- **One signal ≠ attribution:** corroboration-gated leads, adapted from the corroboration rule already enforced by
  the NEXUS cross-case matcher.
- **Human verification and audit:** every lead is confirmed or rejected by an investigator and logged.
- **What-if analysis:** remove a wallet and recompute (existing).
