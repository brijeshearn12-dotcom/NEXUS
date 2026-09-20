# HOLY BUILD BOOK — SIH26189GREEN

> Updated at the start of each day before writing any code.
> Each section records the day's plan, what was built, and what was skipped.

---

## Day 0 — Foundation Scaffold
**Status:** Complete
- [x] Directory structure created
- [x] Next.js 14 initialized with TypeScript, Tailwind, App Router
- [x] FastAPI project initialized with requirements.txt
- [x] GET /health endpoint working
- [x] .env.example files created (both frontend and backend)
- [x] .gitignore configured
- [x] Backend tooling configured (black, ruff, mypy, pytest)
- [x] Frontend tooling configured (ESLint, Prettier, TypeScript strict)
- [x] brain.md, memory.md, design.md placed at repository root
- [x] Git initialized, first commit made

---

## Day 1 — MongoDB Connection and Corpus Fetch
**Status:** Not started
**Plan:**
- [ ] Create MongoDB Atlas free cluster manually
- [ ] Set MONGODB_URI in .env
- [ ] Wire up motor async client in /backend/app/core/db.py
- [ ] Implement fetch_corpus.py (Indian Kanoon API)
- [ ] Store raw responses in /data/raw/ (gitignored)
- [ ] Store document metadata in MongoDB `documents` collection
- [ ] Write pytest for fetch -> store pipeline
- [ ] Commit: `feat(corpus): fetch and store Indian Kanoon judgments`

---

## Day 2 — Regex + spaCy Extraction Pipeline
**Status:** Not started
**Plan:**
- [ ] Implement regex_extractors.py (IPC sections, case numbers, dates)
- [ ] Implement spacy_extractor.py (NER: PERSON, ORG, GPE, DATE)
- [ ] Implement date_extractor.py
- [ ] Implement provenance model (full schema)
- [ ] POST /documents/{id}/extract endpoint
- [ ] Write pytests for each extractor
- [ ] Commit: `feat(extraction): regex + spacy pipeline with provenance`

---

## Day 3 — LLM Fallback and Legal Role Classification
**Status:** Not started
**Plan:**
- [ ] Implement llm_fallback.py (Gemini 2.0 Flash, Groq fallback)
- [ ] Implement legal_role_filter.py (accused, victim, witness, lawyer, judge)
- [ ] Implement accused_extractor.py
- [ ] Cache LLM results per document chunk
- [ ] Write pytests
- [ ] Commit: `feat(extraction): LLM fallback + legal role classifier`

---

## Day 4 — Graph Construction
**Status:** Not started
**Plan:**
- [ ] Implement edge_rules.py (CO_ACCUSED, REPRESENTED_BY, etc.)
- [ ] Implement networkx_loader.py (build graph from MongoDB entities)
- [ ] Implement cross_case_linker.py (alias resolution across cases)
- [ ] GET /corpus/{id}/graph endpoint
- [ ] Write pytests
- [ ] Commit: `feat(graph): NetworkX graph builder + edge rules`

---

## Day 5 — Analytics Layer
**Status:** Not started
**Plan:**
- [ ] Implement centrality.py (PageRank, betweenness, degree)
- [ ] Implement community.py (Louvain clustering)
- [ ] Implement pattern_flags.py (suspicious patterns)
- [ ] Implement key_individuals.py
- [ ] Implement case_priority.py
- [ ] Analytics endpoints
- [ ] Write pytests
- [ ] Commit: `feat(analytics): centrality + community + pattern flags`

---

## Day 6 — Validation Layer
**Status:** Not started
**Plan:**
- [ ] Implement noordin_loader.py (load Noordin Top edge list)
- [ ] Implement alias_resolver.py
- [ ] POST /validate/confirm and POST /validate/reject endpoints
- [ ] Frontend: ConfirmRejectControl component
- [ ] Frontend: ValidationBadge component
- [ ] Write pytests
- [ ] Commit: `feat(validation): Noordin loader + HITL validation endpoints`

---

## Day 7 — Synthetic Data Generators
**Status:** Not started
**Plan:**
- [ ] Implement cdr_generator.py (fake CDR data with Faker)
- [ ] Implement transaction_generator.py (fake financial transactions)
- [ ] CLI scripts to generate N records
- [ ] Write pytests
- [ ] Commit: `feat(synthetic): CDR + transaction data generators`

---

## Day 8 — Frontend Command Center
**Status:** Not started
**Plan:**
- [ ] Implement GraphCanvas.tsx (Cytoscape.js, cose-bilkent)
- [ ] Implement EntityPanel.tsx, ProvenanceLegend.tsx
- [ ] Implement KeyIndividualsPanel.tsx, FlaggedPatternsPanel.tsx
- [ ] Implement ReasoningTrailPanel.tsx, AuditTrailPanel.tsx
- [ ] Wire dashboard page to live API
- [ ] Commit: `feat(frontend): GraphCanvas + dashboard panels`

---

## Day 9 — Report Generation and Audit Trail
**Status:** Not started
**Plan:**
- [ ] Implement POST /report/generate (ReportLab PDF)
- [ ] Implement GET /report/{id} (download)
- [ ] Implement audit trail (append-only MongoDB collection)
- [ ] Frontend: ReportDownloadButton.tsx
- [ ] Frontend: AuditTrailPanel.tsx
- [ ] Commit: `feat(report): PDF generation + immutable audit trail`

---

## Day 10 — End-to-End Testing and Demo Prep
**Status:** Not started
**Plan:**
- [ ] Full E2E test run
- [ ] Demo script prepared
- [ ] README.md written
- [ ] Submission package prepared
- [ ] Final commit: `chore: submission ready — SIH26189GREEN`
