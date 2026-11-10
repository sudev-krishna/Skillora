#!/usr/bin/env python3
"""
Skillora Master Test Runner
Discovers and executes all unittest suites across the tests/ directory.
Provides structured CLI reporting, test category counts, execution timings,
and exit codes (0 for all passed/skipped, 1 for failures/errors).

Usage:
    python tests/run_all_tests.py
    python tests/run_all_tests.py -v
    python tests/run_all_tests.py -s test_pipeline
    python tests/run_all_tests.py -s test_interview_bot
    python tests/run_all_tests.py --failfast
"""

import argparse
import os
import platform
import sys
import time
import unittest
from pathlib import Path
from typing import List, Optional

# Ensure project root is at the head of sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_banner(suite_pattern: str, verbosity: int) -> None:
    """Prints a structured execution banner."""
    print("=" * 78)
    print(" SKILLORA AUTOMATED TEST RUNNER (Python unittest)")
    print("=" * 78)
    print(f" Project Root   : {PROJECT_ROOT}")
    print(f" Python Version : {platform.python_version()} ({platform.python_implementation()})")
    print(f" Platform       : {platform.platform()}")
    print(f" Suite Pattern  : {suite_pattern}")
    print(f" Verbosity Level: {verbosity}")
    print("-" * 78)


def print_summary(
    total_run: int,
    passed: int,
    failures: int,
    errors: int,
    skipped: int,
    duration: float,
    successful: bool,
) -> None:
    """Prints a formatted summary table and final verdict."""
    print("\n" + "=" * 78)
    print(" TEST EXECUTION SUMMARY")
    print("=" * 78)
    print(f"  Total Tests Run : {total_run}")
    print(f"  Passed          : {passed}")
    print(f"  Failed          : {failures}")
    print(f"  Errors          : {errors}")
    print(f"  Skipped         : {skipped}")
    print(f"  Execution Time  : {duration:.3f} seconds")
    print("-" * 78)

    if successful:
        print("  VERDICT: [PASS] All test suites completed successfully.")
        print("=" * 78)
    else:
        print("  VERDICT: [FAIL] One or more tests encountered failures or errors.")
        print("=" * 78)


def run_tests(
    pattern: str = "test_*.py",
    verbosity: int = 2,
    failfast: bool = False,
    buffer: bool = True,
    suite_filter: Optional[str] = None,
) -> int:
    """
    Discovers and executes tests matching pattern in tests/.

    Args:
        pattern: Glob pattern for test file discovery.
        verbosity: Text test runner verbosity (0, 1, or 2).
        failfast: If True, stop immediately on first failure.
        buffer: If True, buffer stdout/stderr during test runs.
        suite_filter: Specific suite name or pattern to run.

    Returns:
        int: 0 if all tests pass (or are skipped), 1 if failures/errors occur.
    """
    tests_dir = PROJECT_ROOT / "tests"
    if not tests_dir.exists():
        print(f"[ERROR] Tests directory does not exist: {tests_dir}", file=sys.stderr)
        return 1

    discovery_pattern = pattern
    if suite_filter:
        clean_filter = suite_filter.strip()
        if not clean_filter.endswith(".py"):
            discovery_pattern = f"*{clean_filter}*.py"
        else:
            discovery_pattern = clean_filter

    print_banner(discovery_pattern, verbosity)

    loader = unittest.defaultTestLoader
    try:
        suite = loader.discover(
            start_dir=str(tests_dir),
            pattern=discovery_pattern,
            top_level_dir=str(PROJECT_ROOT),
        )
    except Exception as err:
        print(f"[FATAL] Test discovery failed: {err}", file=sys.stderr)
        return 1

    total_discovered = suite.countTestCases()
    print(f" Discovered {total_discovered} test cases across test files.")
    print("-" * 78 + "\n")

    start_time = time.perf_counter()
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        failfast=failfast,
        buffer=buffer,
        resultclass=unittest.TextTestResult,
    )
    result = runner.run(suite)
    duration = time.perf_counter() - start_time

    total_run = result.testsRun
    num_failures = len(result.failures)
    num_errors = len(result.errors)
    num_skipped = len(result.skipped)
    num_passed = total_run - num_failures - num_errors - num_skipped
    successful = result.wasSuccessful()

    print_summary(
        total_run=total_run,
        passed=num_passed,
        failures=num_failures,
        errors=num_errors,
        skipped=num_skipped,
        duration=duration,
        successful=successful,
    )

    return 0 if successful else 1


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for test runner."""
    parser = argparse.ArgumentParser(
        description="Skillora Automated Test Runner (Python unittest)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-s",
        "--suite",
        type=str,
        default=None,
        help="Run only tests matching this name/pattern (e.g. 'protocol' or 'test_protocol.py')",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        const=2,
        default=2,
        dest="verbosity",
        help="Verbose test execution output (default)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        const=1,
        dest="verbosity",
        help="Minimal test execution output",
    )
    parser.add_argument(
        "-f",
        "--failfast",
        action="store_true",
        default=False,
        help="Stop execution immediately on first failure or error",
    )
    parser.add_argument(
        "--no-buffer",
        action="store_false",
        default=True,
        dest="buffer",
        help="Do not buffer stdout/stderr during test runs",
    )

    args = parser.parse_args(argv)

    return run_tests(
        verbosity=args.verbosity,
        failfast=args.failfast,
        buffer=args.buffer,
        suite_filter=args.suite,
    )


if __name__ == "__main__":
    sys.exit(main())
