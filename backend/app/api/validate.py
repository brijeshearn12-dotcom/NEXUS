"""Validate router — placeholder. Implement on Day N."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_validate() -> dict:  # type: ignore[return]
    return {"message": "Validate endpoint — coming soon"}
