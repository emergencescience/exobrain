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
    assert "results" not in first_body
    assert "results" not in second_body
    first_results = first_body["snapshot"]["verification_results"]
    second_results = second_body["snapshot"]["verification_results"]
    assert first_results[0]["claim_id"] == second_results[0]["claim_id"]
    assert first_results[0]["line"] == 1
    assert first_results[0]["end_line"] == 1

    snapshots = client.get(
        f"/api/documents/{document_id}/snapshots",
        headers={"X-User-Id": "researcher-1"},
    )
    assert snapshots.status_code == 200
    stored = snapshots.json()["snapshots"]
    assert len(stored) == 2
    assert stored[0]["verification_results"][0]["claim_id"] == first_results[0]["claim_id"]


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


def test_execution_result_can_be_explicitly_linked_to_one_claim(client: TestClient):
    document_id = create_document(client)
    headers = {"X-User-Id": "researcher-1"}
    client.put(
        f"/api/documents/{document_id}",
        headers=headers,
        json={"markdown": "The calculation gives $x=2$."},
    )
    verified = client.post(
        "/api/verify",
        headers=headers,
        json={"document_id": document_id, "markdown": "The calculation gives $x=2$."},
    )
    assert verified.status_code == 200
    snapshot = verified.json()["snapshot"]
    claim_id = snapshot["verification_results"][0]["claim_id"]

    run = client.post(
        "/api/play/exobrain/run",
        headers=headers,
        json={"document_id": document_id, "code": "x = 2\nprint(x)"},
    )
    assert run.status_code == 200
    artifact_id = run.json()["artifact_id"]
    assert artifact_id

    linked = client.post(
        "/api/evidence",
        headers=headers,
        json={
            "document_id": document_id,
            "snapshot_id": snapshot["id"],
            "claim_id": claim_id,
            "artifact_id": artifact_id,
        },
    )
    assert linked.status_code == 200
    assert linked.json()["evidence"]["claim_id"] == claim_id

    evidence = client.get(
        f"/api/evidence/{snapshot['id']}?document_id={document_id}", headers=headers
    )
    assert evidence.status_code == 200
    assert evidence.json()["evidence"][0]["stdout"] == "2\n"


def test_verify_builds_typed_cross_paragraph_claim_edges(client: TestClient):
    document_id = create_document(client)
    markdown = """Assumption: x is real

$$
f(x) = x^2
$$

$$
f'(x) = 2x
$$
"""
    response = client.post(
        "/api/verify",
        headers={"X-User-Id": "researcher-1"},
        json={"document_id": document_id, "markdown": markdown, "locale": "en"},
    )

    assert response.status_code == 200
    results = response.json()["snapshot"]["verification_results"]
    assumption = next(result for result in results if result["claim_type"] == "assumption")
    derivative = next(result for result in results if result["claim_type"] == "differentiation")
    assert derivative["parent_claim_id"] is not None
    assert derivative["edge_type"] == "differentiation"
    assert derivative["assumption_claim_ids"] == [assumption["claim_id"]]
    assert derivative["crosses_paragraph"] is True


def test_title_only_document_update_preserves_markdown_and_messages(client: TestClient):
    document_id = create_document(client)
    headers = {"X-User-Id": "researcher-1"}
    original_markdown = "$$\nx=x\n$$"
    original_messages = [{"role": "user", "content": "keep this history"}]
    saved = client.patch(
        f"/api/documents/{document_id}",
        headers=headers,
        json={"markdown": original_markdown, "messages": original_messages},
    )
    assert saved.status_code == 200

    renamed = client.patch(
        f"/api/documents/{document_id}",
        headers=headers,
        json={"title": "Renamed proof"},
    )

    assert renamed.status_code == 200
    document = renamed.json()["document"]
    assert document["title"] == "Renamed proof"
    assert document["markdown"] == original_markdown
    assert document["messages"] == original_messages


def test_ad_hoc_verify_keeps_results_without_snapshot(client: TestClient):
    response = client.post("/api/verify", json={"markdown": "$$x=x$$", "locale": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"] is None
    assert body["results"][0]["status"] == "verified"


def test_persisted_result_equation_uses_delimiter_free_latex(client: TestClient):
    document_id = create_document(client)
    response = client.post(
        "/api/verify",
        headers={"X-User-Id": "researcher-1"},
        json={"document_id": document_id, "markdown": "$$\nx=x\n$$", "locale": "en"},
    )

    assert response.status_code == 200
    equation = response.json()["snapshot"]["verification_results"][0]["equation"]
    assert equation == "x=x"
    assert not equation.startswith("$")



def test_contextual_tuple_assignment_is_not_required(client: TestClient):
    response = client.post("/api/verify", json={"markdown": "设投影点为\n$$Q=(x,y,0)$$\n"})
    assert response.status_code == 200
    result = next(item for item in response.json()["results"] if item["equation"] == "Q=(x,y,0)")
    assert result["status"] == "not_required"
    assert result["claim_type"] == "definition"


def test_repeated_intermediate_relation_is_context_only(client: TestClient):
    markdown = """$$z=r\\cos\\phi$$

由此得到后续关系。

$$z=r\\cos\\phi$$
"""
    response = client.post("/api/verify", json={"markdown": markdown})
    assert response.status_code == 200
    results = [item for item in response.json()["results"] if item["equation"] == "z=r\\cos\\phi"]
    assert len(results) == 2
    assert results[0]["status"] != "not_required"
    assert results[1]["status"] == "not_required"



def test_atan2_branch_convention_is_explicit():
    from app.verify import latex_to_sympy, verify_equation

    parsed, error = latex_to_sympy(r"\operatorname{atan2}(y,x)")
    assert error is None
    assert parsed is not None
    result = verify_equation(r"\theta=\operatorname{atan2}(y,x)")
    assert result.status == "inconclusive"
    assert "(-π, π]" in result.detail
    assert "mod 2π" in result.detail
