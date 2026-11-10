"""
Empirical Adversarial Stress Test Suite for Milestone 4 (Functional Placement Pipeline).
Authored by: Challenger 1 (teamwork_challenger)

Tests:
1. Curried Predicate Equivalence & Random Fuzzing (500+ randomized combinations)
2. Boundary Condition Stress (CGPA float precision, backlogs, wildcards, missing fields)
3. Purity & Immutability Fuzzing (Frozen dataclasses, deep copy equality, mapping proxies)
4. PRI Mathematical Bounds & Edge Cases (NaN, Inf, CGPA auto-scaling, classification thresholds)
5. High-Concurrency Multithreaded Re-entrancy (50 threads, 10,000 evaluations, zero race conditions)
"""

from __future__ import annotations

import concurrent.futures
import copy
from dataclasses import FrozenInstanceError
import math
import random
from types import MappingProxyType
import unittest

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


class TestCurriedPredicateFuzzing(unittest.TestCase):
    """Adversarially verifies equivalence between curried and direct predicate invocations."""

    def test_randomized_curried_vs_direct_equivalence_500(self) -> None:
        """500 randomized trials asserting is_eligible(c)(s) == is_eligible(c, s)."""
        branches_pool = ["CSE", "IT", "ECE", "MECH", "CIVIL", "EE", "AI", "DS", "ALL", "OPEN", "*"]
        rng = random.Random(424242)

        for trial in range(600):
            min_cgpa = round(rng.uniform(5.0, 9.5), 2)
            max_backlogs = rng.randint(0, 3)
            num_branches = rng.randint(1, 4)
            chosen_branches = rng.sample(branches_pool, num_branches)

            # Randomly format branches: string, list, set, or CompanyProfile
            branch_repr = rng.choice([
                ", ".join(chosen_branches),
                chosen_branches,
                tuple(chosen_branches),
                set(chosen_branches),
            ])

            if rng.choice([True, False]):
                company = {
                    "company_id": trial,
                    "name": f"Company_{trial}",
                    "min_cgpa": min_cgpa,
                    "max_backlogs": max_backlogs,
                    "eligible_branches": branch_repr,
                }
            else:
                company = CompanyProfile(
                    company_id=trial,
                    name=f"Company_{trial}",
                    tier="Tier1",
                    min_cgpa=min_cgpa,
                    max_backlogs=max_backlogs,
                    eligible_branches=tuple(chosen_branches),
                )

            # Generate student
            student_cgpa = round(rng.uniform(4.0, 10.0), 2)
            student_backlogs = rng.randint(0, 4)
            student_branch = rng.choice(branches_pool)

            if rng.choice([True, False]):
                student = {
                    "user_id": trial,
                    "username": f"user_{trial}",
                    "cgpa": student_cgpa,
                    "backlogs": student_backlogs,
                    "branch": student_branch,
                }
            else:
                student = StudentProfile(
                    user_id=trial,
                    username=f"user_{trial}",
                    cgpa=student_cgpa,
                    backlogs=student_backlogs,
                    branch=student_branch,
                )

            direct_result = is_eligible(company, student)
            curried_fn = is_eligible(company)
            curried_result = curried_fn(student)
            explicit_curried = is_eligible_curried(company)(student)

            self.assertEqual(
                direct_result,
                curried_result,
                f"Mismatch at trial {trial}: direct={direct_result}, curried={curried_result}",
            )
            self.assertEqual(
                direct_result,
                explicit_curried,
                f"Mismatch at trial {trial} with explicit curried helper",
            )

    def test_curried_closure_isolation(self) -> None:
        """Predicate closures created for different companies do not cross-contaminate."""
        strict_company = {"min_cgpa": 9.0, "max_backlogs": 0, "eligible_branches": "CSE"}
        lenient_company = {"min_cgpa": 6.0, "max_backlogs": 2, "eligible_branches": "ALL"}

        strict_pred = is_eligible(strict_company)
        lenient_pred = is_eligible(lenient_company)

        average_student = {"cgpa": 7.5, "backlogs": 1, "branch": "ECE"}

        self.assertFalse(strict_pred(average_student))
        self.assertTrue(lenient_pred(average_student))
        # Re-check strict predicate to ensure no state leakage
        self.assertFalse(strict_pred(average_student))


class TestBoundaryConditionStress(unittest.TestCase):
    """Tests extreme floating-point thresholds, backlog boundaries, and branch strings."""

    def test_cgpa_extreme_float_precision(self) -> None:
        """Tests micro-epsilon offsets around cutoff CGPA."""
        company = {"min_cgpa": 7.50, "max_backlogs": 0, "eligible_branches": "ALL"}

        # Exact match
        self.assertTrue(is_eligible(company, {"cgpa": 7.50, "backlogs": 0, "branch": "CSE"}))

        # Epsilon above (7.500000000001)
        self.assertTrue(is_eligible(company, {"cgpa": 7.500000000001, "backlogs": 0, "branch": "CSE"}))

        # Epsilon below (7.499999999999)
        self.assertFalse(is_eligible(company, {"cgpa": 7.499999999999, "backlogs": 0, "branch": "CSE"}))

        # Cutoff at 0.0
        zero_cutoff_company = {"min_cgpa": 0.0, "max_backlogs": 0, "eligible_branches": "ALL"}
        self.assertTrue(is_eligible(zero_cutoff_company, {"cgpa": 0.0, "backlogs": 0, "branch": "CSE"}))
        self.assertFalse(is_eligible(zero_cutoff_company, {"cgpa": -0.01, "backlogs": 0, "branch": "CSE"}))

        # Cutoff at 10.0
        ten_cutoff_company = {"min_cgpa": 10.0, "max_backlogs": 0, "eligible_branches": "ALL"}
        self.assertTrue(is_eligible(ten_cutoff_company, {"cgpa": 10.0, "backlogs": 0, "branch": "CSE"}))
        self.assertFalse(is_eligible(ten_cutoff_company, {"cgpa": 9.999999, "backlogs": 0, "branch": "CSE"}))

    def test_backlog_boundaries_and_negatives(self) -> None:
        """Tests 0 allowed, negative backlogs, and large backlog counts."""
        comp_zero = {"min_cgpa": 6.0, "max_backlogs": 0, "eligible_branches": "ALL"}
        comp_two = {"min_cgpa": 6.0, "max_backlogs": 2, "eligible_branches": "ALL"}

        # 0 allowed: 0 is eligible, 1 is ineligible
        self.assertTrue(is_eligible(comp_zero, {"cgpa": 7.0, "backlogs": 0, "branch": "CSE"}))
        self.assertFalse(is_eligible(comp_zero, {"cgpa": 7.0, "backlogs": 1, "branch": "CSE"}))

        # Negative backlogs (e.g. data anomaly) <= max_backlogs is handled gracefully
        self.assertTrue(is_eligible(comp_zero, {"cgpa": 7.0, "backlogs": -1, "branch": "CSE"}))

        # Exceeding 2 backlogs
        self.assertTrue(is_eligible(comp_two, {"cgpa": 7.0, "backlogs": 2, "branch": "CSE"}))
        self.assertFalse(is_eligible(comp_two, {"cgpa": 7.0, "backlogs": 3, "branch": "CSE"}))

    def test_branch_wildcards_and_whitespace_permutations(self) -> None:
        """Tests all universal wildcard variants, mixed casing, and whitespace formatting."""
        wildcards = ["ALL", "OPEN", "*", "ANY", "ALL BRANCHES", "all", "open", "any", "all branches"]

        for w in wildcards:
            comp = {"min_cgpa": 6.0, "max_backlogs": 0, "eligible_branches": w}
            student = {"cgpa": 7.0, "backlogs": 0, "branch": "AEROSPACE"}
            self.assertTrue(
                is_eligible(comp, student),
                f"Wildcard '{w}' should match branch AEROSPACE",
            )

        # Complex branch string with tabs, newlines, and trailing commas
        comp_messy = {
            "min_cgpa": 6.0,
            "max_backlogs": 0,
            "eligible_branches": "  CSE , \n IT \t,  ECE , ",
        }
        self.assertTrue(is_eligible(comp_messy, {"cgpa": 7.0, "backlogs": 0, "branch": "cse"}))
        self.assertTrue(is_eligible(comp_messy, {"cgpa": 7.0, "backlogs": 0, "branch": "\tIT\n"}))
        self.assertTrue(is_eligible(comp_messy, {"cgpa": 7.0, "backlogs": 0, "branch": "  ECE  "}))
        self.assertFalse(is_eligible(comp_messy, {"cgpa": 7.0, "backlogs": 0, "branch": "MECH"}))

    def test_missing_fields_and_fallbacks(self) -> None:
        """Verifies safe defaults when dictionary keys are missing."""
        # Empty company dict: min_cgpa=0.0, max_backlogs=0, eligible_branches="ALL"
        comp_empty = {}
        student_standard = {"cgpa": 7.0, "backlogs": 0, "branch": "CSE"}
        self.assertTrue(is_eligible(comp_empty, student_standard))

        # Empty student dict: cgpa=0.0, backlogs=0, branch=""
        student_empty = {}
        comp_standard = {"min_cgpa": 0.0, "max_backlogs": 0, "eligible_branches": "ALL"}
        self.assertTrue(is_eligible(comp_standard, student_empty))

        # Company using alias keys: cutoff_cgpa and eligible_branches_csv
        comp_alias = {"cutoff_cgpa": 7.0, "max_backlogs": 1, "eligible_branches_csv": "CSE, IT"}
        self.assertTrue(is_eligible(comp_alias, {"cgpa": 7.5, "backlogs": 0, "branch": "CSE"}))
        self.assertFalse(is_eligible(comp_alias, {"cgpa": 6.5, "backlogs": 0, "branch": "CSE"}))

        # Student using alias key: active_backlogs
        student_alias = {"cgpa": 8.0, "active_backlogs": 2, "branch": "CSE"}
        self.assertFalse(is_eligible(comp_alias, student_alias))


class TestPurityAndImmutabilityFuzzing(unittest.TestCase):
    """Verifies that no pipeline functions ever mutate input objects."""

    def test_filter_eligible_companies_strict_purity(self) -> None:
        """Asserts input sequence and inner dictionaries are untouched."""
        companies = [
            {"company_id": 1, "name": "Co1", "min_cgpa": 7.0, "max_backlogs": 0, "eligible_branches": "CSE"},
            {"company_id": 2, "name": "Co2", "min_cgpa": 8.5, "max_backlogs": 0, "eligible_branches": "CSE"},
        ]
        student = {"cgpa": 7.5, "backlogs": 0, "branch": "CSE"}

        comp_clone = copy.deepcopy(companies)
        student_clone = copy.deepcopy(student)

        result = filter_eligible_companies(companies, student)

        # 1. Inputs must remain strictly identical
        self.assertEqual(companies, comp_clone)
        self.assertEqual(student, student_clone)

        # 2. Mutating result elements must not mutate input elements
        self.assertEqual(len(result), 1)
        result[0]["name"] = "MUTATED_NAME"
        result[0]["new_key"] = 999
        self.assertEqual(companies[0]["name"], "Co1")
        self.assertNotIn("new_key", companies[0])

    def test_filter_eligible_students_strict_purity(self) -> None:
        """Asserts students list and items are never mutated."""
        company = {"min_cgpa": 7.0, "max_backlogs": 0, "eligible_branches": "CSE"}
        students = [
            {"user_id": 1, "username": "u1", "cgpa": 7.5, "backlogs": 0, "branch": "CSE"},
            {"user_id": 2, "username": "u2", "cgpa": 6.5, "backlogs": 0, "branch": "CSE"},
        ]
        students_clone = copy.deepcopy(students)

        result = filter_eligible_students(company, students)
        self.assertEqual(students, students_clone)

        result[0]["username"] = "MUTATED"
        self.assertEqual(students[0]["username"], "u1")

    def test_calculate_round_score_strict_purity(self) -> None:
        """Weights and scores dictionaries remain unchanged."""
        weights = {"coding": 0.40, "technical": 0.60}
        scores = {"coding": 80.0, "technical": 90.0}

        w_clone = dict(weights)
        s_clone = dict(scores)

        score = calculate_round_score(weights, scores)
        self.assertEqual(score, 86.0)
        self.assertEqual(weights, w_clone)
        self.assertEqual(scores, s_clone)

    def test_compute_pri_strict_purity(self) -> None:
        """dimension_scores dict passed to compute_placement_readiness_index is untouched."""
        scores = {"coding": 80.0, "technical": 75.0, "aptitude": 70.0, "academic": 8.0, "communication": 85.0}
        scores_clone = dict(scores)

        res = compute_placement_readiness_index(scores, target_tier="Tier1")
        self.assertEqual(scores, scores_clone)

        # Mutating res['dimension_scores'] does not mutate input
        res["dimension_scores"]["coding"] = 999.0
        self.assertEqual(scores["coding"], 80.0)

    def test_frozen_dataclass_strictness(self) -> None:
        """Frozen dataclasses reject setattr and delattr with FrozenInstanceError."""
        sp = StudentProfile(user_id=1, username="test", branch="CSE", cgpa=8.0)
        cp = CompanyProfile(company_id=1, name="TestCo", tier="Tier1", min_cgpa=7.0, max_backlogs=0)

        with self.assertRaises(FrozenInstanceError):
            sp.cgpa = 9.0  # type: ignore

        with self.assertRaises(FrozenInstanceError):
            del sp.cgpa  # type: ignore

        with self.assertRaises(FrozenInstanceError):
            cp.tier = "Tier2"  # type: ignore

        with self.assertRaises(FrozenInstanceError):
            del cp.tier  # type: ignore


class TestPRICalculationAndMathStress(unittest.TestCase):
    """Stress tests round score and PRI computation against edge mathematical values."""

    def test_academic_cgpa_scaling_logic(self) -> None:
        """CGPA <= 10.0 is scaled x10, but scores > 10.0 are left unscaled."""
        weights = {"academic": 1.0}

        # 8.5 scaled to 85.0
        self.assertEqual(calculate_round_score(weights, {"academic": 8.5}), 85.0)

        # 10.0 scaled to 100.0
        self.assertEqual(calculate_round_score(weights, {"academic": 10.0}), 100.0)

        # 85.0 is NOT scaled (remains 85.0)
        self.assertEqual(calculate_round_score(weights, {"academic": 85.0}), 85.0)

        # 0.0 is 0.0
        self.assertEqual(calculate_round_score(weights, {"academic": 0.0}), 0.0)

    def test_nan_inf_and_unparseable_inputs(self) -> None:
        """NaN, Inf, and non-numeric strings are sanitized to 0.0 without crashing."""
        weights = {"coding": 0.5, "technical": 0.5}

        # NaN
        score_nan = calculate_round_score(weights, {"coding": float("nan"), "technical": 80.0})
        self.assertEqual(score_nan, 40.0)

        # Inf
        score_inf = calculate_round_score(weights, {"coding": float("inf"), "technical": 80.0})
        self.assertEqual(score_inf, 40.0)

        # String number vs non-numeric string
        score_str = calculate_round_score(weights, {"coding": "90.0", "technical": "not_a_number"})
        self.assertEqual(score_str, 45.0)

    def test_classification_threshold_precision(self) -> None:
        """Micro-step tests at 85.0, 70.0, and 50.0 boundaries."""
        # Tier 1 vs Tier 2
        self.assertEqual(classify_tier_readiness(85.0000), TIER_LABEL_1)
        self.assertEqual(classify_tier_readiness(84.9999), TIER_LABEL_2)

        # Tier 2 vs Tier 3
        self.assertEqual(classify_tier_readiness(70.0000), TIER_LABEL_2)
        self.assertEqual(classify_tier_readiness(69.9999), TIER_LABEL_3)

        # Tier 3 vs Needs Dev
        self.assertEqual(classify_tier_readiness(50.0000), TIER_LABEL_3)
        self.assertEqual(classify_tier_readiness(49.9999), TIER_LABEL_NEEDS_DEV)

        # Negative and zero
        self.assertEqual(classify_tier_readiness(0.0), TIER_LABEL_NEEDS_DEV)
        self.assertEqual(classify_tier_readiness(-10.0), TIER_LABEL_NEEDS_DEV)

    def test_pri_step_up_target_tiers(self) -> None:
        """Tests step-up gap analysis selection when target_tier is not explicitly provided."""
        # Score in Tier 3 (e.g. 55.0) steps up to Tier 2 benchmarks
        scores_t3 = {"aptitude": 55.0, "coding": 55.0, "technical": 55.0, "communication": 55.0, "academic": 5.5}
        res_t3 = compute_placement_readiness_index(scores_t3)
        self.assertEqual(res_t3["tier_readiness"], TIER_LABEL_3)
        self.assertEqual(res_t3["target_tier"], "Tier2")

        # Score in Tier 2 (e.g. 75.0) steps up to Tier 1 benchmarks
        scores_t2 = {"aptitude": 75.0, "coding": 75.0, "technical": 75.0, "communication": 75.0, "academic": 7.5}
        res_t2 = compute_placement_readiness_index(scores_t2)
        self.assertEqual(res_t2["tier_readiness"], TIER_LABEL_2)
        self.assertEqual(res_t2["target_tier"], "Tier1")

    def test_none_input_resilience(self) -> None:
        """Pipeline functions handle None inputs without uncaught exceptions."""
        # compute_placement_readiness_index(None)
        res_none = compute_placement_readiness_index(None)  # type: ignore
        self.assertEqual(res_none["pri_score"], 0.0)
        self.assertEqual(res_none["tier_readiness"], TIER_LABEL_NEEDS_DEV)

        # calculate_round_score with None
        self.assertEqual(calculate_round_score(None, None), 0.0)  # type: ignore
        self.assertEqual(calculate_round_score({"coding": 1.0}, None), 0.0)  # type: ignore
        self.assertEqual(calculate_round_score(None, {"coding": 80.0}), 0.0)  # type: ignore

        # filter functions with None
        student = {"cgpa": 8.0, "backlogs": 0, "branch": "CSE"}
        comp = {"min_cgpa": 7.0, "max_backlogs": 0, "eligible_branches": "ALL"}
        self.assertEqual(filter_eligible_companies(None, student), [])  # type: ignore
        self.assertEqual(filter_eligible_companies([comp], None), [])  # type: ignore
        self.assertEqual(filter_eligible_students(None, [student]), [])  # type: ignore
        self.assertEqual(filter_eligible_students(comp, None), [])  # type: ignore

    def test_placement_readiness_result_to_dict_deep_copies(self) -> None:
        """PlacementReadinessResult.to_dict produces mutable independent copies."""
        scores = {"coding": 80.0, "technical": 70.0, "aptitude": 70.0, "communication": 70.0, "academic": 7.0}
        res = compute_placement_readiness_index(scores)
        # Verify gap_analysis is a mutable list that doesn't affect internal state
        self.assertIsInstance(res["gap_analysis"], list)
        self.assertIsInstance(res["dimension_scores"], dict)
        res["gap_analysis"].append("FAKE_GAP")
        res["dimension_scores"]["extra"] = 999.0
        # Re-compute to ensure global state was not affected
        res2 = compute_placement_readiness_index(scores)
        self.assertNotIn("FAKE_GAP", res2["gap_analysis"])
        self.assertNotIn("extra", res2["dimension_scores"])

    def test_tier_lookup_fallbacks(self) -> None:
        """get_tier_weights and get_tier_benchmarks handle unknown strings gracefully."""
        self.assertEqual(get_tier_weights("NonExistentTier"), TIER_WEIGHTS["Baseline"])
        self.assertEqual(get_tier_benchmarks("NonExistentTier"), TIER_BENCHMARKS["Tier3"])
        self.assertEqual(get_tier_benchmarks("Tier 1"), TIER_BENCHMARKS["Tier1"])
        self.assertEqual(get_tier_benchmarks("Tier 2"), TIER_BENCHMARKS["Tier2"])



class TestMultithreadedReentrancyStress(unittest.TestCase):
    """Stress tests concurrency with 50 threads running 10,000 evaluations simultaneously."""

    def test_50_threads_10000_evaluations_reentrancy(self) -> None:
        """Executes 10,000 evaluations across 50 concurrent worker threads."""
        companies = [
            {"company_id": 1, "name": "Amazon", "min_cgpa": 8.0, "max_backlogs": 0, "eligible_branches": "CSE,IT"},
            {"company_id": 2, "name": "Zoho", "min_cgpa": 6.5, "max_backlogs": 1, "eligible_branches": "ALL"},
            {"company_id": 3, "name": "TCS", "min_cgpa": 6.0, "max_backlogs": 2, "eligible_branches": "OPEN"},
        ]

        # 10 deterministic test candidate patterns
        candidates = [
            {
                "student": {"cgpa": 8.5, "backlogs": 0, "branch": "CSE"},
                "scores": {"coding": 90.0, "technical": 85.0, "aptitude": 80.0, "communication": 80.0, "academic": 8.5},
            },
            {
                "student": {"cgpa": 7.0, "backlogs": 1, "branch": "ECE"},
                "scores": {"coding": 65.0, "technical": 65.0, "aptitude": 70.0, "communication": 60.0, "academic": 7.0},
            },
            {
                "student": {"cgpa": 5.5, "backlogs": 3, "branch": "MECH"},
                "scores": {"coding": 40.0, "technical": 45.0, "aptitude": 45.0, "communication": 50.0, "academic": 5.5},
            },
        ]

        # Precompute expected deterministic outputs on main thread
        expected_results = []
        for c in candidates:
            filtered = [comp["name"] for comp in filter_eligible_companies(companies, c["student"])]
            pri_res = compute_placement_readiness_index(c["scores"])
            expected_results.append((filtered, pri_res["pri_score"], pri_res["tier_readiness"]))

        total_runs = 10000

        def _worker_task(index: int) -> tuple[int, list[str], float, str]:
            cand_idx = index % len(candidates)
            c = candidates[cand_idx]
            # 1. Filter companies
            matched = [comp["name"] for comp in filter_eligible_companies(companies, c["student"])]
            # 2. Compute PRI
            pri = compute_placement_readiness_index(c["scores"])
            return cand_idx, matched, pri["pri_score"], pri["tier_readiness"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(_worker_task, i) for i in range(total_runs)]
            completed_count = 0
            for fut in concurrent.futures.as_completed(futures):
                cand_idx, matched, pri_score, tier_readiness = fut.result()
                exp_matched, exp_pri, exp_tier = expected_results[cand_idx]

                self.assertEqual(matched, exp_matched)
                self.assertEqual(pri_score, exp_pri)
                self.assertEqual(tier_readiness, exp_tier)
                completed_count += 1

        self.assertEqual(completed_count, total_runs)


if __name__ == "__main__":
    unittest.main()
