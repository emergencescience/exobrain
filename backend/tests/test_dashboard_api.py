# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Integration coverage for the searchable verification dashboard."""
from __future__ import annotations

import asyncio
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.storage import get_storage
from app.storage.sqlite_storage import SQLiteStorage


@pytest.fixture
def client(tmp_path):
    storage = SQLiteStorage(str(tmp_path / "dashboard.db"))
    asyncio.run(storage.init())

    async def override_storage():
        return storage

    app.dependency_overrides[get_storage] = override_storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_dashboard_aggregates_searchable_snapshot_evidence(client: TestClient):
    headers = {"X-User-Id": "researcher-1"}
    document_id = client.post("/api/documents", headers=headers, json={"title": "Polynomial Series"}).json()["document"]["id"]
    verified = client.post(
        "/api/verify",
        headers=headers,
        json={"document_id": document_id, "markdown": "## Derivation\n$$\nx = x\n$$", "locale": "en"},
    )
    assert verified.status_code == 200

    response = client.get("/api/dashboard", headers=headers, params={"q": "Polynomial", "status": "all"})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["run_count"] == 1
    run = body["runs"][0]
    assert run["document_title"] == "Polynomial Series"
    assert run["claim_count"] == 1
    assert run["fragments"]
    assert "formula_steps" in run["fragments"][0]


def test_dashboard_does_not_return_document_markdown(client: TestClient):
    headers = {"X-User-Id": "researcher-1"}
    document_id = client.post("/api/documents", headers=headers, json={"title": "Private proof"}).json()["document"]["id"]
    source = "## Derivation\n$$\ny = y\n$$"
    client.post("/api/verify", headers=headers, json={"document_id": document_id, "markdown": source, "locale": "en"})

    body = client.get("/api/dashboard", headers=headers).json()

    assert source not in str(body)
    assert "markdown" not in body["runs"][0]
