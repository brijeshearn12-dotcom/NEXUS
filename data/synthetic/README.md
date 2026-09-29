# Synthetic data (SIH26183)

**Everything in this folder is synthetic.** No address, transaction, label or complaint here comes from a real
investigation. Addresses use a `SYN-` prefix so they cannot collide with real wallets; transaction hashes are
placeholders.

| File | Purpose |
|---|---|
| `demo_scenario_v1.json` | The NEXUS demo story and the first validation fixture. A victim-reported suspect wallet is traced over four hops (fan-out → fan-in → deposit address → exchange hot wallet), with a mixer side-branch, to a *potential VASP lead*. Contains the transfers, background exchange activity, labels and the planted **ground truth** (expected path, roles, cluster, patterns, lead, and a safeguard case). |

The scenario matches the illustration on slide 2 of the SIH26183 deck. It is used by the planned scenario loader
(`POST /api/scenarios/load`, see [docs/api-design.md](../../docs/api-design.md)) and by the validation plan in
[docs/methodology.md](../../docs/methodology.md#9-validation-methodology). No code consumes it yet.
