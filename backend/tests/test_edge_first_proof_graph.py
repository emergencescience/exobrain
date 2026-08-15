# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Regression coverage for source-bound calculation relations and proof edges."""

from app.proof_fragments import build_proof_graph
from app.verify import verify_document


CIRCLE_CALCULATION = r"""## Derivation
$$
\begin{aligned}
S
&=4R^2\int_{0}^{\frac{\pi}{2}}\cos^2 t\,\mathrm{d}t \\
&=4R^2\int_{0}^{\frac{\pi}{2}}\frac{1+\cos2t}{2}\,\mathrm{d}t \\
&=2R^2\left[t+\frac{\sin2t}{2}\right]_{0}^{\frac{\pi}{2}} \\
&=2R^2\cdot\frac{\pi}{2}=\boldsymbol{\pi R^2}.
\end{aligned}
$$"""


def test_aligned_calculation_becomes_adjacent_relation_nodes_and_edges():
    results = verify_document(CIRCLE_CALCULATION)
    graph = build_proof_graph(CIRCLE_CALCULATION, [result.__dict__ for result in results])
    steps = graph["fragments"][0]["steps"]
    relation_steps = [step for step in steps if step.get("aligned_relation")]
    relation_edges = [
        edge for edge in graph["dependencies"]
        if edge["from_step_id"] in {step["id"] for step in relation_steps}
        and edge["to_step_id"] in {step["id"] for step in relation_steps}
    ]

    assert len(relation_steps) == 5
    assert all(step["text"].startswith("$$") for step in relation_steps)
    assert all("\\begin{aligned}" not in step["text"] for step in relation_steps)
    assert len(relation_edges) >= 4
    assert any(edge["edge_status"] == "verified" for edge in relation_edges)


def test_aligned_relation_nodes_keep_row_level_source_ranges():
    results = verify_document(CIRCLE_CALCULATION)
    graph = build_proof_graph(CIRCLE_CALCULATION, [result.__dict__ for result in results])
    relation_steps = [step for step in graph["fragments"][0]["steps"] if step.get("aligned_relation")]

    assert relation_steps[0]["source"]["start_line"] == 4
    assert relation_steps[-1]["source"]["start_line"] == 8
