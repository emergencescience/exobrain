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


def test_selected_scope_with_semantic_parse_uses_scope_metadata_not_missing_kind(monkeypatch, client):
    import app.routes.verify as verify_route

    async def unavailable_semantic_parser(_graph, _locale):
        return None, {"status": "unavailable", "reason": "test", "notice": "test"}

    monkeypatch.setattr(verify_route, "propose_semantic_structure", unavailable_semantic_parser)
    response = client.post("/api/verify", json={
        "markdown": "# Scope\n\n$$\nx=x\n$$\n",
        "scope": {"start_line": 3, "end_line": 5, "claim_id": "claim-1"},
        "semantic_parse": True,
    })

    assert response.status_code == 200
    assert response.json()["scope"] == {"kind": "claim", "start_line": 3, "end_line": 5, "claim_id": "claim-1"}


def test_semantic_proposal_is_persisted_in_document_snapshot(monkeypatch, client):
    import app.routes.verify as verify_route

    async def semantic_parser(graph, _locale):
        steps = [step for fragment in graph["fragments"] for step in fragment["steps"]]
        return {
            "fragments": [{"title": "Source calculation", "role": "calculation", "step_ids": [steps[-1]["id"]]}],
            "steps": [{"step_id": steps[-1]["id"], "role": "calculation", "verification_target": "semantic", "rule_id": "", "depends_on": [], "rationale": "Short source-bound calculation."}],
        }, {"status": "proposed", "reason": "", "notice": "test"}

    monkeypatch.setattr(verify_route, "propose_semantic_structure", semantic_parser)
    headers = {"X-User-Id": "researcher-semantic"}
    created = client.post("/api/documents", headers=headers, json={"title": "Semantic snapshot"})
    document_id = created.json()["document"]["id"]
    response = client.post("/api/verify", headers=headers, json={
        "document_id": document_id,
        "markdown": "# Derivation\n\n$$\nx=x\n$$\n",
        "semantic_parse": True,
    })

    assert response.status_code == 200
    graph = response.json()["snapshot"]["proof_graph"]
    assert graph["semantic_proposal"]["status"] == "proposed"
    assert any(
        step.get("semantic_role") == "calculation"
        for fragment in graph["fragments"]
        for step in fragment["steps"]
    )


def test_semantic_review_promotes_only_unresolved_result_and_preserves_deterministic_status(monkeypatch, client):
    import app.routes.verify as verify_route

    async def semantic_parser(graph, _locale):
        formula_step = next(
            step for fragment in graph["fragments"] for step in fragment["steps"] if step.get("is_formula")
        )
        return {
            "fragments": [{"title": "Standard relation", "role": "calculation", "step_ids": [formula_step["id"]]}],
            "steps": [{"step_id": formula_step["id"], "role": "calculation", "verification_target": "semantic", "rule_id": "", "depends_on": [], "rationale": "A standard source-bound relation."}],
        }, {"status": "proposed", "reason": "", "notice": "test"}

    monkeypatch.setattr(verify_route, "propose_semantic_structure", semantic_parser)
    headers = {"X-User-Id": "researcher-semantic-status"}
    created = client.post("/api/documents", headers=headers, json={"title": "Semantic result status"})
    document_id = created.json()["document"]["id"]
    response = client.post("/api/verify", headers=headers, json={
        "document_id": document_id,
        "markdown": "# Relation\n\n$$\nx=y\n$$\n",
        "semantic_parse": True,
    })

    assert response.status_code == 200
    result = response.json()["snapshot"]["verification_results"][0]
    assert result["status"] == "semantically_reviewed"
    assert result["deterministic_status"] == "inconclusive"
    assert result["semantic_status"] == "structurally_reviewed"


def test_semantic_review_never_overwrites_deterministically_verified_result(monkeypatch, client):
    import app.routes.verify as verify_route

    async def semantic_parser(graph, _locale):
        formula_step = next(
            step for fragment in graph["fragments"] for step in fragment["steps"] if step.get("is_formula")
        )
        return {
            "fragments": [{"title": "Identity", "role": "calculation", "step_ids": [formula_step["id"]]}],
            "steps": [{"step_id": formula_step["id"], "role": "calculation", "verification_target": "semantic", "rule_id": "", "depends_on": [], "rationale": "Identity."}],
        }, {"status": "proposed", "reason": "", "notice": "test"}

    monkeypatch.setattr(verify_route, "propose_semantic_structure", semantic_parser)
    response = client.post("/api/verify", json={"markdown": "$$\nx=x\n$$\n", "semantic_parse": True})

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "verified"
    assert result["deterministic_status"] is None
    assert result["semantic_status"] is None
