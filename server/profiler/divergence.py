"""
Skillora Algorithmic Divergence Detection (server/profiler/divergence.py)
Estimates empirical Big-O power exponents via pure standard library log-log linear regression.
Detects divergence between theoretical SymPy Big-O and empirical runtime curves.
Zero third-party dependencies (pure math and statistics).
"""

import math
import statistics
from typing import Any, Dict, List, Optional, Tuple, Union

# Acceptable empirical power exponent ranges [p_min, p_max, target_p] per theoretical Big-O
BIG_O_EXPONENT_RANGES: Dict[str, Tuple[float, float, float]] = {
    "O(1)": (-0.30, 0.35, 0.00),
    "O(log n)": (0.05, 0.45, 0.16),
    "O(sqrt(n))": (0.35, 0.65, 0.50),
    "O(n)": (0.70, 1.35, 1.00),
    "O(n log n)": (0.80, 1.45, 1.16),
    "O(n^2)": (1.60, 2.45, 2.00),
    "O(n^3)": (2.50, 3.50, 3.00),
    "O(2^n)": (3.50, 15.0, 4.00),
}


def normalize_big_o_string(big_o_str: str) -> str:
    """
    Normalizes arbitrary Big-O strings into canonical format.
    E.g. 'o(n**2)' -> 'O(n^2)', 'O(n*log(n))' -> 'O(n log n)'.
    """
    if not big_o_str or not isinstance(big_o_str, str):
        return "O(n)"

    s = big_o_str.strip().replace(" ", "").replace("*", "").lower()

    if s in ("o(1)", "order(1)", "1"):
        return "O(1)"
    if s in ("o(logn)", "o(log(n))", "order(logn)"):
        return "O(log n)"
    if s in ("o(sqrt(n))", "o(sqrtn)"):
        return "O(sqrt(n))"
    if s in ("o(n)", "order(n)", "n"):
        return "O(n)"
    if s in ("o(nlogn)", "o(nlog(n))", "order(nlogn)"):
        return "O(n log n)"
    if s in ("o(n^2)", "o(n**2)", "order(n^2)"):
        return "O(n^2)"
    if s in ("o(n^3)", "o(n**3)", "order(n^3)"):
        return "O(n^3)"
    if s in ("o(2^n)", "o(2**n)", "order(2^n)"):
        return "O(2^n)"

    # Default fallback
    return big_o_str.strip()


def classify_exponent(p: float) -> str:
    """
    Maps an empirical scaling exponent p to the closest canonical Big-O notation.
    """
    if p < 0.25:
        return "O(1)"
    if p < 0.65:
        return "O(log n)"
    if p <= 1.45:
        return "O(n)" if p < 1.10 else "O(n log n)"
    if p <= 2.45:
        return "O(n^2)"
    if p <= 3.45:
        return "O(n^3)"
    return "O(2^n)"


def estimate_power_exponent(points: List[Tuple[Union[int, float], float]]) -> Dict[str, Any]:
    """
    Fits empirical points (N, T) to T(N) = c * N^p via log-log linear regression:
    ln(T) = ln(c) + p * ln(N).

    Args:
        points: List of (N, execution_time_in_seconds) tuples.

    Returns:
        dict: {"p": float, "intercept": float, "r_squared": float,
               "empirical_big_o": str, "valid_points": int}
    """
    # Filter non-positive values to prevent math domain error on ln(0)
    valid = [(float(n), float(t)) for n, t in points if n > 0.0 and t > 0.0]

    if len(valid) < 2:
        return {
            "p": 0.0,
            "intercept": 0.0,
            "r_squared": 0.0,
            "empirical_big_o": "INSUFFICIENT_DATA",
            "valid_points": len(valid),
        }

    ln_n = [math.log(n) for n, t in valid]
    ln_t = [math.log(t) for n, t in valid]

    # Check for zero variance in x (all N values identical)
    if len(set(ln_n)) < 2:
        return {
            "p": 0.0,
            "intercept": 0.0,
            "r_squared": 0.0,
            "empirical_big_o": "DEGENERATE_SCALES",
            "valid_points": len(valid),
        }

    # Standard library simple linear regression
    slope, intercept = statistics.linear_regression(ln_n, ln_t)

    # Calculate Pearson correlation and coefficient of determination R^2
    try:
        r = statistics.correlation(ln_n, ln_t)
        r_squared = round(r ** 2, 4)
    except Exception:
        r_squared = 0.0

    p = round(slope, 4)
    empirical_class = classify_exponent(p)

    return {
        "p": p,
        "intercept": round(intercept, 4),
        "r_squared": r_squared,
        "empirical_big_o": empirical_class,
        "valid_points": len(valid),
    }


def detect_divergence(
    theoretical_big_o: str,
    empirical: Union[Dict[str, Any], float, List[Tuple[Union[int, float], float]]],
) -> Dict[str, Any]:
    """
    Compares empirical scaling exponent against theoretical Big-O complexity class.
    Flags divergence when empirical growth contradicts theoretical bounds.

    Args:
        theoretical_big_o: SymPy derived Big-O string (e.g. 'O(n)').
        empirical: Dict containing 'p' or 'estimated_p', or raw float exponent p,
                   or list of (N, T) runtime points.

    Returns:
        dict: {
            "divergence": bool,
            "alignment_score": float,
            "empirical_p": float,
            "empirical_big_o": str,
            "theoretical_big_o": str,
            "diagnostic": str,
            "nature": "MATCH" | "WORSE_THAN_EXPECTED" | "BETTER_THAN_EXPECTED"
        }
    """
    # 1. Resolve empirical exponent p and empirical Big-O
    if isinstance(empirical, (int, float)):
        p = float(empirical)
        empirical_big_o = classify_exponent(p)
    elif isinstance(empirical, dict):
        p = float(empirical.get("estimated_p", empirical.get("p", 0.0)))
        empirical_big_o = empirical.get("empirical_big_o", classify_exponent(p))
    elif isinstance(empirical, list):
        reg = estimate_power_exponent(empirical)
        p = reg["p"]
        empirical_big_o = reg["empirical_big_o"]
    else:
        p = 0.0
        empirical_big_o = "UNKNOWN"

    canonical_theoretical = normalize_big_o_string(theoretical_big_o)
    p_min, p_max, target_p = BIG_O_EXPONENT_RANGES.get(
        canonical_theoretical,
        (0.70, 1.35, 1.00)  # Default fallback to O(n)
    )

    p_mid = (p_min + p_max) / 2.0

    # 2. Divergence evaluation
    if p_min <= p <= p_max:
        divergence = False
        alignment_score = 100.0
        nature = "MATCH"
        diagnostic = (
            f"Empirical runtime scaling (p = {p:.2f}) matches theoretical {canonical_theoretical} "
            f"complexity (acceptable range [{p_min:.2f}, {p_max:.2f}]). Alignment: 100.0%."
        )
    elif p > p_max:
        divergence = True
        nature = "WORSE_THAN_EXPECTED"
        distance = p - p_mid
        alignment_score = max(0.0, min(100.0, round(100.0 - 35.0 * distance, 1)))
        diagnostic = (
            f"Algorithmic divergence detected! Empirical runtime scaling exhibits {empirical_big_o} "
            f"behavior (p = {p:.2f}), which is significantly worse than theoretical {canonical_theoretical} "
            f"expectation (acceptable upper limit p = {p_max:.2f}). Check for nested loops, repeated copying, "
            f"or unintended high-order operations. Alignment: {alignment_score:.1f}%."
        )
    else:
        divergence = True
        nature = "BETTER_THAN_EXPECTED"
        distance = p_mid - p
        alignment_score = max(0.0, min(100.0, round(100.0 - 35.0 * distance, 1)))
        diagnostic = (
            f"Empirical runtime scaling exhibits {empirical_big_o} behavior (p = {p:.2f}), which scales faster "
            f"than theoretical {canonical_theoretical} expectation (expected lower limit p = {p_min:.2f}). "
            f"The theoretical recurrence may be a conservative upper bound or best-case pruning occurred. "
            f"Alignment: {alignment_score:.1f}%."
        )

    return {
        "divergence": divergence,
        "alignment_score": alignment_score,
        "empirical_p": round(p, 4),
        "empirical_big_o": empirical_big_o,
        "theoretical_big_o": canonical_theoretical,
        "diagnostic": diagnostic,
        "nature": nature,
    }
