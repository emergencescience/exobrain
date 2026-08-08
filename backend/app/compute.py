"""Restricted scientific-computing tools for Exobrain.

This module intentionally does not execute user- or model-supplied Python. The
language model may select a typed operation, but only handwritten operations
below run inside the Exobrain service.
"""

from __future__ import annotations

import re
import uuid
from fractions import Fraction
from typing import Any, Literal

import numpy as np
import sympy as sp
from pydantic import BaseModel, Field


ComputationStatus = Literal[
    "verified",
    "failed",
    "candidate",
    "inconclusive",
    "insufficient_information",
    "reasoned",
    "error",
]

ComputationIntent = Literal[
    "no_tool",
    "matrix_inverse",
    "matrix_determinant",
    "matrix_multiply",
    "symbolic_identity",
    "numeric_evaluate",
]

MAX_MATRIX_SIZE = 6
MATRIX_PATTERN = re.compile(r"\[([^\[\]]+)\]")


class ComputationPlan(BaseModel):
    """A validated request to one allowlisted computation operation."""

    intent: ComputationIntent
    arguments: dict[str, Any] = Field(default_factory=dict)
    locale: Literal["en", "zh"] = "en"


class ComputationArtifact(BaseModel):
    id: str = Field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    kind: str
    status: ComputationStatus
    title: str
    summary: str
    inputs: dict[str, Any]
    result: dict[str, Any]
    code: dict[str, str] | None = None
    provenance: dict[str, str]


class ComputeRequest(BaseModel):
    intent: ComputationIntent
    arguments: dict[str, Any] = Field(default_factory=dict)
    locale: Literal["en", "zh"] = "en"


def _title(locale: str, en: str, zh: str) -> str:
    return zh if locale == "zh" else en


def _safe_scalar(value: Any) -> sp.Rational | sp.Integer | sp.Float:
    """Accept only finite numeric scalar values for public matrix requests."""

    if isinstance(value, bool):
        raise ValueError("Boolean values are not matrix entries")
    if isinstance(value, int):
        return sp.Integer(value)
    if isinstance(value, float):
        if not np.isfinite(value):
            raise ValueError("Matrix entries must be finite")
        return sp.Rational(str(value))
    if isinstance(value, str):
        value = value.strip()
        if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\d+/\d+)", value):
            raise ValueError("Matrix entries must be numeric")
        fraction = Fraction(value)
        return sp.Rational(fraction.numerator, fraction.denominator)
    raise ValueError("Matrix entries must be numeric")


def validate_matrix(raw: Any) -> list[list[sp.Expr]]:
    if not isinstance(raw, list) or not raw or len(raw) > MAX_MATRIX_SIZE:
        raise ValueError(f"Matrix must contain 1 to {MAX_MATRIX_SIZE} rows")
    if not all(isinstance(row, list) and row for row in raw):
        raise ValueError("Matrix rows must be non-empty arrays")
    width = len(raw[0])
    if width > MAX_MATRIX_SIZE or any(len(row) != width for row in raw):
        raise ValueError(f"Matrix must be rectangular and at most {MAX_MATRIX_SIZE} columns")
    return [[_safe_scalar(value) for value in row] for row in raw]


def parse_matlab_matrix(text: str) -> list[list[sp.Expr]] | None:
    """Parse a simple MATLAB-style numeric matrix, e.g. [1,2;3,4]."""

    match = MATRIX_PATTERN.search(text)
    if not match:
        return None
    rows = []
    for raw_row in match.group(1).split(";"):
        entries = [entry.strip() for entry in raw_row.split(",")]
        if not entries or any(not entry for entry in entries):
            return None
        rows.append(entries)
    try:
        return validate_matrix(rows)
    except ValueError:
        return None


def matrix_to_json(matrix: sp.Matrix) -> list[list[str]]:
    return [[str(value) for value in row] for row in matrix.tolist()]


def matrix_to_latex(matrix: sp.Matrix) -> str:
    return sp.latex(matrix)


def matrix_inverse(matrix: list[list[Any]], locale: str) -> ComputationArtifact:
    normalized = validate_matrix(matrix)
    operand = sp.Matrix(normalized)
    determinant = sp.simplify(operand.det())
    code = (
        "import sympy as sp\n\n"
        f"A = sp.Matrix({matrix_to_json(operand)})\n"
        "det_A = A.det()\n"
        "A_inv = A.inv()\n"
        "assert A * A_inv == sp.eye(A.rows)\n"
        "print(det_A)\n"
        "print(A_inv)\n"
    )
    if determinant == 0:
        return ComputationArtifact(
            kind="matrix_inverse",
            status="failed",
            title=_title(locale, "Matrix inverse", "矩阵求逆"),
            summary=_title(locale, "The matrix is singular; no inverse exists.", "该矩阵奇异，不存在逆矩阵。"),
            inputs={"matrix": matrix_to_json(operand)},
            result={"determinant": str(determinant), "inverse_exists": False},
            code={"language": "python", "content": code},
            provenance={"engine": "sympy", "operation": "matrix_inverse"},
        )

    inverse = operand.inv()
    product_is_identity = operand * inverse == sp.eye(operand.rows)
    return ComputationArtifact(
        kind="matrix_inverse",
        status="verified" if product_is_identity else "error",
        title=_title(locale, "Matrix inverse", "矩阵求逆"),
        summary=_title(
            locale,
            f"det(A) = {determinant}; A · A⁻¹ = I.",
            f"det(A) = {determinant}；A · A⁻¹ = I。",
        ),
        inputs={"matrix": matrix_to_json(operand)},
        result={
            "determinant": str(determinant),
            "inverse": matrix_to_json(inverse),
            "inverse_latex": matrix_to_latex(inverse),
            "product_is_identity": product_is_identity,
        },
        code={"language": "python", "content": code},
        provenance={"engine": "sympy", "operation": "matrix_inverse"},
    )


def matrix_determinant(matrix: list[list[Any]], locale: str) -> ComputationArtifact:
    normalized = validate_matrix(matrix)
    operand = sp.Matrix(normalized)
    determinant = sp.simplify(operand.det())
    code = f"import sympy as sp\n\nA = sp.Matrix({matrix_to_json(operand)})\nprint(A.det())\n"
    return ComputationArtifact(
        kind="matrix_determinant",
        status="verified",
        title=_title(locale, "Matrix determinant", "矩阵行列式"),
        summary=_title(locale, f"det(A) = {determinant}", f"det(A) = {determinant}"),
        inputs={"matrix": matrix_to_json(operand)},
        result={"determinant": str(determinant)},
        code={"language": "python", "content": code},
        provenance={"engine": "sympy", "operation": "matrix_determinant"},
    )


def matrix_multiply(left: list[list[Any]], right: list[list[Any]], locale: str) -> ComputationArtifact:
    left_matrix = sp.Matrix(validate_matrix(left))
    right_matrix = sp.Matrix(validate_matrix(right))
    if left_matrix.cols != right_matrix.rows:
        return ComputationArtifact(
            kind="matrix_multiply",
            status="insufficient_information",
            title=_title(locale, "Matrix multiplication", "矩阵乘法"),
            summary=_title(locale, "Matrix dimensions are incompatible.", "矩阵维度不兼容。"),
            inputs={"left": matrix_to_json(left_matrix), "right": matrix_to_json(right_matrix)},
            result={},
            provenance={"engine": "sympy", "operation": "matrix_multiply"},
        )
    product = left_matrix * right_matrix
    code = (
        "import sympy as sp\n\n"
        f"left = sp.Matrix({matrix_to_json(left_matrix)})\n"
        f"right = sp.Matrix({matrix_to_json(right_matrix)})\n"
        "print(left * right)\n"
    )
    return ComputationArtifact(
        kind="matrix_multiply",
        status="verified",
        title=_title(locale, "Matrix multiplication", "矩阵乘法"),
        summary=_title(locale, "Matrix product computed exactly.", "已精确计算矩阵乘积。"),
        inputs={"left": matrix_to_json(left_matrix), "right": matrix_to_json(right_matrix)},
        result={"product": matrix_to_json(product), "product_latex": matrix_to_latex(product)},
        code={"language": "python", "content": code},
        provenance={"engine": "sympy", "operation": "matrix_multiply"},
    )


def plan_from_text(text: str, locale: str) -> ComputationPlan:
    """Conservative P0 router for unambiguous MATLAB-style matrix requests."""

    matrix = parse_matlab_matrix(text)
    lowered = text.lower()
    if matrix:
        matrix_json = [[str(value) for value in row] for row in matrix]
        if any(token in lowered for token in ("inverse", "inv", "求逆", "逆矩阵")):
            return ComputationPlan(intent="matrix_inverse", arguments={"matrix": matrix_json}, locale=locale)
        if any(token in lowered for token in ("determinant", "det", "行列式")):
            return ComputationPlan(intent="matrix_determinant", arguments={"matrix": matrix_json}, locale=locale)
    return ComputationPlan(intent="no_tool", locale=locale)


def execute_plan(plan: ComputationPlan) -> ComputationArtifact | None:
    """Run one validated computation; never evaluates arbitrary source code."""

    if plan.intent == "no_tool":
        return None
    if plan.intent == "matrix_inverse":
        return matrix_inverse(plan.arguments.get("matrix", []), plan.locale)
    if plan.intent == "matrix_determinant":
        return matrix_determinant(plan.arguments.get("matrix", []), plan.locale)
    if plan.intent == "matrix_multiply":
        return matrix_multiply(
            plan.arguments.get("left", []),
            plan.arguments.get("right", []),
            plan.locale,
        )
    raise ValueError(f"Unsupported computation intent: {plan.intent}")
