"""Deterministic entity normalization and deduplication for NEXUS.

Ensures:
- Safe consolidation of multi-extractor detections (e.g., spaCy + accused_pattern)
- Idempotent stable string IDs (sha256 hash of scope, type, and normalized key)
- Preservation of all extraction methods and aliases in metadata
- Prevention of careless merges of distinct actors
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

# Honorific titles to strip during normalization for matching
HONORIFIC_PREFIXES = re.compile(
    r"^(?:mr\.?|ms\.?|mrs\.?|shri\.?|smt\.?|sri\.?|dr\.?|late\.?|md\.?|mohd\.?)\s+",
    re.IGNORECASE,
)


ACCUSED_PREFIX = re.compile(
    r"^(?:A[-.\s]?(\d{1,2})|[Aa]ccused(?:\s+(?:[Nn]o\.?|[Nn]umber))?\s*(\d{1,2}))[\s,–-]+(?:namely,?\s+)?",
    re.IGNORECASE,
)


def normalize_name(name: str, entity_type: str) -> tuple[str, str | None]:
    """Normalize entity text according to its taxonomy type.

    Returns:
        (normalized_name, detected_accused_id_or_none)
    """
    cleaned = re.sub(r"\s+", " ", name).strip()
    detected_accused: str | None = None

    if entity_type in {"PERSON", "ACCUSED"}:
        # Strip accused prefix e.g. "A-1 Rajesh Kumar" -> "Rajesh Kumar" (accused_id="A-1")
        acc_match = ACCUSED_PREFIX.match(cleaned)
        if acc_match:
            num = acc_match.group(1) or acc_match.group(2)
            detected_accused = f"A-{num}"
            rest = cleaned[acc_match.end() :].strip()
            if len(rest) >= 2:
                cleaned = rest

        # Strip honorifics
        stripped = HONORIFIC_PREFIXES.sub("", cleaned).strip()
        # If all uppercase or all lowercase, title case for consistency
        if stripped.isupper() or stripped.islower():
            stripped = stripped.title()
        return stripped, detected_accused

    if entity_type == "VEHICLE":
        return re.sub(r"[\s.-]", "", cleaned).upper(), None

    if entity_type == "PHONE":
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) >= 10:
            ten = digits[-10:]
            return f"+91{ten}", None
        return cleaned, None

    if entity_type in {"FIR", "CASE_NUMBER"}:
        return cleaned.strip(), None

    # LOCATION / ORGANIZATION: standard clean
    if cleaned.isupper() and len(cleaned) > 4:
        return cleaned.title(), None
    return cleaned, None


def generate_stable_entity_id(case_id: str, entity_type: str, normalized_name: str) -> str:
    """Generate an immutable, deterministic entity ID based on case, type, and name."""
    hash_input = f"{case_id}:{entity_type.upper()}:{normalized_name.lower()}"
    digest = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]
    return f"ent_{case_id}_{digest}"


def deduplicate_entities(
    candidate_entities: list[dict[str, Any]],
    case_id: str,
    document_id: str,
) -> list[dict[str, Any]]:
    """Deduplicate and reconcile candidate entities extracted across multiple methods.

    Returns:
        List of finalized, unique entity dictionaries ready for Pydantic Entity instantiation.
    """
    # Map to group entities: key -> aggregated entity record
    # Key: (entity_type, normalized_name)
    grouped: dict[str, dict[str, Any]] = {}

    # First pass: map accused IDs to resolved names if any
    # E.g., "A-1" -> "Rajesh Kumar"
    accused_map: dict[str, str] = {}
    for cand in candidate_entities:
        acc_id = cand.get("accused_id")
        name = cand.get("name", "")
        if acc_id and cand.get("entity_type") == "PERSON" and name and name != acc_id:
            accused_map[acc_id] = name

    for cand in candidate_entities:
        raw_name = cand.get("name", "")
        if not raw_name:
            continue

        raw_type = cand.get("entity_type", "UNKNOWN")
        acc_id = cand.get("accused_id")

        # If this is an unnamed ACCUSED (e.g. name="A-1") and we have resolved "A-1" to a person,
        # redirect this entity to that person
        if raw_type == "ACCUSED" and raw_name in accused_map:
            resolved_name = accused_map[raw_name]
            raw_name = resolved_name
            raw_type = "PERSON"

        norm_name, detected_acc = normalize_name(raw_name, raw_type)
        if not norm_name:
            continue

        effective_acc_id = acc_id or detected_acc
        group_key = f"{raw_type}:{norm_name.lower()}"

        if group_key not in grouped:
            stable_id = generate_stable_entity_id(case_id, raw_type, norm_name)
            methods = [cand.get("method")] if cand.get("method") else []
            aliases: list[str] = []
            if raw_name != norm_name:
                aliases.append(raw_name)
            if effective_acc_id and effective_acc_id not in aliases:
                aliases.append(effective_acc_id)

            grouped[group_key] = {
                "id": stable_id,
                "case_id": case_id,
                "document_id": document_id,
                "name": norm_name,
                "entity_type": raw_type,
                "aliases": aliases,
                "confidence": float(cand.get("confidence", 0.85)),
                "method": cand.get("method", "deterministic"),
                "evidence_snippet": cand.get("evidence_snippet", ""),
                "methods": set(methods),
                "occurrences": 1,
                "start_char": cand.get("start_char"),
                "end_char": cand.get("end_char"),
                "metadata": dict(cand.get("metadata", {})),
            }
        else:
            # Merge with existing group
            entry = grouped[group_key]
            entry["occurrences"] += 1
            if cand.get("method"):
                entry["methods"].add(cand["method"])

            # Add aliases
            if raw_name not in entry["aliases"] and raw_name != norm_name:
                entry["aliases"].append(raw_name)
            if effective_acc_id and effective_acc_id not in entry["aliases"]:
                entry["aliases"].append(effective_acc_id)

            # Keep highest confidence
            cand_conf = float(cand.get("confidence", 0.85))
            if cand_conf > entry["confidence"]:
                entry["confidence"] = cand_conf
                entry["method"] = cand.get("method", entry["method"])

            # Prefer longer, richer evidence snippet
            cand_snip = cand.get("evidence_snippet", "")
            if len(cand_snip) > len(entry["evidence_snippet"]):
                entry["evidence_snippet"] = cand_snip

            # Merge metadata
            entry["metadata"].update(cand.get("metadata", {}))

    # Format final list
    finalized: list[dict[str, Any]] = []
    for entry in grouped.values():
        methods_list = sorted(list(entry.pop("methods", set())))
        entry["metadata"]["extraction_methods"] = methods_list
        entry["metadata"]["occurrence_count"] = entry.pop("occurrences", 1)
        if len(methods_list) > 1 and "accused_pattern" in methods_list:
            # Multi-method consensus
            entry["confidence"] = min(1.0, entry["confidence"] + 0.05)

        finalized.append(entry)

    # Sort deterministically by entity_type, then name
    finalized.sort(key=lambda x: (x["entity_type"], x["name"]))
    return finalized
