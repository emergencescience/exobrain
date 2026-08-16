# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Regression coverage for the bounded exponential-at-zero proof rule."""
from __future__ import annotations

from app.proof_fragments import build_proof_graph


def test_exponential_at_zero_is_verified_under_the_cited_derivative_premise():
    graph = build_proof_graph(
        """## Derivation
$$
f^{(k)}(x)=e^x
$$
Therefore
$$
f^{(k)}(0)=e^0=1
$$
""",
        [],
    )

    target = next(step for fragment in graph["fragments"] for step in fragment["steps"] if "e^0=1" in step["text"].replace(" ", ""))
    incoming = [edge for edge in graph["dependencies"] if edge["to_step_id"] == target["id"]]
    assert any(edge.get("validator", {}).get("id") == "exponential-at-zero-v1" for edge in incoming)
    assert any(edge["edge_status"] == "verified_under_assumptions" for edge in incoming)
    assert target["local_status"] == "partially_checked"
