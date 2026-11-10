"""
Adversarial Stress Test Suite for Milestone 3 (Challenger 2)
Empirical verification of:
1. Recurrence solving edge cases (D&C, linear characteristic roots, invalid inputs)
2. Divergence detection robustness (noisy series, outliers, non-positive times, false claims)
3. Dynamic aptitude math generator invariants (240+ instances across 4 topics)
4. Empirical reproduction of identified asymptotic and Master Theorem edge-case bugs
"""

import math
import os
from pathlib import Path
import random
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sympy as sp

from server.profiler.recurrence import solve_recurrence, verify_master_theorem
from server.profiler.canonical_order import canonicalize_big_o, clean_decaying_terms
from server.profiler.divergence import (
    detect_divergence,
    estimate_power_exponent,
    classify_exponent,
    normalize_big_o_string,
    BIG_O_EXPONENT_RANGES,
)
from server.math_engine.aptitude_generator import (
    generate_problem,
    generate_interest_problem,
    generate_work_problem,
    generate_urn_problem,
    generate_cayley_problem,
    AptitudeTopic,
)


class TestRecurrenceAdversarialCases(unittest.TestCase):
    """Stress tests for recurrence equation parsing, substitution solving, and Master Theorem."""

    def test_diverse_divide_and_conquer_equations(self):
        cases = [
            # 1. T(n) = 3T(n/2) + n -> c_crit = log2(3) ~ 1.585 > 1 -> Case 1: O(n^1.58)
            ("T(n) = 3T(n/2) + n", "O(n^1.58)"),
            # 2. T(n) = 4T(n/2) + n^2 -> closed form O(n^2 log n)
            ("T(n) = 4T(n/2) + n^2", "O(n^2 log n)"),
            # 3. T(n) = T(n/3) + 1 -> c_crit = log3(1) = 0 == 0 -> Case 2: O(log n)
            ("T(n) = T(n/3) + 1", "O(log n)"),
            # 4. T(n) = 8T(n/2) + n^2 -> c_crit = 3 > 2 -> Case 1: O(n^3)
            ("T(n) = 8T(n/2) + n^2", "O(n^3)"),
            # 5. T(n) = 7T(n/2) + n^3 -> c_crit = log2(7) ~ 2.807 < 3 -> Case 3: O(n^3)
            ("T(n) = 7T(n/2) + n^3", "O(n^3)"),
            # 6. T(n) = T(n/2) + n -> c_crit = 0 < 1 -> Case 3: O(n)
            ("T(n) = T(n/2) + n", "O(n)"),
            # 7. T(n) = 2T(n/2) + 1 -> c_crit = 1 > 0 -> Case 1: O(n)
            ("T(n) = 2T(n/2) + 1", "O(n)"),
        ]

        for eq, expected_big_o in cases:
            res = solve_recurrence(eq)
            self.assertIsNone(res.get("error"), f"Unexpected error for {eq}: {res.get('error')}")
            self.assertIsNotNone(res.get("master_theorem"), f"Missing MT info for {eq}")
            if expected_big_o:
                self.assertEqual(
                    res["big_o"],
                    expected_big_o,
                    f"Big-O mismatch for {eq}: expected {expected_big_o}, got {res['big_o']}",
                )

    def test_linear_recurrences_characteristic_roots(self):
        # 1. T(n) = 3T(n-1) - 2T(n-2), roots = 1, 2. Dominant root 2^n -> O(2^n)
        res1 = solve_recurrence("T(n) = 3T(n-1) - 2T(n-2)", {"T(0)": 0, "T(1)": 1})
        self.assertIsNone(res1["error"])
        self.assertEqual(res1["big_o"], "O(2^n)")

        # 2. T(n) = 4T(n-1) - 4T(n-2), repeated root r=2 -> O(2^n)
        res2 = solve_recurrence("T(n) = 4T(n-1) - 4T(n-2)", {"T(0)": 0, "T(1)": 1})
        self.assertIsNone(res2["error"])
        self.assertEqual(res2["big_o"], "O(2^n)")

        # 3. Fibonacci with decaying term: T(n) = T(n-1) + T(n-2)
        res_fib = solve_recurrence("T(n) = T(n-1) + T(n-2)", {"T(0)": 0, "T(1)": 1})
        self.assertIsNone(res_fib["error"])
        self.assertEqual(res_fib["big_o"], "O(2^n)")

        # 4. Pure decaying root: T(n) = (1/2)*T(n-1) -> T(n) -> 0 -> O(1)
        res_decay = solve_recurrence("T(n) = (1/2)*T(n-1)", {"T(0)": 1})
        self.assertIsNone(res_decay["error"])
        self.assertEqual(res_decay["big_o"], "O(1)")

    def test_clean_decaying_terms_preserves_dominant(self):
        n = sp.Symbol("n", positive=True)
        # Expression: 2^n + (1/3)^n
        expr = 2**n + (sp.Rational(1, 3))**n
        cleaned = clean_decaying_terms(expr, n)
        # Dominant term 2^n must remain
        self.assertIn("2**n", str(cleaned))
        self.assertNotIn("(1/3)**n", str(cleaned))

    def test_invalid_recurrence_inputs_graceful_handling(self):
        """Malformed, non-numeric, or illegal recurrences must return clean error dicts without tracebacks."""
        invalid_inputs = [
            "",
            "   ",
            "T(n) = ",
            "T(n) = 2T(n/2 + n",
            "T(n) = 2*T(n/2) ***",
            "T(n) = a*T(n/b) + n",
            "T(n) = 2*T(n/1) + n",   # b = 1
            "T(n) = 2*T(n/0.5) + n", # b < 1
            "T(n) = 0*T(n/2) + n",   # a = 0 < 1
            "completely unparseable gibberish !@#$%^&*",
        ]
        for inv in invalid_inputs:
            try:
                res = solve_recurrence(inv)
                self.assertIsInstance(res, dict)
                self.assertIsNotNone(res.get("error"), f"Expected error for '{inv}', got None")
            except Exception as e:
                self.fail(f"solve_recurrence raised unhandled exception on '{inv}': {e}")


class TestMasterTheoremAndCanonicalBugs(unittest.TestCase):
    """Empirical demonstration and verification of edge-case bugs identified during review."""

    def test_negative_subproblem_count_regex_bypass_bug(self):
        r"""
        Verifies Bug 3 Remediation: In solve_recurrence, dac_pattern captures unary sign.
        For equation T(n) = -3*T(n/2) + n, the regex parses a = -3.0 and triggers
        validation error (Subproblem count a must be >= 1).
        """
        res = solve_recurrence("T(n) = -3*T(n/2) + n")
        self.assertIsNotNone(res.get("error"), "Expected validation error for negative subproblem count")
        self.assertIn("Subproblem count a must be >= 1", res["error"])

    def test_master_theorem_unsimplified_log_ratio_bug(self):
        """
        Verifies Bug 1 Remediation: In verify_master_theorem, c_crit simplifies log(a)/log(b)
        algebraically when a != b.
        For Case 2 equations like T(n) = 4T(n/2) + n^2 and T(n) = 2T(n/4) + sqrt(n),
        Master Theorem Case 2 is correctly identified.
        """
        # 1. T(n) = 4T(n/2) + n^2
        res_4 = solve_recurrence("T(n) = 4*T(n/2) + n^2")
        self.assertIsNone(res_4["error"])
        self.assertEqual(res_4["big_o"], "O(n^2 log n)")
        mt_4 = res_4["master_theorem"]
        self.assertEqual(mt_4["case"], 2)
        self.assertEqual(mt_4["c_crit"], 2.0)
        self.assertEqual(mt_4["big_o"], "O(n^2 log n)")

        # 2. T(n) = 2T(n/4) + sqrt(n)
        res_sqrt = solve_recurrence("T(n) = 2*T(n/4) + sqrt(n)")
        self.assertIsNone(res_sqrt["error"])
        mt_sqrt = res_sqrt["master_theorem"]
        self.assertEqual(mt_sqrt["case"], 2)
        self.assertEqual(mt_sqrt["c_crit"], 0.5)
        self.assertEqual(mt_sqrt["big_o"], "O(n^0.5 log n)")

    def test_canonicalize_big_o_polylog_underestimation_bug(self):
        """
        Verifies Bug 2 Remediation: In canonicalize_big_o, polylog terms with d <= 3
        fall through to Stage 4 to find a true canonical asymptotic upper bound.
        For sqrt(n)*log(n), it correctly returns O(n) rather than the lower bound O(n^0.5).
        """
        n = sp.Symbol("n", positive=True)
        expr = sp.sqrt(n) * sp.log(n)
        classified = canonicalize_big_o(expr, n)
        self.assertEqual(classified, "O(n)")
        # Mathematically verify that ratio against O(n) is finite and non-negative
        ratio = expr / n
        lim = sp.limit(ratio, n, sp.oo)
        self.assertEqual(lim, 0)


class TestDivergenceClassifierAdversarialCases(unittest.TestCase):
    """Stress tests for empirical divergence classifier with noise, false claims, and degenerate runtime inputs."""

    def test_false_claims_alignment_score_degradation(self):
        # 1. Quadratic code claiming O(n)
        res_quad_claim_linear = detect_divergence("O(n)", empirical=2.01)
        self.assertTrue(res_quad_claim_linear["divergence"])
        self.assertEqual(res_quad_claim_linear["nature"], "WORSE_THAN_EXPECTED")
        self.assertLess(res_quad_claim_linear["alignment_score"], 70.0)

        # 2. Cubic code claiming O(n log n)
        res_cube_claim_nlogn = detect_divergence("O(n log n)", empirical=3.02)
        self.assertTrue(res_cube_claim_nlogn["divergence"])
        self.assertEqual(res_cube_claim_nlogn["nature"], "WORSE_THAN_EXPECTED")
        self.assertLess(res_cube_claim_nlogn["alignment_score"], 50.0)

        # 3. Linear code claiming O(1)
        res_linear_claim_o1 = detect_divergence("O(1)", empirical=1.0)
        self.assertTrue(res_linear_claim_o1["divergence"])
        self.assertEqual(res_linear_claim_o1["nature"], "WORSE_THAN_EXPECTED")
        self.assertLess(res_linear_claim_o1["alignment_score"], 75.0)

        # 4. Conforming O(n) implementation
        res_conforming = detect_divergence("O(n)", empirical=1.05)
        self.assertFalse(res_conforming["divergence"])
        self.assertEqual(res_conforming["nature"], "MATCH")
        self.assertEqual(res_conforming["alignment_score"], 100.0)

        # 5. Over-performing (better than expected)
        res_better = detect_divergence("O(n^2)", empirical=0.1)
        self.assertTrue(res_better["divergence"])
        self.assertEqual(res_better["nature"], "BETTER_THAN_EXPECTED")

    def test_noisy_and_jittered_runtime_series(self):
        rng = random.Random(42)
        scales = [100, 200, 400, 800, 1600]
        points_noisy = []
        for n in scales:
            jitter = rng.uniform(-0.15, 0.15)
            t = 1e-6 * (n ** 2) * (1.0 + jitter)
            points_noisy.append((n, t))

        reg = estimate_power_exponent(points_noisy)
        self.assertGreaterEqual(reg["valid_points"], 5)
        self.assertAlmostEqual(reg["p"], 2.0, delta=0.25)
        self.assertGreater(reg["r_squared"], 0.95)

        div_res = detect_divergence("O(n^2)", empirical=points_noisy)
        self.assertFalse(div_res["divergence"])
        self.assertEqual(div_res["nature"], "MATCH")

    def test_degenerate_and_boundary_runtime_points(self):
        # 1. Non-positive runtimes (zeros, negatives)
        points_with_zeros = [(10, 0.0), (100, -0.05), (1000, 0.001), (10000, 0.01)]
        reg = estimate_power_exponent(points_with_zeros)
        self.assertEqual(reg["valid_points"], 2)
        self.assertAlmostEqual(reg["p"], 1.0, delta=0.1)

        # 2. Fewer than 2 valid points
        points_single = [(10, 0.05)]
        reg_single = estimate_power_exponent(points_single)
        self.assertEqual(reg_single["empirical_big_o"], "INSUFFICIENT_DATA")

        # 3. Empty points list
        reg_empty = estimate_power_exponent([])
        self.assertEqual(reg_empty["empirical_big_o"], "INSUFFICIENT_DATA")

        # 4. Zero variance in N (identical scales)
        points_identical_n = [(100, 0.01), (100, 0.02), (100, 0.03)]
        reg_id = estimate_power_exponent(points_identical_n)
        self.assertEqual(reg_id["empirical_big_o"], "DEGENERATE_SCALES")

    def test_extreme_outliers(self):
        points_outlier = [(100, 0.001), (500, 0.005), (1000, 0.999), (5000, 0.050), (10000, 0.100)]
        reg = estimate_power_exponent(points_outlier)
        self.assertIsInstance(reg["p"], float)
        self.assertIsInstance(reg["r_squared"], float)


class TestAptitudeOptionInvariantStress(unittest.TestCase):
    """Generates 200+ randomized questions across all 4 topics and tests mathematical invariants."""

    def test_200_plus_randomized_problems_invariants(self):
        topics = [
            ("interest_difference", AptitudeTopic.INTEREST_DIFFERENCE),
            ("work_collaboration", AptitudeTopic.WORK_COLLABORATION),
            ("urn_probability", AptitudeTopic.URN_PROBABILITY),
            ("cayley_trees", AptitudeTopic.CAYLEY_TREES),
        ]

        total_tested = 0
        seeds = range(1001, 1061)  # 60 seeds * 4 topics = 240 problems

        for topic_name, expected_topic in topics:
            for seed in seeds:
                prob = generate_problem(topic=topic_name, seed=seed)
                total_tested += 1

                # 1. Exactly 4 options
                options = prob["options"]
                self.assertEqual(len(options), 4, f"Failed len(options)==4 for seed={seed}, topic={topic_name}")

                # 2. Strictly distinct options (no duplicate distractors)
                unique_options = set(options)
                self.assertEqual(
                    len(unique_options),
                    4,
                    f"Duplicate options found in seed={seed}, topic={topic_name}: {options}",
                )

                # 3. Correct answer matching
                correct_idx = prob["correct_option_index"]
                self.assertIn(correct_idx, [0, 1, 2, 3])
                self.assertEqual(
                    options[correct_idx],
                    prob["correct_answer"],
                    f"Options[correct_idx] != correct_answer in seed={seed}",
                )

                # 4. Correct option label
                expected_label = ["A", "B", "C", "D"][correct_idx]
                self.assertEqual(prob["correct_option_label"], expected_label)

                # 5. Distractors count and disjointness
                distractors = prob["distractors"]
                self.assertEqual(len(distractors), 3)
                self.assertNotIn(prob["correct_answer"], distractors)

                # 6. Proof text and LaTeX string present and non-empty
                self.assertTrue(prob["latex_proof"], f"Empty latex_proof in seed={seed}")
                self.assertTrue(prob["text_proof"], f"Empty text_proof in seed={seed}")
                self.assertIn("\\begin{aligned}", prob["latex_proof"])
                self.assertIn("\\end{aligned}", prob["latex_proof"])

                # 7. Proof steps has 4 steps
                self.assertEqual(len(prob["proof_steps"]), 4)

                # 8. Domain-specific mathematical verification
                if expected_topic == AptitudeTopic.INTEREST_DIFFERENCE:
                    P = prob["parameters"]["P"]
                    R = prob["parameters"]["R"]
                    years = prob["parameters"]["years"]
                    P_rat = sp.Rational(P, 1)
                    R_rat = sp.Rational(R, 100)
                    if years == 2:
                        expected_delta = P_rat * (R_rat ** 2)
                    else:
                        expected_delta = P_rat * (R_rat ** 2) * (3 + R_rat)
                    self.assertEqual(
                        str(expected_delta),
                        prob["correct_answer"],
                        f"Math error in CI-SI difference for seed={seed}: expected {expected_delta}, got {prob['correct_answer']}",
                    )

                elif expected_topic == AptitudeTopic.WORK_COLLABORATION:
                    A = prob["parameters"]["A"]
                    B = prob["parameters"]["B"]
                    T = prob["parameters"]["target_days"]
                    self.assertEqual(
                        (A * B) // (A + B),
                        T,
                        f"Math error in Work collaboration for seed={seed}: A={A}, B={B}, T={T}",
                    )
                    self.assertEqual(str(T), prob["correct_answer"])

                elif expected_topic == AptitudeTopic.URN_PROBABILITY:
                    r = prob["parameters"]["red"]
                    g = prob["parameters"]["green"]
                    b = prob["parameters"]["blue"]
                    tot = prob["parameters"]["total"]
                    comb_tot = sp.binomial(tot, 2)
                    fav = sp.binomial(r, 2) + sp.binomial(g, 2) + sp.binomial(b, 2)
                    expected_prob = sp.Rational(fav, comb_tot)
                    self.assertEqual(
                        str(expected_prob),
                        prob["correct_answer"],
                        f"Math error in Urn probability for seed={seed}: expected {expected_prob}, got {prob['correct_answer']}",
                    )

                elif expected_topic == AptitudeTopic.CAYLEY_TREES:
                    n = prob["parameters"]["n"]
                    expected_trees = n ** (n - 2)
                    self.assertEqual(
                        str(expected_trees),
                        prob["correct_answer"],
                        f"Math error in Cayley trees for seed={seed}: n={n}, expected {expected_trees}, got {prob['correct_answer']}",
                    )

        self.assertEqual(total_tested, 240, f"Expected 240 problems tested, got {total_tested}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
