"""Document CRUD routes — project management API."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.storage import get_storage, StorageProtocol

logger = logging.getLogger("exobrain.documents")
router = APIRouter(prefix="/api/documents", tags=["documents"])


class CreateDocumentRequest(BaseModel):
    title: str = "Untitled Paper"


class UpdateDocumentRequest(BaseModel):
    markdown: str = ""
    messages: list[dict] = []
    title: str | None = None


@router.get("")
async def list_documents(storage: StorageProtocol = Depends(get_storage)):
    """List all documents for the current user."""
    # For offline: user_id="local". For online: extract from JWT.
    docs = await storage.list_documents("local")
    return {"documents": [d.to_dict() for d in docs]}


@router.post("")
async def create_document(req: CreateDocumentRequest, storage: StorageProtocol = Depends(get_storage)):
    """Create a new document / project."""
    doc = await storage.create_document("local", title=req.title)
    return {"document": doc.to_dict()}


@router.get("/{doc_id}")
async def get_document(doc_id: str, storage: StorageProtocol = Depends(get_storage)):
    """Get a document by ID with full messages."""
    doc = await storage.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document": doc.to_dict()}


@router.patch("/{doc_id}")
async def update_document(doc_id: str, req: UpdateDocumentRequest, storage: StorageProtocol = Depends(get_storage)):
    """Update document markdown and/or messages."""
    doc = await storage.update_document(doc_id, req.markdown, req.messages, title=req.title)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document": doc.to_dict()}


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, storage: StorageProtocol = Depends(get_storage)):
    """Delete a document and its snapshots."""
    ok = await storage.delete_document(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True}


# ── Snapshots ──────────────────────────────────────────────────────────

@router.get("/{doc_id}/snapshots")
async def list_snapshots(doc_id: str, storage: StorageProtocol = Depends(get_storage)):
    """List all snapshots for a document."""
    snaps = await storage.list_snapshots(doc_id)
    return {"snapshots": [s.to_dict() for s in snaps]}


@router.post("/{doc_id}/snapshots/{snapshot_id}/restore")
async def restore_snapshot(doc_id: str, snapshot_id: str, storage: StorageProtocol = Depends(get_storage)):
    """Restore document to a specific snapshot."""
    doc = await storage.restore_snapshot(doc_id, snapshot_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"document": doc.to_dict()}
