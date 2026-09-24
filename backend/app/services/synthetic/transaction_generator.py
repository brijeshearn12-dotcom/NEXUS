"""Synthetic Financial Transaction edge generator for NEXUS.

Connects strictly PRE-EXISTING extracted entities using synthetic financial transfer records.
Every generated edge is explicitly marked with synthetic provenance tier.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from faker import Faker

fake = Faker()


def generate_synthetic_transactions(
    case_id: str,
    eligible_entities: list[dict[str, Any]],
    count: int = 5,
) -> list[dict[str, Any]]:
    """Generate synthetic financial transaction edges connecting existing case entities.

    Args:
        case_id: ID of the case.
        eligible_entities: List of existing entity dicts from MongoDB (must have 'id' and 'name').
        count: Number of synthetic transaction edges to generate.

    Returns:
        List of edge dictionaries conforming to the canonical NEXUS Edge schema.
    """
    if len(eligible_entities) < 2:
        return []

    # Can connect persons or organizations
    valid_types = {"PERSON", "ACCUSED", "ORGANIZATION"}
    candidates = [e for e in eligible_entities if str(e.get("entity_type", "")).upper() in valid_types]
    pool = candidates if len(candidates) >= 2 else eligible_entities

    edges: list[dict[str, Any]] = []
    num_to_generate = max(1, min(count, 50))
    now = datetime.now(UTC)

    seen_pairs: set[tuple[str, str]] = set()
    attempts = 0
    max_attempts = num_to_generate * 10

    txn_methods = [
        ("wire_transfer", "RTGS/NEFT"),
        ("cash_deposit", "Cash Deposit Machine"),
        ("hawala_remittance", "Informal Hawala Channel"),
        ("upi", "Instant Payment UPI"),
    ]

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

        txn_type, channel_desc = random.choice(txn_methods)
        amount = round(random.uniform(25000, 850000) / 1000) * 1000
        days_ago = random.randint(2, 60)
        txn_time = now - timedelta(days=days_ago, seconds=random.randint(60, 86400))
        txn_time_iso = txn_time.isoformat()

        ref_no = fake.bothify("TXN-########")
        edge_unique_id = f"synth_txn_{uuid.uuid4().hex[:12]}"
        src_name = src.get("name") or s_id
        tgt_name = tgt.get("name") or t_id

        edge_doc: dict[str, Any] = {
            "id": edge_unique_id,
            "edge_id": edge_unique_id,
            "case_id": case_id,
            "case_ids": [case_id],
            "source_entity_id": s_id,
            "target_entity_id": t_id,
            "relationship_type": "SYNTHETIC_TRANSACTION",
            "edge_type": "SYNTHETIC_TRANSACTION",
            "weight": 1.0,
            "confidence": 0.70,
            "verification_status": "unverified",
            "evidence": (
                f"[SYNTHETIC DEMO] Financial Transfer: ₹{amount:,.2f} ({channel_desc}) "
                f"from '{src_name}' to '{tgt_name}' [Ref: {ref_no}] at {txn_time_iso}."
            ),
            "provenance": {
                "tier": "synthetic",
                "source_ref": "synthetic-demo",
                "method": "faker",
                "confidence": 0.70,
                "extracted_at": now,
                "metadata": {
                    "synthetic": True,
                    "generator": "transaction_generator",
                    "amount": amount,
                    "currency": "INR",
                    "transaction_type": txn_type,
                    "channel": channel_desc,
                    "reference_no": ref_no,
                    "timestamp": txn_time_iso,
                    "notice": (
                        "SYNTHETIC DEMONSTRATION DATA: Generated via Faker for analytical "
                        "demonstration purposes only. Not a real-world banking transaction."
                    ),
                },
            },
            "created_at": now,
            "updated_at": now,
        }
        edges.append(edge_doc)

    return edges
