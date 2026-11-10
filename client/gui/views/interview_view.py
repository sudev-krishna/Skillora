"""
Skillora Mock Interview Console View (client/gui/views/interview_view.py)
Interactive 3-tier offline interview scoring engine (keywords, lexical structure, AST syntax).
Supports question categories across 6 domains, question selection, dual explanation/code panes,
scorecards, and model answer accordion. Fully operational offline.
"""

import logging
import random
from typing import Any, Dict, List, Optional
import customtkinter as ctk

from client.gui.app_window import BaseView
from client.gui.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_INDIGO,
    COLOR_ACCENT_LIGHT,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_CARD_HOVER,
    COLOR_DANGER,
    COLOR_DANGER_BORDER,
    COLOR_DANGER_LIGHT,
    COLOR_SUCCESS,
    COLOR_SUCCESS_BORDER,
    COLOR_SUCCESS_LIGHT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING,
    COLOR_WARNING_BORDER,
    COLOR_WARNING_LIGHT,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CODE,
    FONT_CODE_BOLD,
    FONT_DISPLAY,
    FONT_HEADING,
    FONT_SMALL,
    FONT_SMALL_BOLD,
    FONT_TITLE,
    RADIUS_CARD,
    create_badge,
    create_button,
    create_card,
)
from server.bot.evaluator import evaluate_answer
from server.db.seed_data import QUESTIONS_SEED_DATA

logger = logging.getLogger("skillora.interview_view")

CATEGORY_MAP = {
    "All Domains": None,
    "DSA Coding": "Coding",
    "System Design": "SystemDesign",
    "Operating Systems": "OS",
    "DBMS & SQL": "DBMS",
    "Computer Networks": "CN",
    "Python Core": "Python",
}


class InterviewView(BaseView):
    """
    Mock Interview Console Screen.
    Presents interview questions, captures conceptual answers and code,
    and runs local 3-tier heuristic evaluation (keywords, lexical structure, AST syntax).
    """

    def _build_ui(self) -> None:
        """Constructs scrollable interview layout."""
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=8, pady=8)

        # 1. Top Controls Card (Domain, Difficulty, Question Selector)
        self._build_controls_card()

        # 2. Question Presentation Card
        self._build_question_card()

        # 3. Dual Input Response Panes (Explanation & Python Code)
        self._build_input_panes()

        # 4. Action Row (Submit, Clear, Load Sample)
        self._build_action_row()

        # 5. Scorecard & Feedback Container (Dynamic)
        self.scorecard_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.scorecard_container.pack(fill="both", expand=True, pady=(8, 0))

        # Filtered questions cache
        self._filtered_questions: List[dict] = []
        self._current_question: Optional[dict] = None

        # Initial populate
        self._apply_question_filters()

    def _build_controls_card(self) -> None:
        """Constructs category and difficulty dropdowns and randomize button."""
        ctrl_card = create_card(self.scroll)
        ctrl_card.pack(fill="x", pady=(0, 10))

        inner = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            inner,
            text="🎯 Round 3: Technical & HR Mock Interview",
            font=FONT_TITLE,
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            inner,
            text="Simulate technical interview rounds with immediate evaluation of your conceptual explanation, communication structure, and code correctness.",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 8))

        # Row 1: Domain & Difficulty Filter
        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(row1, text="Category:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=(0, 4))
        self.category_menu = ctk.CTkOptionMenu(
            row1,
            values=list(CATEGORY_MAP.keys()),
            command=lambda val: self._apply_question_filters(),
            width=160,
            font=FONT_SMALL,
        )
        self.category_menu.set("All Domains")
        self.category_menu.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(row1, text="Difficulty:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=(0, 4))
        self.diff_menu = ctk.CTkOptionMenu(
            row1,
            values=["All", "Easy", "Medium", "Hard"],
            command=lambda val: self._apply_question_filters(),
            width=100,
            font=FONT_SMALL,
        )
        self.diff_menu.set("All")
        self.diff_menu.pack(side="left", padx=(0, 12))

        rand_btn = create_button(
            row1,
            text="🎲 Random Question",
            variant="secondary",
            height=28,
            command=self._on_random_question_clicked,
        )
        rand_btn.pack(side="right")

        # Row 2: Question Selector Dropdown
        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x")

        ctk.CTkLabel(row2, text="Question:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY, width=65, anchor="w").pack(side="left")
        self.question_menu = ctk.CTkOptionMenu(
            row2,
            values=["Loading questions..."],
            command=self._on_question_selected,
            font=FONT_SMALL,
        )
        self.question_menu.pack(side="left", fill="x", expand=True)

    def _build_question_card(self) -> None:
        """Constructs prompt display card."""
        self.q_card = create_card(self.scroll)
        self.q_card.pack(fill="x", pady=(0, 10))

        inner = ctk.CTkFrame(self.q_card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        # Header: Topic & Badges
        h_row = ctk.CTkFrame(inner, fg_color="transparent")
        h_row.pack(fill="x", pady=(0, 6))

        self.q_title_label = ctk.CTkLabel(
            h_row,
            text="Question Topic",
            font=FONT_TITLE,
            text_color=COLOR_TEXT_PRIMARY,
        )
        self.q_title_label.pack(side="left", padx=(0, 8))

        self.q_cat_badge = create_badge(h_row, text="Coding", variant="indigo")
        self.q_cat_badge.pack(side="left", padx=(0, 6))

        self.q_diff_badge = create_badge(h_row, text="Medium", variant="warning")
        self.q_diff_badge.pack(side="left")

        # Question Prompt
        self.q_prompt_label = ctk.CTkLabel(
            inner,
            text="Select an interview question above to begin.",
            font=FONT_BODY,
            text_color=COLOR_TEXT_PRIMARY,
            wraplength=760,
            justify="left",
            anchor="w",
        )
        self.q_prompt_label.pack(fill="x", pady=(4, 6))

        # Expected Concepts Hint
        self.q_hint_label = ctk.CTkLabel(
            inner,
            text="Key concepts hint: --",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
            wraplength=760,
            justify="left",
        )
        self.q_hint_label.pack(fill="x")

    def _build_input_panes(self) -> None:
        """Constructs dual response inputs: Conceptual Explanation & Python Code."""
        input_card = create_card(self.scroll)
        input_card.pack(fill="both", expand=True, pady=(0, 10))

        inner = ctk.CTkFrame(input_card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        # Tabview for Explanation & Code
        self.input_tabview = ctk.CTkTabview(
            inner,
            segmented_button_selected_color=COLOR_ACCENT_BLUE,
            segmented_button_selected_hover_color=COLOR_ACCENT_HOVER,
            corner_radius=8,
            fg_color=COLOR_CARD,
            height=260,
        )
        self.input_tabview.pack(fill="both", expand=True)

        tab_expl = self.input_tabview.add("1. Conceptual & Algorithmic Explanation (Keywords & Lexical)")
        tab_code = self.input_tabview.add("2. Python Code Implementation (AST Static Syntax Inspection)")

        # Explanation Textbox
        ctk.CTkLabel(
            tab_expl,
            text="Explain the conceptual solution, pointer manipulation / state design, edge cases, and time/space complexity:",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x", pady=(2, 4))

        self.expl_textbox = ctk.CTkTextbox(
            tab_expl,
            font=FONT_BODY,
            fg_color=COLOR_BG,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            wrap="word",
            height=180,
        )
        self.expl_textbox.pack(fill="both", expand=True)

        # Code Textbox
        ctk.CTkLabel(
            tab_code,
            text="Implement the Python function (evaluated against AST node syntax and anti-pattern rules):",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x", pady=(2, 4))

        self.code_textbox = ctk.CTkTextbox(
            tab_code,
            font=FONT_CODE,
            fg_color=COLOR_BG,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=6,
            wrap="none",
            height=180,
        )
        self.code_textbox.pack(fill="both", expand=True)

    def _build_action_row(self) -> None:
        """Constructs action buttons: Submit, Clear, Load Sample."""
        action_card = create_card(self.scroll)
        action_card.pack(fill="x", pady=(0, 10))

        inner = ctk.CTkFrame(action_card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)

        self.submit_btn = create_button(
            inner,
            text="✓ Submit for Automated Evaluation",
            variant="primary",
            command=self.submit_evaluation_action,
            height=36,
        )
        self.submit_btn.pack(side="left", padx=(0, 10))

        sample_btn = create_button(
            inner,
            text="Load Sample Good Answer",
            variant="secondary",
            command=self._load_sample_answer,
            height=36,
        )
        sample_btn.pack(side="left", padx=(0, 10))

        clear_btn = create_button(
            inner,
            text="Clear",
            variant="outline",
            command=self._clear_inputs,
            height=36,
        )
        clear_btn.pack(side="left", padx=(0, 12))

        self.eval_status_label = ctk.CTkLabel(
            inner,
            text="Ready. 100% offline rule-based scoring engine.",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
        )
        self.eval_status_label.pack(side="left")

    def _apply_question_filters(self) -> None:
        """Filters question bank and updates dropdown."""
        cat_choice = self.category_menu.get()
        target_cat = CATEGORY_MAP.get(cat_choice)
        diff_choice = self.diff_menu.get()

        prefix_map = {
            "OS": "OS:",
            "DBMS": "DBMS:",
            "CN": "CN:",
            "Python": "Python:",
            "SystemDesign": "System Design:",
            "Coding": "DSA:",
        }
        topic_prefix = prefix_map.get(target_cat) if target_cat else None

        matched = []
        for q in QUESTIONS_SEED_DATA:
            if target_cat:
                cat_match = (q.get("category") == target_cat)
                topic_match = bool(topic_prefix and (topic_prefix.lower() in q.get("topic", "").lower()))
                if not (cat_match or topic_match):
                    continue
            if diff_choice != "All" and q.get("difficulty") != diff_choice:
                continue
            matched.append(q)

        self._filtered_questions = matched
        if matched:
            display_options = [f"[{q.get('category')}] {q.get('topic')}" for q in matched]
            self.question_menu.configure(values=display_options)
            self.question_menu.set(display_options[0])
            self._display_question(matched[0])
        else:
            self.question_menu.configure(values=["No questions matching filter"])
            self.question_menu.set("No questions matching filter")

    def _on_question_selected(self, value: str) -> None:
        """Handles user selecting a question from dropdown."""
        for q in self._filtered_questions:
            opt_title = f"[{q.get('category')}] {q.get('topic')}"
            if opt_title == value:
                self._display_question(q)
                break

    def _on_random_question_clicked(self) -> None:
        """Picks a random question from the current filtered set."""
        if self._filtered_questions:
            q = random.choice(self._filtered_questions)
            opt_title = f"[{q.get('category')}] {q.get('topic')}"
            self.question_menu.set(opt_title)
            self._display_question(q)

    def _display_question(self, q: dict) -> None:
        """Updates presentation card with question data."""
        self._current_question = q
        self.q_title_label.configure(text=q.get("topic", "Question Topic"))
        self.q_cat_badge.configure(text=f" {q.get('category', 'General')} ")
        self.q_diff_badge.configure(text=f" {q.get('difficulty', 'Medium')} ")
        self.q_prompt_label.configure(text=q.get("question_text", ""))

        keywords = q.get("expected_keywords_csv", "")
        if keywords:
            kw_clean = ", ".join(k.strip() for k in keywords.split(",") if k.strip())
            self.q_hint_label.configure(text=f"Key technical concepts expected: {kw_clean}")
        else:
            self.q_hint_label.configure(text="")

        self._clear_inputs()
        # Clear previous scorecard
        for widget in self.scorecard_container.winfo_children():
            widget.destroy()

    def _clear_inputs(self) -> None:
        """Clears textboxes."""
        self.expl_textbox.delete("1.0", "end")
        self.code_textbox.delete("1.0", "end")
        self.eval_status_label.configure(text="Inputs cleared.", text_color=COLOR_TEXT_SECONDARY)

    def _load_sample_answer(self) -> None:
        """Populates textboxes with a high-quality sample answer for testing."""
        if not self._current_question:
            return

        kw = self._current_question.get("expected_keywords_csv", "")
        kw_list = [k.strip() for k in kw.split(",") if k.strip()]
        kw_snippet = ", ".join(kw_list[:5]) if kw_list else "in-place, optimal, time complexity"

        sample_expl = (
            f"To solve this problem, we use an optimal approach capturing {kw_snippet}. "
            "We handle edge cases such as null inputs and single elements gracefully. "
            "The time complexity is O(n) and auxiliary space complexity is O(1) in-place without recursion overhead."
        )
        self.expl_textbox.delete("1.0", "end")
        self.expl_textbox.insert("1.0", sample_expl)

        # Code snippet
        sol = self._current_question.get("symbolic_solution", "")
        if "def " in sol:
            code_part = sol
            if "```python" in code_part:
                code_part = code_part.split("```python")[-1].split("```")[0].strip()
            self.code_textbox.delete("1.0", "end")
            self.code_textbox.insert("1.0", code_part)
        else:
            default_code = "def solution(head):\n    # Optimal implementation\n    return head\n"
            self.code_textbox.delete("1.0", "end")
            self.code_textbox.insert("1.0", default_code)

        self.eval_status_label.configure(text="Sample answer loaded. Ready to submit.", text_color=COLOR_ACCENT_BLUE)

    def submit_evaluation_action(self) -> None:
        """Executes 3-tier offline evaluation on candidate answer."""
        if not self._current_question:
            self.eval_status_label.configure(text="No active question selected.", text_color=COLOR_WARNING)
            return

        student_answer = self.expl_textbox.get("1.0", "end").strip()
        code_snippet = self.code_textbox.get("1.0", "end").strip()

        if not student_answer and not code_snippet:
            self.eval_status_label.configure(text="Please provide an explanation or code snippet.", text_color=COLOR_WARNING)
            return

        self.eval_status_label.configure(text="Evaluating answer with offline rule engine...", text_color=COLOR_ACCENT_BLUE)

        try:
            eval_result = evaluate_answer(self._current_question, student_answer, code_snippet)
            self._render_scorecard(eval_result)
            self.eval_status_label.configure(text="Evaluation complete.", text_color=COLOR_SUCCESS)
        except Exception as ex:
            logger.exception("Error evaluating answer: %s", ex)
            self.eval_status_label.configure(text=f"Evaluation error: {ex}", text_color=COLOR_DANGER)

    def _render_scorecard(self, res: dict) -> None:
        """Renders 3-tier breakdown cards, overall score, strengths, gaps, and model answer."""
        for widget in self.scorecard_container.winfo_children():
            widget.destroy()

        # 1. Overall Composite Score Card
        overall_card = create_card(self.scorecard_container)
        overall_card.pack(fill="x", pady=(0, 8))

        o_inner = ctk.CTkFrame(overall_card, fg_color="transparent")
        o_inner.pack(fill="x", padx=16, pady=12)

        tot_score = float(res.get("total_score", 0.0))
        kw_score = float(res.get("keyword_score", 0.0))
        struct_score = float(res.get("structure_score", 0.0))
        ast_score = float(res.get("ast_score", 0.0))

        score_col = COLOR_SUCCESS if tot_score >= 75.0 else (COLOR_WARNING if tot_score >= 50.0 else COLOR_DANGER)

        h_row = ctk.CTkFrame(o_inner, fg_color="transparent")
        h_row.pack(fill="x")

        left_s = ctk.CTkFrame(h_row, fg_color="transparent")
        left_s.pack(side="left")

        ctk.CTkLabel(left_s, text="Interview Evaluation Score:", font=FONT_TITLE, text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(left_s, text=f"{tot_score:.1f} / 100", font=(FONT_DISPLAY[0], 28, "bold"), text_color=score_col).pack(anchor="w")

        rating_text = "Target Tier 1 Achieved (Ready for Product Drives)" if tot_score >= 75.0 else ("Tier 2 Specialist Benchmark Met" if tot_score >= 60.0 else "Needs Additional Preparation")
        badge_variant = "success" if tot_score >= 75.0 else ("warning" if tot_score >= 60.0 else "danger")
        create_badge(h_row, text=rating_text, variant=badge_variant).pack(side="right")

        # 2. 3-Tier Score Breakdown Grid (3 Columns)
        tiers_grid = ctk.CTkFrame(self.scorecard_container, fg_color="transparent")
        tiers_grid.pack(fill="x", pady=(0, 8))
        tiers_grid.grid_columnconfigure(0, weight=1)
        tiers_grid.grid_columnconfigure(1, weight=1)
        tiers_grid.grid_columnconfigure(2, weight=1)

        # Tier 1 Card (Keywords 50%)
        t1_card = create_card(tiers_grid)
        t1_card.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        t1_in = ctk.CTkFrame(t1_card, fg_color="transparent")
        t1_in.pack(fill="both", expand=True, padx=12, pady=10)
        ctk.CTkLabel(t1_in, text="Pillar 1: Key Concepts (50%)", font=FONT_HEADING, text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        ctk.CTkLabel(t1_in, text=f"{kw_score:.1f}%", font=FONT_DISPLAY, text_color=COLOR_ACCENT_BLUE).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(t1_in, text="Domain Concept Coverage", font=FONT_SMALL, text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")

        # Tier 2 Card (Structure 20%)
        t2_card = create_card(tiers_grid)
        t2_card.grid(row=0, column=1, sticky="nsew", padx=4)
        t2_in = ctk.CTkFrame(t2_card, fg_color="transparent")
        t2_in.pack(fill="both", expand=True, padx=12, pady=10)
        ctk.CTkLabel(t2_in, text="Pillar 2: Articulation (20%)", font=FONT_HEADING, text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        ctk.CTkLabel(t2_in, text=f"{struct_score:.1f}%", font=FONT_DISPLAY, text_color=COLOR_ACCENT_BLUE).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(t2_in, text="Clarity & Explanation Depth", font=FONT_SMALL, text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")

        # Tier 3 Card (AST 30%)
        t3_card = create_card(tiers_grid)
        t3_card.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        t3_in = ctk.CTkFrame(t3_card, fg_color="transparent")
        t3_in.pack(fill="both", expand=True, padx=12, pady=10)
        ctk.CTkLabel(t3_in, text="Pillar 3: Code Logic (30%)", font=FONT_HEADING, text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        ctk.CTkLabel(t3_in, text=f"{ast_score:.1f}%", font=FONT_DISPLAY, text_color=COLOR_ACCENT_INDIGO).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(t3_in, text="Syntax Accuracy & Structure", font=FONT_SMALL, text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")

        # 3. Strengths Card
        strengths = res.get("strengths", [])
        if strengths:
            str_card = create_card(self.scorecard_container)
            str_card.pack(fill="x", pady=(0, 6))
            str_in = ctk.CTkFrame(str_card, fg_color="transparent")
            str_in.pack(fill="x", padx=14, pady=10)
            ctk.CTkLabel(str_in, text="✓ Strong Interview Points Demonstrated:", font=FONT_HEADING, text_color=COLOR_SUCCESS).pack(anchor="w", pady=(0, 4))
            for item in strengths:
                ctk.CTkLabel(str_in, text=f"• {item}", font=FONT_SMALL, text_color=COLOR_TEXT_PRIMARY, anchor="w", wraplength=740, justify="left").pack(fill="x", pady=1)

        # 4. Gaps & Suggestions Card
        gaps = res.get("gaps", [])
        suggestions = res.get("suggestions", [])
        all_feedback = gaps + suggestions
        if all_feedback:
            gap_card = create_card(self.scorecard_container)
            gap_card.pack(fill="x", pady=(0, 6))
            gap_in = ctk.CTkFrame(gap_card, fg_color="transparent")
            gap_in.pack(fill="x", padx=14, pady=10)
            ctk.CTkLabel(gap_in, text="⚡ Areas for Improvement & Interview Tips:", font=FONT_HEADING, text_color=COLOR_DANGER).pack(anchor="w", pady=(0, 4))
            for item in all_feedback:
                ctk.CTkLabel(gap_in, text=f"• {item}", font=FONT_SMALL, text_color=COLOR_TEXT_PRIMARY, anchor="w", wraplength=740, justify="left").pack(fill="x", pady=1)

        # 5. Model Answer Accordion
        model_ans = res.get("model_answer", "")
        if model_ans:
            ma_card = create_card(self.scorecard_container)
            ma_card.pack(fill="x", pady=(0, 8))
            ma_in = ctk.CTkFrame(ma_card, fg_color="transparent")
            ma_in.pack(fill="x", padx=14, pady=10)

            ctk.CTkLabel(ma_in, text="💡 What the Interviewer Was Looking For (Model Answer):", font=FONT_HEADING, text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", pady=(0, 4))
            ma_text = ctk.CTkTextbox(
                ma_in,
                font=FONT_CODE,
                fg_color=COLOR_BG,
                text_color=COLOR_TEXT_PRIMARY,
                border_color=COLOR_BORDER,
                border_width=1,
                corner_radius=6,
                height=150,
            )
            ma_text.insert("1.0", model_ans)
            ma_text.configure(state="disabled")
            ma_text.pack(fill="x", pady=(2, 0))
