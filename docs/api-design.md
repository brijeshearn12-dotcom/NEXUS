# NEXUS for SIH26183 — API Design (draft)

> **Design only — none of the endpoints in section 2 exist yet.** Existing endpoints are listed in
> [prototype-engine.md](prototype-engine.md#api-endpoints-existing). Names and shapes may change during Phase 1–4.

A blockchain investigation is a NEXUS **case**, so the existing case endpoints keep working unchanged: graph
(`GET /api/cases/{case_id}/graph`), analysis, what-if (`POST .../simulate`), audit (`GET .../audit`) and PDF report.
New resources are added under the case.

## 1. Conventions

- JSON over HTTPS; UTC ISO-8601 timestamps; amounts as decimal strings in asset units plus the raw integer.
- `chain` values: `bitcoin`, `ethereum`, `tron` (more via adapters); `synthetic` for demo data.
- Every returned finding includes `evidence[]` (transaction hashes and label sources) and `provenance`.
- Errors follow the existing safe-error contract (no internal details in responses).

## 2. Planned endpoints

| Method | Path | Purpose | Phase |
|---|---|---|---|
| POST | `/api/cases/{case_id}/wallets` | Register a victim-reported wallet (address, chain, complaint ref) | 1 |
| GET | `/api/wallets/{chain}/{address}` | Wallet profile: counts, inflow / outflow, timeline, counterparties, labels, roles | 3 |
| POST | `/api/cases/{case_id}/traces` | Start a trace from a wallet with parameters | 2 |
| GET | `/api/cases/{case_id}/traces/{trace_id}` | Trace status, paths and statistics | 2 |
| GET | `/api/cases/{case_id}/leads` | Potential VASP leads with signals, confidence, risk | 4 |
| PATCH | `/api/cases/{case_id}/leads/{lead_id}/verify` | Investigator confirm / reject (writes the audit trail) | 4 |
| GET | `/api/cases/{case_id}/patterns` | Typology flags with evidence (reuses the flag model) | 5 |
| GET | `/api/cases/{case_id}/risk` | Risk level with contributing factors | 6 |
| GET | `/api/alerts` · POST `/api/alerts/{alert_id}/ack` | Alert feed and acknowledgement | 11 |
| GET | `/api/cross-complaint/links` | Wallets / infrastructure shared across complaints (reuses cross-case review flow) | 10 |
| POST | `/api/scenarios/load` | Load a synthetic scenario (e.g. `demo_scenario_v1`) into a case — demo and validation only | 1 |

## 3. Key payloads

**Register wallet**

```json
{ "address": "SYN-SUSPECT-01", "chain": "synthetic", "complaint_ref": "TBD", "incident_time": "2026-06-14T13:58:00Z" }
```

**Start trace**

```json
{ "wallet": "SYN-SUSPECT-01", "chain": "synthetic", "direction": "out", "max_hops": 5,
  "window": { "from": "2026-06-14T13:58:00Z", "to": "2026-06-21T13:58:00Z" }, "min_value": "10" }
```

**Transfer (common schema)**

```json
{ "chain": "synthetic", "tx_hash": "0x7c1e…a09b", "block_number": 0, "block_time": "2026-06-14T14:41:05Z",
  "from_address": "SYN-W3", "to_address": "SYN-DEPOSIT-01", "asset": "USDT", "amount": "4400", "amount_raw": "4400000000",
  "hop": 3, "provenance": { "tier": "synthetic", "source_ref": "demo_scenario_v1", "method": "derived", "confidence": 1.0 } }
```

**Lead**

```json
{ "lead_id": "lead_…", "vasp": "Exchange X (synthetic label)", "endpoint_wallet": "SYN-HOT-01",
  "path": ["SYN-SUSPECT-01", "SYN-W1", "SYN-W3", "SYN-DEPOSIT-01", "SYN-HOT-01"],
  "signals": [ { "type": "known_label", "evidence": ["label:synthetic-labels-v1#SYN-HOT-01"] },
               { "type": "deposit_sweep", "evidence": ["0x…"] },
               { "type": "cluster_membership", "evidence": ["cluster:C-7"] } ],
  "confidence": "medium", "risk": { "level": "high", "factors": ["vasp_proximity", "layering", "rapid_movement", "mixer_exposure"] },
  "status": "proposed" }
```

**Verify lead**

```json
{ "decision": "confirmed", "note": "Matches VASP response", "analyst": "TBD" }
```

## 4. Open decisions (TBD)

- First live chain adapter for the MVP (recommendation in [project-plan.md](project-plan.md#mvp-definition)).
- Label-set sources and licensing.
- Authentication and access control before any real case data (the prototype has none).
- Async execution for long traces (job queue) versus bounded synchronous traces for the MVP.
