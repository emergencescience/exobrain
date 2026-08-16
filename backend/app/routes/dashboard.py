# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Searchable, read-only aggregation of immutable verification snapshots."""
from __future__ import annotations

from collections import Counter
from fastapi import APIRouter, Depends, Query
from app.routes.documents import get_user_id
from app.storage import StorageProtocol, get_storage

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _run_status(results: list[dict]) -> str:
    statuses = {str(result.get("status", "")) for result in results}
    if "error" in statuses or "failed" in statuses:
        return "failed"
    if "verified" in statuses and not (statuses - {"verified"}):
        return "verified"
    if "verified" in statuses:
        return "mixed"
    return "needs_review"


def _fragment_summary(fragment: dict) -> dict:
    steps = list(fragment.get("steps") or [])
    formulas = [step for step in steps if step.get("is_formula")]
    local_statuses = Counter(str(step.get("local_status", "not_checked")) for step in formulas)
    return {
        "id": fragment.get("id", ""),
        "title": fragment.get("title", "Untitled fragment"),
        "kind": fragment.get("kind", "context"),
        "source": fragment.get("source", {}),
        "formula_count": len(formulas),
        "local_status_counts": dict(local_statuses),
        "formula_steps": [
            {
                "id": step.get("id", ""),
                "text": step.get("text", ""),
                "local_status": step.get("local_status", "not_checked"),
                "semantic_role": step.get("semantic_role"),
                "verification_target": step.get("verification_target"),
                "semantic_rationale": step.get("semantic_rationale"),
                "source": step.get("source", {}),
            }
            for step in formulas
        ],
    }


@router.get("")
async def verification_dashboard(
    q: str = Query(default="", max_length=200),
    status: str = Query(default="all", pattern="^(all|verified|mixed|needs_review|failed)$"),
    user_id: str = Depends(get_user_id),
    storage: StorageProtocol = Depends(get_storage),
):
    """Return search-ready snapshot summaries without duplicating document bodies.

    The dashboard only aggregates persisted snapshots. It never executes code or
    re-runs verification, preserving the immutable-evidence boundary.
    """
    query = q.strip().lower()
    documents = await storage.list_documents(user_id)
    runs: list[dict] = []
    for document in documents:
        snapshots = await storage.list_snapshots(document.id)
        for snapshot in snapshots:
            results = list(snapshot.verification_results or [])
            graph = snapshot.proof_graph or {}
            fragments = [_fragment_summary(fragment) for fragment in graph.get("fragments", [])]
            counts = Counter(str(result.get("status", "needs_review")) for result in results)
            run = {
                "snapshot_id": snapshot.id,
                "document_id": document.id,
                "document_title": document.title,
                "created_at": snapshot.created_at,
                "verification_scope": snapshot.verification_scope,
                "run_status": _run_status(results),
                "claim_count": len(results),
                "status_counts": dict(counts),
                "fragments": fragments,
                "edge_count": len(graph.get("dependencies", [])),
                "verified_edge_count": sum(
                    1
                    for edge in graph.get("dependencies", [])
                    if edge.get("edge_status") in {"verified", "verified_under_assumptions"}
                ),
            }
            searchable = " ".join(
                [
                    document.title,
                    *[str(result.get("equation", "")) for result in results],
                    *[str(result.get("detail", "")) for result in results],
                    *[str(fragment.get("title", "")) for fragment in fragments],
                    *[
                        str(step.get("text", ""))
                        for fragment in fragments
                        for step in fragment["formula_steps"]
                    ],
                ]
            ).lower()
            if status != "all" and run["run_status"] != status:
                continue
            if query and query not in searchable:
                continue
            runs.append(run)
    runs.sort(key=lambda item: item["created_at"], reverse=True)
    aggregate = Counter(run["run_status"] for run in runs)
    return {
        "query": q,
        "filters": {"status": status},
        "summary": {
            "run_count": len(runs),
            "verified_runs": aggregate["verified"],
            "mixed_runs": aggregate["mixed"],
            "needs_review_runs": aggregate["needs_review"],
            "failed_runs": aggregate["failed"],
            "deterministic_edges": sum(run["verified_edge_count"] for run in runs),
        },
        "runs": runs,
    }
