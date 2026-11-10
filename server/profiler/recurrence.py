"""
Skillora Algorithmic Profiler: Symbolic Recurrence Solver (server/profiler/recurrence.py)
Parses recurrence relations, solves linear difference equations and divide-and-conquer
relations via logarithmic substitution transform, and provides Master Theorem explanations.
Zero third-party dependencies (SymPy + standard library only).
"""

import re
from typing import Any, Dict, Optional, Tuple
import sympy as sp
from sympy.core.function import AppliedUndef
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
)

from server.profiler.canonical_order import canonicalize_big_o

_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)


def normalize_base_cases(base_cases: Optional[Dict[Any, Any]], func_sym: sp.Function) -> Dict[Any, Any]:
    """
    Normalizes base cases from various formats ({'T(1)': 1}, {1: 1}, {'1': 1}, {f(1): 1})
    into SymPy {func_sym(k): v} mapping.
    """
    normalized = {}
    if not base_cases:
        return normalized

    for k, v in base_cases.items():
        val = int(v) if isinstance(v, (int, str)) and str(v).isdigit() else v
        if isinstance(k, int):
            normalized[func_sym(k)] = val
        elif isinstance(k, str):
            m = re.search(r"\b(\d+)\b", k)
            if m:
                idx = int(m.group(1))
                normalized[func_sym(idx)] = val
        elif hasattr(k, "args") and len(k.args) == 1:
            try:
                normalized[func_sym(int(k.args[0]))] = val
            except Exception:
                normalized[k] = val
    return normalized


def verify_master_theorem(a: float, b: float, f_n: sp.Expr) -> Dict[str, Any]:
    """
    Evaluates Master Theorem cases and pedagogical explanation for T(n) = a*T(n/b) + f(n).
    """
    n = sp.Symbol("n", positive=True)
    try:
        c_crit = sp.simplify(sp.log(sp.nsimplify(a)) / sp.log(sp.nsimplify(b)))
    except Exception:
        c_crit = sp.simplify(sp.log(a) / sp.log(b))
    c_crit_float = float(sp.N(c_crit, 4))
    ref = n ** c_crit

    try:
        ratio = f_n / ref
        lim = sp.limit(ratio, n, sp.oo)

        if lim == 0:
            case = 1
            big_o = "O(1)" if c_crit_float == 0 else ("O(n)" if c_crit_float == 1 else f"O(n^{c_crit_float:g})")
            explanation = (
                f"Master Theorem Case 1: f(n) = O(n^(c_crit - eps)) where c_crit = log_{b}({a}) = {c_crit_float:g}. "
                f"Work is dominated by recursive leaves: {big_o}."
            )
        elif lim.is_finite and lim > 0:
            case = 2
            big_o = "O(log n)" if c_crit_float == 0 else ("O(n log n)" if c_crit_float == 1 else f"O(n^{c_crit_float:g} log n)")
            explanation = (
                f"Master Theorem Case 2: f(n) = Theta(n^(log_{b}({a}))). "
                f"Work is distributed evenly across recursion levels: {big_o}."
            )
        elif lim == sp.oo:
            lim_log = sp.limit(ratio / sp.log(n), n, sp.oo)
            if lim_log.is_finite and lim_log > 0:
                case = 2
                big_o = "O(log^2 n)" if c_crit_float == 0 else f"O(n^{c_crit_float:g} log^2 n)"
                explanation = f"Master Theorem Extended Case 2: f(n) = Theta(n^{c_crit_float:g} * log n): {big_o}."
            else:
                case = 3
                regularity = a * f_n.subs(n, n / b) / f_n
                reg_lim = sp.limit(regularity, n, sp.oo)
                reg_ok = bool(reg_lim < 1) if reg_lim.is_number else True
                big_o = canonicalize_big_o(f_n, n)
                explanation = (
                    f"Master Theorem Case 3: f(n) dominates leaves (c_crit = {c_crit_float:g}). "
                    f"Regularity condition limit {reg_lim} < 1: {reg_ok}. Dominated by root: {big_o}."
                )
        else:
            case = None
            big_o = "Unknown"
            explanation = "Master Theorem is inconclusive for this equation."
    except Exception as e:
        case = None
        big_o = "Unknown"
        explanation = f"Master Theorem analysis could not be completed: {e}"

    return {
        "case": case,
        "c_crit": c_crit_float,
        "big_o": big_o,
        "explanation": explanation,
    }


def solve_recurrence(equation_str: str, base_cases: Optional[Dict[Any, Any]] = None) -> Dict[str, Any]:
    """
    Main interface contract: Parses and solves a recurrence equation.

    Parameters:
        equation_str: String representation of recurrence (e.g. 'T(n) = 2*T(n/2) + n').
        base_cases: Dictionary of initial conditions (e.g. {'T(1)': 1}).

    Returns:
        dict with keys:
            'closed_form': str,
            'big_o': str,
            'method': str,
            'error': str | None,
            'master_theorem': dict | None (if divide-and-conquer)
    """
    if base_cases is None:
        base_cases = {}

    eq_clean = equation_str.replace("^", "**").strip()
    if "=" in eq_clean:
        lhs_str, rhs_str = eq_clean.split("=", 1)
    else:
        lhs_str, rhs_str = "T(n)", eq_clean
    lhs_str = lhs_str.strip()
    rhs_str = rhs_str.strip()

    # -------------------------------------------------------------
    # 1. Divide-and-Conquer Detection & Substitution Solver
    # -------------------------------------------------------------
    dac_pattern = r"([-+]?[0-9]*\.?[0-9]*)\s*\*?\s*[TtfF]\s*\(\s*n\s*/\s*([0-9]*\.?[0-9]+)\s*\)"
    m = re.search(dac_pattern, rhs_str)
    if m:
        a_str = m.group(1).strip()
        b_str = m.group(2).strip()
        if a_str == "-":
            a = -1.0
        elif a_str in ("", "+"):
            a = 1.0
        else:
            a = float(a_str)
        if a.is_integer():
            a = int(a)
        b = float(b_str)
        if b.is_integer():
            b = int(b)

        if b <= 1:
            return {
                "closed_form": "",
                "big_o": "",
                "method": "divide_and_conquer",
                "error": f"Division factor b must be > 1, got {b}",
                "master_theorem": None,
            }
        if a < 1:
            return {
                "closed_form": "",
                "big_o": "",
                "method": "divide_and_conquer",
                "error": f"Subproblem count a must be >= 1, got {a}",
                "master_theorem": None,
            }

        rhs_wo = rhs_str[: m.start()] + "0" + rhs_str[m.end() :]
        n = sp.Symbol("n", positive=True)
        local_dict = {"n": n, "log": sp.log, "sqrt": sp.sqrt}
        try:
            f_n = parse_expr(rhs_wo.strip(), local_dict=local_dict, transformations=_TRANSFORMATIONS)
        except Exception as e:
            return {
                "closed_form": "",
                "big_o": "",
                "method": "divide_and_conquer",
                "error": f"Syntax error in non-recursive work term f(n): {e}",
                "master_theorem": None,
            }

        # Resolve base case: T(1) corresponds to g(0)
        base_val = 1
        for k, v in base_cases.items():
            if str(k) in ("1", "T(1)", "f(1)", "t(1)"):
                base_val = v
                break
            elif str(k) in ("0", "T(0)", "f(0)", "t(0)"):
                base_val = v
                break

        # Formulate auxiliary equation: g(k) - a*g(k-1) = f(b^k)
        k = sp.Symbol("k", integer=True, positive=True)
        g = sp.Function("g")
        f_bk = f_n.subs(n, b ** k)
        aux_eq = g(k) - a * g(k - 1) - f_bk

        mt_info = verify_master_theorem(a, b, f_n)

        try:
            sol_k = sp.rsolve(aux_eq, g(k), {g(0): base_val})
            if sol_k is None:
                return {
                    "closed_form": "",
                    "big_o": mt_info.get("big_o", "Unknown"),
                    "method": "divide_and_conquer_substitution",
                    "error": "SymPy could not solve auxiliary difference equation",
                    "master_theorem": mt_info,
                }

            # Back-substitution: b**k -> n, a**k -> n^(log_b a), k -> log_b(n)
            sol_expanded = sp.expand(sol_k)
            sol_n = sol_expanded.subs(b ** k, n)
            if a != b:
                try:
                    c_crit_sub = sp.simplify(sp.log(sp.nsimplify(a)) / sp.log(sp.nsimplify(b)))
                except Exception:
                    c_crit_sub = sp.log(a) / sp.log(b)
                sol_n = sol_n.subs(a ** k, n ** c_crit_sub)
            sol_n = sol_n.subs(k, sp.log(n) / sp.log(b))

            try:
                sol_n = sp.expand(sp.expand_log(sol_n, force=True))
            except Exception:
                pass

            big_o = canonicalize_big_o(sol_n, n)
            return {
                "closed_form": str(sol_n),
                "big_o": big_o,
                "method": "divide_and_conquer_substitution",
                "error": None,
                "master_theorem": mt_info,
            }
        except Exception as e:
            return {
                "closed_form": "",
                "big_o": mt_info.get("big_o", "Unknown"),
                "method": "divide_and_conquer_substitution",
                "error": str(e),
                "master_theorem": mt_info,
            }

    # -------------------------------------------------------------
    # 2. Linear Difference Equation Solver
    # -------------------------------------------------------------
    n = sp.Symbol("n", integer=True, positive=True)
    f = sp.Function("f")
    local_dict = {"f": f, "n": n, "log": sp.log, "sqrt": sp.sqrt}

    lhs_norm = re.sub(r"[Tt]\s*\(", "f(", lhs_str)
    rhs_norm = re.sub(r"[Tt]\s*\(", "f(", rhs_str)

    try:
        lhs_expr = parse_expr(lhs_norm, local_dict=local_dict, transformations=_TRANSFORMATIONS)
        rhs_expr = parse_expr(rhs_norm, local_dict=local_dict, transformations=_TRANSFORMATIONS)
        diff_eq = lhs_expr - rhs_expr
    except Exception as e:
        return {
            "closed_form": "",
            "big_o": "",
            "method": "linear_rsolve",
            "error": f"Recurrence syntax parsing error: {e}",
            "master_theorem": None,
        }

    init_conds = normalize_base_cases(base_cases, f)

    # Supply default initial conditions if omitted
    if not init_conds:
        f_atoms = [atom for atom in diff_eq.atoms(AppliedUndef) if atom.func == f]
        shifts = []
        for atom in f_atoms:
            diff = sp.expand(atom.args[0] - n)
            if diff.is_number:
                shifts.append(int(diff))
        order = (max(shifts) - min(shifts)) if shifts else 1
        if order <= 1:
            init_conds = {f(1): 1}
        elif order == 2:
            init_conds = {f(0): 0, f(1): 1}

    try:
        sol = sp.rsolve(diff_eq, f(n), init_conds)
        if sol is None:
            return {
                "closed_form": "",
                "big_o": "",
                "method": "linear_rsolve",
                "error": "SymPy rsolve returned None (unresolvable linear difference relation)",
                "master_theorem": None,
            }

        n_pos = sp.Symbol("n", positive=True)
        sol_n = sol.subs(n, n_pos)
        big_o = canonicalize_big_o(sol_n, n_pos)

        return {
            "closed_form": str(sol),
            "big_o": big_o,
            "method": "linear_rsolve",
            "error": None,
            "master_theorem": None,
        }
    except Exception as e:
        return {
            "closed_form": "",
            "big_o": "",
            "method": "linear_rsolve",
            "error": str(e),
            "master_theorem": None,
        }
