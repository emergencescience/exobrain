"""Document CRUD routes — project management API."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from app.storage import get_storage, StorageProtocol

logger = logging.getLogger("exobrain.documents")
router = APIRouter(prefix="/api/documents", tags=["documents"])


def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    """Resolve the acting user.

    Online: the orchestrator forwards the authenticated user id as X-User-Id.
    Offline/open-source: no header → single-user "local" namespace.
    """
    return x_user_id or "local"


class CreateDocumentRequest(BaseModel):
    title: str = "Untitled Paper"


class UpdateDocumentRequest(BaseModel):
    markdown: str | None = None
    messages: list[dict] | None = None
    title: str | None = None


@router.get("")
async def list_documents(
    user_id: str = Depends(get_user_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """List all documents owned by the current user."""
    docs = await storage.list_documents(user_id)
    return {"documents": [d.to_dict() for d in docs]}


@router.post("")
async def create_document(
    req: CreateDocumentRequest,
    user_id: str = Depends(get_user_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Create a new document / project owned by the current user."""
    doc = await storage.create_document(user_id, title=req.title)
    return {"document": doc.to_dict()}


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    user_id: str = Depends(get_user_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Get a document by ID with full messages (owner-only)."""
    doc = await storage.get_document(doc_id)
    if doc is None or doc.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document": doc.to_dict()}


@router.patch("/{doc_id}")
async def update_document(
    doc_id: str,
    req: UpdateDocumentRequest,
    user_id: str = Depends(get_user_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Update document markdown, messages and/or title (owner-only, partial).

    Any field left null is preserved from the existing document — so a title-only
    rename does not wipe content, and a content save does not require the title.
    """
    existing = await storage.get_document(doc_id)
    if existing is None or existing.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    markdown = req.markdown if req.markdown is not None else existing.markdown
    messages = req.messages if req.messages is not None else existing.messages
    doc = await storage.update_document(doc_id, markdown, messages, title=req.title)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document": doc.to_dict()}


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    user_id: str = Depends(get_user_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Delete a document and its snapshots (owner-only)."""
    existing = await storage.get_document(doc_id)
    if existing is None or existing.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    ok = await storage.delete_document(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True}


# ── Snapshots ──────────────────────────────────────────────────────────

@router.get("/{doc_id}/snapshots")
async def list_snapshots(
    doc_id: str,
    user_id: str = Depends(get_user_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """List all snapshots for a document (owner-only)."""
    existing = await storage.get_document(doc_id)
    if existing is None or existing.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    snaps = await storage.list_snapshots(doc_id)
    return {"snapshots": [s.to_dict() for s in snaps]}


@router.post("/{doc_id}/snapshots/{snapshot_id}/restore")
async def restore_snapshot(
    doc_id: str,
    snapshot_id: str,
    user_id: str = Depends(get_user_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Restore document to a specific snapshot (owner-only)."""
    existing = await storage.get_document(doc_id)
    if existing is None or existing.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = await storage.restore_snapshot(doc_id, snapshot_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"document": doc.to_dict()}
