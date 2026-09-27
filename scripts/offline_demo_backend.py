"""offline_demo_backend.py — Task 9.2 fallback: run the real NEXUS API fully offline on a laptop.

Use when the venue network or the hosted backend is unavailable. Everything shown comes from
real computation on the committed curated corpus (data/curated) — nothing is canned:

  * in-memory MongoDB (mongomock) seeded with the curated Indian Kanoon judgments;
  * the existing pipeline (extract -> resolve -> build-graph) runs for the demo cases before
    the server starts, rule-based only (no LLM keys are read);
  * outbound network is blocked by default, proving zero live-API dependency;
  * the production database is never contacted (MONGODB_URI is ignored).

Usage (from the repository root, backend virtualenv active):
    python scripts/offline_demo_backend.py                 # demo cases, port 8765
    python scripts/offline_demo_backend.py --all           # all 20 curated cases (slower)
    python scripts/offline_demo_backend.py --cases case_100478559 --port 8765

Then run the frontend against it (Next.js reads NEXT_PUBLIC_API_URL from the shell):
    cd frontend
    NEXT_PUBLIC_API_URL=http://127.0.0.1:8765 npm run dev        # PowerShell: $env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8765"; npm run dev

State lives in memory only: restarting the script resets analyst decisions and audit entries.
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import time
import warnings
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ["case_100478559", "case_141720225", "case_31981506", "case_152095124"]

_BLOCKED: list[str] = []


def _block_outbound_network() -> None:
    """Allow loopback only; any other connection attempt fails immediately and is recorded."""
    real_connect, real_getaddrinfo = socket.socket.connect, socket.getaddrinfo
    local = ("127.0.0.1", "::1", "localhost")

    def guarded_connect(self: socket.socket, address):  # type: ignore[no-untyped-def]
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in local:
            _BLOCKED.append(host)
            raise OSError(f"offline demo: outbound connection to {host} blocked")
        return real_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):  # type: ignore[no-untyped-def]
        if host not in (*local, None):
            _BLOCKED.append(str(host))
            raise socket.gaierror(f"offline demo: DNS lookup for {host} blocked")
        return real_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    socket.getaddrinfo = guarded_getaddrinfo  # type: ignore[assignment]


class _InMemoryClient:
    """Pins every database lookup made through app.core.db to one in-memory database."""

    def __init__(self, client, name: str) -> None:  # type: ignore[no-untyped-def]
        self._client, self._name = client, name

    def __getitem__(self, _requested: str):  # type: ignore[no-untyped-def]
        return self._client[self._name]

    def get_database(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self._client[self._name]

    def __getattr__(self, attr: str):  # type: ignore[no-untyped-def]
        return getattr(self._client, attr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the NEXUS API offline on an in-memory database.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--cases", nargs="*", default=DEFAULT_CASES, help="case IDs to precompute")
    parser.add_argument("--all", action="store_true", help="precompute all curated cases")
    parser.add_argument("--allow-network", action="store_true", help="do not block outbound connections")
    args = parser.parse_args()

    os.chdir(REPO)  # the corpus loader resolves data/curated from the repository root
    sys.path.insert(0, str(REPO / "backend"))
    warnings.filterwarnings("ignore")
    for key in ("MONGODB_URI", "GEMINI_API_KEY", "GROQ_API_KEY", "INDIAN_KANOON_API_TOKEN", "INDIAN_KANOON_API_KEY"):
        os.environ.pop(key, None)
    if not args.allow_network:
        _block_outbound_network()

    try:
        import mongomock
    except ImportError:
        print("mongomock is required: pip install -r backend/requirements.txt", file=sys.stderr)
        return 2

    from app.core import db as core_db

    core_db._client = _InMemoryClient(mongomock.MongoClient(), "nexus_offline_demo")
    core_db.test_db_connection = lambda: (True, "connected (offline in-memory demo database)")

    from app.services.corpus_service import load_curated_corpus
    from app.services.extraction.service import extract_and_store_document
    from app.services.graph.builder import build_graph_for_case
    from app.services.resolution.alias_resolver import resolve_case_aliases

    logging.disable(logging.INFO)
    db = core_db.get_db()
    started = time.perf_counter()
    loaded = load_curated_corpus()
    cases = sorted({d["case_id"] for d in db.documents.find({}, {"case_id": 1})}) if args.all else args.cases
    print(f"Loaded {loaded.get('total', loaded.get('inserted', '?'))} curated judgments into the in-memory database.")
    for case_id in cases:
        docs = [d["id"] for d in db.documents.find({"case_id": case_id}, {"id": 1})]
        if not docs:
            print(f"  ! {case_id}: not in the curated corpus - skipped")
            continue
        for doc_id in docs:
            extract_and_store_document(doc_id, enable_gemini_fallback=False)
        resolve_case_aliases(case_id=case_id, database=db)
        graph = build_graph_for_case(case_id=case_id, database=db)
        print(f"  {case_id}: {graph.get('nodes')} nodes, {graph.get('edges_created')} edges")
    logging.disable(logging.NOTSET)

    network = "allowed" if args.allow_network else f"blocked ({len(_BLOCKED)} outbound attempts so far)"
    print(
        f"\nOFFLINE DEMO BACKEND ready in {time.perf_counter() - started:.0f}s - http://{args.host}:{args.port}\n"
        f"  data: curated corpus in memory (not production) | LLM: disabled | outbound network: {network}\n"
        f"  frontend: NEXT_PUBLIC_API_URL=http://{args.host}:{args.port} npm run dev   (inside frontend/)\n",
        flush=True,
    )

    import uvicorn

    from app.main import app

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
