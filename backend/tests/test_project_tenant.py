"""Internal API key and project header behaviour."""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import get_storage
from app.storage.sqlite_storage import SQLiteStorage


@pytest.fixture
def client(tmp_path, monkeypatch):
    storage = SQLiteStorage(str(tmp_path / "exobrain.db"))
    asyncio.run(storage.init())

    async def override_storage():
        return storage

    app.dependency_overrides[get_storage] = override_storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    monkeypatch.delenv("EXOBRAIN_INTERNAL_API_KEY", raising=False)
    monkeypatch.delenv("EXOBRAIN_REQUIRE_INTERNAL_KEY", raising=False)


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


def test_internal_key_rejects_unauthenticated_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("EXOBRAIN_INTERNAL_API_KEY", "secret-key")
    monkeypatch.setenv("EXOBRAIN_REQUIRE_INTERNAL_KEY", "1")
    storage = SQLiteStorage(str(tmp_path / "exobrain.db"))
    asyncio.run(storage.init())

    async def override_storage():
        return storage

    app.dependency_overrides[get_storage] = override_storage
    try:
        with TestClient(app) as client:
            denied = client.post("/api/documents", json={"title": "nope"})
            assert denied.status_code == 401
            allowed = client.post(
                "/api/documents",
                headers={"X-API-Key": "secret-key", "X-Project-Id": "local"},
                json={"title": "ok"},
            )
            assert allowed.status_code == 200
            health = client.get("/health")
            assert health.status_code == 200
    finally:
        app.dependency_overrides.clear()
