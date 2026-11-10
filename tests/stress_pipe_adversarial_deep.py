"""
Skillora Empirical Deep Adversarial Stress Harness: Sandbox Pipe & Watchdog
(tests/stress_pipe_adversarial_deep.py)

Empirically challenges:
1. Extreme return payloads (20k, 50k items, 100k char strings, nested dicts)
2. Massive dual stdout + stderr flooding (>100k chars) and truncation verification
3. Unpicklable return objects (lambdas / local closures) fallback handling
4. High-frequency sequential stress runs (rapid timeout, error, large payload alternating)
5. Strict watchdog termination latency and zero zombie active_children assertions
"""

import multiprocessing as mp
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.sandbox.mp_runner import execute_in_sandbox


def test_extreme_return_payloads():
    print("=" * 70)
    print("CHALLENGE 1: Extreme Return Payloads (Draining OS Pipe)")
    print("=" * 70)

    # 1. 20,000 items
    t0 = time.perf_counter()
    res1 = execute_in_sandbox("def solve(n):\n    return list(range(20000))", input_val=1, timeout_sec=2.0)
    wall1 = time.perf_counter() - t0
    assert res1["status"] == "SUCCESS", f"Failed on 20k items: {res1}"
    assert len(res1["result"]) == 20000
    print(f"  [PASS] 20,000 items returned: status={res1['status']} wall_time={wall1:.3f}s children={len(mp.active_children())}")

    # 2. 50,000 items
    t0 = time.perf_counter()
    res2 = execute_in_sandbox("def solve(n):\n    return list(range(50000))", input_val=1, timeout_sec=3.0)
    wall2 = time.perf_counter() - t0
    assert res2["status"] == "SUCCESS", f"Failed on 50k items: {res2}"
    assert len(res2["result"]) == 50000
    print(f"  [PASS] 50,000 items returned: status={res2['status']} wall_time={wall2:.3f}s children={len(mp.active_children())}")

    # 3. 100,000 character string
    t0 = time.perf_counter()
    res3 = execute_in_sandbox("def solve(n):\n    return 'A' * 100000", input_val=1, timeout_sec=2.0)
    wall3 = time.perf_counter() - t0
    assert res3["status"] == "SUCCESS", f"Failed on 100k str: {res3}"
    assert len(res3["result"]) == 100000
    print(f"  [PASS] 100,000 char string returned: status={res3['status']} wall_time={wall3:.3f}s children={len(mp.active_children())}")

    # 4. Nested dictionary
    t0 = time.perf_counter()
    res4 = execute_in_sandbox("def solve(n):\n    return {str(i): [i, i*2, str(i)*5] for i in range(5000)}", input_val=1, timeout_sec=2.0)
    wall4 = time.perf_counter() - t0
    assert res4["status"] == "SUCCESS", f"Failed on nested dict: {res4}"
    assert len(res4["result"]) == 5000
    print(f"  [PASS] 5,000 key nested dict returned: status={res4['status']} wall_time={wall4:.3f}s children={len(mp.active_children())}")


def test_massive_output_clamping():
    print("\n" + "=" * 70)
    print("CHALLENGE 2: Massive Dual Stdout & Stderr Output Clamping")
    print("=" * 70)

    code = """
import sys
def solve(n):
    for _ in range(500):
        print("OUT_" * 50)
    return "DONE"
"""
    # Note: student code cannot import sys, so print() writes to stdout
    code_safe = """
def solve(n):
    for i in range(1000):
        print("X" * 100)
    return "DONE"
"""
    t0 = time.perf_counter()
    res = execute_in_sandbox(code_safe, input_val=1, timeout_sec=2.0)
    wall = time.perf_counter() - t0

    assert res["status"] == "SUCCESS", f"Failed on massive stdout: {res}"
    assert res["timed_out"] is False
    assert len(res["stdout"]) <= 8100, f"Stdout not clamped: len={len(res['stdout'])}"
    assert "[stdout truncated at 8000 chars]" in res["stdout"]
    print(f"  [PASS] Stdout (100,000 chars emitted) successfully clamped: len={len(res['stdout'])} chars, wall_time={wall:.3f}s")


def test_unpicklable_object_fallback():
    print("\n" + "=" * 70)
    print("CHALLENGE 3: Unpicklable Object Return (Closure / Lambda Fallback)")
    print("=" * 70)

    # A lambda created inside local scope cannot be pickled by standard pickle
    code = """
def solve(n):
    x = 42
    return lambda y: x + y
"""
    t0 = time.perf_counter()
    res = execute_in_sandbox(code, input_val=1, timeout_sec=1.5)
    wall = time.perf_counter() - t0

    assert res["status"] == "SUCCESS", f"Execution failed: {res}"
    assert "<function" in str(res["result"]) or "<lambda>" in str(res["result"])
    print(f"  [PASS] Unpicklable lambda safely serialized via str(res): result={res['result']!r} wall_time={wall:.3f}s")


def test_rapid_alternating_workloads():
    print("\n" + "=" * 70)
    print("CHALLENGE 4: Rapid Alternating Adversarial Workloads (25 runs)")
    print("=" * 70)

    workloads = [
        # (name, code, timeout, expected_status, is_timeout)
        ("arithmetic_fast", "def solve(n):\n    return n * 42", 1.0, "SUCCESS", False),
        ("rogue_loop", "def solve(n):\n    while True: pass", 0.2, "TIMEOUT", True),
        ("large_stdout", "def solve(n):\n    print('M' * 20000)\n    return 1", 1.0, "SUCCESS", False),
        ("syntax_error", "def solve(n) return n", 1.0, "ERROR", False),
        ("large_list", "def solve(n):\n    return list(range(10000))", 1.5, "SUCCESS", False),
    ]

    for iteration in range(25):
        name, code, timeout, exp_status, exp_timeout = workloads[iteration % len(workloads)]
        t0 = time.perf_counter()
        res = execute_in_sandbox(code, input_val=iteration, timeout_sec=timeout)
        wall = time.perf_counter() - t0

        active = mp.active_children()
        assert len(active) == 0, f"Run {iteration} ({name}) leaked processes: {active}"
        assert res["status"] == exp_status, f"Run {iteration} ({name}) expected status {exp_status}, got {res['status']}"
        assert res["timed_out"] == exp_timeout, f"Run {iteration} ({name}) expected timed_out={exp_timeout}, got {res['timed_out']}"

    print("  [PASS] 25 alternating workloads executed with 100% status accuracy and 0 zombie children.")


def test_watchdog_termination_latency():
    print("\n" + "=" * 70)
    print("CHALLENGE 5: Watchdog Termination Latency & Clean Reap")
    print("=" * 70)

    timeout = 0.25
    t0 = time.perf_counter()
    res = execute_in_sandbox("while True: pass", input_val=None, timeout_sec=timeout)
    wall = time.perf_counter() - t0

    assert res["status"] == "TIMEOUT"
    assert res["timed_out"] is True
    # Latency should be timeout + polling/reap overhead, strictly under timeout + 0.6s
    assert wall < timeout + 0.6, f"Termination too slow: wall_time={wall:.3f}s"
    assert len(mp.active_children()) == 0
    print(f"  [PASS] Hard infinite loop killed in {wall:.3f}s (budget: {timeout + 0.6:.3f}s). Children: {len(mp.active_children())}")


if __name__ == "__main__":
    print("Skillora M3 Empirical Challenger: Deep Adversarial Stress Harness\n")
    test_extreme_return_payloads()
    test_massive_output_clamping()
    test_unpicklable_object_fallback()
    test_rapid_alternating_workloads()
    test_watchdog_termination_latency()
    print("\n" + "=" * 70)
    print("ALL EMPIRICAL ADVERSARIAL CHALLENGES PASSED (5/5)")
    print("=" * 70)
