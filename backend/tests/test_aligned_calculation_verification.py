# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Regression tests for aligned calculation blocks."""

from app.proof_fragments import build_proof_graph
from app.verify import extract_equations, verify_document


ALIGNED_CIRCLE_CALCULATION = r"""$$
\begin{aligned}
S
&=4R^2\int_{0}^{\frac{\pi}{2}}\cos^2 t\,\mathrm{d}t \\
&=4R^2\int_{0}^{\frac{\pi}{2}}\frac{1+\cos2t}{2}\,\mathrm{d}t \\
&=2R^2\left[t+\frac{\sin2t}{2}\right]_{0}^{\frac{\pi}{2}} \\
&=2R^2\cdot\frac{\pi}{2}=\boldsymbol{\pi R^2}.
\end{aligned}
$$"""


def test_aligned_calculation_is_one_source_claim_with_terminal_evidence():
    equations = extract_equations(ALIGNED_CIRCLE_CALCULATION)
    assert len(equations) == 1
    assert equations[0][0] == 1
    assert equations[0][2] == "block"

    results = verify_document(ALIGNED_CIRCLE_CALCULATION)
    assert len(results) == 1
    result = results[0]
    assert result.status == "partially_checked"
    assert "terminal relation" in result.detail
    assert r"\begin{aligned}" in result.equation


def test_aligned_calculation_is_retained_as_one_review_unit():
    results = verify_document(ALIGNED_CIRCLE_CALCULATION)
    graph = build_proof_graph(ALIGNED_CIRCLE_CALCULATION, [result.__dict__ for result in results])
    steps = graph["fragments"][0]["steps"]

    assert len(steps) == 1
    assert "\\begin{aligned}" in steps[0]["text"]
    assert all(edge.get("review_visible") is False for edge in graph["dependencies"])
