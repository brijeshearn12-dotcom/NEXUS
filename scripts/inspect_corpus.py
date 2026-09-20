#!/usr/bin/env python3
"""
inspect_corpus.py — Basic sanity check and statistics for cached judgments in data/raw.

SIH26189GREEN | Criminal Network Analysis System
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List


def find_repo_root() -> Path:
    """Locate the repository root directory."""
    current = Path(__file__).resolve().parent
    while current.parent != current:
        if (current / ".git").exists() or (current / "data").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent


def inspect_corpus(raw_dir: Path, sample_count: int = 3) -> Dict[str, Any]:
    print("=" * 68)
    print("CORPUS SANITY CHECK & QUALITY AUDIT — SIH26189GREEN")
    print("=" * 68)
    print(f"Inspecting directory: {raw_dir.resolve()}\n")

    if not raw_dir.exists():
        print(f"Error: Directory does not exist: {raw_dir}")
        sys.exit(1)

    json_files = sorted(raw_dir.glob("doc_*.json"))
    manifest_file = raw_dir / "corpus_manifest.json"
    index_file = raw_dir / "index.json"

    total_files = len(json_files)
    print(f"Total judgment files found (doc_*.json): {total_files}")
    print(f"Index file present (index.json)       : {index_file.exists()}")
    print(f"Manifest file present (corpus_manifest): {manifest_file.exists()}\n")

    if total_files == 0:
        print("Warning: No judgment documents found in data/raw.")
        return {"total_documents": 0}

    valid_docs = 0
    empty_or_invalid_docs: List[str] = []
    text_lengths: List[int] = []
    parsed_records: List[Dict[str, Any]] = []

    for fpath in json_files:
        try:
            with open(fpath, "r", encoding="utf-8") as fp:
                data = json.load(fp)

            tid = data.get("tid")
            raw_response = data.get("raw_api_response", {})
            doc_body = raw_response.get("doc") or data.get("doc", "")

            # Check if document has usable text content
            if not doc_body or not isinstance(doc_body, str) or len(doc_body.strip()) < 100:
                empty_or_invalid_docs.append(fpath.name)
            else:
                valid_docs += 1
                text_lengths.append(len(doc_body))
                parsed_records.append({
                    "tid": tid,
                    "title": data.get("title", ""),
                    "docsource": data.get("docsource", ""),
                    "publishdate": data.get("publishdate", ""),
                    "source_url": data.get("source_url", ""),
                    "query_used": data.get("query_used", ""),
                    "text_length": len(doc_body),
                    "file_name": fpath.name,
                })
        except Exception as err:
            empty_or_invalid_docs.append(f"{fpath.name} (Error: {err})")

    # Statistics
    stats: Dict[str, Any] = {}
    if text_lengths:
        stats["min"] = min(text_lengths)
        stats["max"] = max(text_lengths)
        stats["mean"] = round(statistics.mean(text_lengths), 1)
        stats["median"] = round(statistics.median(text_lengths), 1)
        stats["total_characters"] = sum(text_lengths)

    print("-" * 68)
    print("DOCUMENT INTEGRITY")
    print("-" * 68)
    print(f"Valid, usable judgments : {valid_docs} / {total_files} ({round(valid_docs/total_files*100, 1)}%)")
    print(f"Empty or invalid files  : {len(empty_or_invalid_docs)}")
    if empty_or_invalid_docs:
        print(f"  Flagged files: {empty_or_invalid_docs[:5]}")

    print("\n" + "-" * 68)
    print("TEXT LENGTH STATISTICS (CHARACTERS)")
    print("-" * 68)
    if text_lengths:
        print(f"Minimum length : {stats['min']:,} chars")
        print(f"Maximum length : {stats['max']:,} chars")
        print(f"Mean length    : {stats['mean']:,} chars")
        print(f"Median length  : {stats['median']:,} chars")
        print(f"Total volume   : {stats['total_characters']:,} chars")

    # Display samples
    print("\n" + "-" * 68)
    print(f"SAMPLE DOCUMENT METADATA RECORDS (Showing {min(sample_count, len(parsed_records))})")
    print("-" * 68)
    for idx, rec in enumerate(parsed_records[:sample_count], 1):
        print(f"--- [Sample {idx}] ---")
        print(f"Document ID : {rec['tid']}")
        print(f"Title       : {rec['title']}")
        print(f"Court/Source: {rec['docsource']}")
        print(f"Date        : {rec['publishdate']}")
        print(f"Query       : {rec['query_used']}")
        print(f"Source URL  : {rec['source_url']}")
        print(f"Text Length : {rec['text_length']:,} characters")
        print(f"Stored file : {rec['file_name']}")
        print()

    print("=" * 68)
    return {
        "total_documents": total_files,
        "valid_documents": valid_docs,
        "empty_or_invalid": len(empty_or_invalid_docs),
        "text_length_stats": stats,
        "samples": parsed_records[:sample_count],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Corpus sanity check for SIH26189GREEN.")
    parser.add_argument(
        "--dir",
        "-d",
        type=str,
        default=None,
        help="Path to raw data directory (default: data/raw)",
    )
    parser.add_argument(
        "--samples",
        "-s",
        type=int,
        default=3,
        help="Number of sample records to display (default: 3)",
    )
    args = parser.parse_args()

    raw_dir = Path(args.dir) if args.dir else find_repo_root() / "data" / "raw"
    inspect_corpus(raw_dir=raw_dir, sample_count=args.samples)


if __name__ == "__main__":
    main()
