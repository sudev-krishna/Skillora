"""
Skillora Math Studio View (client/gui/views/math_studio_view.py)
Interactive SymPy Recurrence Solver and Dynamic Aptitude Practice with symbolic proofs.
Fully operational offline.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import customtkinter as ctk

from client.gui.app_window import BaseView
from client.gui.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_INDIGO,
    COLOR_ACCENT_INDIGO_HOVER,
    COLOR_ACCENT_LIGHT,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_CARD_HOVER,
    COLOR_DANGER,
    COLOR_DANGER_LIGHT,
    COLOR_SUCCESS,
    COLOR_SUCCESS_LIGHT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING,
    COLOR_WARNING_LIGHT,
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
    RADIUS_CARD,
    create_badge,
    create_button,
    create_card,
    create_entry,
)
from server.math_engine.aptitude_generator import generate_problem
from server.profiler.recurrence import solve_recurrence

logger = logging.getLogger("skillora.math_studio_view")

# Preset classic recurrence relations
RECURRENCE_TEMPLATES = {
    "Merge Sort: T(n) = 2*T(n/2) + n": ("T(n) = 2*T(n/2) + n", "T(1) = 1"),
    "Binary Search: T(n) = T(n/2) + 1": ("T(n) = T(n/2) + 1", "T(1) = 1"),
    "Strassen Matrix: T(n) = 7*T(n/2) + n^2": ("T(n) = 7*T(n/2) + n^2", "T(1) = 1"),
    "Karatsuba Mult: T(n) = 3*T(n/2) + n": ("T(n) = 3*T(n/2) + n", "T(1) = 1"),
    "Linear Recursion: T(n) = T(n-1) + n": ("T(n) = T(n-1) + n", "T(0) = 0"),
    "Tower of Hanoi: T(n) = 2*T(n-1) + 1": ("T(n) = 2*T(n-1) + 1", "T(1) = 1"),
}

APTITUDE_TOPICS = [
    ("Time, Work & Efficiency", "work"),
    ("Compound vs Simple Interest", "ci_si"),
    ("Probability & Combinatorics", "urn"),
    ("Graph Theory & Discrete Puzzles", "cayley"),
]


class MathStudioView(BaseView):
    """
    Math Studio Screen.
    Contains 2 tabs:
    1. Symbolic Recurrence Solver (SymPy rsolve & Master Theorem breakdown)
    2. Dynamic Aptitude Practice (Symbolic problem generator with verifiable step proofs)
    """

    def _build_ui(self) -> None:
        """Constructs tabview layout with Recurrence Solver and Aptitude Practice."""
        # Main Tabview
        self.tabview = ctk.CTkTabview(
            self,
            segmented_button_selected_color=COLOR_ACCENT_BLUE,
            segmented_button_selected_hover_color=COLOR_ACCENT_HOVER,
            corner_radius=RADIUS_CARD,
            fg_color=COLOR_BG,
        )
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_aptitude = self.tabview.add("🧮 Round 1: Aptitude Drills")
        self.tab_recurrence = self.tabview.add("⚡ Big-O & Recursion Master")

        self._build_aptitude_tab()
        self._build_recurrence_tab()

    # ==========================================================================
    # Tab 1: Symbolic Recurrence Solver
    # ==========================================================================
    def _build_recurrence_tab(self) -> None:
        """Constructs Tab 1: Recurrence Equation Solver."""
        scroll = ctk.CTkScrollableFrame(self.tab_recurrence, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # Controls Card
        ctrl_card = create_card(scroll)
        ctrl_card.pack(fill="x", pady=(0, 10))

        ctrl_inner = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        ctrl_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            ctrl_inner,
            text="⚡ Big-O & Algorithm Complexity Finder",
            font=FONT_TITLE,
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            ctrl_inner,
            text="Analyze how divide-and-conquer and recursive algorithms scale. Master Big-O notation for technical interviews.",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 10))

        # Preset Templates Dropdown
        tmpl_row = ctk.CTkFrame(ctrl_inner, fg_color="transparent")
        tmpl_row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(tmpl_row, text="Classic Algorithm Presets:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY, width=170, anchor="w").pack(side="left")
        tmpl_options = ["Select Algorithm Preset..."] + list(RECURRENCE_TEMPLATES.keys())
        self.tmpl_menu = ctk.CTkOptionMenu(
            tmpl_row,
            values=tmpl_options,
            command=self._on_template_selected,
            width=360,
            font=FONT_SMALL,
        )
        self.tmpl_menu.set(tmpl_options[0])
        self.tmpl_menu.pack(side="left")

        # Equation Input
        eq_row = ctk.CTkFrame(ctrl_inner, fg_color="transparent")
        eq_row.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(eq_row, text="Recurrence Relation T(n):", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY, width=170, anchor="w").pack(side="left")
        self.eq_entry = create_entry(eq_row, placeholder_text="e.g. T(n) = 2*T(n/2) + n", width=360)
        self.eq_entry.insert(0, "T(n) = 2*T(n/2) + n")
        self.eq_entry.pack(side="left")

        # Base Cases Input
        base_row = ctk.CTkFrame(ctrl_inner, fg_color="transparent")
        base_row.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(base_row, text="Base Cases / Conditions:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY, width=170, anchor="w").pack(side="left")
        self.base_entry = create_entry(base_row, placeholder_text="e.g. T(1) = 1, T(0) = 0", width=360)
        self.base_entry.insert(0, "T(1) = 1")
        self.base_entry.pack(side="left")

        # Solve Button
        btn_row = ctk.CTkFrame(ctrl_inner, fg_color="transparent")
        btn_row.pack(fill="x")

        self.solve_btn = create_button(
            btn_row,
            text="Analyze Time Complexity (Big-O)",
            variant="primary",
            command=self.solve_recurrence_action,
            height=36,
        )
        self.solve_btn.pack(side="left", padx=(170, 0))

        # Status / Execution info banner
        self.rec_status_label = ctk.CTkLabel(
            btn_row,
            text="Ready to solve.",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
        )
        self.rec_status_label.pack(side="left", padx=12)

        # Output Results Container
        self.rec_results_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self.rec_results_frame.pack(fill="both", expand=True)

        # Run initial solve for default Merge Sort
        self.solve_recurrence_action()

    def _on_template_selected(self, value: str) -> None:
        """Loads selected template into input fields."""
        if value in RECURRENCE_TEMPLATES:
            eq, base = RECURRENCE_TEMPLATES[value]
            self.eq_entry.delete(0, "end")
            self.eq_entry.insert(0, eq)
            self.base_entry.delete(0, "end")
            self.base_entry.insert(0, base)
            self.solve_recurrence_action()

    def solve_recurrence_action(self) -> None:
        """Solves recurrence relation using offline profiler engine."""
        eq_str = self.eq_entry.get().strip()
        base_str = self.base_entry.get().strip()

        if not eq_str:
            self.rec_status_label.configure(text="Please specify a recurrence equation.", text_color=COLOR_DANGER)
            return

        # Parse base cases
        base_dict: Dict[str, Any] = {}
        if base_str:
            parts = [p.strip() for p in base_str.replace(";", ",").split(",") if p.strip()]
            for part in parts:
                if "=" in part:
                    k, v = part.split("=", 1)
                elif ":" in part:
                    k, v = part.split(":", 1)
                else:
                    continue
                try:
                    base_dict[k.strip()] = int(v.strip())
                except ValueError:
                    try:
                        base_dict[k.strip()] = float(v.strip())
                    except ValueError:
                        base_dict[k.strip()] = v.strip()

        t0 = time.perf_counter()
        self.rec_status_label.configure(text="Solving recurrence...", text_color=COLOR_TEXT_SECONDARY)
        try:
            result = solve_recurrence(eq_str, base_dict)
            elapsed = time.perf_counter() - t0
            self._render_recurrence_results(result, elapsed)
            self.rec_status_label.configure(text=f"Solved in {elapsed*1000:.1f} ms", text_color=COLOR_SUCCESS)
        except Exception as ex:
            logger.exception("Recurrence solver error: %s", ex)
            self.rec_status_label.configure(text=f"Solver error: {ex}", text_color=COLOR_DANGER)

    @staticmethod
    def _get_big_o_interview_insight(big_o_str: str) -> Tuple[str, str]:
        """Provides concise interview-oriented takeaway for Big-O notation."""
        bo = big_o_str.replace(" ", "").lower()
        if "o(1)" in bo:
            return "⚡ Constant Time • Instant lookup", "Optimal speed: Execution time stays constant regardless of dataset size."
        elif "o(logn)" in bo:
            return "🚀 Logarithmic Time • Halving Divide & Conquer", "Interview Gold Standard: Scales to billions of items with minimal operations."
        elif "o(nlogn)" in bo:
            return "⚡ Linearithmic Time • Optimal Sorting Bound", "Target for Sorting: Achieved by Merge Sort & Heap Sort without nested quadratic slowdown."
        elif "o(n)" in bo:
            return "✅ Linear Time • Direct Single Pass", "Standard Pass: Traverses the input once; ideal for array scans and two-pointer solutions."
        elif "o(n^2)" in bo or "o(n**2)" in bo:
            return "⚠️ Quadratic Time • Nested Loops", "Interview Warning: Acceptable for small inputs, but often triggers TLE for N > 10,000."
        elif "o(2^n)" in bo or "o(2**n)" in bo or "o(n!)" in bo:
            return "❌ Exponential / Factorial Time", "Critical Bottleneck: Naive recursion. Expect to optimize via Dynamic Programming or Memoization."
        return "Algorithm Complexity", "Standard technical interview scaling profile."

    @staticmethod
    def _get_pedagogical_explanation(result: dict, big_o: str) -> str:
        """Returns plain-English explanation of why this algorithm scales this way."""
        mt = result.get("master_theorem")
        if mt and isinstance(mt, dict):
            case = mt.get("case", 2)
            if case == 2:
                return (
                    "Why this complexity? At each recursive step, the input is split into equal subproblems. "
                    "The work performed at each level is balanced evenly with the division cost across log₂(N) levels, "
                    f"yielding a tight asymptotic bound of {big_o}."
                )
            elif case == 1:
                return (
                    "Why this complexity? The number of recursive subproblems grows faster than the work done to combine them. "
                    f"Hence, the computation is dominated by the leaf nodes (base cases), resulting in {big_o}."
                )
            elif case == 3:
                return (
                    "Why this complexity? The work performed at the root (top-level division/combination) dominates "
                    f"the subproblems at deeper levels, resulting in {big_o}."
                )
        return (
            f"The algorithm scales proportionally to {big_o}. "
            "In technical rounds, explain the depth of the recursion tree multiplied by the work per level."
        )

    def _render_recurrence_results(self, result: dict, elapsed: float) -> None:
        """Renders Big-O card, Closed-form card, and Master Theorem card."""
        for widget in self.rec_results_frame.winfo_children():
            widget.destroy()

        if result.get("error"):
            err_card = create_card(self.rec_results_frame, fg_color=COLOR_DANGER_LIGHT)
            err_card.pack(fill="x", pady=6)
            ctk.CTkLabel(
                err_card,
                text=f"Analysis unsuccessful: {result.get('error')}",
                font=FONT_BODY_BOLD,
                text_color=COLOR_DANGER,
            ).pack(padx=16, pady=12)
            return

        # 1. Big-O Badge Card (Interview Focus)
        big_o = result.get("big_o", "Unknown")
        big_o_card = create_card(self.rec_results_frame, fg_color=COLOR_ACCENT_LIGHT)
        big_o_card.pack(fill="x", pady=4)

        bo_inner = ctk.CTkFrame(big_o_card, fg_color="transparent")
        bo_inner.pack(fill="x", padx=16, pady=12)

        bo_row = ctk.CTkFrame(bo_inner, fg_color="transparent")
        bo_row.pack(fill="x")

        ctk.CTkLabel(bo_row, text="Interview Time Complexity:", font=FONT_HEADING, text_color=COLOR_TEXT_SECONDARY).pack(side="left", anchor="w")
        create_badge(bo_row, text=f"Solved in {elapsed*1000:.1f} ms", variant="info").pack(side="right")

        ctk.CTkLabel(bo_inner, text=big_o, font=(FONT_DISPLAY[0], 28, "bold"), text_color=COLOR_ACCENT_INDIGO).pack(anchor="w", pady=(2, 4))

        badge_txt, advice_txt = self._get_big_o_interview_insight(big_o)
        create_badge(bo_inner, text=badge_txt, variant="indigo").pack(anchor="w", pady=(2, 4))
        ctk.CTkLabel(bo_inner, text=advice_txt, font=FONT_BODY, text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")

        # 2. Closed-Form & Interview Intuition Card
        closed_form = result.get("closed_form", "N/A")
        cf_card = create_card(self.rec_results_frame)
        cf_card.pack(fill="x", pady=4)

        cf_inner = ctk.CTkFrame(cf_card, fg_color="transparent")
        cf_inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(cf_inner, text="💡 Interview Answer Guide: Why this complexity?", font=FONT_HEADING, text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")

        why_text = self._get_pedagogical_explanation(result, big_o)
        ctk.CTkLabel(cf_inner, text=why_text, font=FONT_BODY, text_color=COLOR_TEXT_PRIMARY, wraplength=720, justify="left").pack(anchor="w", pady=(4, 8))

        # Collapsible / nested formal proof drawer
        proof_box = ctk.CTkFrame(cf_inner, fg_color=COLOR_BG, corner_radius=6, border_width=1, border_color=COLOR_BORDER)
        proof_box.pack(fill="x", pady=(4, 0))

        pb_in = ctk.CTkFrame(proof_box, fg_color="transparent")
        pb_in.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(pb_in, text="📐 Formal Derivation Details (SymPy):", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        ctk.CTkLabel(pb_in, text=f"Exact Closed-Form Solution: T(n) = {closed_form}", font=FONT_CODE_BOLD, text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", pady=(2, 0))

        method_text = result.get("method", "SymPy Symbolic Engine")
        ctk.CTkLabel(pb_in, text=f"Method: {method_text}", font=FONT_SMALL, text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")

        # 3. Master Theorem Breakdown Card (if applicable)
        mt_data = result.get("master_theorem")
        if mt_data and isinstance(mt_data, dict):
            mt_card = create_card(self.rec_results_frame)
            mt_card.pack(fill="x", pady=4)

            mt_inner = ctk.CTkFrame(mt_card, fg_color="transparent")
            mt_inner.pack(fill="x", padx=16, pady=12)

            ctk.CTkLabel(mt_inner, text="Master Theorem Analysis:", font=FONT_HEADING, text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")

            case_num = mt_data.get("case", 2)
            c_crit = mt_data.get("c_crit", 1.0)
            expl = mt_data.get("explanation", "")

            param_text = f"Master Theorem Case: {case_num}  |  Critical Exponent c_crit = {c_crit:.3f}"
            create_badge(mt_inner, text=param_text, variant="indigo").pack(anchor="w", pady=(4, 4))

            ctk.CTkLabel(mt_inner, text=expl, font=FONT_BODY, text_color=COLOR_TEXT_PRIMARY, wraplength=700, justify="left").pack(anchor="w", pady=(2, 0))

    # ==========================================================================
    # Tab 2: Dynamic Aptitude Practice
    # ==========================================================================
    def _build_aptitude_tab(self) -> None:
        """Constructs Tab 2: Dynamic Quantitative Aptitude Practice."""
        scroll = ctk.CTkScrollableFrame(self.tab_aptitude, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # Controls Card
        ctrl_card = create_card(scroll)
        ctrl_card.pack(fill="x", pady=(0, 10))

        ctrl_inner = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        ctrl_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            ctrl_inner,
            text="🧮 Round 1: Campus Placement Aptitude Practice",
            font=FONT_TITLE,
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            ctrl_inner,
            text="Master quantitative aptitude questions commonly asked in company screening rounds (TCS, Infosys, Wipro, Cognizant, Amazon OA).",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 10))

        # Topic & Difficulty Selectors Row
        row = ctk.CTkFrame(ctrl_inner, fg_color="transparent")
        row.pack(fill="x")

        ctk.CTkLabel(row, text="Domain:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self.apt_topic_menu = ctk.CTkOptionMenu(
            row,
            values=[t[0] for t in APTITUDE_TOPICS],
            width=260,
            font=FONT_SMALL,
        )
        self.apt_topic_menu.set(APTITUDE_TOPICS[0][0])
        self.apt_topic_menu.pack(side="left", padx=(0, 14))

        ctk.CTkLabel(row, text="Difficulty:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self.apt_diff_menu = ctk.CTkOptionMenu(
            row,
            values=["Easy", "Medium", "Hard"],
            width=100,
            font=FONT_SMALL,
        )
        self.apt_diff_menu.set("Medium")
        self.apt_diff_menu.pack(side="left", padx=(0, 14))

        self.gen_btn = create_button(
            row,
            text="Generate Practice Problem",
            variant="secondary",
            command=self.generate_problem_action,
            height=34,
        )
        self.gen_btn.pack(side="left")

        # Question Presentation Card
        self.q_card = create_card(scroll)
        self.q_card.pack(fill="x", pady=(0, 10))

        q_inner = ctk.CTkFrame(self.q_card, fg_color="transparent")
        q_inner.pack(fill="x", padx=16, pady=14)

        q_h = ctk.CTkFrame(q_inner, fg_color="transparent")
        q_h.pack(fill="x", pady=(0, 8))

        self.q_topic_badge = create_badge(q_h, text="Time & Work", variant="indigo")
        self.q_topic_badge.pack(side="left", padx=(0, 8))

        self.q_diff_badge = create_badge(q_h, text="Medium", variant="warning")
        self.q_diff_badge.pack(side="left")

        self.q_text_label = ctk.CTkLabel(
            q_inner,
            text="Click 'Generate Dynamic Problem' to load a quantitative question.",
            font=FONT_BODY,
            text_color=COLOR_TEXT_PRIMARY,
            wraplength=760,
            justify="left",
            anchor="w",
        )
        self.q_text_label.pack(fill="x", pady=(4, 12))

        # 4 Radio Button Options
        self.radio_var = ctk.IntVar(value=-1)
        self.radio_buttons: List[ctk.CTkRadioButton] = []
        self.options_frame = ctk.CTkFrame(q_inner, fg_color="transparent")
        self.options_frame.pack(fill="x", pady=(0, 10))

        for opt_idx in range(4):
            opt_letter = chr(ord("A") + opt_idx)
            rb = ctk.CTkRadioButton(
                self.options_frame,
                text=f"Option {opt_letter}: --",
                variable=self.radio_var,
                value=opt_idx,
                font=FONT_BODY,
                text_color=COLOR_TEXT_PRIMARY,
            )
            rb.pack(fill="x", pady=3)
            self.radio_buttons.append(rb)

        # Verification Button Row
        verify_row = ctk.CTkFrame(q_inner, fg_color="transparent")
        verify_row.pack(fill="x", pady=(6, 0))

        self.verify_btn = create_button(
            verify_row,
            text="Verify Answer & Reveal Steps",
            variant="primary",
            command=self.verify_answer_action,
            height=34,
        )
        self.verify_btn.pack(side="left")

        self.verify_status_label = ctk.CTkLabel(
            verify_row,
            text="",
            font=FONT_BODY_BOLD,
        )
        self.verify_status_label.pack(side="left", padx=12)

        # Proof Accordion Container
        self.proof_container = ctk.CTkFrame(scroll, fg_color="transparent")
        self.proof_container.pack(fill="both", expand=True)

        self._current_problem: Optional[dict] = None

        # Load initial problem
        self.generate_problem_action()

    def generate_problem_action(self) -> None:
        """Generates dynamic problem using offline aptitude generator."""
        chosen_topic_name = self.apt_topic_menu.get()
        topic_key = "work"
        for name, key in APTITUDE_TOPICS:
            if name == chosen_topic_name:
                topic_key = key
                break
        else:
            lower = chosen_topic_name.lower()
            if "work" in lower:
                topic_key = "work"
            elif "interest" in lower or "ci" in lower or "si" in lower:
                topic_key = "ci_si"
            elif "urn" in lower or "probab" in lower:
                topic_key = "urn"
            elif "cayley" in lower or "tree" in lower or "graph" in lower:
                topic_key = "cayley"

        difficulty = self.apt_diff_menu.get().lower()

        try:
            problem = generate_problem(topic=topic_key, difficulty=difficulty)
            self._current_problem = problem
            self._display_problem(problem)
        except Exception as ex:
            logger.exception("Error generating problem: %s", ex)
            self.verify_status_label.configure(text=f"Error generating problem: {ex}", text_color=COLOR_DANGER)

    def _display_problem(self, problem: dict) -> None:
        """Populates question card with problem data and resets option selection."""
        self.q_topic_badge.configure(text=problem.get("topic_display", "Aptitude"))
        self.q_diff_badge.configure(text=problem.get("difficulty", "Medium").capitalize())
        self.q_text_label.configure(text=problem.get("question_text", ""))

        options = problem.get("options", ["A", "B", "C", "D"])
        for idx, rb in enumerate(self.radio_buttons):
            if idx < len(options):
                opt_letter = chr(ord("A") + idx)
                rb.configure(text=f"Option {opt_letter}: {options[idx]}", state="normal")
            else:
                rb.configure(text="--", state="disabled")

        self.radio_var.set(-1)
        self.verify_status_label.configure(text="")

        # Clear proof container
        for widget in self.proof_container.winfo_children():
            widget.destroy()

    def verify_answer_action(self) -> None:
        """Verifies selected option and displays step-by-step symbolic proof."""
        if not self._current_problem:
            return

        selected_idx = self.radio_var.get()
        if selected_idx < 0:
            self.verify_status_label.configure(text="Please select an option first.", text_color=COLOR_WARNING)
            return

        correct_idx = self._current_problem.get("correct_option_index", 0)
        correct_label = self._current_problem.get("correct_option_label", "A")

        is_correct = (selected_idx == correct_idx)

        # Clear proof container
        for widget in self.proof_container.winfo_children():
            widget.destroy()

        proof_card = create_card(self.proof_container)
        proof_card.pack(fill="both", expand=True, pady=6)

        p_inner = ctk.CTkFrame(proof_card, fg_color="transparent")
        p_inner.pack(fill="both", expand=True, padx=16, pady=14)

        if is_correct:
            self.verify_status_label.configure(text="✓ Correct! Matches exact symbolic derivation.", text_color=COLOR_SUCCESS)
            banner = ctk.CTkFrame(p_inner, fg_color=COLOR_SUCCESS_LIGHT, corner_radius=6)
            banner.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(
                banner,
                text=f"✓ Excellent! Option {correct_label} is mathematically correct.",
                font=FONT_BODY_BOLD,
                text_color=COLOR_SUCCESS,
            ).pack(padx=12, pady=8)
        else:
            self.verify_status_label.configure(text=f"✗ Incorrect. Correct answer is Option {correct_label}.", text_color=COLOR_DANGER)
            banner = ctk.CTkFrame(p_inner, fg_color=COLOR_DANGER_LIGHT, corner_radius=6)
            banner.pack(fill="x", pady=(0, 10))

            # Look up misconception
            options = self._current_problem.get("options", [])
            chosen_val = options[selected_idx] if selected_idx < len(options) else ""
            misconceptions = self._current_problem.get("misconception_map", {})
            diag_text = misconceptions.get(str(chosen_val), "Candidate selected non-optimal approximation.")

            ctk.CTkLabel(
                banner,
                text=f"✗ Misconception Detected: {diag_text}",
                font=FONT_BODY_BOLD,
                text_color=COLOR_DANGER,
                wraplength=700,
                justify="left",
            ).pack(padx=12, pady=8)

        # Step-by-Step Proof Breakdown
        ctk.CTkLabel(
            p_inner,
            text="Verifiable Step-by-Step Symbolic Proof:",
            font=FONT_HEADING,
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(anchor="w", pady=(4, 6))

        proof_steps = self._current_problem.get("proof_steps", [])
        if proof_steps:
            for step in proof_steps:
                s_box = ctk.CTkFrame(p_inner, fg_color=COLOR_BG, corner_radius=6, border_width=1, border_color=COLOR_BORDER)
                s_box.pack(fill="x", pady=3)

                s_content = ctk.CTkFrame(s_box, fg_color="transparent")
                s_content.pack(fill="x", padx=10, pady=8)

                step_num = step.get("step", 1)
                step_title = step.get("title", f"Step {step_num}")
                step_desc = step.get("explanation", "")
                step_math = step.get("formula", "")

                ctk.CTkLabel(
                    s_content,
                    text=f"Step {step_num}: {step_title}",
                    font=FONT_SMALL_BOLD,
                    text_color=COLOR_ACCENT_BLUE,
                ).pack(anchor="w")

                if step_desc:
                    ctk.CTkLabel(
                        s_content,
                        text=step_desc,
                        font=FONT_SMALL,
                        text_color=COLOR_TEXT_PRIMARY,
                        wraplength=720,
                        justify="left",
                    ).pack(anchor="w", pady=(1, 2))

                if step_math:
                    ctk.CTkLabel(
                        s_content,
                        text=f"Formula: {step_math}",
                        font=FONT_CODE_BOLD,
                        text_color=COLOR_ACCENT_INDIGO,
                    ).pack(anchor="w")
        else:
            text_proof = self._current_problem.get("text_proof", "Proof derivation generated via SymPy.")
            ctk.CTkLabel(
                p_inner,
                text=text_proof,
                font=FONT_BODY,
                text_color=COLOR_TEXT_PRIMARY,
                wraplength=720,
                justify="left",
            ).pack(anchor="w")
