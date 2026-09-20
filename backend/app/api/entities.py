"""Entities router — placeholder. Implement on Day N."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_entities() -> dict:  # type: ignore[return]
    return {"message": "Entities endpoint — coming soon"}
