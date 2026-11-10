"""
Skillora GUI Architecture, Theme System & Bridge Test Suite (tests/test_gui.py)
Exercises theme color compliance, font tuple safety, Tkinter queue polling bridge,
view frame switching, and offline self-contained fallbacks across all 5 views.
Headless CI-compatible (tests pass 100% both in headless CI and desktop display environments).
"""

import os
import sys
import unittest
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.gui.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_INDIGO,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CODE,
    FONT_CODE_BOLD,
    FONT_DISPLAY,
    FONT_HEADING,
    FONT_SMALL,
    FONT_SMALL_BOLD,
    FONT_SUBTITLE,
    FONT_TITLE,
    RADIUS_BADGE,
    RADIUS_BUTTON,
    RADIUS_CARD,
    RADIUS_PILL,
    enforce_light_theme,
    get_font,
)
from client.network.socket_client import SocketClient
from server.bot.evaluator import evaluate_answer
from server.db.seed_data import COMPANIES_SEED_DATA, QUESTIONS_SEED_DATA
from server.math_engine.aptitude_generator import generate_problem
from server.pipeline.placement import (
    compute_placement_readiness_index,
    filter_eligible_companies,
    is_eligible,
)
from server.profiler.recurrence import solve_recurrence


def is_display_available() -> bool:
    """Checks whether a GUI display is accessible for widget rendering."""
    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        r.destroy()
        return True
    except Exception:
        return False


class MockTkRoot:
    """Mock Tkinter root object for testing bind_to_tk without an active display."""

    def __init__(self):
        self.timers: Dict[int, Any] = {}
        self._timer_counter = 0

    def after(self, ms: int, func: Any) -> int:
        self._timer_counter += 1
        timer_id = self._timer_counter
        self.timers[timer_id] = (ms, func)
        return timer_id

    def after_cancel(self, timer_id: int) -> None:
        self.timers.pop(timer_id, None)


# ==============================================================================
# Tier 1: Theme & Style Integrity Tests (100% Headless)
# ==============================================================================
class TestGUIThemeSystem(unittest.TestCase):
    """Tier 1: Theme & Style Integrity Tests without creating Tk root."""

    def test_strict_light_palette_hex_codes(self):
        """Verifies all mandatory colors match the warm minimalist studio specification."""
        self.assertEqual(COLOR_BG, "#FAF9F5", "Background must be Warm Studio Canvas (#FAF9F5)")
        self.assertEqual(COLOR_CARD, "#FFFFFF", "Card surface must be pure white (#FFFFFF)")
        self.assertEqual(COLOR_BORDER, "#EAE6DF", "Border must be Warm Divider (#EAE6DF)")
        self.assertEqual(COLOR_TEXT_PRIMARY, "#191C1F", "Primary text must be Deep Charcoal (#191C1F)")
        self.assertEqual(COLOR_TEXT_SECONDARY, "#686B6F", "Secondary text must be Medium Slate (#686B6F)")
        self.assertEqual(COLOR_ACCENT_BLUE, "#FF6442", "Accent brand color must be #FF6442")
        self.assertEqual(COLOR_ACCENT_INDIGO, "#FF7A59", "Accent peach/indigo must be #FF7A59")
        self.assertEqual(COLOR_SUCCESS, "#10B981", "Success color must be Emerald Green (#10B981)")
        self.assertEqual(COLOR_WARNING, "#F59E0B", "Warning color must be Warm Amber (#F59E0B)")
        self.assertEqual(COLOR_DANGER, "#EF4444", "Danger color must be Rose Red (#EF4444)")

    def test_font_tuples_zero_root_safety(self):
        """Verifies font constants are immutable tuples safe to import without root."""
        for name, font_tuple in [
            ("DISPLAY", FONT_DISPLAY),
            ("TITLE", FONT_TITLE),
            ("SUBTITLE", FONT_SUBTITLE),
            ("HEADING", FONT_HEADING),
            ("BODY", FONT_BODY),
            ("BODY_BOLD", FONT_BODY_BOLD),
            ("SMALL", FONT_SMALL),
            ("SMALL_BOLD", FONT_SMALL_BOLD),
            ("CODE", FONT_CODE),
            ("CODE_BOLD", FONT_CODE_BOLD),
        ]:
            self.assertIsInstance(font_tuple, tuple, f"{name} font must be a tuple")
            self.assertEqual(len(font_tuple), 3, f"{name} font tuple must have (family, size, weight)")
            self.assertIsInstance(font_tuple[0], str)
            self.assertIsInstance(font_tuple[1], int)
            self.assertIsInstance(font_tuple[2], str)

    def test_enforce_light_theme(self):
        """Verifies light theme enforcement sets CustomTkinter appearance mode."""
        import customtkinter as ctk
        enforce_light_theme()
        self.assertEqual(ctk.get_appearance_mode(), "Light")

    def test_get_font_helper_fallback(self):
        """Verifies get_font helper returns valid font spec even without root."""
        font_res = get_font(FONT_TITLE)
        self.assertIsNotNone(font_res)

    def test_radii_constants(self):
        """Verifies radii dimensions are configured."""
        self.assertEqual(RADIUS_CARD, 12)
        self.assertEqual(RADIUS_BUTTON, 8)
        self.assertEqual(RADIUS_BADGE, 12)
        self.assertEqual(RADIUS_PILL, 16)


# ==============================================================================
# Tier 2: Bridge & Queue Polling Logic Tests (100% Headless via MockTkRoot)
# ==============================================================================
class TestSocketTkBridge(unittest.TestCase):
    """Tier 2: Bridge & Queue Polling Logic Tests via MockTkRoot."""

    def test_bind_to_tk_schedules_polling(self):
        """Verifies bind_to_tk registers recurring after() tick with specified interval."""
        mock_root = MockTkRoot()
        client = SocketClient(host="127.0.0.1", port=59990, auto_reconnect=False)
        client.bind_to_tk(mock_root, interval_ms=50)

        self.assertEqual(len(mock_root.timers), 1)
        timer_id, (ms, callback) = list(mock_root.timers.items())[0]
        self.assertEqual(ms, 50)
        self.assertTrue(callable(callback))

        # Stop client cancels timer
        client.stop()
        self.assertEqual(len(mock_root.timers), 0)

    def test_poll_responses_drains_and_executes_callback(self):
        """Verifies responses placed on the internal queue fire UI callbacks during polling."""
        client = SocketClient(host="127.0.0.1", port=59991, auto_reconnect=False)
        received_data = []

        def ui_callback(payload):
            received_data.append(payload)

        req_id = client.send_request("PING", {"test": 1}, callback=ui_callback)

        # Simulate synthetic server response enqueued
        fake_response = {
            "action": "PING",
            "request_id": req_id,
            "status": "SUCCESS",
            "payload": {"server_time": 123456.0},
        }
        client._response_queue.put(("RESPONSE", fake_response))

        # Drain queue via poll_responses (simulating root.after tick on main thread)
        processed = client.poll_responses()
        self.assertGreaterEqual(processed, 1)
        self.assertEqual(len(received_data), 1)
        self.assertEqual(received_data[0]["payload"]["server_time"], 123456.0)

    def test_connection_status_listener_dispatch(self):
        """Verifies connection state transitions are dispatched to registered UI listeners."""
        client = SocketClient(host="127.0.0.1", port=59992, auto_reconnect=False)
        states = []

        def status_observer(status, data):
            states.append(status)

        client.register_status_listener(status_observer)
        # Immediate initial state notification
        self.assertIn("DISCONNECTED", states)

        # Enqueue state update and poll
        client._set_state("CONNECTING")
        client.poll_responses()
        self.assertIn("CONNECTING", states)


# ==============================================================================
# Tier 3: Offline Data & Engine Fallback Tests (100% Headless)
# ==============================================================================
class TestOfflineDataAndEngineFallbacks(unittest.TestCase):
    """Tier 3: Verifies 100% offline self-contained calculation for all views."""

    def test_dashboard_offline_pri_and_eligibility(self):
        """Verifies Dashboard pure functional PRI and company eligibility calculations."""
        student = {
            "cgpa": 8.42,
            "backlogs": 0,
            "branch": "CSE",
            "dimension_scores": {
                "aptitude": 82.0,
                "coding": 70.0,
                "technical": 78.0,
                "communication": 85.0,
                "academic": 84.2,
            },
        }
        pri_res = compute_placement_readiness_index(student["dimension_scores"], "Tier1")
        self.assertIsInstance(pri_res, dict)
        self.assertIn("pri_score", pri_res)
        self.assertGreater(pri_res["pri_score"], 70.0)
        self.assertIn("tier_readiness", pri_res)
        self.assertIn("gap_analysis", pri_res)

        eligible = filter_eligible_companies(COMPANIES_SEED_DATA, student)
        self.assertIsInstance(eligible, list)
        self.assertGreaterEqual(len(eligible), 5)

    def test_company_seed_data_eligibility_predicates(self):
        """Verifies company explorer eligibility predicate matching."""
        student_eligible = {"cgpa": 9.0, "backlogs": 0, "branch": "CSE"}
        student_ineligible = {"cgpa": 5.0, "backlogs": 3, "branch": "CIVIL"}

        for comp in COMPANIES_SEED_DATA:
            self.assertTrue(is_eligible(comp, student_eligible))
            # student with 5.0 CGPA and 3 backlogs is ineligible for Tier 1
            if comp["tier"] == "Tier1":
                self.assertFalse(is_eligible(comp, student_ineligible))

    def test_math_studio_offline_recurrence_solver(self):
        """Verifies recurrence equations solve offline via SymPy rsolve."""
        res = solve_recurrence("T(n) = 2*T(n/2) + n", {"T(1)": 1})
        self.assertIsNone(res.get("error"))
        self.assertEqual(res.get("big_o"), "O(n log n)")
        self.assertIsNotNone(res.get("closed_form"))

    def test_math_studio_offline_aptitude_generator(self):
        """Verifies aptitude problems generate offline with 4 options and proof steps."""
        for domain in ["work", "ci_si", "urn", "cayley"]:
            prob = generate_problem(domain, "medium")
            self.assertEqual(len(prob["options"]), 4)
            self.assertIn(prob["correct_option_index"], [0, 1, 2, 3])
            self.assertTrue(len(prob["proof_steps"]) >= 2)

    def test_interview_offline_evaluator(self):
        """Verifies interview answers evaluate offline with 3-tier scoring."""
        q = QUESTIONS_SEED_DATA[0]
        ans = "Iterative three-pointer approach using prev, current, next. In-place O(1) space, O(n) time."
        code = "def reverse_list(head):\n    prev = None\n    curr = head\n    while curr:\n        nxt = curr.next\n        curr.next = prev\n        prev = curr\n        curr = nxt\n    return prev\n"
        eval_res = evaluate_answer(q, ans, code)
        self.assertIn("total_score", eval_res)
        self.assertGreater(eval_res["total_score"], 60.0)
        self.assertIn("keyword_score", eval_res)
        self.assertIn("structure_score", eval_res)
        self.assertIn("ast_score", eval_res)


# ==============================================================================
# Tier 4: Live GUI Widget Integration Tests (Withdrawn Tk Root)
# ==============================================================================
@unittest.skipUnless(is_display_available(), "Display not available in headless environment")
class TestLiveGUIWidgetIntegration(unittest.TestCase):
    """Tier 4: Live Widget Instantiation & Frame Switching Tests (Withdrawn Tk)."""

    def setUp(self):
        import customtkinter as ctk
        self.root = ctk.CTk()
        self.root.withdraw()  # Never display a physical window during automated tests

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

    def test_app_window_initialization_and_switching(self):
        """Verifies AppWindow layout construction, view registration, and frame switching."""
        from client.gui.app_window import AppWindow
        from client.gui.views import (
            CodingSandboxView,
            CompanyView,
            DashboardView,
            InterviewView,
            MathStudioView,
        )

        app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        app.register_view("dashboard", DashboardView)
        app.register_view("company", CompanyView)
        app.register_view("math_studio", MathStudioView)
        app.register_view("coding_sandbox", CodingSandboxView)
        app.register_view("interview", InterviewView)

        # Navigate across all 5 views
        for view_key in ["dashboard", "company", "math_studio", "coding_sandbox", "interview"]:
            app.navigate_to(view_key)
            self.assertEqual(app._current_view_key, view_key)

        # Pump Tkinter event loop
        self.root.update_idletasks()
        self.root.update()

    def test_dashboard_view_components(self):
        """Verifies DashboardView KPI cards, canvas chart, and tier selection."""
        from client.gui.app_window import AppWindow
        from client.gui.views.dashboard_view import DashboardView

        app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        dash = app.register_view("dashboard", DashboardView)
        app.navigate_to("dashboard")

        self.assertIsNotNone(dash.pri_score_label)
        self.assertIsNotNone(dash.chart_canvas)
        # Test selecting a different tier
        dash._on_tier_selected("Tier 2 Specialist")
        self.assertEqual(app.session_data.get("target_tier"), "Tier2")
        self.root.update_idletasks()

    def test_company_view_filter_interaction(self):
        """Verifies CompanyView filter changes and drawer expansion."""
        from client.gui.app_window import AppWindow
        from client.gui.views.company_view import CompanyView

        app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        comp_view = app.register_view("company", CompanyView)
        app.navigate_to("company")

        # Test search query filter
        comp_view.search_entry.insert(0, "Amazon")
        comp_view.apply_filters()
        self.assertIn("Showing", comp_view.count_badge.cget("text"))

        # Test drawer toggle
        comp_view._toggle_drawer("Amazon", COMPANIES_SEED_DATA[0])
        self.assertTrue(comp_view._expanded_drawers.get("Amazon", False))
        self.root.update_idletasks()

    def test_math_studio_solve_interaction(self):
        """Verifies MathStudioView solving and aptitude generation."""
        from client.gui.app_window import AppWindow
        from client.gui.views.math_studio_view import MathStudioView

        app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        math_view = app.register_view("math_studio", MathStudioView)
        app.navigate_to("math_studio")

        # Test solving recurrence
        math_view.eq_entry.delete(0, "end")
        math_view.eq_entry.insert(0, "T(n) = T(n/2) + 1")
        math_view.solve_recurrence_action()
        self.root.update_idletasks()

        # Test generating problem
        math_view.generate_problem_action()
        self.assertIsNotNone(math_view._current_problem)
        self.root.update_idletasks()

    def test_coding_sandbox_template_selection(self):
        """Verifies CodingSandboxView template loading."""
        from client.gui.app_window import AppWindow
        from client.gui.views.coding_sandbox_view import CodingSandboxView

        app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        sandbox = app.register_view("coding_sandbox", CodingSandboxView)
        app.navigate_to("coding_sandbox")

        sandbox._load_template("Bubble Sort (O(n^2))")
        code = sandbox.code_editor.get("1.0", "end")
        self.assertIn("def solve(n):", code)
        self.assertEqual(sandbox.claimed_menu.get(), "O(n^2)")
        self.root.update_idletasks()

    def test_interview_view_sample_answer_and_eval(self):
        """Verifies InterviewView sample answer loading and evaluation."""
        from client.gui.app_window import AppWindow
        from client.gui.views.interview_view import InterviewView

        app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        iv_view = app.register_view("interview", InterviewView)
        app.navigate_to("interview")

        iv_view._load_sample_answer()
        self.assertTrue(len(iv_view.expl_textbox.get("1.0", "end").strip()) > 10)

        # Trigger evaluation
        iv_view.submit_evaluation_action()
        self.root.update_idletasks()

    def test_global_on_demand_zoom_hud_and_shortcuts(self):
        """Verifies invisible-by-default global zoom HUD, Ctrl shortcuts, and scale clamping."""
        from client.gui.app_window import AppWindow

        app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        # Ensure clean 1.0 zoom baseline for test
        app._apply_zoom(1.0, reveal_hud=False)
        app._hide_zoom_hud()
        self.root.update_idletasks()

        # 1. Initially hidden (no place geometry manager attached)
        self.assertFalse(bool(app._zoom_hud.place_info()))

        # 2. Zoom in triggers HUD reveal and updates percentage
        app._zoom_in()
        self.root.update_idletasks()
        self.assertEqual(app._zoom_factor, 1.1)
        self.assertEqual(app._zoom_percent_label.cget("text"), "110%")
        self.assertTrue(bool(app._zoom_hud.place_info()))

        # 3. Zoom out returns to 100%
        app._zoom_out()
        self.root.update_idletasks()
        self.assertEqual(app._zoom_factor, 1.0)
        self.assertEqual(app._zoom_percent_label.cget("text"), "100%")

        # 4. Hide HUD hides the widget cleanly
        app._hide_zoom_hud()
        self.root.update_idletasks()
        self.assertFalse(bool(app._zoom_hud.place_info()))

        # 5. Boundary clamping
        app._apply_zoom(2.5, reveal_hud=True)
        self.assertEqual(app._zoom_factor, 1.8)
        self.assertEqual(app._zoom_percent_label.cget("text"), "180%")

        app._apply_zoom(0.2, reveal_hud=True)
        self.assertEqual(app._zoom_factor, 0.8)
        self.assertEqual(app._zoom_percent_label.cget("text"), "80%")

        # 6. Reset restores 100%
        app._zoom_reset()
        self.assertEqual(app._zoom_factor, 1.0)
        self.assertEqual(app._zoom_percent_label.cget("text"), "100%")

        # 7. Ctrl + MouseWheel event simulation
        class FakeWheelEvent:
            delta = 120
        app._on_global_ctrl_mousewheel(FakeWheelEvent())
        self.assertEqual(app._zoom_factor, 1.1)

        FakeWheelEvent.delta = -120
        app._on_global_ctrl_mousewheel(FakeWheelEvent())
        self.assertEqual(app._zoom_factor, 1.0)
        app._hide_zoom_hud()



if __name__ == "__main__":
    unittest.main()
