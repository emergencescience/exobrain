# Copyright (c) 2026 Symbol Science. All rights reserved.
from app.proof_fragments import build_proof_graph


GAUSSIAN_DERIVATION = r"""# Gaussian integral

## Assumptions

1. Tonelli applies because the integrand is nonnegative.

## Derivation

Let
$$
I = \int_0^\infty e^{-x^2}\,dx.
$$

Compute the radial integral:
$$
\int_0^\infty r e^{-r^2}\,dr = \frac12.
$$

Compute the angular integral:
$$
\int_0^{\pi/2} \frac12\,d\theta = \frac{\pi}{4}.
$$

Thus
$$
I^2 = \frac{\pi}{4}.
$$

Since $I>0$, taking the positive square root gives
$$
I = \sqrt{\frac{\pi}{4}} = \frac{\sqrt{\pi}}{2}.
$$
"""


def _edge(graph, validator_id):
    return next(edge for edge in graph["dependencies"] if edge.get("validator", {}).get("id") == validator_id)


def test_gaussian_local_integral_edges_are_discharged_by_named_rules():
    graph = build_proof_graph(GAUSSIAN_DERIVATION, [])

    radial = _edge(graph, "gaussian-radial-integral-v1")
    angular = _edge(graph, "gaussian-angular-integral-v1")

    assert radial["edge_status"] == "verified"
    assert radial["validator"]["evidence"]["result"] == "1/2"
    assert angular["edge_status"] == "verified"
    assert angular["validator"]["evidence"]["result"] == "pi/4"


def test_positive_root_is_verified_only_under_explicit_positivity_assumption():
    graph = build_proof_graph(GAUSSIAN_DERIVATION, [])

    root = _edge(graph, "positive-square-root-v1")

    assert root["edge_status"] == "verified_under_assumptions"
    assert root["validator"]["evidence"]["premise"] == "I > 0"
    assert root["kind"] == "derives"


def test_theorem_precondition_edge_is_not_promoted_by_local_integral_rules():
    graph = build_proof_graph(GAUSSIAN_DERIVATION, [])

    assumption_edges = [edge for edge in graph["dependencies"] if edge["kind"] == "requires_assumption"]
    assert assumption_edges
    assert all(edge["edge_status"] == "declared" for edge in assumption_edges)
