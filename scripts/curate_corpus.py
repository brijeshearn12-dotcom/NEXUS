#!/usr/bin/env python3
"""
curate_corpus.py — Automated curation of high-value criminal network judgments.

SIH26189GREEN | Criminal Network Analysis System
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
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


# Regex pattern definitions for relationship categories
RELATIONSHIP_PATTERNS: Dict[str, List[str]] = {
    "multi_accused": [
        r"\bA[- ]?[1-9]\b",
        r"\baccused\s+no\.?\s*[1-9]\b",
        r"\bco[- ]accused\b",
        r"\bappellant\s+no\.?\s*[1-9]\b",
        r"\brespondent\s+no\.?\s*[1-9]\b",
        r"\bco[- ]conspirator\b",
    ],
    "conspiracy_and_common_intention": [
        r"\b120[- ]?B\b",
        r"\bSection\s+34\b",
        r"\bmeeting\s+of\s+minds\b",
        r"\bcommon\s+intention\b",
        r"\bcriminal\s+conspiracy\b",
        r"\bconcerted\s+plan\b",
    ],
    "communication_evidence": [
        r"\bCDR\b",
        r"\bcall\s+detail\s+records?\b",
        r"\bwhatsapp\b",
        r"\bmobile\s+phones?\b",
        r"\bface\s+time\b",
        r"\bsim\s+cards?\b",
        r"\btower\s+location\b",
        r"\bphone\s+calls?\b",
        r"\bintercepted\s+calls?\b",
    ],
    "financial_relationships": [
        r"\bhawala\b",
        r"\bbank\s+accounts?\b",
        r"\bfinancial\s+assistance\b",
        r"\btransferred\s+money\b",
        r"\bproceeds\s+of\s+crime\b",
        r"\bbribe\b",
        r"\bcash\s+of\s+Rs\b",
        r"\bfunds\b",
        r"\bmoney\s+laundering\b",
    ],
    "operational_and_logistics": [
        r"\bharbouring\b|\bharboring\b",
        r"\bshelter\b",
        r"\bprovided\s+vehicle\b",
        r"\bfirearms?\b|\bweapons?\b",
        r"\bcartridges?\b|\bammunition\b",
        r"\bexplosives?\b",
        r"\bhideout\b",
        r"\blogistical\s+support\b",
        r"\brecovery\s+of\b",
    ],
    "hierarchy_and_instructions": [
        r"\bmastermind\b",
        r"\bkingpin\b",
        r"\bat\s+the\s+behest\s+of\b",
        r"\bon\s+the\s+instructions\s+of\b",
        r"\bdirected\s+by\b",
        r"\bhandler\b",
        r"\bkey\s+conspirator\b",
        r"\bactive\s+role\b",
        r"\bprime\s+accused\b",
        r"\bleader\b",
    ],
    "syndicate_and_gang": [
        r"\borgani[sz]ed\s+crime\b",
        r"\bgang\b",
        r"\bsyndicate\b",
        r"\bcartel\b",
        r"\bmafia\b",
        r"\bMCOCA\b",
        r"\bgangster\s+act\b",
        r"\binter[- ]state\b",
    ],
    "testimony_and_statements": [
        r"\bSection\s+161\b",
        r"\bSection\s+164\b",
        r"\bconfessional\s+statement\b",
        r"\bdisclosure\s+statement\b",
        r"\bstatement\s+of\s+co[- ]accused\b",
        r"\bapprover\b",
    ],
}


def strip_html_tags(text: str) -> str:
    """Remove HTML formatting to work on raw text."""
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean)


def analyze_document(fpath: Path) -> Dict[str, Any]:
    with open(fpath, "r", encoding="utf-8") as fp:
        data = json.load(fp)

    tid = data.get("tid")
    title = data.get("title", "")
    court = data.get("docsource", "")
    pdate = data.get("publishdate", "")
    src_url = data.get("source_url", "")
    query = data.get("query_used", "")

    raw_response = data.get("raw_api_response", {})
    doc_html = raw_response.get("doc") or data.get("doc", "")
    plain_text = strip_html_tags(doc_html)
    text_length = len(plain_text)

    detected_categories: Dict[str, int] = {}
    matched_phrases: Dict[str, List[str]] = {}

    for cat_name, patterns in RELATIONSHIP_PATTERNS.items():
        total_cat_matches = 0
        cat_matches: List[str] = []
        for pat in patterns:
            matches = re.findall(pat, plain_text, flags=re.IGNORECASE)
            if matches:
                total_cat_matches += len(matches)
                cat_matches.append(pat)
        if total_cat_matches > 0:
            detected_categories[cat_name] = total_cat_matches
            matched_phrases[cat_name] = cat_matches

    # Extract distinct accused identifiers
    accused_matches = set(re.findall(r"\b(?:A[- ]?\d+|accused\s+no\.?\s*\d+)\b", plain_text, flags=re.IGNORECASE))

    # Scoring formulation:
    # 1. Category Diversity: 0 to 8 categories present
    category_count = len(detected_categories)

    # 2. Critical Relationship Pillars:
    # Must have communication, financial, or operational ties for strong network analysis
    has_network_ties = (
        ("communication_evidence" in detected_categories) or
        ("financial_relationships" in detected_categories) or
        ("operational_and_logistics" in detected_categories)
    )
    has_hierarchy_or_gang = (
        ("hierarchy_and_instructions" in detected_categories) or
        ("syndicate_and_gang" in detected_categories)
    )
    has_multi_accused = ("multi_accused" in detected_categories) or (len(accused_matches) >= 2)
    has_conspiracy = "conspiracy_and_common_intention" in detected_categories

    # Base score: Category breadth * 15
    score = category_count * 15.0

    # Multi-accused bonus
    if has_multi_accused:
        score += 25.0
        score += min(len(accused_matches) * 2.0, 20.0)

    # Conspiracy bonus
    if has_conspiracy:
        score += 20.0

    # Concrete relational evidence bonuses (CDR, money, shelter, logistics)
    if has_network_ties:
        score += 25.0
    if has_hierarchy_or_gang:
        score += 20.0
    if "testimony_and_statements" in detected_categories:
        score += 10.0

    # Minimum text length viability threshold
    if text_length < 8000:
        score *= 0.5
    elif text_length > 30000:
        score += 10.0

    # Reason for selection formulation
    key_reasons: List[str] = []
    if len(accused_matches) >= 2:
        key_reasons.append(f"Multiple accused structure ({len(accused_matches)} accused identifiers found)")
    elif "multi_accused" in detected_categories:
        key_reasons.append("Co-accused references documented")

    if has_conspiracy:
        key_reasons.append("Criminal conspiracy / Section 120-B charge")
    if "communication_evidence" in detected_categories:
        key_reasons.append("Telecommunication / CDR / mobile interaction evidence")
    if "financial_relationships" in detected_categories:
        key_reasons.append("Financial transactions / funds / hawala links")
    if "operational_and_logistics" in detected_categories:
        key_reasons.append("Logistical support / shelter / weapons recovery")
    if "hierarchy_and_instructions" in detected_categories:
        key_reasons.append("Hierarchical directives / mastermind instruction roles")
    if "syndicate_and_gang" in detected_categories:
        key_reasons.append("Organised criminal syndicate / gang activity")

    return {
        "tid": tid,
        "title": title,
        "court": court,
        "date": pdate,
        "text_length": text_length,
        "source_url": src_url,
        "query_used": query,
        "score": round(score, 2),
        "category_count": category_count,
        "detected_categories": list(detected_categories.keys()),
        "category_match_counts": detected_categories,
        "accused_identified": sorted(list(accused_matches))[:10],
        "reason_for_selection": " | ".join(key_reasons) if key_reasons else "Criminal proceedings",
        "file_name": fpath.name,
        "source_path": fpath,
    }


def curate_corpus(
    raw_dir: Path,
    curated_dir: Path,
    target_count: int = 25,
    min_score: float = 70.0,
) -> Dict[str, Any]:
    print("=" * 68)
    print("DEMO CORPUS CURATION PIPELINE — SIH26189GREEN")
    print("=" * 68)
    print(f"Source Raw Directory   : {raw_dir.resolve()}")
    print(f"Target Curated Dir     : {curated_dir.resolve()}")
    print(f"Target Selection Range : 20 - 30 cases (Default target: {target_count})\n")

    raw_files = sorted(raw_dir.glob("doc_*.json"))
    print(f"Total raw judgments to analyze: {len(raw_files)}")

    evaluated_docs: List[Dict[str, Any]] = []
    for rf in raw_files:
        res = analyze_document(rf)
        evaluated_docs.append(res)

    # Sort descending by network suitability score
    evaluated_docs.sort(key=lambda x: (x["score"], x["category_count"], x["text_length"]), reverse=True)

    # Filter by quality threshold
    strong_candidates = [d for d in evaluated_docs if d["score"] >= min_score]
    print(f"Candidates meeting quality threshold (score >= {min_score}): {len(strong_candidates)}")

    # Select between 20 and 30 cases (or 12-15 if genuinely fewer strong cases exist)
    if len(strong_candidates) >= 20:
        selected = strong_candidates[:min(target_count, 30)]
    elif len(strong_candidates) >= 12:
        print(f"Fewer than 20 cases met high threshold; selecting {len(strong_candidates)} genuinely strong cases.")
        selected = strong_candidates
    else:
        # Fallback to top candidates with at least 4 relationship categories
        selected = [d for d in evaluated_docs if d["category_count"] >= 4][:20]

    print(f"Selected final curated cases: {len(selected)}\n")

    # Clean and recreate data/curated/
    curated_dir.mkdir(parents=True, exist_ok=True)

    copied_count = 0
    curated_records: List[Dict[str, Any]] = []

    for rank, doc in enumerate(selected, 1):
        src_file = doc["source_path"]
        dest_file = curated_dir / doc["file_name"]

        # Copy original raw JSON without modifying judgment text
        shutil.copy2(src_file, dest_file)
        copied_count += 1

        curated_records.append({
            "rank": rank,
            "tid": doc["tid"],
            "title": doc["title"],
            "court": doc["court"],
            "date": doc["date"],
            "text_length": doc["text_length"],
            "score": doc["score"],
            "source_url": doc["source_url"],
            "query_used": doc["query_used"],
            "file_name": doc["file_name"],
            "reason_for_selection": doc["reason_for_selection"],
            "detected_relationship_categories": doc["detected_categories"],
            "accused_identified": doc["accused_identified"],
        })
        print(f"[{rank:02d}] Score: {doc['score']:5.1f} | Categories: {doc['category_count']}/8 | [{doc['tid']}] {doc['title'][:55]}...")

    # Write curated_manifest.json
    manifest_data = {
        "project": "SIH26189GREEN",
        "task": "Task 1.2 - Curated Demo Corpus",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_raw_analyzed": len(raw_files),
        "total_curated_selected": len(selected),
        "selection_criteria": (
            "Multi-dimensional network analysis scoring prioritizing co-accused identifiers, "
            "conspiracy charges (Section 120-B/34), telecommunication/CDR evidence, "
            "financial transactions/hawala, logistical support/shelter/weapons, and hierarchical command roles."
        ),
        "curated_documents": curated_records,
    }

    manifest_file = curated_dir / "curated_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as mf:
        json.dump(manifest_data, mf, indent=2, ensure_ascii=False)

    print("\n" + "=" * 68)
    print("CURATION SUMMARY")
    print("=" * 68)
    print(f"Raw documents analyzed : {len(raw_files)}")
    print(f"Curated files saved    : {copied_count} to {curated_dir.resolve()}")
    print(f"Manifest generated     : {manifest_file.resolve()}")
    print("=" * 68)

    return manifest_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Curate demo criminal network judgment corpus.")
    parser.add_argument(
        "--raw-dir",
        "-r",
        type=str,
        default=None,
        help="Path to raw data directory (default: data/raw)",
    )
    parser.add_argument(
        "--curated-dir",
        "-c",
        type=str,
        default=None,
        help="Path to curated data directory (default: data/curated)",
    )
    parser.add_argument(
        "--target",
        "-t",
        type=int,
        default=25,
        help="Target number of cases to curate (between 20 and 30, default: 25)",
    )
    args = parser.parse_args()

    repo_root = find_repo_root()
    raw_dir = Path(args.raw_dir) if args.raw_dir else repo_root / "data" / "raw"
    curated_dir = Path(args.curated_dir) if args.curated_dir else repo_root / "data" / "curated"

    curate_corpus(raw_dir=raw_dir, curated_dir=curated_dir, target_count=args.target)


if __name__ == "__main__":
    main()
