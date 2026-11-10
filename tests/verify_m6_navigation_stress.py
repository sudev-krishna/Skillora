"""
Skillora Milestone 6 Empirical Challenger Navigation Stress & State Dirty-Checking Verification Harness
File: tests/verify_m6_navigation_stress.py

Adversarially challenges:
1. Dirty-checking cache invalidation and state retention in CompanyView:
   - Filter parameter sweeps (search query, tier, CGPA slider, backlogs, branch)
   - Student session data mutations (CGPA, backlogs, branch)
   - Expandable card drawers state tracking and toggling
   - Stale card and label corruption detection
   - Idempotent no-op skip verification
2. Dirty-checking cache invalidation in DashboardView:
   - Target tier switching and PRI recalculation
   - In-place CTkLabel reuse in _update_gap_labels across varying gap counts (0, 1, 3, 5)
   - Dimensional score mutations and canvas chart redrawing
   - Idempotent no-op skip verification
3. Concurrent navigation stress:
   - Rapid view switching concurrent with background polling and state updates
   - Latency profiling and Tkinter event loop stability
"""

import logging
import os
import sys
import threading
import time
import unittest
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import customtkinter as ctk

from client.gui.app_window import AppWindow
from client.gui.views.coding_sandbox_view import CodingSandboxView
from client.gui.views.company_view import CompanyView
from client.gui.views.dashboard_view import DashboardView
from client.gui.views.interview_view import InterviewView
from client.gui.views.math_studio_view import MathStudioView
from server.db.seed_data import COMPANIES_SEED_DATA

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("skillora.m6_challenger_stress")


def is_display_available() -> bool:
    """Detects whether a graphical display is accessible for Tkinter rendering."""
    if sys.platform != "win32" and not os.environ.get("DISPLAY"):
        return False
    try:
        t = ctk.CTk()
        t.withdraw()
        t.destroy()
        return True
    except Exception:
        return False


class TestCompanyViewDirtyCheckingAdversarial(unittest.TestCase):
    """
    Adversarial verification of CompanyView state caching, dirty checking,
    and drawer expansion behavior.
    """

    @classmethod
    def setUpClass(cls):
        if not is_display_available():
            raise unittest.SkipTest("Display unavailable for Tkinter testing")
        cls.root = ctk.CTk()
        cls.root.withdraw()

    def setUp(self):
        self.root = ctk.CTk()
        self.root.withdraw()
        self.session_data = {
            "username": "candidate_test",
            "full_name": "Test Candidate",
            "cgpa": 8.50,
            "backlogs": 0,
            "branch": "CSE",
            "target_tier": "Tier1",
            "dimension_scores": {
                "aptitude": 85.0,
                "coding": 80.0,
                "technical": 82.0,
                "communication": 88.0,
                "academic": 85.0,
            },
        }
        self.app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        self.app.session_data = self.session_data
        self.view = self.app.register_view("company", CompanyView)
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

    def test_dirty_checking_no_op_preserves_widgets(self):
        """
        Verify that repeated calls to on_show() without state change
        DO NOT destroy and re-create child widgets in cards_scroll.
        """
        initial_children = self.view.cards_scroll.winfo_children()
        initial_count = len(initial_children)
        self.assertGreater(initial_count, 0, "Initial render must have company cards")
        initial_ids = [id(w) for w in initial_children]

        # Call on_show() multiple times without mutating state
        for _ in range(20):
            self.view.on_show()

        subsequent_children = self.view.cards_scroll.winfo_children()
        subsequent_ids = [id(w) for w in subsequent_children]

        self.assertEqual(
            initial_ids,
            subsequent_ids,
            "Dirty checking MUST bypass widget destruction and maintain exact widget identities when state is unmodified",
        )

    def test_rapid_filter_mutations_invalidate_cache_correctly(self):
        """
        Rapidly mutates all 5 filter controls and verifies that cards update accurately
        without leaving stale cards or desynchronized badges.
        """
        # 1. Search Query mutation
        self.view.search_entry.delete(0, "end")
        self.view.search_entry.insert(0, "Amazon")
        self.view.apply_filters()
        self.root.update_idletasks()
        self.assertIn("Showing 1 of 10", self.view.count_badge.cget("text"))

        # 2. Non-existent Query mutation
        self.view.search_entry.delete(0, "end")
        self.view.search_entry.insert(0, "NonExistentCompany_XYZ_999")
        self.view.apply_filters()
        self.root.update_idletasks()
        self.assertIn("Showing 0 of 10", self.view.count_badge.cget("text"))

        # 3. Reset filters
        self.view.reset_filters()
        self.root.update_idletasks()
        self.assertIn("Showing 10 of 10", self.view.count_badge.cget("text"))

        # 4. Tier Filter mutation
        self.view.tier_segmented.set("Tier 1 Product")
        self.view.apply_filters()
        self.root.update_idletasks()
        t1_count = len([c for c in COMPANIES_SEED_DATA if c.get("tier") == "Tier1"])
        self.assertIn(f"Showing {t1_count} of 10", self.view.count_badge.cget("text"))

        # 5. Backlogs Filter mutation
        self.view.tier_segmented.set("All")
        self.view.backlogs_menu.set("0 (No Backlogs)")
        self.view.apply_filters()
        self.root.update_idletasks()
        zero_bl_count = len([c for c in COMPANIES_SEED_DATA if int(c.get("max_backlogs", 0)) == 0])
        self.assertIn(f"Showing {zero_bl_count} of 10", self.view.count_badge.cget("text"))

        # 6. Branch Filter mutation
        self.view.backlogs_menu.set("Any")
        self.view.branch_menu.set("CIVIL")
        self.view.apply_filters()
        self.root.update_idletasks()
        civil_count = len([
            c for c in COMPANIES_SEED_DATA
            if "ALL" in [b.strip().upper() for b in c.get("eligible_branches_csv", "").split(",")]
            or "CIVIL" in [b.strip().upper() for b in c.get("eligible_branches_csv", "").split(",")]
        ])
        self.assertIn(f"Showing {civil_count} of 10", self.view.count_badge.cget("text"))

    def test_student_session_mutation_updates_eligibility_pills(self):
        """
        Verifies that mutating student session attributes (CGPA, backlogs, branch)
        forces cache invalidation on on_show() and updates eligibility badges accurately.
        """
        # Baseline: 8.5 CGPA, 0 backlogs, CSE -> High eligibility
        self.view.reset_filters()
        self.view.on_show()
        badge_text_initial = self.view.count_badge.cget("text")

        # Mutate student session: drop CGPA to 5.5 (ineligible for most Tier 1/2)
        self.session_data["cgpa"] = 5.50
        self.view.on_show()
        self.root.update_idletasks()
        badge_text_low_cgpa = self.view.count_badge.cget("text")
        self.assertNotEqual(badge_text_initial, badge_text_low_cgpa)

        # Mutate student session: set backlogs to 3 (ineligible for zero-backlog companies)
        self.session_data["cgpa"] = 9.00
        self.session_data["backlogs"] = 3
        self.view.on_show()
        self.root.update_idletasks()
        badge_text_high_backlogs = self.view.count_badge.cget("text")
        self.assertNotEqual(badge_text_initial, badge_text_high_backlogs)

        # Mutate student session: set branch to MECH
        self.session_data["backlogs"] = 0
        self.session_data["branch"] = "MECH"
        self.view.on_show()
        self.root.update_idletasks()
        badge_text_mech = self.view.count_badge.cget("text")
        self.assertNotEqual(badge_text_initial, badge_text_mech)

    def test_drawer_expansion_state_cached_and_toggled(self):
        """
        Verifies that expanding and collapsing company card drawers properly invalidates
        the cache key and preserves expanded drawer states without crash.
        """
        comp_name = "Amazon"
        self.assertFalse(self.view._expanded_drawers.get(comp_name, False))

        # Expand drawer
        comp = next(c for c in COMPANIES_SEED_DATA if c.get("name") == comp_name)
        self.view._toggle_drawer(comp_name, comp)
        self.root.update_idletasks()

        self.assertTrue(self.view._expanded_drawers.get(comp_name, False))
        self.assertIn(comp_name, self.view._drawer_frames)

        # Verify on_show() maintains expanded drawer without discarding it
        self.view.on_show()
        self.root.update_idletasks()
        self.assertTrue(self.view._expanded_drawers.get(comp_name, False))

        # Collapse drawer
        self.view._toggle_drawer(comp_name, comp)
        self.root.update_idletasks()
        self.assertFalse(self.view._expanded_drawers.get(comp_name, False))


class TestDashboardViewDirtyCheckingAdversarial(unittest.TestCase):
    """
    Adversarial verification of DashboardView state caching, gap label reuse,
    and tier switching behavior.
    """

    @classmethod
    def setUpClass(cls):
        if not is_display_available():
            raise unittest.SkipTest("Display unavailable for Tkinter testing")
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.root = ctk.CTk()
        self.root.withdraw()
        self.session_data = {
            "username": "dash_tester",
            "full_name": "Dashboard Tester",
            "cgpa": 8.42,
            "backlogs": 0,
            "branch": "CSE",
            "target_tier": "Tier1",
            "dimension_scores": {
                "aptitude": 82.0,
                "coding": 70.0,
                "technical": 78.0,
                "communication": 85.0,
                "academic": 84.2,
            },
        }
        self.app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        self.app.session_data = self.session_data
        self.view = self.app.register_view("dashboard", DashboardView)
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

    def test_dashboard_dirty_checking_no_op_bypasses_redraw(self):
        """
        Verify that repeated calls to on_show() without state change
        bypass canvas chart deletion and maintain gap label widgets.
        """
        initial_labels = [w for w in self.view.gap_labels_container.winfo_children() if isinstance(w, ctk.CTkLabel)]
        initial_label_ids = [id(w) for w in initial_labels]

        for _ in range(25):
            self.view.on_show()

        subsequent_labels = [w for w in self.view.gap_labels_container.winfo_children() if isinstance(w, ctk.CTkLabel)]
        subsequent_label_ids = [id(w) for w in subsequent_labels]

        self.assertEqual(
            initial_label_ids,
            subsequent_label_ids,
            "Dashboard dirty checking must preserve gap label widgets across idempotent on_show() calls",
        )

    def test_gap_labels_in_place_update_transitions(self):
        """
        Stress tests _update_gap_labels with varying numbers of gap items:
        5 gaps -> 2 gaps -> 0 gaps (success label) -> 3 gaps.
        Confirms zero widget leaks and zero Tkinter errors.
        """
        # Case A: 5 gaps
        gaps_5 = [f"Competency gap in dimension {i}" for i in range(1, 6)]
        self.view._update_gap_labels(gaps_5)
        self.root.update_idletasks()
        labels_5 = [w for w in self.view.gap_labels_container.winfo_children() if isinstance(w, ctk.CTkLabel)]
        self.assertEqual(len(labels_5), 5)
        for i, lbl in enumerate(labels_5):
            self.assertIn(f"Competency gap in dimension {i+1}", lbl.cget("text"))

        # Case B: Shrink to 2 gaps (reusing first 2 labels, destroying 3 surplus)
        gaps_2 = ["Gap Alpha", "Gap Beta"]
        self.view._update_gap_labels(gaps_2)
        self.root.update_idletasks()
        labels_2 = [w for w in self.view.gap_labels_container.winfo_children() if isinstance(w, ctk.CTkLabel)]
        self.assertEqual(len(labels_2), 2)
        self.assertIn("Gap Alpha", labels_2[0].cget("text"))
        self.assertIn("Gap Beta", labels_2[1].cget("text"))

        # Case C: 0 gaps (all benchmarks met -> single success badge)
        self.view._update_gap_labels([])
        self.root.update_idletasks()
        labels_0 = [w for w in self.view.gap_labels_container.winfo_children() if isinstance(w, ctk.CTkLabel)]
        self.assertEqual(len(labels_0), 1)
        self.assertIn("Outstanding", labels_0[0].cget("text"))

        # Case D: Expand back to 3 gaps
        gaps_3 = ["Gap X", "Gap Y", "Gap Z"]
        self.view._update_gap_labels(gaps_3)
        self.root.update_idletasks()
        labels_3 = [w for w in self.view.gap_labels_container.winfo_children() if isinstance(w, ctk.CTkLabel)]
        self.assertEqual(len(labels_3), 3)

    def test_rapid_tier_switching(self):
        """
        Rapidly switches target placement tier and verifies that PRI score,
        eligibility, and competency chart reflect tier benchmarks.
        """
        tiers = [
            ("Tier 1 Product", "Tier1"),
            ("Tier 2 Specialist", "Tier2"),
            ("Tier 3 Mass", "Tier3"),
        ]

        for display_tier, internal_tier in tiers:
            self.view.tier_segmented.set(display_tier)
            self.view._on_tier_selected(display_tier)
            self.root.update_idletasks()

            self.assertEqual(self.session_data.get("target_tier"), internal_tier)
            pri_text = self.view.pri_score_label.cget("text")
            self.assertTrue(pri_text.endswith("%"), f"PRI score should end with % but got {pri_text}")
            self.assertIn(internal_tier, self.view.pri_deficit_label.cget("text"))

    def test_session_data_mutation_forces_recalculation(self):
        """
        Mutating student dimension_scores directly in session_data triggers
        recalculation on subsequent on_show().
        """
        initial_pri_text = self.view.pri_score_label.cget("text")

        # Drastically reduce coding score
        self.session_data["dimension_scores"]["coding"] = 25.0
        self.view.on_show()
        self.root.update_idletasks()

        new_pri_text = self.view.pri_score_label.cget("text")
        self.assertNotEqual(initial_pri_text, new_pri_text, "PRI score must update when dimension scores mutate")


class TestConcurrentNavigationAndBackgroundActivity(unittest.TestCase):
    """
    Simulates high concurrency: rapid view switching on the main Tkinter thread
    concurrent with active background socket / polling activity.
    """

    @classmethod
    def setUpClass(cls):
        if not is_display_available():
            raise unittest.SkipTest("Display unavailable for Tkinter testing")
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.root = ctk.CTk()
        self.root.withdraw()
        self.app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        self.app.register_view("dashboard", DashboardView)
        self.app.register_view("company", CompanyView)
        self.app.register_view("math_studio", MathStudioView)
        self.app.register_view("coding_sandbox", CodingSandboxView)
        self.app.register_view("interview", InterviewView)
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

    def test_rapid_navigation_under_concurrent_background_polling(self):
        """
        Runs 100 rapid view transitions while a background thread continuously
        simulates packet reception and status polling.
        """
        stop_event = threading.Event()
        poll_count = [0]

        def background_poller():
            while not stop_event.is_set():
                poll_count[0] += 1
                time.sleep(0.005)  # 5ms background activity burst

        poller_thread = threading.Thread(target=background_poller, daemon=True)
        poller_thread.start()

        view_keys = ["dashboard", "company", "math_studio", "coding_sandbox", "interview"]
        t0 = time.perf_counter()
        switches = 100

        try:
            for i in range(switches):
                target = view_keys[i % len(view_keys)]
                self.app.navigate_to(target)
                self.root.update_idletasks()
                self.assertEqual(self.app._current_view_key, target)
        finally:
            stop_event.set()
            poller_thread.join(timeout=1.0)

        elapsed = time.perf_counter() - t0
        avg_ms = (elapsed / switches) * 1000.0

        logger.info(
            "Concurrent stress: %d switches in %.3fs (avg %.2fms/switch), background polls: %d",
            switches,
            elapsed,
            avg_ms,
            poll_count[0],
        )

        self.assertLess(elapsed, 15.0, f"100 concurrent switches took {elapsed:.2f}s, exceeding 15s budget")
        self.assertLess(avg_ms, 150.0, f"Average switch latency ({avg_ms:.2f}ms) exceeds 150ms budget")
        self.assertGreater(poll_count[0], 50, "Background poller should have executed > 50 times during test")


if __name__ == "__main__":
    unittest.main()
