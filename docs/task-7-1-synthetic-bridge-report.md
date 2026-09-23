# NEXUS Task 7.1 — Synthetic CDR/Transaction Bridge & Report Export

## Overview
**NEXUS Task 7.1** establishes an honest, forensic-grade demonstration bridge connecting extracted entities via synthetic Call Detail Records (CDR) and financial transactions, paired with a professional ReportLab PDF investigation dossier export.

---

## 1. Core Principles & Forensic Guarantees

### Real Entities + Synthetic Events = Analytical Bridge
$$\text{REAL EXTRACTED ENTITIES} + \text{SYNTHETIC CDR/TRANSACTION EVENTS} = \text{DEMONSTRATION BRIDGE}$$

1. **Pre-Existing Entity Constraint**: Synthetic generators **NEVER** invent new identities, persons, organizations, or vehicles. They operate strictly on canonical entities already extracted into MongoDB for the case.
2. **Explicit Provenance**:
   - `tier`: `"synthetic"`
   - `method`: `"faker"`
   - `source_ref`: `"synthetic-demo"`
   - `confidence`: `0.70`
   - `metadata.synthetic`: `True`
   - `metadata.disclaimer`: *"SYNTHETIC DEMONSTRATION DATA: Not a real-world record."*
3. **Sparse Edge Density (Non-Domination)**: Default generation is conservative (default 5 CDR, 5 Transactions, weight 1.0) so synthetic relationships demonstrate multi-modal graph analysis without overwhelming primary evidence rankings.
4. **Instant Reversibility**: Analysts can wipe all synthetic demonstration edges with a single click or `DELETE /api/cases/{case_id}/synthetic`, instantly restoring the pure evidentiary baseline.
5. **Authoritative Audit Logging**: Both generation and clearing operations are recorded immutably in `db.audit_log`.

---

## 2. Architecture & Components

```
backend/
  app/
    services/
      synthetic/
        cdr_generator.py          # Generates CDR events (voice, sms, cell tower, IMEI)
        transaction_generator.py  # Generates transfers (RTGS, cash, hawala, UPI)
        synthetic_bridge.py       # Orchestrates generation, DB storage, audit logging, and cleanup
      report_generator.py         # ReportLab PDF dossier generation engine
    api/
      report.py                   # GET/POST /api/report/{case_id}
      cases.py                    # Endpoints for synthetic bridge and report export
  tests/
    test_synthetic_and_report.py  # Unit & integration tests

frontend/
  components/
    SyntheticBridgeControl.tsx    # Interactive bridge panel with statutory disclosure
    ReportDownloadButton.tsx      # Blob download button with fallback
    ProvenanceLegend.tsx          # Updated key with dashed line for synthetic records
    GraphCanvas.tsx               # Cytoscape dashed-line styling for synthetic edges
  lib/
    api.ts                        # Typed client methods for synthetic bridge & summaries
  app/cases/[id]/graph/page.tsx   # Integrated top bar export & right drawer "Bridge" tab
```

---

## 3. Backend Endpoints

### 1. Generate Synthetic Demonstration Edges
- **Route**: `POST /api/cases/{case_id}/synthetic/generate`
- **Request Payload**:
  ```json
  {
    "cdr_count": 5,
    "transaction_count": 5
  }
  ```
- **Response**:
  ```json
  {
    "status": "ok",
    "case_id": "case_100478559",
    "cdr_count": 5,
    "transaction_count": 5,
    "total_generated": 10,
    "message": "Successfully generated 10 synthetic relationships..."
  }
  ```

### 2. Clear Synthetic Edges (Restore Baseline)
- **Route**: `DELETE /api/cases/{case_id}/synthetic`
- **Response**:
  ```json
  {
    "status": "ok",
    "case_id": "case_100478559",
    "deleted_count": 10,
    "message": "Successfully removed 10 synthetic demonstration relationships."
  }
  ```

### 3. Get Synthetic Edge Summary
- **Route**: `GET /api/cases/{case_id}/synthetic/summary`
- **Response**:
  ```json
  {
    "case_id": "case_100478559",
    "total_edges": 198,
    "synthetic_edges": 0,
    "primary_edges": 198,
    "synthetic_cdr_count": 0,
    "synthetic_transaction_count": 0,
    "has_synthetic_data": false
  }
  ```

### 4. PDF Investigation Report Export
- **Routes**:
  - `GET /api/cases/{case_id}/report`
  - `POST /api/cases/{case_id}/report`
  - `GET /api/report/{case_id}`
- **Response Headers**:
  - `Content-Type: application/pdf`
  - `Content-Disposition: attachment; filename="NEXUS_Investigation_Dossier_{case_id}.pdf"`
- **Contents**:
  1. Cover / Document Header with "RESTRICTED // LAW ENFORCEMENT SENSITIVE" security banner.
  2. Case Executive Summary & KPI metrics.
  3. Key Individuals Centrality Rankings (PageRank + Betweenness) and Factual Reasoning Trail for the lead orchestrator.
  4. Structural Threat Flags & Subgraph Anomalies.
  5. Academic Methodology Validation (Noordin Top Ground Truth — 4 of 5 matched, 80% precision@5).
  6. Human-in-the-Loop Verification Audit summary.
  7. Authoritative Case Audit Trail Chronology.
  8. **Mandatory Provenance Appendix**: Explicit 3-tier matrix separating Primary Source Evidence, Derived Analytical Results, and Synthetic Demonstration Data.

---

## 4. Frontend User Experience

1. **Top Command Bar**: "Export Dossier (PDF)" button triggers immediate ReportLab generation and client-side browser download.
2. **Right Drawer "Bridge" Tab**:
   - Amber **Mandatory Provenance Notice**: Clearly explains synthetic nature and that no new entities were fabricated.
   - Live KPI Counters: Primary Edges vs Synthetic CDR vs Synthetic Txn.
   - Sliders/inputs to configure counts (1 to 20).
   - "Generate Bridge" & "Clear Synth" buttons.
3. **Graph Visuals**:
   - Synthetic CDR edges: dashed cyan line (`#06B6D4`).
   - Synthetic Transaction edges: dashed emerald line (`#10B981`).
   - Inferred / other synthetic edges: dashed slate line (`#94A3B8`).
   - Primary evidence edges: solid lines colored by legal relationship type.
