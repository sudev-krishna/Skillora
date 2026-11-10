"""
Skillora Multiprocessing Execution Sandbox (server/sandbox/mp_runner.py)
Executes untrusted student code in an isolated multiprocessing.Process with hard timeouts.
Supports Windows spawn semantics, unified namespace for recursive calls, and monotonic timing.
Zero third-party dependencies (standard library only).
"""

import io
import math
import multiprocessing as mp
from multiprocessing.connection import Connection
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Whitelist of safe builtins permitted in student execution scope
SAFE_BUILTINS: Dict[str, Any] = {
    # Types & Constructors
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "frozenset": frozenset,
    "bytes": bytes,
    "bytearray": bytearray,
    # Sequence Operations & Iterables
    "len": len,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "reversed": reversed,
    "sorted": sorted,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
    "pow": pow,
    "divmod": divmod,
    "all": all,
    "any": any,
    "map": map,
    "filter": filter,
    "iter": iter,
    "next": next,
    "slice": slice,
    # Introspection & Utilities
    "isinstance": isinstance,
    "issubclass": issubclass,
    "callable": callable,
    "repr": repr,
    "print": print,
    "hash": hash,
    "ord": ord,
    "chr": chr,
    "bin": bin,
    "hex": hex,
    "oct": oct,
    # Standard Constants
    "True": True,
    "False": False,
    "None": None,
    # Standard Exception Hierarchy
    "Exception": Exception,
    "BaseException": BaseException,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "IndexError": IndexError,
    "KeyError": KeyError,
    "ZeroDivisionError": ZeroDivisionError,
    "RecursionError": RecursionError,
    "OverflowError": OverflowError,
    "StopIteration": StopIteration,
    "RuntimeError": RuntimeError,
    "AttributeError": AttributeError,
    "LookupError": LookupError,
    "ArithmeticError": ArithmeticError,
    "AssertionError": AssertionError,
}


def _worker_entry(
    code_str: str,
    input_val: Any,
    conn: Connection,
    entry_point: Optional[str] = "solve",
) -> None:
    """
    Worker entry point executed in the spawned child process.
    MUST be defined as a top-level module function for Windows spawn picklability.
    """
    # Buffer stdout and stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    buf_stdout = io.StringIO()
    buf_stderr = io.StringIO()
    sys.stdout = buf_stdout
    sys.stderr = buf_stderr

    # Construct unified execution scope
    scope: Dict[str, Any] = {
        "__builtins__": SAFE_BUILTINS,
        "math": math,
        "input_val": input_val,
        "N": input_val if isinstance(input_val, (int, float)) else None,
    }

    status = "SUCCESS"
    error_msg: Optional[str] = None
    res: Any = None
    elapsed = 0.0

    try:
        # Time the compilation + execution
        t0 = time.perf_counter()
        # Single unified namespace: exec(code, scope, scope) guarantees recursion resolves
        exec(code_str, scope, scope)

        # Call target entry point if defined
        if entry_point and entry_point in scope and callable(scope[entry_point]):
            res = scope[entry_point](input_val) if input_val is not None else scope[entry_point]()
        elif "solution" in scope and callable(scope["solution"]):
            res = scope["solution"](input_val) if input_val is not None else scope["solution"]()
        elif "solve" in scope and callable(scope["solve"]):
            res = scope["solve"](input_val) if input_val is not None else scope["solve"]()
        else:
            # Procedural code; inspect scope for result or last computed variable
            res = scope.get("result", None)

        elapsed = time.perf_counter() - t0
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        status = "ERROR"
        error_msg = f"{type(exc).__name__}: {str(exc)}"
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    # Clamp captured stdout and stderr to prevent IPC pipe buffer bloat
    MAX_OUTPUT_CHARS = 8000
    stdout_raw = buf_stdout.getvalue()
    if len(stdout_raw) > MAX_OUTPUT_CHARS:
        stdout_str = stdout_raw[:MAX_OUTPUT_CHARS] + f"\n... [stdout truncated at {MAX_OUTPUT_CHARS} chars]"
    else:
        stdout_str = stdout_raw

    stderr_raw = buf_stderr.getvalue()
    if len(stderr_raw) > MAX_OUTPUT_CHARS:
        stderr_str = stderr_raw[:MAX_OUTPUT_CHARS] + f"\n... [stderr truncated at {MAX_OUTPUT_CHARS} chars]"
    else:
        stderr_str = stderr_raw

    # Ensure result is serializable; fallback to str(res) if unpicklable
    payload = {
        "status": status,
        "elapsed": elapsed,
        "result": res,
        "error": error_msg,
        "stdout": stdout_str,
        "stderr": stderr_str,
        "timed_out": False,
    }

    try:
        conn.send(payload)
    except Exception:
        # If payload.result cannot be pickled, serialize as string representation
        payload["result"] = str(res)
        try:
            conn.send(payload)
        except Exception:
            pass
    finally:
        conn.close()


def execute_in_sandbox(
    code_str: str,
    input_val: Any = None,
    timeout_sec: float = 2.0,
    entry_point: Optional[str] = "solve",
) -> Dict[str, Any]:
    """
    Executes student Python code in an isolated multiprocessing.Process with hard timeout.

    Args:
        code_str: Python code submitted by student.
        input_val: Optional input passed to the entry point function or available as `N`.
        timeout_sec: Maximum execution duration before forced termination.
        entry_point: Function name to invoke inside student code (default 'solve').

    Returns:
        dict: {"status": "SUCCESS" | "TIMEOUT" | "ERROR", "elapsed": float, "result": Any,
               "error": str | None, "stdout": str, "stderr": str, "timed_out": bool}
    """
    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)

    process = ctx.Process(
        target=_worker_entry,
        args=(code_str, input_val, child_conn, entry_point),
        daemon=True,
    )

    process.start()
    child_conn.close()  # Parent must close child end of pipe

    # Monitor process and poll connection to prevent pipe buffer deadlock
    payload = None
    start_poll = time.perf_counter()
    deadline = start_poll + timeout_sec
    poll_interval = 0.02

    while time.perf_counter() < deadline:
        if parent_conn.poll(poll_interval):
            try:
                payload = parent_conn.recv()
            except (EOFError, OSError):
                pass
            break
        if not process.is_alive():
            # Process exited; drain pipe if data arrived just before exit
            if parent_conn.poll(0.05):
                try:
                    payload = parent_conn.recv()
                except (EOFError, OSError):
                    pass
            break

    # Check if timed out
    if payload is None and process.is_alive():
        # 3-stage watchdog termination
        process.terminate()
        process.join(timeout=0.2)
        if process.is_alive():
            process.kill()
            process.join(timeout=0.2)
        try:
            parent_conn.close()
        except Exception:
            pass
        return {
            "status": "TIMEOUT",
            "elapsed": timeout_sec,
            "result": None,
            "error": f"Execution timed out after {timeout_sec:.2f} seconds",
            "stdout": "",
            "stderr": "",
            "timed_out": True,
        }

    # Grace period join to ensure child is reaped
    process.join(timeout=0.5)
    if process.is_alive():
        process.terminate()
        process.join(timeout=0.2)

    try:
        parent_conn.close()
    except Exception:
        pass

    if payload is None:
        payload = {
            "status": "ERROR",
            "elapsed": 0.0,
            "result": None,
            "error": f"Process exited with code {process.exitcode} without sending result",
            "stdout": "",
            "stderr": "",
            "timed_out": False,
        }

    return payload


def benchmark_scaling(
    code_str: str,
    scales: List[int],
    timeout_sec: float = 2.0,
    input_generator: Optional[Union[str, Callable[[int], Any]]] = None,
    entry_point: Optional[str] = "solve",
) -> Dict[str, Any]:
    """
    Executes student code across scaling input sizes N, measuring empirical runtimes.

    Args:
        code_str: Python code to benchmark.
        scales: List of input sizes (e.g. [100, 500, 1000, 2000, 5000]).
        timeout_sec: Timeout per individual scale execution.
        input_generator: Callable(n) -> input_val, or preset string ('int', 'list', 'reversed_list').
        entry_point: Function name in student code to execute.

    Returns:
        dict: {"points": [(N, elapsed), ...], "results": [dict, ...], "timed_out": bool,
               "timeout_scale": int | None, "scales_completed": [int, ...]}
    """
    points: List[Tuple[int, float]] = []
    results: List[Dict[str, Any]] = []
    timed_out = False
    timeout_scale: Optional[int] = None
    scales_completed: List[int] = []

    for n in scales:
        # Generate input
        if callable(input_generator):
            inp = input_generator(n)
        elif input_generator == "list" or input_generator == "sorted_list":
            inp = list(range(n))
        elif input_generator == "reversed_list":
            inp = list(range(n, 0, -1))
        else:
            inp = n

        res = execute_in_sandbox(code_str, input_val=inp, timeout_sec=timeout_sec, entry_point=entry_point)
        results.append(res)

        if res["timed_out"]:
            timed_out = True
            timeout_scale = n
            # Stop scaling on first timeout
            break

        if res["status"] == "SUCCESS":
            points.append((n, res["elapsed"]))
            scales_completed.append(n)
        else:
            # If runtime error occurred on a scale, abort further scaling
            break

    return {
        "points": points,
        "results": results,
        "timed_out": timed_out,
        "timeout_scale": timeout_scale,
        "scales_completed": scales_completed,
    }


def run_empirical_profile(
    code_str: str,
    input_scales: List[int],
    timeout_sec: float = 2.0,
    entry_point: Optional[str] = "solve",
    input_generator: Optional[Union[str, Callable[[int], Any]]] = None,
) -> Dict[str, Any]:
    """
    High-level facade matching PROJECT.md interface contract.
    Runs scaling benchmark and computes empirical power exponent p and Big-O.
    """
    # Import divergence lazily to avoid circular imports
    from server.profiler.divergence import estimate_power_exponent

    benchmark = benchmark_scaling(
        code_str=code_str,
        scales=input_scales,
        timeout_sec=timeout_sec,
        input_generator=input_generator,
        entry_point=entry_point,
    )

    reg = estimate_power_exponent(benchmark["points"])

    return {
        "points": benchmark["points"],
        "estimated_p": reg["p"],
        "empirical_big_o": reg["empirical_big_o"],
        "r_squared": reg["r_squared"],
        "timed_out": benchmark["timed_out"],
        "timeout_scale": benchmark["timeout_scale"],
        "scales_completed": benchmark["scales_completed"],
    }
