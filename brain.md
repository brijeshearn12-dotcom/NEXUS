# BRAIN.md — Operating Rules for SIH26189GREEN

> Read this file at the start of every session. It is the authoritative
> source of truth for how the AI assistant must behave on this project.

---

## 1. Project Identity

| Field | Value |
|---|---|
| Problem Statement ID | SIH26189GREEN |
| Title | AI-Powered Criminal Network Analysis System |
| Ministry | Ministry of Home Affairs |
| Track | Software / Blockchain & Cybersecurity |
| Developer | Solo primary developer |
| Window | 10-day sprint |
| Infrastructure | Free-tier only |

---

## 2. Core Operating Rules

1. **Read before writing.** Before any session, re-read `brain.md`,
   `memory.md`, and `design.md` from the repository root.

2. **No hallucinated features.** Only build what is in the current Day's
   instructions. Do not speculate about future features.

3. **Free-tier discipline.** Every service, API, and dependency must have a
   free tier or be open-source. Call out any exception immediately.

4. **Provenance is non-negotiable.** Every extracted entity, edge, and flag
   must carry a `source_text`, `source_doc_id`, `page`, `confidence`, and
   `method` field. Never store an entity without provenance.

5. **Incremental commits.** Commit after every meaningful unit of work
   (endpoint, extractor, test). Message format: `type(scope): description`.

6. **Test coverage gating.** No extraction or analytics function ships
   without a pytest unit test covering the happy path and at least one
   edge case.

7. **memory.md is the live log.** After every session, update `memory.md`
   with decisions made, blockers hit, and next priority.


8. **design.md is immutable intent.** Do not change `design.md` without
   the developer's explicit instruction. It captures UI/UX and system
   design decisions.

9. **No real secrets ever.** Only `.env.example` files with placeholder
   values are committed. `.env` is gitignored unconditionally.

---

## 3. Stack Constraints

| Layer | Choice | Reason |
|---|---|---|
| Frontend | Next.js 14, App Router, TypeScript, Tailwind | Free, modern, type-safe |
| Backend | FastAPI, Python 3.11 | Fast async, easy AI integration |
| Database | MongoDB Atlas Free Tier | 512 MB free, flexible schema |
| Corpus | Indian Kanoon API | Free academic tier |
| LLM (primary) | Google Gemini 2.0 Flash (free tier) | 1M context, free |
| LLM (fallback) | Groq (Llama 3.3 70B) | Fast free tier |
| Graph | NetworkX + python-louvain | Open-source |
| NER | spaCy en_core_web_sm | Free, offline |
| Geocoding | Nominatim (OpenStreetMap) | Free, no key required |
| PDF export | ReportLab | Open-source |
| Validation | Noordin Top dataset | Public research dataset |

---

## 4. Architecture in One Paragraph

Judgments are fetched from Indian Kanoon, cached locally, then pushed
through a multi-layer extraction pipeline (regex → spaCy NER → LLM fallback)
that produces entities (accused, victims, witnesses, lawyers, judges,
organizations, locations) and edges (co-accused, represented-by,
testified-against, linked-to). Each entity/edge carries full provenance.
A NetworkX graph is built per corpus and per cross-case. Centrality,
community detection (Louvain), and pattern flags surface key individuals
and suspicious patterns. A human-in-the-loop validation layer lets the
analyst confirm or reject extracted entities before they are committed to
the knowledge graph. Every analyst action is recorded in an immutable
audit trail. The Command Center dashboard ties everything together. Synthetic
CDR and transaction data can be generated for demo purposes.

