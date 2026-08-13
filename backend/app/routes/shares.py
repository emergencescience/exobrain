"""Read-only, revocable links to immutable verification snapshots."""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.storage import StorageProtocol, get_storage

router = APIRouter(prefix="/api/shares", tags=["shares"])


def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    return x_user_id or "local"


class CreateShareRequest(BaseModel):
    document_id: str
    snapshot_id: str


class RevokeShareRequest(BaseModel):
    document_id: str


async def _owned_snapshot(
    document_id: str,
    snapshot_id: str,
    user_id: str,
    storage: StorageProtocol,
):
    document = await storage.get_document(document_id)
    if document is None or document.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    snapshot = next(
        (item for item in await storage.list_snapshots(document_id) if item.id == snapshot_id),
        None,
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Verification snapshot not found")
    return snapshot


@router.post("")
async def create_share(
    req: CreateShareRequest,
    user_id: str = Depends(get_user_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Create an opaque, read-only capability link for one saved snapshot."""
    snapshot = await _owned_snapshot(req.document_id, req.snapshot_id, user_id, storage)
    share = await storage.create_snapshot_share(snapshot.id)
    return {"token": share.token, "snapshot_id": snapshot.id, "created_at": share.created_at}


@router.get("/{token}")
async def read_shared_snapshot(
    token: str,
    storage: StorageProtocol = Depends(get_storage),
):
    """Read only the immutable evidence needed to review a verification."""
    snapshot = await storage.get_shared_snapshot(token)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Shared verification not found or revoked")
    return {
        "snapshot": {
            "id": snapshot.id,
            "markdown": snapshot.markdown,
            "content_hash": snapshot.content_hash,
            "verification_results": snapshot.verification_results,
            "created_at": snapshot.created_at,
        }
    }


@router.delete("/{token}")
async def revoke_share(
    token: str,
    req: RevokeShareRequest,
    user_id: str = Depends(get_user_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Revoke a share link. The caller must own its underlying document."""
    snapshot = await storage.get_shared_snapshot(token)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Shared verification not found or revoked")
    await _owned_snapshot(req.document_id, snapshot.id, user_id, storage)
    if not await storage.revoke_snapshot_share(snapshot.id, token):
        raise HTTPException(status_code=404, detail="Shared verification not found or revoked")
    return {"revoked": True}
