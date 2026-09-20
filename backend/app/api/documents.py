"""Documents router — placeholder. Implement on Day N."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_documents() -> dict:  # type: ignore[return]
    return {"message": "Documents endpoint — coming soon"}
