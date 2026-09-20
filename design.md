# DESIGN.md — UI/UX and System Design Decisions

> This file captures immutable design decisions. Do not modify without
> explicit developer instruction. It is the single source of truth for
> visual and architectural intent.

---

## 1. Design Language

| Token | Value |
|---|---|
| Primary color | `#0F172A` (slate-900) — command-center dark |
| Accent | `#3B82F6` (blue-500) — interactive elements |
| Danger / flag | `#EF4444` (red-500) — flagged patterns, high-risk |
| Success / confirmed | `#22C55E` (green-500) — validated entities |
| Warning / pending | `#F59E0B` (amber-500) — needs review |
| Graph node: accused | `#EF4444` |
| Graph node: organization | `#8B5CF6` (violet-500) |
| Graph node: location | `#06B6D4` (cyan-500) |
| Graph node: lawyer | `#F59E0B` |
| Graph node: judge | `#6B7280` (gray-500) |
| Graph edge: co-accused | `#EF4444` dashed |
| Graph edge: represented-by | `#F59E0B` solid |
| Graph edge: testified-against | `#3B82F6` solid |
| Font | Inter (system fallback: sans-serif) |
| Border radius | 8px standard, 4px for chips/badges |
| Panel background | `#1E293B` (slate-800) |

---

## 2. Page Map

### 2.1 Command Center Dashboard (`/dashboard`)
- Full-width dark canvas
- Top bar: corpus selector, global search (`GraphSearch`), notification bell
- Left sidebar: `KeyIndividualsPanel`, `FlaggedPatternsPanel`
- Center: `GraphCanvas` (force-directed, zoomable, pannable)
- Right sidebar: `EntityPanel` (selected node details), `ProvenanceLegend`
- Bottom drawer: `ReasoningTrailPanel`, `AuditTrailPanel`
- Floating: `ConfidenceIndicator` overlay on hovered node
- Top-right: `ReportDownloadButton`, `ValidationBadge`

### 2.2 Corpus List (`/corpus`)
- Table view of all fetched corpora
- Columns: name, document count, date fetched, status, action buttons
- Action: "Open Graph" to navigates to `/dashboard?corpus=<id>`

### 2.3 Entity List for Corpus (`/corpus/[id]/entities`)
- Filterable, sortable table of all entities
- Columns: name, type, aliases, confidence, source doc, validation status
- Inline `ConfirmRejectControl` for human-in-the-loop validation
- Export button (CSV)

### 2.4 Case Detail (`/cases/[id]`)
- Document metadata, full extracted text preview
- Entity list specific to this case
- Link to `/cases/[id]/graph`

### 2.5 Case Graph (`/cases/[id]/graph`)
- Same `GraphCanvas` but scoped to single case
- `ProvenanceLegend` + `ReasoningTrailPanel` always visible

---

## 3. Graph Canvas Spec

- Library: **Cytoscape.js** (client-side, no server needed, free)
- Layout: `cose-bilkent` (force-directed, handles large graphs)
- Min nodes to trigger clustering: 200
- Node size: proportional to PageRank centrality (min 20px, max 60px)
- Edge thickness: proportional to edge weight (co-occurrence count)
- Hover: show confidence tooltip + provenance snippet
- Click: open `EntityPanel` with full provenance + audit trail
- Double-click: expand node (load neighbors from API)
- Right-click: context menu (confirm, reject, flag, export subgraph)
- Search: `GraphSearch` highlights matching nodes, dims others

---

## 4. Provenance Model (Canonical)

Every entity and edge in the database must include:

```typescript
interface Provenance {
  source_doc_id: string;       // MongoDB ObjectId of source document
  source_text: string;         // Exact quoted text that produced this entity
  page: number | null;         // Page number if available
  confidence: number;          // 0.0-1.0
  method: "regex" | "spacy" | "llm" | "manual";
  extracted_at: string;        // ISO 8601 timestamp
  validated_by: string | null; // Analyst ID if manually confirmed
  validated_at: string | null;
}
```

---

## 5. API Contract (FastAPI to Next.js)

Base URL: `NEXT_PUBLIC_API_BASE_URL` (env var)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/corpus` | List all corpora |
| POST | `/corpus` | Create corpus (trigger fetch) |
| GET | `/corpus/{id}/entities` | List entities with provenance |
| GET | `/corpus/{id}/graph` | Graph nodes + edges JSON |
| GET | `/cases/{id}` | Case detail |
| GET | `/cases/{id}/graph` | Case-scoped graph |
| POST | `/validate/confirm` | Confirm entity/edge |
| POST | `/validate/reject` | Reject entity/edge |
| GET | `/documents/{id}` | Raw document + metadata |
| POST | `/report/generate` | Trigger PDF report |
| GET | `/report/{id}` | Download generated report |

All responses: `application/json`. Errors: `{ "detail": "..." }` (FastAPI default).

---

## 6. Entity Types (Canonical)

```python
ENTITY_TYPES = [
    "ACCUSED",        # Primary defendants
    "VICTIM",
    "WITNESS",
    "LAWYER",
    "JUDGE",
    "ORGANIZATION",   # Criminal gangs, companies, government bodies
    "LOCATION",       # Cities, states, specific addresses
    "DATE",
    "CASE_NUMBER",
    "STATUTE",        # IPC sections, special acts
]
```

---

## 7. Edge Types (Canonical)

```python
EDGE_TYPES = [
    "CO_ACCUSED",           # Both accused in same case
    "REPRESENTED_BY",       # Accused -> Lawyer
    "TESTIFIED_AGAINST",    # Witness -> Accused
    "LINKED_TO",            # Generic association (LLM-inferred)
    "LOCATED_AT",           # Entity -> Location
    "MEMBER_OF",            # Person -> Organization
    "PRESIDED_BY",          # Case -> Judge
]
```

---

## 8. Validation Strategy

- **Noordin Top network** (public terrorism research dataset) used as
  ground truth for graph structure validation
- Precision/Recall/F1 computed against Noordin edge list
- Target: Precision >= 0.75, Recall >= 0.60
- Validation results stored in `validation_runs` collection
- `ValidationBadge` component shows live score on dashboard

---

## 9. Performance Constraints (Free-Tier Reality)

| Constraint | Limit |
|---|---|
| MongoDB Atlas | 512 MB storage |
| Gemini API | 1500 requests/day (free tier) |
| Groq API | 14,400 requests/day (free tier) |
| Indian Kanoon | Rate-limited — add 1s delay between requests |
| Nominatim | 1 request/second (usage policy) |
| Vercel (frontend) | 100 GB bandwidth/month |

LLM calls must be batched and cached. Never call LLM twice for the same
document chunk.

---

## 10. Immutable Decisions (Do Not Override)

1. Cytoscape.js for graph rendering (not D3, not vis.js)
2. Motor (async) for all MongoDB operations (not PyMongo sync)
3. Pydantic v2 for all request/response models
4. Tailwind CSS only — no external UI component library
5. App Router only — no Next.js Pages Router
6. All LLM prompts stored as constants in `backend/app/services/extraction/llm_fallback.py`
7. Audit trail is append-only — no updates or deletes
8. `confidence` field is always a float 0.0-1.0, never a string or percentage
