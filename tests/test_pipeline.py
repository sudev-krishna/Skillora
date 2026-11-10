"""
Comprehensive Unit Test Suite for Skillora Pure Functional Placement Pipeline.
Tests curried predicates, built-in filter pipelines, map/reduce PRI calculations,
tier readiness classifications, gap analysis, immutability, and thread safety.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
from types import MappingProxyType
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.pipeline.placement import (
    CompanyProfile,
    DIMENSIONS,
    PlacementReadinessResult,
    StudentProfile,
    TIER_BENCHMARKS,
    TIER_LABEL_1,
    TIER_LABEL_2,
    TIER_LABEL_3,
    TIER_LABEL_NEEDS_DEV,
    TIER_WEIGHTS,
    calculate_round_score,
    classify_tier_readiness,
    compute_placement_readiness_index,
    filter_eligible_companies,
    filter_eligible_students,
    generate_gap_analysis,
    get_tier_benchmarks,
    get_tier_weights,
    is_eligible,
    is_eligible_curried,
)


class TestCurriedPredicates(unittest.TestCase):
    """Verifies curried and direct invocations of is_eligible predicate."""

    def setUp(self) -> None:
        self.company = {
            "name": "Amazon",
            "tier": "Tier1",
            "min_cgpa": 7.5,
            "max_backlogs": 0,
            "eligible_branches": ["CSE", "IT", "ECE"],
        }
        self.student_eligible = {
            "name": "Aarav Sharma",
            "cgpa": 8.5,
            "backlogs": 0,
            "branch": "CSE",
        }
        self.student_ineligible_cgpa = {
            "name": "Priya Nair",
            "cgpa": 7.2,
            "backlogs": 0,
            "branch": "CSE",
        }

    def test_curried_invocation(self) -> None:
        """Predicate can be invoked as is_eligible(company)(student)."""
        predicate = is_eligible(self.company)
        self.assertTrue(callable(predicate))
        self.assertTrue(predicate(self.student_eligible))
        self.assertFalse(predicate(self.student_ineligible_cgpa))

    def test_direct_binary_invocation(self) -> None:
        """Predicate can be invoked directly as is_eligible(company, student)."""
        self.assertTrue(is_eligible(self.company, self.student_eligible))
        self.assertFalse(is_eligible(self.company, self.student_ineligible_cgpa))

    def test_is_eligible_curried_helper(self) -> None:
        """is_eligible_curried returns an explicit unary predicate."""
        pred = is_eligible_curried(self.company)
        self.assertTrue(pred(self.student_eligible))
        self.assertFalse(pred(self.student_ineligible_cgpa))

    def test_functools_partial_compatibility(self) -> None:
        """Predicate works seamlessly with functools.partial."""
        import functools
        partial_pred = functools.partial(is_eligible, self.company)
        self.assertTrue(partial_pred(self.student_eligible))
        self.assertFalse(partial_pred(self.student_ineligible_cgpa))

    def test_predicate_idempotence(self) -> None:
        """Calling predicate repeatedly on same inputs produces identical results."""
        pred = is_eligible(self.company)
        for _ in range(5):
            self.assertTrue(pred(self.student_eligible))
            self.assertFalse(pred(self.student_ineligible_cgpa))

    def test_none_handling(self) -> None:
        """Gracefully handles None student without crashing."""
        self.assertFalse(is_eligible(self.company, None))
        pred = is_eligible(self.company)
        self.assertFalse(pred(None))


class TestEligibilityBoundaries(unittest.TestCase):
    """Verifies edge case boundaries for CGPA, backlogs, and branch matching."""

    def test_exact_cgpa_cutoff_eligible(self) -> None:
        """Student with exact cutoff CGPA is strictly eligible."""
        comp = {"min_cgpa": 7.00, "max_backlogs": 0, "eligible_branches": "CSE"}
        student = {"cgpa": 7.00, "backlogs": 0, "branch": "CSE"}
        self.assertTrue(is_eligible(comp, student))

    def test_just_below_cgpa_cutoff_ineligible(self) -> None:
        """Student just below cutoff CGPA is ineligible."""
        comp = {"min_cgpa": 7.00, "max_backlogs": 0, "eligible_branches": "CSE"}
        student = {"cgpa": 6.99, "backlogs": 0, "branch": "CSE"}
        self.assertFalse(is_eligible(comp, student))

    def test_backlog_exact_limit_eligible(self) -> None:
        """Student with backlogs matching max_backlogs is strictly eligible."""
        comp = {"min_cgpa": 6.0, "max_backlogs": 1, "eligible_branches": "ALL"}
        student = {"cgpa": 7.5, "backlogs": 1, "branch": "IT"}
        self.assertTrue(is_eligible(comp, student))

    def test_backlog_exceeded_ineligible(self) -> None:
        """Student with backlogs exceeding allowance is ineligible."""
        comp = {"min_cgpa": 6.0, "max_backlogs": 0, "eligible_branches": "ALL"}
        student = {"cgpa": 9.5, "backlogs": 1, "branch": "CSE"}
        self.assertFalse(is_eligible(comp, student))

    def test_zero_backlog_default_when_missing(self) -> None:
        """Student dictionary missing backlogs defaults to 0 backlogs."""
        comp = {"min_cgpa": 6.0, "max_backlogs": 0, "eligible_branches": "ALL"}
        student = {"cgpa": 8.0, "branch": "CSE"}
        self.assertTrue(is_eligible(comp, student))

    def test_branch_case_and_whitespace_insensitivity(self) -> None:
        """Branch comparison handles uppercase, lowercase, and surrounding whitespace."""
        comp = {"min_cgpa": 6.5, "max_backlogs": 0, "eligible_branches": "CSE, ECE"}
        student1 = {"cgpa": 7.0, "backlogs": 0, "branch": "cse"}
        student2 = {"cgpa": 7.0, "backlogs": 0, "branch": "  ECE  "}
        self.assertTrue(is_eligible(comp, student1))
        self.assertTrue(is_eligible(comp, student2))

    def test_branch_wildcards(self) -> None:
        """Wildcards 'ALL', 'OPEN', and '*' allow any engineering branch."""
        for wildcard in ["ALL", "OPEN", "*", "ANY"]:
            comp = {"min_cgpa": 6.0, "max_backlogs": 2, "eligible_branches": wildcard}
            mech_student = {"cgpa": 7.0, "backlogs": 0, "branch": "MECH"}
            civil_student = {"cgpa": 7.0, "backlogs": 0, "branch": "CIVIL"}
            self.assertTrue(is_eligible(comp, mech_student))
            self.assertTrue(is_eligible(comp, civil_student))

    def test_branch_rejection(self) -> None:
        """Student from unlisted branch is rejected."""
        comp = {"min_cgpa": 6.0, "max_backlogs": 0, "eligible_branches": "CSE, IT"}
        biotech_student = {"cgpa": 9.0, "backlogs": 0, "branch": "BIOTECH"}
        self.assertFalse(is_eligible(comp, biotech_student))


class TestCompanyFiltering(unittest.TestCase):
    """Verifies pure filter operations over sequences of companies."""

    def setUp(self) -> None:
        self.companies = [
            {"company_id": 1, "name": "Amazon", "tier": "Tier1", "min_cgpa": 8.0, "max_backlogs": 0, "eligible_branches": "CSE,IT"},
            {"company_id": 2, "name": "Microsoft", "tier": "Tier1", "min_cgpa": 8.5, "max_backlogs": 0, "eligible_branches": "CSE,IT,ECE"},
            {"company_id": 3, "name": "Zoho", "tier": "Tier1", "min_cgpa": 6.5, "max_backlogs": 1, "eligible_branches": "ALL"},
            {"company_id": 4, "name": "TCS Digital", "tier": "Tier2", "min_cgpa": 7.0, "max_backlogs": 0, "eligible_branches": "CSE,IT,ECE,EE"},
            {"company_id": 5, "name": "TCS Ninja", "tier": "Tier3", "min_cgpa": 6.0, "max_backlogs": 1, "eligible_branches": "ALL"},
        ]

    def test_filter_eligible_companies_high_performer(self) -> None:
        """Student with high CGPA and 0 backlogs matches all eligible companies."""
        student = {"cgpa": 8.8, "backlogs": 0, "branch": "CSE"}
        eligible = filter_eligible_companies(self.companies, student)
        names = [c["name"] for c in eligible]
        self.assertEqual(len(names), 5)
        self.assertIn("Amazon", names)
        self.assertIn("Microsoft", names)

    def test_filter_eligible_companies_with_backlog(self) -> None:
        """Student with 1 backlog is filtered out of zero-backlog companies."""
        student = {"cgpa": 8.5, "backlogs": 1, "branch": "CSE"}
        eligible = filter_eligible_companies(self.companies, student)
        names = [c["name"] for c in eligible]
        # Only Zoho and TCS Ninja permit 1 backlog
        self.assertEqual(set(names), {"Zoho", "TCS Ninja"})

    def test_filter_eligible_companies_non_cs_branch(self) -> None:
        """Student in EE matches only companies permitting EE or ALL."""
        student = {"cgpa": 7.5, "backlogs": 0, "branch": "EE"}
        eligible = filter_eligible_companies(self.companies, student)
        names = [c["name"] for c in eligible]
        self.assertEqual(set(names), {"Zoho", "TCS Digital", "TCS Ninja"})

    def test_filter_preserves_input_immutability(self) -> None:
        """Original list and dictionaries are not mutated by filtering."""
        student = {"cgpa": 8.5, "backlogs": 0, "branch": "CSE"}
        companies_copy = [dict(c) for c in self.companies]
        _ = filter_eligible_companies(self.companies, student)
        self.assertEqual(self.companies, companies_copy)

    def test_filter_eligible_students(self) -> None:
        """filter_eligible_students returns only students matching target company."""
        comp = self.companies[0]  # Amazon: min_cgpa 8.0, 0 backlogs, CSE/IT
        students = [
            {"user_id": 1, "username": "s1", "cgpa": 8.2, "backlogs": 0, "branch": "CSE"},
            {"user_id": 2, "username": "s2", "cgpa": 7.8, "backlogs": 0, "branch": "CSE"},
            {"user_id": 3, "username": "s3", "cgpa": 8.5, "backlogs": 1, "branch": "CSE"},
            {"user_id": 4, "username": "s4", "cgpa": 9.0, "backlogs": 0, "branch": "MECH"},
        ]
        eligible = filter_eligible_students(comp, students)
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]["username"], "s1")


class TestDimensionalScoringAndReduce(unittest.TestCase):
    """Verifies map and reduce mechanics in calculate_round_score."""

    def test_calculate_round_score_standard(self) -> None:
        """Computes weighted average correctly."""
        weights = {"coding": 0.50, "technical": 0.30, "aptitude": 0.20}
        scores = {"coding": 80.0, "technical": 90.0, "aptitude": 70.0}
        # 0.50 * 80 + 0.30 * 90 + 0.20 * 70 = 40 + 27 + 14 = 81.0
        result = calculate_round_score(weights, scores)
        self.assertEqual(result, 81.0)

    def test_calculate_round_score_weight_normalization(self) -> None:
        """Weights that sum to 100 or arbitrary numbers are normalized."""
        weights = {"coding": 50, "technical": 30, "aptitude": 20}
        scores = {"coding": 80.0, "technical": 90.0, "aptitude": 70.0}
        result = calculate_round_score(weights, scores)
        self.assertEqual(result, 81.0)

    def test_calculate_round_score_clamping(self) -> None:
        """Scores above 100 or below 0 are clamped."""
        weights = {"coding": 1.0}
        scores_high = {"coding": 150.0}
        scores_low = {"coding": -20.0}
        self.assertEqual(calculate_round_score(weights, scores_high), 100.0)
        self.assertEqual(calculate_round_score(weights, scores_low), 0.0)

    def test_calculate_round_score_cgpa_scaling(self) -> None:
        """Academic score <= 10.0 is automatically scaled by 10."""
        weights = {"academic": 1.0}
        scores = {"academic": 8.5}
        self.assertEqual(calculate_round_score(weights, scores), 85.0)

    def test_empty_weights_or_scores(self) -> None:
        """Handles empty dictionary gracefully with 0.0."""
        self.assertEqual(calculate_round_score({}, {"coding": 80.0}), 0.0)
        self.assertEqual(calculate_round_score({"coding": 1.0}, {}), 0.0)


class TestPlacementReadinessIndex(unittest.TestCase):
    """Verifies PRI computation, tier readiness labels, and gap analysis."""

    def test_perfect_candidate_tier_1(self) -> None:
        """Candidate with 100 across dimensions gets PRI=100 and Ready for Tier 1."""
        scores = {dim: 100.0 for dim in DIMENSIONS}
        result = compute_placement_readiness_index(scores, target_tier="Tier1")
        self.assertEqual(result["pri_score"], 100.0)
        self.assertEqual(result["tier_readiness"], TIER_LABEL_1)
        self.assertEqual(len(result["gap_analysis"]), 0)

    def test_zero_candidate_needs_development(self) -> None:
        """Candidate with 0 across dimensions gets PRI=0 and Needs Development."""
        scores = {dim: 0.0 for dim in DIMENSIONS}
        result = compute_placement_readiness_index(scores)
        self.assertEqual(result["pri_score"], 0.0)
        self.assertEqual(result["tier_readiness"], TIER_LABEL_NEEDS_DEV)
        # Should have deficits across all 5 benchmark dimensions
        self.assertEqual(len(result["gap_analysis"]), 5)

    def test_tier_readiness_boundary_85(self) -> None:
        """Score >= 85.0 maps to Ready for Tier 1, 84.9 to Ready for Tier 2."""
        self.assertEqual(classify_tier_readiness(85.0), TIER_LABEL_1)
        self.assertEqual(classify_tier_readiness(85.1), TIER_LABEL_1)
        self.assertEqual(classify_tier_readiness(84.9), TIER_LABEL_2)

    def test_tier_readiness_boundary_70(self) -> None:
        """Score >= 70.0 maps to Ready for Tier 2, 69.9 to Ready for Tier 3."""
        self.assertEqual(classify_tier_readiness(70.0), TIER_LABEL_2)
        self.assertEqual(classify_tier_readiness(69.9), TIER_LABEL_3)

    def test_tier_readiness_boundary_50(self) -> None:
        """Score >= 50.0 maps to Ready for Tier 3, 49.9 to Needs Development."""
        self.assertEqual(classify_tier_readiness(50.0), TIER_LABEL_3)
        self.assertEqual(classify_tier_readiness(49.9), TIER_LABEL_NEEDS_DEV)

    def test_gap_analysis_targeted_deficits(self) -> None:
        """Identifies specific dimensions falling below target tier benchmarks."""
        # Tier 1 benchmarks: coding=85, technical=80, aptitude=75, communication=75, academic=75
        scores = {
            "coding": 90.0,         # satisfies Tier 1 (>=85)
            "technical": 82.0,      # satisfies Tier 1 (>=80)
            "aptitude": 60.0,       # deficit: 75 - 60 = 15
            "communication": 70.0,  # deficit: 75 - 70 = 5
            "academic": 8.0,        # 80% satisfies Tier 1 (>=75)
        }
        gaps = generate_gap_analysis(scores, target_tier="Tier1")
        self.assertEqual(len(gaps), 2)
        gap_text = " ".join(gaps)
        self.assertIn("Aptitude", gap_text)
        self.assertIn("Communication", gap_text)
        self.assertNotIn("Coding", gap_text)


class TestImmutabilityAndConcurrency(unittest.TestCase):
    """Verifies frozen dataclass immutability and multi-threaded safety."""

    def test_frozen_student_profile(self) -> None:
        """StudentProfile cannot be mutated after creation."""
        sp = StudentProfile(
            user_id=1,
            username="student1",
            branch="CSE",
            cgpa=8.5,
            backlogs=0,
        )
        with self.assertRaises(FrozenInstanceError):
            sp.cgpa = 9.0  # type: ignore

    def test_frozen_company_profile(self) -> None:
        """CompanyProfile cannot be mutated after creation."""
        cp = CompanyProfile(
            company_id=1,
            name="Zoho",
            tier="Tier1",
            min_cgpa=6.5,
            max_backlogs=1,
        )
        with self.assertRaises(FrozenInstanceError):
            cp.min_cgpa = 7.0  # type: ignore

    def test_mapping_proxy_constants(self) -> None:
        """TIER_WEIGHTS and TIER_BENCHMARKS are read-only MappingProxyType."""
        self.assertIsInstance(TIER_WEIGHTS, MappingProxyType)
        self.assertIsInstance(TIER_BENCHMARKS, MappingProxyType)
        with self.assertRaises(TypeError):
            TIER_WEIGHTS["Tier1"] = {}  # type: ignore

    def test_thread_safety_concurrent_execution(self) -> None:
        """Concurrent evaluation of candidates across 20 threads operates safely."""
        candidates = [
            {"coding": 50.0 + i * 2, "technical": 60.0, "aptitude": 70.0, "communication": 65.0, "academic": 7.5}
            for i in range(20)
        ]

        def _evaluate(c: dict) -> float:
            res = compute_placement_readiness_index(c)
            return res["pri_score"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_evaluate, c) for c in candidates]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), 20)
        for r in results:
            self.assertGreaterEqual(r, 0.0)
            self.assertLessEqual(r, 100.0)


if __name__ == "__main__":
    unittest.main()
