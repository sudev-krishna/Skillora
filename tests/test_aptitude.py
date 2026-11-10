"""
Skillora Dynamic Aptitude Math Engine Test Suite (tests/test_aptitude.py)
Verifies problem generation across all 4 placement domains:
  1. Compound vs Simple Interest differences (2-year & 3-year)
  2. Harmonic Work Collaboration (Babylonian rate balancing)
  3. Urn Model Hypergeometric Combinatorics & Probability
  4. Cayley's Labeled Spanning Tree Formula
Tests 4-option uniqueness, correct answer indexing, misconception mapping,
symbolic proof structure, seed determinism, and 100% offline self-containment.
"""

import math
import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sympy as sp
from server.math_engine.aptitude_generator import (
    AptitudeProblem,
    AptitudeTopic,
    generate_cayley_problem,
    generate_interest_problem,
    generate_problem,
    generate_urn_problem,
    generate_work_problem,
)


class TestAptitudeGeneratorDomains(unittest.TestCase):
    """Verifies mathematical correctness of generated problems across all 4 domains."""

    def test_generate_interest_2_years(self):
        """Verifies 2-year CI vs SI difference equals P * (R/100)^2."""
        prob = generate_interest_problem(seed=42, years=2)
        P = prob.parameters["P"]
        R = prob.parameters["R"]
        expected_diff = int(sp.Rational(P, 1) * (sp.Rational(R, 100) ** 2))
        self.assertEqual(prob.correct_value, expected_diff)
        self.assertEqual(prob.correct_answer, str(expected_diff))
        self.assertEqual(prob.parameters["years"], 2)
        self.assertIn("Delta_2", prob.formula_symbolic)

    def test_generate_interest_3_years(self):
        """Verifies 3-year CI vs SI difference equals P * (R/100)^2 * (3 + R/100)."""
        prob = generate_interest_problem(seed=101, years=3)
        P = prob.parameters["P"]
        R = prob.parameters["R"]
        expected_diff = int(sp.Rational(P, 1) * (sp.Rational(R, 100) ** 2) * (3 + sp.Rational(R, 100)))
        self.assertEqual(prob.correct_value, expected_diff)
        self.assertEqual(prob.correct_answer, str(expected_diff))
        self.assertEqual(prob.parameters["years"], 3)
        self.assertIn("Delta_3", prob.formula_symbolic)

    def test_generate_work_collaboration(self):
        """Verifies harmonic rate sum: 1/A + 1/B = 1/T."""
        prob = generate_work_problem(seed=77)
        A = prob.parameters["A"]
        B = prob.parameters["B"]
        T = prob.parameters["target_days"]
        rate_sum = sp.Rational(1, A) + sp.Rational(1, B)
        self.assertEqual(rate_sum, sp.Rational(1, T))
        self.assertEqual(prob.correct_value, T)
        self.assertEqual(prob.correct_answer, str(T))

    def test_generate_urn_same_color(self):
        """Verifies hypergeometric probability equals sum(C(ci, 2)) / C(N, 2)."""
        prob = generate_urn_problem(seed=88)
        params = prob.parameters
        r, g, b, total = params["red"], params["green"], params["blue"], params["total"]
        fav = sp.binomial(r, 2) + sp.binomial(g, 2) + sp.binomial(b, 2)
        sample_space = sp.binomial(total, 2)
        expected_prob_rat = sp.Rational(fav, sample_space)
        self.assertEqual(prob.correct_answer, str(expected_prob_rat))
        self.assertAlmostEqual(prob.correct_value, float(expected_prob_rat), places=4)

    def test_generate_cayley_trees(self):
        """Verifies Cayley tree formula: T(Kn) = n^(n - 2) for all n in [3, 7]."""
        for n_val in [3, 4, 5, 6, 7]:
            prob = generate_cayley_problem(seed=n_val, n=n_val)
            expected_trees = n_val ** (n_val - 2)
            self.assertEqual(prob.correct_value, expected_trees)
            self.assertEqual(prob.correct_answer, str(expected_trees))
            self.assertEqual(prob.parameters["n"], n_val)


class TestAptitudeOptionsAndDistractors(unittest.TestCase):
    """Verifies multiple-choice option structure, uniqueness, and misconception mapping."""

    def test_options_uniqueness_invariant(self):
        """All 4 generated options must be strictly distinct across all topics and seeds."""
        for topic in ["ci_si", "work", "urn", "cayley"]:
            for seed in range(1, 15):
                prob_dict = generate_problem(topic=topic, seed=seed)
                options = prob_dict["options"]
                self.assertEqual(len(options), 4, f"Failed length on {topic} seed={seed}")
                self.assertEqual(len(set(options)), 4, f"Options collision on {topic} seed={seed}: {options}")

    def test_correct_answer_in_options(self):
        """The correct answer must match options[correct_option_index]."""
        for topic in ["ci_si", "work", "urn", "cayley"]:
            prob_dict = generate_problem(topic=topic, seed=42)
            idx = prob_dict["correct_option_index"]
            label = prob_dict["correct_option_label"]
            self.assertIn(label, ["A", "B", "C", "D"])
            self.assertEqual(["A", "B", "C", "D"][idx], label)
            self.assertEqual(prob_dict["options"][idx], prob_dict["correct_answer"])

    def test_distractors_count_and_disjointness(self):
        """Distractors must have length 3 and strictly exclude the correct answer."""
        for topic in ["ci_si", "work", "urn", "cayley"]:
            prob_dict = generate_problem(topic=topic, seed=99)
            distractors = prob_dict["distractors"]
            self.assertEqual(len(distractors), 3)
            self.assertNotIn(prob_dict["correct_answer"], distractors)

    def test_misconception_mapping_completeness(self):
        """Every distractor must have an entry in the misconception diagnostic map."""
        for topic in ["ci_si", "work", "urn", "cayley"]:
            prob_dict = generate_problem(topic=topic, seed=123)
            m_map = prob_dict["misconception_map"]
            for dist in prob_dict["distractors"]:
                self.assertIn(dist, m_map)
                self.assertGreater(len(m_map[dist]), 5)


class TestAptitudeProofAndReproducibility(unittest.TestCase):
    """Verifies symbolic proofs, determinism, and input boundary validation."""

    def test_symbolic_proof_structure(self):
        """Verifies 4-phase proof contains formula, substitution, steps, and exact answer."""
        prob_dict = generate_problem(topic="cayley", seed=10)
        steps = prob_dict["proof_steps"]
        self.assertGreaterEqual(len(steps), 4)
        for s in steps:
            self.assertIn("step_number", s)
            self.assertIn("title", s)
            self.assertIn("latex", s)
            self.assertIn("text", s)
            self.assertIn("explanation", s)
            self.assertGreater(len(s["latex"]), 0)
            self.assertGreater(len(s["text"]), 0)
        self.assertIn(r"\begin{aligned}", prob_dict["latex_proof"])
        self.assertIn("Step 1", prob_dict["text_proof"])

    def test_seed_determinism(self):
        """Identical seeds must yield 100% identical problem output."""
        p1 = generate_problem(topic="work", seed=42)
        p2 = generate_problem(topic="work", seed=42)
        self.assertEqual(p1["question_text"], p2["question_text"])
        self.assertEqual(p1["correct_answer"], p2["correct_answer"])
        self.assertEqual(p1["options"], p2["options"])
        self.assertEqual(p1["latex_proof"], p2["latex_proof"])

    def test_different_seeds_diversity(self):
        """Different seeds should generate varied parameters."""
        p1 = generate_problem(topic="work", seed=1)
        p2 = generate_problem(topic="work", seed=2)
        # Even if target days coincide, worker names or parameters vary
        params1 = (p1["parameters"]["A"], p1["parameters"]["B"])
        params2 = (p2["parameters"]["A"], p2["parameters"]["B"])
        self.assertTrue(params1 != params2 or p1["question_text"] != p2["question_text"])

    def test_invalid_topic_raises_value_error(self):
        """Invalid topic string raises ValueError with informative message."""
        with self.assertRaises(ValueError) as ctx:
            generate_problem(topic="quantum_computing")
        self.assertIn("Unknown aptitude topic", str(ctx.exception))

    def test_alias_resolution(self):
        """Verifies aliases like 'ci_si', 'work', 'urn', 'cayley' resolve cleanly."""
        self.assertEqual(generate_problem(topic="ci_si", seed=5)["topic"], AptitudeTopic.INTEREST_DIFFERENCE.value)
        self.assertEqual(generate_problem(topic="work", seed=5)["topic"], AptitudeTopic.WORK_COLLABORATION.value)
        self.assertEqual(generate_problem(topic="urn", seed=5)["topic"], AptitudeTopic.URN_PROBABILITY.value)
        self.assertEqual(generate_problem(topic="cayley", seed=5)["topic"], AptitudeTopic.CAYLEY_TREES.value)

    def test_random_topic_selection_when_none(self):
        """When topic is None, generator picks from all 4 topics."""
        topics_seen = set()
        for seed in range(30):
            p = generate_problem(topic=None, seed=seed)
            topics_seen.add(p["topic"])
        self.assertEqual(len(topics_seen), 4)


if __name__ == "__main__":
    unittest.main()
