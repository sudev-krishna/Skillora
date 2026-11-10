"""
Skillora Empirical Verification Suite for Milestone 3 Remediation (Challenger 2)
Tests:
1. verify_master_theorem & solve_recurrence Case 2 when a != b
2. solve_recurrence rejection of negative subproblem counts and parameter bounds
3. canonicalize_big_o polylogarithmic upper bound matching and mathematical validity
"""

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sympy as sp
from server.profiler.recurrence import solve_recurrence, verify_master_theorem
from server.profiler.canonical_order import canonicalize_big_o, _CANONICAL_CLASSES


class TestMasterTheoremCase2Remediation(unittest.TestCase):
    """Verifies that verify_master_theorem correctly evaluates Case 2 when a != b."""

    def test_master_theorem_case2_a_neq_b(self):
        cases = [
            # eq, expected_case, expected_c_crit, expected_mt_big_o
            ("T(n) = 4*T(n/2) + n^2", 2, 2.0, "O(n^2 log n)"),
            ("T(n) = 2*T(n/4) + sqrt(n)", 2, 0.5, "O(n^0.5 log n)"),
            ("T(n) = 8*T(n/2) + n^3", 2, 3.0, "O(n^3 log n)"),
            ("T(n) = 9*T(n/3) + n^2", 2, 2.0, "O(n^2 log n)"),
            ("T(n) = 3*T(n/9) + sqrt(n)", 2, 0.5, "O(n^0.5 log n)"),
            ("T(n) = 16*T(n/4) + n^2", 2, 2.0, "O(n^2 log n)"),
            ("T(n) = 27*T(n/3) + n^3", 2, 3.0, "O(n^3 log n)"),
            ("T(n) = 8*T(n/4) + n**1.5", 2, 1.5, "O(n^1.5 log n)"),
        ]

        for eq, exp_case, exp_crit, exp_big_o in cases:
            res = solve_recurrence(eq)
            self.assertIsNone(res.get("error"), f"Failed for {eq}: {res.get('error')}")
            mt = res.get("master_theorem")
            self.assertIsNotNone(mt, f"Master theorem missing for {eq}")
            self.assertEqual(mt["case"], exp_case, f"Case mismatch for {eq}: got {mt['case']}")
            self.assertAlmostEqual(mt["c_crit"], exp_crit, places=3, msg=f"c_crit mismatch for {eq}")
            self.assertEqual(mt["big_o"], exp_big_o, f"MT big_o mismatch for {eq}: got {mt['big_o']}")

    def test_direct_verify_master_theorem_case2(self):
        n = sp.Symbol("n", positive=True)
        # 1. a=4, b=2, f(n) = n^2
        mt1 = verify_master_theorem(4, 2, n**2)
        self.assertEqual(mt1["case"], 2)
        self.assertEqual(mt1["c_crit"], 2.0)
        self.assertEqual(mt1["big_o"], "O(n^2 log n)")

        # 2. a=2, b=4, f(n) = sqrt(n)
        mt2 = verify_master_theorem(2, 4, sp.sqrt(n))
        self.assertEqual(mt2["case"], 2)
        self.assertEqual(mt2["c_crit"], 0.5)
        self.assertEqual(mt2["big_o"], "O(n^0.5 log n)")

    def test_master_theorem_case1_and_case3_a_neq_b(self):
        # Case 1: T(n) = 4*T(n/2) + n -> c_crit = 2 > 1 -> O(n^2)
        res1 = solve_recurrence("T(n) = 4*T(n/2) + n")
        self.assertIsNone(res1["error"])
        self.assertEqual(res1["master_theorem"]["case"], 1)
        self.assertEqual(res1["master_theorem"]["big_o"], "O(n^2)")

        # Case 3: T(n) = 4*T(n/2) + n^3 -> c_crit = 2 < 3 -> O(n^3)
        res3 = solve_recurrence("T(n) = 4*T(n/2) + n^3")
        self.assertIsNone(res3["error"])
        self.assertEqual(res3["master_theorem"]["case"], 3)
        self.assertEqual(res3["master_theorem"]["big_o"], "O(n^3)")


class TestSubproblemValidationRemediation(unittest.TestCase):
    """Verifies solve_recurrence input validation for negative subproblems and invalid parameters."""

    def test_negative_subproblem_coefficients_rejected(self):
        invalid_equations = [
            "T(n) = -3*T(n/2) + n",
            "T(n) = -1*T(n/2) + n",
            "T(n) = -T(n/2) + n",
            "T(n) = -0.5*T(n/2) + n",
            "T(n) = -5*T(n/4)",
        ]
        for eq in invalid_equations:
            res = solve_recurrence(eq)
            self.assertIsNotNone(res.get("error"), f"Expected error for {eq}")
            self.assertIn("Subproblem count a must be >= 1", res["error"])

    def test_boundary_subproblem_coefficients(self):
        # a = 0 -> rejected
        res0 = solve_recurrence("T(n) = 0*T(n/2) + n")
        self.assertIn("Subproblem count a must be >= 1", res0.get("error", ""))

        # a = 0.5 -> rejected
        res_half = solve_recurrence("T(n) = 0.5*T(n/2) + n")
        self.assertIn("Subproblem count a must be >= 1", res_half.get("error", ""))

        # a = 1 -> accepted
        res1 = solve_recurrence("T(n) = 1*T(n/2) + n")
        self.assertIsNone(res1.get("error"))

        # Explicit positive sign: +3*T(n/2) -> accepted
        res_pos = solve_recurrence("T(n) = +3*T(n/2) + n")
        self.assertIsNone(res_pos.get("error"))

        # Implicit positive sign: +T(n/2) -> accepted
        res_plus = solve_recurrence("T(n) = +T(n/2) + n")
        self.assertIsNone(res_plus.get("error"))

    def test_division_factor_b_validation(self):
        # b = 1 -> rejected
        res_b1 = solve_recurrence("T(n) = 2*T(n/1) + n")
        self.assertIn("Division factor b must be > 1", res_b1.get("error", ""))

        # b = 0.5 -> rejected
        res_b_half = solve_recurrence("T(n) = 2*T(n/0.5) + n")
        self.assertIn("Division factor b must be > 1", res_b_half.get("error", ""))


class TestCanonicalBigORemediation(unittest.TestCase):
    """Verifies canonicalize_big_o properly matches upper bounds for polylogarithmic functions."""

    def test_polylog_upper_bound_matching(self):
        n = sp.Symbol("n", positive=True)

        # 1. sqrt(n)*log(n) -> matches O(n), NOT O(n^0.5)
        res_sqrt_log = canonicalize_big_o(sp.sqrt(n) * sp.log(n), n)
        self.assertEqual(res_sqrt_log, "O(n)")

        # 2. n*(log(n)**2) -> matches O(n^2), NOT O(n)
        res_n_log2 = canonicalize_big_o(n * (sp.log(n) ** 2), n)
        self.assertEqual(res_n_log2, "O(n^2)")

        # 3. log(n)**2 -> matches O(sqrt(n))
        res_log2 = canonicalize_big_o(sp.log(n) ** 2, n)
        self.assertEqual(res_log2, "O(sqrt(n))")

        # 4. n^2*(log(n)**2) -> matches O(n^3)
        res_n2_log2 = canonicalize_big_o((n**2) * (sp.log(n) ** 2), n)
        self.assertEqual(res_n2_log2, "O(n^3)")

    def test_mathematical_upper_bound_invariant(self):
        """
        By definition of Big-O: f(n) in O(g(n)) iff lim_{n->oo} f(n)/g(n) is finite.
        If lim = oo, then g(n) is an asymptotic underestimation (not a valid Big-O).
        """
        n = sp.Symbol("n", positive=True)
        class_map = {label: ref for label, ref in _CANONICAL_CLASSES}

        test_expressions = [
            sp.sqrt(n) * sp.log(n),
            n * (sp.log(n) ** 2),
            sp.log(n) ** 2,
            (n**2) * (sp.log(n) ** 2),
            n * sp.log(n),
            n**2,
            n**3,
        ]

        for expr in test_expressions:
            res_label = canonicalize_big_o(expr, n)
            self.assertIn(res_label, class_map, f"Result {res_label} not in canonical classes")
            ref_sym = class_map[res_label]
            ratio = expr / ref_sym
            lim = sp.limit(ratio, n, sp.oo)
            self.assertTrue(
                lim.is_finite,
                f"Big-O violation: {expr} classified as {res_label}, but limit ratio is infinite ({lim})",
            )
            self.assertGreaterEqual(
                float(lim), 0.0,
                f"Negative limit ratio for {expr} against {res_label}",
            )

    def test_polynomial_exceeding_classes(self):
        n = sp.Symbol("n", positive=True)
        self.assertEqual(canonicalize_big_o(n**4, n), "O(n^4)")
        self.assertEqual(canonicalize_big_o(n**5, n), "O(n^5)")
        self.assertEqual(canonicalize_big_o(n**1.58, n), "O(n^1.58)")
        self.assertEqual(canonicalize_big_o(n**2.5, n), "O(n^2.5)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
