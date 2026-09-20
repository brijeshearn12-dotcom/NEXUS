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


def get_db(db_name: str = DB_NAME) -> Any:
    """Return a database instance from the reusable client."""
    client = get_mongo_client()
    return client[db_name]


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
    """Initialize client on application startup if configured."""
    if settings.mongodb_uri:
        try:
            get_mongo_client()
            logger.info("MongoDB client initialized for database: %s", DB_NAME)
        except Exception:
            logger.error("Failed to initialize MongoDB client on startup.")


async def disconnect() -> None:
    """Close client on application shutdown."""
    close_mongo_client()
