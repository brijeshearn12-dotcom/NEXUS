#!/usr/bin/env python3
"""
fetch_corpus.py — Acquire real Indian criminal judgment corpus from Indian Kanoon API.

SIH26189GREEN | Criminal Network Analysis System
"""
from __future__ import annotations

import warnings
# Suppress dependency warning before importing requests
warnings.filterwarnings("ignore")

import argparse
import datetime
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests  # type: ignore[import-untyped]
from dotenv import load_dotenv  # type: ignore[import-untyped]

# Configure logging without leaking secrets
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("fetch_corpus")

# Base URL according to official documentation
IK_BASE_URL = "https://api.indiankanoon.org"
SEARCH_ENDPOINT = f"{IK_BASE_URL}/search/"
DOC_ENDPOINT_TEMPLATE = f"{IK_BASE_URL}/doc/{{doc_id}}/"

# Predefined criminal query presets relevant to SIH26189GREEN track
PRESET_QUERIES: Dict[str, str] = {
    "conspiracy": '"criminal conspiracy" multiple accused',
    "ndps": '"NDPS Act" commercial quantity conspiracy',
    "multiple_accused": '"multiple accused" Section 120B IPC',
    "organised_crime": '"organised crime" OR "economic offences" conspiracy',
}


def find_repo_root() -> Path:
    """Locate the repository root directory."""
    current = Path(__file__).resolve().parent
    while current.parent != current:
        if (current / ".git").exists() or (current / ".env.example").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent


def get_api_token() -> str:
    """
    Read the API token ONLY from the INDIAN_KANOON_API_TOKEN environment variable.
    Loads from .env if present, but never reads any other token variable name.
    """
    repo_root = find_repo_root()
    env_file = repo_root / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)

    token = os.environ.get("INDIAN_KANOON_API_TOKEN", "").strip()
    if not token:
        logger.error(
            "INDIAN_KANOON_API_TOKEN is not set. "
            "Please configure INDIAN_KANOON_API_TOKEN in your environment or root .env file."
        )
        sys.exit(1)
    return token


class KanoonClient:
    """Safe HTTP client for the official Indian Kanoon API."""

    def __init__(self, token: str, request_delay: float = 1.0, max_retries: int = 3, timeout: int = 25):
        self._token = token  # Never print, log, or export this
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Token {self._token}",
            "Accept": "application/json",
            "User-Agent": "NEXUS-SIH26189-CorpusFetcher/1.0",
        }

    def _post(self, url: str, data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """POST request with retries, exponential backoff, and safe error handling."""
        headers = self._get_headers()
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.post(url, data=data, headers=headers, timeout=self.timeout)
                if response.status_code == 200:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON response from {url}")
                        return None
                elif response.status_code == 403:
                    logger.error("Authentication failed (HTTP 403): Invalid or inactive INDIAN_KANOON_API_TOKEN.")
                    return None
                elif response.status_code == 429:
                    wait_time = (2 ** attempt) * 2
                    logger.warning(f"Rate limited (HTTP 429). Backing off for {wait_time}s (attempt {attempt}/{self.max_retries})...")
                    time.sleep(wait_time)
                elif response.status_code in (500, 502, 503, 504):
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error (HTTP {response.status_code}). Retrying in {wait_time}s (attempt {attempt}/{self.max_retries})...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"HTTP {response.status_code} received from {url}: {response.text[:200]}")
                    return None
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout for {url} (attempt {attempt}/{self.max_retries})")
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error when calling {url}: {e.__class__.__name__}")
                time.sleep(2 ** attempt)

        logger.error(f"Failed after {self.max_retries} attempts for {url}")
        return None

    def search(self, query: str, pagenum: int = 0) -> Optional[Dict[str, Any]]:
        """
        Search judgments matching query.
        Endpoint: POST https://api.indiankanoon.org/search/
        Parameters: formInput=<query>, pagenum=<pagenum>
        """
        data = {
            "formInput": query,
            "pagenum": pagenum,
        }
        return self._post(SEARCH_ENDPOINT, data=data)

    def get_document(self, doc_id: str | int) -> Optional[Dict[str, Any]]:
        """
        Fetch full judgment text and metadata.
        Endpoint: POST https://api.indiankanoon.org/doc/<doc_id>/
        """
        url = DOC_ENDPOINT_TEMPLATE.format(doc_id=doc_id)
        return self._post(url)


def update_raw_index(raw_dir: Path, entry: Dict[str, Any]) -> None:
    """Maintain an index file of all cached judgments in data/raw/index.json."""
    index_file = raw_dir / "index.json"
    index_data: Dict[str, Any] = {}
    if index_file.exists():
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                index_data = json.load(f)
        except Exception:
            index_data = {}

    doc_id_str = str(entry["tid"])
    index_data[doc_id_str] = {
        "tid": entry["tid"],
        "title": entry.get("title", ""),
        "docsource": entry.get("docsource", ""),
        "publishdate": entry.get("publishdate", ""),
        "source_url": entry.get("source_url", ""),
        "query_used": entry.get("query_used", ""),
        "fetched_at": entry.get("fetched_at", ""),
        "file_name": f"doc_{entry['tid']}.json",
    }

    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)


def fetch_corpus(
    query: str,
    limit: int = 5,
    raw_dir: Optional[Path] = None,
    delay: float = 1.0,
) -> Dict[str, int]:
    """
    Search and download judgments matching query up to limit.
    Avoids duplicate downloads, caches raw responses with provenance, and reports stats.
    """
    if raw_dir is None:
        raw_dir = find_repo_root() / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    token = get_api_token()
    client = KanoonClient(token=token, request_delay=delay)

    logger.info("=" * 65)
    logger.info("INDIAN KANOON CORPUS FETCHER — SIH26189GREEN")
    logger.info("=" * 65)
    logger.info(f"Target Query: {query}")
    logger.info(f"Document Limit: {limit}")
    logger.info(f"Output Directory: {raw_dir}")

    stats = {
        "found_on_kanoon": 0,
        "processed": 0,
        "downloaded": 0,
        "skipped_existing": 0,
        "failed": 0,
    }

    current_page = 0
    candidate_docs: List[Dict[str, Any]] = []

    # 1. Search phase
    logger.info("Step 1: Querying Indian Kanoon Search API...")
    while len(candidate_docs) < limit:
        search_result = client.search(query=query, pagenum=current_page)
        if not search_result:
            logger.error("Failed to retrieve search results.")
            break

        total_found_raw = search_result.get("found", 0)
        found_num = 0
        if isinstance(total_found_raw, int):
            found_num = total_found_raw
        elif isinstance(total_found_raw, str):
            match = re.search(r"of\s+([0-9]+)", total_found_raw)
            if match:
                found_num = int(match.group(1))
            else:
                digits = re.findall(r"\d+", total_found_raw)
                if digits:
                    found_num = int(digits[-1])
        stats["found_on_kanoon"] = found_num

        docs = search_result.get("docs", [])
        if not docs:
            logger.info(f"No further documents returned on page {current_page}.")
            break

        logger.info(f"Page {current_page}: Found {len(docs)} search result(s) (Total matching on Kanoon: {total_found_raw})")
        for doc in docs:
            candidate_docs.append(doc)
            if len(candidate_docs) >= limit:
                break

        current_page += 1
        time.sleep(delay)

    if not candidate_docs:
        logger.warning("No candidate documents found matching the search criteria.")
        return stats

    logger.info(f"\nStep 2: Processing {len(candidate_docs)} judgment candidate(s)...")

    # 2. Document fetch phase
    for idx, doc_summary in enumerate(candidate_docs, 1):
        stats["processed"] += 1
        tid = doc_summary.get("tid")
        title = doc_summary.get("title", f"Doc_{tid}")
        docsource = doc_summary.get("docsource", "")
        publishdate = doc_summary.get("publishdate", "")

        if not tid:
            logger.warning(f"[{idx}/{len(candidate_docs)}] Missing tid in result, skipping.")
            stats["failed"] += 1
            continue

        doc_file = raw_dir / f"doc_{tid}.json"

        # Check for existing download (avoid duplicate)
        if doc_file.exists():
            logger.info(f"[{idx}/{len(candidate_docs)}] SKIPPED (Already cached): [{tid}] {title[:60]}...")
            stats["skipped_existing"] += 1
            continue

        logger.info(f"[{idx}/{len(candidate_docs)}] DOWNLOADING: [{tid}] {title[:60]}...")
        doc_data = client.get_document(doc_id=tid)

        if not doc_data:
            logger.error(f"[{idx}/{len(candidate_docs)}] FAILED to download doc [{tid}].")
            stats["failed"] += 1
            time.sleep(delay)
            continue

        # Build provenance record
        provenance_record = {
            "tid": tid,
            "title": doc_data.get("title") or title,
            "docsource": doc_data.get("docsource") or docsource,
            "publishdate": doc_data.get("publishdate") or publishdate,
            "source_url": f"https://indiankanoon.org/doc/{tid}/",
            "query_used": query,
            "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "raw_api_response": doc_data,
        }

        try:
            with open(doc_file, "w", encoding="utf-8") as f:
                json.dump(provenance_record, f, indent=2, ensure_ascii=False)

            update_raw_index(raw_dir, provenance_record)
            stats["downloaded"] += 1
            logger.info(f"[{idx}/{len(candidate_docs)}] SAVED -> {doc_file.name}")
        except Exception as e:
            logger.error(f"[{idx}/{len(candidate_docs)}] Failed to write file {doc_file}: {e}")
            stats["failed"] += 1

        time.sleep(delay)

    # 3. Final Summary Report
    logger.info("\n" + "=" * 65)
    logger.info("CORPUS FETCH SUMMARY")
    logger.info("=" * 65)
    logger.info(f"Query executed          : {query}")
    logger.info(f"Total matching on Kanoon: {stats['found_on_kanoon']}")
    logger.info(f"Candidates processed    : {stats['processed']}")
    logger.info(f"Successfully downloaded : {stats['downloaded']}")
    logger.info(f"Skipped (already cached): {stats['skipped_existing']}")
    logger.info(f"Failed                  : {stats['failed']}")
    logger.info(f"Raw cache directory     : {raw_dir}")
    logger.info("=" * 65)

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Acquire Indian criminal judgment corpus from Indian Kanoon API for SIH26189GREEN."
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        default=None,
        help="Custom search query (e.g. '\"criminal conspiracy\" multiple accused')",
    )
    parser.add_argument(
        "--preset",
        "-p",
        type=str,
        choices=list(PRESET_QUERIES.keys()),
        default="conspiracy",
        help=(
            "Preset query choice: "
            "'conspiracy' (criminal conspiracy), "
            "'ndps' (NDPS Act), "
            "'multiple_accused' (multiple accused S.120B), "
            "'organised_crime' (organised/economic offences)"
        ),
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=5,
        help="Maximum number of judgments to download (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Path to output directory (default: data/raw)",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=1.0,
        help="Polite delay in seconds between requests to respect rate limits (default: 1.0)",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run a minimal test query (limit 1) to verify API token authentication and connectivity",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.smoke_test:
        logger.info("Starting smoke test (testing API authentication with 1 document)...")
        query = PRESET_QUERIES["conspiracy"]
        limit = 1
    elif args.query:
        query = args.query.strip()
        limit = args.limit
    else:
        query = PRESET_QUERIES[args.preset]
        limit = args.limit

    output_dir = Path(args.output_dir) if args.output_dir else None
    fetch_corpus(query=query, limit=limit, raw_dir=output_dir, delay=args.delay)


if __name__ == "__main__":
    main()
