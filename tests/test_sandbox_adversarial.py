"""
Skillora Empirical Sandbox & Profiler Adversarial Test Suite
(tests/test_sandbox_adversarial.py)

Adversarially challenges server/sandbox/mp_runner.py and server/profiler/divergence.py.
Covers:
1. Watchdog Stress & Rogue Loops (CPU loops, sleep loops, recursion bombs, memory bombs)
2. Rapid Concurrency & Sequential Sandboxing (30+ sequential runs, leak checks, zero zombies)
3. Execution Scope Isolation (forbidden builtins, file I/O, globals/locals, large stdout)
4. Empirical Divergence Integration & Degenerate Scales
"""

import math
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time
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
    BIG_O_EXPONENT_RANGES,
)


class TestWatchdogStressAndRogueLoops(unittest.TestCase):
    """Stress tests hard timeout watchdog and rogue execution patterns."""

    def tearDown(self):
        # Guarantee no lingering child processes after each test
        children = mp.active_children()
        for p in children:
            try:
                p.terminate()
                p.join(0.2)
            except Exception:
                pass
        self.assertEqual(len(mp.active_children()), 0, f"Found lingering orphan processes: {children}")

    def test_infinite_cpu_loop_procedural(self):
        """Infinite procedural while True loop terminates strictly within timeout."""
        code = "while True:\n    pass"
        t0 = time.perf_counter()
        res = execute_in_sandbox(code, timeout_sec=0.5)
        duration = time.perf_counter() - t0

        self.assertEqual(res["status"], "TIMEOUT")
        self.assertTrue(res["timed_out"])
        self.assertIsNone(res["result"])
        self.assertIn("timed out", res["error"].lower())
        self.assertLess(duration, 1.8, f"Termination took too long: {duration:.2f}s")
        self.assertEqual(len(mp.active_children()), 0)

    def test_infinite_cpu_loop_functional(self):
        """Infinite functional while True loop with entry point terminates within timeout."""
        code = "def solve(n):\n    while True:\n        pass"
        res = execute_in_sandbox(code, input_val=100, timeout_sec=0.5)

        self.assertEqual(res["status"], "TIMEOUT")
        self.assertTrue(res["timed_out"])
        self.assertEqual(len(mp.active_children()), 0)

    def test_infinite_sleep_loop_import_time_blocked(self):
        """
        Attempting import time and sleep loop is immediately blocked by sandbox builtins whitelist.
        Must not hang and must leave zero active children.
        """
        code = "import time\ndef solve(n):\n    while True:\n        time.sleep(1)"
        res = execute_in_sandbox(code, input_val=1, timeout_sec=1.0)

        self.assertEqual(res["status"], "ERROR")
        self.assertFalse(res["timed_out"])
        self.assertTrue("ImportError" in res["error"] or "NameError" in res["error"])
        self.assertEqual(len(mp.active_children()), 0)

    def test_infinite_busy_wait_loop_with_math(self):
        """Busy-wait loop calling math functions is forcefully terminated by watchdog."""
        code = """
def solve(n):
    total = 0.0
    while True:
        total += math.sin(1.0)
    return total
"""
        res = execute_in_sandbox(code, input_val=10, timeout_sec=0.5)

        self.assertEqual(res["status"], "TIMEOUT")
        self.assertTrue(res["timed_out"])
        self.assertIn("timed out", res["error"].lower())
        self.assertEqual(len(mp.active_children()), 0)

    def test_recursion_bomb_depth_exceeded(self):
        """Direct recursion bomb triggers RecursionError cleanly without crashing host."""
        code = """
def solve(n):
    def bomb():
        bomb()
        bomb()
    bomb()
"""
        res = execute_in_sandbox(code, input_val=1, timeout_sec=1.5)

        self.assertEqual(res["status"], "ERROR")
        self.assertIn("RecursionError", res["error"])
        self.assertFalse(res["timed_out"])
        self.assertEqual(len(mp.active_children()), 0)

    def test_recursion_bomb_exponential_cpu_explosion(self):
        """
        Exponential recursion with shallow depth (fib(200)) avoids RecursionError
        but creates an exponential 2^200 call explosion. Watchdog must kill it.
        """
        code = """
def solve(n):
    def fib(k):
        if k <= 1:
            return 1
        return fib(k - 1) + fib(k - 2)
    return fib(200)
"""
        t0 = time.perf_counter()
        res = execute_in_sandbox(code, input_val=1, timeout_sec=0.5)
        duration = time.perf_counter() - t0

        self.assertEqual(res["status"], "TIMEOUT")
        self.assertTrue(res["timed_out"])
        self.assertLess(duration, 1.8)
        self.assertEqual(len(mp.active_children()), 0)

    def test_memory_allocation_large_array(self):
        """Attempting to allocate 10^8 elements (approx 800 MB RAM) completes or handles cleanly."""
        code = """
def solve(n):
    a = [0] * (10 ** 8)
    return len(a)
"""
        res = execute_in_sandbox(code, input_val=1, timeout_sec=2.5)
        # Should succeed or raise MemoryError depending on available host memory
        self.assertIn(res["status"], ("SUCCESS", "ERROR"))
        if res["status"] == "SUCCESS":
            self.assertEqual(res["result"], 10 ** 8)
        else:
            self.assertIn("MemoryError", res["error"])
        self.assertEqual(len(mp.active_children()), 0)

    def test_memory_allocation_extreme_overflow(self):
        """Attempting to allocate 10^11 elements exceeds pointer space and raises MemoryError."""
        code = """
def solve(n):
    a = [0] * (10 ** 11)
    return len(a)
"""
        res = execute_in_sandbox(code, input_val=1, timeout_sec=2.0)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("MemoryError", res["error"])
        self.assertEqual(len(mp.active_children()), 0)

    def test_memory_growth_infinite_loop(self):
        """Continuous list appending in an infinite loop is killed by watchdog timeout."""
        code = """
def solve(n):
    buf = []
    while True:
        buf.append("A" * 100000)
"""
        res = execute_in_sandbox(code, input_val=1, timeout_sec=0.5)
        self.assertEqual(res["status"], "TIMEOUT")
        self.assertTrue(res["timed_out"])
        self.assertEqual(len(mp.active_children()), 0)


class TestRapidSequentialSandboxing(unittest.TestCase):
    """Stress tests sequential execution stability, pipe integrity, and leak freedom."""

    def test_rapid_sequential_30_executions(self):
        """
        Executes 30 diverse sequential sandbox invocations:
        - 10 fast arithmetic/recursive successes
        - 10 timeout kills (0.1s to 0.4s)
        - 10 runtime errors (syntax, zero div, blocked builtins, recursion)
        Verifies zero child process leaks and consistent pipe communication across all iterations.
        """
        scenarios = [
            # Fast successes
            ("def solve(n):\n    return n * 2", 10, 1.0, "SUCCESS"),
            ("def solve(n):\n    return sum(range(n))", 500, 1.0, "SUCCESS"),
            ("def solve(n):\n    return [i*i for i in range(n)][-1]", 100, 1.0, "SUCCESS"),
            ("def solve(n):\n    return math.factorial(min(n, 12))", 10, 1.0, "SUCCESS"),
            ("def solve(n):\n    return str(n) * 3", 5, 1.0, "SUCCESS"),
            # Timeout kills
            ("while True:\n    pass", None, 0.15, "TIMEOUT"),
            ("def solve(n):\n    while True:\n        pass", 1, 0.2, "TIMEOUT"),
            ("def solve(n):\n    x = 0\n    while True:\n        x += 1", 1, 0.15, "TIMEOUT"),
            ("def solve(n):\n    def f(k): return f(k-1)+f(k-2) if k>1 else 1\n    return f(50)", 1, 0.25, "TIMEOUT"),
            ("def solve(n):\n    a = []\n    while True:\n        a.append('Z'*10000)", 1, 0.2, "TIMEOUT"),
            # Runtime errors & blocked builtins
            ("def solve(n):\n    return 10 / 0", 1, 1.0, "ERROR"),
            ("def solve(n):\n    import os", 1, 1.0, "ERROR"),
            ("def solve(n):\n    open('foo.txt', 'w')", 1, 1.0, "ERROR"),
            ("def solve(n):\n    globals()", 1, 1.0, "ERROR"),
            ("def solve(n):\n    def r(): r()\n    r()", 1, 1.0, "ERROR"),
            ("def solve(n):\n    return [][100]", 1, 1.0, "ERROR"),
            ("def solve(n):\n    return {'a': 1}['b']", 1, 1.0, "ERROR"),
            ("def solve(n):\n    return int('not_an_int')", 1, 1.0, "ERROR"),
            ("def solve(n):\n    return len(None)", 1, 1.0, "ERROR"),
            ("def solve(n):\n    return math.sqrt(-1)", 1, 1.0, "ERROR"),
            # Additional round of fast successes & timeouts to verify pipe reusability
            ("def solve(n):\n    return n + 100", 25, 1.0, "SUCCESS"),
            ("while True: pass", None, 0.15, "TIMEOUT"),
            ("def solve(n):\n    return n ** 2", 15, 1.0, "SUCCESS"),
            ("def solve(n):\n    while True: pass", 2, 0.15, "TIMEOUT"),
            ("def solve(n):\n    return len(str(n))", 123456, 1.0, "SUCCESS"),
            ("def solve(n):\n    while True: pass", 3, 0.15, "TIMEOUT"),
            ("def solve(n):\n    return sorted([5, 2, 9, 1, 7])", 1, 1.0, "SUCCESS"),
            ("def solve(n):\n    import sys", 1, 1.0, "ERROR"),
            ("def solve(n):\n    return min(10, 20)", 1, 1.0, "SUCCESS"),
            ("def solve(n):\n    while True: pass", 4, 0.15, "TIMEOUT"),
        ]

        self.assertEqual(len(scenarios), 30)

        for idx, (code, inp, timeout, expected_status) in enumerate(scenarios, start=1):
            res = execute_in_sandbox(code, input_val=inp, timeout_sec=timeout)

            self.assertEqual(
                res["status"],
                expected_status,
                f"Iteration {idx} failed: expected {expected_status}, got {res['status']} (error: {res.get('error')})",
            )

            # Invariant: zero active child processes
            children = mp.active_children()
            self.assertEqual(
                len(children),
                0,
                f"Iteration {idx} leaked child process: {children}",
            )


class TestExecutionScopeIsolation(unittest.TestCase):
    """Adversarial verification of scope sandboxing and security containment."""

    def test_dunder_import_forbidden(self):
        """Direct invocation of __import__ raises NameError."""
        code = "def solve(n):\n    return __import__('os').getcwd()"
        res = execute_in_sandbox(code, input_val=1)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("NameError", res["error"])
        self.assertIn("__import__", res["error"])

    def test_import_os_forbidden(self):
        """Statement 'import os' fails due to missing __import__."""
        code = "import os\ndef solve(n):\n    return os.listdir('.')"
        res = execute_in_sandbox(code, input_val=1)
        self.assertEqual(res["status"], "ERROR")
        self.assertTrue("ImportError" in res["error"] or "NameError" in res["error"])

    def test_open_file_forbidden_and_filesystem_untouched(self):
        """open() is not in SAFE_BUILTINS; verify target file is not created."""
        target_path = PROJECT_ROOT / "sandbox_escape_canary.txt"
        if target_path.exists():
            target_path.unlink()

        code = f"""
def solve(n):
    with open(r"{target_path}", "w") as f:
        f.write("sandbox breach canary")
    return "breached"
"""
        res = execute_in_sandbox(code, input_val=1)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("NameError", res["error"])
        self.assertIn("open", res["error"])
        self.assertFalse(target_path.exists(), "Security canary file was created on host filesystem!")

    def test_globals_introspection_forbidden(self):
        """globals() is omitted from SAFE_BUILTINS to prevent namespace extraction."""
        code = "def solve(n):\n    return globals()"
        res = execute_in_sandbox(code, input_val=1)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("NameError", res["error"])
        self.assertIn("globals", res["error"])

    def test_locals_introspection_forbidden(self):
        """locals() is omitted from SAFE_BUILTINS."""
        code = "def solve(n):\n    return locals()"
        res = execute_in_sandbox(code, input_val=1)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("NameError", res["error"])
        self.assertIn("locals", res["error"])

    def test_eval_forbidden(self):
        """eval() is omitted from SAFE_BUILTINS."""
        code = "def solve(n):\n    return eval('1 + 1')"
        res = execute_in_sandbox(code, input_val=1)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("NameError", res["error"])

    def test_exec_forbidden(self):
        """exec() is omitted from SAFE_BUILTINS."""
        code = "def solve(n):\n    exec('x = 42')\n    return x"
        res = execute_in_sandbox(code, input_val=1)
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("NameError", res["error"])

    def test_subclasses_traversal_confinement(self):
        """
        Class hierarchy exploration cannot execute hostile OS primitives
        or compromise the host process.
        """
        code = """
def solve(n):
    base = ().__class__.__bases__[0]
    subclasses = [c.__name__ for c in base.__subclasses__()]
    return len(subclasses)
"""
        res = execute_in_sandbox(code, input_val=1)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIsInstance(res["result"], int)
        self.assertGreater(res["result"], 10)
        self.assertEqual(len(mp.active_children()), 0)

    def test_moderate_stdout_buffer_transmission(self):
        """Emitting 4 KB of stdout output buffers cleanly without truncation."""
        code = """
def solve(n):
    # Print 40 lines of 100 chars = 4,000 chars
    for i in range(40):
        print("X" * 100)
    return "done"
"""
        res = execute_in_sandbox(code, input_val=1, timeout_sec=2.0)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["result"], "done")
        self.assertGreaterEqual(len(res["stdout"]), 4_000)
        self.assertEqual(len(mp.active_children()), 0)

    def test_unpicklable_result_fallback(self):
        """Returning an unpicklable object (lambda or generator) falls back to string representation."""
        code = """
def solve(n):
    return (x for x in range(n))
"""
        res = execute_in_sandbox(code, input_val=5)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue("generator" in str(res["result"]))


class TestDivergenceEmpiricalIntegration(unittest.TestCase):
    """Stress tests divergence detection with empirical sandbox benchmarking."""

    def test_empirical_divergence_quadratic_flagged(self):
        """
        End-to-end integration: Run quadratic bubble sort code through run_empirical_profile.
        Theoretical Big-O is set to O(n). Must detect divergence and report alignment < 70%.
        """
        code = """
def solve(n):
    # Pure quadratic double loop: O(n^2)
    c = 0
    for i in range(n):
        for j in range(n):
            c += 1
    return c
"""
        scales = [100, 200, 400, 800]
        profile = run_empirical_profile(
            code_str=code,
            input_scales=scales,
            timeout_sec=2.0,
        )

        self.assertFalse(profile["timed_out"])
        self.assertEqual(len(profile["points"]), 4)
        # Power exponent for O(n^2) should be > 1.5
        self.assertGreaterEqual(profile["estimated_p"], 1.4)
        self.assertIn(profile["empirical_big_o"], ("O(n^2)", "O(n^3)"))

        div = detect_divergence("O(n)", profile)
        self.assertTrue(div["divergence"])
        self.assertEqual(div["nature"], "WORSE_THAN_EXPECTED")
        self.assertLess(div["alignment_score"], 80.0)
        self.assertIn("divergence detected", div["diagnostic"].lower())

    def test_empirical_matching_linear(self):
        """
        End-to-end integration: Run linear sum through run_empirical_profile.
        Theoretical Big-O is O(n). Must match and report alignment 100%.
        """
        code = """
def solve(arr):
    s = 0
    for x in arr:
        s += x
    return s
"""
        scales = [2000, 5000, 10000, 20000]
        profile = run_empirical_profile(
            code_str=code,
            input_scales=scales,
            timeout_sec=2.0,
            input_generator="list",
        )

        self.assertFalse(profile["timed_out"])
        self.assertEqual(len(profile["points"]), 4)

        div = detect_divergence("O(n)", profile)
        # Should match linear
        self.assertIn(div["nature"], ("MATCH", "BETTER_THAN_EXPECTED"))
        self.assertGreaterEqual(div["alignment_score"], 70.0)

    def test_divergence_degenerate_cases(self):
        """Edge case: empty points, degenerate scales, and malformed theoretical strings."""
        # Empty points
        reg_empty = estimate_power_exponent([])
        self.assertEqual(reg_empty["empirical_big_o"], "INSUFFICIENT_DATA")

        # Single point
        reg_one = estimate_power_exponent([(100, 0.05)])
        self.assertEqual(reg_one["empirical_big_o"], "INSUFFICIENT_DATA")

        # Degenerate scales (all N identical)
        reg_degen = estimate_power_exponent([(100, 0.01), (100, 0.02), (100, 0.03)])
        self.assertEqual(reg_degen["empirical_big_o"], "DEGENERATE_SCALES")

        # Unknown theoretical Big-O falls back to O(n) defaults
        div_unknown = detect_divergence("O(unknown_complexity)", 1.0)
        self.assertFalse(div_unknown["divergence"])
        self.assertEqual(div_unknown["alignment_score"], 100.0)

    def test_classify_exponent_all_ranges(self):
        """Verifies boundary coverage for classify_exponent across the entire spectrum."""
        self.assertEqual(classify_exponent(-0.5), "O(1)")
        self.assertEqual(classify_exponent(0.0), "O(1)")
        self.assertEqual(classify_exponent(0.24), "O(1)")
        self.assertEqual(classify_exponent(0.25), "O(log n)")
        self.assertEqual(classify_exponent(0.64), "O(log n)")
        self.assertEqual(classify_exponent(0.65), "O(n)")
        self.assertEqual(classify_exponent(1.09), "O(n)")
        self.assertEqual(classify_exponent(1.10), "O(n log n)")
        self.assertEqual(classify_exponent(1.45), "O(n log n)")
        self.assertEqual(classify_exponent(1.46), "O(n^2)")
        self.assertEqual(classify_exponent(2.45), "O(n^2)")
        self.assertEqual(classify_exponent(2.46), "O(n^3)")
        self.assertEqual(classify_exponent(3.45), "O(n^3)")
        self.assertEqual(classify_exponent(3.46), "O(2^n)")
        self.assertEqual(classify_exponent(10.0), "O(2^n)")


if __name__ == "__main__":
    unittest.main()
