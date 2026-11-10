"""
Skillora Offline Rule-Based Mock Interview Bot: Unified Interview Evaluator.
100% offline, zero external dependencies, standard library only.
Orchestrates 3-tier scoring:
- Tier 1: Keyword & Concept Matching (50% or 70% for pure theory)
- Tier 2: Lexical Quality & Structural Coherence (20% or 30% for pure theory)
- Tier 3: Python AST Static Code Inspection (30% or 0% for pure theory)
Strictly adheres to Interface Contract 5.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

from server.bot.ast_checker import check_code_ast
from server.bot.keyword_matcher import compute_keyword_coverage

logger = logging.getLogger("skillora.bot.evaluator")

# Markdown code fence regex for automatic extraction from student responses
_CODE_FENCE_REGEX = re.compile(r"```(?:python)?\s*([\s\S]*?)```", re.IGNORECASE)

# Structural markers for technical writing evaluation
_LIST_MARKER_REGEX = re.compile(
    r"(?:^|\n)\s*(?:[-*•]|\d+\.|\(\d+\)|\d+\))\s+\S+", re.MULTILINE
)
_DEFINITION_MARKER_REGEX = re.compile(
    r"\b(?:is defined as|are defined as|refers to|refer to|is a technique|is an algorithm|is a data structure|"
    r"is the process of|represents|represent|means that|means|describes|describe)\b",
    re.IGNORECASE
)
_COMPLEXITY_MARKER_REGEX = re.compile(
    r"\b(?:time complexity|space complexity|runtime|auxiliary space|big-o|o\s*\([^)]+\))\b",
    re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Tier 2: Lexical & Structural Quality Evaluator
# ---------------------------------------------------------------------------
def evaluate_lexical_structure(text: str) -> Dict[str, Any]:
    """
    Evaluates communication maturity, structure, and lexical depth:
    - Length curve (up to 35 pts)
    - Lexical diversity / Type-Token Ratio (up to 20 pts)
    - Structured formatting (bullets/numbered lists) (up to 15 pts)
    - Definitional introductory statements (up to 15 pts)
    - Algorithmic complexity mentions (up to 15 pts)
    Returns normalized structure_score in [0.0, 100.0] and diagnostic feedback.
    """
    clean_text = (text or "").strip()
    words = [w.lower() for w in re.findall(r"\b\w+\b", clean_text)]
    total_words = len(words)

    if total_words == 0:
        return {
            "structure_score": 0.0,
            "word_count": 0,
            "type_token_ratio": 0.0,
            "has_formatting": False,
            "has_definition": False,
            "has_complexity": False,
            "strengths": [],
            "gaps": ["No verbal or conceptual explanation provided."],
            "suggestions": ["Articulate your conceptual reasoning in complete sentences."],
        }

    strengths: List[str] = []
    gaps: List[str] = []
    suggestions: List[str] = []

    # 1. Word Length Curve (up to 35 pts)
    if total_words < 15:
        score_length = 5.0
        gaps.append(f"Response is too brief ({total_words} words); lacks technical depth.")
        suggestions.append("Expand on your explanation with definition, trade-offs, and examples.")
    elif total_words < 35:
        score_length = 18.0
        suggestions.append("Provide additional technical context to demonstrate complete mastery.")
    elif total_words < 55:
        score_length = 28.0
    elif total_words <= 350:
        score_length = 35.0
        strengths.append(f"Well-balanced explanation length ({total_words} words).")
    else:
        # Slightly verbose but comprehensive
        score_length = 30.0
        strengths.append(f"Detailed explanation provided ({total_words} words).")

    # 2. Type-Token Ratio / Lexical Diversity (up to 20 pts)
    unique_words = set(words)
    ttr = len(unique_words) / total_words
    if ttr >= 0.45 or (total_words < 30 and ttr >= 0.60):
        score_diversity = 20.0
        strengths.append("High lexical diversity and varied technical vocabulary.")
    elif ttr >= 0.35:
        score_diversity = 15.0
    elif ttr >= 0.25:
        score_diversity = 10.0
    else:
        score_diversity = 5.0
        gaps.append("Low vocabulary diversity detected; avoid repeating identical phrases.")
        suggestions.append("Vary your phrasing and explore broader technical concepts.")

    # 3. Structural Formatting (bullets / numbered points) (up to 15 pts)
    has_formatting = bool(_LIST_MARKER_REGEX.search(clean_text))
    if has_formatting:
        score_lists = 15.0
        strengths.append("Structured response using clear bulleted or numbered breakdown.")
    else:
        score_lists = 0.0
        suggestions.append("Organize multi-step technical explanations into numbered points or bullet lists.")

    # 4. Introductory Definition (up to 15 pts)
    has_definition = bool(_DEFINITION_MARKER_REGEX.search(clean_text))
    if has_definition:
        score_definition = 15.0
        strengths.append("Clear opening technical definition provided.")
    else:
        score_definition = 0.0

    # 5. Complexity Analysis Mention (up to 15 pts)
    has_complexity = bool(_COMPLEXITY_MARKER_REGEX.search(clean_text))
    if has_complexity:
        score_complexity = 15.0
        strengths.append("Explicitly analyzed asymptotic time or space complexity.")
    else:
        score_complexity = 0.0
        suggestions.append("Always state the time and space complexity of your approach.")

    total_structure_score = min(
        100.0,
        score_length + score_diversity + score_lists + score_definition + score_complexity
    )

    return {
        "structure_score": round(total_structure_score, 2),
        "word_count": total_words,
        "type_token_ratio": round(ttr, 3),
        "has_formatting": has_formatting,
        "has_definition": has_definition,
        "has_complexity": has_complexity,
        "strengths": strengths,
        "gaps": gaps,
        "suggestions": suggestions,
    }


# ---------------------------------------------------------------------------
# Code Snippet & Question Normalization Helpers
# ---------------------------------------------------------------------------
def _extract_code_and_text(
    student_answer: str,
    explicit_code: str
) -> Tuple[str, str]:
    """
    Separates natural language explanation from embedded Python code blocks.
    If explicit_code is provided, uses that.
    Otherwise, extracts markdown ```python ... ``` code fences if present.
    If no code fences are found, automatically detects raw Python code blocks
    (e.g. definitions, classes, statements) and separates them from explanation text.
    """
    if explicit_code and explicit_code.strip():
        # Code explicitly provided; text is student_answer
        return student_answer.strip(), explicit_code.strip()

    raw_answer = (student_answer or "").strip()
    if not raw_answer:
        return "", ""

    code_blocks: List[str] = []

    def _replace_fence(match: re.Match[str]) -> str:
        code_content = match.group(1).strip()
        if code_content:
            code_blocks.append(code_content)
        return ""

    text_without_code = _CODE_FENCE_REGEX.sub(_replace_fence, raw_answer).strip()
    extracted_code = "\n\n".join(code_blocks).strip()

    if extracted_code:
        return text_without_code, extracted_code

    # Fallback: scan for raw Python code lines when code fences are omitted
    lines = raw_answer.splitlines()
    code_lines: List[str] = []
    text_lines: List[str] = []
    in_code_block = False

    _CODE_START_PREFIXES = ("def ", "class ", "async def ", "import ", "from ")
    _CODE_CONTINUATION_PREFIXES = (
        "return", "if ", "elif ", "else:", "for ", "while ",
        "try:", "except", "finally:", "with ", "raise ", "pass",
        "yield", "assert ", "print(",
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_code_block:
                code_lines.append(line)
            else:
                text_lines.append(line)
            continue

        is_code_start = any(stripped.startswith(p) for p in _CODE_START_PREFIXES)
        is_indented = line.startswith(("    ", "\t"))
        is_code_cont = in_code_block and (
            is_indented
            or any(stripped.startswith(p) for p in _CODE_CONTINUATION_PREFIXES)
            or line.startswith("#")
            or bool(re.match(r"^[a-zA-Z_]\w*\s*(?:[+\-*/%&|^]?=|\.append|\.extend|\.add|\.remove|\.pop)\b", stripped))
        )

        if is_code_start or (in_code_block and (is_indented or is_code_cont)):
            in_code_block = True
            code_lines.append(line)
        else:
            in_code_block = False
            text_lines.append(line)

    candidate_code = "\n".join(code_lines).strip()
    candidate_text = "\n".join(text_lines).strip()

    if candidate_code:
        try:
            tree = ast.parse(candidate_code)
            if tree.body:
                return candidate_text, candidate_code
        except SyntaxError:
            try:
                tree = ast.parse(raw_answer)
                if tree.body:
                    return "", raw_answer.strip()
            except SyntaxError:
                if any(p in candidate_code for p in ("def ", "class ", "return ")):
                    return candidate_text, candidate_code

    if raw_answer.strip():
        try:
            tree = ast.parse(raw_answer.strip())
            has_code_nodes = any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                  ast.For, ast.While, ast.If, ast.With, ast.Try))
                for node in ast.walk(tree)
            )
            if has_code_nodes:
                return "", raw_answer.strip()
        except SyntaxError:
            pass

    return raw_answer.strip(), ""


def _normalize_question_data(question: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalizes question dictionary across DB schema, DAO formats, and seed dicts."""
    category = str(question.get("category", "Coding")).strip()
    question_text = str(question.get("question_text", question.get("topic", ""))).strip()

    # Model answer / canonical solution
    model_answer = str(
        question.get("model_answer", question.get("symbolic_solution", ""))
    ).strip()

    # Keywords parsing
    raw_kw = question.get("expected_keywords", question.get("expected_keywords_csv", []))
    if isinstance(raw_kw, str):
        expected_keywords = [k.strip() for k in raw_kw.split(",") if k.strip()]
    elif isinstance(raw_kw, (list, tuple, set)):
        expected_keywords = [str(k).strip() for k in raw_kw if str(k).strip()]
    else:
        expected_keywords = []

    # Test cases & rubric parsing
    raw_tc = question.get("test_cases", question.get("test_cases_json", {}))
    if isinstance(raw_tc, str):
        try:
            test_cases = json.loads(raw_tc)
        except Exception:
            test_cases = {}
    elif isinstance(raw_tc, dict):
        test_cases = dict(raw_tc)
    else:
        test_cases = {}

    expected_constructs = test_cases.get("expected_constructs", [])
    if isinstance(expected_constructs, (list, tuple)):
        expected_constructs = [str(c).strip() for c in expected_constructs if str(c).strip()]
    else:
        expected_constructs = []

    rubric = test_cases.get("rubric", {})
    if not isinstance(rubric, dict):
        rubric = {}

    return {
        "category": category,
        "question_text": question_text,
        "model_answer": model_answer,
        "expected_keywords": expected_keywords,
        "expected_constructs": expected_constructs,
        "rubric": rubric,
    }


# ---------------------------------------------------------------------------
# Main Evaluator Entry Point (Interface Contract 5)
# ---------------------------------------------------------------------------
def evaluate_answer(
    question: Mapping[str, Any],
    student_answer: str,
    code_snippet: str = ""
) -> Dict[str, Any]:
    """
    Evaluates candidate response across 3-tier offline rubric.
    Strictly adheres to Interface Contract 5.

    Returns:
        {
            "total_score": float,              # 0.0 - 100.0
            "keyword_score": float,            # Tier 1 score
            "structure_score": float,          # Tier 2 score (lexical & structural)
            "lexical_score": float,            # Alias of structure_score
            "ast_score": float,                # Tier 3 score (Python AST)
            "strengths": List[str],
            "gaps": List[str],
            "suggestions": List[str],
            "detected_constructs": List[str],
            "flagged_anti_patterns": List[str],
            "model_answer": str
        }
    """
    q_data = _normalize_question_data(question)
    explanation_text, code = _extract_code_and_text(student_answer, code_snippet)

    # Combine text and code for keyword matching so keywords in code comments/variable names count
    combined_text = f"{explanation_text}\n{code}".strip()

    # 1. Tier 1: Keyword & Concept Matching
    kw_result = compute_keyword_coverage(
        student_text=combined_text,
        expected_keywords=q_data["expected_keywords"]
    )
    keyword_score = kw_result["keyword_score"]

    # 2. Tier 2: Lexical & Structural Quality
    lex_result = evaluate_lexical_structure(explanation_text or student_answer)
    structure_score = lex_result["structure_score"]

    # 3. Tier 3: Python AST Static Code Inspection
    has_code = bool(code.strip())
    ast_result = check_code_ast(
        code_snippet=code,
        expected_constructs=q_data["expected_constructs"]
    )
    ast_score = ast_result["ast_score"]

    # 4. Dynamic Rubric Resolution
    # Check if explicit rubric provided in test_cases
    rubric = q_data["rubric"]
    is_pure_theory = (
        q_data["category"].lower() in ("technical", "aptitude")
        or (not q_data["expected_constructs"] and not has_code)
    )

    if "keywords" in rubric and "structure" in rubric and not has_code:
        # Question explicitly configured with custom rubric (e.g. 70/30 theory)
        w_keywords = float(rubric.get("keywords", 0.70))
        w_structure = float(rubric.get("structure", 0.30))
        w_ast = float(rubric.get("ast", 0.0))
    elif is_pure_theory and not has_code:
        # Pure theoretical question without code submission
        w_keywords = 0.70
        w_structure = 0.30
        w_ast = 0.0
    else:
        # Coding question or response with code snippet
        w_keywords = 0.50
        w_structure = 0.20
        w_ast = 0.30

    # Ensure weights sum to 1.0
    sum_w = w_keywords + w_structure + w_ast
    if sum_w > 0:
        w_keywords /= sum_w
        w_structure /= sum_w
        w_ast /= sum_w

    # Calculate final composite score
    total_score = round(
        (w_keywords * keyword_score) + (w_structure * structure_score) + (w_ast * ast_score),
        2
    )
    total_score = max(0.0, min(100.0, total_score))

    # 5. Synthesize Strengths, Gaps, and Suggestions
    strengths: List[str] = []
    gaps: List[str] = []
    suggestions: List[str] = []

    # Keyword feedback
    if kw_result["matched_keywords"]:
        strengths.append(f"Captured key technical concepts: {', '.join(kw_result['matched_keywords'][:5])}")
    if kw_result["missing_keywords"]:
        gaps.append(f"Missed essential concepts: {', '.join(kw_result['missing_keywords'][:5])}")
        suggestions.append(f"Discuss {', '.join(kw_result['missing_keywords'][:3])} to enhance completeness.")

    # Lexical feedback
    strengths.extend(lex_result["strengths"])
    gaps.extend(lex_result["gaps"])
    suggestions.extend(lex_result["suggestions"])

    # AST feedback (only if code was analyzed or expected)
    if has_code or q_data["expected_constructs"]:
        strengths.extend(ast_result["strengths"])
        gaps.extend(ast_result["gaps"])
        suggestions.extend(ast_result["suggestions"])

    # Empty answer guard
    if not (explanation_text or code):
        total_score = 0.0
        keyword_score = 0.0
        structure_score = 0.0
        ast_score = 0.0
        strengths = []
        gaps = ["No response submitted."]
        suggestions = ["Review the question requirements and model answer."]

    # Deduplicate while preserving order
    def _dedup(items: List[str]) -> List[str]:
        seen = set()
        out = []
        for it in items:
            clean = it.strip()
            if clean and clean not in seen:
                seen.add(clean)
                out.append(clean)
        return out

    return {
        "total_score": total_score,
        "keyword_score": keyword_score,
        "structure_score": structure_score,
        "lexical_score": structure_score,
        "ast_score": ast_score,
        "strengths": _dedup(strengths),
        "gaps": _dedup(gaps),
        "suggestions": _dedup(suggestions),
        "detected_constructs": ast_result["detected_constructs"],
        "flagged_anti_patterns": ast_result["flagged_anti_patterns"],
        "model_answer": q_data["model_answer"],
    }
