"""
Skillora Company Explorer View (client/gui/views/company_view.py)
Tiered company card grid, academic cutoff filters, functional eligibility evaluation,
and expandable role/selection stages drawer. Fully operational offline.
"""

import logging
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
from server.db.seed_data import COMPANIES_SEED_DATA
from server.pipeline.placement import is_eligible

logger = logging.getLogger("skillora.company_view")


class CompanyView(BaseView):
    """
    Company Explorer Screen.
    Browse Tier 1/2/3 companies, filter by CGPA/backlogs/branch, evaluate eligibility,
    and inspect selection stages and package details.
    """

    def _build_ui(self) -> None:
        """Builds search filters panel and scrollable company cards grid."""
        # Top Header & Filters Panel
        self._build_filters_panel()

        # Scrollable area for company cards
        self.cards_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.cards_scroll.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        # Expanded state tracking for card drawers: {company_name: bool}
        self._expanded_drawers: Dict[str, bool] = {}
        self._drawer_frames: Dict[str, ctk.CTkFrame] = {}
        self._last_rendered_state: Optional[tuple] = None

        # Initial render
        self.apply_filters()

    def _build_filters_panel(self) -> None:
        """Constructs top panel with search, tier, CGPA, backlogs, and branch filters."""
        panel_card = create_card(self)
        panel_card.pack(fill="x", padx=12, pady=(12, 6))

        panel = ctk.CTkFrame(panel_card, fg_color="transparent")
        panel.pack(fill="x", padx=16, pady=12)

        # Header Row
        header_row = ctk.CTkFrame(panel, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 10))

        title_box = ctk.CTkFrame(header_row, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="🏢 Target Companies & Placement Cutoffs",
            font=FONT_TITLE,
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Explore campus recruitment drives, verify your academic eligibility cutoffs, and view selection stages.",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        self.count_badge = create_badge(header_row, text="Showing 10 of 10", variant="peach")
        self.count_badge.pack(side="right")

        # Row 1: Search & Tier Segmented Button
        row1 = ctk.CTkFrame(panel, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 8))

        self.search_entry = create_entry(
            row1,
            placeholder_text="Search company name, role, or keywords...",
            width=280,
        )
        self.search_entry.pack(side="left", padx=(0, 12))
        self.search_entry.bind("<KeyRelease>", lambda event: self.apply_filters())

        ctk.CTkLabel(row1, text="Tier:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=(0, 6))
        self.tier_segmented = ctk.CTkSegmentedButton(
            row1,
            values=["All", "Tier 1 Product", "Tier 2 Specialist", "Tier 3 Mass"],
            command=lambda val: self.apply_filters(),
            selected_color=COLOR_ACCENT_CORAL,
            selected_hover_color=COLOR_ACCENT_HOVER,
            font=FONT_SMALL_BOLD,
        )
        self.tier_segmented.set("All")
        self.tier_segmented.pack(side="left")

        # Row 2: CGPA Slider, Backlogs, Branch
        row2 = ctk.CTkFrame(panel, fg_color="transparent")
        row2.pack(fill="x")

        # CGPA Filter
        cgpa_box = ctk.CTkFrame(row2, fg_color="transparent")
        cgpa_box.pack(side="left", padx=(0, 16))

        self.cgpa_label = ctk.CTkLabel(
            cgpa_box,
            text="Min CGPA Cutoff: >= 5.00",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_SECONDARY,
        )
        self.cgpa_label.pack(anchor="w")

        self.cgpa_slider = ctk.CTkSlider(
            cgpa_box,
            from_=5.0,
            to=9.5,
            number_of_steps=45,
            width=160,
            command=self._on_cgpa_slider_changed,
        )
        self.cgpa_slider.set(5.0)
        self.cgpa_slider.pack(anchor="w", pady=(2, 0))

        # Backlogs Filter
        backlog_box = ctk.CTkFrame(row2, fg_color="transparent")
        backlog_box.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(backlog_box, text="Max Backlogs Allowed:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.backlogs_menu = ctk.CTkOptionMenu(
            backlog_box,
            values=["Any", "0 (No Backlogs)", "Max 1", "Max 2"],
            command=lambda val: self.apply_filters(),
            width=140,
            font=FONT_SMALL,
        )
        self.backlogs_menu.set("Any")
        self.backlogs_menu.pack(anchor="w", pady=(2, 0))

        # Branch Filter
        branch_box = ctk.CTkFrame(row2, fg_color="transparent")
        branch_box.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(branch_box, text="Candidate Branch:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.branch_menu = ctk.CTkOptionMenu(
            branch_box,
            values=["ALL", "CSE", "IT", "ECE", "EEE", "MECH", "CIVIL", "MCA"],
            command=lambda val: self.apply_filters(),
            width=110,
            font=FONT_SMALL,
        )
        self.branch_menu.set("ALL")
        self.branch_menu.pack(anchor="w", pady=(2, 0))

        # Reset Filters Button
        reset_btn = create_button(
            row2,
            text="Reset Filters",
            variant="outline",
            height=28,
            command=self.reset_filters,
        )
        reset_btn.pack(side="right")

    def _on_cgpa_slider_changed(self, value: float) -> None:
        """Updates CGPA label dynamically and reapplies filter."""
        self.cgpa_label.configure(text=f"Min CGPA Cutoff: >= {value:.2f}")
        self.apply_filters()

    def reset_filters(self) -> None:
        """Resets all search filters to default."""
        self.search_entry.delete(0, "end")
        self.tier_segmented.set("All")
        self.cgpa_slider.set(5.0)
        self.cgpa_label.configure(text="Min CGPA Cutoff: >= 5.00")
        self.backlogs_menu.set("Any")
        self.branch_menu.set("ALL")
        self.apply_filters()

    def _get_filter_state_key(self) -> tuple:
        """Returns a hashable tuple representing the full filter, drawer, and student profile state."""
        student = self.session_data if hasattr(self, "session_data") and isinstance(self.session_data, dict) else {}
        return (
            self.search_entry.get().strip().lower() if hasattr(self, "search_entry") else "",
            self.tier_segmented.get() if hasattr(self, "tier_segmented") else "All",
            float(self.cgpa_slider.get()) if hasattr(self, "cgpa_slider") else 5.0,
            self.backlogs_menu.get() if hasattr(self, "backlogs_menu") else "Any",
            self.branch_menu.get() if hasattr(self, "branch_menu") else "ALL",
            float(student.get("cgpa", 0.0)),
            int(student.get("backlogs", 0)),
            str(student.get("branch", "")).strip().upper(),
            tuple(sorted(self._expanded_drawers.items())) if hasattr(self, "_expanded_drawers") else (),
        )

    def on_show(self) -> None:
        """Refreshes cards on navigation to company view only if filter criteria or student state changed."""
        current_state = self._get_filter_state_key()
        if current_state != self._last_rendered_state or not self.cards_scroll.winfo_children():
            self.apply_filters(force=True)

    def apply_filters(self, force: bool = True) -> None:
        """Filters COMPANIES_SEED_DATA based on active UI inputs and renders cards."""
        current_state = self._get_filter_state_key()
        if not force and current_state == self._last_rendered_state and self.cards_scroll.winfo_children():
            return
        self._last_rendered_state = current_state

        query = self.search_entry.get().strip().lower()
        tier_choice = self.tier_segmented.get()
        tier_filter_map = {
            "Tier 1 Product": "Tier1",
            "Tier 2 Specialist": "Tier2",
            "Tier 3 Mass": "Tier3",
        }
        target_tier = tier_filter_map.get(tier_choice)

        min_cgpa_val = float(self.cgpa_slider.get())
        backlog_choice = self.backlogs_menu.get()
        branch_choice = self.branch_menu.get()

        student = dict(self.session_data)

        # Clear existing cards
        for widget in self.cards_scroll.winfo_children():
            widget.destroy()
        self._drawer_frames.clear()

        matched_companies = []
        eligible_count = 0

        for comp in COMPANIES_SEED_DATA:
            c_name = comp.get("name", "")
            c_tier = comp.get("tier", "")
            c_cgpa = float(comp.get("min_cgpa", 0.0))
            c_backlogs = int(comp.get("max_backlogs", 0))
            c_branches = comp.get("eligible_branches_csv", "").split(",")
            c_branches_clean = [b.strip().upper() for b in c_branches]

            # Text query filter (name or roles)
            if query:
                roles_text = " ".join(r.get("role_title", "") for r in comp.get("roles", [])).lower()
                if query not in c_name.lower() and query not in roles_text:
                    continue

            # Tier filter
            if target_tier and c_tier != target_tier:
                continue

            # CGPA slider filter
            if c_cgpa < min_cgpa_val:
                continue

            # Backlogs filter
            if backlog_choice == "0 (No Backlogs)" and c_backlogs != 0:
                continue
            elif backlog_choice == "Max 1" and c_backlogs > 1:
                continue
            elif backlog_choice == "Max 2" and c_backlogs > 2:
                continue

            # Branch filter
            if branch_choice != "ALL" and "ALL" not in c_branches_clean and branch_choice not in c_branches_clean:
                continue

            # Determine eligibility using genuine pure functional predicate
            elig = is_eligible(comp, student)
            if elig:
                eligible_count += 1

            matched_companies.append((comp, elig))

        # Update count badge
        self.count_badge.configure(text=f"Showing {len(matched_companies)} of {len(COMPANIES_SEED_DATA)} ({eligible_count} Eligible)")

        # Render cards
        if not matched_companies:
            empty_card = create_card(self.cards_scroll)
            empty_card.pack(fill="x", padx=8, pady=20)
            ctk.CTkLabel(
                empty_card,
                text="No recruitment drives match the specified filters. Try lowering CGPA cutoff or selecting 'All' tiers.",
                font=FONT_BODY,
                text_color=COLOR_TEXT_SECONDARY,
            ).pack(padx=20, pady=24)
            return

        for comp, elig in matched_companies:
            self._render_company_card(comp, elig, student)

    def _render_company_card(self, comp: dict, is_elig: bool, student: dict) -> None:
        """Constructs an individual tiered company card."""
        card = create_card(self.cards_scroll)
        card.pack(fill="x", padx=4, pady=6)

        c_name = comp.get("name", "Company")
        c_tier = comp.get("tier", "Tier1")
        roles = comp.get("roles", [])

        # Extract max package
        packages = [float(r.get("package_lpa", 0.0)) for r in roles]
        max_pkg = max(packages) if packages else 0.0

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=12)

        # Header Row: Name, Tier Badge, Package, Eligibility Badge
        h_row = ctk.CTkFrame(content, fg_color="transparent")
        h_row.pack(fill="x")

        # Left: Name and Tier
        left_box = ctk.CTkFrame(h_row, fg_color="transparent")
        left_box.pack(side="left")

        ctk.CTkLabel(
            left_box,
            text=c_name,
            font=FONT_TITLE,
            text_color=COLOR_TEXT_PRIMARY,
        ).pack(side="left", padx=(0, 8))

        tier_display = "Tier 1 Product" if c_tier == "Tier1" else ("Tier 2 Specialist" if c_tier == "Tier2" else "Tier 3 Mass")
        tier_badge = create_badge(left_box, text=tier_display, variant="peach" if c_tier == "Tier1" else "info")
        tier_badge.pack(side="left")

        # Right: Package and Eligibility Pill
        right_box = ctk.CTkFrame(h_row, fg_color="transparent")
        right_box.pack(side="right")

        ctk.CTkLabel(
            right_box,
            text=f"{max_pkg:.1f} LPA",
            font=FONT_TITLE,
            text_color=COLOR_SUCCESS,
        ).pack(side="left", padx=(0, 12))

        if is_elig:
            elig_pill = create_badge(right_box, text="✓ ELIGIBLE", variant="success")
        else:
            # Determine specific deficit reason
            cand_cgpa = float(student.get("cgpa", 0.0))
            cand_backlogs = int(student.get("backlogs", 0))
            cand_branch = str(student.get("branch", "")).upper()
            req_cgpa = float(comp.get("min_cgpa", 0.0))
            req_backlogs = int(comp.get("max_backlogs", 0))
            req_branches = [b.strip().upper() for b in comp.get("eligible_branches_csv", "").split(",")]

            if cand_cgpa < req_cgpa:
                reason = f"CGPA Deficit ({cand_cgpa:.2f} < {req_cgpa:.2f})"
            elif cand_backlogs > req_backlogs:
                reason = f"Backlogs Exceeded ({cand_backlogs} > {req_backlogs})"
            elif "ALL" not in req_branches and cand_branch not in req_branches:
                reason = f"Branch Mismatch ({cand_branch})"
            else:
                reason = "Ineligible"

            elig_pill = create_badge(right_box, text=f"✗ {reason}", variant="danger")
        elig_pill.pack(side="left")

        # Metadata Row
        m_row = ctk.CTkFrame(content, fg_color="transparent")
        m_row.pack(fill="x", pady=(8, 4))

        meta_items = [
            f"Min CGPA: {comp.get('min_cgpa', 0.0):.2f}",
            f"Max Backlogs: {comp.get('max_backlogs', 0)}",
            f"Branches: {comp.get('eligible_branches_csv', 'ALL')}",
            f"Roles Offered: {len(roles)}",
        ]
        for m_text in meta_items:
            m_box = ctk.CTkFrame(m_row, fg_color=COLOR_BG, corner_radius=6, border_width=1, border_color=COLOR_BORDER)
            m_box.pack(side="left", padx=(0, 8), pady=2)
            ctk.CTkLabel(m_box, text=m_text, font=FONT_SMALL, text_color=COLOR_TEXT_SECONDARY).pack(padx=8, pady=3)

        # Expand / Collapse Roles Drawer Button
        drawer_key = c_name
        is_expanded = self._expanded_drawers.get(drawer_key, False)

        toggle_btn = create_button(
            content,
            text="Collapse Selection Details (▲)" if is_expanded else "View Roles & Selection Stages (▼)",
            variant="outline",
            height=28,
            command=lambda k=drawer_key, c=comp: self._toggle_drawer(k, c),
        )
        toggle_btn.pack(anchor="w", pady=(6, 0))

        # Drawer container frame
        drawer_frame = ctk.CTkFrame(content, fg_color=COLOR_BG, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        self._drawer_frames[drawer_key] = drawer_frame

        if is_expanded:
            self._populate_drawer(drawer_frame, comp)
            drawer_frame.pack(fill="x", pady=(8, 0))

    def _toggle_drawer(self, drawer_key: str, comp: dict) -> None:
        """Toggles expanding roles and selection stages drawer for a company card."""
        current = self._expanded_drawers.get(drawer_key, False)
        self._expanded_drawers[drawer_key] = not current
        self.apply_filters()

    def _populate_drawer(self, drawer_frame: ctk.CTkFrame, comp: dict) -> None:
        """Fills the expanded drawer with roles, interview stages, and round weights."""
        inner = ctk.CTkFrame(drawer_frame, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)

        roles = comp.get("roles", [])
        ctk.CTkLabel(inner, text="Available Roles & Compensation:", font=FONT_HEADING, text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(fill="x", pady=(0, 4))

        for r in roles:
            role_title = r.get("role_title", "Software Engineer")
            pkg = r.get("package_lpa", 0.0)
            r_box = ctk.CTkFrame(inner, fg_color=COLOR_CARD, corner_radius=6, border_width=1, border_color=COLOR_BORDER)
            r_box.pack(fill="x", pady=2)

            r_inner = ctk.CTkFrame(r_box, fg_color="transparent")
            r_inner.pack(fill="x", padx=10, pady=6)

            ctk.CTkLabel(r_inner, text=f"• {role_title}", font=FONT_BODY_BOLD, text_color=COLOR_TEXT_PRIMARY).pack(side="left")
            ctk.CTkLabel(r_inner, text=f"{pkg:.1f} LPA CTC", font=FONT_BODY_BOLD, text_color=COLOR_SUCCESS).pack(side="right")

            # Selection stages & weights
            round_struct = r.get("round_structure", {})
            rounds = round_struct.get("rounds", [])
            weights = round_struct.get("weights", {})

            if rounds:
                ctk.CTkLabel(inner, text="Recruitment Selection Pipeline:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY, anchor="w").pack(fill="x", pady=(6, 2))
                for s_idx, round_name in enumerate(rounds, 1):
                    s_label = ctk.CTkLabel(inner, text=f"   Stage {s_idx}: {round_name}", font=FONT_SMALL, text_color=COLOR_TEXT_PRIMARY, anchor="w")
                    s_label.pack(fill="x")

            if weights:
                w_str = " • ".join(f"{k.capitalize()} {int(v*100)}%" for k, v in weights.items())
                ctk.CTkLabel(inner, text=f"Evaluation Weights: {w_str}", font=FONT_SMALL_BOLD, text_color=COLOR_ACCENT_BLUE, anchor="w").pack(fill="x", pady=(4, 0))
