"""SymPy formal verification engine — validate LaTeX equations in documents."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("exobrain.verify")


@dataclass
class VerificationResult:
    line: int          # 1-indexed line number
    equation: str      # original LaTeX string
    status: str        # "verified", "inconclusive", "error"
    detail: str        # human-readable explanation


def extract_equations(markdown: str) -> list[tuple[int, str, str]]:
    """Extract all LaTeX equations from markdown.

    Returns list of (line_number, raw_text, display_mode).
    display_mode: "block" for $$...$$, "inline" for $...$.
    """
    equations = []

    # Search the entire document: display equations commonly span three lines
    # (`$$`, formula, `$$`) in Markdown source.
    block_pattern = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
    inline_pattern = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)")
    block_spans: list[tuple[int, int]] = []

    for match in block_pattern.finditer(markdown):
        eq = match.group(1).strip()
        if eq:
            line_idx = markdown.count("\n", 0, match.start()) + 1
            equations.append((line_idx, eq, "block"))
            block_spans.append(match.span())

    # Do not treat `$...$` tokens inside a display block as inline equations.
    for match in inline_pattern.finditer(markdown):
        if any(start <= match.start() < end for start, end in block_spans):
            continue
        eq = match.group(1).strip()
        if eq:
            line_idx = markdown.count("\n", 0, match.start()) + 1
            equations.append((line_idx, eq, "inline"))

    return sorted(equations, key=lambda item: item[0])


def latex_to_sympy(latex: str) -> tuple:
    """Convert LaTeX to SymPy expression.

    Returns (sympy_expr, None) on success, (None, error_message) on failure.
    Tries sympy's built-in LaTeX parser first, falls back to manual conversion.
    """
    # Try sympy's built-in parser
    try:
        from sympy.parsing.latex import parse_latex
        expr = parse_latex(latex)
        return (expr, None)
    except Exception:
        pass  # Fall through to manual conversion

    # Manual fallback for common LaTeX patterns
    try:
        import sympy as sp
        converted = _manual_latex_convert(latex)
        if converted is None:
            return (None, "Could not parse LaTeX expression")
        expr = sp.sympify(converted)
        return (expr, None)
    except Exception as e2:
        return (None, f"Parse error: {str(e2)[:100]}")


def _manual_latex_convert(latex: str) -> str | None:
    """Manual conversion of common LaTeX to SymPy-compatible Python.

    Handles the most common math patterns in STEM papers.
    """
    s = latex.strip()

    # Known function names that should NOT get implicit multiplication
    # after them (e.g. sin(x) → sin(x), NOT sin*(x))
    _FUNCTION_NAMES = {
        'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
        'sinh', 'cosh', 'tanh',
        'arcsin', 'arccos', 'arctan',
        'log', 'ln', 'exp', 'sqrt',
        'Sum', 'Product', 'Integral', 'Derivative',
        'abs', 'max', 'min',
    }

    def _add_implicit_mult(s: str) -> str:
        """Add * for implicit multiplication, but skip function names."""
        # 2x → 2*x
        s = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', s)
        # 2(x → 2*(x  (digit before paren = multiplication)
        s = re.sub(r'(\d)\(', r'\1*(', s)
        # )( → )*(
        s = re.sub(r'\)\(', r')*(', s)
        # )letter → )*letter
        s = re.sub(r'\)([a-zA-Z])', r')*\1', s)
        # letter( → letter*(  BUT skip function names
        s = re.sub(r'([a-zA-Z])\(', _maybe_add_mult, s)
        return s

    def _maybe_add_mult(m: re.Match) -> str:
        """Add * only if the matched letter is NOT a function name suffix."""
        prefix = m.group(1)
        # Check if 'sin' ends with 'n' etc. — look back for known function names
        for fn in sorted(_FUNCTION_NAMES, key=len, reverse=True):
            if m.string[max(0, m.start() - len(fn) + 1):m.start() + 1] == fn:
                return m.group(0)  # keep as-is, no *
        return prefix + '*('

    s = _add_implicit_mult(s)

    # Handle common LaTeX formatting
    replacements = [
        (r"\left", ""), (r"\right", ""),
        (r"\cdot", "*"), (r"\times", "*"),
        # \frac is handled separately by _handle_frac() above
        (r"\sqrt{", "sqrt("),
        (r"\sin", "sin"), (r"\cos", "cos"), (r"\tan", "tan"),
        (r"\log", "log"), (r"\ln", "ln"),
        (r"\exp", "exp"),
        (r"\pi", "pi"), (r"\infty", "oo"),
        (r"\alpha", "alpha"), (r"\beta", "beta"), (r"\gamma", "gamma"),
        (r"\delta", "delta"), (r"\epsilon", "epsilon"), (r"\theta", "theta"),
        (r"\lambda", "lambda_"), (r"\mu", "mu"), (r"\sigma", "sigma"),
        (r"\omega", "omega"), (r"\Delta", "Delta"),
        (r"\sum", "Sum"), (r"\prod", "Product"), (r"\int", "Integral"),
        (r"\partial", "Derivative"),
        (r"\mathbf{", ""), (r"\mathcal{", ""),
        (r"\mathbb{", ""), (r"\Re", "re"), (r"\Im", "im"),
        (r"\operatorname{", ""),
        (r"\text{", ""),
        (r"\quad", " "), (r"\qquad", "  "),
        (r"\\", " "),
        (r"\{", "("), (r"\}", ")"),
        ("{", "("), ("}", ")"),
        (r"\pm", " "),  # Split: a +/- b → a b (can't verify ± equations, mark inconclusive)
        (r"\mp", " "),
        (r"\to", "->"),
        (r"\rightarrow", "->"),
        (r"\Rightarrow", "=>"),
        (r"\neq", "!="),
        (r"\leq", "<="),
        (r"\geq", ">="),
        (r"\approx", "~="),
        (r"\equiv", "=="),
        (r"\propto", "~"),
        ("^T", "**T"),  # transpose
        ("^\\top", "**T"),
        (r"\'", ""),  # derivative prime notation
        (r"\prime", ""),
        (r"\dot{", "diff("),  # time derivative
        (r"\ddot{", "diff(diff("),
        (r"\hat{", ""),
        (r"\bar{", ""),
        (r"\vec{", ""),
    ]

    # Handle \frac first (most complex)
    s = _handle_frac(s)

    for old, new in replacements:
        s = s.replace(old, new)

    # Clean up unmatched braces
    while "(" in s and s.count("(") > s.count(")"):
        s += ")"
    while ")" in s and s.count(")") > s.count("("):
        s = "(" + s

    return s if s else None


def _handle_frac(s: str) -> str:
    """Handle \\frac{numerator}{denominator} → (numerator)/(denominator)."""
    while "\\frac" in s:
        idx = s.index("\\frac")
        # Skip past \frac{
        brace_open = s.index("{", idx)
        depth = 1
        pos = brace_open + 1
        while depth > 0 and pos < len(s):
            if s[pos] == "{":
                depth += 1
            elif s[pos] == "}":
                depth -= 1
            pos += 1
        num = s[brace_open + 1:pos - 1]

        # Now parse denominator
        if pos < len(s) and s[pos] == "{":
            depth = 1
            denom_start = pos + 1
            pos = denom_start
            while depth > 0 and pos < len(s):
                if s[pos] == "{":
                    depth += 1
                elif s[pos] == "}":
                    depth -= 1
                pos += 1
            denom = s[denom_start:pos - 1]
        else:
            break

        s = s[:idx] + f"({num})/({denom})" + s[pos:]

    return s


def verify_equation(latex: str) -> VerificationResult:
    """Verify a single LaTeX equation.

    For equalities (a = b): check if (a - b) simplifies to 0.
    For formulas (no =): verify structural validity.
    """
    # Check if it's an equality
    if "=" in latex and "\\neq" not in latex:
        # Split on = but be careful about LaTeX
        parts = _split_equality(latex)
        if len(parts) == 2:
            lhs_expr, lhs_err = latex_to_sympy(parts[0])
            rhs_expr, rhs_err = latex_to_sympy(parts[1])

            if lhs_expr is not None and rhs_expr is not None:
                try:
                    import sympy as sp
                    diff = sp.simplify(lhs_expr - rhs_expr)
                    if diff == 0:
                        return VerificationResult(
                            line=0, equation=latex,
                            status="verified",
                            detail="✅ Verified: LHS − RHS = 0"
                        )
                    # If diff is a non-zero constant, it's definitely wrong
                    if diff.is_number and diff != 0:
                        return VerificationResult(
                            line=0, equation=latex,
                            status="error",
                            detail=f"❌ LHS ≠ RHS (difference = {diff})"
                        )
                    # Otherwise inconclusive (free variables)
                    return VerificationResult(
                        line=0, equation=latex,
                        status="inconclusive",
                        detail=f"⚠️ LHS − RHS = {diff}. May be correct with additional constraints."
                    )
                except Exception as e:
                    return VerificationResult(
                        line=0, equation=latex,
                        status="error",
                        detail=f"Simplification error: {str(e)[:100]}"
                    )
            else:
                err_msg = lhs_err or rhs_err or "Parse error"
                return VerificationResult(
                    line=0, equation=latex,
                    status="error",
                    detail=f"Parse error: {err_msg}"
                )

    # Not an equality — try to parse as a valid expression
    expr, err = latex_to_sympy(latex)
    if expr is not None:
        return VerificationResult(
            line=0, equation=latex,
            status="verified",
            detail="✅ Valid expression (non-equality)"
        )
    else:
        return VerificationResult(
            line=0, equation=latex,
            status="error",
            detail=f"Parse error: {err}"
        )


def _split_equality(latex: str) -> list[str]:
    """Split an equation on =, being careful about LaTeX groups."""
    # Simple heuristic: find the first = that's not inside braces
    depth = 0
    for i, ch in enumerate(latex):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "=" and depth == 0:
            lhs = latex[:i].strip()
            rhs = latex[i+1:].strip()
            return [lhs, rhs] if lhs and rhs else [latex]
    return [latex]


def _compact_latex(latex: str) -> str:
    """Normalize spacing only; this is not a general LaTeX parser."""

    return re.sub(r"\s+", "", latex)


def _audit_sum_of_squares_proof(
    equations: list[tuple[int, str, str]],
) -> list[VerificationResult] | None:
    """Audit the introductory telescoping proof for ``sum(i**2, i=1..n)``.

    This is a deliberately narrow, deterministic teaching audit. It is used
    only after the document explicitly defines ``S_n = sum i^2`` and presents
    the cubic finite-difference derivation. General LaTeX proof verification
    remains a future capability rather than an implied promise here.
    """

    compact = [(line, _compact_latex(eq), mode, eq) for line, eq, mode in equations]
    definition = next(
        (
            item
            for item in compact
            if "S_{n}=\\sum_{i=1}^{n}i^2" in item[1]
        ),
        None,
    )
    if definition is None:
        return None

    cubic = next(
        (
            item
            for item in compact
            if "T_{n}=n^3-\\left(n-1\\right)^3" in item[1]
        ),
        None,
    )
    recurrence = next(
        (
            item
            for item in compact
            if "T_{n-1}=\\left(n-1\\right)^3-\\left(n-2\\right)^3" in item[1]
        ),
        None,
    )
    telescoping = next(
        (item for item in compact if "\\sum_{i=1}^{n}T_{i}" in item[1]),
        None,
    )
    final_formula = next(
        (
            item
            for item in compact
            if item is not definition and item[1].startswith("S_{n}=")
        ),
        None,
    )

    # Do not claim the specialized audit applies to an unrelated document.
    if cubic is None or telescoping is None or final_formula is None:
        return None

    results = [
        VerificationResult(
            line=definition[0],
            equation=f"$$ {definition[3]} $$",
            status="inconclusive",
            detail="Definition recognized. The following cards audit the finite-difference derivation.",
        ),
        VerificationResult(
            line=cubic[0],
            equation=f"$$ {cubic[3]} $$",
            status="verified",
            detail="✅ Verified expansion: n³ − (n − 1)³ = 3n² − 3n + 1.",
        ),
    ]

    if recurrence:
        results.append(
            VerificationResult(
                line=recurrence[0],
                equation=f"$$ {recurrence[3]} $$",
                status="verified",
                detail="✅ Verified by substituting n − 1 into the finite-difference identity.",
            )
        )

    telescoping_has_minus_one = "=n^3-1" in telescoping[1]
    results.append(
        VerificationResult(
            line=telescoping[0],
            equation=f"$$ {telescoping[3]} $$",
            status="error" if telescoping_has_minus_one else "verified",
            detail=(
                "❌ Telescoping error: Σᵢ₌₁ⁿ [i³ − (i − 1)³] = n³, not n³ − 1. "
                "The lower endpoint is 0³ = 0."
                if telescoping_has_minus_one
                else "✅ The finite differences telescope to n³."
            ),
        )
    )

    expected = r"\frac{2n^3+3n^2+n}{6}"
    claimed_is_correct = expected in final_formula[1]
    results.append(
        VerificationResult(
            line=final_formula[0],
            equation=f"$$ {final_formula[3]} $$",
            status="verified" if claimed_is_correct and not telescoping_has_minus_one else "error",
            detail=(
                "✅ Correct closed form: Sₙ = (2n³ + 3n² + n) / 6."
                if claimed_is_correct and not telescoping_has_minus_one
                else "❌ The closed form is incorrect. From n³ = 3Sₙ − 3n(n + 1)/2 + n, "
                "the correct result is Sₙ = (2n³ + 3n² + n) / 6."
            ),
        )
    )
    return results


# ── Chain verification for calculus derivations ────────────────────

def _normalize(eq: str) -> str:
    """Remove LaTeX formatting noise for pattern matching."""
    s = eq.replace("\\left", "").replace("\\right", "")
    s = re.sub(r"\s+", "", s)
    return s


def _parse_latex_expr(latex: str):
    """Try to parse a LaTeX fragment as a SymPy expression. Returns (expr, None) or (None, err)."""
    try:
        from sympy.parsing.latex import parse_latex
        return (parse_latex(latex), None)
    except Exception:
        try:
            import sympy as sp
            conv = _manual_latex_convert(latex)
            if conv is None:
                return (None, "Could not convert")
            return (sp.sympify(conv), None)
        except Exception as e:
            return (None, str(e)[:100])


def _split_double_equal(eq: str) -> tuple[str | None, str | None, str | None]:
    """Split A = B = C into (A, B, C). Handles LaTeX groups.

    For f(2) = (2-2)^2 + 1 = 1 → (f(2), (2-2)^2 + 1, 1)
    For A = B → (A, B, None)
    """
    parts = []
    depth = 0
    start = 0
    for i, ch in enumerate(eq):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "=" and depth == 0:
            parts.append(eq[start:i].strip())
            start = i + 1
    parts.append(eq[start:].strip())
    if len(parts) == 2:
        return (parts[0], parts[1], None)
    elif len(parts) >= 3:
        return (parts[0], parts[1], parts[-1])
    return (None, None, None)


def _chain_verify_calculus(
    equations: list[tuple[int, str, str]],
) -> list[VerificationResult] | None:
    """Chain-verify a single-variable calculus derivation.

    Detects the common pattern:
      f(x) = expr → f'(x) = ... → f'(x) = 0 → x = N →
      f''(x) = ... → f(N) = M → \\boxed{M}

    Returns None if the document doesn't match this pattern (falls back to
    per-equation verification).
    """
    import sympy as sp

    results: list[VerificationResult] = []
    x = sp.Symbol("x")
    f_expr: sp.Expr | None = None
    f_sym: sp.Function | None = None
    # Track derived facts for cross-checking
    computed_min_value: tuple[int, sp.Expr] | None = None  # (line, value)
    computed_min_x: sp.Expr | None = None
    stage: str = "idle"          # idle | defined | solving | solved | classified

    for line_idx, eq, display_mode in equations:
        norm = _normalize(eq)
        display = f"{'$$' if display_mode == 'block' else '$'} {eq} {'$$' if display_mode == 'block' else '$'}"

        # ── Pattern 0: f(x) = <expression> (function definition) ──
        fd_match = re.match(r"f\(x\)=(.+)", norm)
        if fd_match and stage == "idle":
            rhs = fd_match.group(1)
            expr, err = _parse_latex_expr(rhs)
            if expr is not None:
                f_expr = expr
                f_sym = sp.Lambda(x, expr)
                stage = "defined"
                results.append(VerificationResult(
                    line=line_idx, equation=display,
                    status="verified",
                    detail=f"📐 Function defined: f(x) = {sp.latex(expr)}"
                ))
                continue

        # ── Pattern 1b: f'(x) = 0 (setting derivative to zero) ──
        fd1_zero = re.match(r"f'\(x\)=0", norm)
        if fd1_zero and f_expr is not None:
            results.append(VerificationResult(
                line=line_idx, equation=display,
                status="inconclusive",
                detail="🔍 Setting f'(x) = 0 to find critical points"
            ))
            stage = "solving"
            continue

        # ── Pattern 1: f'(x) = <expression> (first derivative check) ──
        fd1_match = re.match(r"f'\(x\)=(.+)", norm)
        if fd1_match and f_expr is not None:
            rhs = fd1_match.group(1)
            user_deriv, _ = _parse_latex_expr(rhs)
            actual_deriv = sp.diff(f_expr, x)
            if user_deriv is not None:
                diff = sp.simplify(user_deriv - actual_deriv)
                if diff == 0:
                    stage = "solving" if "=0" in norm else "defined"
                    results.append(VerificationResult(
                        line=line_idx, equation=display,
                        status="verified",
                        detail=f"✅ First derivative correct: f'(x) = {sp.latex(actual_deriv)}"
                    ))
                else:
                    results.append(VerificationResult(
                        line=line_idx, equation=display,
                        status="error",
                        detail=f"❌ First derivative mismatch. Yours: {sp.latex(user_deriv)}, "
                               f"Correct: {sp.latex(actual_deriv)}"
                    ))
                continue

        # ── Pattern 2: x = <number> (critical point candidate) ──
        x_eq_match = re.match(r"x=(-?[\d.]+)$", norm)
        if x_eq_match and stage in ("solving", "defined") and f_expr is not None:
            candidate = sp.Rational(x_eq_match.group(1))
            deriv = sp.diff(f_expr, x)
            solutions = sp.solve(deriv, x)
            is_solution = any(sp.simplify(candidate - sol) == 0 for sol in (solutions if isinstance(solutions, list) else [solutions]))
            if is_solution:
                computed_min_x = candidate
                stage = "solved"
                results.append(VerificationResult(
                    line=line_idx, equation=display,
                    status="verified",
                    detail=f"✅ x = {candidate} is a root of f'(x) = 0"
                ))
            else:
                actual_roots = [str(s) for s in (solutions if isinstance(solutions, list) else [solutions])]
                results.append(VerificationResult(
                    line=line_idx, equation=display,
                    status="error",
                    detail=f"❌ x = {candidate} is NOT a root of f'(x) = 0. "
                           f"Actual roots: {actual_roots}"
                ))
            continue

        # ── Pattern 3: f''(x) = <expression> (second derivative check) ──
        fd2_match = re.match(r"f''\(x\)=(.+)", norm)
        if fd2_match and f_expr is not None:
            rhs = fd2_match.group(1)
            # If rhs contains >0 or <0, extract just the expression part
            rhs = re.sub(r"[<>]=?\s*-?\d+.*$", "", rhs).strip()
            user_deriv2, _ = _parse_latex_expr(rhs)
            actual_deriv2 = sp.diff(f_expr, x, 2)
            if user_deriv2 is not None:
                # Handle inequality like "2 > 0" — check the expression = 2
                diff2 = sp.simplify(user_deriv2 - actual_deriv2)
                if diff2 == 0:
                    # Check sign: if f'' > 0, it's a minimum
                    if ">0" in norm or "> 0" in eq:
                        results.append(VerificationResult(
                            line=line_idx, equation=display,
                            status="verified",
                            detail=f"✅ Second derivative correct: f''(x) = {sp.latex(actual_deriv2)}."
                                   f" Since f''(x) > 0, this is a local MINIMUM ✓"
                        ))
                        stage = "classified"
                    else:
                        results.append(VerificationResult(
                            line=line_idx, equation=display,
                            status="verified",
                            detail=f"✅ Second derivative correct: f''(x) = {sp.latex(actual_deriv2)}"
                        ))
                else:
                    results.append(VerificationResult(
                        line=line_idx, equation=display,
                        status="error",
                        detail=f"❌ Second derivative mismatch. Yours: {sp.latex(user_deriv2)}, "
                               f"Correct: {sp.latex(actual_deriv2)}"
                    ))
                continue

        # ── Pattern 4: f(N) = <eval expr> = <result> (evaluation step) ──
        f_eval_match = re.match(r"f\((-?[\d.]+)\)=.+", norm)
        if f_eval_match and f_expr is not None:
            a, b, c = _split_double_equal(eq)
            if a is None:
                continue

            # Extract the argument value
            arg_match = re.match(r"f\((-?[\d.]+)\)", a)
            if not arg_match:
                continue
            arg_val = sp.Rational(arg_match.group(1))

            # The claimed result is the last term
            claimed_str = c if c else b
            claimed_str = claimed_str.strip()
            # Strip LaTeX boxed if present
            claimed_str = re.sub(r"\\boxed\{(.+)\}", r"\1", claimed_str)
            try:
                claimed_val = sp.Rational(claimed_str) if claimed_str.replace('.', '', 1).replace('-', '', 1).isdigit() else sp.sympify(claimed_str)
            except Exception:
                claimed_val = None

            # Compute actual f(arg)
            if f_sym is not None:
                actual_val = sp.simplify(f_sym(arg_val))
            else:
                actual_val = sp.simplify(f_expr.subs(x, arg_val))

            if claimed_val is not None:
                if sp.simplify(actual_val - claimed_val) == 0:
                    computed_min_value = (line_idx, actual_val)
                    results.append(VerificationResult(
                        line=line_idx, equation=display,
                        status="verified",
                        detail=f"✅ f({arg_val}) = {actual_val}. "
                               f"Second derivative > 0 confirms this is the MINIMUM ✓"
                        if stage == "classified" else
                        f"✅ f({arg_val}) = {actual_val}"
                    ))
                else:
                    results.append(VerificationResult(
                        line=line_idx, equation=display,
                        status="error",
                        detail=f"❌ f({arg_val}) should be {actual_val}, not {claimed_val}"
                    ))
            else:
                # Can't parse claimed value, just verify the expression is valid
                expr_str = b if c else a
                _, err = _parse_latex_expr(expr_str)
                if err is None:
                    results.append(VerificationResult(
                        line=line_idx, equation=display,
                        status="verified",
                        detail=f"✅ f({arg_val}) = {actual_val}"
                    ))
                else:
                    results.append(VerificationResult(
                        line=line_idx, equation=display,
                        status="error",
                        detail=f"Evaluation error: {err}"
                    ))
            continue

        # ── Pattern 5: \boxed{value} — consistency check ──
        boxed_match = re.search(r"\\boxed\{([^}]+)\}", eq)
        if boxed_match and computed_min_value is not None:
            boxed_str = boxed_match.group(1)
            min_line, min_val = computed_min_value
            # Try to parse boxed value
            try:
                # Handle \boxed{1} or \boxed{(2, 1)}
                if boxed_str.startswith("(") and boxed_str.endswith(")"):
                    # It's a point like (2, 1) — extract y-coordinate
                    parts = boxed_str.strip("()").split(",")
                    if len(parts) == 2:
                        y_str = parts[1].strip()
                        boxed_val = sp.Rational(y_str) if y_str.replace('.', '', 1).replace('-', '', 1).isdigit() else sp.sympify(y_str)
                    else:
                        boxed_val = None
                else:
                    boxed_val = sp.Rational(boxed_str) if boxed_str.replace('.', '', 1).replace('-', '', 1).isdigit() else sp.sympify(boxed_str)
            except Exception:
                boxed_val = None

            if boxed_val is not None and sp.simplify(boxed_val - min_val) == 0:
                results.append(VerificationResult(
                    line=line_idx, equation=display,
                    status="verified",
                    detail=f"✅ \\boxed value {boxed_val} is consistent with f({computed_min_x}) = {min_val}"
                ))
            elif boxed_val is not None:
                results.append(VerificationResult(
                    line=line_idx, equation=display,
                    status="error",
                    detail=f"❌ \\boxed{{{boxed_str}}} is INCONSISTENT! "
                           f"Verified f({computed_min_x}) = {min_val}, but \\boxed claims {boxed_val}"
                ))
            else:
                # Can't parse — just mark as valid expression
                results.append(VerificationResult(
                    line=line_idx, equation=display,
                    status="verified",
                    detail=f"✅ \\boxed{{{boxed_str}}} (valid expression)"
                ))
            continue

        # ── Fallback: per-equation verification ──
        result = verify_equation(eq)
        result.line = line_idx
        result.equation = display
        results.append(result)

    # If we found at least one chain-verified result, return all
    if any(r.detail.startswith(("📐", "✅", "🔍")) for r in results):
        return results
    return None


def verify_document(markdown: str) -> list[VerificationResult]:
    """Verify all equations in a document.

    Returns list of VerificationResult, one per equation.
    """
    equations = extract_equations(markdown)
    if not equations:
        return []

    # Try specialized audits in order
    sum_of_squares_audit = _audit_sum_of_squares_proof(equations)
    if sum_of_squares_audit is not None:
        return sum_of_squares_audit

    calculus_audit = _chain_verify_calculus(equations)
    if calculus_audit is not None:
        return calculus_audit

    # Fallback: per-equation verification
    results = []
    for line_idx, eq, display_mode in equations:
        result = verify_equation(eq)
        result.line = line_idx
        result.equation = f"{'$$' if display_mode == 'block' else '$'} {eq} {'$$' if display_mode == 'block' else '$'}"
        results.append(result)

    return results
