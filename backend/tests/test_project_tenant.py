"""Project header isolation. Trust boundary is the private network + Orchestrator JWT."""

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


def test_documents_are_isolated_by_project_header(client: TestClient):
    created = client.post(
        "/api/documents",
        headers={"X-Project-Id": "alpha"},
        json={"title": "Alpha paper"},
    )
    assert created.status_code == 200
    doc_id = created.json()["document"]["id"]
    assert created.json()["document"]["project_id"] == "alpha"

    other = client.get("/api/documents", headers={"X-Project-Id": "beta"})
    assert other.status_code == 200
    assert other.json()["documents"] == []

    hidden = client.get(f"/api/documents/{doc_id}", headers={"X-Project-Id": "beta"})
    assert hidden.status_code == 404

    owned = client.get(f"/api/documents/{doc_id}", headers={"X-Project-Id": "alpha"})
    assert owned.status_code == 200
