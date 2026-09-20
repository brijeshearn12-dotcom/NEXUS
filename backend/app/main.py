"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import connect, disconnect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting up %s", settings.app_name)
    # NOTE: connect() is a no-op if MONGODB_URI is empty.
    # Day 1: set MONGODB_URI in /.env and restart.
    await connect()
    yield
    await disconnect()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI-Powered Criminal Network Analysis System — SIH26189GREEN",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", settings.next_public_api_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Liveness check — always returns 200 OK."""
    return {"status": "ok"}


# ── Route modules (stubs — will be fleshed out on their respective days) ──────
from app.api import corpus, cases, documents, entities, validate, report  # noqa: E402

app.include_router(corpus.router, prefix="/corpus", tags=["Corpus"])
app.include_router(cases.router, prefix="/cases", tags=["Cases"])
app.include_router(documents.router, prefix="/documents", tags=["Documents"])
app.include_router(entities.router, prefix="/entities", tags=["Entities"])
app.include_router(validate.router, prefix="/validate", tags=["Validation"])
app.include_router(report.router, prefix="/report", tags=["Report"])
