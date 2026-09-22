# NEXUS Task 4.1 — Entity Alias Resolution

## Approach

The NEXUS alias resolution subsystem implements deterministic, conservative entity resolution designed specifically for criminal intelligence data extracted from Indian judicial records. The core design principles are:

1. **Intra-Case Scope**: Resolution evaluates entity pairs strictly within the same case (`case_id`).
2. **Type Compatibility**: Compares only compatible entity types (e.g. `PERSON` and `ACCUSED` within the person family; `ORGANIZATION`, `LOCATION`, `VEHICLE`, etc. strictly isolated).
3. **Blocking without All-Against-All**: Names are blocked by token prefixes to restrict pairwise comparison to plausible candidates, avoiding unrestricted $O(N^2)$ comparisons.
4. **Multi-Stage Conservative Scoring**: Combines exact normalized matching, initials-abbreviation matching, and RapidFuzz string similarity guarded by numeric consistency and given-name alignment checks.
5. **Additive, Reversible Storage**: Resolved alias pairs are stored as merge records in a separate `entity_merges` MongoDB collection. The original extracted entities in `entities` are never deleted or destructively altered.
6. **Idempotent Execution**: Merge decisions use deterministic stable merge IDs and unique compound indexes, ensuring identical results upon repeated runs.

## Normalization

Entity names undergo deterministic canonicalization prior to comparison:

```python
def normalize_alias_name(name: str) -> str:
    # 1. Strip possessive 's and ’s
    # 2. Lowercase
    # 3. Replace punctuation (.,-_/@ etc.) with whitespace
    # 4. Collapse repeated whitespace and strip
    # 5. Strip honorific prefixes (Mr., Ms., Mrs., Shri, Smt., Sri, Dr., Late, Md., Mohd.)
```

Examples:
- `"Atiq Ahmad's"` $\rightarrow$ `"atiq ahmad"`
- `"  Mr. Rajesh   Kumar  "` $\rightarrow$ `"rajesh kumar"`
- `"R.K. Sharma"` $\rightarrow$ `"r k sharma"`
- `"A-1 Rajesh Kumar"` $\rightarrow$ `"a 1 rajesh kumar"`

## Blocking

To prevent quadratic performance degradation and spurious comparisons across disjoint names, entities are blocked before comparison:

1. Entities are partitioned by compatible taxonomy families (`PERSON`, `ORGANIZATION`, `LOCATION`, `VEHICLE`, `PHONE`, `FIR`, `CASE_NUMBER`).
2. Tokens in normalized names are extracted, omitting legal stopwords (`v`, `vs`, `state`, `of`, `appeal`, etc.).
3. Blocking keys are generated:
   - For tokens $\ge 3$ characters: first 3 characters (e.g., `"atiq"` $\rightarrow$ `"ati"`, `"ahmad"` $\rightarrow$ `"ahm"`).
   - For tokens $< 3$ characters: full token (e.g., `"a"`, `"ed"`).
4. Candidate pairs are constructed exclusively between entities sharing at least one blocking key.

Across real corpus cases, this blocking strategy prunes $>90\%$ of candidate comparisons while preserving all true alias candidates.

## Threshold

A conservative similarity threshold of **`0.85`** ($85.0\%$) is enforced with three safety guardrails:

1. **RapidFuzz Similarity**: Uses $\max(\text{fuzz.ratio}, \text{fuzz.token\_sort\_ratio}) / 100.0$.
2. **Numeric Consistency Guardrail**: If either or both entity names contain digits/numbers, the extracted numbers must match identically. Any numerical mismatch (e.g. `FIR 123/2021` vs `FIR 456/2021`, or `1980` vs `2008`) immediately assigns a score of `0.0` (`numeric_mismatch`), preventing false merges of numbered legal records.
3. **Given-Name Guardrail**: For multi-word names where both first tokens have length $\ge 3$, their first tokens must achieve a similarity $\ge 70.0\%$. This prevents false merges between distinct individuals sharing common Indian surnames (e.g., `"Kaish Ahmad"` vs `"Atiq Ahmad"` or `"Rajesh Kumar"` vs `"Suresh Kumar"`).
4. **Single-Token Guardrail**: Single tokens under 4 characters require exact match, preventing spurious merges between short acronyms or single names.

## Merge Schema

Merge decisions are stored in the `entity_merges` collection in MongoDB:

```json
{
  "merge_id": "merge_case_141720225_7d10e527dbcf9e34",
  "canonical_entity_id": "ent_case_141720225_20d8400413d080dc",
  "alias_entity_id": "ent_case_141720225_ef039267f7380a76",
  "case_id": "case_141720225",
  "similarity_score": 0.9000,
  "confidence": 0.8100,
  "method": "rapidfuzz_token_sort",
  "verification_status": "unverified",
  "created_at": "2026-09-23T00:45:00.000Z",
  "source_refs": [
    "doc_141720225"
  ]
}
```

- **`merge_id`**: Deterministic SHA-256 hash of `case_id:canonical_id:alias_id`.
- **`canonical_entity_id`**: Deterministically selected based on name completeness/length, confidence score, occurrence count, and entity ID tie-breaker.
- **`alias_entity_id`**: ID of the resolved alias entity.
- **`case_id`**: Case context.
- **`similarity_score`**: Float between `0.0` and `1.0`.
- **`confidence`**: Float between `0.0` and `1.0`, computed as $\min(\text{conf}_1, \text{conf}_2) \times \text{similarity}$.
- **`method`**: Resolution method (`exact_match`, `initials_match`, `rapidfuzz_token_sort`, `rapidfuzz_ratio`).
- **`verification_status`**: Verification state (`unverified`, `confirmed`, `rejected`).
- **`created_at`**: UTC timestamp.
- **`source_refs`**: Unified provenance references from both entities.

Original entities in the `entities` collection remain completely intact.

## Real-Corpus Test Result

The resolver was verified against real Indian court judgments in the NEXUS corpus (`case_141720225` and `case_100478559`):

### Real-Corpus Statistics (`case_141720225`)
- `entities_checked`: 148
- `candidate_pairs`: 217
- `merges_created`: 8
- `merges_skipped`: 209

### Verified True Variants (Merged)
1. **`Atiq Ahmad`** $\leftrightarrow$ **`Atiq Ahmed`**
   - Result: **Merged**
   - Score: `0.9000` (Method: `rapidfuzz_token_sort`)
   - Canonical: `Atiq Ahmad`
2. **`Manish Goel`** $\leftrightarrow$ **`Manish Goyal`**
   - Result: **Merged**
   - Score: `0.8700` (Method: `rapidfuzz_token_sort`)
   - Canonical: `Manish Goyal`
3. **`Mr.N.Ananthapadmanabhan`** $\leftrightarrow$ **`N.Ananthapadmanabhan`** (in `case_100478559`)
   - Result: **Merged**
   - Score: `1.0000` (Method: `exact_match`)
   - Canonical: `Mr.N.Ananthapadmanabhan`

### Verified False Matches (Rejected / Not Merged)
1. **`Kaish Ahmad`** $\leftrightarrow$ **`Kaish Mohammad`**
   - Result: **Not Merged**
   - Score: `0.7200` (Below conservative threshold `0.85`, different family/surname)
2. **`Kaish Ahmad`** $\leftrightarrow$ **`Atiq Ahmad`**
   - Result: **Not Merged**
   - Score: `0.0000` (Rejected by given-name guardrail: `Kaish` vs `Atiq` ratio $< 70\%$)
3. **`Mr.KA.Ramakrishnan`** $\leftrightarrow$ **`Mr.A.Ramesh`** (in `case_100478559`)
   - Result: **Not Merged**
   - Score: `0.6900` (Below conservative threshold `0.85`)

## Known Limitations

1. **Intra-Case Only**: The resolver operates strictly within a single case scope. Cross-case entity linking across different FIRs or court jurisdictions is not performed.
2. **Phonetic / Transliteration Variations**: Non-Latin or Hindi transliteration nuances with significant phonetic drift (e.g. `Laxmi` vs `Lakshmi`) beyond Levenshtein distance require phonetic embedding or soundex models.
3. **Graph Topology Omission**: Resolution is purely deterministic and text-based; graph co-occurrence patterns and relationship edges are not yet utilized.
4. **Single-Token Aliases**: Nicknames without surnames (e.g., "Pappu") cannot be safely resolved to full names without contextual co-occurrence or explicit alias markers in text.
