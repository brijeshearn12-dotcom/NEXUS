# MEMORY.md — Live Session Log

> Updated after every session. Read this before starting any new session.
> Newest entries at the top.

---

## Session: Day 3 — Task 3.1: Rule-Based + spaCy + Gemini Fallback Entity Extraction
**Date:** 2026-09-21
**Status:** Complete

### Decisions Made
- Implemented multi-stage extraction pipeline: regex (phones, vehicle plates with state validation, FIRs, court case numbers) + spaCy (`en_core_web_sm`) + conservative legal-role filtering + dedicated accused-reference extraction (`A-1`..`A-n` and explicit name mapping).
- Implemented Gemini 2.0 Flash fallback trigger with strict guardrails: only invoked under Condition A (low deterministic yield <0.5 entities/1,000 chars) or Condition B (Devanagari text presence >=20 chars).
- Enforced strict verbatim evidence snippet validation against source text to prevent hallucinations.
- Retained offline resilience: pipeline completes with zero Gemini calls when key is disabled or deterministic yield is sufficient.
- Integrated `/api/extraction/run`, `/api/extraction/run-batch`, `/api/extraction/run-all`, `/api/entities/`, and `/api/entities/{id}` with MongoDB idempotent upserts and immutable audit logging.
- Verified on 5 real curated judgments: Micro-F1 84.14%, Micro-Recall 95.31%, Micro-Precision 75.31%, and 10/10 evidence snippets verified verbatim against source text.
- 59 pytest tests passing, mypy clean, ruff clean, and frontend production build passing.

### Blockers
- None.

### Next Priority (Day 3 / Task 3.2)
1. Task 3.2: Relationship & Edge Extraction pipeline (co-accused, representation, testimony, communication links).
2. Graph schema integration with NetworkX.

---

## Session: Day 0 — Foundation Scaffold
**Date:** 2026-09-20
**Status:** Complete

### Decisions Made
- Repository root: `C:\Users\brije\Documents\NEXUS`
- Next.js 14 in `/frontend`, FastAPI in `/backend`
- MongoDB Atlas free tier selected (512 MB limit — must stay lean)
- Gemini 2.0 Flash as primary LLM (free tier, 1M context)
- Groq Llama 3.3 70B as fallback LLM
- spaCy `en_core_web_sm` for offline NER (no API cost)
- Nominatim for geocoding (no API key required)
- `python-louvain` for community detection (Louvain algorithm)
- All environment variables in `.env.example` only — no real secrets committed
- `/data/raw` contents gitignored; `/data/curated` and `/data/validation` committed
- Provenance fields required on every entity/edge: `source_text`, `source_doc_id`, `page`, `confidence`, `method`

### Blockers
- None at Day 0

### Tomorrow's Top Priority (Day 1)
1. Manually create MongoDB Atlas free cluster and copy URI into `.env`
2. Wire up `motor` async client in `/backend/app/core/db.py`
3. Run `fetch_corpus.py` to pull first batch of Indian Kanoon judgments
4. Cache raw responses in `/data/raw/`
5. Store document metadata in MongoDB `documents` collection
6. Write pytest for the fetch -> store pipeline

---

## Template for Future Sessions

```
## Session: Day N — <Focus Area>
**Date:** YYYY-MM-DD
**Status:** In Progress / Complete / Blocked

### Decisions Made
-

### Blockers
-

### Tomorrow's Top Priority
1.
```
