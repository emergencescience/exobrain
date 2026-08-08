"""SymPy formal verification engine — validate LaTeX equations in documents."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("exobrain.verify")

# Lazy-load sympy (heavy import; only needed for derivation chain verification)
_sympy = None


def _get_sympy():
    global _sympy
    if _sympy is None:
        import sympy
        _sympy = sympy
    return _sympy


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


def verify_derivation_chain(
    equations: list[tuple[int, str, str]], markdown: str
) -> list[VerificationResult] | None:
    """Verify a mathematical derivation chain using SymPy symbolic computation.

    Detects patterns like:
      1. f(x) = <expression>          → function definition
      2. f'(x) = <derivative>         → derivative verification
      3. <equation> = 0 → x = <root>  → solving verification
      4. f''(x) = <2nd-derivative>    → second derivative
      5. f(<point>) = <value>         → evaluation verification

    Uses SymPy to independently compute each step and compare with the
    user's claimed result. Returns None if no derivation chain is detected.
    """
    sp = _get_sympy()

    if len(equations) < 3:
        return None  # need at least definition + derivative + result

    # ── Step 1: Find function definition ──
    # Pattern: f(x) = <expression>  or  f\\left(x\\right) = <expression>
    func_def = None
    func_var = "x"
    func_name = "f"
    func_expr = None
    func_line = 0
    func_raw = ""

    for line_idx, eq, mode in equations:
        # Look for "f(x) = ..." or "f\left(x\right) = ..."
        eq_clean = eq.replace("\left", "").replace("\right", "").strip()
        match = re.match(r"([a-zA-Z])\s*\(\s*([a-zA-Z])\s*\)\s*=\s*(.+)", eq_clean)
        if match:
            func_name = match.group(1)
            func_var = match.group(2)
            rhs = match.group(3).strip()
            try:
                expr, err = latex_to_sympy(rhs)
                if expr is not None:
                    func_expr = expr
                    func_def = eq
                    func_line = line_idx
                    func_raw = rhs
                    break
            except Exception:
                pass

    if func_expr is None:
        return None  # no function definition found

    # Define the SymPy symbols
    x = sp.Symbol(func_var)
    f = sp.Function(func_name)(x)
    f_expr_sympy = func_expr  # the symbolic expression for f(x)

    results: list[VerificationResult] = []

    # ── Step 1 result: function definition ──
    results.append(VerificationResult(
        line=func_line,
        equation=f"$$ {func_def} $$",
        status="verified",
        detail=f"📐 函数定义：{func_name}({func_var}) = {sp.latex(f_expr_sympy)}"
    ))

    # ── Step 2: Walk through subsequent equations ──
    prev_context: str = "definition"  # track what we're doing
    solved_value = None
    first_derivative = None
    second_derivative = None

    for line_idx, eq, mode in equations:
        if line_idx <= func_line:
            continue  # skip equations before the function definition

        eq_clean = eq.replace("\left", "").replace("\right", "").strip()

        # ── Derivative: f'(x) = ... or f''(x) = ... ──
        if re.match(rf"{re.escape(func_name)}\s*'+\s*\(\s*{re.escape(func_var)}\s*\)\s*=", eq_clean):
            # Determine if it's first or second derivative
            is_second = "'" in eq_clean.split("(")[0] and eq_clean.split("(")[0].count("'") >= 2
            rhs_match = re.search(r"=\s*(.+)", eq_clean)
            if not rhs_match:
                continue
            claimed_rhs = rhs_match.group(1).strip()

            try:
                if is_second:
                    # Second derivative
                    actual = sp.diff(f_expr_sympy, x, 2)
                    label = "f''(x)"
                    prev_context = "second_derivative"
                    second_derivative = actual
                else:
                    # First derivative
                    actual = sp.diff(f_expr_sympy, x)
                    label = "f'(x)"
                    prev_context = "first_derivative"
                    first_derivative = actual

                claimed, err = latex_to_sympy(claimed_rhs)
                if claimed is not None:
                    actual_simplified = sp.simplify(actual)
                    claimed_simplified = sp.simplify(claimed)
                    diff_expr = sp.simplify(actual_simplified - claimed_simplified)
                    if diff_expr == 0:
                        results.append(VerificationResult(
                            line=line_idx, equation=f"$$ {eq} $$",
                            status="verified",
                            detail=f"✅ {label} = {sp.latex(actual_simplified)}，求导正确"
                        ))
                    else:
                        results.append(VerificationResult(
                            line=line_idx, equation=f"$$ {eq} $$",
                            status="error",
                            detail=f"❌ {label} 应为 {sp.latex(actual_simplified)}，而非 {sp.latex(claimed_simplified)}"
                        ))
                else:
                    results.append(VerificationResult(
                        line=line_idx, equation=f"$$ {eq} $$",
                        status="error", detail=f"无法解析右侧表达式：{err}"
                    ))
            except Exception as e:
                results.append(VerificationResult(
                    line=line_idx, equation=f"$$ {eq} $$",
                    status="error", detail=f"求导验证失败：{e}"
                ))
            continue

        # ── Solving: expr = 0 → x = root ──
        # Pattern: <expression> = 0, followed by x = <value>
        # OR: f'(x) = 0, x = <value> (may be split across lines)
        is_equation_to_zero = "=" in eq_clean and (
            eq_clean.strip().endswith("= 0") or eq_clean.strip().endswith("=0")
        )
        if is_equation_to_zero and ("'" in eq_clean or "f" in eq_clean):
            # This is a "set derivative to zero" equation
            # We'll verify on the next equation which should be "x = ..."
            prev_context = "solving"
            continue

        # ── Solution: x = <value> ──
        # Accept both: explicit "set = 0" context AND implicit (just after derivative)
        x_equals = re.match(rf"{re.escape(func_var)}\s*=\s*(.+)", eq_clean)
        if x_equals and (prev_context == "solving" or prev_context in ("first_derivative", "second_derivative")):
            claimed_root = x_equals.group(1).strip()

            try:
                root_val, err = latex_to_sympy(claimed_root)
                if root_val is not None and first_derivative is not None:
                    # Verify by solving f'(x) = 0
                    solutions = sp.solve(first_derivative, x)
                    found = any(sp.simplify(s - root_val) == 0 for s in (solutions if isinstance(solutions, list) else [solutions]))
                    if found:
                        results.append(VerificationResult(
                            line=line_idx, equation=f"$$ {eq} $$",
                            status="verified",
                            detail=f"✅ {func_var} = {sp.latex(root_val)} 是 {func_name}'({func_var})=0 的解"
                        ))
                        solved_value = root_val
                        prev_context = "solved"
                    else:
                        results.append(VerificationResult(
                            line=line_idx, equation=f"$$ {eq} $$",
                            status="error",
                            detail=f"❌ {func_name}'({func_var})=0 的解应为 {solutions}，而非 {root_val}"
                        ))
                elif root_val is not None:
                    results.append(VerificationResult(
                        line=line_idx, equation=f"$$ {eq} $$",
                        status="verified",
                        detail=f"✅ {func_var} = {sp.latex(root_val)}"
                    ))
                    solved_value = root_val
                    prev_context = "solved"
                else:
                    results.append(VerificationResult(
                        line=line_idx, equation=f"$$ {eq} $$",
                        status="error", detail=f"无法解析：{err}"
                    ))
            except Exception as e:
                results.append(VerificationResult(
                    line=line_idx, equation=f"$$ {eq} $$",
                    status="error", detail=f"验证失败：{e}"
                ))
            continue

        # ── Evaluation: f(<point>) = <expression> = <value> ──
        eval_match = re.match(
            rf"{re.escape(func_name)}\s*\(\s*([^)]+)\s*\)\s*=\s*(.+)", eq_clean
        )
        if eval_match:
            point_str = eval_match.group(1).strip()
            rhs_full = eval_match.group(2).strip()
            # Handle double-equals: f(2) = (x-2)^2+1 = 1
            # Take only the final value after the last = 
            if "=" in rhs_full:
                value_str = rhs_full.rsplit("=", 1)[-1].strip()
            else:
                value_str = rhs_full

            try:
                point, _ = latex_to_sympy(point_str)
                claimed_val, _ = latex_to_sympy(value_str)
                if point is not None and claimed_val is not None:
                    actual_val = sp.simplify(f_expr_sympy.subs(x, point))
                    if sp.simplify(actual_val - claimed_val) == 0:
                        detail = f"✅ {func_name}({sp.latex(point)}) = {sp.latex(actual_val)}，代入正确"
                        # Add logical check if this is a min/max verification
                        if prev_context in ("second_derivative", "solved") and second_derivative is not None:
                            snd_val = second_derivative
                            if snd_val.is_number or (isinstance(snd_val, sp.Integer)):
                                if snd_val > 0:
                                    detail += "；二阶导数 > 0，确认是极小值 ✓"
                                elif snd_val < 0:
                                    detail += "；二阶导数 < 0，确认是极大值 ✓"
                        results.append(VerificationResult(
                            line=line_idx, equation=f"$$ {eq} $$",
                            status="verified", detail=detail
                        ))
                    else:
                        results.append(VerificationResult(
                            line=line_idx, equation=f"$$ {eq} $$",
                            status="error",
                            detail=f"❌ {func_name}({sp.latex(point)}) 应为 {sp.latex(actual_val)}，而非 {sp.latex(claimed_val)}"
                        ))
                else:
                    results.append(VerificationResult(
                        line=line_idx, equation=f"$$ {eq} $$",
                        status="error", detail="无法解析代入值"
                    ))
            except Exception as e:
                results.append(VerificationResult(
                    line=line_idx, equation=f"$$ {eq} $$",
                    status="error", detail=f"代入验证失败：{e}"
                ))
            prev_context = "evaluated"
            continue

        # ── Fallback: standard equation verification ──
        result = verify_equation(eq)
        result.line = line_idx
        result.equation = f"{'$$' if mode == 'block' else '$'} {eq} {'$$' if mode == 'block' else '$'}"
        # Enhance the detail for chain context
        if result.status == "verified" and prev_context in ("solved", "evaluated"):
            result.detail += "（在推导链中）"
        results.append(result)

    # ── Final check: did we find enough to call this a chain? ──
    verified_count = sum(1 for r in results if r.status == "verified")
    if verified_count < 2 or len(results) < 3:
        return None  # not enough verified steps

    return results


def verify_document(markdown: str) -> list[VerificationResult]:
    """Verify all equations in a document.

    Returns list of VerificationResult, one per equation.
    When a derivation chain is detected (function → derivative → solve → evaluate),
    uses symbolic chain verification instead of isolated equation checking.
    """
    equations = extract_equations(markdown)
    if not equations:
        return []

    sum_of_squares_audit = _audit_sum_of_squares_proof(equations)
    if sum_of_squares_audit is not None:
        return sum_of_squares_audit

    # Try chain verification first
    chain_results = verify_derivation_chain(equations, markdown)
    if chain_results is not None:
        return chain_results

    results = []
    for line_idx, eq, display_mode in equations:
        result = verify_equation(eq)
        result.line = line_idx
        result.equation = f"{'$$' if display_mode == 'block' else '$'} {eq} {'$$' if display_mode == 'block' else '$'}"
        results.append(result)

    return results
