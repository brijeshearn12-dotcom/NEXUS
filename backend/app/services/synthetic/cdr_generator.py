"""Synthetic Call Detail Record (CDR) edge generator for NEXUS.

Connects strictly PRE-EXISTING extracted entities using synthetic CDR communication records.
Every generated edge is explicitly marked with synthetic provenance tier.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from faker import Faker

fake = Faker()


def generate_synthetic_cdr(
    case_id: str,
    eligible_entities: list[dict[str, Any]],
    count: int = 5,
) -> list[dict[str, Any]]:
    """Generate synthetic CDR communication edges connecting existing case entities.

    Args:
        case_id: ID of the case.
        eligible_entities: List of existing entity dicts from MongoDB (must have 'id' and 'name').
        count: Number of synthetic CDR edges to generate.

    Returns:
        List of edge dictionaries conforming to the canonical NEXUS Edge schema.
    """
    if len(eligible_entities) < 2:
        return []

    # Prefer PERSON entities, fallback to general entities if fewer than 2 persons
    persons = [e for e in eligible_entities if str(e.get("entity_type", "")).upper() in {"PERSON", "ACCUSED"}]
    pool = persons if len(persons) >= 2 else eligible_entities

    edges: list[dict[str, Any]] = []
    num_to_generate = max(1, min(count, 50))
    now = datetime.now(UTC)

    # Track generated entity pairs to avoid duplicate parallel synthetic edges
    seen_pairs: set[tuple[str, str]] = set()

    attempts = 0
    max_attempts = num_to_generate * 10

    while len(edges) < num_to_generate and attempts < max_attempts:
        attempts += 1
        src, tgt = random.sample(pool, 2)
        s_id, t_id = str(src.get("id")), str(tgt.get("id"))
        if not s_id or not t_id or s_id == t_id:
            continue

        pair_key = (min(s_id, t_id), max(s_id, t_id))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        call_type = random.choices(["voice", "sms"], weights=[0.7, 0.3])[0]
        duration_seconds = random.randint(25, 480) if call_type == "voice" else 0
        days_ago = random.randint(1, 45)
        call_time = now - timedelta(days=days_ago, seconds=random.randint(60, 86400))
        call_time_iso = call_time.isoformat()

        region_code = random.choice(["DL", "MH", "JK", "KA", "WB", "PB"])
        cell_tower = f"TOWER-{region_code}-{random.randint(101, 899)}"
        caller_imei = fake.numerify("35###########")
        recipient_imei = fake.numerify("35###########")

        edge_unique_id = f"synth_cdr_{uuid.uuid4().hex[:12]}"
        src_name = src.get("name") or s_id
        tgt_name = tgt.get("name") or t_id

        edge_doc: dict[str, Any] = {
            "id": edge_unique_id,
            "edge_id": edge_unique_id,
            "case_id": case_id,
            "case_ids": [case_id],
            "source_entity_id": s_id,
            "target_entity_id": t_id,
            "relationship_type": "SYNTHETIC_CDR",
            "edge_type": "SYNTHETIC_CDR",
            "weight": 1.0,
            "confidence": 0.70,
            "verification_status": "unverified",
            "evidence": (
                f"[SYNTHETIC DEMO] CDR Event: {call_type.upper()} ({duration_seconds}s) "
                f"between '{src_name}' and '{tgt_name}' logged via cell tower {cell_tower} "
                f"at {call_time_iso}."
            ),
            "provenance": {
                "tier": "synthetic",
                "source_ref": "synthetic-demo",
                "method": "faker",
                "confidence": 0.70,
                "extracted_at": now,
                "metadata": {
                    "synthetic": True,
                    "generator": "cdr_generator",
                    "call_type": call_type,
                    "duration_seconds": duration_seconds,
                    "cell_tower_id": cell_tower,
                    "timestamp": call_time_iso,
                    "caller_imei": caller_imei,
                    "recipient_imei": recipient_imei,
                    "notice": (
                        "SYNTHETIC DEMONSTRATION DATA: Generated via Faker for analytical "
                        "demonstration purposes only. Not a real-world telecommunications intercept."
                    ),
                },
            },
            "created_at": now,
            "updated_at": now,
        }
        edges.append(edge_doc)

    return edges
