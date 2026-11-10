"""
Skillora Milestone 4 Adversarial Stress & Empirical Challenge Suite.
Adversarially challenges:
- server/bot/keyword_matcher.py (gaming, spamming, word salad, typos, leetspeak, punctuation noise, substring leaks)
- server/bot/ast_checker.py (nesting bombs, recursion, all 7 anti-patterns simultaneously, syntax bombs)
- server/bot/evaluator.py (Interface Contract 5, seed question bank evaluation across 30 questions)
"""

from __future__ import annotations

import difflib
import json
import string
import unittest
from typing import Any, Dict, List

from server.bot.ast_checker import analyze_code_ast, check_code_ast
from server.bot.evaluator import _normalize_question_data, evaluate_answer, evaluate_lexical_structure
from server.bot.keyword_matcher import (
    TECHNICAL_SYNONYMS,
    compute_keyword_coverage,
    match_keywords,
    match_single_keyword,
    normalize_text,
    stem_token,
)
from server.db.seed_data import QUESTIONS_SEED_DATA


class TestAdversarialKeywordGaming(unittest.TestCase):
    """
    Adversarial attacks targeting keyword matching and concept density:
    - Single keyword stuffing / spamming
    - Multi-keyword word salad repetition
    - Leetspeak, typos, and noisy punctuation
    - Extremely long inputs (5k+ words)
    - Substring leakage vulnerability proof
    - Boundary and empty inputs
    """

    def test_single_keyword_stuffing_lexical_penalty(self) -> None:
        """
        Attacking a multi-concept question by spamming a single keyword 100 times.
        Candidate should be heavily penalized by missing concepts and low TTR diversity.
        """
        question = {
            "category": "Technical",
            "topic": "OS: Deadlocks",
            "expected_keywords": [
                "deadlock", "Coffman conditions", "mutual exclusion",
                "hold and wait", "no preemption", "circular wait"
            ],
            "test_cases": {"rubric": {"keywords": 0.70, "structure": 0.30}}
        }
        spammed_answer = "deadlock " * 100
        result = evaluate_answer(question, spammed_answer)

        # Structure score must be heavily penalized for low vocabulary diversity (TTR)
        self.assertLessEqual(result["structure_score"], 45.0)

        # Gaps must explicitly highlight missing concepts and low diversity
        self.assertTrue(
            any("low vocabulary diversity" in g.lower() for g in result["gaps"]),
            f"Expected diversity penalty in gaps, got: {result['gaps']}"
        )
        self.assertTrue(
            any("missed essential concepts" in g.lower() for g in result["gaps"]),
            f"Expected missing concepts in gaps, got: {result['gaps']}"
        )

    def test_keyword_matcher_substring_leakage_vulnerability(self) -> None:
        """
        REMEDIATION VERIFICATION:
        Verifies that whole-word boundary enforcement prevents substring leakage:
        - Target 'log' must NOT match inside 'analog' or 'dialogue'.
        - Target 'mutual exclusion' with synonym 'lock' must NOT match inside 'deadlock'.
        - Authentic whole-word occurrences must still match with 1.0 credit.
        """
        tokens = ["we", "use", "an", "analog", "dialogue"]
        stemmed_tokens = set(stem_token(t) for t in tokens)
        norm_text = "we use an analog dialogue"

        # Case 1: Target 'log' does NOT match inside 'analog' and 'dialogue'
        score_log, match_log = match_single_keyword(
            target="log",
            normalized_text=norm_text,
            tokens=tokens,
            stemmed_tokens=stemmed_tokens,
            stemmed_target="log",
            target_synonyms=set(),
        )
        self.assertEqual(match_log, "none")
        self.assertEqual(score_log, 0.0)

        # Authentic 'log' whole word matches
        valid_tokens = ["inspect", "system", "log", "file"]
        score_valid, match_valid = match_single_keyword(
            target="log",
            normalized_text="inspect system log file",
            tokens=valid_tokens,
            stemmed_tokens=set(stem_token(t) for t in valid_tokens),
            stemmed_target="log",
            target_synonyms=set(),
        )
        self.assertEqual(match_valid, "exact")
        self.assertEqual(score_valid, 1.0)

        # Case 2: Target 'mutual exclusion' has synonym 'lock'.
        # Word 'deadlock' must NOT trigger synonym match for 'lock'
        deadlock_tokens = ["deadlock"]
        score_mutex, match_mutex = match_single_keyword(
            target="mutual exclusion",
            normalized_text="deadlock",
            tokens=deadlock_tokens,
            stemmed_tokens=set(stem_token(t) for t in deadlock_tokens),
            stemmed_target=stem_token("mutual exclusion"),
            target_synonyms={"mutual exclusion", "lock", "mutex"},
        )
        self.assertEqual(match_mutex, "none")
        self.assertEqual(score_mutex, 0.0)

        # Authentic 'lock' whole word matches synonym
        lock_tokens = ["acquire", "lock"]
        score_lock, match_lock = match_single_keyword(
            target="mutual exclusion",
            normalized_text="acquire lock",
            tokens=lock_tokens,
            stemmed_tokens=set(stem_token(t) for t in lock_tokens),
            stemmed_target=stem_token("mutual exclusion"),
            target_synonyms={"mutual exclusion", "lock", "mutex"},
        )
        self.assertEqual(match_lock, "synonym")
        self.assertEqual(score_lock, 1.0)

    def test_all_keywords_word_salad_repetition_penalized(self) -> None:
        """
        Candidate dumps all expected keywords repeated 25 times in a word salad without
        proper definitions, bullet points, complexity, or grammatical sentences.
        Structure score must be penalized (<= 45.0) and vocabulary diversity flagged.
        """
        question = {
            "category": "Technical",
            "topic": "DBMS: ACID Properties",
            "expected_keywords": [
                "ACID", "atomicity", "consistency", "isolation", "durability", "WAL"
            ],
            "test_cases": {"rubric": {"keywords": 0.70, "structure": 0.30}}
        }
        word_salad = "ACID atomicity consistency isolation durability WAL " * 25
        result = evaluate_answer(question, word_salad)

        # Structure score is penalized for lack of definitions, lists, and low TTR
        self.assertLessEqual(result["structure_score"], 45.0)
        # Verify gap flags low diversity or repetition
        self.assertTrue(
            any("vocabulary diversity" in g.lower() or "repeating" in g.lower() for g in result["gaps"])
        )
        # Suggestions must urge formatting and definition
        self.assertTrue(
            any("organize" in s.lower() or "phrasing" in s.lower() for s in result["suggestions"])
        )

    def test_typo_variations_and_punctuation_noise(self) -> None:
        """
        Verifies robustness against punctuation noise, casing, and typos requested in dispatch:
        - 'h@sh table' -> fuzzy match
        - 'b1nary search' -> fuzzy match
        - 'O(N LOG N)!!!' -> exact match
        - 'multi-threading' -> exact match
        """
        # 1. Punctuation noise inside word: "h@sh table"
        res1 = compute_keyword_coverage("We use a h@sh table for lookup.", ["hash table"])
        self.assertIn("hash table", res1["matched_keywords"])
        self.assertGreaterEqual(res1["keyword_score"], 80.0)

        # 2. Leetspeak single typo: "b1nary search"
        res2 = compute_keyword_coverage("Perform b1nary search over the array.", ["binary search"])
        self.assertIn("binary search", res2["matched_keywords"])
        self.assertGreaterEqual(res2["keyword_score"], 80.0)

        # 3. Exclamation and irregular casing: "O(N LOG N)!!!"
        res3 = compute_keyword_coverage("The algorithm runs in O(N LOG N)!!! time.", ["o(n log n)"])
        self.assertIn("o(n log n)", res3["matched_keywords"])
        self.assertEqual(res3["keyword_score"], 100.0)

        # 4. Hyphenated / unhyphenated compound: "multi-threading"
        res4 = compute_keyword_coverage("Achieve concurrency with multi-threading.", ["multi-threading"])
        self.assertIn("multi-threading", res4["matched_keywords"])
        self.assertEqual(res4["keyword_score"], 100.0)

        # 5. Additional noisy permutations
        noise_text = "Using r3cursion to invert tree with O( 1 ) extra-memory and d@t@base index."
        res5 = compute_keyword_coverage(noise_text, ["recursion", "o(1) space", "database", "index"])
        self.assertGreaterEqual(len(res5["matched_keywords"]), 3)

    def test_extreme_word_flood_concept_density(self) -> None:
        """
        Candidate dumps a 5,000-word essay containing a couple keywords buried inside.
        Verifies concept density is appropriately low and no timeout or catastrophic slowdown occurs.
        """
        filler = ("The placement preparation system evaluates candidate readiness across multiple rounds. " * 500)
        text = f"We implement a binary search tree. {filler} The time complexity is logarithmic."
        res = compute_keyword_coverage(text, ["binary search tree", "recursion", "hash map"])

        # Matched 1 keyword out of 3, but in a 5,000+ word ocean
        self.assertIn("binary search tree", res["matched_keywords"])
        self.assertLessEqual(res["concept_density"], 0.005)
        # Should not get any density bonus
        self.assertLessEqual(res["keyword_score"], 35.0)

    def test_empty_and_noise_only_inputs(self) -> None:
        """Verifies graceful handling of empty, whitespace, and symbol-only inputs."""
        question = {
            "category": "Technical",
            "expected_keywords": ["hash map", "two pointer"],
            "test_cases": {"rubric": {"keywords": 0.70, "structure": 0.30}}
        }
        # Empty string
        res_empty = evaluate_answer(question, "")
        self.assertEqual(res_empty["total_score"], 0.0)
        self.assertEqual(res_empty["keyword_score"], 0.0)
        self.assertEqual(res_empty["structure_score"], 0.0)
        self.assertIn("No response submitted.", res_empty["gaps"])

        # Pure whitespace
        res_spaces = evaluate_answer(question, "   \n\t  ")
        self.assertEqual(res_spaces["total_score"], 0.0)

        # Symbol noise
        res_noise = evaluate_answer(question, "!@#$%^&*()_+-=[]{}|;':,.<>?/")
        self.assertLessEqual(res_noise["total_score"], 10.0)
        self.assertEqual(res_noise["keyword_score"], 0.0)


class TestASTParserAdversarialBombs(unittest.TestCase):
    """
    Adversarial stress testing of Python AST static code checker:
    - Extreme nesting depths (brackets, parentheses, expressions)
    - Deep and multi-scope recursive constructs
    - Simultaneous presence of all 7 anti-patterns
    - Malformed and incomplete syntax bombs
    """

    def test_extreme_nesting_depth_brackets_and_parens(self) -> None:
        """
        50 to 80 levels of nested brackets and parentheses.
        Parser must parse safely without RecursionError or crash.
        """
        # 50 levels of brackets
        nested_brackets = "[" * 50 + "1" + "]" * 50
        res1 = analyze_code_ast(nested_brackets)
        self.assertTrue(res1["is_valid_syntax"])
        self.assertIsNone(res1["syntax_error"])
        self.assertEqual(res1["ast_score"], 100.0)

        # 60 levels of nested parentheses
        nested_parens = "(" * 60 + "42" + ")" * 60
        res2 = analyze_code_ast(nested_parens)
        self.assertTrue(res2["is_valid_syntax"])
        self.assertIsNone(res2["syntax_error"])
        self.assertEqual(res2["ast_score"], 100.0)

        # Deeply nested list comprehensions
        nested_comp = "[x for x in [y for y in [z for z in range(10)]]]"
        res3 = analyze_code_ast(nested_comp, ["ListComp", "Comprehension"])
        self.assertTrue(res3["is_valid_syntax"])
        self.assertIn("ListComp", res3["detected_constructs"])

    def test_deep_recursive_functions(self) -> None:
        """
        Tests direct recursion, nested helper recursion, and method recursion.
        Verifies 'Recursion' is reliably detected across scopes.
        """
        # 1. Direct recursion with type annotations
        code1 = (
            "def fib(n: int) -> int:\n"
            "    if n <= 1:\n"
            "        return n\n"
            "    return fib(n - 1) + fib(n - 2)\n"
        )
        res1 = analyze_code_ast(code1, ["FunctionDef", "Recursion", "If", "Return"])
        self.assertTrue(res1["has_recursion"])
        self.assertTrue(res1["has_type_annotations"])
        self.assertIn("Recursion", res1["detected_constructs"])
        self.assertEqual(res1["ast_score"], 100.0)  # Clamped to 100.0 max

        # 2. Nested helper recursion
        code2 = (
            "def outer(nums: list[int]) -> int:\n"
            "    def helper(idx: int) -> int:\n"
            "        if idx >= len(nums):\n"
            "            return 0\n"
            "        return nums[idx] + helper(idx + 1)\n"
            "    return helper(0)\n"
        )
        res2 = analyze_code_ast(code2, ["Recursion"])
        self.assertTrue(res2["has_recursion"])
        self.assertIn("Recursion", res2["detected_constructs"])

        # 3. Class method recursion using self.method()
        code3 = (
            "class Solution:\n"
            "    def dfs(self, node):\n"
            "        if not node:\n"
            "            return 0\n"
            "        return 1 + self.dfs(node.left) + self.dfs(node.right)\n"
        )
        res3 = analyze_code_ast(code3, ["Recursion"])
        self.assertTrue(res3["has_recursion"])
        self.assertIn("Recursion", res3["detected_constructs"])

    def test_simultaneous_all_seven_anti_patterns(self) -> None:
        """
        Adversarial snippet containing all 7 anti-patterns simultaneously:
        1. bare_except
        2. eval_or_exec
        3. global_variable
        4. range_len
        5. infinite_while_true
        6. mutable_default_arg
        7. dead_code
        Verifies complete detection, penalty accumulation, and score clamping to 0.0.
        """
        catastrophic_code = (
            "def catastrophic_function(items=[], cache={}):\n"
            "    global system_counter\n"
            "    try:\n"
            "        eval('1 + 2')\n"
            "    except:\n"
            "        pass\n"
            "    for i in range(len(items)):\n"
            "        print(items[i])\n"
            "    while True:\n"
            "        pass\n"
            "    return 42\n"
            "    print('This is dead unreachable code')\n"
        )
        res = analyze_code_ast(catastrophic_code)
        self.assertTrue(res["is_valid_syntax"])

        expected_patterns = {
            "bare_except",
            "eval_or_exec",
            "global_variable",
            "range_len",
            "infinite_while_true",
            "mutable_default_arg",
            "dead_code",
        }
        detected = set(res["flagged_anti_patterns"])

        for pat in expected_patterns:
            self.assertIn(
                pat, detected,
                f"Missing expected anti-pattern '{pat}' from detected: {detected}"
            )

        # Anti-pattern penalties: 15 + 30 + 10 + 10 + 25 + 10 + 10 = 110!
        # Base 100 - 110 = -10, clamped to 0.0
        self.assertEqual(res["ast_score"], 0.0)
        self.assertGreaterEqual(len(res["anti_pattern_details"]), 7)

    def test_malformed_incomplete_syntax_zero_unhandled_exceptions(self) -> None:
        """
        Tests varied malformed syntax constructs.
        analyze_code_ast must catch SyntaxError cleanly and return informative diagnostics.
        """
        syntax_bombs = [
            ("def missing_colon()\n    pass", "missing colon in header"),
            ("def unclosed_list():\n    return [1, 2, 3", "unclosed bracket"),
            ("def bad_indent():\nreturn 1", "indentation error"),
            ("while True:", "unexpected EOF"),
            ("for in if else:", "scrambled keywords"),
            ("print 'python 2 print syntax'", "Python 2 print statement"),
            ("x = 1\n  y = 2", "unexpected indentation"),
            ("import = 42", "keyword as variable"),
        ]

        for code_snippet, label in syntax_bombs:
            with self.subTest(label=label):
                res = analyze_code_ast(code_snippet)
                self.assertFalse(res["is_valid_syntax"], f"Failed for {label}")
                self.assertEqual(res["ast_score"], 0.0)
                self.assertIsNotNone(res["syntax_error"])
                self.assertTrue(len(res["syntax_error"]) > 0)
                self.assertTrue(
                    any("syntax error" in g.lower() for g in res["gaps"]),
                    f"Expected syntax error note in gaps for {label}"
                )


class TestSeedQuestionBankScoreSeparation(unittest.TestCase):
    """
    Empirical testing of seed question bank from server/db/seed_data.py.
    Tests 25+ questions across Technical, DSA, and System Design categories.
    For every question, verifies strict separation:
      score(model_benchmark) >= 85.0%
      40.0% <= score(mediocre_answer) <= 75.0%
      score(irrelevant_answer) <= 20.0%
      score(model) > score(mediocre) > score(irrelevant)
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.questions = QUESTIONS_SEED_DATA
        cls.assertTrue(
            len(cls.questions) >= 20,
            f"Expected at least 20 seed questions, found {len(cls.questions)}"
        )

    def test_seed_questions_count_and_domains(self) -> None:
        """Verifies the question bank contains questions across required domains."""
        categories = {q.get("category") for q in self.questions}
        self.assertIn("Coding", categories)
        self.assertIn("Technical", categories)

        topics = [q.get("topic", "") for q in self.questions]
        self.assertTrue(any("DSA" in t for t in topics), "Missing DSA questions")
        self.assertTrue(any("OS" in t for t in topics), "Missing OS questions")
        self.assertTrue(any("DBMS" in t for t in topics), "Missing DBMS questions")
        self.assertTrue(any("CN" in t for t in topics), "Missing CN questions")
        self.assertTrue(any("Python" in t for t in topics), "Missing Python questions")
        self.assertTrue(any("System Design" in t for t in topics), "Missing System Design questions")

    def test_seed_questions_three_tier_score_separation(self) -> None:
        """
        Runs evaluate_answer on 25+ questions with:
        a) Benchmark Model answer: assert score >= 85.0%
        b) Mediocre / partial answer: assert 40.0% <= score <= 75.0%
        c) Irrelevant answer: assert score <= 20.0%
        """
        tested_count = 0

        for i, q in enumerate(self.questions):
            category = q.get("category", "Technical")
            topic = q.get("topic", f"Question {i}")
            raw_kws = q.get("expected_keywords_csv", "")
            kws = [k.strip() for k in raw_kws.split(",") if k.strip()]

            # 1. Benchmark Model Answer:
            # Contains all expected keywords, structured bullet points, definition, and complexity
            if category == "Coding":
                code_snippet = (
                    "def solution(arr: list[int]) -> int:\n"
                    "    '''Optimized algorithm implementation.'''\n"
                    "    left, right = 0, len(arr) - 1\n"
                    "    result = []\n"
                    "    while left <= right:\n"
                    "        mid = left + (right - left) // 2\n"
                    "        result.append(arr[mid])\n"
                    "        if arr[mid] == 0:\n"
                    "            return mid\n"
                    "        left += 1\n"
                    "    return -1\n"
                )
                model_text = (
                    f"- Problem definition: This algorithm is defined as an efficient solution using {', '.join(kws[:4])}.\n"
                    f"- Method explanation: We process the elements systematically covering {', '.join(kws[4:])}.\n"
                    f"- Complexity analysis: The algorithm operates in O(N) time complexity and O(1) space complexity."
                )
                res_model = evaluate_answer(q, model_text, code_snippet)
            else:
                model_text = (
                    f"This concept is defined as a fundamental architecture in software systems.\n"
                    f"- Key principles: We address {', '.join(kws[:5])} to ensure correctness.\n"
                    f"- Implementation details: The system maintains {', '.join(kws[5:])} for robustness.\n"
                    f"- Complexity and trade-offs: We analyze runtime performance and space complexity constraints."
                )
                res_model = evaluate_answer(q, model_text)

            score_model = res_model["total_score"]
            self.assertGreaterEqual(
                score_model, 85.0,
                f"Question {i} [{topic}] benchmark model answer score {score_model}% < 85.0%. "
                f"Details: kw={res_model['keyword_score']}, struct={res_model['structure_score']}, ast={res_model['ast_score']}, gaps={res_model['gaps']}"
            )

            # 2. Mediocre / partial answer evaluation:
            # Contains ~50% of keywords, rudimentary explanation, basic loops/conditionals
            half_kws = kws[:max(2, len(kws) // 2)]
            if category == "Coding":
                mediocre_text = (
                    f"This problem can be addressed by applying {', '.join(half_kws)}. "
                    f"We iterate over the elements to check conditions and maintain the state across iterations."
                )
                mediocre_code = (
                    "def solution(arr):\n"
                    "    for x in arr:\n"
                    "        if x > 0:\n"
                    "            return x\n"
                    "    return -1\n"
                )
                res_mediocre = evaluate_answer(q, mediocre_text, mediocre_code)
            else:
                mediocre_text = (
                    f"This concept relates to {', '.join(half_kws)}. "
                    f"It is used across system operations to organize execution flow and manage components."
                )
                res_mediocre = evaluate_answer(q, mediocre_text)

            score_mediocre = res_mediocre["total_score"]
            self.assertGreaterEqual(
                score_mediocre, 40.0,
                f"Question {i} [{topic}] mediocre answer score {score_mediocre}% < 40.0%. "
                f"Details: kw={res_mediocre['keyword_score']}, struct={res_mediocre['structure_score']}, ast={res_mediocre['ast_score']}"
            )
            self.assertLessEqual(
                score_mediocre, 75.0,
                f"Question {i} [{topic}] mediocre answer score {score_mediocre}% > 75.0%. "
                f"Details: kw={res_mediocre['keyword_score']}, struct={res_mediocre['structure_score']}, ast={res_mediocre['ast_score']}"
            )

            # 3. Irrelevant answer evaluation:
            irrelevant_text = (
                "Baking a traditional chocolate sponge cake requires all-purpose flour, cocoa powder, "
                "fresh eggs, and vanilla extract preheated to 350 degrees."
            )
            res_irrelevant = evaluate_answer(q, irrelevant_text)
            score_irrelevant = res_irrelevant["total_score"]

            self.assertLessEqual(
                score_irrelevant, 20.0,
                f"Question {i} [{topic}] irrelevant answer score {score_irrelevant}% > 20.0%. "
                f"Details: kw={res_irrelevant['keyword_score']}, struct={res_irrelevant['structure_score']}"
            )

            # 4. Strict monotonic separation
            self.assertGreater(
                score_model, score_mediocre,
                f"Question {i} [{topic}]: model score {score_model} <= mediocre score {score_mediocre}"
            )
            self.assertGreater(
                score_mediocre, score_irrelevant,
                f"Question {i} [{topic}]: mediocre score {score_mediocre} <= irrelevant score {score_irrelevant}"
            )

            tested_count += 1

        self.assertGreaterEqual(tested_count, 25, f"Only tested {tested_count} questions")

    def test_raw_seed_data_symbolic_solution_discrepancy(self) -> None:
        """
        REMEDIATION VERIFICATION:
        Audits raw 'symbolic_solution' from QUESTIONS_SEED_DATA evaluated via evaluate_answer.
        Verifies that all 30 seed questions achieve >= 85.0% score:
        1. Coding solutions have markdown code fences and structured complexity analysis.
        2. Technical solutions contain all required keywords and structured explanations.
        3. AST parser detects code constructs with ast_score == 100.0 for coding questions.
        """
        passing_questions = []
        failing_questions = []

        for i, q in enumerate(self.questions):
            model = q.get("symbolic_solution", "")
            res = evaluate_answer(q, model)
            score = res["total_score"]
            topic = q.get("topic", "")
            cat = q.get("category", "")

            if score >= 85.0:
                passing_questions.append((i, topic, score))
            else:
                failing_questions.append((i, topic, cat, score, res["keyword_score"], res["ast_score"]))

        # Verify all 30 questions achieve >= 85.0% score when raw symbolic_solution is evaluated
        self.assertEqual(
            len(passing_questions), 30,
            f"Expected 30 passing questions, got {len(passing_questions)}. Failing: {failing_questions}"
        )
        self.assertEqual(
            len(failing_questions), 0,
            f"Expected 0 failing questions, got {len(failing_questions)}: {failing_questions}"
        )

        # Verify all 8 coding questions achieve ast_score == 100.0
        for i in range(8):
            q = self.questions[i]
            res = evaluate_answer(q, q.get("symbolic_solution", ""))
            self.assertEqual(
                res["ast_score"], 100.0,
                f"Coding question {i} [{q.get('topic')}] AST score {res['ast_score']} != 100.0"
            )


class TestInterfaceContract5AdversarialFuzzing(unittest.TestCase):
    """
    Fuzzing evaluate_answer against degraded, incomplete, and unexpected inputs.
    Verifies Interface Contract 5 dictionary contract is invariant.
    """

    def test_contract_keys_and_types_present(self) -> None:
        """Every evaluate_answer call must return all Interface Contract 5 fields."""
        q = {
            "category": "Coding",
            "topic": "Sample Question",
            "expected_keywords": ["hash map"],
            "model_answer": "Sample model answer",
        }
        result = evaluate_answer(q, "Sample student answer", "def foo(): pass")

        required_keys = {
            "total_score",
            "keyword_score",
            "structure_score",
            "ast_score",
            "strengths",
            "gaps",
            "model_answer",
        }
        for k in required_keys:
            self.assertIn(k, result, f"Interface Contract 5 missing required key '{k}'")

        # Extended fields check
        extended_keys = {
            "lexical_score",
            "suggestions",
            "detected_constructs",
            "flagged_anti_patterns",
        }
        for k in extended_keys:
            self.assertIn(k, result, f"Extended evaluator missing key '{k}'")

        # Numerical bounds
        for score_key in ("total_score", "keyword_score", "structure_score", "ast_score", "lexical_score"):
            val = result[score_key]
            self.assertIsInstance(val, (int, float), f"{score_key} must be numeric")
            self.assertTrue(0.0 <= val <= 100.0, f"{score_key} out of bounds: {val}")

        # List fields
        for list_key in ("strengths", "gaps", "suggestions", "detected_constructs", "flagged_anti_patterns"):
            self.assertIsInstance(result[list_key], list, f"{list_key} must be list")

    def test_fuzzing_with_corrupted_question_dicts(self) -> None:
        """Calls evaluate_answer with malformed and empty question dictionaries."""
        malformed_questions: List[Dict[str, Any]] = [
            {},  # Empty dict
            {"category": None, "expected_keywords": None},  # Nones
            {"category": 12345, "expected_keywords": [1, 2, 3]},  # Ints in keywords
            {"test_cases": "CORRUPTED_NON_JSON_STRING"},  # Corrupted JSON string
            {"rubric": "NOT_A_DICT"},  # Corrupted rubric
        ]

        for i, bad_q in enumerate(malformed_questions):
            with self.subTest(idx=i):
                try:
                    res = evaluate_answer(bad_q, "student text here", "x = 1")
                    self.assertIsInstance(res, dict)
                    self.assertIn("total_score", res)
                    self.assertTrue(0.0 <= res["total_score"] <= 100.0)
                except Exception as ex:
                    self.fail(f"evaluate_answer crashed on malformed question {bad_q}: {ex}")


if __name__ == "__main__":
    unittest.main()
