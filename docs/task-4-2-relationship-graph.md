# NEXUS Task 4.2 — Relationship Graph Builder

## Approach & Architecture

The NEXUS Relationship Graph Builder constructs evidence-backed relational networks from entities extracted (Task 3.1) and resolved (Task 4.1) from real Indian criminal judgments. In accordance with core NEXUS principles, relationships are strictly calculated from evidence actually present in the source documents; AI does not hallucinate edges, and weak name similarity alone never produces relationships.

### Architectural Workflow

1. **Entity & Alias Retrieval**: Loads all extracted entities for the requested case and resolves transitive alias chains from `entity_merges` (Task 4.1) so all relationships link canonical entity IDs.
2. **Deterministic Edge Rules**: Evaluates judgment documents against explicit relationship rules:
   - **Person ↔ Person**: Co-accused in the same case (`co_accused`), or co-occurring in the same sentence (`associated_with`).
   - **Person ↔ Organization**: Co-occurring in the same sentence (`associated_with`).
   - **Person ↔ Location**: Co-occurring in the same sentence (`located_at`).
   - **Person ↔ Vehicle**: Co-occurring in the same sentence (`used_vehicle`).
3. **Legal Role Guardrails**: Excludes judicial officers, defense counsels, and public prosecutors from accused/conspiracy edge rules via regex and contextual appearance-roster filtering.
4. **Deduplication & Weight Aggregation**: Groups edges by `(source_entity_id, target_entity_id, edge_type)` with deterministic undirected ID generation. Multiple supporting sentences aggregate edge weights and merge source provenance snippets.
5. **Cross-Case Linkage**: When a canonical entity is referenced across multiple judgments or cases, edges preserve cross-case references across all participating `case_ids`.
6. **In-Memory NetworkX Loading**: Downstream graph analytics interact with graphs loaded via `load_case_graph(case_id)`.

---

## Edge Extraction Rules

| Relationship Type | Entity Types | Extraction Condition | Base Weight | Increment |
|---|---|---|---|---|
| **`co_accused`** | `PERSON` ↔ `PERSON` | Both individuals explicitly identified as accused in the same judgment and non-legal roles | `1.0` | `+0.2` |
| **`used_vehicle`** | `PERSON` ↔ `VEHICLE` | Person and vehicle/registration co-occurring in the same sentence | `0.8` | `+0.2` |
| **`associated_with`** | `PERSON` ↔ `PERSON` | Individuals co-occurring within the same sentence boundary | `0.5` | `+0.1` |
| **`associated_with`** | `PERSON` ↔ `ORGANIZATION` | Person and organization co-occurring within the same sentence boundary | `0.5` | `+0.1` |
| **`located_at`** | `PERSON` ↔ `LOCATION` | Person and geographical location co-occurring within the same sentence boundary | `0.5` | `+0.1` |

### Word-Boundary Matching & Legal Role Guardrail

- Entity matching in sentence contexts uses compiled regular expressions with strict word boundaries `\b` (`re.escape(pattern)`), preventing substring false positives (e.g., short tokens inside common English words).
- `is_valid_accused_person` filters out court titles (`Public Prosecutor`, `Advocate`, `Senior Counsel`, `Sessions Judge`, `High Court`, `Crl.A`, etc.) and appearance-block boilerplate so that lawyers representing accused persons are never conflated as co-conspirators.

---

## Edge Storage Schema

Edges are stored in the MongoDB `edges` collection:

```json
{
  "_id": "ObjectId(...)",
  "id": "edge_7eadd8d02e9a01df",
  "edge_id": "edge_7eadd8d02e9a01df",
  "source_entity_id": "ent_case_141720225_0152c6f19ed219ee",
  "target_entity_id": "ent_case_141720225_69c1daba0f0bc897",
  "edge_type": "co_accused",
  "relationship_type": "co_accused",
  "weight": 1.0,
  "case_id": "case_141720225",
  "case_ids": ["case_141720225"],
  "document_ids": ["doc_141720225"],
  "evidence": "Co-accused in case case_141720225: Atiq Ahmad and Guddu Muslim",
  "confidence": 0.95,
  "provenance": {
    "tier": "primary",
    "source_ref": "doc_141720225",
    "method": "accused_pattern",
    "confidence": 0.95,
    "extracted_at": "2026-09-22T20:04:33.123000Z",
    "metadata": {
      "evidence_count": 1,
      "evidence_snippets": [
        "Co-accused in case case_141720225: Atiq Ahmad and Guddu Muslim"
      ],
      "edge_type": "co_accused"
    }
  },
  "verification_status": "unverified",
  "created_at": "2026-09-22T20:04:33.123000Z",
  "updated_at": "2026-09-22T20:04:33.123000Z",
  "attributes": {
    "evidence_count": 1,
    "weight": 1.0
  }
}
```

---

## Deduplication and Weighting Strategy

1. **Deterministic Edge ID**:
   $$\text{edge\_id} = \text{"edge\_"} + \text{SHA256}(\min(s, t) + ":" + \max(s, t) + ":" + \text{edge\_type})[:16]$$
   Guarantees that undirected entity pairs always yield identical edge identifiers regardless of traversal order.

2. **Weight Aggregation Formula**:
   $$\text{weight} = \min\left(5.0, \text{base\_weight} + \text{increment\_weight} \times (N - 1)\right)$$
   Where $N$ is the number of distinct evidentiary occurrences across sentences or documents. Repeated mentions reinforce connection strength deterministically up to a maximum cap of `5.0`.

---

## Canonical Alias Handling & Cross-Case Linking

1. **Canonical Entity Normalization**: When entities have been resolved in `entity_merges` (Task 4.1), their raw entity IDs are resolved to canonical IDs before edge evaluation.
2. **Multi-Case Bridging**: If an individual appears in multiple judgments (e.g., Atiq Ahmad appearing in multiple criminal cases across jurisdictions), the canonical entity bridges multiple cases. Edges store all contributing cases in `case_ids` and documents in `document_ids`.
3. **`find_cross_case_canonical_entities(db)`**: Traverses entity collections and merge mappings to identify all network targets spanning $\ge 2$ cases.

---

## NetworkX Integration

`load_case_graph(case_id: str, database=None) -> nx.Graph` converts stored MongoDB edges and nodes into an in-memory `networkx.Graph` for downstream graph analytics:
- **Nodes**: Loaded with entity attributes (`name`, `entity_type`, `verification_status`, `aliases`, `case_id`).
- **Edges**: Loaded with relationship attributes (`edge_id`, `edge_type`, `weight`, `verification_status`, `provenance`).
- Multi-edges between node pairs aggregate edge weights so standard NetworkX centrality and pathfinding algorithms operate correctly.

---

## API Endpoints

### 1. Build Case Graph
```http
POST /api/cases/{case_id}/build-graph
```
**Response (200 OK)**:
```json
{
  "case_id": "case_141720225",
  "nodes": 141,
  "edges_created": 307,
  "edges_updated": 0
}
```

### 2. Retrieve Case Graph
```http
GET /api/cases/{case_id}/graph
```
**Response (200 OK)**:
```json
{
  "nodes": [
    {
      "id": "ent_case_141720225_0152c6f19ed219ee",
      "name": "Atiq Ahmad",
      "entity_type": "PERSON",
      "verification_status": "unverified",
      "aliases": ["Atiq Ahmad's"]
    }
  ],
  "edges": [
    {
      "edge_id": "edge_7eadd8d02e9a01df",
      "source_entity_id": "ent_case_141720225_0152c6f19ed219ee",
      "target_entity_id": "ent_case_141720225_69c1daba0f0bc897",
      "edge_type": "co_accused",
      "weight": 1.0,
      "case_ids": ["case_141720225"],
      "document_ids": ["doc_141720225"],
      "provenance": { ... }
    }
  ]
}
```

---

## Real-Corpus Verification (10 Edges)

Evaluated against Allahabad High Court judgment **`case_141720225`** (Criminal Appeal No. 9417 of 2023):

| # | Edge ID | Source Entity | Target Entity | Edge Type | Weight | Evidence / Verification against Source Judgment | Result |
|---|---|---|---|---|---|---|---|
| **1** | `edge_7eadd8d02e9a01df` | Atiq Ahmad (`PERSON`) | Guddu Muslim (`PERSON`) | `co_accused` | 1.0 | Identified as co-accused in Umesh Pal murder / gang network | **VERIFIED** |
| **2** | `edge_aee9b43ba3a3ef55` | Atiq Ahmad (`PERSON`) | Kaish (`PERSON`) | `co_accused` | 1.0 | Kaish named alongside gang leader Atiq Ahmad | **VERIFIED** |
| **3** | `edge_ab511ca44e0ef9af` | Atiq Ahmad (`PERSON`) | Rakesh (`PERSON`) | `co_accused` | 1.0 | Co-accused Rakesh @ Nakesh @ Lala in conspiracy charge | **VERIFIED** |
| **4** | `edge_2186f674375d6f5e` | Atiq Ahmad (`PERSON`) | Shahrukh (`PERSON`) | `co_accused` | 1.0 | Co-accused operative Shahrukh in murder conspiracy | **VERIFIED** |
| **5** | `edge_b43e93695c1be9a7` | Atiq Ahmad (`PERSON`) | Vijay Mishra (`PERSON`) | `co_accused` | 1.0 | Co-accused advocate/associate Vijay Mishra charged in same case | **VERIFIED** |
| **6** | `edge_9816536825d4e365` | Guddu Muslim (`PERSON`) | Kaish (`PERSON`) | `co_accused` | 1.0 | Operatives Guddu Muslim and Kaish named together in charges | **VERIFIED** |
| **7** | `edge_c9aa65e4ff8fa24e` | Guddu Muslim (`PERSON`) | Rakesh (`PERSON`) | `co_accused` | 1.0 | Both accused of bomb-throwing and arms handling in narrative | **VERIFIED** |
| **8** | `edge_6e38c23e708a71ad` | Guddu Muslim (`PERSON`) | Shahrukh (`PERSON`) | `co_accused` | 1.0 | Gang associates named in Section 161 CrPC witness statements | **VERIFIED** |
| **9** | `edge_1396b35b398da53a` | Vijay Mishra (`PERSON`) | Guddu Muslim (`PERSON`) | `co_accused` | 1.0 | Co-conspirators in hotel meeting planning homicide | **VERIFIED** |
| **10** | `edge_75696a97c87a5a72` | Kaish (`PERSON`) | Rakesh (`PERSON`) | `co_accused` | 1.0 | Co-accused statements corroborating recovery of weapons | **VERIFIED** |

---

## Known Limitations

1. **NER Entity Misclassifications**: spaCy occasionally tags an accused name as `GPE`/`LOCATION` or procedural text as `PERSON` in Indian English court transcripts.
2. **Appearance Roster Density**: In judgments with large counsel appearance rosters, legal role filtering must catch all informal variants of counsel representation.
3. **Implicit Relations**: Pronoun-based references (e.g. "he then accompanied the accused") require coreference resolution before full sentence-level co-occurrence can capture all implicit interactions.
