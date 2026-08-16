# Copyright (c) 2026 Symbol Science. All rights reserved.
from app.verify import verify_document, verify_equation


INTEGRAL_DEFINITION = r"I = \int_0^\infty e^{-x^2}\,dx."


def test_named_integral_definition_is_not_sent_to_sympy_as_a_standalone_equality():
    result = verify_equation(INTEGRAL_DEFINITION)

    assert result.status == "inconclusive"
    assert result.equation == INTEGRAL_DEFINITION
    assert "named integral definition" in result.detail
    assert "Parse error" not in result.detail


def test_document_verification_preserves_integral_definition_without_false_error():
    results = verify_document(f"$$\n{INTEGRAL_DEFINITION}\n$$")

    assert len(results) == 1
    assert results[0].status == "inconclusive"
    assert "standalone executable equality" in results[0].detail
