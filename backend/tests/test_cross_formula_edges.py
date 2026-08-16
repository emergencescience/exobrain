# Copyright (c) 2026 Symbol Science. All rights reserved.
from app.proof_fragments import build_proof_graph


MARKDOWN = r"""# Gaussian fragment

## Assumptions

Assumption: Tonelli applies to the nonnegative integrand.

## Derivation

Let
$$
I = \int_0^\infty e^{-x^2}\,dx.
$$

$$
I^2 = \left(\int_0^\infty e^{-x^2}\,dx\right)^2.
$$

This equality is justified by Tonelli's theorem.

$$
\int_0^\infty r e^{-r^2}\,dr = \frac12.
$$

$$
I^2 = \int_0^{\pi/2} \frac12\,d\theta = \frac{\pi}{4}.
$$

$$
I = \sqrt{\frac{\pi}{4}} = \frac{\sqrt{\pi}}{2}.
$$
"""


def test_extracts_named_cross_formula_dependencies_without_promoting_them():
    graph = build_proof_graph(MARKDOWN, [])
    edges = graph["dependencies"]
    kinds = {edge["kind"] for edge in edges}

    assert "uses_definition" in kinds
    assert "formula_transform" in kinds
    assert "justifies" in kinds
    assert "substitutes_result" in kinds

    named = [edge for edge in edges if edge["kind"] in {"uses_definition", "formula_transform", "justifies", "substitutes_result"}]
    assert named
    assert all(edge["edge_status"] == "not_checked" for edge in named)
    assert all("Candidate" in edge["reason"] or "explicitly names" in edge["reason"] for edge in named)


def test_theorem_justification_points_to_preceding_formula_not_next_formula():
    graph = build_proof_graph(MARKDOWN, [])
    steps = {step["id"]: step for fragment in graph["fragments"] for step in fragment["steps"]}
    edge = next(item for item in graph["dependencies"] if item["kind"] == "justifies")

    source = steps[edge["from_step_id"]]
    target = steps[edge["to_step_id"]]

    assert "Tonelli" in source["text"]
    assert "left" in target["text"]
