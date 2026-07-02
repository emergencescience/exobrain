"""Verification route — SymPy formal checking of LaTeX equations."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.verify import verify_document

logger = logging.getLogger("exobrain.verify")
router = APIRouter(prefix="/api", tags=["verify"])


class VerifyRequest(BaseModel):
    markdown: str


class VerifyResult(BaseModel):
    line: int
    equation: str
    status: str   # verified | inconclusive | error
    detail: str


@router.post("/verify", response_model=list[VerifyResult])
async def verify(req: VerifyRequest):
    """Verify all LaTeX equations in a document."""
    if not req.markdown.strip():
        return []

    results = verify_document(req.markdown)
    return [
        VerifyResult(line=r.line, equation=r.equation, status=r.status, detail=r.detail)
        for r in results
    ]
