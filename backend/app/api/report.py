"""Report router for NEXUS.

Provides endpoints to generate and download comprehensive PDF investigation dossiers.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status

from app.core.db import get_db
from app.services.report_generator import generate_case_pdf_report

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{case_id}",
    summary="Download Investigation Dossier PDF",
    response_class=Response,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/{case_id}",
    summary="Generate and Download Investigation Dossier PDF",
    response_class=Response,
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/{case_id}/pdf",
    summary="Download Investigation Dossier PDF",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def get_case_report_pdf(case_id: str) -> Response:
    """Generate and return a professional Law Enforcement Investigation Dossier in PDF format."""
    db = get_db()
    case = db.cases.find_one({"case_id": case_id}) or db.cases.find_one({"id": case_id})
    has_entities = db.entities.find_one({"case_id": case_id}) is not None

    if not case and not has_entities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    try:
        pdf_bytes = generate_case_pdf_report(case_id=case_id, database=db)
        filename = f"NEXUS_Investigation_Dossier_{case_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "application/pdf",
                "X-Report-Case-ID": case_id,
            },
        )
    except Exception as err:
        logger.error("Failed to generate PDF report for case %s: %s", case_id, err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF report: {str(err)}",
        ) from err
