"""
Skillora Multiprocessing Sandbox & Divergence Test Suite (tests/test_sandbox.py)
Verifies process isolation, hard timeouts, recursion scopes, log-log regression,
and algorithmic divergence detection against theoretical Big-O bounds.
"""

import math
import statistics
import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.sandbox.mp_runner import execute_in_sandbox, benchmark_scaling, run_empirical_profile
from server.profiler.divergence import (
    estimate_power_exponent,
    classify_exponent,
    detect_divergence,
    normalize_big_o_string,
)


class TestMultiprocessingSandboxHappyPath(unittest.TestCase):
    """Tier 1: Basic isolation, execution correctness, and return value types."""

    def test_arithmetic_execution(self):
        code = "def solve(n):\n    return n * 3"
        res = execute_in_sandbox(code, input_val=14)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["result"], 42)
        self.assertFalse(res["timed_out"])
        self.assertGreater(res["elapsed"], 0.0)

    def test_unified_namespace_recursion(self):
        """Verifies recursive function can find its own name without NameError."""
        code = """
def solve(n):
    if n <= 1:
        return 1
    return n * solve(n - 1)
"""
        res = execute_in_sandbox(code, input_val=6)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["result"], 720)

    def test_complex_return_types(self):
        code = """
def solve(n):
    return {"evens": [i for i in range(n) if i % 2 == 0], "count": n // 2}
"""
        res = execute_in_sandbox(code, input_val=10)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["result"]["count"], 5)
        self.assertEqual(len(res["result"]["evens"]), 5)

    def test_stdout_capture(self):
        code = """
def solve(n):
    print("Debug message 1")
    print(f"Value is {n}")
    return n
"""
        res = execute_in_sandbox(code, input_val=99)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("Debug message 1", res["stdout"])
        self.assertIn("Value is 99", res["stdout"])

    def test_safe_math_library_preloaded(self):
        code = """
def solve(n):
    return int(math.sqrt(n))
"""
        res = execute_in_sandbox(code, input_val=144)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["result"], 12)


class TestMultiprocessingSandboxAdversarialAndBoundaries(unittest.TestCase):
    """Tier 2: Infinite loops, hard timeouts, security violations, and exceptions."""

    def test_infinite_loop_timeout_termination(self):
        """Infinite while True loop is forcefully killed within timeout."""
        code = "def solve(n):\n    while True:\n        pass"
        res = execute_in_sandbox(code, input_val=10, timeout_sec=0.8)
        self.assertEqual(res["status"], "TIMEOUT")
        self.assertTrue(res["timed_out"])
        self.assertIsNone(res["result"])
        self.assertIn("timed out", res["error"].lower())

    def test_deep_recursion_error(self):
        """Deep recursion raises RecursionError inside child without crashing parent."""
        code = """
def solve(n):
    return solve(n + 1)
"""
        res = execute_in_sandbox(code, input_val=1, timeout_sec=1.5)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("RecursionError", res["error"])
        self.assertFalse(res["timed_out"])

    def test_zero_division_error(self):
        code = "def solve(n):\n    return n / 0"
        res = execute_in_sandbox(code, input_val=5)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("ZeroDivisionError", res["error"])

    def test_forbidden_builtin_open_blocked(self):
        code = "def solve(n):\n    with open('test.txt', 'w') as f: f.write('bad')"
        res = execute_in_sandbox(code, input_val=1)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("NameError", res["error"])

    def test_forbidden_builtin_import_blocked(self):
        code = "def solve(n):\n    import os\n    return os.getcwd()"
        res = execute_in_sandbox(code, input_val=1)
        self.assertEqual(res["status"], "ERROR")
        self.assertTrue("ImportError" in res["error"] or "NameError" in res["error"])


class TestBenchmarkScalingHarness(unittest.TestCase):
    """Tier 3: Multi-scale benchmarking and input generators."""

    def test_linear_scaling_execution(self):
        code = "def solve(n):\n    return sum(range(n))"
        scales = [500, 1000, 2000, 4000]
        res = benchmark_scaling(code, scales=scales, timeout_sec=2.0)
        self.assertFalse(res["timed_out"])
        self.assertEqual(len(res["points"]), 4)
        self.assertEqual(res["scales_completed"], scales)

    def test_early_exit_on_timeout_during_scaling(self):
        """When scale 200 times out, higher scales (400, 800) are skipped."""
        code = """
def solve(n):
    if n >= 200:
        while True: pass
    return n
"""
        scales = [100, 200, 400, 800]
        res = benchmark_scaling(code, scales=scales, timeout_sec=1.0)
        self.assertTrue(res["timed_out"])
        self.assertEqual(res["timeout_scale"], 200)
        self.assertEqual(len(res["points"]), 1)
        self.assertEqual(res["scales_completed"], [100])

    def test_reversed_list_input_generator(self):
        code = """
def solve(arr):
    # Selection sort
    for i in range(len(arr)):
        m = i
        for j in range(i+1, len(arr)):
            if arr[j] < arr[m]: m = j
        arr[i], arr[m] = arr[m], arr[i]
    return arr[0]
"""
        scales = [50, 100, 150]
        res = benchmark_scaling(code, scales=scales, input_generator="reversed_list", timeout_sec=2.0)
        self.assertFalse(res["timed_out"])
        self.assertEqual(len(res["points"]), 3)


class TestDivergenceDetectionAndCurveFitting(unittest.TestCase):
    """Tier 3 & 4: Power law regression, Big-O classification, and divergence scenarios."""

    def test_power_exponent_synthetic_linear(self):
        # T = 0.0001 * N^1.0
        scales = [100, 500, 1000, 2000, 5000]
        points = [(n, 0.0001 * n) for n in scales]
        reg = estimate_power_exponent(points)
        self.assertAlmostEqual(reg["p"], 1.0, places=2)
        self.assertEqual(reg["empirical_big_o"], "O(n)")
        self.assertGreaterEqual(reg["r_squared"], 0.99)

    def test_power_exponent_synthetic_quadratic(self):
        # T = 0.00001 * N^2.0
        scales = [100, 200, 400, 800]
        points = [(n, 0.00001 * (n ** 2)) for n in scales]
        reg = estimate_power_exponent(points)
        self.assertAlmostEqual(reg["p"], 2.0, places=2)
        self.assertEqual(reg["empirical_big_o"], "O(n^2)")

    def test_non_positive_runtime_filtering(self):
        # Zero or negative times must be stripped safely
        raw_points = [(100, 0.0), (200, -0.05), (500, 0.01), (1000, 0.02)]
        reg = estimate_power_exponent(raw_points)
        self.assertEqual(reg["valid_points"], 2)
        self.assertAlmostEqual(reg["p"], 1.0, places=2)

    def test_insufficient_points_fallback(self):
        reg = estimate_power_exponent([(100, 0.01)])
        self.assertEqual(reg["p"], 0.0)
        self.assertEqual(reg["empirical_big_o"], "INSUFFICIENT_DATA")

    def test_divergence_matching_linear(self):
        div = detect_divergence("O(n)", 1.05)
        self.assertFalse(div["divergence"])
        self.assertEqual(div["alignment_score"], 100.0)
        self.assertEqual(div["nature"], "MATCH")

    def test_divergence_flagged_quadratic_masquerading_as_linear(self):
        """Crucial Requirement: Student claims O(n), but empirical curve is O(n^2)."""
        div = detect_divergence("O(n)", 2.01)
        self.assertTrue(div["divergence"])
        self.assertEqual(div["nature"], "WORSE_THAN_EXPECTED")
        self.assertLess(div["alignment_score"], 70.0)
        self.assertIn("divergence detected", div["diagnostic"].lower())

    def test_divergence_matching_quadratic(self):
        div = detect_divergence("O(n^2)", 1.98)
        self.assertFalse(div["divergence"])
        self.assertEqual(div["alignment_score"], 100.0)
        self.assertEqual(div["nature"], "MATCH")

    def test_divergence_better_than_expected(self):
        # Student claims O(n^2), but algorithm is actually O(n)
        div = detect_divergence("O(n^2)", 1.02)
        self.assertTrue(div["divergence"])
        self.assertEqual(div["nature"], "BETTER_THAN_EXPECTED")
        self.assertLess(div["alignment_score"], 70.0)


if __name__ == "__main__":
    unittest.main()
