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


def load_noordin_edges() -> list[dict[str, Any]]:
    """Load ground-truth network edges from CSV."""
    val_dir = get_validation_dir()
    edge_file = val_dir / "noordin_top_edges.csv"
    if not edge_file.exists():
        raise FileNotFoundError(f"Noordin Top edge list not found at {edge_file}")

    edges: list[dict[str, Any]] = []
    with open(edge_file, encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            edges.append({
                "source": row["source"],
                "target": row["target"],
                "relationship_type": row["relationship_type"],
                "weight": float(row.get("weight", 1.0)),
                "provenance": row.get("provenance", "ICG Report No. 114"),
            })
    return edges
