"""Document CRUD routes — files inside a project."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import config
from app.storage import StorageProtocol, get_storage
from app.tenant import get_project_id

logger = logging.getLogger("exobrain.documents")
router = APIRouter(prefix="/api/documents", tags=["documents"])


class CreateDocumentRequest(BaseModel):
    title: str = "Untitled Paper"


class UpdateDocumentRequest(BaseModel):
    markdown: str | None = None
    messages: list[dict] | None = None
    title: str | None = None


@router.get("")
async def list_documents(
    project_id: str = Depends(get_project_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """List all documents in the current project."""
    docs = await storage.list_documents(project_id)
    return {"documents": [d.to_dict() for d in docs]}


@router.post("")
async def create_document(
    req: CreateDocumentRequest,
    project_id: str = Depends(get_project_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Create a new document in the current project."""
    doc = await storage.create_document(project_id, title=req.title)
    return {"document": doc.to_dict()}


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    project_id: str = Depends(get_project_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Get a document by ID with full messages (project-only)."""
    doc = await storage.get_document(doc_id)
    if doc is None or doc.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document": doc.to_dict()}


@router.patch("/{doc_id}")
async def update_document(
    doc_id: str,
    req: UpdateDocumentRequest,
    project_id: str = Depends(get_project_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Update document markdown, messages and/or title (project-only, partial)."""
    existing = await storage.get_document(doc_id)
    if existing is None or existing.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found")
    markdown = req.markdown if req.markdown is not None else existing.markdown
    if len(markdown) > config.max_document_chars:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Document exceeds the {config.max_document_chars:,}-character V1 limit. "
                "Split it into a smaller document before saving."
            ),
        )
    messages = req.messages if req.messages is not None else existing.messages
    doc = await storage.update_document(doc_id, markdown, messages, title=req.title)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document": doc.to_dict()}


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    project_id: str = Depends(get_project_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Delete a document and its snapshots (project-only)."""
    existing = await storage.get_document(doc_id)
    if existing is None or existing.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found")
    ok = await storage.delete_document(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True}


@router.get("/{doc_id}/snapshots")
async def list_snapshots(
    doc_id: str,
    project_id: str = Depends(get_project_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """List all snapshots for a document (project-only)."""
    existing = await storage.get_document(doc_id)
    if existing is None or existing.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found")
    snaps = await storage.list_snapshots(doc_id)
    return {"snapshots": [s.to_dict() for s in snaps]}


@router.post("/{doc_id}/snapshots/{snapshot_id}/restore")
async def restore_snapshot(
    doc_id: str,
    snapshot_id: str,
    project_id: str = Depends(get_project_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Restore document to a specific snapshot (project-only)."""
    existing = await storage.get_document(doc_id)
    if existing is None or existing.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = await storage.restore_snapshot(doc_id, snapshot_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"document": doc.to_dict()}
