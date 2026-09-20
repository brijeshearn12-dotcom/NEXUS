"""Report router — placeholder. Implement on Day N."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_report() -> dict:  # type: ignore[return]
    return {"message": "Report endpoint — coming soon"}
