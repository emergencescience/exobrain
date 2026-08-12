"""Verification route — SymPy formal checking of LaTeX equations."""

import hashlib
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.config import config
from app.storage import StorageProtocol, get_storage
from app.verify import verify_document

logger = logging.getLogger("exobrain.verify")
router = APIRouter(prefix="/api", tags=["verify"])


class VerifyRequest(BaseModel):
    markdown: str
    locale: str = "en"
    document_id: str | None = None


class VerifyResult(BaseModel):
    claim_id: str
    line: int
    end_line: int
    equation: str
    status: str   # verified | inconclusive | error
    detail: str


def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    """Use the identity forwarded by the authenticated orchestrator."""
    return x_user_id or "local"


@router.post("/verify")
async def verify(
    req: VerifyRequest,
    user_id: str = Depends(get_user_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Verify equations and preserve a reproducible source snapshot when saved."""
    if not req.markdown.strip():
        return {"results": [], "snapshot": None}
    if len(req.markdown) > config.max_document_chars:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Document exceeds the {config.max_document_chars:,}-character V1 limit. "
                "Split it into a smaller document before verifying."
            ),
        )

    document = None
    if req.document_id:
        document = await storage.get_document(req.document_id)
        if document is None or document.user_id != user_id:
            raise HTTPException(status_code=404, detail="Document not found")

    content_hash = hashlib.sha256(req.markdown.encode("utf-8")).hexdigest()
    results = []
    for result in verify_document(req.markdown, req.locale):
        end_line = result.line + result.equation.count("\n")
        claim_id = hashlib.sha256(
            f"{content_hash}:{result.line}:{end_line}:{result.equation}".encode("utf-8")
        ).hexdigest()[:20]
        results.append(
            VerifyResult(
                claim_id=claim_id,
                line=result.line,
                end_line=end_line,
                equation=result.equation,
                status=result.status,
                detail=result.detail,
            )
        )

    snapshot = None
    if document is not None:
        snapshot = await storage.save_snapshot(
            document.id,
            req.markdown,
            document.messages,
            content_hash=content_hash,
            verification_results=[result.model_dump() for result in results],
        )

    return {
        "results": [result.model_dump() for result in results],
        "snapshot": snapshot.to_dict() if snapshot else None,
    }
