"""Edge generation rules for NEXUS criminal network graphs.

Rules:
A. Person <-> Person:
   - co_accused: multiple individuals identified as accused in the same case.
   - associated_with: individuals explicitly co-occurring in the same sentence or connected fact section.
B. Person <-> Organization:
   - associated_with: person explicitly co-occurring with an organization in the same sentence.
C. Person <-> Location:
   - located_at: person explicitly linked with a location in the same sentence.
D. Person <-> Vehicle:
   - used_vehicle: person explicitly associated with a vehicle in the same sentence.

Principle:
Relationships are strictly derived from source text evidence. Weak name similarity alone never generates edges.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.models.enums import ProvenanceMethod
from app.services.extraction.legal_role_filter import is_legal_role

logger = logging.getLogger(__name__)

# Base deterministic weights by relationship type
EDGE_WEIGHT_MAP = {
    "co_accused": 1.0,
    "used_vehicle": 0.8,
    "associated_with": 0.5,
    "located_at": 0.5,
}

INCREMENT_WEIGHT_MAP = {
    "co_accused": 0.2,
    "used_vehicle": 0.2,
    "associated_with": 0.1,
    "located_at": 0.1,
}


def is_valid_accused_person(name: str, evidence_snippet: str = "") -> bool:
    """Check if entity name represents a plausible person and not a legal role or court citation."""
    name_clean = name.strip()
    if len(name_clean) < 3:
        return False
    # Check legal role filter
    is_filtered, _ = is_legal_role(name_clean, "", -1, -1)
    if is_filtered:
        return False
    name_lower = name_clean.lower()
    invalid_keywords = [
        "public prosecutor",
        "prosecutor",
        "advocate",
        "counsel",
        "sessions judge",
        "special judge",
        "high court",
        "supreme court",
        "police station",
        "crl.a",
        "crl. appeal",
        "criminal appeal",
        "section ",
        "act, ",
        "senior",
        "senior counsel",
        "standing counsel",
        "government pleader",
    ]
    if any(kw in name_lower for kw in invalid_keywords):
        return False
    if evidence_snippet:
        snip_lower = evidence_snippet.lower()
        if re.search(r"\b(?:senior\s+counsel|counsel\s+for|advocate\s+for|appeared\s+for)\b", snip_lower):
            return False
    return True


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences deterministically."""
    if not text:
        return []
    # Split on sentence boundaries (.!? followed by space or newline)
    raw_sentences = re.split(r"(?<=[.!?])\s+", text)
    cleaned = []
    for s in raw_sentences:
        s_clean = s.strip()
        if len(s_clean) >= 10:
            cleaned.append(s_clean)
    return cleaned


def extract_candidate_edges_from_document(
    doc_id: str,
    case_id: str,
    text: str,
    entities: list[dict[str, Any]],
    alias_map: dict[str, str],
) -> list[dict[str, Any]]:
    """Extract candidate relationship edges from a document text.

    Args:
        doc_id: Document string identifier.
        case_id: Case string identifier.
        text: Judgment / fact narrative text.
        entities: List of entity dictionaries for this case.
        alias_map: Mapping from entity ID to canonical entity ID.

    Returns:
        List of candidate edge dicts with canonicalized source and target IDs.
    """
    candidate_edges: list[dict[str, Any]] = []
    if not text or not entities:
        return candidate_edges

    # Canonicalize and organize entities
    # Map canonical_id -> entity metadata
    canonical_entities: dict[str, dict[str, Any]] = {}
    for ent in entities:
        orig_id = ent.get("id")
        if not orig_id:
            continue
        canon_id = alias_map.get(orig_id, orig_id)
        if canon_id not in canonical_entities:
            canonical_entities[canon_id] = {
                "id": canon_id,
                "name": ent.get("name", ""),
                "entity_type": ent.get("entity_type", "UNKNOWN").upper(),
                "is_accused": bool(ent.get("metadata", {}).get("is_accused")),
                "aliases": list(ent.get("aliases", [])),
                "case_id": ent.get("case_id", case_id),
                "evidence_snippet": ent.get("evidence_snippet", ""),
            }
        else:
            # Aggregate accused flags / aliases / snippets
            if ent.get("metadata", {}).get("is_accused"):
                canonical_entities[canon_id]["is_accused"] = True
            canonical_entities[canon_id]["aliases"].extend(ent.get("aliases", []))
            if not canonical_entities[canon_id].get("evidence_snippet") and ent.get("evidence_snippet"):
                canonical_entities[canon_id]["evidence_snippet"] = ent.get("evidence_snippet", "")

    # 1. Rule A1: Person <-> Person (co-accused in the same case)
    accused_persons = [
        e for e in canonical_entities.values()
        if e["entity_type"] in {"PERSON", "ACCUSED"}
        and e["is_accused"]
        and is_valid_accused_person(e["name"], e.get("evidence_snippet", ""))
    ]

    for i in range(len(accused_persons)):
        for j in range(i + 1, len(accused_persons)):
            p1 = accused_persons[i]
            p2 = accused_persons[j]
            if p1["id"] == p2["id"]:
                continue
            src_id, tgt_id = (p1["id"], p2["id"]) if p1["id"] < p2["id"] else (p2["id"], p1["id"])
            candidate_edges.append({
                "source_entity_id": src_id,
                "target_entity_id": tgt_id,
                "edge_type": "co_accused",
                "case_id": case_id,
                "document_id": doc_id,
                "evidence_snippet": f"Co-accused in case {case_id}: {p1['name']} and {p2['name']}",
                "method": ProvenanceMethod.ACCUSED_PATTERN.value,
                "confidence": 0.95,
            })

    # Prepare entity surface forms for sentence-level co-occurrence
    # Build list of (canon_id, entity_type, compiled_regex_list)
    entity_matchers: list[tuple[str, str, list[re.Pattern[str]]]] = []
    for canon_id, e in canonical_entities.items():
        name = e["name"].strip()
        if len(name) < 3:
            continue
        if e["entity_type"] in {"PERSON", "ACCUSED"} and not is_valid_accused_person(name, e.get("evidence_snippet", "")):
            continue
        patterns = [name]
        for a in e["aliases"]:
            a_clean = a.strip()
            if len(a_clean) >= 3 and a_clean not in patterns:
                patterns.append(a_clean)

        # Compile word-boundary regex patterns
        compiled: list[re.Pattern[str]] = []
        for pat in patterns:
            try:
                compiled.append(re.compile(r"\b" + re.escape(pat) + r"\b", re.IGNORECASE))
            except re.error:
                continue
        if compiled:
            entity_matchers.append((canon_id, e["entity_type"], compiled))

    # Sentence segmentation for explicit co-occurrence
    sentences = split_into_sentences(text)

    for sentence in sentences:
        matched_in_sentence: list[tuple[str, str]] = []  # (canon_id, entity_type)

        for canon_id, etype, compiled_patterns in entity_matchers:
            matched = False
            for pat_re in compiled_patterns:
                if pat_re.search(sentence):
                    matched = True
                    break
            if matched:
                matched_in_sentence.append((canon_id, etype))

        if len(matched_in_sentence) < 2:
            continue

        # Evaluate pairs in the sentence
        for i in range(len(matched_in_sentence)):
            for j in range(i + 1, len(matched_in_sentence)):
                id_a, type_a = matched_in_sentence[i]
                id_b, type_b = matched_in_sentence[j]
                if id_a == id_b:
                    continue

                # Ensure deterministic ordering
                src_id, tgt_id = (id_a, id_b) if id_a < id_b else (id_b, id_a)
                s_type, t_type = (type_a, type_b) if id_a < id_b else (type_b, type_a)

                # Determine edge type based on taxonomy
                edge_type: str | None = None
                conf = 0.85

                if {s_type, t_type}.issubset({"PERSON", "ACCUSED"}):
                    # Person <-> Person in same sentence
                    edge_type = "associated_with"
                elif (s_type in {"PERSON", "ACCUSED"} and t_type == "ORGANIZATION") or \
                     (t_type in {"PERSON", "ACCUSED"} and s_type == "ORGANIZATION"):
                    # Person <-> Organization
                    edge_type = "associated_with"
                elif (s_type in {"PERSON", "ACCUSED"} and t_type == "LOCATION") or \
                     (t_type in {"PERSON", "ACCUSED"} and s_type == "LOCATION"):
                    # Person <-> Location
                    edge_type = "located_at"
                elif (s_type in {"PERSON", "ACCUSED"} and t_type == "VEHICLE") or \
                     (t_type in {"PERSON", "ACCUSED"} and s_type == "VEHICLE"):
                    # Person <-> Vehicle
                    edge_type = "used_vehicle"

                if edge_type:
                    # Snippet max 250 chars
                    snip = sentence if len(sentence) <= 250 else sentence[:247] + "..."
                    candidate_edges.append({
                        "source_entity_id": src_id,
                        "target_entity_id": tgt_id,
                        "edge_type": edge_type,
                        "case_id": case_id,
                        "document_id": doc_id,
                        "evidence_snippet": snip,
                        "method": ProvenanceMethod.DIRECT_TEXT.value,
                        "confidence": conf,
                    })

    return candidate_edges
