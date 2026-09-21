"""Corpus service managing curated dataset ingestion, manual ingestion, and retrieval."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo.collection import Collection

from app.core.db import get_db
from app.models.audit import AuditLogEntry
from app.models.case import Case
from app.models.document import Document
from app.models.enums import ProvenanceMethod, ProvenanceTier, VerificationStatus
from app.models.provenance import Provenance
from app.services.fact_segmenter import segment_facts
from app.services.text_cleaner import clean_judgment_text

logger = logging.getLogger(__name__)

# Locate data/curated relative to this file:
# backend/app/services/corpus_service.py -> backend/app/services -> backend/app -> backend -> NEXUS -> data/curated
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
CURATED_DIR = DATA_DIR / "curated"
CURATED_MANIFEST_PATH = CURATED_DIR / "curated_manifest.json"


def get_documents_collection() -> Collection[Any]:
    return get_db().documents


def get_cases_collection() -> Collection[Any]:
    return get_db().cases


def get_audit_collection() -> Collection[Any]:
    return get_db().audit_log


def load_curated_corpus(curated_path: Path | None = None) -> dict[str, Any]:
    """Ingest the 20 audited curated judgments into MongoDB with provenance and audit logs.

    Idempotent: updates existing records by stable document ID without creating duplicates.
    """
    target_dir = curated_path or CURATED_DIR
    manifest_file = target_dir / "curated_manifest.json"

    if not target_dir.exists():
        raise FileNotFoundError(f"Curated corpus directory does not exist: {target_dir}")

    db_docs = get_documents_collection()
    db_cases = get_cases_collection()
    db_audit = get_audit_collection()

    manifest_docs: list[dict[str, Any]] = []
    if manifest_file.exists():
        try:
            with open(manifest_file, encoding="utf-8") as f:
                manifest_data = json.load(f)
                manifest_docs = manifest_data.get("curated_documents", [])
        except Exception as err:
            logger.warning("Failed to parse curated_manifest.json: %s", err)

    # Fallback to file globbing if manifest is missing or empty
    if not manifest_docs:
        files = sorted(target_dir.glob("doc_*.json"))
        for json_path in files:
            manifest_docs.append({"file_name": json_path.name})

    total_count = len(manifest_docs)
    inserted_count = 0
    updated_count = 0
    failed_count = 0
    processed_items: list[dict[str, Any]] = []

    # Record start audit log
    audit_start = AuditLogEntry(
        case_id="corpus_batch",
        actor="system_corpus_loader",
        action="corpus_load_started",
        timestamp=datetime.now(UTC),
        input_summary={"total_candidate_files": total_count, "directory": str(target_dir.name)},
        result_summary=f"Initiated curated corpus ingestion for {total_count} documents",
    )
    db_audit.insert_one(audit_start.model_dump(by_alias=True))

    for doc_meta in manifest_docs:
        file_name = doc_meta.get("file_name", "")
        file_path = target_dir / file_name

        if not file_path.exists():
            failed_count += 1
            logger.error("Curated file missing: %s", file_name)
            continue

        try:
            with open(file_path, encoding="utf-8") as f:
                raw_json = json.load(f)

            tid = doc_meta.get("tid") or raw_json.get("tid")
            if not tid and file_name.startswith("doc_"):
                tid = file_name.replace("doc_", "").replace(".json", "")

            stable_doc_id = f"doc_{tid}"
            stable_case_id = f"case_{tid}"

            # Extract text from raw_api_response.doc or doc or text
            raw_response = raw_json.get("raw_api_response", {})
            if isinstance(raw_response, dict) and "doc" in raw_response:
                raw_text = raw_response["doc"]
            else:
                raw_text = raw_json.get("doc", raw_json.get("text", ""))

            title = doc_meta.get("title") or raw_json.get("title") or f"Judgment {tid}"
            court = doc_meta.get("court") or raw_json.get("docsource")
            date_val = doc_meta.get("date") or raw_json.get("publishdate")
            source_url = doc_meta.get("source_url") or raw_json.get("source_url")

            # Conservative Boilerplate Stripping
            cleaned_text, cleaning_meta = clean_judgment_text(raw_text)

            # Fact-Section Segmentation
            segmentation_meta = segment_facts(cleaned_text)
            extraction_text = segmentation_meta["text"]

            # Provenance construction
            provenance = Provenance(
                tier=ProvenanceTier.PRIMARY.value,
                source_ref=file_name,
                method=ProvenanceMethod.API.value,
                confidence=1.0,
                extracted_at=datetime.now(UTC),
                metadata={
                    "query_used": doc_meta.get("query_used") or raw_json.get("query_used"),
                    "score": doc_meta.get("score"),
                    "source_corpus": "curated",
                },
            )

            # Metadata enrichment from curated manifest
            doc_metadata = {
                "rank": doc_meta.get("rank"),
                "score": doc_meta.get("score"),
                "query_used": doc_meta.get("query_used"),
                "detected_relationship_categories": doc_meta.get(
                    "detected_relationship_categories", []
                ),
                "accused_identified": doc_meta.get("accused_identified", []),
                "reason_for_selection": doc_meta.get("reason_for_selection"),
            }

            document = Document(
                id=stable_doc_id,
                case_id=stable_case_id,
                title=title,
                text=cleaned_text,
                extraction_text=extraction_text,
                source_ref=file_name,
                court=court,
                date=str(date_val) if date_val else None,
                source_url=source_url,
                provenance=provenance,
                verification_status=VerificationStatus.UNVERIFIED,
                cleaning_metadata=cleaning_meta,
                segmentation_metadata=segmentation_meta,
                metadata=doc_metadata,
            )

            case_obj = Case(
                id=stable_case_id,
                case_id=stable_case_id,
                title=title,
                description=doc_meta.get("reason_for_selection"),
                provenance=provenance,
                verification_status=VerificationStatus.UNVERIFIED,
                metadata={
                    "court": court,
                    "date": str(date_val) if date_val else None,
                    "document_id": stable_doc_id,
                },
            )

            # Upsert document into MongoDB
            doc_dump = document.model_dump(by_alias=True)
            existing_doc = db_docs.find_one({"id": stable_doc_id})

            if existing_doc:
                db_docs.replace_one({"id": stable_doc_id}, doc_dump, upsert=True)
                updated_count += 1
                action_type = "document_updated"
            else:
                db_docs.insert_one(doc_dump)
                inserted_count += 1
                action_type = "document_ingested"

            # Upsert case container into MongoDB
            db_cases.replace_one(
                {"id": stable_case_id}, case_obj.model_dump(by_alias=True), upsert=True
            )

            # Create concise audit log entry
            audit_item = AuditLogEntry(
                case_id=stable_case_id,
                actor="system_corpus_loader",
                action=action_type,
                timestamp=datetime.now(UTC),
                input_summary={"document_id": stable_doc_id, "file_name": file_name},
                result_summary=(
                    f"Cleaned {cleaning_meta['original_length']} -> {cleaning_meta['cleaned_length']} chars "
                    f"({cleaning_meta['retention_ratio']:.1%} retained); section: {segmentation_meta['section_name']}"
                ),
                entity_type="document",
                entity_id=stable_doc_id,
                provenance=provenance,
                verification_status=VerificationStatus.UNVERIFIED,
            )
            db_audit.insert_one(audit_item.model_dump(by_alias=True))

            processed_items.append(
                {
                    "id": stable_doc_id,
                    "case_id": stable_case_id,
                    "title": title,
                    "retention_ratio": cleaning_meta["retention_ratio"],
                    "fact_section": segmentation_meta["section_name"],
                    "status": "ingested",
                }
            )

        except Exception as err:
            failed_count += 1
            logger.error("Failed ingesting document %s: %s", file_name, err, exc_info=True)
            db_audit.insert_one(
                AuditLogEntry(
                    case_id=f"doc_error_{file_name}",
                    actor="system_corpus_loader",
                    action="document_failed",
                    timestamp=datetime.now(UTC),
                    input_summary={"file_name": file_name},
                    result_summary=f"Ingestion failed: {err}",
                ).model_dump(by_alias=True)
            )

    return {
        "status": "ok",
        "total": total_count,
        "inserted": inserted_count,
        "updated": updated_count,
        "skipped": 0,
        "failed": failed_count,
        "documents": processed_items,
    }


def ingest_manual_text(
    case_id: str,
    text: str,
    title: str | None = None,
    source_ref: str | None = None,
) -> Document:
    """Ingest a manually pasted judgment text under a specific case_id."""
    if not text or not text.strip():
        raise ValueError("Text is required and must not be empty.")

    db_docs = get_documents_collection()
    db_cases = get_cases_collection()
    db_audit = get_audit_collection()

    doc_uuid = uuid.uuid4().hex[:12]
    doc_id = f"doc_manual_{doc_uuid}"
    doc_title = title.strip() if title and title.strip() else f"Manual Ingest {doc_uuid}"
    source_reference = source_ref.strip() if source_ref and source_ref.strip() else "manual_paste"

    # Clean & segment
    cleaned_text, cleaning_meta = clean_judgment_text(text)
    segmentation_meta = segment_facts(cleaned_text)
    extraction_text = segmentation_meta["text"]

    provenance = Provenance(
        tier=ProvenanceTier.SECONDARY.value,
        source_ref=source_reference,
        method=ProvenanceMethod.MANUAL.value,
        confidence=0.80,
        extracted_at=datetime.now(UTC),
        metadata={"ingest_type": "manual_paste"},
    )

    doc = Document(
        id=doc_id,
        case_id=case_id,
        title=doc_title,
        text=cleaned_text,
        extraction_text=extraction_text,
        source_ref=source_reference,
        provenance=provenance,
        verification_status=VerificationStatus.UNVERIFIED,
        cleaning_metadata=cleaning_meta,
        segmentation_metadata=segmentation_meta,
    )

    # Insert document
    db_docs.insert_one(doc.model_dump(by_alias=True))

    # Ensure case exists
    existing_case = db_cases.find_one({"id": case_id})
    if not existing_case:
        case_obj = Case(
            id=case_id,
            case_id=case_id,
            title=doc_title,
            provenance=provenance,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        db_cases.insert_one(case_obj.model_dump(by_alias=True))

    # Record audit log
    db_audit.insert_one(
        AuditLogEntry(
            case_id=case_id,
            actor="analyst_manual",
            action="manual_document_ingested",
            timestamp=datetime.now(UTC),
            input_summary={"case_id": case_id, "length": len(text), "title": doc_title},
            result_summary=f"Ingested manual document {doc_id} ({cleaning_meta['cleaned_length']} cleaned chars)",
            entity_type="document",
            entity_id=doc_id,
            provenance=provenance,
            verification_status=VerificationStatus.UNVERIFIED,
        ).model_dump(by_alias=True)
    )

    return doc
