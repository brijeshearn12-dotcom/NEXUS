# NEXUS for SIH26183 — Methodology

How NEXUS is designed to trace funds, resolve wallets, propose VASP leads, detect laundering patterns and explain
risk. Everything in this document is **PLANNED design** unless marked EXISTING. Thresholds and weights are initial
values to be calibrated on synthetic ground truth — they are not validated.

## 1. Intake

- Input: wallet address, chain, complaint / case reference, optional incident time and amount.
- Validate the address format for the chain (e.g. Bitcoin Base58 / Bech32, EVM hex with checksum, TRON Base58 `T…`).
- Create (or attach to) a NEXUS case, so the existing graph, audit and report machinery apply unchanged.

## 2. Chain adapters and the common schema

Each adapter fetches transactions for an address from a **permitted** source (candidate public APIs: Esplora for
Bitcoin, Etherscan for EVM chains, TronGrid for TRON; or a self-hosted node) and emits `Transfer` records in one
common schema ([architecture.md §4](architecture.md#4-data-model-planned)).

| Chain family | Model | Normalisation notes |
|---|---|---|
| Bitcoin | UTXO | A transaction spends inputs and creates outputs. Transfers are expanded input-address → output-address, keeping `utxo_ref`; value attribution across many inputs / outputs is ambiguous and recorded as such. |
| Ethereum / EVM | Account | Native transfers plus token transfers (e.g. ERC-20 USDT) decoded from logs; contract interactions kept as typed edges. |
| TRON | Account | Native TRX plus TRC-20 token transfers. |

All amounts are stored in asset units with the raw integer kept; times are UTC block times. Every record carries
provenance (adapter, source, fetched-at).

## 3. Multi-hop tracing

Bounded traversal from the seed wallet (default: forward, i.e. following outflows):

- **Parameters:** `max_hops` (default 4–6), `direction` (in / out / both), time window (from the incident), minimum
  value, and dust filtering.
- **Expansion rule:** from each wallet, follow transfers inside the window and above the value threshold, in time
  order after the incoming transfer being followed (funds cannot leave before they arrive).
- **Stops:** a labelled VASP endpoint; a mixer or bridge (flagged, **not followed** — cross-chain continuation is a
  separate, investigator-triggered trace); hop / size limits; high-fan-out service wallets.
- **Output:** the trace graph plus reconstructed paths from the seed to each endpoint, each hop tied to its
  transaction.

Value tracking across hops is heuristic (funds are fungible). Paths are presented as *candidate fund flows* with the
supporting transactions, not as proof that specific coins moved.

## 4. Wallet resolution

### 4.1 Clustering (chain-specific)

| Chain | Heuristic | Caveat |
|---|---|---|
| Bitcoin | **Common-input ownership** — inputs spent together are likely controlled by one entity (Nakamoto 2008 §10; Meiklejohn et al. 2013) | Broken by CoinJoin and collaborative transactions; such transactions are excluded |
| Bitcoin | **Change-address** patterns | Error-prone; used only as a weak signal |
| EVM / TRON | **Deposit-address pattern** — exchange deposit addresses forward (sweep) received funds to a hot wallet (Victor 2020) | Needs repeated sweep behaviour; single forwards are not enough |
| All | Known labels; repeated interaction; behavioural similarity | Label quality varies; source and date are always stored |

Common-input heuristics are **never** applied to account-based chains.

### 4.2 Role classification

| Role | Example signals |
|---|---|
| Suspect wallet | Reported by the victim / complaint |
| Intermediary | Receives and forwards most value quickly; low balance retained |
| Deposit wallet | Receives from many unrelated senders; periodically sweeps to one hot wallet |
| Hot wallet | High volume and degree; receives sweeps from many deposit wallets; labelled or clustered with a VASP |
| Mixer / bridge | Known contract or label; many-to-many flows |
| Broker | High betweenness between otherwise separate groups (existing NEXUS bridge / articulation analysis) |
| Unknown | Default |

Each role is stored with the signals that produced it and a confidence; the investigator can confirm or reject it.

## 5. VASP / exchange attribution

**Output:** a *potential VASP lead* — never a statement of ownership or guilt.

Signals:

1. Known wallet label (with source and date).
2. Deposit → hot-wallet sweep relationship.
3. Cluster membership with labelled VASP wallets.
4. Transaction behaviour consistent with exchange infrastructure.
5. Repeated interaction (the same deposit wallet used by several traced flows).
6. Path proximity (number of hops from the suspect wallet).
7. External intelligence, where lawfully available.

Initial confidence rules (to be calibrated):

| Confidence | Rule |
|---|---|
| High | ≥ 4 independent signals, including a sourced label and a structural signal (sweep or cluster); complete evidence path; no mixer / bridge hop on the path |
| Medium | 3 independent signals, or ≥ 4 when the path contains an obfuscation hop |
| Low | 2 independent signals |
| — (no lead) | A single signal. Recorded as an observation only. |

Example: the synthetic demo scenario has three signals (known label · deposit → hot-wallet sweep · cluster
membership), so its lead is **Medium**.

Safeguards: stale or unverified labels are flagged; mixer / bridge hops lower confidence; every lead lists its
signals and evidence; the investigator's decision is logged in the audit trail.

## 6. Fraud / laundering typology engine

Rule-based first. Initial definitions (parameters TBD):

| Typology | Rule sketch |
|---|---|
| Fan-out (fragmentation) | One wallet splits value to ≥ k wallets within a short window |
| Fan-in (consolidation) | ≥ k wallets send to one wallet within a short window |
| Layering | Fan-out followed by fan-in along the trace |
| Peel chain | Repeated transfers where a small amount peels off and the remainder moves on |
| Rapid movement | ≥ n hops within t minutes |
| Mixer / bridge interaction | Transfer to / from a labelled mixer or bridge |
| Cross-chain movement | Bridge deposit followed by activity on another chain (requires a second trace) |
| Unusual velocity | Activity rate far above the wallet's own baseline |

Each detected pattern becomes a flag with nodes, transactions and a reasoning trail (existing flag mechanism).

## 7. Risk intelligence

An **explainable risk-scoring framework**, not a validated score:

- Factors: VASP proximity, layering, rapid movement, mixer / bridge exposure, value, recurrence across complaints,
  newly created wallet.
- Each factor contributes a documented weight; the total maps to Low / Medium / High severity.
- The UI always shows the contributing factors, e.g. *High — VASP deposit 4 hops away · layering · rapid movement
  (4 hops in 38 min) · mixer exposure*.
- Used for **investigation priority**, not as a judgement about a person.

## 8. ML-assisted intelligence (later phase)

Only after enough structured data exists:

```text
transaction features → behavioural features → ML / analytics engine → typology · anomaly · priority → explanation
```

Plan: feature engineering on the common schema; datasets from synthetic scenarios and public labelled data (e.g.
the Elliptic data set, Weber et al. 2019) where licensing allows; simple, explainable baselines first; evaluation
against held-out data before any claim is made. No model exists today.

## 9. Validation methodology

Synthetic transaction scenarios with **planted ground truth** (e.g.
[`data/synthetic/demo_scenario_v1.json`](../data/synthetic/demo_scenario_v1.json)):

1. **Path reconstruction:** traced paths equal the planted paths.
2. **Wallet clustering:** heuristic clusters compared with planted clusters.
3. **VASP matching:** leads compared with held-out labels.
4. **Provenance:** every lead and flag links to transaction hashes.
5. **Safeguards:** single-signal cases must produce no lead; mixer hops must lower confidence.
6. **Scalability:** synthetic volumes with timings logged.

Results are reported only once measured.

## 10. Human-in-the-loop and audit (EXISTING mechanism)

Investigators confirm or reject leads, roles and flags; each decision is written to the append-only audit trail with
time and note, and appears in the PDF report. The audit log is an application log, not a cryptographic ledger.
