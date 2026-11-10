"""
Comprehensive Unit Test Suite for Skillora Offline Rule-Based Mock Interview Bot.
Tests keyword matching ladder, synonym expansion, typo tolerance, lexical scoring,
Python AST static analysis, anti-pattern detection, unified 3-tier evaluation,
Interface Contract 5 conformance, and 100% offline purity.
"""

from __future__ import annotations

import inspect
import unittest

from server.bot.ast_checker import (
    ASTAntiPatternDetector,
    ASTConstructVisitor,
    analyze_code_ast,
    check_code_ast,
)
from server.bot.evaluator import (
    evaluate_answer,
    evaluate_lexical_structure,
)
from server.bot.keyword_matcher import (
    SYNONYM_DICTIONARY,
    TECHNICAL_SYNONYMS,
    compute_keyword_coverage,
    match_keywords,
    normalize_text,
    stem_token,
)


class TestKeywordMatcher(unittest.TestCase):
    """Verifies 4-stage matching ladder, normalization, stemming, and concept density."""

    def test_exact_keyword_matching(self) -> None:
        """Exact keywords present in candidate response receive full credit."""
        text = "We use two pointers to traverse the singly linked list in-place."
        keywords = ["two pointers", "singly linked list", "in-place"]
        result = compute_keyword_coverage(text, keywords)
        self.assertEqual(len(result["matched_keywords"]), 3)
        self.assertEqual(len(result["missing_keywords"]), 0)
        self.assertEqual(result["keyword_score"], 100.0)

    def test_case_and_punctuation_insensitivity(self) -> None:
        """Matching handles differing capitalization, hyphens, and whitespace."""
        text = "The time complexity is O( N ) with O(1) extra AUXILIARY SPACE."
        keywords = ["O(n)", "o(1) space"]
        result = compute_keyword_coverage(text, keywords)
        self.assertEqual(len(result["matched_keywords"]), 2)
        self.assertGreaterEqual(result["keyword_score"], 90.0)

    def test_stemmed_token_matching(self) -> None:
        """Lightweight stemmer matches plural and inflected variations."""
        # 'pointers' matches 'pointer', 'reversing' matches 'reverse'
        self.assertEqual(stem_token("pointers"), "pointer")
        self.assertEqual(stem_token("reversing"), "revers")
        self.assertEqual(stem_token("normalized"), "normal")

        text = "By reversing the pointers at each iteration, we avoid extra memory."
        keywords = ["pointer", "reverse"]
        result = compute_keyword_coverage(text, keywords)
        self.assertEqual(set(result["matched_keywords"]), {"pointer", "reverse"})

    def test_synonym_expansion_dsa(self) -> None:
        """Technical synonym expansion correctly resolves equivalent CS terminology."""
        # Candidate uses 'dictionary' instead of 'hash table', 'pointer pair' instead of 'two pointer'
        text = "Store frequency counts in a python dictionary to achieve constant lookup."
        keywords = ["hash table", "constant"]
        result = compute_keyword_coverage(text, keywords)
        self.assertIn("hash table", result["matched_keywords"])

    def test_synonym_expansion_os_dbms(self) -> None:
        """OS and DBMS synonym matching works seamlessly."""
        text = "A deadlock occurs when there is circular wait among processes."
        keywords = ["deadlock", "coffman conditions"]
        result = compute_keyword_coverage(text, keywords)
        self.assertIn("deadlock", result["matched_keywords"])

        db_text = "Transactions ensure atomicity, consistency, isolation, and durability."
        db_keywords = ["acid"]
        db_result = compute_keyword_coverage(db_text, db_keywords)
        self.assertIn("acid", db_result["matched_keywords"])

    def test_fuzzy_typo_matching(self) -> None:
        """Minor candidate typos are recognized via difflib SequenceMatcher."""
        # 'dicitonary' typo (ratio ~0.90) for 'dictionary'
        text = "We can use a dicitonary to store the visited nodes."
        keywords = ["dictionary"]
        result = compute_keyword_coverage(text, keywords, fuzzy_threshold=0.82)
        self.assertIn("dictionary", result["matched_keywords"])
        self.assertGreaterEqual(result["keyword_score"], 70.0)

    def test_concept_density_bonus(self) -> None:
        """High-density technical articulation receives modest density bonus."""
        concise_text = "Binary search splits array in half achieving logarithmic time complexity O(log n)."
        keywords = ["binary search", "logarithmic", "time complexity"]
        result = compute_keyword_coverage(concise_text, keywords)
        self.assertEqual(len(result["matched_keywords"]), 3)
        self.assertGreaterEqual(result["concept_density"], 0.15)
        self.assertEqual(result["keyword_score"], 100.0)

    def test_zero_coverage_on_irrelevant_text(self) -> None:
        """Completely unrelated text yields zero keyword score."""
        text = "The weather today is sunny and pleasant in Bangalore."
        keywords = ["hash map", "binary search tree", "recursion", "time complexity"]
        result = compute_keyword_coverage(text, keywords)
        self.assertEqual(result["keyword_score"], 0.0)
        self.assertEqual(len(result["matched_keywords"]), 0)
        self.assertEqual(len(result["missing_keywords"]), 4)

    def test_empty_input_handling(self) -> None:
        """Handles empty text or empty expected keywords gracefully."""
        self.assertEqual(compute_keyword_coverage("", ["stack"])["keyword_score"], 0.0)
        self.assertEqual(compute_keyword_coverage("Valid text", [])["keyword_score"], 100.0)


class TestLexicalEvaluator(unittest.TestCase):
    """Verifies Tier 2 lexical quality, formatting, definition, and complexity scoring."""

    def test_brevity_penalty(self) -> None:
        """Extremely brief answers (< 15 words) incur a penalty."""
        res = evaluate_lexical_structure("Use two pointers.")
        self.assertLess(res["structure_score"], 40.0)
        self.assertTrue(any("too brief" in g.lower() for g in res["gaps"]))

    def test_comprehensive_depth_reward(self) -> None:
        """Balanced explanation (80-350 words) with formatting and definitions achieves high score."""
        text = (
            "A Process is defined as an execution instance of a computer program that has its own "
            "independent virtual address space, memory pages, open file descriptors, and security context.\n"
            "In contrast, a Thread represents a lightweight unit of execution within a parent process that shares "
            "the text section, data section, and operating system resources.\n"
            "Key differences include:\n"
            "1. Memory Allocation: Processes operate in isolated memory spaces guarded by MMU page tables.\n"
            "2. Context Switching Overhead: Thread context switching is significantly faster than process context switching.\n"
            "3. Inter-process Communication: Threads communicate directly via shared memory with mutex synchronization, "
            "whereas processes require IPC mechanisms such as pipes, message queues, or UNIX domain sockets.\n"
            "4. Crash Resilience: A segfault in one thread terminates the entire parent process, while process isolation "
            "prevents cascade failures."
        )
        res = evaluate_lexical_structure(text)
        self.assertGreaterEqual(res["structure_score"], 80.0)
        self.assertTrue(res["has_formatting"])
        self.assertTrue(res["has_definition"])

    def test_structural_bullet_detection(self) -> None:
        """Detects numbered or bulleted list items."""
        text = (
            "We reverse the linked list using three pointers:\n"
            "* prev initialized to None\n"
            "* curr initialized to head\n"
            "* next initialized inside loop"
        )
        res = evaluate_lexical_structure(text)
        self.assertTrue(res["has_formatting"])

    def test_introductory_definition_detection(self) -> None:
        """Detects standard definitional introductory phrasing."""
        text = "A hash table is defined as a data structure that implements an associative array abstract data type."
        res = evaluate_lexical_structure(text)
        self.assertTrue(res["has_definition"])

    def test_complexity_analysis_detection(self) -> None:
        """Detects mentions of Big-O time and space complexity."""
        text = "The algorithm runs with O(n) time complexity and O(1) auxiliary space complexity."
        res = evaluate_lexical_structure(text)
        self.assertTrue(res["has_complexity"])

    def test_lexical_diversity_spam_penalty(self) -> None:
        """Repeating the exact same phrase 20 times incurs low Type-Token Ratio penalty."""
        spam_text = " ".join(["hash map hash map hash map"] * 20)
        res = evaluate_lexical_structure(spam_text)
        self.assertLess(res["type_token_ratio"], 0.20)
        self.assertTrue(any("diversity" in g.lower() for g in res["gaps"]))


class TestASTChecker(unittest.TestCase):
    """Verifies static AST inspection, construct detection, and anti-pattern penalties."""

    def test_ast_construct_detection(self) -> None:
        """Detects standard algorithmic constructs in valid Python code."""
        code = (
            "def reverse_list(head):\n"
            "    prev = None\n"
            "    curr = head\n"
            "    while curr is not None:\n"
            "        next_node = curr.next\n"
            "        curr.next = prev\n"
            "        prev = curr\n"
            "        curr = next_node\n"
            "    return prev\n"
        )
        res = check_code_ast(code, expected_constructs=["FunctionDef", "While", "Return", "Assign"])
        self.assertTrue(res["is_valid_syntax"])
        self.assertEqual(res["ast_score"], 100.0)
        self.assertIn("FunctionDef", res["detected_constructs"])
        self.assertIn("While", res["detected_constructs"])
        self.assertIn("Return", res["detected_constructs"])
        self.assertEqual(len(res["missing_constructs"]), 0)

    def test_comprehensions_and_loops(self) -> None:
        """Detects list comprehensions, for loops, and conditionals."""
        code = (
            "def filter_evens(nums):\n"
            "    evens = [x for x in nums if x % 2 == 0]\n"
            "    for e in evens:\n"
            "        print(e)\n"
            "    return evens\n"
        )
        res = check_code_ast(code, expected_constructs=["FunctionDef", "ListComp", "For", "If"])
        self.assertIn("ListComp", res["detected_constructs"])
        self.assertIn("For", res["detected_constructs"])
        self.assertIn("If", res["detected_constructs"])
        self.assertEqual(res["ast_score"], 100.0)

    def test_recursion_detection(self) -> None:
        """Detects recursive self-calling functions."""
        code = (
            "def factorial(n: int) -> int:\n"
            "    '''Computes n! recursively.'''\n"
            "    if n <= 1:\n"
            "        return 1\n"
            "    return n * factorial(n - 1)\n"
        )
        res = check_code_ast(code, expected_constructs=["FunctionDef", "Return"])
        self.assertTrue(res["has_recursion"])
        self.assertTrue(res["has_type_annotations"])
        self.assertTrue(res["has_docstrings"])
        self.assertIn("Recursion", res["detected_constructs"])
        self.assertEqual(res["ast_score"], 100.0)

    def test_syntax_error_resilience(self) -> None:
        """Syntax errors do NOT crash the engine and provide clean diagnostics."""
        broken_code = "def invalid_python(\n    print('missing paren'"
        res = check_code_ast(broken_code)
        self.assertFalse(res["is_valid_syntax"])
        self.assertEqual(res["ast_score"], 0.0)
        self.assertIsNotNone(res["syntax_error"])
        self.assertTrue(any("syntax error" in g.lower() for g in res["gaps"]))

    def test_anti_pattern_bare_except(self) -> None:
        """Bare except clause triggers penalty and diagnostic warning."""
        code = (
            "def risky():\n"
            "    try:\n"
            "        x = 1 / 0\n"
            "    except:\n"
            "        pass\n"
        )
        res = check_code_ast(code)
        self.assertIn("bare_except", res["flagged_anti_patterns"])
        self.assertLessEqual(res["ast_score"], 85.0)

    def test_anti_pattern_eval_or_exec(self) -> None:
        """Dangerous eval/exec invocation triggers heavy penalty."""
        code = "def run_dynamic(cmd):\n    return eval(cmd)\n"
        res = check_code_ast(code)
        self.assertIn("eval_or_exec", res["flagged_anti_patterns"])
        self.assertLessEqual(res["ast_score"], 70.0)

    def test_anti_pattern_global_variable(self) -> None:
        """Global variable mutation triggers anti-pattern penalty."""
        code = "total = 0\ndef add(x):\n    global total\n    total += x\n"
        res = check_code_ast(code)
        self.assertIn("global_variable", res["flagged_anti_patterns"])
        self.assertLessEqual(res["ast_score"], 90.0)

    def test_anti_pattern_range_len(self) -> None:
        """Non-idiomatic for i in range(len(arr)) triggers penalty."""
        code = "def loop_arr(arr):\n    for i in range(len(arr)):\n        print(arr[i])\n"
        res = check_code_ast(code)
        self.assertIn("range_len", res["flagged_anti_patterns"])
        self.assertLessEqual(res["ast_score"], 90.0)

    def test_anti_pattern_dead_code(self) -> None:
        """Unreachable statements following return trigger dead code penalty."""
        code = "def compute():\n    return 42\n    print('never reached')\n"
        res = check_code_ast(code)
        self.assertIn("dead_code", res["flagged_anti_patterns"])
        self.assertLessEqual(res["ast_score"], 90.0)

    def test_anti_pattern_mutable_default(self) -> None:
        """Mutable default arguments trigger penalty."""
        code = "def append_item(val, container=[]):\n    container.append(val)\n    return container\n"
        res = check_code_ast(code)
        self.assertIn("mutable_default_arg", res["flagged_anti_patterns"])
        self.assertLessEqual(res["ast_score"], 90.0)

    def test_anti_pattern_infinite_while_true(self) -> None:
        """while True loop without break triggers penalty."""
        code = "def loop():\n    while True:\n        print('looping')\n"
        res = check_code_ast(code)
        self.assertIn("infinite_while_true", res["flagged_anti_patterns"])
        self.assertLessEqual(res["ast_score"], 75.0)


class TestEvaluatorPipeline(unittest.TestCase):
    """Verifies unified 3-tier scoring, dynamic rubric, markdown extraction, and Contract 5."""

    def test_coding_question_three_tier_evaluation(self) -> None:
        """Coding question applies 50% Keywords, 20% Lexical, 30% AST."""
        question = {
            "category": "Coding",
            "question_text": "Reverse a singly linked list in-place.",
            "expected_keywords": ["in-place", "three pointers", "prev", "curr", "O(n) time", "O(1) space"],
            "test_cases": {"expected_constructs": ["FunctionDef", "While", "Return", "Assign"]},
            "model_answer": "Standard iterative three pointer solution.",
        }
        answer_text = (
            "We can reverse the linked list iteratively in-place using three pointers: prev, curr, and next.\n"
            "At each step, we save curr.next, reverse the pointer to point to prev, and advance prev and curr.\n"
            "This achieves O(n) time complexity and O(1) space complexity."
        )
        code = (
            "def reverse_list(head):\n"
            "    prev = None\n"
            "    curr = head\n"
            "    while curr:\n"
            "        next_node = curr.next\n"
            "        curr.next = prev\n"
            "        prev = curr\n"
            "        curr = next_node\n"
            "    return prev\n"
        )
        res = evaluate_answer(question, answer_text, code)

        self.assertIn("total_score", res)
        self.assertIn("keyword_score", res)
        self.assertIn("structure_score", res)
        self.assertIn("ast_score", res)
        self.assertIn("strengths", res)
        self.assertIn("gaps", res)
        self.assertIn("model_answer", res)

        self.assertGreaterEqual(res["total_score"], 85.0)
        self.assertEqual(res["ast_score"], 100.0)

    def test_theoretical_question_dynamic_weights(self) -> None:
        """Theoretical questions redistribute weights to 70% Keywords / 30% Lexical with 0% AST."""
        question = {
            "category": "Technical",
            "question_text": "Explain ACID properties in relational database management systems.",
            "expected_keywords": ["atomicity", "consistency", "isolation", "durability", "wal"],
            "test_cases": {"expected_constructs": [], "rubric": {"keywords": 0.70, "structure": 0.30}},
            "model_answer": "ACID properties ensure reliable transaction processing.",
        }
        answer_text = (
            "ACID properties are defined as the fundamental principles governing reliable database transactions:\n"
            "1. Atomicity: All operations in a transaction succeed or all are rolled back ('all-or-nothing').\n"
            "2. Consistency: Transactions transition the database from one valid state to another, satisfying integrity constraints.\n"
            "3. Isolation: Concurrent transactions execute independently without interference, governed by isolation levels.\n"
            "4. Durability: Once committed, updates persist permanently even through power failure or system crashes using WAL (Write-Ahead Logging)."
        )
        res = evaluate_answer(question, answer_text, code_snippet="")

        self.assertGreaterEqual(res["keyword_score"], 85.0)
        self.assertGreaterEqual(res["structure_score"], 80.0)
        self.assertGreaterEqual(res["total_score"], 85.0)
        # AST score is 0.0 but does not drag down total_score because weight is 0.0
        self.assertEqual(res["ast_score"], 0.0)

    def test_markdown_code_fence_extraction(self) -> None:
        """Embedded markdown code fences are automatically split into text and code."""
        question = {
            "category": "Coding",
            "question_text": "Two Sum problem using hash table.",
            "expected_keywords": ["hash map", "O(n) time", "complement"],
            "test_cases": {"expected_constructs": ["FunctionDef", "For", "Return"]},
        }
        student_submission = (
            "We solve Two Sum in O(n) time using a hash map to look up the complement.\n\n"
            "```python\n"
            "def two_sum(nums, target):\n"
            "    seen = {}\n"
            "    for i, num in enumerate(nums):\n"
            "        comp = target - num\n"
            "        if comp in seen:\n"
            "            return [seen[comp], i]\n"
            "        seen[num] = i\n"
            "    return []\n"
            "```\n"
        )
        res = evaluate_answer(question, student_submission)
        self.assertGreaterEqual(res["ast_score"], 90.0)
        self.assertIn("FunctionDef", res["detected_constructs"])
        self.assertGreaterEqual(res["total_score"], 85.0)

    def test_interface_contract_5_compliance(self) -> None:
        """Result contains all required keys from Interface Contract 5."""
        question = {
            "category": "Technical",
            "question_text": "Describe TCP 3-way handshake.",
            "expected_keywords": ["syn", "syn-ack", "ack", "handshake"],
            "model_answer": "Client sends SYN, server replies SYN-ACK, client sends ACK.",
        }
        res = evaluate_answer(question, "Client sends SYN, server replies SYN-ACK, client sends ACK.")
        expected_keys = [
            "total_score",
            "keyword_score",
            "structure_score",
            "lexical_score",
            "ast_score",
            "strengths",
            "gaps",
            "suggestions",
            "detected_constructs",
            "flagged_anti_patterns",
            "model_answer",
        ]
        for key in expected_keys:
            self.assertIn(key, res, f"Missing required Interface Contract 5 key: {key}")


class TestOfflineCompliance(unittest.TestCase):
    """Verifies that server.bot has zero network, cloud, or external NLP dependencies."""

    def test_strictly_offline_standard_library(self) -> None:
        """server.bot modules import only standard library modules."""
        import server.bot
        import server.bot.ast_checker
        import server.bot.evaluator
        import server.bot.keyword_matcher

        modules_to_inspect = [
            server.bot,
            server.bot.ast_checker,
            server.bot.evaluator,
            server.bot.keyword_matcher,
        ]

        forbidden_prefixes = [
            "urllib", "requests", "http.client", "socket", "aiohttp",
            "openai", "anthropic", "google.generativeai", "huggingface",
            "nltk", "spacy", "sklearn", "torch", "transformers",
        ]

        for mod in modules_to_inspect:
            source = inspect.getsource(mod)
            for forbidden in forbidden_prefixes:
                self.assertNotIn(
                    f"import {forbidden}",
                    source,
                    f"Forbidden import '{forbidden}' found in {mod.__name__}"
                )
                self.assertNotIn(
                    f"from {forbidden}",
                    source,
                    f"Forbidden import 'from {forbidden}' found in {mod.__name__}"
                )


if __name__ == "__main__":
    unittest.main()
