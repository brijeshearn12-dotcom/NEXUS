"""Corpus router — placeholder. Implement on Day N."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_corpus() -> dict:  # type: ignore[return]
    return {"message": "Corpus endpoint — coming soon"}
