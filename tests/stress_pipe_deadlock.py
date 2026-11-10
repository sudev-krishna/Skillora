"""
Skillora Empirical Stress Reproduction Script: OS Pipe Buffer Deadlock
(tests/stress_pipe_deadlock.py)

Demonstrates the OS Pipe Buffer Deadlock defect in server/sandbox/mp_runner.py:
When stdout or return data exceeds the OS anonymous pipe buffer (~8,192 bytes on Windows),
the child process blocks on conn.send(payload) waiting for the reader to drain the pipe.
Meanwhile, the parent process synchronously blocks on process.join(timeout=timeout_sec)
without reading from parent_conn.
This results in mutual deadlock until watchdog timeout forcibly kills the child.
"""

import multiprocessing as mp
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.sandbox.mp_runner import execute_in_sandbox


def test_stdout_thresholds():
    print("=" * 70)
    print("1. EMPIRICAL TEST: Stdout Buffer Scaling Across 8 KB Pipe Threshold")
    print("=" * 70)
    sizes = [1000, 4000, 8000, 8500, 9000, 15000]

    for s in sizes:
        code = f"def solve(n):\n    print('X' * {s})\n    return 'COMPLETED'"
        t0 = time.perf_counter()
        res = execute_in_sandbox(code, input_val=1, timeout_sec=1.0)
        wall_time = time.perf_counter() - t0

        print(
            f"  Payload Size {s:5d} bytes: status={res['status']:7s} "
            f"timed_out={str(res['timed_out']):5s} elapsed={res['elapsed']:.2f}s "
            f"wall_clock={wall_time:.2f}s children={len(mp.active_children())}"
        )


def test_large_data_return():
    print("\n" + "=" * 70)
    print("2. EMPIRICAL TEST: Large Data Return Serialization Deadlock")
    print("=" * 70)
    counts = [500, 1000, 2000, 5000]

    for c in counts:
        code = f"def solve(n):\n    return list(range({c}))"
        t0 = time.perf_counter()
        res = execute_in_sandbox(code, input_val=1, timeout_sec=1.0)
        wall_time = time.perf_counter() - t0

        is_list = isinstance(res.get("result"), list)
        print(
            f"  List Length {c:5d} items: status={res['status']:7s} "
            f"timed_out={str(res['timed_out']):5s} elapsed={res['elapsed']:.2f}s "
            f"wall_clock={wall_time:.2f}s is_list={is_list}"
        )


if __name__ == "__main__":
    print("Skillora M3 Empirical Challenger: Pipe Deadlock Reproduction Harness\n")
    test_stdout_thresholds()
    test_large_data_return()
    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
