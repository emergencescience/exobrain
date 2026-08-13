"""Verification route — SymPy formal checking of LaTeX equations."""

import hashlib
import logging
import re

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
    claim_type: str = "equation"
    parent_claim_id: str | None = None
    edge_type: str | None = None
    assumption_claim_ids: list[str] = []
    crosses_paragraph: bool = False


def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    """Use the identity forwarded by the authenticated orchestrator."""
    return x_user_id or "local"


_ASSUMPTION_PATTERN = re.compile(
    r"^\s*(?:assumption|assume|given|假设|前提|已知)\s*[:：]\s*(.+)$",
    re.IGNORECASE,
)


def _claim_type(equation: str, detail: str, index: int) -> str:
    """Classify only evidence-backed relation types; unknown steps stay explicit."""
    normalized = f"{equation} {detail}".lower()
    if index == 0:
        return "definition"
    if "\\sum" in equation or "\\int" in equation or "telescop" in normalized or "求和" in detail:
        return "summation"
    if "derivative" in normalized or "求导" in detail or "'" in equation:
        return "differentiation"
    if "substitut" in normalized or "代入" in detail:
        return "substitution"
    if "expand" in normalized or "展开" in detail:
        return "expansion"
    if "\\implies" in equation or "\\therefore" in equation or "conclusion" in normalized:
        return "conclusion"
    return "algebraic_rewrite"


def _assumptions(markdown: str) -> list[tuple[int, str]]:
    return [
        (line_number, match.group(1).strip())
        for line_number, line in enumerate(markdown.splitlines(), start=1)
        if (match := _ASSUMPTION_PATTERN.match(line))
    ]


def _crosses_paragraph(markdown: str, earlier_end_line: int, later_line: int) -> bool:
    between = markdown.splitlines()[earlier_end_line:later_line - 1]
    return any(not line.strip() for line in between)


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
    raw_results = verify_document(req.markdown, req.locale)
    candidates: list[tuple[int, int, str, str, str, str]] = [
        (
            result.line,
            result.line + result.equation.count("\n"),
            result.equation,
            result.status,
            result.detail,
            _claim_type(result.equation, result.detail, index),
        )
        for index, result in enumerate(raw_results)
    ]
    candidates.extend(
        (
            line,
            line,
            text,
            "inconclusive",
            f"Assumption recorded for downstream verification: {text}",
            "assumption",
        )
        for line, text in _assumptions(req.markdown)
    )
    candidates.sort(key=lambda item: (item[0], item[5] != "assumption"))

    results = []
    active_assumptions: list[str] = []
    previous_claim_id: str | None = None
    previous_end_line = 0
    for line, end_line, equation, status, detail, claim_type in candidates:
        claim_id = hashlib.sha256(
            f"{content_hash}:{line}:{end_line}:{equation}".encode("utf-8")
        ).hexdigest()[:20]
        if claim_type == "assumption":
            active_assumptions.append(claim_id)
        results.append(
            VerifyResult(
                claim_id=claim_id,
                line=line,
                end_line=end_line,
                equation=equation,
                status=status,
                detail=detail,
                claim_type=claim_type,
                parent_claim_id=previous_claim_id,
                edge_type=None if claim_type in {"definition", "assumption"} else claim_type,
                assumption_claim_ids=[] if claim_type == "assumption" else active_assumptions.copy(),
                crosses_paragraph=bool(previous_claim_id)
                and _crosses_paragraph(req.markdown, previous_end_line, line),
            )
        )
        if claim_type != "assumption":
            previous_claim_id = claim_id
            previous_end_line = end_line

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
