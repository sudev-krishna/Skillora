"""
Skillora Algorithmic Profiler: Canonical Big-O Classifier (server/profiler/canonical_order.py)
Eliminates SymPy log(1/n) artifacts via asymptotic limit evaluation against standard classes.
Zero third-party dependencies (SymPy + standard library only).
"""

from typing import Optional, Union
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
)

_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)

_CANONICAL_CLASSES = [
    ("O(1)", sp.Integer(1)),
    ("O(log n)", sp.log(sp.Symbol("n", positive=True))),
    ("O(sqrt(n))", sp.sqrt(sp.Symbol("n", positive=True))),
    ("O(n)", sp.Symbol("n", positive=True)),
    ("O(n log n)", sp.Symbol("n", positive=True) * sp.log(sp.Symbol("n", positive=True))),
    ("O(n^2)", sp.Symbol("n", positive=True) ** 2),
    ("O(n^2 log n)", (sp.Symbol("n", positive=True) ** 2) * sp.log(sp.Symbol("n", positive=True))),
    ("O(n^3)", sp.Symbol("n", positive=True) ** 3),
    ("O(2^n)", 2 ** sp.Symbol("n", positive=True)),
]


def clean_decaying_terms(expr: sp.Expr, symbol: sp.Symbol) -> sp.Expr:
    """
    Prunes geometric decay terms (base**n where |base| < 1) that cause
    Gruntz algorithm NotImplementedError in SymPy limit evaluation.
    E.g. In Fibonacci, ((1 - sqrt(5))/2)^n where base ~ -0.618 < 1.
    """
    try:
        expr_expanded = sp.expand(expr)
        if not expr_expanded.is_Add:
            return expr_expanded

        cleaned_terms = []
        for term in expr_expanded.as_ordered_terms():
            powers = [p for p in term.atoms(sp.Pow) if p.exp == symbol]
            decaying = False
            for p in powers:
                try:
                    val = float(sp.Abs(p.base).evalf())
                    if val < 1.0:
                        decaying = True
                        break
                except Exception:
                    pass
            if not decaying:
                cleaned_terms.append(term)
        return sp.Add(*cleaned_terms) if cleaned_terms else expr_expanded
    except Exception:
        return expr


def canonicalize_big_o(expr: Union[sp.Expr, str, int, float], symbol_n: Optional[sp.Symbol] = None) -> str:
    """
    Computes the canonical Big-O string for a given expression using limit comparison.

    Parameters:
        expr: SymPy expression, string formula, or numeric constant.
        symbol_n: SymPy symbol representing input size n (default: Symbol('n', positive=True)).

    Returns:
        Canonical Big-O string (e.g. 'O(1)', 'O(log n)', 'O(sqrt(n))', 'O(n)', 'O(n log n)', 'O(n^2)', 'O(2^n)').
    """
    if symbol_n is None:
        symbol_n = sp.Symbol("n", positive=True)

    if isinstance(expr, (int, float)):
        return "O(1)"

    if isinstance(expr, str):
        expr_clean = expr.replace("^", "**").strip()
        try:
            expr = parse_expr(
                expr_clean,
                local_dict={"n": symbol_n, "log": sp.log, "sqrt": sp.sqrt},
                transformations=_TRANSFORMATIONS,
            )
        except Exception:
            return "Unknown"

    if not isinstance(expr, sp.Expr):
        return "Unknown"

    # Prune decaying geometric terms (e.g. ((1-sqrt(5))/2)^n in Fibonacci)
    expr_cleaned = clean_decaying_terms(expr, symbol_n)

    # Stage 1: Exact Theta match (finite strictly positive limit)
    for label, ref in _CANONICAL_CLASSES:
        ref_sym = ref.subs(sp.Symbol("n", positive=True), symbol_n)
        try:
            ratio = expr_cleaned / ref_sym
            lim = sp.limit(ratio, symbol_n, sp.oo)
            if lim.is_finite and lim > 0:
                return label
        except Exception:
            continue

    # Stage 2: Exponential check (growth rate of log(E(n))/n > 0)
    try:
        exp_rate = sp.limit(sp.log(expr_cleaned) / symbol_n, symbol_n, sp.oo)
        if exp_rate > 0:
            return "O(2^n)"
    except Exception:
        pass

    # Stage 3: Arbitrary polynomial degree detection exceeding canonical classes (d > 3 or fractional powers)
    try:
        poly_deg = sp.limit(sp.log(expr_cleaned) / sp.log(symbol_n), symbol_n, sp.oo)
        if poly_deg.is_finite and poly_deg > 0:
            d = round(float(poly_deg), 2)
            lim_ratio = sp.limit(expr_cleaned / (symbol_n ** poly_deg), symbol_n, sp.oo)
            if lim_ratio.is_finite and lim_ratio > 0:
                if d > 3 or (d != int(d) and d != 0.5):
                    return f"O(n^{int(d)})" if d == int(d) else f"O(n^{d})"
    except Exception:
        pass

    # Stage 4: First upper bound where limit is finite non-negative
    for label, ref in _CANONICAL_CLASSES:
        ref_sym = ref.subs(sp.Symbol("n", positive=True), symbol_n)
        try:
            ratio = expr_cleaned / ref_sym
            lim = sp.limit(ratio, symbol_n, sp.oo)
            if lim.is_finite and lim >= 0:
                return label
        except Exception:
            continue

    return "Unknown"
