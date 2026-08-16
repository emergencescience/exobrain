# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Tests for bounded proof fragments and proof dependency graph extraction."""
from app.proof_fragments import build_proof_graph


def test_builds_local_fragments_and_conservative_dependencies_for_gaussian_style_proof():
    markdown = """# Gaussian integral

## Assumptions

1. Tonelli applies to the nonnegative integrand.

## Derivation

Let
$$
I = \\int_0^\\infty e^{-x^2} dx.
$$

Form the product integral.
$$
I^2 = \\int_0^\\infty \\int_0^\\infty e^{-(x^2+y^2)} dx dy.
$$

This equality is justified by Tonelli's theorem.

Therefore
$$
I^2 = \\frac{\\pi}{4}.
$$
"""
    verification_results = [
        {"line": 8, "end_line": 10, "status": "verified"},
        {"line": 13, "end_line": 15, "status": "verified"},
        {"line": 20, "end_line": 22, "status": "verified"},
    ]

    graph = build_proof_graph(markdown, verification_results)

    assert graph["schema_version"] == "proof-dependency-graph-v1"
    assert {fragment["title"] for fragment in graph["fragments"]} >= {"Assumptions", "Derivation"}
    steps = [step for fragment in graph["fragments"] for step in fragment["steps"]]
    assert any(step["kind"] == "assumption" for step in steps)
    theorem_step = next(step for step in steps if step["kind"] == "theorem_application")
    assert theorem_step["local_status"] == "not_checked"
    assert any(step["kind"] == "definition" and step["local_status"] == "locally_verified" for step in steps)
    assert any(
        edge["to_step_id"] == theorem_step["id"] and edge["kind"] == "requires_assumption"
        for edge in graph["dependencies"]
    )
    assert all(edge["edge_status"] != "verified" for edge in graph["dependencies"])


def test_proof_fragment_ids_are_stable_for_identical_source():
    markdown = """## Claim
$$
a = a
$$
"""
    first = build_proof_graph(markdown, [])
    second = build_proof_graph(markdown, [])
    assert first == second
