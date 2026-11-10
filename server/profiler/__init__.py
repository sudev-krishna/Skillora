"""
Skillora Algorithmic Profiler Package (server/profiler/__init__.py)
Exports recurrence solving, canonical Big-O classification, and empirical divergence profiling.
"""

from server.profiler.canonical_order import canonicalize_big_o, clean_decaying_terms
from server.profiler.recurrence import normalize_base_cases, solve_recurrence, verify_master_theorem
from server.profiler.divergence import (
    BIG_O_EXPONENT_RANGES,
    classify_exponent,
    detect_divergence,
    estimate_power_exponent,
    normalize_big_o_string,
)

__all__ = [
    "solve_recurrence",
    "verify_master_theorem",
    "normalize_base_cases",
    "canonicalize_big_o",
    "clean_decaying_terms",
    "detect_divergence",
    "estimate_power_exponent",
    "classify_exponent",
    "normalize_big_o_string",
    "BIG_O_EXPONENT_RANGES",
]
