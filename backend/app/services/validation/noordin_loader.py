"""
noordin_loader.py — Load Noordin Top validation dataset for graph algorithm benchmarking.

SIH26189GREEN | Criminal Network Analysis System
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def get_validation_dir() -> Path:
    """Return the data/validation directory path."""
    current = Path(__file__).resolve()
    # backend/app/services/validation/noordin_loader.py -> backend -> NEXUS -> data/validation
    repo_root = current.parents[4]
    return repo_root / "data" / "validation"


def load_noordin_metadata() -> dict[str, Any]:
    """Load metadata describing the Noordin Top dataset."""
    val_dir = get_validation_dir()
    meta_file = val_dir / "noordin_top_metadata.json"
    if not meta_file.exists():
        raise FileNotFoundError(f"Noordin Top metadata file not found at {meta_file}")
    with open(meta_file, encoding="utf-8") as fp:
        return json.load(fp)


def load_edge_file(filename: str) -> list[dict[str, Any]]:
    """Load an edge list CSV by filename."""
    val_dir = get_validation_dir()
    file_path = val_dir / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Validation edge file not found: {file_path}")

    edges: list[dict[str, Any]] = []
    with open(file_path, encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            if not row or not row.get("source"):
                continue
            edges.append({
                "source": row["source"],
                "target": row["target"],
                "relationship": row.get("relationship", ""),
                "confidence": float(row.get("confidence", 1.0)),
                "source_reference": row.get("source_reference", ""),
            })
    return edges


def load_communication_edges() -> list[dict[str, Any]]:
    return load_edge_file("communication_edges.csv")


def load_operational_edges() -> list[dict[str, Any]]:
    return load_edge_file("operational_edges.csv")


def load_trust_edges() -> list[dict[str, Any]]:
    return load_edge_file("trust_edges.csv")


def load_financial_edges() -> list[dict[str, Any]]:
    return load_edge_file("financial_edges.csv")


def load_all_noordin_edges() -> dict[str, list[dict[str, Any]]]:
    """Load all categorized edge lists for validation benchmarking."""
    return {
        "communication": load_communication_edges(),
        "operational": load_operational_edges(),
        "trust": load_trust_edges(),
        "financial": load_financial_edges(),
    }
