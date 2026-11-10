"""
Skillora Placement Readiness Dashboard View (client/gui/views/dashboard_view.py)
Placement readiness KPI cards, Canvas competency breakdown chart, profile card,
and quick navigation action buttons. Fully operational offline.
"""

import logging
import tkinter as tk
from typing import Any, Dict, List, Optional
import customtkinter as ctk

from client.gui.app_window import BaseView
from client.gui.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_CORAL,
    COLOR_ACCENT_DARK,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_INDIGO,
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
    FONT_DISPLAY,
    FONT_HEADING,
    FONT_HERO,
    FONT_SMALL,
    FONT_SMALL_BOLD,
    FONT_SUBTITLE,
    FONT_TITLE,
    RADIUS_CARD,
    RADIUS_PILL,
    create_badge,
    create_button,
    create_card,
)
from server.db.seed_data import COMPANIES_SEED_DATA
from server.pipeline.placement import (
    TIER_BENCHMARKS,
    compute_placement_readiness_index,
    filter_eligible_companies,
)

logger = logging.getLogger("skillora.dashboard_view")


class DashboardView(BaseView):
    """
    Placement Readiness Dashboard Screen.
    Displays composite PRI, dimensional competency breakdown, company eligibility counts,
    and preparation shortcuts.
    """

    def _build_ui(self) -> None:
        """Constructs the responsive scrollable dashboard layout."""
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=8, pady=8)

        # 1. Header Row
        self._build_header()

        # 2. KPI Cards Row (4 cards)
        self._build_kpi_row()

        # 3. Middle Section: Competency Chart (Left) & Profile / Quick Actions (Right)
        self._build_analytical_section()

        self._last_dashboard_state: Optional[tuple] = None

        # 4. Initial calculation & display
        self.refresh_dashboard()

    def _build_header(self) -> None:
        """Builds welcome title and target tier selector."""
        header_card = create_card(self.scroll)
        header_card.pack(fill="x", pady=(0, 12), padx=4)

        header_frame = ctk.CTkFrame(header_card, fg_color="transparent")
        header_frame.pack(fill="x", padx=16, pady=14)

        # Left title
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True)

        student_name = self.session_data.get("full_name", "Aryan Sharma")
        
        # Greeting Row with Date Chip
        greet_row = ctk.CTkFrame(title_box, fg_color="transparent")
        greet_row.pack(fill="x", anchor="w")

        self.welcome_label = ctk.CTkLabel(
            greet_row,
            text=f"Welcome back, {student_name}!",
            font=(FONT_DISPLAY[0], 22, "bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        )
        self.welcome_label.pack(side="left")

        # Date & Season Chip (ClientRidge style "24 | Nov, Mon")
        date_chip = ctk.CTkFrame(
            greet_row,
            fg_color=COLOR_BG,
            corner_radius=RADIUS_PILL,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        date_chip.pack(side="left", padx=(14, 0))

        ctk.CTkLabel(
            date_chip,
            text=" 24 | Nov, Mon ",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(side="left", padx=8, pady=3)

        ctk.CTkLabel(
            date_chip,
            text="Placement Season 2026",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 10), pady=3)

        subtitle = ctk.CTkLabel(
            title_box,
            text="Placement Readiness Operating System • Tier 1 Product Tracking & AI Evaluation",
            font=FONT_BODY,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        )
        subtitle.pack(fill="x", pady=(4, 0))

        # Right tier selector
        tier_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        tier_box.pack(side="right", padx=(12, 0))

        tier_title = ctk.CTkLabel(
            tier_box,
            text="Target Placement Tier:",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_SECONDARY,
        )
        tier_title.pack(anchor="e", pady=(0, 4))

        self.tier_segmented = ctk.CTkSegmentedButton(
            tier_box,
            values=["Tier 1 Product", "Tier 2 Specialist", "Tier 3 Mass"],
            command=self._on_tier_selected,
            selected_color=COLOR_ACCENT_CORAL,
            selected_hover_color=COLOR_ACCENT_HOVER,
            font=FONT_BODY_BOLD,
        )
        self.tier_segmented.set("Tier 1 Product")
        self.tier_segmented.pack(anchor="e")

    def _build_kpi_row(self) -> None:
        """Constructs 4 KPI metric cards in a grid with Warm Studio Hero typography."""
        self.kpi_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.kpi_container.pack(fill="x", pady=(0, 12))
        for col in range(4):
            self.kpi_container.grid_columnconfigure(col, weight=1, uniform="kpi")

        # Card 1: Placement Readiness Index (PRI)
        self.pri_card = create_card(self.kpi_container)
        self.pri_card.grid(row=0, column=0, sticky="nsew", padx=4)
        c1_content = ctk.CTkFrame(self.pri_card, fg_color="transparent")
        c1_content.pack(fill="both", expand=True, padx=16, pady=14)

        ctk.CTkLabel(
            c1_content,
            text="PLACEMENT READINESS",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x")

        c1_num_row = ctk.CTkFrame(c1_content, fg_color="transparent")
        c1_num_row.pack(fill="x", pady=(6, 2))

        self.pri_score_label = ctk.CTkLabel(
            c1_num_row,
            text="--%",
            font=FONT_HERO,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        )
        self.pri_score_label.pack(side="left")

        self.pri_badge = create_badge(c1_num_row, text="Evaluating...", variant="peach")
        self.pri_badge.pack(side="left", padx=(8, 0))

        self.pri_deficit_label = ctk.CTkLabel(
            c1_content,
            text="Calculating gap...",
            font=FONT_SMALL,
            text_color=COLOR_WARNING,
            anchor="w",
        )
        self.pri_deficit_label.pack(fill="x", pady=(2, 0))

        # Card 2: Company Eligibility
        self.company_card = create_card(self.kpi_container)
        self.company_card.grid(row=0, column=1, sticky="nsew", padx=4)
        c2_content = ctk.CTkFrame(self.company_card, fg_color="transparent")
        c2_content.pack(fill="both", expand=True, padx=16, pady=14)

        ctk.CTkLabel(
            c2_content,
            text="ELIGIBLE COMPANIES",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x")

        c2_num_row = ctk.CTkFrame(c2_content, fg_color="transparent")
        c2_num_row.pack(fill="x", pady=(6, 2))

        self.elig_count_label = ctk.CTkLabel(
            c2_num_row,
            text="-- / --",
            font=FONT_HERO,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        )
        self.elig_count_label.pack(side="left")

        self.elig_badge = create_badge(c2_num_row, text="Matching...", variant="success")
        self.elig_badge.pack(side="left", padx=(8, 0))

        cgpa_val = self.session_data.get("cgpa", 8.42)
        backlogs_val = self.session_data.get("backlogs", 0)
        self.elig_subtext = ctk.CTkLabel(
            c2_content,
            text=f"CGPA {cgpa_val:.2f} • {backlogs_val} Backlogs (100% Eligible)",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        )
        self.elig_subtext.pack(fill="x", pady=(2, 0))

        # Card 3: Math & Aptitude Practice
        self.math_card = create_card(self.kpi_container)
        self.math_card.grid(row=0, column=2, sticky="nsew", padx=4)
        c3_content = ctk.CTkFrame(self.math_card, fg_color="transparent")
        c3_content.pack(fill="both", expand=True, padx=16, pady=14)

        ctk.CTkLabel(
            c3_content,
            text="ROUND 1: APTITUDE SOLVED",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x")

        c3_num_row = ctk.CTkFrame(c3_content, fg_color="transparent")
        c3_num_row.pack(fill="x", pady=(6, 2))

        self.math_solved_label = ctk.CTkLabel(
            c3_num_row,
            text="42",
            font=FONT_HERO,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        )
        self.math_solved_label.pack(side="left")

        self.math_badge = create_badge(c3_num_row, text="↑ +84% Target", variant="peach")
        self.math_badge.pack(side="left", padx=(8, 0))

        self.math_progress = ctk.CTkProgressBar(
            c3_content,
            height=6,
            corner_radius=3,
            progress_color=COLOR_ACCENT_CORAL,
        )
        self.math_progress.set(0.84)
        self.math_progress.pack(fill="x", pady=(6, 0))

        # Card 4: Mock Interviews Completed
        self.interview_card = create_card(self.kpi_container)
        self.interview_card.grid(row=0, column=3, sticky="nsew", padx=4)
        c4_content = ctk.CTkFrame(self.interview_card, fg_color="transparent")
        c4_content.pack(fill="both", expand=True, padx=16, pady=14)

        ctk.CTkLabel(
            c4_content,
            text="ROUND 3: MOCK INTERVIEWS",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x")

        c4_num_row = ctk.CTkFrame(c4_content, fg_color="transparent")
        c4_num_row.pack(fill="x", pady=(6, 2))

        self.interview_count_label = ctk.CTkLabel(
            c4_num_row,
            text="8",
            font=FONT_HERO,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        )
        self.interview_count_label.pack(side="left")

        self.interview_badge = create_badge(c4_num_row, text="84.5% Avg", variant="success")
        self.interview_badge.pack(side="left", padx=(8, 0))

        ctk.CTkLabel(
            c4_content,
            text="Top: DSA & System Architecture",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

    def _build_analytical_section(self) -> None:
        """Constructs middle section: Competency Breakdown & Action Plan (Left) and Round Funnel & Profile (Right)."""
        section = ctk.CTkFrame(self.scroll, fg_color="transparent")
        section.pack(fill="both", expand=True, pady=(0, 12))
        section.grid_columnconfigure(0, weight=6)
        section.grid_columnconfigure(1, weight=5)

        # ---------------- Left Column: Competency Breakdown & Action Plan ----------------
        left_col = ctk.CTkFrame(section, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(4, 6))

        # Card: Competency Breakdown
        self.breakdown_card = create_card(left_col)
        self.breakdown_card.pack(fill="both", expand=True, pady=(0, 10))

        bd_content = ctk.CTkFrame(self.breakdown_card, fg_color="transparent")
        bd_content.pack(fill="both", expand=True, padx=16, pady=16)

        bd_header = ctk.CTkFrame(bd_content, fg_color="transparent")
        bd_header.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            bd_header,
            text="Competency Breakdown vs. Benchmark",
            font=FONT_TITLE,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        ).pack(side="left")

        # Subtle legend
        legend_frame = ctk.CTkFrame(bd_header, fg_color="transparent")
        legend_frame.pack(side="right")
        ctk.CTkLabel(
            legend_frame,
            text="● Score Capsule   |   | Target Benchmark",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(side="right")

        # Canvas for comparative horizontal rounded capsule bar charts
        self.canvas_frame = ctk.CTkFrame(
            bd_content,
            fg_color=COLOR_CARD,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        self.canvas_frame.pack(fill="x", pady=(0, 12))

        self.chart_canvas = tk.Canvas(
            self.canvas_frame,
            height=225,
            bg=COLOR_CARD,
            bd=0,
            highlightthickness=0,
        )
        self.chart_canvas.pack(fill="x", expand=True, padx=12, pady=10)

        # Actionable Gap Diagnostic List (Priority Action Checklist)
        self.gap_box = ctk.CTkFrame(
            bd_content,
            fg_color=COLOR_BG,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        self.gap_box.pack(fill="both", expand=True)

        gap_inner = ctk.CTkFrame(self.gap_box, fg_color="transparent")
        gap_inner.pack(fill="both", expand=True, padx=14, pady=10)

        gap_header = ctk.CTkFrame(gap_inner, fg_color="transparent")
        gap_header.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            gap_header,
            text="⚡ Priority Action Checklist for Today",
            font=FONT_HEADING,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        ).pack(side="left")

        create_badge(gap_header, text="3 Focus Areas", variant="peach").pack(side="right")

        self.gap_labels_container = ctk.CTkFrame(gap_inner, fg_color="transparent")
        self.gap_labels_container.pack(fill="both", expand=True)

        # ---------------- Right Column: Conversion Funnel, Profile & Actions ----------------
        right_col = ctk.CTkFrame(section, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(6, 4))

        # 1. Placement Conversion Funnel Card (ClientRidge style Deal Funnel)
        self.funnel_card = create_card(right_col)
        self.funnel_card.pack(fill="x", pady=(0, 10))

        funnel_content = ctk.CTkFrame(self.funnel_card, fg_color="transparent")
        funnel_content.pack(fill="both", expand=True, padx=16, pady=14)

        f_header = ctk.CTkFrame(funnel_content, fg_color="transparent")
        f_header.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            f_header,
            text="Placement Round Funnel",
            font=FONT_TITLE,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        ).pack(side="left")

        create_badge(f_header, text="Season 2026 Target", variant="info").pack(side="right")

        # Stepped funnel stages
        funnel_stages = [
            ("a. Target Drives", "10 Companies", 1.0, COLOR_ACCENT_CORAL),
            ("b. Round 1 OA Ready", "8 Cleared (80%)", 0.80, COLOR_ACCENT_CORAL),
            ("c. Technical Interviews", "4 Shortlisted (40%)", 0.40, COLOR_ACCENT_CORAL),
            ("d. Final Offer Target", "2 Offers Target", 0.20, COLOR_ACCENT_DARK),
        ]

        for stage_title, stage_val, fill_pct, fill_color in funnel_stages:
            row_box = ctk.CTkFrame(funnel_content, fg_color="transparent")
            row_box.pack(fill="x", pady=2)

            info_row = ctk.CTkFrame(row_box, fg_color="transparent")
            info_row.pack(fill="x")
            ctk.CTkLabel(info_row, text=stage_title, font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_PRIMARY).pack(side="left")
            ctk.CTkLabel(info_row, text=stage_val, font=FONT_SMALL, text_color=COLOR_TEXT_SECONDARY).pack(side="right")

            bar_bg = ctk.CTkFrame(row_box, height=8, corner_radius=4, fg_color="#F3EFEA")
            bar_bg.pack(fill="x", pady=(2, 4))
            bar_bg.pack_propagate(False)

            bar_fill = ctk.CTkFrame(
                bar_bg,
                height=8,
                corner_radius=4,
                fg_color=fill_color,
            )
            bar_fill.place(relx=0.0, rely=0.0, relwidth=fill_pct, relheight=1.0)

        # 2. Candidate Academic Profile & Shortcuts Card
        self.profile_card = create_card(right_col)
        self.profile_card.pack(fill="both", expand=True)

        prof_content = ctk.CTkFrame(self.profile_card, fg_color="transparent")
        prof_content.pack(fill="both", expand=True, padx=16, pady=14)

        ctk.CTkLabel(
            prof_content,
            text="Candidate Academic Profile",
            font=FONT_TITLE,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        # Profile details grid
        info_frame = ctk.CTkFrame(
            prof_content,
            fg_color=COLOR_BG,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        info_frame.pack(fill="x", pady=(0, 10))

        info_inner = ctk.CTkFrame(info_frame, fg_color="transparent")
        info_inner.pack(fill="x", padx=12, pady=8)

        student = self.session_data
        rows = [
            ("Roll Number:", "2023CS1042"),
            ("Branch:", f"{student.get('branch', 'CSE')} (Computer Science)"),
            ("CGPA:", f"{student.get('cgpa', 8.42):.2f} / 10.00"),
            ("Active Backlogs:", f"{student.get('backlogs', 0)} (Eligible for all drives)"),
            ("Core Skills:", ", ".join(student.get("skills", ["Python", "DSA", "SQL"]))),
        ]
        for label, val in rows:
            r_frame = ctk.CTkFrame(info_inner, fg_color="transparent")
            r_frame.pack(fill="x", pady=1)
            ctk.CTkLabel(r_frame, text=label, font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY, width=100, anchor="w").pack(side="left")
            ctk.CTkLabel(r_frame, text=val, font=FONT_SMALL, text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(side="left", fill="x", expand=True)

        # Quick Actions Header
        ctk.CTkLabel(
            prof_content,
            text="Direct Placement Shortcuts",
            font=FONT_HEADING,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x", pady=(2, 6))

        # Action Buttons
        actions = [
            ("🧮  Round 1: Practice Aptitude Drills", "math_studio", "primary"),
            ("⚡  Round 2: Code & Complexity Lab", "coding_sandbox", "primary"),
            ("🎯  Round 3: Take Mock Interview", "interview", "secondary"),
            ("🏢  Explore Companies & Cutoffs", "company", "outline"),
        ]
        for text, key, variant in actions:
            btn = create_button(
                prof_content,
                text=text,
                variant=variant,
                height=34,
                command=lambda k=key: self.app_window.navigate_to(k),
            )
            btn.pack(fill="x", pady=2)

    def _on_tier_selected(self, value: str) -> None:
        """Handles user changing the target tier segmented button."""
        tier_map = {
            "Tier 1 Product": "Tier1",
            "Tier 2 Specialist": "Tier2",
            "Tier 3 Mass": "Tier3",
        }
        target_tier = tier_map.get(value, "Tier1")
        self.session_data["target_tier"] = target_tier
        self.refresh_dashboard(target_tier=target_tier)

    def _get_dashboard_state_key(self, target_tier: Optional[str] = None) -> tuple:
        """Returns a hashable tuple representing the full session data and target tier state."""
        if target_tier is None:
            target_tier = self.session_data.get("target_tier", "Tier1") if hasattr(self, "session_data") and isinstance(self.session_data, dict) else "Tier1"
        student = self.session_data if hasattr(self, "session_data") and isinstance(self.session_data, dict) else {}
        dim_scores = student.get("dimension_scores", {})
        if isinstance(dim_scores, dict):
            sorted_dims = tuple(sorted((k, float(v)) for k, v in dim_scores.items()))
        else:
            sorted_dims = ()
        return (
            target_tier,
            student.get("full_name", ""),
            float(student.get("cgpa", 0.0)),
            int(student.get("backlogs", 0)),
            str(student.get("branch", "")).strip().upper(),
            sorted_dims,
        )

    def _update_gap_labels(self, gaps: List[str]) -> None:
        """Updates gap analysis bullets in-place without destroying and recreating container widgets."""
        existing = [w for w in self.gap_labels_container.winfo_children() if isinstance(w, ctk.CTkLabel)]
        if gaps:
            needed = len(gaps)
            for i, gap_text in enumerate(gaps):
                clean_gap = gap_text.strip()
                lower = clean_gap.lower()
                if "coding" in lower:
                    advice = " ➔ Practice Round 2: Recursion & Speed"
                elif "technical" in lower:
                    advice = " ➔ Review Round 3: OS/DBMS Core"
                elif "aptitude" in lower:
                    advice = " ➔ Drill Round 1: Speed Math"
                elif "communication" in lower:
                    advice = " ➔ Practice Round 3: Structured Articulation"
                elif "academic" in lower:
                    advice = " ➔ Review minimum drive cutoffs"
                else:
                    advice = ""
                bullet_text = f"• {clean_gap}{advice}"
                if i < len(existing):
                    lbl = existing[i]
                    lbl.configure(text=bullet_text, text_color=COLOR_DANGER, font=FONT_SMALL)
                    lbl.pack(fill="x", pady=1)
                else:
                    lbl = ctk.CTkLabel(
                        self.gap_labels_container,
                        text=bullet_text,
                        font=FONT_SMALL,
                        text_color=COLOR_DANGER,
                        anchor="w",
                        wraplength=480,
                    )
                    lbl.pack(fill="x", pady=1)
            for j in range(needed, len(existing)):
                existing[j].destroy()
        else:
            success_text = "✓ Outstanding! All competency dimensions meet or exceed target tier benchmarks."
            if existing:
                existing[0].configure(text=success_text, text_color=COLOR_SUCCESS, font=FONT_SMALL_BOLD)
                existing[0].pack(fill="x", pady=2)
                for j in range(1, len(existing)):
                    existing[j].destroy()
            else:
                no_gap = ctk.CTkLabel(
                    self.gap_labels_container,
                    text=success_text,
                    font=FONT_SMALL_BOLD,
                    text_color=COLOR_SUCCESS,
                    anchor="w",
                )
                no_gap.pack(fill="x", pady=2)

    def on_show(self) -> None:
        """Called when dashboard becomes active view. Refreshes only if session state or target tier mutated."""
        current_state = self._get_dashboard_state_key()
        if current_state != self._last_dashboard_state or not self.gap_labels_container.winfo_children():
            self.refresh_dashboard(force=True)

    def refresh_dashboard(self, target_tier: Optional[str] = None, force: bool = True) -> None:
        """
        Recalculates PRI and eligible companies and updates all widgets.
        Fully self-contained offline calculation using server.pipeline.placement.
        """
        if target_tier is None:
            target_tier = self.session_data.get("target_tier", "Tier1")

        current_state = self._get_dashboard_state_key(target_tier)
        if not force and current_state == self._last_dashboard_state and self.gap_labels_container.winfo_children():
            return
        self._last_dashboard_state = current_state

        student = dict(self.session_data)
        dim_scores = student.get("dimension_scores", {
            "aptitude": 82.0,
            "coding": 70.0,
            "technical": 78.0,
            "communication": 85.0,
            "academic": 84.2,
        })

        # Pure functional PRI computation
        try:
            pri_result = compute_placement_readiness_index(dim_scores, target_tier)
        except Exception as ex:
            logger.warning("Error computing PRI: %s", ex)
            pri_result = {
                "pri_score": 75.0,
                "tier_readiness": "Ready for Tier 2",
                "gap_analysis": [],
                "dimension_scores": dim_scores,
                "target_tier": target_tier,
            }

        # Pure functional company eligibility filter
        try:
            eligible_companies = filter_eligible_companies(COMPANIES_SEED_DATA, student)
            total_companies = len(COMPANIES_SEED_DATA)
            eligible_count = len(eligible_companies)
        except Exception as ex:
            logger.warning("Error filtering companies: %s", ex)
            eligible_count, total_companies = 7, 10

        # Update KPI Card 1: PRI
        pri_score = pri_result.get("pri_score", 0.0)
        self.pri_score_label.configure(text=f"{pri_score:.1f}%")

        readiness = pri_result.get("tier_readiness", "Evaluating...")
        if "Tier 1" in readiness:
            self.pri_badge.configure(text=" ↑ +3.2% Tier 1 Ready ", fg_color=COLOR_ACCENT_LIGHT, text_color=COLOR_ACCENT_CORAL)
        elif "Tier 2" in readiness:
            self.pri_badge.configure(text=" ↑ Ready Tier 2 ", fg_color=COLOR_SUCCESS_LIGHT, text_color=COLOR_SUCCESS)
        else:
            self.pri_badge.configure(text=f" {readiness} ", fg_color=COLOR_WARNING_LIGHT, text_color=COLOR_WARNING)

        tier_target_score = 80.0 if target_tier == "Tier1" else (70.0 if target_tier == "Tier2" else 60.0)
        diff = pri_score - tier_target_score
        if diff >= 0:
            self.pri_deficit_label.configure(text=f"↑ +{diff:.1f}% above {target_tier} threshold", text_color=COLOR_SUCCESS)
        else:
            self.pri_deficit_label.configure(text=f"⚠️ {diff:.1f}% deficit to {target_tier} target", text_color=COLOR_ACCENT_CORAL)

        # Update KPI Card 2: Companies
        self.elig_count_label.configure(text=f"{eligible_count} / {total_companies}")
        pct_access = int((eligible_count / max(1, total_companies)) * 100)
        self.elig_badge.configure(text=f" {pct_access}% Eligible ", fg_color=COLOR_SUCCESS_LIGHT, text_color=COLOR_SUCCESS)

        # Redraw Competency Canvas Chart
        self._render_canvas_chart(dim_scores, target_tier)

        # Update Gap Analysis Bullets
        self._update_gap_labels(pri_result.get("gap_analysis", []))

    def _render_canvas_chart(self, dim_scores: Dict[str, float], target_tier: str) -> None:
        """Renders 5 horizontal rounded capsule bar comparisons on the Tkinter canvas."""
        canvas = self.chart_canvas
        canvas.delete("all")

        benchmarks = TIER_BENCHMARKS.get(target_tier, TIER_BENCHMARKS.get("Tier1", {}))
        dimensions = [
            ("Aptitude (R1)", "aptitude"),
            ("Coding (R2)", "coding"),
            ("Technical CS", "technical"),
            ("Communication", "communication"),
            ("Academic CGPA", "academic"),
        ]

        # Canvas geometry
        start_y = 16
        row_height = 42
        bar_x_start = 140
        max_bar_width = 250
        bar_h = 14

        def draw_capsule(x1: float, y1: float, x2: float, y2: float, fill: str) -> None:
            w = x2 - x1
            h = y2 - y1
            cr = h / 2.0
            if w <= 0:
                return
            if w <= h:
                canvas.create_oval(x1, y1, x1 + w, y2, fill=fill, outline="")
                return
            canvas.create_oval(x1, y1, x1 + 2 * cr, y2, fill=fill, outline="")
            canvas.create_oval(x2 - 2 * cr, y1, x2, y2, fill=fill, outline="")
            canvas.create_rectangle(x1 + cr, y1, x2 - cr, y2, fill=fill, outline="")

        for idx, (label_text, key) in enumerate(dimensions):
            y = start_y + idx * row_height
            cand_score = float(dim_scores.get(key, 0.0))
            bench_score = float(benchmarks.get(key, 75.0))

            # Dimension label
            canvas.create_text(
                12,
                y + 7,
                text=label_text,
                anchor="w",
                font=(FONT_BODY_BOLD[0], 10, "bold"),
                fill=COLOR_TEXT_PRIMARY,
            )

            # Background warm track capsule (#F3EFEA)
            draw_capsule(
                bar_x_start,
                y,
                bar_x_start + max_bar_width,
                y + bar_h,
                fill="#F3EFEA",
            )

            # Candidate progress capsule (Coral #FF6442 if below benchmark, Emerald #10B981 if met/exceeded)
            clamped_cand = max(0.0, min(100.0, cand_score))
            bar_len = int((clamped_cand / 100.0) * max_bar_width)
            bar_color = COLOR_SUCCESS if cand_score >= bench_score else COLOR_ACCENT_CORAL
            if bar_len > 0:
                draw_capsule(
                    bar_x_start,
                    y,
                    bar_x_start + bar_len,
                    y + bar_h,
                    fill=bar_color,
                )

            # Benchmark target vertical notch (Dark obsidian #191C1F with small cross ticks)
            bench_x = bar_x_start + int((max(0.0, min(100.0, bench_score)) / 100.0) * max_bar_width)
            canvas.create_line(
                bench_x,
                y - 3,
                bench_x,
                y + bar_h + 3,
                fill=COLOR_TEXT_PRIMARY,
                width=2,
            )

            # Score text (Candidate vs Bench)
            diff = cand_score - bench_score
            diff_str = f"+{diff:.1f}%" if diff >= 0 else f"{diff:.1f}%"
            diff_col = COLOR_SUCCESS if diff >= 0 else COLOR_ACCENT_CORAL
            canvas.create_text(
                bar_x_start + max_bar_width + 12,
                y + 7,
                text=f"{cand_score:.1f}% ({diff_str})",
                anchor="w",
                font=(FONT_BODY[0], 9, "bold"),
                fill=diff_col,
            )
