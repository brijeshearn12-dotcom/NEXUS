# `blockchain/` — SIH26183 layer (planned)

**Not implemented yet.** This folder reserves the location of the SIH26183 blockchain layer so the planned modules
have an agreed home. It contains no code; nothing here is imported by the application.

| Planned module | Responsibility | Roadmap phase |
|---|---|---|
| `intake/` | Wallet + chain + complaint reference; address-format validation | 1 |
| `adapters/` | One adapter per chain family (Bitcoin, EVM, TRON) from permitted sources; caching | 1 |
| `normalise/` | Common transaction schema; token transfers; units; UTC | 1 |
| `scenarios/` | Loader for synthetic scenarios (`data/synthetic/`) | 1 |
| `tracing/` | Bounded multi-hop traversal and path reconstruction | 2 |
| `resolution/` | Chain-specific clustering, role classification, labels | 3 |
| `attribution/` | Multi-signal potential VASP leads with confidence | 4 |
| `typology/` | Rule-based laundering patterns (existing flag mechanism) | 5 |
| `risk/` | Explainable risk factors → severity → priority | 6 |
| `alerts/` | Trace-on-intake and movement alerts | 11 |

These modules plug into the existing NEXUS core: graph engine (`services/graph/`), analytics
(`services/analytics/`), provenance model (`models/provenance.py`), audit and reports. Design:
[docs/architecture.md](../../../../docs/architecture.md) · [docs/methodology.md](../../../../docs/methodology.md).
