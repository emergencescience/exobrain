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


def test_verify_route_persists_named_semantic_parser_audit_log(client, monkeypatch):
    from app.routes import verify as verify_route

    headers = {"X-User-Id": "researcher-1"}
    document_id = client.post("/api/documents", headers=headers, json={"title": "Semantic audit"}).json()["document"]["id"]

    async def fake_proposal(graph, locale):
        step = graph["fragments"][0]["steps"][0]
        return ({
            "fragments": [{"title": "Definition", "role": "definition", "step_ids": [step["id"]]}],
            "steps": [{"step_id": step["id"], "role": "definition", "verification_target": "none", "rule_id": "", "depends_on": [], "rationale": "definition"}],
        }, {
            "status": "proposed",
            "reason": "",
            "notice": "Source-bound LLM structure proposal available.",
            "_llm_call_log": {
                "call_name": "semantic_proof_structure",
                "system_prompt_name": "semantic-proof-structure-v1",
                "provider": "provider.test",
                "model": "test-model",
                "request_payload": {"locale": locale, "source_steps": [{"id": step["id"]}]},
                "response_text": '{"steps": []}',
                "status": "proposed",
                "http_status": 200,
                "error_type": "",
            },
        })

    monkeypatch.setattr(verify_route, "propose_semantic_structure", fake_proposal)
    response = client.post(
        "/api/verify",
        headers=headers,
        json={"document_id": document_id, "markdown": "## Derivation\n$$\nx=x\n$$", "locale": "en", "semantic_parse": True},
    )
    assert response.status_code == 200
    logs = client.get(f"/api/documents/{document_id}/llm-call-logs", headers=headers)
    assert logs.status_code == 200
    record = logs.json()["llm_call_logs"][0]
    assert record["system_prompt_name"] == "semantic-proof-structure-v1"
    assert record["response_text"] == '{"steps": []}'


def test_semantic_calculation_upgrades_a_hidden_sequence_edge_and_flags_implicit_substitution():
    from app.proof_fragments import build_proof_graph
    from app.semantic_proof import apply_semantic_proposal, validate_semantic_proposal
    from app.verify import verify_document

    markdown = r"""## Derivation
采用三角代换：令 $x=R\sin t$，$\mathrm{d}x=R\cos t\,\mathrm{d}t$。
$$
\begin{aligned}
S &= 4\int_0^{\pi/2} R^2\cos^2 t\,\mathrm{d}t \\
  &= \pi R^2.
\end{aligned}
$$"""
    results = verify_document(markdown)
    graph = build_proof_graph(markdown, [result.__dict__ for result in results])
    steps = graph["fragments"][0]["steps"]
    substitution, calculation = steps
    proposal = validate_semantic_proposal({
        "fragments": [{"title": "Trigonometric substitution calculation", "role": "calculation", "step_ids": [substitution["id"], calculation["id"]]}],
        "steps": [
            {"step_id": substitution["id"], "role": "calculation", "verification_target": "semantic", "rule_id": "", "depends_on": [], "rationale": "Substitution setup."},
            {"step_id": calculation["id"], "role": "calculation", "verification_target": "semantic", "rule_id": "", "depends_on": [substitution["id"]], "rationale": "Evaluate the substituted integral."},
        ],
    }, graph)

    assert proposal is not None
    annotated = apply_semantic_proposal(graph, proposal)
    edge = next(item for item in annotated["dependencies"] if item["from_step_id"] == substitution["id"] and item["to_step_id"] == calculation["id"])
    assert edge["review_visible"] is True
    assert edge["kind"] == "requires_assumption"
    assert edge["edge_status"] == "declared"
    assert "function of the parameter" in edge["reason"]
    assert annotated["fragments"][0]["steps"][1]["local_status"] == "semantically_reviewed"


def test_semantic_parser_retries_without_response_format_when_provider_rejects_schema(monkeypatch):
    import asyncio
    import json
    import httpx
    import app.semantic_proof as semantic_proof

    graph = _graph()
    source_step = graph["fragments"][0]["steps"][0]
    raw_proposal = {
        "fragments": [{"title": "Definition", "role": "definition", "step_ids": [source_step["id"]]}],
        "steps": [{"step_id": source_step["id"], "role": "definition", "verification_target": "none", "rule_id": "", "depends_on": [], "rationale": "Definition."}],
    }

    class CompatibleClient:
        payloads = []
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, traceback):
            return False
        async def post(self, _url, *, headers, json):
            self.payloads.append(json)
            request = httpx.Request("POST", "https://provider.test/v1/chat/completions")
            if len(self.payloads) == 1:
                return httpx.Response(400, request=request, text='{"error":{"message":"This response_format type is unavailable now"}}')
            return httpx.Response(200, request=request, json={"choices": [{"message": {"content": __import__("json").dumps(raw_proposal)}}]})

    client = CompatibleClient()
    monkeypatch.setattr(semantic_proof.config, "llm_api_key", "configured")
    monkeypatch.setattr(semantic_proof.config, "llm_base_url", "https://provider.test")
    monkeypatch.setattr(semantic_proof.httpx, "AsyncClient", lambda timeout: client)

    proposal, status = asyncio.run(semantic_proof.propose_semantic_structure(graph, "en"))

    assert proposal is not None
    assert status["status"] == "proposed"
    assert "response_format" in client.payloads[0]
    assert "response_format" not in client.payloads[1]


def test_deepseek_semantic_parse_skips_unsupported_schema_and_bounds_request(monkeypatch):
    import asyncio
    import httpx
    import app.semantic_proof as semantic_proof

    graph = _graph()
    step = graph["fragments"][0]["steps"][0]
    raw_proposal = {
        "fragments": [{"title": "Definition", "role": "definition", "step_ids": [step["id"]]}],
        "steps": [{"step_id": step["id"], "role": "definition", "verification_target": "none", "rule_id": "", "depends_on": [], "rationale": "Definition."}],
    }

    class DeepSeekClient:
        requests = []
        timeout = None
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, traceback):
            return False
        async def post(self, _url, *, headers, json):
            self.requests.append(json)
            request = httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions")
            return httpx.Response(200, request=request, json={"choices": [{"message": {"content": __import__("json").dumps(raw_proposal)}}]})

    client = DeepSeekClient()
    monkeypatch.setattr(semantic_proof.config, "llm_api_key", "configured")
    monkeypatch.setattr(semantic_proof.config, "llm_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(semantic_proof.httpx, "AsyncClient", lambda timeout: setattr(client, "timeout", timeout) or client)

    proposal, status = asyncio.run(semantic_proof.propose_semantic_structure(graph, "en"))

    assert proposal is not None
    assert status["status"] == "proposed"
    assert len(client.requests) == 1
    assert client.requests[0]["response_format"] == {"type": "json_object"}
    assert client.requests[0]["thinking"] == {"type": "disabled"}
    assert client.requests[0]["max_tokens"] == 1200
    assert client.timeout.read == 15.0


def test_fragment_only_deepseek_json_object_proposal_is_expanded_source_bound():
    import app.semantic_proof as semantic_proof

    graph = _graph()
    definition, calculation = graph["fragments"][0]["steps"][:2]
    proposal = semantic_proof.validate_semantic_proposal({
        "fragments": [
            {
                "id": "frag_definition",
                "source_ids": [definition["id"]],
                "kind": "definition",
                "verification_target": "none",
                "depends_on": [],
                "rationale": "Define the source variable.",
            },
            {
                "id": "frag_calculation",
                "source_ids": [calculation["id"]],
                "kind": "calculation",
                "verification_target": "semantic",
                "depends_on": ["frag_definition"],
                "rationale": "Evaluate the source-bound calculation.",
            },
        ],
    }, graph)

    assert proposal is not None
    by_id = {item["step_id"]: item for item in proposal["steps"]}
    assert by_id[definition["id"]]["role"] == "definition"
    assert by_id[calculation["id"]]["role"] == "calculation"
    assert by_id[calculation["id"]]["depends_on"] == [definition["id"]]


def test_semantic_parser_audits_empty_non_json_provider_response(monkeypatch):
    import asyncio
    import httpx
    import app.semantic_proof as semantic_proof

    class EmptyBodyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, *_args, **_kwargs):
            request = httpx.Request("POST", "https://provider.test/v1/chat/completions")
            return httpx.Response(200, request=request, text="")

    monkeypatch.setattr(semantic_proof.config, "llm_api_key", "configured")
    monkeypatch.setattr(semantic_proof.config, "llm_base_url", "https://provider.test")
    monkeypatch.setattr(semantic_proof.httpx, "AsyncClient", lambda timeout: EmptyBodyClient())

    proposal, status = asyncio.run(semantic_proof.propose_semantic_structure(_graph(), "en"))

    assert proposal is None
    audit = status["_llm_call_log"]
    assert audit["status"] == "provider_error"
    assert audit["http_status"] == 200
    assert audit["error_type"] == "JSONDecodeError"
    assert "empty provider response body" in audit["response_text"]
    assert "http_status=200" in audit["response_text"]


def test_semantic_parser_audits_non_json_provider_body(monkeypatch):
    import asyncio
    import httpx
    import app.semantic_proof as semantic_proof

    class InvalidJsonClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, *_args, **_kwargs):
            request = httpx.Request("POST", "https://provider.test/v1/chat/completions")
            return httpx.Response(200, request=request, text="upstream gateway returned HTML")

    monkeypatch.setattr(semantic_proof.config, "llm_api_key", "configured")
    monkeypatch.setattr(semantic_proof.config, "llm_base_url", "https://provider.test")
    monkeypatch.setattr(semantic_proof.httpx, "AsyncClient", lambda timeout: InvalidJsonClient())

    proposal, status = asyncio.run(semantic_proof.propose_semantic_structure(_graph(), "en"))

    assert proposal is None
    audit = status["_llm_call_log"]
    assert audit["http_status"] == 200
    assert audit["error_type"] == "JSONDecodeError"
    assert audit["response_text"] == "upstream gateway returned HTML"


def test_semantic_parser_marks_length_limited_provider_output_as_truncated(monkeypatch):
    import asyncio
    import httpx
    import app.semantic_proof as semantic_proof

    class TruncatedClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, *_args, **_kwargs):
            request = httpx.Request("POST", "https://provider.test/v1/chat/completions")
            return httpx.Response(
                200,
                request=request,
                json={"choices": [{"finish_reason": "length", "message": {"content": "{\"steps\":["}}]},
            )

    monkeypatch.setattr(semantic_proof.config, "llm_api_key", "configured")
    monkeypatch.setattr(semantic_proof.config, "llm_base_url", "https://provider.test")
    monkeypatch.setattr(semantic_proof.httpx, "AsyncClient", lambda timeout: TruncatedClient())

    proposal, status = asyncio.run(semantic_proof.propose_semantic_structure(_graph(), "en"))

    assert proposal is None
    assert status["reason"] == "provider_output_truncated"
    audit = status["_llm_call_log"]
    assert audit["status"] == "truncated"
    assert audit["error_type"] == "OutputTruncated"
    assert audit["http_status"] == 200
    assert '"finish_reason":"length"' in audit["response_text"]
