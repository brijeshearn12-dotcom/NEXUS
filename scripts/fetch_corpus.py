#!/usr/bin/env python3
"""
fetch_corpus.py — Acquire real Indian criminal judgment corpus from Indian Kanoon API.

SIH26189GREEN | Criminal Network Analysis System
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests  # type: ignore[import-untyped]
from dotenv import load_dotenv  # type: ignore[import-untyped]

# Suppress harmless dependency version mismatch warnings from requests
warnings.filterwarnings("ignore")

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
TARGET_CRIMINAL_QUERIES: Dict[str, str] = {
    "criminal_conspiracy": '"criminal conspiracy" "Section 120B"',
    "ndps_narcotics": '"NDPS Act" "commercial quantity" conspiracy',
    "multiple_accused": '"multiple accused" "common intention" Section 34',
    "organised_crime": '"organised crime" syndicate OR gang',
    "economic_offences": '"economic offences" "criminal conspiracy" fraud OR forgery',
    "co_accused_networks": '"co-accused" "conspiracy" "active role"',
}

PRESET_QUERIES: Dict[str, str] = {
    "conspiracy": TARGET_CRIMINAL_QUERIES["criminal_conspiracy"],
    "ndps": TARGET_CRIMINAL_QUERIES["ndps_narcotics"],
    "multiple_accused": TARGET_CRIMINAL_QUERIES["multiple_accused"],
    "organised_crime": TARGET_CRIMINAL_QUERIES["organised_crime"],
    "economic": TARGET_CRIMINAL_QUERIES["economic_offences"],
    "networks": TARGET_CRIMINAL_QUERIES["co_accused_networks"],
}


class APIFatalError(Exception):
    """Raised when the API returns an unrecoverable error (e.g. 403 Forbidden or quota exhausted)."""
    pass


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

    def __init__(self, token: str, request_delay: float = 0.8, max_retries: int = 3, timeout: int = 25):
        self._token = token  # Never print, log, or export this
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = requests.Session()
        self.consecutive_errors = 0

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Token {self._token}",
            "Accept": "application/json",
            "User-Agent": "NEXUS-SIH26189-CorpusFetcher/1.0",
        }

    def _post(self, url: str, data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """POST request with retries, exponential backoff, and circuit breaker for fatal errors."""
        headers = self._get_headers()
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.post(url, data=data, headers=headers, timeout=self.timeout)
                if response.status_code == 200:
                    self.consecutive_errors = 0
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON response from {url}")
                        return None
                elif response.status_code == 403:
                    # Fatal authentication / quota error - stop immediately
                    logger.critical(
                        "Authentication failed or quota exhausted (HTTP 403). "
                        "Pausing immediately to avoid hammering the API."
                    )
                    raise APIFatalError("HTTP 403 Forbidden: Invalid token or API quota reached.")
                elif response.status_code == 429:
                    wait_time = (2 ** attempt) * 2
                    logger.warning(
                        f"Rate limited (HTTP 429). Backing off for {wait_time}s (attempt {attempt}/{self.max_retries})..."
                    )
                    time.sleep(wait_time)
                elif response.status_code in (500, 502, 503, 504):
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Server error (HTTP {response.status_code}). Retrying in {wait_time}s (attempt {attempt}/{self.max_retries})..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"HTTP {response.status_code} received from {url}")
                    return None
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout for {url} (attempt {attempt}/{self.max_retries})")
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error when calling {url}: {e.__class__.__name__}")
                time.sleep(2 ** attempt)

        self.consecutive_errors += 1
        if self.consecutive_errors >= 5:
            raise APIFatalError(f"Encountered {self.consecutive_errors} consecutive failures. Pausing to avoid hammering.")

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
    delay: float = 0.8,
    client: Optional[KanoonClient] = None,
) -> Dict[str, Any]:
    """
    Search and download judgments matching query up to limit.
    Avoids duplicate downloads, caches raw responses with provenance, and reports stats.
    """
    if raw_dir is None:
        raw_dir = find_repo_root() / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if client is None:
        token = get_api_token()
        client = KanoonClient(token=token, request_delay=delay)

    logger.info("=" * 65)
    logger.info(f"FETCH QUERY: {query} (Limit: {limit})")
    logger.info("=" * 65)

    stats: Dict[str, Any] = {
        "query": query,
        "found_on_kanoon": 0,
        "processed": 0,
        "downloaded": 0,
        "skipped_existing": 0,
        "failed": 0,
        "downloaded_ids": [],
        "skipped_ids": [],
        "failed_ids": [],
    }

    current_page = 0
    candidate_docs: List[Dict[str, Any]] = []

    # 1. Search phase
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

        logger.info(
            f"Page {current_page}: Received {len(docs)} search hits "
            f"(Total matches on Kanoon: {total_found_raw})"
        )
        for doc in docs:
            candidate_docs.append(doc)
            if len(candidate_docs) >= limit:
                break

        current_page += 1
        time.sleep(delay)

    if not candidate_docs:
        logger.warning(f"No candidate documents returned for query: {query}")
        return stats

    logger.info(f"Processing {len(candidate_docs)} judgment candidate(s)...")

    # 2. Document fetch phase
    for idx, doc_summary in enumerate(candidate_docs, 1):
        stats["processed"] += 1
        tid = doc_summary.get("tid")
        title = doc_summary.get("title", f"Doc_{tid}")
        docsource = doc_summary.get("docsource", "")
        publishdate = doc_summary.get("publishdate", "")

        if not tid:
            logger.warning(f"[{idx}/{len(candidate_docs)}] Missing tid, skipping.")
            stats["failed"] += 1
            continue

        doc_file = raw_dir / f"doc_{tid}.json"

        # Check for existing download (avoid duplicate)
        if doc_file.exists():
            logger.info(f"[{idx}/{len(candidate_docs)}] SKIPPED (Already cached): [{tid}] {title[:55]}...")
            stats["skipped_existing"] += 1
            stats["skipped_ids"].append(tid)
            continue

        logger.info(f"[{idx}/{len(candidate_docs)}] DOWNLOADING: [{tid}] {title[:55]}...")
        doc_data = client.get_document(doc_id=tid)

        if not doc_data:
            logger.error(f"[{idx}/{len(candidate_docs)}] FAILED to download doc [{tid}].")
            stats["failed"] += 1
            stats["failed_ids"].append(tid)
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
            stats["downloaded_ids"].append(tid)
            logger.info(f"[{idx}/{len(candidate_docs)}] SAVED -> {doc_file.name}")
        except Exception as e:
            logger.error(f"[{idx}/{len(candidate_docs)}] Failed to write file {doc_file}: {e}")
            stats["failed"] += 1
            stats["failed_ids"].append(tid)

        time.sleep(delay)

    logger.info(
        f"Query complete: {stats['downloaded']} downloaded, "
        f"{stats['skipped_existing']} skipped, {stats['failed']} failed."
    )
    return stats


def run_bulk_acquisition(
    limit_per_query: int = 35,
    delay: float = 0.8,
    raw_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Execute bulk corpus acquisition across all target criminal law queries.
    Saves a machine-readable manifest at data/raw/corpus_manifest.json.
    """
    if raw_dir is None:
        raw_dir = find_repo_root() / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    token = get_api_token()
    client = KanoonClient(token=token, request_delay=delay)

    start_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    logger.info("=" * 65)
    logger.info("STARTING BULK INDIAN CRIMINAL JUDGMENT CORPUS ACQUISITION")
    logger.info(f"Target categories: {len(TARGET_CRIMINAL_QUERIES)}")
    logger.info(f"Limit per category: {limit_per_query}")
    logger.info(f"Target total: {len(TARGET_CRIMINAL_QUERIES) * limit_per_query} documents")
    logger.info("=" * 65)

    all_query_stats: List[Dict[str, Any]] = []
    total_downloaded = 0
    total_skipped = 0
    total_failed = 0

    try:
        for category_name, query_str in TARGET_CRIMINAL_QUERIES.items():
            logger.info(f"\n>>> Running Category: [{category_name}] <<<")
            q_stats = fetch_corpus(
                query=query_str,
                limit=limit_per_query,
                raw_dir=raw_dir,
                delay=delay,
                client=client,
            )
            q_stats["category"] = category_name
            all_query_stats.append(q_stats)

            total_downloaded += q_stats["downloaded"]
            total_skipped += q_stats["skipped_existing"]
            total_failed += q_stats["failed"]

    except APIFatalError as fatal_err:
        logger.critical(f"Bulk acquisition halted due to fatal API condition: {fatal_err}")
    except KeyboardInterrupt:
        logger.warning("Bulk acquisition interrupted by user. Generating partial manifest...")

    end_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Discover all unique documents currently cached in data/raw
    all_doc_files = list(raw_dir.glob("doc_*.json"))
    unique_tids: List[int] = []
    for df in all_doc_files:
        try:
            tid_match = re.search(r"doc_(\d+)\.json", df.name)
            if tid_match:
                unique_tids.append(int(tid_match.group(1)))
        except Exception:
            pass

    manifest = {
        "project": "SIH26189GREEN",
        "task": "Task 1.1 - Corpus Acquisition",
        "source": "Indian Kanoon API (api.indiankanoon.org)",
        "acquisition_started_at": start_time,
        "acquisition_completed_at": end_time,
        "total_documents_downloaded_this_run": total_downloaded,
        "total_documents_skipped_this_run": total_skipped,
        "total_requests_failed_this_run": total_failed,
        "total_unique_documents_cached": len(all_doc_files),
        "queries_used": [
            {
                "category": s.get("category", ""),
                "query": s["query"],
                "total_matching_on_kanoon": s["found_on_kanoon"],
                "downloaded": s["downloaded"],
                "skipped": s["skipped_existing"],
                "failed": s["failed"],
            }
            for s in all_query_stats
        ],
        "cached_document_ids": sorted(unique_tids),
        "raw_cache_directory": str(raw_dir.resolve()),
    }

    manifest_file = raw_dir / "corpus_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2, ensure_ascii=False)

    logger.info("\n" + "=" * 65)
    logger.info("BULK ACQUISITION SUMMARY REPORT")
    logger.info("=" * 65)
    logger.info(f"Total downloaded in this run : {total_downloaded}")
    logger.info(f"Total skipped (pre-cached)   : {total_skipped}")
    logger.info(f"Total failures               : {total_failed}")
    logger.info(f"Total unique cached docs now : {len(all_doc_files)}")
    logger.info(f"Manifest written to          : {manifest_file}")
    logger.info("=" * 65)

    return manifest


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
        help="Maximum number of judgments to download for a single query (default: 5)",
    )
    parser.add_argument(
        "--bulk",
        action="store_true",
        help="Run bulk acquisition across all 6 target criminal categories to reach 150-300 judgments",
    )
    parser.add_argument(
        "--limit-per-query",
        type=int,
        default=35,
        help="Number of judgments to download per category when --bulk is active (default: 35)",
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
        default=0.8,
        help="Polite delay in seconds between requests to respect rate limits (default: 0.8)",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run a minimal test query (limit 1) to verify API token authentication and connectivity",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else None

    if args.bulk:
        run_bulk_acquisition(
            limit_per_query=args.limit_per_query,
            delay=args.delay,
            raw_dir=output_dir,
        )
        return

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

    fetch_corpus(query=query, limit=limit, raw_dir=output_dir, delay=args.delay)


if __name__ == "__main__":
    main()
