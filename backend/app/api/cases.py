"""Cases router — placeholder. Implement on Day N."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_cases() -> dict:  # type: ignore[return]
    return {"message": "Cases endpoint — coming soon"}
