"""
Skillora Offline Rule-Based Mock Interview Bot: Python AST Static Code Checker.
100% offline, zero external dependencies, Python standard library 'ast' module only.
Parses code safely, extracts structural constructs, detects anti-patterns/code smells,
and provides detailed syntax diagnostics and scoring.
"""

from __future__ import annotations

import ast
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("skillora.bot.ast_checker")


# ---------------------------------------------------------------------------
# Construct Visitor
# ---------------------------------------------------------------------------
class ASTConstructVisitor(ast.NodeVisitor):
    """
    Traverses the AST to detect canonical algorithmic constructs,
    recursion, type annotations, and docstrings.
    """

    def __init__(self) -> None:
        super().__init__()
        self.constructs: Set[str] = set()
        self.has_recursion: bool = False
        self.has_type_annotations: bool = False
        self.has_docstrings: bool = False
        self._function_scope_stack: List[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.constructs.add("FunctionDef")
        if ast.get_docstring(node):
            self.has_docstrings = True

        # Check type annotations in arguments or return type
        if node.returns is not None:
            self.has_type_annotations = True
        for arg in node.args.args + node.args.kwonlyargs:
            if arg.annotation is not None:
                self.has_type_annotations = True

        self._function_scope_stack.append(node.name)
        self.generic_visit(node)
        self._function_scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.constructs.add("AsyncFunctionDef")
        self.constructs.add("FunctionDef")
        if ast.get_docstring(node):
            self.has_docstrings = True
        if node.returns is not None:
            self.has_type_annotations = True

        self._function_scope_stack.append(node.name)
        self.generic_visit(node)
        self._function_scope_stack.pop()

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.has_type_annotations = True
        self.constructs.add("Assign")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.constructs.add("For")
        self.constructs.add("Loop")
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.constructs.add("AsyncFor")
        self.constructs.add("Loop")
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.constructs.add("While")
        self.constructs.add("Loop")
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        self.constructs.add("If")
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.constructs.add("If")
        self.constructs.add("IfExp")
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self.constructs.add("ListComp")
        self.constructs.add("Comprehension")
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self.constructs.add("DictComp")
        self.constructs.add("Comprehension")
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self.constructs.add("SetComp")
        self.constructs.add("Comprehension")
        self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self.constructs.add("GeneratorExp")
        self.constructs.add("Comprehension")
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        if node.ifs:
            self.constructs.add("If")
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self.constructs.add("Try")
        self.generic_visit(node)

    def visit_Yield(self, node: ast.Yield) -> None:
        self.constructs.add("Yield")
        self.constructs.add("Generator")
        self.generic_visit(node)

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        self.constructs.add("YieldFrom")
        self.constructs.add("Generator")
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        self.constructs.add("Return")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.constructs.add("Assign")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.constructs.add("AugAssign")
        self.constructs.add("Assign")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Detect recursion: function call whose name matches any enclosing function in scope
        if isinstance(node.func, ast.Name):
            callee_name = node.func.id
            if callee_name in self._function_scope_stack:
                self.has_recursion = True
                self.constructs.add("Recursion")
        elif isinstance(node.func, ast.Attribute):
            # Check self.method() or cls.method() recursion
            if isinstance(node.func.value, ast.Name) and node.func.value.id in ("self", "cls"):
                if node.func.attr in self._function_scope_stack:
                    self.has_recursion = True
                    self.constructs.add("Recursion")

        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Anti-Pattern & Code Smell Detector
# ---------------------------------------------------------------------------
class ASTAntiPatternDetector(ast.NodeVisitor):
    """
    Inspects syntax tree for dangerous practices, code smells, and anti-patterns:
    - Bare except: clauses (catches SystemExit/KeyboardInterrupt)
    - eval() / exec() / __import__() dynamic code execution
    - global variable declarations
    - range(len(...)) non-idiomatic iteration
    - dead/unreachable code after unconditional return/raise/break
    - mutable default arguments in functions (def f(x=[]):)
    - infinite while True without break
    """

    def __init__(self) -> None:
        super().__init__()
        self.anti_patterns: List[str] = []
        self.details: List[str] = []
        self.penalties: float = 0.0

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # Bare except: statement where exception type is None
        if node.type is None:
            self.anti_patterns.append("bare_except")
            self.details.append(
                f"Line {node.lineno}: Bare 'except:' clause masks unexpected exceptions; "
                f"use 'except Exception:' instead."
            )
            self.penalties += 15.0
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # eval, exec, __import__, compile
        if isinstance(node.func, ast.Name):
            if node.func.id in ("eval", "exec", "__import__", "compile"):
                self.anti_patterns.append("eval_or_exec")
                self.details.append(
                    f"Line {node.lineno}: Dangerous dynamic code execution '{node.func.id}()' detected."
                )
                self.penalties += 30.0
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        self.anti_patterns.append("global_variable")
        names_str = ", ".join(node.names)
        self.details.append(
            f"Line {node.lineno}: Non-idiomatic global variable mutation 'global {names_str}'."
        )
        self.penalties += 10.0
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        # Detect for i in range(len(arr)):
        if isinstance(node.iter, ast.Call):
            call_node = node.iter
            if isinstance(call_node.func, ast.Name) and call_node.func.id == "range":
                if call_node.args and isinstance(call_node.args[0], ast.Call):
                    inner_call = call_node.args[0]
                    if isinstance(inner_call.func, ast.Name) and inner_call.func.id == "len":
                        self.anti_patterns.append("range_len")
                        self.details.append(
                            f"Line {node.lineno}: Non-idiomatic 'range(len(...))' loop. "
                            f"Prefer 'enumerate()' or direct iteration."
                        )
                        self.penalties += 10.0

        self._check_block_dead_code(node.body)
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        # Check while True: without a break
        is_while_true = False
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            is_while_true = True

        if is_while_true:
            has_break = any(isinstance(n, ast.Break) for n in ast.walk(node))
            if not has_break:
                self.anti_patterns.append("infinite_while_true")
                self.details.append(
                    f"Line {node.lineno}: 'while True' loop contains no 'break' statement; "
                    f"risks infinite execution."
                )
                self.penalties += 25.0

        self._check_block_dead_code(node.body)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Check mutable default arguments: def f(a=[]) or def f(a={})
        for default in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.anti_patterns.append("mutable_default_arg")
                self.details.append(
                    f"Line {node.lineno}: Mutable default argument in function '{node.name}'. "
                    f"Use 'None' and initialize inside function."
                )
                self.penalties += 10.0

        self._check_block_dead_code(node.body)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_block_dead_code(node.body)
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        self._check_block_dead_code(node.body)
        if node.orelse:
            self._check_block_dead_code(node.orelse)
        self.generic_visit(node)

    def _check_block_dead_code(self, stmts: List[ast.stmt]) -> None:
        """Flags statements occurring strictly after an unconditional return, raise, or break."""
        terminator_encountered = False
        terminator_line = 0

        for stmt in stmts:
            if terminator_encountered:
                self.anti_patterns.append("dead_code")
                self.details.append(
                    f"Line {stmt.lineno}: Unreachable dead code after terminating statement at line {terminator_line}."
                )
                self.penalties += 10.0
                break

            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break)):
                terminator_encountered = True
                terminator_line = stmt.lineno


# ---------------------------------------------------------------------------
# AST Static Code Inspection Entry Point
# ---------------------------------------------------------------------------
def check_code_ast(
    code_snippet: str,
    expected_constructs: Optional[List[str]] = None,
    forbidden_patterns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Performs complete static AST inspection on a Python code snippet:
    - Parses safely with standard library ast.parse.
    - Handles SyntaxError gracefully with line/column diagnostic without crashing.
    - Extracts detected structural constructs and best practices.
    - Identifies anti-patterns and code smells.
    - Returns standardized dictionary with ast_score in [0.0, 100.0].
    """
    clean_code = (code_snippet or "").strip()
    if not clean_code:
        return {
            "is_valid_syntax": True,
            "ast_score": 0.0,
            "detected_constructs": [],
            "missing_constructs": list(expected_constructs or []),
            "flagged_anti_patterns": [],
            "anti_pattern_details": [],
            "syntax_error": None,
            "has_recursion": False,
            "has_type_annotations": False,
            "has_docstrings": False,
            "strengths": [],
            "gaps": ["No code snippet provided for static AST evaluation."],
            "suggestions": ["Provide a complete Python implementation."],
        }

    # Safe AST parse with error handling
    try:
        tree = ast.parse(clean_code)
    except SyntaxError as err:
        error_msg = f"SyntaxError at line {err.lineno or '?'}, col {err.offset or '?'}: {err.msg}"
        return {
            "is_valid_syntax": False,
            "ast_score": 0.0,
            "detected_constructs": [],
            "missing_constructs": list(expected_constructs or []),
            "flagged_anti_patterns": [],
            "anti_pattern_details": [],
            "syntax_error": error_msg,
            "has_recursion": False,
            "has_type_annotations": False,
            "has_docstrings": False,
            "strengths": [],
            "gaps": [f"Code contains syntax error: {error_msg}"],
            "suggestions": ["Ensure code compiles cleanly without Python syntax errors."],
        }

    # 1. Inspect constructs
    visitor = ASTConstructVisitor()
    visitor.visit(tree)
    detected_constructs = sorted(list(visitor.constructs))

    # 2. Inspect anti-patterns
    anti_detector = ASTAntiPatternDetector()
    anti_detector.visit(tree)
    flagged_anti_patterns = sorted(list(set(anti_detector.anti_patterns)))
    anti_pattern_details = anti_detector.details

    # 3. Calculate construct coverage
    strengths: List[str] = []
    gaps: List[str] = []
    suggestions: List[str] = []

    expected = list(expected_constructs or [])
    missing_constructs: List[str] = []
    if expected:
        matched = [c for c in expected if c in visitor.constructs]
        missing = [c for c in expected if c not in visitor.constructs]
        missing_constructs = missing
        coverage_ratio = len(matched) / len(expected)
        base_score = coverage_ratio * 100.0

        if matched:
            strengths.append(f"Implemented required constructs: {', '.join(matched)}")
        if missing:
            gaps.append(f"Missing expected algorithmic constructs: {', '.join(missing)}")
            suggestions.append(f"Consider integrating {', '.join(missing)} for optimal implementation structure.")
    else:
        # No specific constructs demanded; valid code has 100 base score
        base_score = 100.0
        if detected_constructs:
            strengths.append(f"Structured syntax utilizing: {', '.join(detected_constructs[:4])}")

    # 4. Best practice bonuses
    bonuses = 0.0
    if visitor.has_type_annotations:
        bonuses += 5.0
        strengths.append("Employed PEP 484 type annotations for clarity.")
    if visitor.has_docstrings:
        bonuses += 5.0
        strengths.append("Included informative function/module docstrings.")
    if visitor.has_recursion:
        strengths.append("Utilized clean recursive decomposition.")

    # 5. Anti-pattern penalties
    penalties = anti_detector.penalties
    for detail in anti_pattern_details:
        gaps.append(f"Code smell: {detail}")
    if flagged_anti_patterns:
        suggestions.append(
            f"Refactor to eliminate anti-patterns: {', '.join(set(flagged_anti_patterns))}."
        )

    # Composite AST score clamped to [0.0, 100.0]
    final_ast_score = max(0.0, min(100.0, base_score + bonuses - penalties))

    return {
        "is_valid_syntax": True,
        "ast_score": round(final_ast_score, 2),
        "detected_constructs": detected_constructs,
        "missing_constructs": missing_constructs,
        "flagged_anti_patterns": flagged_anti_patterns,
        "anti_pattern_details": anti_pattern_details,
        "syntax_error": None,
        "has_recursion": visitor.has_recursion,
        "has_type_annotations": visitor.has_type_annotations,
        "has_docstrings": visitor.has_docstrings,
        "strengths": strengths,
        "gaps": gaps,
        "suggestions": suggestions,
    }


def analyze_code_ast(
    code_snippet: str,
    expected_constructs: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Convenience alias for check_code_ast adhering to interface specification.
    """
    return check_code_ast(code_snippet, expected_constructs)
