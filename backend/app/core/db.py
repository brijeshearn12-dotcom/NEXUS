"""
MongoDB async client placeholder.
Do NOT call connect() here — that is a manual Day 1 step.
Run: await connect() after verifying MONGODB_URI in .env
"""
from __future__ import annotations

import logging
from typing import Optional

import motor.motor_asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None  # type: ignore[type-arg]
_db: Optional[motor.motor_asyncio.AsyncIOMotorDatabase] = None  # type: ignore[type-arg]

DB_NAME = "nexus_criminal_network"


async def connect() -> None:
    """Call this on application startup (after verifying MONGODB_URI)."""
    global _client, _db
    if not settings.mongodb_uri:
        logger.warning("MONGODB_URI not set — running without database connection.")
        return
    _client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongodb_uri)
    _db = _client[DB_NAME]
    logger.info("Connected to MongoDB: %s / %s", settings.mongodb_uri[:30], DB_NAME)


async def disconnect() -> None:
    """Call this on application shutdown."""
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed.")


def get_db() -> motor.motor_asyncio.AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Return the active database handle. Raises if not connected."""
    if _db is None:
        raise RuntimeError("Database not connected. Call connect() first.")
    return _db
