# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Regression coverage for coarse source-bound calculation units."""

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


def test_aligned_calculation_remains_one_coarse_source_bound_unit():
    results = verify_document(CIRCLE_CALCULATION)
    graph = build_proof_graph(CIRCLE_CALCULATION, [result.__dict__ for result in results])
    steps = graph["fragments"][0]["steps"]

    assert len(steps) == 1
    assert steps[0]["source"] == {"start_line": 2, "end_line": 10}
    assert "\\begin{aligned}" in steps[0]["text"]
    assert not steps[0].get("aligned_relation")


def test_sequence_only_edges_are_not_review_visible():
    markdown = "## Derivation\nA premise.\n$$\nx=x\n$$"
    results = verify_document(markdown)
    graph = build_proof_graph(markdown, [result.__dict__ for result in results])

    assert graph["dependencies"]
    assert all(edge.get("review_visible") is False for edge in graph["dependencies"])
