# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Integration coverage for persisted local proof dependency graphs."""
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


def test_verify_persists_local_proof_dependency_graph(client: TestClient):
    headers = {"X-User-Id": "researcher-1"}
    created = client.post("/api/documents", headers=headers, json={"title": "Gaussian fragment"})
    assert created.status_code == 200
    document_id = created.json()["document"]["id"]
    markdown = """## Assumptions

Assumption: Tonelli applies to the nonnegative integrand.

## Derivation

Let
$$
I = x + 1
$$

Therefore
$$
I - 1 = x
$$
"""

    response = client.post(
        "/api/verify",
        headers=headers,
        json={"document_id": document_id, "markdown": markdown, "locale": "en"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "proof_graph" not in body
    graph = body["snapshot"]["proof_graph"]
    assert graph["schema_version"] == "proof-dependency-graph-v1"
    assert graph["fragments"]
    assert any(
        step["kind"] == "assumption"
        for fragment in graph["fragments"]
        for step in fragment["steps"]
    )
    assert all(edge["edge_status"] != "verified" for edge in graph["dependencies"])
    assert body["snapshot"]["proof_graph"] == graph

    snapshots = client.get(f"/api/documents/{document_id}/snapshots", headers=headers)
    assert snapshots.status_code == 200
    stored = snapshots.json()["snapshots"][0]["proof_graph"]
    assert stored == graph
