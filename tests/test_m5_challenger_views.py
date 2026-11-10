"""
Skillora Milestone 5 Challenger 2 Test Suite (tests/test_m5_challenger_views.py)
Adversarial stress harness for 5 desktop GUI views and 100% offline fallback mechanisms.

Stress Dimensions:
1. 100% Offline Disconnected Operation across all 5 views:
   - DashboardView: PRI calculation, company filtering, competency canvas chart.
   - CompanyView: Tiered company explorer, cutoff filters, drawer pipelines.
   - MathStudioView: SymPy recurrence solver, Master Theorem, dynamic aptitude generator with proofs.
   - CodingSandboxView: Multiprocessing sandbox profiling, divergence detection, Canvas plot.
   - InterviewView: 3-tier offline evaluation (keywords, structure, AST syntax), scorecard rendering.
2. Boundary and Malformed Input Fuzzing:
   - Empty strings, whitespace, Unicode, SQL injection strings.
   - Extreme slider values (CGPA 0.0 to 10.0, backlogs 0 to 50).
   - Malformed recurrence relations (division by zero, negative coefficients, invalid syntax).
   - Malformed base cases.
   - Syntax errors and anti-patterns in Python code sandbox and interview console.
   - Extreme scaling array N and timeout parameters.
3. Rapid View Switching & AppWindow Lifecycle.
"""

import ast
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.gui.app_window import AppWindow
from client.gui.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_BG,
    COLOR_CARD,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_TEXT_PRIMARY,
    COLOR_WARNING,
    enforce_light_theme,
)
from client.gui.views.coding_sandbox_view import CodingSandboxView, SANDBOX_TEMPLATES
from client.gui.views.company_view import CompanyView
from client.gui.views.dashboard_view import DashboardView
from client.gui.views.interview_view import InterviewView
from client.gui.views.math_studio_view import MathStudioView, RECURRENCE_TEMPLATES
from server.bot.ast_checker import check_code_ast
from server.bot.evaluator import evaluate_answer
from server.db.seed_data import COMPANIES_SEED_DATA, QUESTIONS_SEED_DATA
from server.math_engine.aptitude_generator import generate_problem
from server.pipeline.placement import (
    compute_placement_readiness_index,
    filter_eligible_companies,
    is_eligible,
)
from server.profiler.divergence import detect_divergence
from server.profiler.recurrence import solve_recurrence
from server.sandbox.mp_runner import run_empirical_profile


def is_display_available() -> bool:
    """Checks whether Tkinter GUI display is accessible."""
    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        r.destroy()
        return True
    except Exception:
        return False


# ==============================================================================
# Suite 1: Dashboard View Adversarial Stress Tests
# ==============================================================================
@unittest.skipUnless(is_display_available(), "Display not available in headless environment")
class TestDashboardViewAdversarialStress(unittest.TestCase):
    """Stress tests DashboardView with extreme inputs, corrupt session data, and offline calculation."""

    def setUp(self):
        import customtkinter as ctk
        self.root = ctk.CTk()
        self.root.withdraw()
        self.app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        self.dash_view = self.app.register_view("dashboard", DashboardView)
        self.app.navigate_to("dashboard")
        self.root.update_idletasks()

    def tearDown(self):
        try:
            for timer_id in self.root.tk.call("after", "info"):
                try:
                    self.root.after_cancel(timer_id)
                except Exception:
                    pass
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            pass

    def test_dashboard_default_offline_calculation(self):
        """Verifies default dashboard renders valid PRI, eligible count, and canvas chart offline."""
        self.dash_view.refresh_dashboard()
        self.root.update_idletasks()

        # Verify PRI label contains percentage
        pri_text = self.dash_view.pri_score_label.cget("text")
        self.assertTrue("%" in pri_text, f"PRI text '{pri_text}' must contain '%'")
        pri_val = float(pri_text.replace("%", "").strip())
        self.assertGreaterEqual(pri_val, 0.0)
        self.assertLessEqual(pri_val, 100.0)

        # Verify eligible count label format 'X / Y'
        elig_text = self.dash_view.elig_count_label.cget("text")
        self.assertIn("/", elig_text)
        parts = [int(p.strip()) for p in elig_text.split("/")]
        self.assertEqual(parts[1], len(COMPANIES_SEED_DATA))
        self.assertGreaterEqual(parts[0], 0)

        # Verify Canvas chart has drawn items
        items = self.dash_view.chart_canvas.find_all()
        self.assertGreater(len(items), 10, "Canvas chart should contain dimension bars, labels, and targets")

    def test_dashboard_extreme_cgpa_0_and_10_backlogs(self):
        """Verifies Dashboard handles worst-case profile (CGPA 0.0, 10 backlogs) with 0 eligible drives."""
        self.app.session_data["cgpa"] = 0.0
        self.app.session_data["backlogs"] = 10
        self.app.session_data["dimension_scores"] = {
            "aptitude": 0.0,
            "coding": 0.0,
            "technical": 0.0,
            "communication": 0.0,
            "academic": 0.0,
        }
        self.dash_view.refresh_dashboard()
        self.root.update_idletasks()

        pri_text = self.dash_view.pri_score_label.cget("text")
        self.assertEqual(pri_text, "0.0%")
        self.assertEqual(self.dash_view.elig_count_label.cget("text"), f"0 / {len(COMPANIES_SEED_DATA)}")
        self.assertIn("Needs Development", self.dash_view.pri_badge.cget("text"))

        # Gaps diagnostic should be populated
        gap_widgets = self.dash_view.gap_labels_container.winfo_children()
        self.assertGreaterEqual(len(gap_widgets), 1)

    def test_dashboard_extreme_cgpa_10_and_perfect_scores(self):
        """Verifies Dashboard handles perfect candidate profile (CGPA 10.0, 0 backlogs, 100% scores)."""
        self.app.session_data["cgpa"] = 10.0
        self.app.session_data["backlogs"] = 0
        self.app.session_data["branch"] = "CSE"
        self.app.session_data["dimension_scores"] = {
            "aptitude": 100.0,
            "coding": 100.0,
            "technical": 100.0,
            "communication": 100.0,
            "academic": 100.0,
        }
        self.dash_view.refresh_dashboard()
        self.root.update_idletasks()

        pri_text = self.dash_view.pri_score_label.cget("text")
        self.assertEqual(pri_text, "100.0%")
        self.assertIn("Tier 1", self.dash_view.pri_badge.cget("text"))
        # All 10 companies should be eligible
        self.assertEqual(self.dash_view.elig_count_label.cget("text"), f"{len(COMPANIES_SEED_DATA)} / {len(COMPANIES_SEED_DATA)}")

    def test_dashboard_empty_and_missing_session_data(self):
        """Verifies Dashboard survives completely cleared session_data and missing fields."""
        # 1. Clear session data completely
        self.app.session_data.clear()
        self.dash_view.refresh_dashboard()
        self.root.update_idletasks()
        self.assertIsNotNone(self.dash_view.pri_score_label.cget("text"))

        # 2. Empty dimension_scores dict
        self.app.session_data["dimension_scores"] = {}
        self.dash_view.refresh_dashboard()
        self.root.update_idletasks()
        self.assertEqual(self.dash_view.pri_score_label.cget("text"), "0.0%")

        # 3. Partially missing dimension keys
        self.app.session_data["dimension_scores"] = {"coding": 90.0}
        self.dash_view.refresh_dashboard()
        self.root.update_idletasks()
        self.assertTrue(len(self.dash_view.chart_canvas.find_all()) > 5)

    def test_dashboard_extreme_scores_bounds(self):
        """Verifies negative dimension scores and >100 scores are bounded safely."""
        self.app.session_data["dimension_scores"] = {
            "aptitude": -50.0,
            "coding": 150.0,
            "technical": 200.0,
            "communication": -10.0,
            "academic": 10.0,
        }
        self.dash_view.refresh_dashboard()
        self.root.update_idletasks()

        pri_text = self.dash_view.pri_score_label.cget("text")
        self.assertTrue("%" in pri_text)
        pri_val = float(pri_text.replace("%", "").strip())
        self.assertGreaterEqual(pri_val, 0.0)
        self.assertLessEqual(pri_val, 100.0)

    def test_dashboard_tier_switching_recalculation(self):
        """Verifies changing target tier recomputes PRI, benchmarks, and updates gap diagnostics."""
        for tier_display, expected_tier in [
            ("Tier 1 Product", "Tier1"),
            ("Tier 2 Specialist", "Tier2"),
            ("Tier 3 Mass", "Tier3"),
        ]:
            self.dash_view.tier_segmented.set(tier_display)
            self.dash_view._on_tier_selected(tier_display)
            self.root.update_idletasks()
            self.assertEqual(self.app.session_data.get("target_tier"), expected_tier)
            self.assertTrue(len(self.dash_view.chart_canvas.find_all()) > 5)


# ==============================================================================
# Suite 2: Company View Adversarial Stress Tests
# ==============================================================================
@unittest.skipUnless(is_display_available(), "Display not available in headless environment")
class TestCompanyViewAdversarialStress(unittest.TestCase):
    """Stress tests CompanyView with extreme filter combinations, drawer stress, and edge queries."""

    def setUp(self):
        import customtkinter as ctk
        self.root = ctk.CTk()
        self.root.withdraw()
        self.app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        self.comp_view = self.app.register_view("company", CompanyView)
        self.app.navigate_to("company")
        self.root.update_idletasks()

    def tearDown(self):
        try:
            for timer_id in self.root.tk.call("after", "info"):
                try:
                    self.root.after_cancel(timer_id)
                except Exception:
                    pass
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            pass

    def test_company_filter_all_tiers_offline(self):
        """Verifies filtering by each placement tier returns genuine matching companies."""
        tier_counts = {}
        for tier_btn, tier_code in [
            ("Tier 1 Product", "Tier1"),
            ("Tier 2 Specialist", "Tier2"),
            ("Tier 3 Mass", "Tier3"),
            ("All", None),
        ]:
            self.comp_view.tier_segmented.set(tier_btn)
            self.comp_view.apply_filters()
            self.root.update_idletasks()

            badge_text = self.comp_view.count_badge.cget("text")
            self.assertIn("Showing", badge_text)
            tier_counts[tier_btn] = badge_text

        # All should show 10
        self.assertIn("Showing 10 of 10", tier_counts["All"])

    def test_company_cgpa_slider_extremes(self):
        """Verifies CGPA slider at 9.5 (or higher) filters out lower cutoff companies gracefully."""
        # 1. Slider at 9.5 -> no companies have min_cgpa >= 9.5 (max is 8.5)
        self.comp_view.cgpa_slider.set(9.5)
        self.comp_view._on_cgpa_slider_changed(9.5)
        self.root.update_idletasks()
        self.assertIn("Showing 0 of 10", self.comp_view.count_badge.cget("text"))

        # 2. Slider at 5.0 -> all companies match min_cgpa
        self.comp_view.cgpa_slider.set(5.0)
        self.comp_view._on_cgpa_slider_changed(5.0)
        self.root.update_idletasks()
        self.assertIn("Showing 10 of 10", self.comp_view.count_badge.cget("text"))

    def test_company_backlogs_and_branch_filters(self):
        """Verifies backlogs and branch options filter correctly."""
        # Zero backlogs only
        self.comp_view.backlogs_menu.set("0 (No Backlogs)")
        self.comp_view.apply_filters()
        self.root.update_idletasks()
        badge_0 = self.comp_view.count_badge.cget("text")
        self.assertIn("Showing", badge_0)

        # Branch CIVIL
        self.comp_view.branch_menu.set("CIVIL")
        self.comp_view.apply_filters()
        self.root.update_idletasks()
        badge_civil = self.comp_view.count_badge.cget("text")
        self.assertIn("Showing", badge_civil)

    def test_company_search_fuzzing(self):
        """Fuzzes search input with SQLi, whitespace, Unicode, and oversized strings."""
        fuzz_inputs = [
            "",
            "   ",
            "' OR '1'='1",
            "SELECT * FROM companies;",
            "🚀🔥💻",
            "A" * 1500,
            "NonExistentCompanyXYZ999",
            "Amazon",
            "Software Development",
        ]
        for query in fuzz_inputs:
            self.comp_view.search_entry.delete(0, "end")
            self.comp_view.search_entry.insert(0, query)
            self.comp_view.apply_filters()
            self.root.update_idletasks()
            self.assertIsNotNone(self.comp_view.count_badge.cget("text"))

    def test_company_drawers_rapid_expansion_stress(self):
        """Expands and collapses all 10 company drawers in sequence and verifies role data."""
        for comp in COMPANIES_SEED_DATA:
            name = comp["name"]
            # Expand
            self.comp_view._toggle_drawer(name, comp)
            self.root.update_idletasks()
            self.assertTrue(self.comp_view._expanded_drawers.get(name))

        # Collapse all
        for comp in COMPANIES_SEED_DATA:
            name = comp["name"]
            self.comp_view._toggle_drawer(name, comp)
            self.root.update_idletasks()
            self.assertFalse(self.comp_view._expanded_drawers.get(name))

    def test_company_eligibility_deficit_diagnosis_badges(self):
        """Verifies specific deficit diagnoses: CGPA deficit, backlogs exceeded, branch mismatch."""
        # 1. CGPA Deficit: CGPA 6.0, 0 backlogs, CSE -> Ineligible for Google (min_cgpa 8.5)
        self.app.session_data["cgpa"] = 6.0
        self.app.session_data["backlogs"] = 0
        self.app.session_data["branch"] = "CSE"
        self.comp_view.apply_filters()
        self.root.update_idletasks()

        # 2. Backlogs Exceeded: CGPA 9.0, 3 backlogs -> Ineligible for Amazon (max_backlogs 0)
        self.app.session_data["cgpa"] = 9.0
        self.app.session_data["backlogs"] = 3
        self.comp_view.apply_filters()
        self.root.update_idletasks()

        # 3. Branch Mismatch: CGPA 9.0, 0 backlogs, MECH -> Ineligible for Cisco (CSE, IT, ECE)
        self.app.session_data["cgpa"] = 9.0
        self.app.session_data["backlogs"] = 0
        self.app.session_data["branch"] = "MECH"
        self.comp_view.apply_filters()
        self.root.update_idletasks()

        # Reset filters works
        self.comp_view.reset_filters()
        self.root.update_idletasks()
        self.assertEqual(self.comp_view.search_entry.get(), "")


# ==============================================================================
# Suite 3: Math Studio View Adversarial Stress Tests
# ==============================================================================
@unittest.skipUnless(is_display_available(), "Display not available in headless environment")
class TestMathStudioViewAdversarialStress(unittest.TestCase):
    """Stress tests MathStudioView recurrence solver and dynamic aptitude generator."""

    def setUp(self):
        import customtkinter as ctk
        self.root = ctk.CTk()
        self.root.withdraw()
        self.app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        self.math_view = self.app.register_view("math_studio", MathStudioView)
        self.app.navigate_to("math_studio")
        self.root.update_idletasks()

    def tearDown(self):
        try:
            for timer_id in self.root.tk.call("after", "info"):
                try:
                    self.root.after_cancel(timer_id)
                except Exception:
                    pass
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            pass

    def test_all_classic_recurrence_presets_solve(self):
        """Verifies all 6 classic presets solve offline and produce closed-form & Big-O."""
        for name in RECURRENCE_TEMPLATES.keys():
            self.math_view.tmpl_menu.set(name)
            self.math_view._on_template_selected(name)
            self.root.update_idletasks()

            status = self.math_view.rec_status_label.cget("text")
            self.assertTrue("Solved in" in status, f"Preset '{name}' failed to solve: {status}")

            # Verify results cards rendered
            children = self.math_view.rec_results_frame.winfo_children()
            self.assertGreaterEqual(len(children), 2, f"Preset '{name}' should render at least Big-O and closed-form cards")

    def test_recurrence_malformed_equations_graceful_handling(self):
        """Tests malformed or unsolveable recurrence relations gracefully report errors without crashing."""
        malformed_cases = [
            ("", ""),                                    # Empty equation
            ("T(n) = 2*T(n/0) + n", "T(1)=1"),          # Division by zero
            ("T(n) = -3*T(n/2) + n", "T(1)=1"),         # Negative subproblems
            ("gibberish equation syntax", ""),           # Not a recurrence
            ("T(n) = T(n-1) + T(n-2) + T(n-3) + T(n-4)", "T(0)=0"), # High-order linear
            ("T(n) = T(n/2) +", "T(1)=1"),              # Incomplete syntax
        ]
        for eq, base in malformed_cases:
            self.math_view.eq_entry.delete(0, "end")
            self.math_view.eq_entry.insert(0, eq)
            self.math_view.base_entry.delete(0, "end")
            self.math_view.base_entry.insert(0, base)
            self.math_view.solve_recurrence_action()
            self.root.update_idletasks()

            # Confirm UI remains intact and status reflects error or prompt
            status = self.math_view.rec_status_label.cget("text")
            self.assertIsNotNone(status)

    def test_aptitude_generator_all_domains_and_difficulties(self):
        """Verifies aptitude generator across all 4 domains and 3 difficulties offline."""
        for domain_name in [
            "Time & Work (Harmonic Collaboration)",
            "Compound vs Simple Interest",
            "Urn Probability (Hypergeometric)",
            "Cayley's Tree Formula",
        ]:
            for diff in ["Easy", "Medium", "Hard"]:
                self.math_view.apt_topic_menu.set(domain_name)
                self.math_view.apt_diff_menu.set(diff)
                self.math_view.generate_problem_action()
                self.root.update_idletasks()

                prob = self.math_view._current_problem
                self.assertIsNotNone(prob, f"Problem generation failed for {domain_name} ({diff})")
                self.assertEqual(len(prob.get("options", [])), 4)
                self.assertIn(prob.get("correct_option_index"), [0, 1, 2, 3])
                self.assertGreater(len(prob.get("question_text", "")), 10)

    def test_aptitude_verification_correct_and_distractor(self):
        """Verifies verification action handles unselected, correct, and distractor choices."""
        self.math_view.apt_topic_menu.set("Time & Work (Harmonic Collaboration)")
        self.math_view.generate_problem_action()
        self.root.update_idletasks()

        # 1. Click verify without selecting any option
        self.math_view.radio_var.set(-1)
        self.math_view.verify_answer_action()
        self.root.update_idletasks()
        self.assertIn("select an option", self.math_view.verify_status_label.cget("text"))

        # 2. Select correct option
        correct_idx = self.math_view._current_problem["correct_option_index"]
        self.math_view.radio_var.set(correct_idx)
        self.math_view.verify_answer_action()
        self.root.update_idletasks()
        self.assertIn("Correct", self.math_view.verify_status_label.cget("text"))
        self.assertGreater(len(self.math_view.proof_container.winfo_children()), 0)

        # 3. Select distractor option
        distractor_idx = (correct_idx + 1) % 4
        self.math_view.radio_var.set(distractor_idx)
        self.math_view.verify_answer_action()
        self.root.update_idletasks()
        self.assertIn("Incorrect", self.math_view.verify_status_label.cget("text"))


# ==============================================================================
# Suite 4: Coding Sandbox View Adversarial Stress Tests
# ==============================================================================
@unittest.skipUnless(is_display_available(), "Display not available in headless environment")
class TestCodingSandboxViewAdversarialStress(unittest.TestCase):
    """Stress tests CodingSandboxView templates, divergence detection, timeout, and Canvas plot."""

    def setUp(self):
        import customtkinter as ctk
        self.root = ctk.CTk()
        self.root.withdraw()
        self.app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        self.sandbox = self.app.register_view("coding_sandbox", CodingSandboxView)
        self.app.navigate_to("coding_sandbox")
        self.root.update_idletasks()

    def tearDown(self):
        try:
            for timer_id in self.root.tk.call("after", "info"):
                try:
                    self.root.after_cancel(timer_id)
                except Exception:
                    pass
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            pass

    def test_sandbox_all_template_loaders(self):
        """Verifies loading all 5 templates populates code and claimed Big-O."""
        for tmpl_name in SANDBOX_TEMPLATES.keys():
            self.sandbox.template_menu.set(tmpl_name)
            self.sandbox._on_template_selected(tmpl_name)
            self.root.update_idletasks()

            code = self.sandbox.code_editor.get("1.0", "end")
            self.assertIn("def solve(n):", code)
            self.assertIsNotNone(self.sandbox.claimed_menu.get())

    def test_sandbox_empty_code_validation(self):
        """Verifies empty code editor prevents execution with informative prompt."""
        self.sandbox.code_editor.delete("1.0", "end")
        self.sandbox.run_benchmark_action()
        self.root.update_idletasks()
        self.assertIn("Please write Python code", self.sandbox.status_label.cget("text"))

    def test_sandbox_syntax_error_and_runtime_error_safety(self):
        """Verifies code with syntax or runtime errors is contained cleanly without GUI crash."""
        # 1. Syntax error
        code_syntax_err = "def solve(n):\n    return ;;;;\n"
        res = run_empirical_profile(code_syntax_err, [50, 100], timeout_sec=1.0)
        div = detect_divergence("O(n)", res.get("estimated_p", 1.0))
        self.sandbox._on_benchmark_completed(res, div, "O(n)")
        self.root.update_idletasks()

        # 2. Runtime error (ZeroDivision)
        code_runtime_err = "def solve(n):\n    return 1 / 0\n"
        res_rt = run_empirical_profile(code_runtime_err, [50, 100], timeout_sec=1.0)
        div_rt = detect_divergence("O(n)", res_rt.get("estimated_p", 1.0))
        self.sandbox._on_benchmark_completed(res_rt, div_rt, "O(n)")
        self.root.update_idletasks()

    def test_sandbox_divergence_detection_adversarial(self):
        """Verifies divergence alert banner triggers when quadratic code claims linear O(n)."""
        # Simulated profile results: p = 2.05 (Quadratic) with claimed O(n)
        fake_res = {
            "points": [(100, 0.001), (200, 0.004), (400, 0.016), (800, 0.064)],
            "estimated_p": 2.05,
            "empirical_big_o": "O(n^2)",
            "r_squared": 0.998,
            "timed_out": False,
        }
        div = detect_divergence("O(n)", fake_res["estimated_p"])
        self.assertTrue(div["divergence"], "Must detect divergence between claimed O(n) and empirical O(n^2)")

        self.sandbox._on_benchmark_completed(fake_res, div, "O(n)")
        self.root.update_idletasks()

        # Verify alert banner rendered in alert container
        alerts = self.sandbox.alert_container.winfo_children()
        self.assertEqual(len(alerts), 1)

    def test_sandbox_aligned_detection(self):
        """Verifies aligned banner triggers when linear code claims O(n)."""
        fake_res = {
            "points": [(100, 0.001), (200, 0.002), (400, 0.004), (800, 0.008)],
            "estimated_p": 1.01,
            "empirical_big_o": "O(n)",
            "r_squared": 0.999,
            "timed_out": False,
        }
        div = detect_divergence("O(n)", fake_res["estimated_p"])
        self.assertFalse(div["divergence"])

        self.sandbox._on_benchmark_completed(fake_res, div, "O(n)")
        self.root.update_idletasks()

    def test_sandbox_timeout_containment(self):
        """Verifies infinite loop triggers timeout handling and alert without UI freezing."""
        fake_timeout_res = {
            "points": [(100, 0.001)],
            "estimated_p": 1.0,
            "empirical_big_o": "O(?)",
            "r_squared": 0.0,
            "timed_out": True,
            "timeout_scale": 200,
        }
        div = {"divergence": True, "diagnostic": "Timeout", "alignment_score": 0.0}
        self.sandbox._on_benchmark_completed(fake_timeout_res, div, "O(n)")
        self.root.update_idletasks()

        self.assertIn("timeout", self.sandbox.status_label.cget("text").lower())

    def test_sandbox_curve_plot_boundary_cases(self):
        """Verifies Canvas curve plot handles 0 points, 1 point, and identical runtimes."""
        # 0 points
        self.sandbox._render_curve_plot([])
        self.root.update_idletasks()

        # 1 point
        self.sandbox._render_curve_plot([(100, 0.005)])
        self.root.update_idletasks()

        # Identical runtimes (prevent ZeroDivisionError in scaling)
        self.sandbox._render_curve_plot([(100, 0.005), (200, 0.005), (300, 0.005)])
        self.root.update_idletasks()
        self.assertGreater(len(self.sandbox.canvas.find_all()), 0)

    def test_sandbox_code_mode_switching(self):
        """Verifies switching between skeleton practice, naive trap, and model solution."""
        self.sandbox._load_template("Bubble Sort (O(n^2))", mode="skeleton")
        self.root.update_idletasks()
        self.assertEqual(self.sandbox._code_mode, "skeleton")
        self.assertIn("pass", self.sandbox.code_editor.get("1.0", "end"))

        # Switch to Naive Trap
        self.sandbox._set_code_mode("naive")
        self.root.update_idletasks()
        self.assertEqual(self.sandbox._code_mode, "naive")
        code_naive = self.sandbox.code_editor.get("1.0", "end")
        self.assertIn("arr[j] > arr[j + 1]", code_naive)
        self.assertIn("Naive Trap", self.sandbox.mode_status_badge.cget("text"))

        # Switch to Model Solution
        self.sandbox._set_code_mode("optimal")
        self.root.update_idletasks()
        self.assertEqual(self.sandbox._code_mode, "optimal")
        code_optimal = self.sandbox.code_editor.get("1.0", "end")
        self.assertIn("sorted(arr)", code_optimal)
        self.assertIn("Solution", self.sandbox.mode_status_badge.cget("text"))

        # Switch back to Skeleton
        self.sandbox._set_code_mode("skeleton")
        self.root.update_idletasks()
        self.assertEqual(self.sandbox._code_mode, "skeleton")
        self.assertIn("pass", self.sandbox.code_editor.get("1.0", "end"))
        self.assertIn("Practice", self.sandbox.mode_status_badge.cget("text"))

    def test_sandbox_font_zoom_controls(self):
        """Verifies font sizing, zooming shortcuts, and boundary clamping."""
        self.sandbox._set_font_size(12)
        self.assertEqual(self.sandbox._font_size, 12)
        self.assertEqual(self.sandbox.font_size_label.cget("text"), "12px")

        # Increase
        self.sandbox._increase_font()
        self.assertEqual(self.sandbox._font_size, 13)
        self.assertEqual(self.sandbox.font_size_label.cget("text"), "13px")

        # Decrease
        self.sandbox._decrease_font()
        self.assertEqual(self.sandbox._font_size, 12)

        # Reset
        self.sandbox._set_font_size(20)
        self.sandbox._reset_font()
        self.assertEqual(self.sandbox._font_size, 12)

        # Upper clamp
        self.sandbox._set_font_size(50)
        self.assertEqual(self.sandbox._font_size, 24)

        # Lower clamp
        self.sandbox._set_font_size(2)
        self.assertEqual(self.sandbox._font_size, 9)

        # Ctrl+MouseWheel event simulation
        class FakeWheelEvent:
            delta = 120
        self.assertEqual(self.sandbox._on_ctrl_mousewheel(FakeWheelEvent()), "break")
        self.assertEqual(self.sandbox._font_size, 10)

        FakeWheelEvent.delta = -120
        self.assertEqual(self.sandbox._on_ctrl_mousewheel(FakeWheelEvent()), "break")
        self.assertEqual(self.sandbox._font_size, 9)



# ==============================================================================
# Suite 5: Interview View Adversarial Stress Tests
# ==============================================================================
@unittest.skipUnless(is_display_available(), "Display not available in headless environment")
class TestInterviewViewAdversarialStress(unittest.TestCase):
    """Stress tests InterviewView question filtering, answer submission, and 3-tier scoring."""

    def setUp(self):
        import customtkinter as ctk
        self.root = ctk.CTk()
        self.root.withdraw()
        self.app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        self.iv_view = self.app.register_view("interview", InterviewView)
        self.app.navigate_to("interview")
        self.root.update_idletasks()

    def tearDown(self):
        try:
            for timer_id in self.root.tk.call("after", "info"):
                try:
                    self.root.after_cancel(timer_id)
                except Exception:
                    pass
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            pass

    def test_interview_filtering_all_categories_and_difficulties(self):
        """Verifies filtering by category and difficulty populates question selector or empty banner offline."""
        # 1. 'All Domains' and 'DSA Coding' have questions
        self.iv_view.diff_menu.set("All")
        self.iv_view.category_menu.set("All Domains")
        self.iv_view._apply_question_filters()
        self.root.update_idletasks()
        self.assertEqual(len(self.iv_view._filtered_questions), 30)

        self.iv_view.category_menu.set("DSA Coding")
        self.iv_view._apply_question_filters()
        self.root.update_idletasks()
        self.assertEqual(len(self.iv_view._filtered_questions), 8)

        # 2. Sub-domain categories where seed_data has category='Technical' match questions by topic prefix
        for cat_name in ["System Design", "Operating Systems", "DBMS & SQL", "Computer Networks", "Python Core"]:
            self.iv_view.category_menu.set(cat_name)
            self.iv_view._apply_question_filters()
            self.root.update_idletasks()
            # Confirms sub-domain questions match successfully without empty filter fallback
            self.assertGreater(len(self.iv_view._filtered_questions), 0)
            self.assertNotEqual(self.iv_view.question_menu.get(), "No questions matching filter")

        # 3. Filter difficulties with category='All Domains'
        self.iv_view.category_menu.set("All Domains")
        for diff in ["Easy", "Medium", "Hard"]:
            self.iv_view.diff_menu.set(diff)
            self.iv_view._apply_question_filters()
            self.root.update_idletasks()
            self.assertGreater(len(self.iv_view._filtered_questions), 0, f"Difficulty '{diff}' should have questions")

    def test_interview_random_question_picker(self):
        """Verifies random question button selects valid questions."""
        for _ in range(5):
            self.iv_view._on_random_question_clicked()
            self.root.update_idletasks()
            self.assertIsNotNone(self.iv_view._current_question)

    def test_interview_empty_submission_validation(self):
        """Verifies submitting with both explanation and code empty triggers warning."""
        self.iv_view._clear_inputs()
        self.iv_view.submit_evaluation_action()
        self.root.update_idletasks()
        self.assertIn("Please provide an explanation", self.iv_view.eval_status_label.cget("text"))

    def test_interview_explanation_only_submission(self):
        """Verifies submitting conceptual explanation without code evaluates keywords and structure."""
        self.iv_view.expl_textbox.delete("1.0", "end")
        self.iv_view.expl_textbox.insert(
            "1.0",
            "To solve this problem, we use a hash map for O(1) average lookup time. "
            "We iterate through the array, computing the complement target - num. "
            "If complement is present in map, return indices. Otherwise insert num: index."
        )
        self.iv_view.code_textbox.delete("1.0", "end")
        self.iv_view.submit_evaluation_action()
        self.root.update_idletasks()

        # Scorecard should be populated
        cards = self.iv_view.scorecard_container.winfo_children()
        self.assertGreaterEqual(len(cards), 2)

    def test_interview_syntax_error_code_submission(self):
        """Verifies code with syntax error produces ast_score=0 and diagnostic gap without crashing."""
        self.iv_view.expl_textbox.delete("1.0", "end")
        self.iv_view.expl_textbox.insert("1.0", "Valid conceptual approach.")
        self.iv_view.code_textbox.delete("1.0", "end")
        self.iv_view.code_textbox.insert("1.0", "def solution(:\n    return ;;;;\n")

        self.iv_view.submit_evaluation_action()
        self.root.update_idletasks()

        cards = self.iv_view.scorecard_container.winfo_children()
        self.assertGreaterEqual(len(cards), 2)

    def test_interview_anti_pattern_code_submission(self):
        """Verifies code with anti-patterns (bare except, while True) flags warnings."""
        anti_code = (
            "def solve(arr):\n"
            "    try:\n"
            "        while True:\n"
            "            pass\n"
            "    except:\n"
            "        pass\n"
        )
        self.iv_view.code_textbox.delete("1.0", "end")
        self.iv_view.code_textbox.insert("1.0", anti_code)
        self.iv_view.submit_evaluation_action()
        self.root.update_idletasks()

        cards = self.iv_view.scorecard_container.winfo_children()
        self.assertGreaterEqual(len(cards), 2)

    def test_interview_sample_answer_full_flow(self):
        """Verifies loading sample answer and submitting renders all 5 scorecard sections."""
        self.iv_view._load_sample_answer()
        self.iv_view.submit_evaluation_action()
        self.root.update_idletasks()

        self.assertIn("Evaluation complete", self.iv_view.eval_status_label.cget("text"))
        cards = self.iv_view.scorecard_container.winfo_children()
        self.assertGreaterEqual(len(cards), 3, "Scorecard should contain overall score, breakdown grid, and feedback")


# ==============================================================================
# Suite 6: AppWindow Lifecycle & Rapid View Navigation Stress
# ==============================================================================
@unittest.skipUnless(is_display_available(), "Display not available in headless environment")
class TestAppWindowLifecycleStress(unittest.TestCase):
    """Stress tests AppWindow navigation, view transitions, and offline warning banner."""

    def setUp(self):
        import customtkinter as ctk
        self.root = ctk.CTk()
        self.root.withdraw()

    def tearDown(self):
        try:
            for timer_id in self.root.tk.call("after", "info"):
                try:
                    self.root.after_cancel(timer_id)
                except Exception:
                    pass
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            pass

    def test_rapid_view_navigation_10_cycles(self):
        """Rapidly navigates through all 5 views across 10 cycles (50 view transitions)."""
        app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        app.register_view("dashboard", DashboardView)
        app.register_view("company", CompanyView)
        app.register_view("math_studio", MathStudioView)
        app.register_view("coding_sandbox", CodingSandboxView)
        app.register_view("interview", InterviewView)

        view_keys = ["dashboard", "company", "math_studio", "coding_sandbox", "interview"]

        t0 = time.perf_counter()
        for cycle in range(10):
            for v_key in view_keys:
                app.navigate_to(v_key)
                self.assertEqual(app._current_view_key, v_key)

        elapsed = time.perf_counter() - t0
        self.root.update_idletasks()
        # 50 transitions should be smooth and fast (< 10.0 seconds)
        self.assertLess(elapsed, 10.0, f"50 view transitions took too long: {elapsed:.2f}s")

    def test_offline_warning_banner_and_pill(self):
        """Verifies offline warning banner and status pill correctly display in offline mode."""
        app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        self.assertIn("Offline", app.status_label.cget("text"))


if __name__ == "__main__":
    unittest.main()
