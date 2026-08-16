"""Integration tests for claim- and block-scoped verification snapshots."""
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


def create_document(client: TestClient) -> str:
    response = client.post(
        "/api/documents",
        headers={"X-User-Id": "researcher-1"},
        json={"title": "Scoped verification fixture"},
    )
    assert response.status_code == 200
    return response.json()["document"]["id"]


def test_claim_scoped_verify_preserves_snapshot_scope_and_assumption_context(client: TestClient):
    document_id = create_document(client)
    markdown = """Assumption: x is real

$$
f(x) = x^2
$$

$$
f'(x) = 2x
$$
"""
    headers = {"X-User-Id": "researcher-1"}
    whole_document = client.post(
        "/api/verify",
        headers=headers,
        json={"document_id": document_id, "markdown": markdown, "locale": "en"},
    )
    assert whole_document.status_code == 200
    whole_results = whole_document.json()["snapshot"]["verification_results"]
    target = next(item for item in whole_results if item["claim_type"] == "differentiation")

    scoped = client.post(
        "/api/verify",
        headers=headers,
        json={
            "document_id": document_id,
            "markdown": markdown,
            "locale": "en",
            "scope": {
                "start_line": target["line"],
                "end_line": target["end_line"],
                "claim_id": target["claim_id"],
            },
        },
    )
    assert scoped.status_code == 200
    body = scoped.json()
    assert body["scope"] == {
        "kind": "claim",
        "start_line": target["line"],
        "end_line": target["end_line"],
        "claim_id": target["claim_id"],
    }
    assert body["snapshot"]["verification_scope"] == body["scope"]

    scoped_results = body["snapshot"]["verification_results"]
    scoped_claim_ids = {item["claim_id"] for item in scoped_results}
    assert target["claim_id"] in scoped_claim_ids
    scoped_target = next(item for item in scoped_results if item["claim_id"] == target["claim_id"])
    assert scoped_target["assumption_claim_ids"]
    assert any(item["claim_type"] == "assumption" for item in scoped_results)
    assert all(
        item["claim_type"] == "assumption" or item["line"] >= target["line"]
        for item in scoped_results
    )

    snapshots = client.get(f"/api/documents/{document_id}/snapshots", headers=headers)
    assert snapshots.status_code == 200
    stored_scope = snapshots.json()["snapshots"][0]["verification_scope"]
    assert stored_scope == body["scope"]


def test_block_scoped_verify_rejects_source_ranges_outside_document(client: TestClient):
    document_id = create_document(client)
    response = client.post(
        "/api/verify",
        headers={"X-User-Id": "researcher-1"},
        json={
            "document_id": document_id,
            "markdown": "$$x=x$$",
            "scope": {"start_line": 1, "end_line": 4},
        },
    )
    assert response.status_code == 422
    assert "scope" in response.json()["detail"].lower()
