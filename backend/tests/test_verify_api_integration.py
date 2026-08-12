"""Integration tests for the persisted verification HTTP workflow."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import get_storage
from app.storage.sqlite_storage import SQLiteStorage


@pytest.fixture
def client(tmp_path):
    storage = SQLiteStorage(str(tmp_path / "exobrain.db"))
    asyncio.run(storage.init())

    async def override_storage():
        return storage

    app.dependency_overrides[get_storage] = override_storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_document(client: TestClient, user_id: str = "researcher-1") -> str:
    response = client.post(
        "/api/documents",
        headers={"X-User-Id": user_id},
        json={"title": "Verification fixture"},
    )
    assert response.status_code == 200
    return response.json()["document"]["id"]


def test_verify_persists_snapshot_claims_and_keeps_claim_ids_stable(client: TestClient):
    document_id = create_document(client)
    markdown = "$$\nx=x\n$$"

    first = client.post(
        "/api/verify",
        headers={"X-User-Id": "researcher-1"},
        json={"document_id": document_id, "markdown": markdown, "locale": "en"},
    )
    second = client.post(
        "/api/verify",
        headers={"X-User-Id": "researcher-1"},
        json={"document_id": document_id, "markdown": markdown, "locale": "en"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["snapshot"]["id"] != second_body["snapshot"]["id"]
    assert first_body["snapshot"]["content_hash"] == second_body["snapshot"]["content_hash"]
    assert first_body["results"][0]["claim_id"] == second_body["results"][0]["claim_id"]
    assert first_body["results"][0]["line"] == 1
    assert first_body["results"][0]["end_line"] == 1

    snapshots = client.get(
        f"/api/documents/{document_id}/snapshots",
        headers={"X-User-Id": "researcher-1"},
    )
    assert snapshots.status_code == 200
    stored = snapshots.json()["snapshots"]
    assert len(stored) == 2
    assert stored[0]["verification_results"][0]["claim_id"] == first_body["results"][0]["claim_id"]


def test_verify_rejects_other_users_document(client: TestClient):
    document_id = create_document(client, user_id="researcher-1")

    response = client.post(
        "/api/verify",
        headers={"X-User-Id": "researcher-2"},
        json={"document_id": document_id, "markdown": "$$x=x$$", "locale": "en"},
    )

    assert response.status_code == 404


def test_verify_and_document_save_enforce_v1_character_limit(client: TestClient):
    document_id = create_document(client)
    oversized_markdown = "x" * 30_001

    verify_response = client.post(
        "/api/verify",
        headers={"X-User-Id": "researcher-1"},
        json={"document_id": document_id, "markdown": oversized_markdown, "locale": "en"},
    )
    save_response = client.patch(
        f"/api/documents/{document_id}",
        headers={"X-User-Id": "researcher-1"},
        json={"markdown": oversized_markdown},
    )

    assert verify_response.status_code == 413
    assert save_response.status_code == 413
