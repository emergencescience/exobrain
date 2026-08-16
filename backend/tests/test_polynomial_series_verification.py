# Copyright (c) 2026 Symbol Science. All rights reserved.
from pathlib import Path

from app.verify import extract_equations, verify_document, verify_equation


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_series_schematic_is_not_forced_through_scalar_simplification():
    result = verify_equation(
        r"P_n(x)=\sum_{k=0}^{n}\frac{x^k}{k!}=1+x+\cdots+\frac{x^n}{n!}"
    )

    assert result.status == "inconclusive"
    assert "informal ellipsis" in result.detail
    assert "Simplification error" not in result.detail


def test_chained_equality_is_not_subtracted_as_a_single_sympy_value():
    result = verify_equation(r"f^{(k)}(0)=e^0=1")

    assert result.status == "inconclusive"
    assert "higher-order derivative" in result.detail
    assert "Parse error" not in result.detail


def test_inline_context_does_not_become_an_executable_claim():
    equations = extract_equations("For $x=0$, $f(x)$ is normalized and $a=b$ is a claim.")

    assert equations == [(1, "a=b", "inline")]


def test_polynomial_series_document_has_no_false_error_results():
    markdown = (REPO_ROOT / "logs/polynomial-series.md").read_text()
    results = verify_document(markdown)

    assert results
    assert not [result for result in results if result.status == "error"]
    first_series = next(result for result in results if result.line == 7)
    assert first_series.status == "inconclusive"
    assert "informal ellipsis" in first_series.detail
