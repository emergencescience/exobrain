# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Unit coverage for source-bound LLM semantic proof proposals."""
from __future__ import annotations

import asyncio
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.semantic_proof import apply_semantic_proposal, validate_semantic_proposal
from app.storage import get_storage
from app.storage.sqlite_storage import SQLiteStorage


@pytest.fixture
def client(tmp_path):
    storage = SQLiteStorage(str(tmp_path / "semantic-proof.db"))
    asyncio.run(storage.init())

    async def override_storage():
        return storage

    app.dependency_overrides[get_storage] = override_storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _graph():
    return {
        "fragments": [{
            "id": "fragment_1",
            "steps": [
                {"id": "definition", "text": "$$\nf(x)=e^x\n$$", "source": {"start_line": 1, "end_line": 3}, "kind": "definition", "is_formula": True, "local_status": "inconclusive"},
                {"id": "lemma", "text": "$$\nf^{(k)}(x)=e^x\n$$", "source": {"start_line": 5, "end_line": 7}, "kind": "statement", "is_formula": True, "local_status": "inconclusive"},
                {"id": "deduction", "text": "$$\nf^{(k)}(0)=e^0=1\n$$", "source": {"start_line": 9, "end_line": 11}, "kind": "derivation_step", "is_formula": True, "local_status": "inconclusive"},
            ],
        }],
        "dependencies": [],
    }


def test_semantic_proposal_marks_cited_lemmas_not_required_but_keeps_deductions_open():
    graph = _graph()
    proposal = validate_semantic_proposal({
        "fragments": [{"title": "Exponential premise", "role": "lemma", "step_ids": ["definition", "lemma"]}, {"title": "Evaluate at zero", "role": "deduction", "step_ids": ["deduction"]}],
        "steps": [
            {"step_id": "definition", "role": "definition", "verification_target": "none", "rule_id": "", "depends_on": [], "rationale": "definition"},
            {"step_id": "lemma", "role": "lemma", "verification_target": "none", "rule_id": "", "depends_on": [], "rationale": "cited property"},
            {"step_id": "deduction", "role": "deduction", "verification_target": "rule", "rule_id": "exponential-at-zero-v1", "depends_on": ["lemma"], "rationale": "evaluate"},
        ],
    }, graph)

    assert proposal is not None
    annotated = apply_semantic_proposal(graph, proposal)
    steps = {step["id"]: step for step in annotated["fragments"][0]["steps"]}
    assert steps["definition"]["local_status"] == "not_required"
    assert steps["lemma"]["local_status"] == "not_required"
    assert steps["deduction"]["local_status"] == "inconclusive"
    assert annotated["semantic_proposal"]["status"] == "proposed"


def test_semantic_proposal_rejects_unknown_source_ids():
    assert validate_semantic_proposal({
        "fragments": [{"title": "Bad", "role": "lemma", "step_ids": ["missing"]}],
        "steps": [],
    }, _graph()) is None


def test_verify_route_persists_a_source_bound_semantic_proposal(client, monkeypatch):
    from app.routes import verify as verify_route

    headers = {"X-User-Id": "researcher-1"}
    document_id = client.post("/api/documents", headers=headers, json={"title": "Semantic proof"}).json()["document"]["id"]

    async def fake_proposal(graph, locale):
        steps = [step for fragment in graph["fragments"] for step in fragment["steps"]]
        return ({
            "fragments": [{"title": "Cited premise", "role": "lemma", "step_ids": [steps[0]["id"]]}],
            "steps": [{
                "step_id": steps[0]["id"],
                "role": "lemma",
                "verification_target": "none",
                "rule_id": "",
                "depends_on": [],
                "rationale": "Cited source premise.",
            }],
        }, {"status": "proposed", "reason": "", "notice": "Source-bound LLM structure proposal available."})

    monkeypatch.setattr(verify_route, "propose_semantic_structure", fake_proposal)
    response = client.post(
        "/api/verify",
        headers=headers,
        json={
            "document_id": document_id,
            "markdown": "## Derivation\n$$\nf(x)=e^x\n$$",
            "locale": "en",
            "semantic_parse": True,
        },
    )

    assert response.status_code == 200
    graph = response.json()["snapshot"]["proof_graph"]
    assert graph["semantic_proposal"]["status"] == "proposed"
    annotated = graph["fragments"][0]["steps"][0]
    assert annotated["semantic_role"] == "lemma"
    assert annotated["local_status"] == "not_required"
    assert "LLM structure" in graph["semantic_proposal"]["notice"]


def test_semantic_parser_reports_provider_authentication_failure(monkeypatch):
    import httpx
    import app.semantic_proof as semantic_proof

    graph = _graph()

    class FailingClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, traceback):
            return False
        async def post(self, *args, **kwargs):
            request = httpx.Request("POST", "https://provider.invalid/v1/chat/completions")
            response = httpx.Response(401, request=request)
            raise httpx.HTTPStatusError("401", request=request, response=response)

    monkeypatch.setattr(semantic_proof.config, "llm_api_key", "configured")
    monkeypatch.setattr(semantic_proof.httpx, "AsyncClient", lambda timeout: FailingClient())
    proposal, status = __import__("asyncio").run(semantic_proof.propose_semantic_structure(graph, "en"))

    assert proposal is None
    assert status["reason"] == "provider_authentication_failed"
    assert status["status"] == "unavailable"
