"""
Skillora Algorithmic Profiler Test Suite (tests/test_profiler.py)
Verifies symbolic recurrence solving, divide-and-conquer substitution transform,
Master Theorem evaluation, and asymptotic Big-O limit canonicalization.
"""

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sympy as sp
from server.profiler.canonical_order import canonicalize_big_o, clean_decaying_terms
from server.profiler.recurrence import solve_recurrence, verify_master_theorem, normalize_base_cases


class TestRecurrenceSolver(unittest.TestCase):
    """Verifies symbolic recurrence solving across standard and edge-case relations."""

    def test_linear_recurrence_insertion_sort(self):
        # T(n) = T(n-1) + n with T(1) = 1 -> n*(n+1)/2 -> O(n^2)
        res = solve_recurrence("T(n) = T(n-1) + n", {"T(1)": 1})
        self.assertIsNone(res["error"])
        self.assertEqual(res["big_o"], "O(n^2)")
        self.assertIn("n*(n + 1)/2", res["closed_form"])

    def test_linear_recurrence_constant_step(self):
        # T(n) = T(n-1) + 1 with T(1) = 1 -> n -> O(n)
        res = solve_recurrence("T(n) = T(n-1) + 1", {"T(1)": 1})
        self.assertIsNone(res["error"])
        self.assertEqual(res["big_o"], "O(n)")
        self.assertEqual(res["closed_form"], "n")

    def test_linear_recurrence_tower_of_hanoi(self):
        # T(n) = 2*T(n-1) + 1 with T(1) = 1 -> 2^n - 1 -> O(2^n)
        res = solve_recurrence("T(n) = 2*T(n-1) + 1", {"T(1)": 1})
        self.assertIsNone(res["error"])
        self.assertEqual(res["big_o"], "O(2^n)")
        self.assertIn("2**n - 1", res["closed_form"])

    def test_linear_recurrence_fibonacci(self):
        # T(n) = T(n-1) + T(n-2) with T(0)=0, T(1)=1 -> O(2^n)
        res = solve_recurrence("T(n) = T(n-1) + T(n-2)", {"T(0)": 0, "T(1)": 1})
        self.assertIsNone(res["error"])
        self.assertEqual(res["big_o"], "O(2^n)")
        self.assertTrue(len(res["closed_form"]) > 0)

    def test_divide_and_conquer_merge_sort(self):
        # T(n) = 2*T(n/2) + n with T(1) = 1 -> O(n log n)
        res = solve_recurrence("T(n) = 2*T(n/2) + n", {"T(1)": 1})
        self.assertIsNone(res["error"])
        self.assertEqual(res["big_o"], "O(n log n)")
        self.assertIn("log", res["closed_form"])
        self.assertEqual(res["master_theorem"]["case"], 2)

    def test_divide_and_conquer_binary_search(self):
        # T(n) = T(n/2) + 1 with T(1) = 1 -> O(log n)
        res = solve_recurrence("T(n) = T(n/2) + 1", {"T(1)": 1})
        self.assertIsNone(res["error"])
        self.assertEqual(res["big_o"], "O(log n)")
        self.assertEqual(res["master_theorem"]["case"], 2)

    def test_divide_and_conquer_case1(self):
        # T(n) = 4*T(n/2) + n -> O(n^2)
        res = solve_recurrence("T(n) = 4*T(n/2) + n", {"T(1)": 1})
        self.assertIsNone(res["error"])
        self.assertEqual(res["big_o"], "O(n^2)")
        self.assertEqual(res["master_theorem"]["case"], 1)

    def test_divide_and_conquer_case3(self):
        # T(n) = 2*T(n/2) + n^2 -> O(n^2)
        res = solve_recurrence("T(n) = 2*T(n/2) + n^2", {"T(1)": 1})
        self.assertIsNone(res["error"])
        self.assertEqual(res["big_o"], "O(n^2)")
        self.assertEqual(res["master_theorem"]["case"], 3)

    def test_implicit_multiplication_parsing(self):
        # 2T(n/2) + n instead of 2*T(n/2) + n
        res = solve_recurrence("T(n) = 2T(n/2) + n")
        self.assertIsNone(res["error"])
        self.assertEqual(res["big_o"], "O(n log n)")

    def test_default_base_cases(self):
        # Empty base cases uses automatic defaults
        res = solve_recurrence("T(n) = T(n-1) + n", {})
        self.assertIsNone(res["error"])
        self.assertEqual(res["big_o"], "O(n^2)")

    def test_invalid_syntax_error(self):
        res = solve_recurrence("T(n) = 2*T(n/2) +++")
        self.assertIsNotNone(res["error"])
        self.assertEqual(res["closed_form"], "")

    def test_invalid_divide_factor(self):
        res = solve_recurrence("T(n) = 2*T(n/0.5) + n")
        self.assertIsNotNone(res["error"])
        self.assertIn("factor b must be > 1", res["error"].lower())

    def test_invalid_subproblem_count(self):
        res = solve_recurrence("T(n) = 0*T(n/2) + n")
        self.assertIsNotNone(res["error"])
        self.assertIn("count a must be >= 1", res["error"].lower())

    def test_base_case_normalization(self):
        f = sp.Function("f")
        cases = {"T(0)": 0, "1": 10, f(2): 20}
        norm = normalize_base_cases(cases, f)
        self.assertEqual(norm[f(0)], 0)
        self.assertEqual(norm[f(1)], 10)
        self.assertEqual(norm[f(2)], 20)


class TestCanonicalOrder(unittest.TestCase):
    """Verifies asymptotic Big-O canonicalization."""

    def setUp(self):
        self.n = sp.Symbol("n", positive=True)

    def test_canonical_constant(self):
        self.assertEqual(canonicalize_big_o(5), "O(1)")
        self.assertEqual(canonicalize_big_o("100"), "O(1)")

    def test_canonical_log(self):
        self.assertEqual(canonicalize_big_o(sp.log(self.n) + 1), "O(log n)")
        self.assertEqual(canonicalize_big_o("log(n)/log(2) + 1"), "O(log n)")

    def test_canonical_linear(self):
        self.assertEqual(canonicalize_big_o(3 * self.n + 10), "O(n)")

    def test_canonical_n_log_n(self):
        expr = self.n * sp.log(self.n) / sp.log(2) + 2 * self.n
        self.assertEqual(canonicalize_big_o(expr), "O(n log n)")

    def test_canonical_quadratic(self):
        self.assertEqual(canonicalize_big_o(self.n * (self.n + 1) / 2), "O(n^2)")

    def test_canonical_cubic(self):
        self.assertEqual(canonicalize_big_o(self.n**3 + 4 * self.n**2), "O(n^3)")

    def test_canonical_exponential(self):
        self.assertEqual(canonicalize_big_o(2**self.n - 1), "O(2^n)")

    def test_clean_decaying_terms_fibonacci(self):
        # (-0.618)^n drops cleanly and evaluates to O(2^n)
        phi = (1 + sp.sqrt(5)) / 2
        psi = (1 - sp.sqrt(5)) / 2
        fib = (phi**self.n - psi**self.n) / sp.sqrt(5)
        self.assertEqual(canonicalize_big_o(fib), "O(2^n)")

    def test_arbitrary_polynomial_degree(self):
        expr = self.n**4 + 3 * self.n**2
        self.assertEqual(canonicalize_big_o(expr), "O(n^4)")


if __name__ == "__main__":
    unittest.main()
