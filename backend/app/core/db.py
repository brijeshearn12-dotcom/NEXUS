"""
MongoDB database connection management using PyMongo.

Features:
- PyMongo client with connection pooling and timeouts
- Reads MONGODB_URI from environment via Settings
- Safe error handling: credentials and connection strings are NEVER logged or exposed
- Reusable client lifecycle
"""

from __future__ import annotations

import logging
from typing import Any

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError, ServerSelectionTimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)

DB_NAME = "nexus_criminal_network"
CONNECT_TIMEOUT_MS = 5000
SERVER_SELECTION_TIMEOUT_MS = 5000

_client: MongoClient[Any] | None = None


def get_mongo_client() -> MongoClient[Any]:
    """
    Return the reusable PyMongo client singleton.
    Initializes on first call with safe connection timeouts.
    """
    global _client
    if _client is None:
        if not settings.mongodb_uri:
            raise RuntimeError("MONGODB_URI is not configured in environment.")
        _client = MongoClient(
            settings.mongodb_uri,
            connectTimeoutMS=CONNECT_TIMEOUT_MS,
            serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
        )
    return _client


def test_db_connection() -> tuple[bool, str]:
    """
    Actively ping MongoDB Atlas to test connectivity and authentication.

    Returns:
        (True, "connected") if ping succeeded.
        (False, <safe_error_message>) if ping failed.
    Safe: No credentials or secret URIs are ever included in the returned message or logs.
    """
    if not settings.mongodb_uri:
        return False, "MONGODB_URI is not configured"

    try:
        client = get_mongo_client()
        # The admin 'ping' command forces server selection and authentication check
        response = client.admin.command("ping")
        if response.get("ok") == 1 or response.get("ok") == 1.0:
            return True, "connected"
        return False, "Database ping response was not ok"
    except (ServerSelectionTimeoutError, ConnectionFailure):
        logger.error("MongoDB Atlas connection timed out or failed to reach host.")
        return False, "Connection timed out"
    except PyMongoError:
        logger.error("MongoDB Atlas operation or authentication failed.")
        return False, "Authentication or operation failed"
    except Exception:
        logger.error("Unexpected error while testing MongoDB connection.")
        return False, "Database health check encountered an unexpected error"


COLLECTIONS = {
    "CASES": "cases",
    "DOCUMENTS": "documents",
    "ENTITIES": "entities",
    "EDGES": "edges",
    "FLAGS": "flags",
    "VALIDATION_RUNS": "validation_runs",
    "AUDIT_LOG": "audit_log",
}
ENTITY_MERGES_COLLECTION = "entity_merges"


def get_db(db_name: str = DB_NAME) -> Any:
    """Return a database instance from the reusable client."""
    client = get_mongo_client()
    return client[db_name]


def get_collection(name: str, db_name: str = DB_NAME) -> Any:
    """Return a collection handle from the configured database."""
    return get_db(db_name)[name]


def ensure_indexes(database: Any | None = None) -> dict[str, list[str]]:
    """
    Ensure required indexes exist across canonical NEXUS collections.

    Indexes:
    - cases: case_id
    - documents: case_id
    - entities: case_id
    - edges: case_id, source_entity_id, target_entity_id
    - flags: case_id
    - validation_runs: case_id
    - audit_log: case_id, timestamp

    Safe and idempotent: uses PyMongo create_index with background=True.
    Does NOT drop, purge, or overwrite any collections or documents.
    """
    db = database if database is not None else get_db()
    index_manifest: dict[str, list[str]] = {}

    try:
        idx_cases = db.cases.create_index("case_id", background=True)
        index_manifest["cases"] = [idx_cases]

        idx_doc = db.documents.create_index("case_id", background=True)
        index_manifest["documents"] = [idx_doc]

        idx_ent_case = db.entities.create_index("case_id", background=True)
        idx_ent_doc = db.entities.create_index("document_id", background=True)
        idx_ent_type = db.entities.create_index("entity_type", background=True)
        idx_ent_status = db.entities.create_index("verification_status", background=True)
        index_manifest["entities"] = [idx_ent_case, idx_ent_doc, idx_ent_type, idx_ent_status]

        idx_edge_case = db.edges.create_index("case_id", background=True)
        idx_edge_src = db.edges.create_index("source_entity_id", background=True)
        idx_edge_tgt = db.edges.create_index("target_entity_id", background=True)
        index_manifest["edges"] = [idx_edge_case, idx_edge_src, idx_edge_tgt]

        idx_flag = db.flags.create_index("case_id", background=True)
        index_manifest["flags"] = [idx_flag]

        idx_val = db.validation_runs.create_index("case_id", background=True)
        index_manifest["validation_runs"] = [idx_val]

        idx_audit_case = db.audit_log.create_index("case_id", background=True)
        idx_audit_time = db.audit_log.create_index("timestamp", background=True)
        index_manifest["audit_log"] = [idx_audit_case, idx_audit_time]

        if hasattr(db, "entity_merges"):
            idx_merge_case = db.entity_merges.create_index("case_id", background=True)
            idx_merge_canon = db.entity_merges.create_index("canonical_entity_id", background=True)
            idx_merge_alias = db.entity_merges.create_index("alias_entity_id", background=True)
            idx_merge_unique = db.entity_merges.create_index(
                [("case_id", 1), ("canonical_entity_id", 1), ("alias_entity_id", 1)],
                unique=True,
                background=True,
            )
            index_manifest["entity_merges"] = [
                idx_merge_case,
                idx_merge_canon,
                idx_merge_alias,
                idx_merge_unique,
            ]

        logger.info(
            "Canonical indexes verified on MongoDB database: %s", getattr(db, "name", "unknown")
        )
    except Exception as exc:
        logger.warning("Index verification encountered an issue: %s", exc)

    return index_manifest


def close_mongo_client() -> None:
    """Close the reusable PyMongo client on application shutdown."""
    global _client
    if _client is not None:
        try:
            _client.close()
            logger.info("MongoDB client connection closed cleanly.")
        except Exception as exc:
            logger.warning("Error closing MongoDB client: %s", type(exc).__name__)
        finally:
            _client = None


# Async lifespan helpers for FastAPI
async def connect() -> None:
    """Initialize client on application startup if configured and ensure indexes."""
    if settings.mongodb_uri:
        try:
            get_mongo_client()
            logger.info("MongoDB client initialized for database: %s", DB_NAME)
            ensure_indexes()
        except Exception:
            logger.error("Failed to initialize MongoDB client or indexes on startup.")


async def disconnect() -> None:
    """Close client on application shutdown."""
    close_mongo_client()
