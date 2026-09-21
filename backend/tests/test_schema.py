"""Tests for Task 2.1 — Provenance-Aware Schema, Verification Status, and Audit Log."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.db import COLLECTIONS, ensure_indexes
from app.models import (
    AuditLogEntry,
    Case,
    Document,
    Edge,
    Entity,
    Flag,
    Provenance,
    ProvenanceMethod,
    ProvenanceTier,
    ValidationRun,
    VerificationStatus,
)


@pytest.fixture
def sample_provenance() -> Provenance:
    return Provenance(
        tier=ProvenanceTier.PRIMARY.value,
        source_ref="doc_100478559",
        method=ProvenanceMethod.DIRECT_TEXT.value,
        confidence=0.95,
        metadata={"court": "Madras High Court"},
    )


# 1. Provenance model accepts valid data
def test_provenance_accepts_valid_data(sample_provenance: Provenance):
    assert sample_provenance.tier == "primary"
    assert sample_provenance.source_ref == "doc_100478559"
    assert sample_provenance.method == "direct_text"
    assert sample_provenance.confidence == 0.95
    assert isinstance(sample_provenance.extracted_at, datetime)


# 2. Provenance rejects confidence < 0
def test_provenance_rejects_confidence_less_than_zero():
    with pytest.raises(ValidationError):
        Provenance(
            tier="primary",
            source_ref="doc_test",
            method="direct_text",
            confidence=-0.01,
        )


# 3. Provenance rejects confidence > 1
def test_provenance_rejects_confidence_greater_than_one():
    with pytest.raises(ValidationError):
        Provenance(
            tier="primary",
            source_ref="doc_test",
            method="direct_text",
            confidence=1.001,
        )


# 4. Document can be instantiated
def test_document_can_be_instantiated(sample_provenance: Provenance):
    doc = Document(
        id="doc_test_001",
        case_id="case_001",
        title="State vs Accused on 13 August, 2019",
        text="Sample cleaned text of the judgment...",
        source_ref="https://indiankanoon.org/doc/100478559/",
        provenance=sample_provenance,
        verification_status=VerificationStatus.UNVERIFIED,
        court="Madras High Court",
        date="2019-08-13",
    )
    assert doc.id == "doc_test_001"
    assert doc.case_id == "case_001"
    assert doc.verification_status == "unverified"
    assert isinstance(doc.created_at, datetime)
    assert isinstance(doc.updated_at, datetime)


# 5. Entity can be instantiated
def test_entity_can_be_instantiated(sample_provenance: Provenance):
    entity = Entity(
        id="ent_001",
        case_id="case_001",
        name="Balakarupasamy",
        entity_type="person",
        aliases=["A-1", "Bala"],
        provenance=sample_provenance,
        verification_status=VerificationStatus.CONFIRMED,
    )
    assert entity.id == "ent_001"
    assert entity.name == "Balakarupasamy"
    assert entity.entity_type == "person"
    assert entity.aliases == ["A-1", "Bala"]
    assert entity.verification_status == "confirmed"


# 6. Edge can be instantiated
def test_edge_can_be_instantiated(sample_provenance: Provenance):
    edge = Edge(
        id="edge_001",
        case_id="case_001",
        source_entity_id="ent_001",
        target_entity_id="ent_002",
        relationship_type="communicated_with",
        provenance=sample_provenance,
        verification_status=VerificationStatus.UNVERIFIED,
        confidence=0.88,
        evidence="CDR logs show 14 calls exchanged between accused.",
    )
    assert edge.id == "edge_001"
    assert edge.source_entity_id == "ent_001"
    assert edge.target_entity_id == "ent_002"
    assert edge.relationship_type == "communicated_with"
    assert edge.confidence == 0.88
    assert edge.evidence is not None


# 7. Flag can be instantiated
def test_flag_can_be_instantiated(sample_provenance: Provenance):
    flag = Flag(
        id="flag_001",
        case_id="case_001",
        flag_type="high_frequency_cdr",
        description="Abnormal burst of communications right before incident.",
        severity="high",
        provenance=sample_provenance,
        verification_status=VerificationStatus.CONFIRMED,
    )
    assert flag.id == "flag_001"
    assert flag.severity == "high"
    assert flag.flag_type == "high_frequency_cdr"
    assert flag.verification_status == "confirmed"


# 8. ValidationRun can be instantiated
def test_validation_run_can_be_instantiated(sample_provenance: Provenance):
    val_run = ValidationRun(
        id="val_001",
        case_id="case_001",
        dataset_ref="noordin_top_edges.csv",
        validation_type="ground_truth_benchmark",
        status="completed",
        provenance=sample_provenance,
        verification_status=VerificationStatus.CONFIRMED,
        result_summary={"precision": 0.91, "recall": 0.87, "f1": 0.89},
    )
    assert val_run.id == "val_001"
    assert val_run.dataset_ref == "noordin_top_edges.csv"
    assert val_run.status == "completed"
    assert isinstance(val_run.result_summary, dict)
    assert val_run.result_summary["f1"] == 0.89


# 9. AuditLogEntry can be instantiated
def test_audit_log_entry_can_be_instantiated(sample_provenance: Provenance):
    audit = AuditLogEntry(
        id="audit_001",
        case_id="case_001",
        actor="analyst_investigator_1",
        action="confirm_entity_identity",
        timestamp=datetime.now(UTC),
        input_summary={"entity_id": "ent_001", "action": "confirm"},
        result_summary="Status changed from unverified to confirmed",
        entity_type="person",
        entity_id="ent_001",
        provenance=sample_provenance,
        verification_status=VerificationStatus.CONFIRMED,
    )
    assert audit.id == "audit_001"
    assert audit.actor == "analyst_investigator_1"
    assert audit.action == "confirm_entity_identity"
    assert audit.verification_status == "confirmed"
    assert audit.provenance is not None


# 10. Every required model accepts unverified, confirmed, rejected
def test_models_accept_all_verification_statuses(sample_provenance: Provenance):
    statuses: list[Any] = [
        VerificationStatus.UNVERIFIED,
        VerificationStatus.CONFIRMED,
        VerificationStatus.REJECTED,
        "unverified",
        "confirmed",
        "rejected",
    ]

    for st in statuses:
        doc = Document(
            case_id="c1",
            title="t",
            text="txt",
            source_ref="s",
            provenance=sample_provenance,
            verification_status=st,
        )
        assert doc.verification_status in ("unverified", "confirmed", "rejected")

        ent = Entity(
            case_id="c1",
            name="n",
            entity_type="person",
            provenance=sample_provenance,
            verification_status=st,
        )
        assert ent.verification_status in ("unverified", "confirmed", "rejected")

        edge = Edge(
            case_id="c1",
            source_entity_id="e1",
            target_entity_id="e2",
            relationship_type="co_accused",
            provenance=sample_provenance,
            verification_status=st,
        )
        assert edge.verification_status in ("unverified", "confirmed", "rejected")

        flag = Flag(
            case_id="c1",
            flag_type="ft",
            description="desc",
            severity="low",
            provenance=sample_provenance,
            verification_status=st,
        )
        assert flag.verification_status in ("unverified", "confirmed", "rejected")

        val = ValidationRun(
            dataset_ref="ds",
            validation_type="benchmark",
            status="pending",
            provenance=sample_provenance,
            verification_status=st,
        )
        assert val.verification_status in ("unverified", "confirmed", "rejected")

        case = Case(
            case_id="c1",
            title="Case One",
            provenance=sample_provenance,
            verification_status=st,
        )
        assert case.verification_status in ("unverified", "confirmed", "rejected")

    # Reject invalid verification statuses
    with pytest.raises(ValidationError):
        Document(
            case_id="c1",
            title="t",
            text="txt",
            source_ref="s",
            provenance=sample_provenance,
            verification_status="invalid_status_xyz",  # type: ignore[arg-type]
        )


# 11. IDs remain strings
def test_ids_remain_strings(sample_provenance: Provenance):
    doc = Document(
        case_id="c1",
        title="t",
        text="txt",
        source_ref="s",
        provenance=sample_provenance,
    )
    assert isinstance(doc.id, str)
    assert len(doc.id) > 0

    # Coerces MongoDB _id string or representation to string id
    ent = Entity.model_validate(
        {
            "_id": "mongo_str_id_123",
            "case_id": "c1",
            "name": "Entity A",
            "entity_type": "organization",
            "provenance": sample_provenance.model_dump(),
        }
    )
    assert isinstance(ent.id, str)
    assert ent.id == "mongo_str_id_123"


# 12. Models serialize successfully to JSON
def test_models_serialize_successfully_to_json(sample_provenance: Provenance):
    doc = Document(
        id="doc_1",
        case_id="c1",
        title="Test Doc",
        text="Some text",
        source_ref="ref1",
        provenance=sample_provenance,
        verification_status=VerificationStatus.CONFIRMED,
    )
    doc_json = doc.model_dump_json()
    data = json.loads(doc_json)
    assert data["id"] == "doc_1"
    assert data["verification_status"] == "confirmed"
    assert data["provenance"]["confidence"] == 0.95

    audit = AuditLogEntry(
        id="audit_1",
        case_id="c1",
        actor="system",
        action="ingest_doc",
        input_summary="Document doc_1 ingested",
        result_summary="Success",
        verification_status=VerificationStatus.UNVERIFIED,
    )
    audit_json = audit.model_dump_json()
    audit_data = json.loads(audit_json)
    assert audit_data["id"] == "audit_1"
    assert audit_data["verification_status"] == "unverified"


# 13. MongoDB collection/index initialization does not destroy existing data
def test_mongodb_collections_and_safe_index_init():
    expected_collections = {
        "CASES": "cases",
        "DOCUMENTS": "documents",
        "ENTITIES": "entities",
        "EDGES": "edges",
        "FLAGS": "flags",
        "VALIDATION_RUNS": "validation_runs",
        "AUDIT_LOG": "audit_log",
    }
    assert COLLECTIONS == expected_collections

    # Mock database object to verify ensure_indexes executes without destroying data
    class MockCollection:
        def __init__(self, name: str):
            self.name = name
            self.indexes: list[str] = []

        def create_index(self, key, background=True):
            idx_name = f"{key}_1" if isinstance(key, str) else "compound_1"
            self.indexes.append(idx_name)
            return idx_name

    class MockDB:
        def __init__(self):
            self.name = "mock_nexus_db"
            self.cases = MockCollection("cases")
            self.documents = MockCollection("documents")
            self.entities = MockCollection("entities")
            self.edges = MockCollection("edges")
            self.flags = MockCollection("flags")
            self.validation_runs = MockCollection("validation_runs")
            self.audit_log = MockCollection("audit_log")

    mock_db = MockDB()
    manifest = ensure_indexes(mock_db)

    assert "cases" in manifest
    assert "documents" in manifest
    assert "entities" in manifest
    assert "edges" in manifest
    assert "flags" in manifest
    assert "validation_runs" in manifest
    assert "audit_log" in manifest
    assert manifest["audit_log"] == ["case_id_1", "timestamp_1"]
