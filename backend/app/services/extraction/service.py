"""Master extraction orchestration service for NEXUS Day 3.

Coordinates:
1. Document retrieval & text preparation (extraction_text from Day 2 segmentation)
2. Deterministic Regex extractors (Phone, Vehicle, FIR, Case Number)
3. spaCy NER (PERSON, ORG, GPE)
4. Contextual Legal-Role Filter (Judges, Counsels, Prosecutors)
5. Accused Extraction & Name Mapping
6. Normalization & Deduplication
7. Yield / Language Check -> Gemini Fallback ONLY if triggered
8. Provenance & Evidence Snippets
9. Idempotent MongoDB Entity upsert
10. Immutable Audit Trail Logging
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pymongo.collection import Collection

from app.core.db import get_collection
from app.models.audit import AuditLogEntry
from app.models.entity import Entity
from app.models.enums import ProvenanceTier, VerificationStatus
from app.models.provenance import Provenance
from app.services.extraction.accused_extractor import extract_accused_entities
from app.services.extraction.deduplication import deduplicate_entities
from app.services.extraction.legal_role_filter import filter_legal_roles
from app.services.extraction.llm_fallback import (
    extract_with_gemini_fallback,
    should_trigger_fallback,
)
from app.services.extraction.regex_extractors import extract_all_regex
from app.services.extraction.spacy_extractor import extract_spacy_entities

logger = logging.getLogger(__name__)


def get_entities_collection() -> Collection[Any]:
    return get_collection("entities")


def get_audit_collection() -> Collection[Any]:
    return get_collection("audit_log")


def get_documents_collection() -> Collection[Any]:
    return get_collection("documents")


def run_extraction_pipeline_on_text(
    text: str,
    case_id: str,
    document_id: str,
    enable_gemini_fallback: bool = True,
    gemini_api_key: str | None = None,
) -> dict[str, Any]:
    """Execute the multi-stage extraction pipeline on raw cleaned/segmented text.

    Returns:
        Structured result dictionary containing extracted Entity models, statistics by method,
        and audit metadata.
    """
    if not text or not text.strip():
        return {
            "document_id": document_id,
            "case_id": case_id,
            "entities_extracted": 0,
            "by_method": {
                "regex_phone": 0,
                "regex_vehicle": 0,
                "regex_fir": 0,
                "regex_case_number": 0,
                "spacy_ner": 0,
                "accused_pattern": 0,
                "gemini_fallback": 0,
            },
            "gemini_used": False,
            "gemini_reason": None,
            "filtered_legal_roles_count": 0,
            "entities": [],
        }

    # Step 1: Deterministic Regex Extractors (Phone, Vehicle, FIR, Case numbers)
    regex_candidates = extract_all_regex(text)

    # Step 2: spaCy NER (PERSON, ORG, GPE)
    spacy_candidates = extract_spacy_entities(text)

    # Step 3: Legal-Role Filter on spaCy PERSON candidates
    accepted_spacy, filtered_legal_roles = filter_legal_roles(spacy_candidates, text)

    # Step 4: Dedicated Accused-Reference Extractor
    accused_candidates = extract_accused_entities(text)

    # Combine deterministic candidates
    all_deterministic: list[dict[str, Any]] = []
    all_deterministic.extend(regex_candidates)
    all_deterministic.extend(accepted_spacy)
    all_deterministic.extend(accused_candidates)

    # Step 5: Normalization + Deduplication on deterministic candidates
    deduped_entities = deduplicate_entities(all_deterministic, case_id, document_id)

    # Step 6: Yield / Language Check for Gemini Fallback
    gemini_used = False
    gemini_trigger_reason: str | None = None
    gemini_candidates: list[dict[str, Any]] = []

    if enable_gemini_fallback:
        should_trigger, reason = should_trigger_fallback(text, deduped_entities)
        if should_trigger:
            logger.info(
                "Triggering Gemini LLM fallback for document %s: %s",
                document_id,
                reason,
            )
            gemini_candidates = extract_with_gemini_fallback(text, api_key=gemini_api_key)
            if gemini_candidates:
                gemini_used = True
                gemini_trigger_reason = reason
                # Filter any legal roles from Gemini results too
                accepted_gemini, _ = filter_legal_roles(gemini_candidates, text)
                all_deterministic.extend(accepted_gemini)
                # Re-deduplicate with LLM candidates
                deduped_entities = deduplicate_entities(all_deterministic, case_id, document_id)

    # Step 7: Build canonical Pydantic Entity models with Provenance
    final_entities: list[Entity] = []
    by_method: dict[str, int] = {
        "regex_phone": 0,
        "regex_vehicle": 0,
        "regex_fir": 0,
        "regex_case_number": 0,
        "spacy_ner": 0,
        "accused_pattern": 0,
        "gemini_fallback": 0,
    }

    for item in deduped_entities:
        primary_method = item.get("method", "spacy_ner")
        if primary_method in by_method:
            by_method[primary_method] += 1
        else:
            by_method[primary_method] = 1

        provenance = Provenance(
            tier=ProvenanceTier.PRIMARY.value,
            source_ref=document_id,
            method=primary_method,
            confidence=float(item.get("confidence", 0.85)),
            extracted_at=datetime.now(UTC),
            metadata={
                "case_id": case_id,
                "document_id": document_id,
                "extraction_methods": item.get("metadata", {}).get("extraction_methods", [primary_method]),
                "start_char": item.get("start_char"),
                "end_char": item.get("end_char"),
            },
        )

        entity_obj = Entity(
            id=item["id"],
            case_id=case_id,
            document_id=document_id,
            name=item["name"],
            entity_type=item["entity_type"],
            aliases=item.get("aliases", []),
            provenance=provenance,
            verification_status=VerificationStatus.UNVERIFIED,
            evidence_snippet=item.get("evidence_snippet"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            metadata=item.get("metadata", {}),
        )
        final_entities.append(entity_obj)

    return {
        "document_id": document_id,
        "case_id": case_id,
        "entities_extracted": len(final_entities),
        "by_method": by_method,
        "gemini_used": gemini_used,
        "gemini_reason": gemini_trigger_reason,
        "filtered_legal_roles_count": len(filtered_legal_roles),
        "entities": final_entities,
    }


def extract_and_store_document(
    document_id: str,
    enable_gemini_fallback: bool = True,
    gemini_api_key: str | None = None,
) -> dict[str, Any]:
    """Retrieve document from MongoDB, execute pipeline, upsert entities, and log audit record."""
    db_docs = get_documents_collection()
    db_entities = get_entities_collection()
    db_audit = get_audit_collection()

    doc_data = db_docs.find_one({"id": document_id})
    if not doc_data:
        raise ValueError(f"Document not found with ID: {document_id}")

    case_id = doc_data.get("case_id", f"case_{document_id}")
    # Retrieve cleaned document text as specified in Task 3.1 & 3.2
    text_to_extract = (
        doc_data.get("text")
        or doc_data.get("extraction_text")
        or ""
    )

    if not text_to_extract or not text_to_extract.strip():
        raise ValueError(f"Document '{document_id}' has empty text content.")

    # Record extraction started audit
    audit_start = AuditLogEntry(
        case_id=case_id,
        actor="nexus_extraction_pipeline",
        action="extraction_started",
        timestamp=datetime.now(UTC),
        input_summary={
            "document_id": document_id,
            "text_length": len(text_to_extract),
            "source_ref": doc_data.get("source_ref"),
        },
        result_summary=f"Initiated entity extraction on document {document_id}",
    )
    db_audit.insert_one(audit_start.model_dump(by_alias=True))

    try:
        extraction_result = run_extraction_pipeline_on_text(
            text=text_to_extract,
            case_id=case_id,
            document_id=document_id,
            enable_gemini_fallback=enable_gemini_fallback,
            gemini_api_key=gemini_api_key,
        )

        entities: list[Entity] = extraction_result["entities"]

        # Remove previous extractions for this document to ensure strict idempotency
        db_entities.delete_many({"document_id": document_id})

        # Idempotent upsert into MongoDB entities collection
        upserted_count = 0
        for ent in entities:
            ent_dict = ent.model_dump(by_alias=True)
            db_entities.replace_one({"id": ent.id}, ent_dict, upsert=True)
            upserted_count += 1

        # Calculate counts by entity type
        by_type: dict[str, int] = {}
        for ent in entities:
            by_type[ent.entity_type] = by_type.get(ent.entity_type, 0) + 1

        # Audit completion
        audit_finish = AuditLogEntry(
            case_id=case_id,
            actor="nexus_extraction_pipeline",
            action="extraction_completed",
            timestamp=datetime.now(UTC),
            input_summary={
                "document_id": document_id,
                "text_length": len(text_to_extract),
            },
            result_summary=(
                f"{len(entities)} entities extracted; "
                f"Gemini used: {extraction_result['gemini_used']}; "
                f"Methods: {extraction_result['by_method']}"
            ),
        )
        db_audit.insert_one(audit_finish.model_dump(by_alias=True))

        return {
            "document_id": document_id,
            "case_id": case_id,
            "status": "success",
            "entities_extracted": len(entities),
            "by_method": extraction_result["by_method"],
            "by_type": by_type,
            "gemini_used": extraction_result["gemini_used"],
            "gemini_reason": extraction_result["gemini_reason"],
            "filtered_legal_roles_count": extraction_result["filtered_legal_roles_count"],
            "entities": [e.model_dump(by_alias=True) for e in entities],
        }

    except Exception as exc:
        logger.error("Extraction pipeline failed for document %s: %s", document_id, exc)
        audit_fail = AuditLogEntry(
            case_id=case_id,
            actor="nexus_extraction_pipeline",
            action="extraction_failed",
            timestamp=datetime.now(UTC),
            input_summary={"document_id": document_id},
            result_summary=f"Extraction failed: {type(exc).__name__}: {str(exc)}",
        )
        db_audit.insert_one(audit_fail.model_dump(by_alias=True))
        raise


def extract_all_corpus_documents(
    enable_gemini_fallback: bool = True,
    gemini_api_key: str | None = None,
) -> dict[str, Any]:
    """Execute extraction safely across all corpus documents in MongoDB.

    Continues processing on individual failures, calculates duration, aggregates entity counts
    by type and method, and logs audit events.
    """
    import time

    start_time = time.perf_counter()
    db_docs = get_documents_collection()
    db_audit = get_audit_collection()

    cursor = db_docs.find({}, {"id": 1, "case_id": 1, "title": 1})
    all_doc_ids = [doc["id"] for doc in cursor if "id" in doc]

    total_docs = len(all_doc_ids)
    successful_docs = 0
    failed_docs = 0
    total_entities = 0
    entity_counts_by_type: dict[str, int] = {}
    entity_counts_by_method: dict[str, int] = {
        "regex_phone": 0,
        "regex_vehicle": 0,
        "regex_fir": 0,
        "regex_case_number": 0,
        "spacy_ner": 0,
        "accused_pattern": 0,
        "gemini_fallback": 0,
    }
    error_details: list[dict[str, str]] = []
    results: list[dict[str, Any]] = []

    # Audit start
    audit_start = AuditLogEntry(
        case_id="corpus_batch",
        actor="nexus_batch_extractor",
        action="batch_extraction_started",
        timestamp=datetime.now(UTC),
        input_summary={"total_documents": total_docs},
        result_summary=f"Started batch entity extraction across {total_docs} documents",
    )
    db_audit.insert_one(audit_start.model_dump(by_alias=True))

    for doc_id in all_doc_ids:
        try:
            res = extract_and_store_document(
                document_id=doc_id,
                enable_gemini_fallback=enable_gemini_fallback,
                gemini_api_key=gemini_api_key,
            )
            successful_docs += 1
            extracted_cnt = res["entities_extracted"]
            total_entities += extracted_cnt

            for m_name, cnt in res.get("by_method", {}).items():
                entity_counts_by_method[m_name] = entity_counts_by_method.get(m_name, 0) + cnt
            for t_name, cnt in res.get("by_type", {}).items():
                entity_counts_by_type[t_name] = entity_counts_by_type.get(t_name, 0) + cnt

            results.append({
                "document_id": doc_id,
                "case_id": res.get("case_id"),
                "status": "success",
                "entities_extracted": extracted_cnt,
                "by_method": res.get("by_method", {}),
                "by_type": res.get("by_type", {}),
                "gemini_used": res.get("gemini_used", False),
            })
        except Exception as exc:
            failed_docs += 1
            err_msg = str(exc)
            logger.warning("Batch extraction error on document %s: %s", doc_id, err_msg)
            error_details.append({
                "document_id": doc_id,
                "error": err_msg,
            })
            results.append({
                "document_id": doc_id,
                "status": "failed",
                "error": err_msg,
            })

    duration_sec = round(time.perf_counter() - start_time, 3)

    # Audit finish
    audit_finish = AuditLogEntry(
        case_id="corpus_batch",
        actor="nexus_batch_extractor",
        action="batch_extraction_completed",
        timestamp=datetime.now(UTC),
        input_summary={
            "total_documents": total_docs,
            "duration_sec": duration_sec,
        },
        result_summary=(
            f"Batch completed: {successful_docs}/{total_docs} succeeded, "
            f"{failed_docs} failed, {total_entities} total entities."
        ),
    )
    db_audit.insert_one(audit_finish.model_dump(by_alias=True))

    return {
        "status": "success" if failed_docs == 0 else "partial_success",
        "total_documents": total_docs,
        "successful_documents": successful_docs,
        "failed_documents": failed_docs,
        "total_entities_extracted": total_entities,
        "total_entities_created_or_updated": total_entities,
        "entity_counts_by_type": entity_counts_by_type,
        "entity_counts_by_method": entity_counts_by_method,
        "processing_duration_sec": duration_sec,
        "error_details": error_details,
        "results": results,
    }
