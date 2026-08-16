"""Explicit, owner-approved links between execution results and paper claims."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.storage import ClaimEvidenceLink, StorageProtocol, get_storage
from app.tenant import get_project_id

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


class LinkEvidenceRequest(BaseModel):
    document_id: str
    snapshot_id: str
    claim_id: str
    artifact_id: str


async def _owned_snapshot(document_id: str, snapshot_id: str, project_id: str, storage: StorageProtocol):
    document = await storage.get_document(document_id)
    if document is None or document.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found")
    snapshot = next((item for item in await storage.list_snapshots(document_id) if item.id == snapshot_id), None)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Verification snapshot not found")
    return snapshot


@router.post("")
async def link_execution_evidence(
    req: LinkEvidenceRequest,
    project_id: str = Depends(get_project_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Link one saved execution artifact to one claim in an immutable snapshot."""
    snapshot = await _owned_snapshot(req.document_id, req.snapshot_id, project_id, storage)
    if not any(item.get("claim_id") == req.claim_id for item in snapshot.verification_results):
        raise HTTPException(status_code=404, detail="Claim not found in verification snapshot")
    artifact = await storage.get_execution_artifact(req.artifact_id)
    if artifact is None or artifact.document_id != req.document_id:
        raise HTTPException(status_code=404, detail="Execution artifact not found")
    link = await storage.link_claim_evidence(
        ClaimEvidenceLink(
            snapshot_id=snapshot.id,
            claim_id=req.claim_id,
            artifact_id=artifact.id,
        )
    )
    return {
        "evidence": {
            "id": link.id,
            "snapshot_id": link.snapshot_id,
            "claim_id": link.claim_id,
            "artifact_id": link.artifact_id,
            "code_hash": artifact.code_hash,
            "exit_code": artifact.exit_code,
            "created_at": link.created_at,
        }
    }


@router.get("/{snapshot_id}")
async def list_evidence(
    snapshot_id: str,
    document_id: str,
    project_id: str = Depends(get_project_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """List linked execution evidence for an owned verification snapshot."""
    await _owned_snapshot(document_id, snapshot_id, project_id, storage)
    links = await storage.list_claim_evidence(snapshot_id)
    response = []
    for link in links:
        artifact = await storage.get_execution_artifact(link.artifact_id)
        if artifact is None:
            continue
        response.append(
            {
                "id": link.id,
                "claim_id": link.claim_id,
                "artifact_id": artifact.id,
                "code_hash": artifact.code_hash,
                "stdout": artifact.stdout,
                "stderr": artifact.stderr,
                "exit_code": artifact.exit_code,
                "created_at": link.created_at,
            }
        )
    return {"evidence": response}
