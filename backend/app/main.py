"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.db import connect, disconnect, test_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting up %s", settings.app_name)
    await connect()
    yield
    await disconnect()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI-Powered Criminal Network Analysis System — SIH26189GREEN",
    lifespan=lifespan,
)

cors_origins = settings.allowed_cors_origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Liveness check — always returns 200 OK."""
    return {"status": "ok"}


@app.get("/health/db", tags=["System"])
async def health_db_check() -> JSONResponse:
    """Database connectivity check — tests MongoDB Atlas via PyMongo ping."""
    ok, message = test_db_connection()
    if not ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "message": message},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ok", "database": message},
    )


# ── Route modules (stubs — will be fleshed out on their respective days) ──────
from app.api import cases, corpus, documents, entities, report, validate  # noqa: E402

# Mount primary /api endpoints as specified in Task 2.2
app.include_router(corpus.router, prefix="/api/corpus", tags=["Corpus"])
app.include_router(cases.router, prefix="/api/cases", tags=["Cases"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(entities.router, prefix="/api/entities", tags=["Entities"])
app.include_router(validate.router, prefix="/api/validate", tags=["Validation"])
app.include_router(report.router, prefix="/api/report", tags=["Report"])

# Also mount under non-/api prefix for backward compatibility with frontend / existing routes
app.include_router(corpus.router, prefix="/corpus", tags=["Corpus"], include_in_schema=False)
app.include_router(cases.router, prefix="/cases", tags=["Cases"], include_in_schema=False)
app.include_router(
    documents.router, prefix="/documents", tags=["Documents"], include_in_schema=False
)
app.include_router(entities.router, prefix="/entities", tags=["Entities"], include_in_schema=False)
app.include_router(
    validate.router, prefix="/validate", tags=["Validation"], include_in_schema=False
)
app.include_router(report.router, prefix="/report", tags=["Report"], include_in_schema=False)


if __name__ == "__main__":
    import os

    import uvicorn

    server_port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=server_port, reload=False)
