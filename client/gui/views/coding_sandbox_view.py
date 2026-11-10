"""
Skillora Coding Sandbox View (client/gui/views/coding_sandbox_view.py)
Monospace Python code editor, algorithm templates, input scaling selector,
multiprocessing sandbox runner, Tkinter Canvas curve plot, empirical Big-O classification,
and Algorithmic Divergence Alert Banner. Fully non-blocking and operational offline.
"""

import logging
import threading
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple
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
    FONT_FAMILY_CODE,
    FONT_HEADING,
    FONT_SMALL,
    FONT_SMALL_BOLD,
    FONT_TITLE,
    RADIUS_BUTTON,
    RADIUS_CARD,
    create_badge,
    create_button,
    create_card,
    create_entry,
)
from server.profiler.divergence import detect_divergence
from server.sandbox.mp_runner import run_empirical_profile

logger = logging.getLogger("skillora.coding_sandbox_view")

# Code Templates with Interview Challenge Metadata
SANDBOX_TEMPLATES = {
    "Linear Sum (O(n))": {
        "title": "Single Pass Range Sum",
        "companies": ["TCS Digital", "Infosys", "Wipro"],
        "difficulty": "Easy",
        "description": "Calculate the sum of all integers from 0 up to n - 1. A single loop must complete in linear time.",
        "goal": "Ensure O(n) single pass without nested iterations.",
        "claimed": "O(n)",
        "skeleton": '''def solve(n):
    """
    Challenge: Single Pass Range Sum
    Input: n (integer size)
    Target: O(n) linear single pass
    """
    # Write your solution below:
    pass
''',
        "naive": '''def solve(n):
    # Redundant iteration simulation:
    total = 0
    for i in range(n):
        for _ in range(1):
            total += i
    return total
''',
        "optimal": '''def solve(n):
    total = 0
    for i in range(n):
        total += i
    return total
''',
        "code": '''def solve(n):
    """
    Challenge: Single Pass Range Sum
    Input: n (integer size)
    Target: O(n) linear single pass
    """
    # Write your solution below:
    pass
''',
    },
    "Bubble Sort (O(n^2))": {
        "title": "Naive Bubble Sort Challenge",
        "companies": ["Cognizant", "Accenture"],
        "difficulty": "Easy-Medium",
        "description": "Sort an array of n random integers using adjacent pairwise comparisons. Notice how quadratic time explodes on large inputs.",
        "goal": "Identify O(n²) scaling bottleneck and consider upgrading to O(n log n).",
        "claimed": "O(n^2)",
        "skeleton": '''def solve(n):
    """
    Challenge: Naive Bubble Sort Challenge
    Input: n (size of array to sort)
    Target: Observe O(n^2) quadratic scaling bottleneck vs O(n log n)
    """
    import random
    arr = [random.randint(0, 1000) for _ in range(n)]
    # Write your sorting logic below:
    pass
''',
        "naive": '''def solve(n):
    import random
    arr = [random.randint(0, 1000) for _ in range(n)]
    for i in range(len(arr)):
        for j in range(0, len(arr) - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
''',
        "optimal": '''def solve(n):
    import random
    arr = [random.randint(0, 1000) for _ in range(n)]
    # Standard Python Timsort (O(n log n))
    return sorted(arr)
''',
        "code": '''def solve(n):
    """
    Challenge: Naive Bubble Sort Challenge
    Input: n (size of array to sort)
    Target: Observe O(n^2) quadratic scaling bottleneck vs O(n log n)
    """
    import random
    arr = [random.randint(0, 1000) for _ in range(n)]
    # Write your sorting logic below:
    pass
''',
    },
    "Merge Sort (O(n log n))": {
        "title": "Divide-and-Conquer Merge Sort",
        "companies": ["Amazon", "Microsoft", "Google"],
        "difficulty": "Medium-Hard",
        "description": "Recursively split an array in half and merge in linear time. Optimal sorting benchmark for product company coding rounds.",
        "goal": "Achieve O(n log n) optimal comparison sorting.",
        "claimed": "O(n log n)",
        "skeleton": '''def solve(n):
    """
    Challenge: Divide-and-Conquer Merge Sort
    Input: n (size of array to sort)
    Target: O(n log n) optimal divide-and-conquer
    """
    import random
    arr = [random.randint(0, 1000) for _ in range(n)]
    # Write your recursive merge sort logic below:
    pass
''',
        "naive": '''def solve(n):
    # Naive pairwise comparison sort fallback: O(n^2)
    import random
    arr = [random.randint(0, 1000) for _ in range(n)]
    for i in range(len(arr)):
        for j in range(i + 1, len(arr)):
            if arr[j] < arr[i]:
                arr[i], arr[j] = arr[j], arr[i]
    return arr
''',
        "optimal": '''def solve(n):
    import random
    arr = [random.randint(0, 1000) for _ in range(n)]
    
    def merge_sort(a):
        if len(a) <= 1:
            return a
        mid = len(a) // 2
        left = merge_sort(a[:mid])
        right = merge_sort(a[mid:])
        res = []
        i = j = 0
        while i < len(left) and j < len(right):
            if left[i] <= right[j]:
                res.append(left[i]); i += 1
            else:
                res.append(right[j]); j += 1
        res.extend(left[i:]); res.extend(right[j:])
        return res

    return merge_sort(arr)
''',
        "code": '''def solve(n):
    """
    Challenge: Divide-and-Conquer Merge Sort
    Input: n (size of array to sort)
    Target: O(n log n) optimal divide-and-conquer
    """
    import random
    arr = [random.randint(0, 1000) for _ in range(n)]
    # Write your recursive merge sort logic below:
    pass
''',
    },
    "Algorithmic Divergence Demo (Claims O(n), Actually O(n^2))": {
        "title": "Ordered Pair Counting (The TLE Trap)",
        "companies": ["Amazon", "Zoho", "Adobe"],
        "difficulty": "Medium",
        "description": "Count all ordered index pairs (i, j) where j < i. The candidate claims O(n), but the inner loop creates quadratic O(n²) TLE!",
        "goal": "Avoid nested loops (O(n²)) to beat the interview time limit.",
        "claimed": "O(n)",
        "skeleton": '''def solve(n):
    """
    Challenge: Ordered Pair Counting (The TLE Trap)
    Input: n (integer size)
    Target: Claim O(n), discover if nested loop triggers divergence!
    """
    # Write your solution below:
    pass
''',
        "naive": '''def solve(n):
    # Candidate claims this is O(n), but inner loop causes O(n^2) scaling!
    acc = 0
    for i in range(n):
        for j in range(i):
            acc += 1
    return acc
''',
        "optimal": '''def solve(n):
    # Direct closed-form mathematical formula: O(1)
    return n * (n - 1) // 2
''',
        "code": '''def solve(n):
    """
    Challenge: Ordered Pair Counting (The TLE Trap)
    Input: n (integer size)
    Target: Claim O(n), discover if nested loop triggers divergence!
    """
    # Write your solution below:
    pass
''',
    },
    "Infinite Loop Timeout Demo (Terminates Safely)": {
        "title": "Infinite Loop & Deadlock Watchdog",
        "companies": ["All Online Assessments"],
        "difficulty": "Stress Test",
        "description": "Demonstrates rogue loop termination: an intentional infinite while-loop that the sandbox cleanly intercepts without crashing.",
        "goal": "Learn how online assessment platforms kill runaway programs.",
        "claimed": "O(n)",
        "skeleton": '''def solve(n):
    """
    Challenge: Infinite Loop & Deadlock Watchdog
    Input: n (integer size)
    Target: Watchdog cleanly terminates runaway code
    """
    # Write your test loop below:
    pass
''',
        "naive": '''def solve(n):
    # Rogue infinite loop: demonstrates hard sandbox timeout!
    while True:
        pass
''',
        "optimal": '''def solve(n):
    # Safe bounded loop that terminates well within time limit
    s = 0
    for i in range(min(n, 1000)):
        s += i
    return s
''',
        "code": '''def solve(n):
    """
    Challenge: Infinite Loop & Deadlock Watchdog
    Input: n (integer size)
    Target: Watchdog cleanly terminates runaway code
    """
    # Write your test loop below:
    pass
''',
    },
}


class CodingSandboxView(BaseView):
    """
    Coding Complexity Sandbox Screen.
    Executes student Python code across scaling input sizes N in an isolated
    multiprocessing sandbox, measures runtimes, plots empirical curves, and
    flags algorithmic divergences without UI freezing.
    """

    def _build_ui(self) -> None:
        """Constructs LeetCode 3.0 split-pane studio: Left Problem Arena, Right Editor & Console."""
        self._font_size = 12
        self._code_mode = "skeleton"

        # Main 2-Column Split Frame
        split_frame = ctk.CTkFrame(self, fg_color="transparent")
        split_frame.pack(fill="both", expand=True, padx=8, pady=4)
        split_frame.grid_columnconfigure(0, weight=4, minsize=350)  # Left: Problem Arena (robust minimum width)
        split_frame.grid_columnconfigure(1, weight=5, minsize=480)  # Right: Code Studio & Console
        split_frame.grid_rowconfigure(0, weight=1)

        # ---------------- Left Column: Problem & Challenge Arena ----------------
        self._build_problem_pane(split_frame)

        # ---------------- Right Column: Editor & Tabbed Console ----------------
        self._build_editor_and_console_pane(split_frame)

        # Load default template in skeleton practice mode
        self._load_template("Linear Sum (O(n))", mode="skeleton")

    def _build_problem_pane(self, parent: ctk.CTkFrame) -> None:
        """Constructs left LeetCode-style problem arena with specifications, constraints, and hints."""
        left_card = create_card(parent)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(4, 6), pady=4)

        self._left_scroll = ctk.CTkScrollableFrame(left_card, fg_color="transparent")
        self._left_scroll.pack(fill="both", expand=True, padx=12, pady=10)

        # 1. Header Row (Specification Title & Difficulty Badge)
        meta_row = ctk.CTkFrame(self._left_scroll, fg_color="transparent")
        meta_row.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            meta_row,
            text="CHALLENGE SPECIFICATION",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(side="left")

        self.q_diff_badge = create_badge(meta_row, text=" Easy ", variant="success")
        self.q_diff_badge.pack(side="right")

        # Company Tags Sub-Row (Dedicated full-width row so it never collides or gets pushed off)
        company_row = ctk.CTkFrame(self._left_scroll, fg_color="transparent")
        company_row.pack(fill="x", pady=(0, 6))

        self.q_company_badge = create_badge(company_row, text=" 🏢 TCS Digital, Infosys ", variant="indigo")
        self.q_company_badge.pack(side="left")

        # 2. Challenge Title (responsive auto-wrap)
        init_wrap = 190
        self.q_title_label = ctk.CTkLabel(
            self._left_scroll,
            text="📌 Single Pass Range Sum",
            font=FONT_TITLE,
            text_color=COLOR_TEXT_PRIMARY,
            justify="left",
            anchor="w",
            wraplength=init_wrap,
        )
        self.q_title_label.pack(fill="x", pady=(2, 6))

        # 3. Problem Statement & Goal Card
        desc_box = ctk.CTkFrame(self._left_scroll, fg_color=COLOR_BG, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        desc_box.pack(fill="x", pady=(4, 8))
        d_inner = ctk.CTkFrame(desc_box, fg_color="transparent")
        d_inner.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(
            d_inner,
            text="Problem Description:",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        ).pack(fill="x")

        self.q_desc_label = ctk.CTkLabel(
            d_inner,
            text="Calculate the sum of all integers from 0 up to n - 1. A single loop must complete in linear time.",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            wraplength=init_wrap,
            justify="left",
            anchor="w",
        )
        self.q_desc_label.pack(fill="x", pady=(4, 6))

        self.q_goal_label = ctk.CTkLabel(
            d_inner,
            text="🎯 Target Goal: Ensure O(n) single pass without nested iterations.",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_ACCENT_BLUE,
            wraplength=init_wrap,
            justify="left",
            anchor="w",
        )
        self.q_goal_label.pack(fill="x")

        # 4. Constraints Card
        const_box = ctk.CTkFrame(self._left_scroll, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        const_box.pack(fill="x", pady=(0, 8))
        c_inner = ctk.CTkFrame(const_box, fg_color="transparent")
        c_inner.pack(fill="x", padx=12, pady=10)

        self.q_const_title = ctk.CTkLabel(
            c_inner,
            text="Input Constraints & Assessment Limits:",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_PRIMARY,
            wraplength=init_wrap,
            justify="left",
            anchor="w",
        )
        self.q_const_title.pack(fill="x", pady=(0, 4))

        self.q_const_body = ctk.CTkLabel(
            c_inner,
            text="• 100 <= N <= 100,000 scaling inputs\n• Time Limit: 2.0s per test execution\n• Execution Sandbox: Isolated Multiprocessing Daemon\n• TLE Trigger: Empirical scaling exponent p > target Big-O",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            wraplength=init_wrap,
            justify="left",
            anchor="w",
        )
        self.q_const_body.pack(fill="x")

        # 5. "Why this matters in OA" Interview Hint Box
        hint_box = ctk.CTkFrame(self._left_scroll, fg_color=COLOR_ACCENT_LIGHT, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        hint_box.pack(fill="x")
        h_inner = ctk.CTkFrame(hint_box, fg_color="transparent")
        h_inner.pack(fill="x", padx=12, pady=10)

        self.q_hint_title = ctk.CTkLabel(
            h_inner,
            text="💡 WHY THIS MATTERS IN TECHNICAL OA:",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_ACCENT_INDIGO,
            wraplength=init_wrap,
            justify="left",
            anchor="w",
        )
        self.q_hint_title.pack(fill="x")

        self.q_hint_body = ctk.CTkLabel(
            h_inner,
            text="In campus technical rounds (Amazon, TCS Digital, Zoho), correct logic that runs too slowly causes Time Limit Exceeded (TLE) and immediate elimination. This sandbox benchmarks your code across scaling sizes to prove whether your algorithm is truly fast enough to pass!",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_PRIMARY,
            wraplength=init_wrap,
            justify="left",
            anchor="w",
        )
        self.q_hint_body.pack(fill="x", pady=(4, 0))

        # Dynamic auto-wrap listener on frame resize / zoom with DPI & widget scaling correction
        self._left_wrap_labels = [
            self.q_desc_label,
            self.q_goal_label,
            self.q_const_title,
            self.q_const_body,
            self.q_hint_title,
            self.q_hint_body,
        ]

        def _on_left_resize(event: Optional[Any] = None) -> None:
            self._update_left_wraplengths()

        self._left_scroll.bind("<Configure>", _on_left_resize, add="+")
        # Initial sizing trigger
        self.after(50, self._update_left_wraplengths)

    def _build_editor_and_console_pane(self, parent: ctk.CTkFrame) -> None:
        """Constructs right LeetCode studio: Python editor on top, tabbed console on bottom."""
        right_container = ctk.CTkFrame(parent, fg_color="transparent")
        right_container.grid(row=0, column=1, sticky="nsew", padx=(6, 4), pady=4)
        right_container.grid_rowconfigure(0, weight=6, minsize=240)  # Editor Card
        right_container.grid_rowconfigure(1, weight=5, minsize=180)  # Tabbed Console Card
        right_container.grid_columnconfigure(0, weight=1)

        # ---------------- Top: Code Editor Studio ----------------
        editor_card = create_card(right_container)
        editor_card.grid(row=0, column=0, sticky="nsew", pady=(0, 6))

        e_inner = ctk.CTkFrame(editor_card, fg_color="transparent")
        e_inner.pack(fill="both", expand=True, padx=12, pady=10)

        # 1. Row 1 (Top): Template, Claimed Big-O, and Font Zoom Controls
        row1 = ctk.CTkFrame(e_inner, fg_color="transparent")
        row1.pack(side="top", fill="x", pady=(0, 4))

        ctk.CTkLabel(row1, text="Template:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=(0, 4))
        self.template_menu = ctk.CTkOptionMenu(
            row1,
            values=list(SANDBOX_TEMPLATES.keys()),
            command=self._on_template_selected,
            width=190,
            font=FONT_SMALL,
        )
        self.template_menu.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(row1, text="Claimed:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=(0, 4))
        self.claimed_menu = ctk.CTkOptionMenu(
            row1,
            values=["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)"],
            width=90,
            font=FONT_SMALL_BOLD,
        )
        self.claimed_menu.set("O(n)")
        self.claimed_menu.pack(side="left")

        # Font Zoom Controls (Top Right)
        font_ctrl = ctk.CTkFrame(row1, fg_color="transparent")
        font_ctrl.pack(side="right")

        ctk.CTkLabel(font_ctrl, text="Font:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=(0, 3))

        self.font_down_btn = ctk.CTkButton(
            font_ctrl,
            text="A-",
            width=26,
            height=24,
            font=FONT_SMALL_BOLD,
            fg_color=COLOR_CARD,
            text_color=COLOR_TEXT_PRIMARY,
            hover_color=COLOR_CARD_HOVER,
            border_width=1,
            border_color=COLOR_BORDER,
            corner_radius=4,
            command=self._decrease_font,
        )
        self.font_down_btn.pack(side="left", padx=(0, 2))

        self.font_size_label = ctk.CTkLabel(
            font_ctrl,
            text=f"{self._font_size}px",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_ACCENT_BLUE,
            width=32,
        )
        self.font_size_label.pack(side="left", padx=(0, 2))

        self.font_up_btn = ctk.CTkButton(
            font_ctrl,
            text="A+",
            width=26,
            height=24,
            font=FONT_SMALL_BOLD,
            fg_color=COLOR_CARD,
            text_color=COLOR_TEXT_PRIMARY,
            hover_color=COLOR_CARD_HOVER,
            border_width=1,
            border_color=COLOR_BORDER,
            corner_radius=4,
            command=self._increase_font,
        )
        self.font_up_btn.pack(side="left", padx=(0, 2))

        self.font_reset_btn = ctk.CTkButton(
            font_ctrl,
            text="↺",
            width=24,
            height=24,
            font=FONT_SMALL_BOLD,
            fg_color=COLOR_CARD,
            text_color=COLOR_TEXT_SECONDARY,
            hover_color=COLOR_CARD_HOVER,
            border_width=1,
            border_color=COLOR_BORDER,
            corner_radius=4,
            command=self._reset_font,
        )
        self.font_reset_btn.pack(side="left")

        # 2. Row 2 (Top): Code Mode Selector
        row2 = ctk.CTkFrame(e_inner, fg_color="transparent")
        row2.pack(side="top", fill="x", pady=(2, 4))

        ctk.CTkLabel(row2, text="Code Mode:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=(0, 4))

        self._mode_buttons = {}
        modes = [
            ("skeleton", "✍️ Starter Skeleton"),
            ("naive", "⚠️ Naive Trap O(N²)"),
            ("optimal", "💡 Model Solution"),
        ]

        for m_key, m_label in modes:
            btn = ctk.CTkButton(
                row2,
                text=m_label,
                font=FONT_SMALL_BOLD,
                fg_color=COLOR_ACCENT_LIGHT if m_key == "skeleton" else COLOR_CARD,
                text_color=COLOR_ACCENT_BLUE if m_key == "skeleton" else COLOR_TEXT_SECONDARY,
                hover_color=COLOR_CARD_HOVER,
                border_width=1,
                border_color=COLOR_BORDER,
                corner_radius=RADIUS_BUTTON,
                height=26,
                command=lambda k=m_key: self._set_code_mode(k),
            )
            btn.pack(side="left", padx=(0, 4))
            self._mode_buttons[m_key] = btn

        self.mode_status_badge = create_badge(row2, text=" ✍️ Practice ", variant="info")
        self.mode_status_badge.pack(side="right")

        # 3. Bottom Execution Controls Row (PACKED AT BOTTOM FIRST so it is NEVER clipped!)
        row3 = ctk.CTkFrame(e_inner, fg_color="transparent")
        row3.pack(side="bottom", fill="x", pady=(4, 0))

        # Scales input
        s_box = ctk.CTkFrame(row3, fg_color="transparent")
        s_box.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(s_box, text="Test Input Sizes N:", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.scales_entry = create_entry(s_box, placeholder_text="100, 200, 400, 800", width=140)
        self.scales_entry.insert(0, "100, 200, 400, 800")
        self.scales_entry.pack(anchor="w")

        # Timeout input
        t_box = ctk.CTkFrame(row3, fg_color="transparent")
        t_box.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(t_box, text="Timeout (s):", font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.timeout_entry = create_entry(t_box, placeholder_text="2.0", width=55)
        self.timeout_entry.insert(0, "2.0")
        self.timeout_entry.pack(anchor="w")

        # Run Button
        self.run_btn = create_button(
            row3,
            text="⚡ Run Benchmark & Measure Speed",
            variant="primary",
            command=self.run_benchmark_action,
            height=32,
        )
        self.run_btn.pack(side="left", pady=(10, 0))

        # 4. Python Code Textbox (Fills all available vertical space between Row 2 and Row 3)
        self.code_editor = ctk.CTkTextbox(
            e_inner,
            font=(FONT_FAMILY_CODE, self._font_size),
            fg_color=COLOR_BG,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=8,
            height=120,
            wrap="none",
        )
        self.code_editor.pack(side="top", fill="both", expand=True, pady=(2, 4))

        # Bind zoom and font shortcuts
        for target in [self.code_editor, getattr(self.code_editor, "_textbox", None)]:
            if target is not None:
                target.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)
                target.bind("<Control-plus>", self._increase_font)
                target.bind("<Control-equal>", self._increase_font)
                target.bind("<Control-KP_Add>", self._increase_font)
                target.bind("<Control-minus>", self._decrease_font)
                target.bind("<Control-KP_Subtract>", self._decrease_font)
                target.bind("<Control-0>", self._reset_font)
                target.bind("<Control-Key-0>", self._reset_font)

        # ---------------- Bottom: Tabbed LeetCode Console ----------------
        console_card = create_card(right_container)
        console_card.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        c_inner = ctk.CTkFrame(console_card, fg_color="transparent")
        c_inner.pack(fill="both", expand=True, padx=12, pady=8)

        # Tab Bar Header
        tab_bar = ctk.CTkFrame(c_inner, fg_color="transparent")
        tab_bar.pack(fill="x", pady=(0, 6))

        self._console_tabs = {}
        self._active_tab = "curve"

        tabs_spec = [
            ("curve", "📈 Scaling Curve"),
            ("table", "⏱️ Benchmark Table"),
            ("verdict", "💡 Hiring Verdict"),
        ]

        for tab_id, tab_label in tabs_spec:
            btn = ctk.CTkButton(
                tab_bar,
                text=tab_label,
                font=FONT_SMALL_BOLD,
                fg_color=COLOR_ACCENT_LIGHT if tab_id == "curve" else "transparent",
                text_color=COLOR_ACCENT_BLUE if tab_id == "curve" else COLOR_TEXT_SECONDARY,
                hover_color=COLOR_CARD_HOVER,
                corner_radius=RADIUS_BUTTON,
                height=28,
                command=lambda tid=tab_id: self._switch_console_tab(tid),
            )
            btn.pack(side="left", padx=(0, 6))
            self._console_tabs[tab_id] = btn

        # Tab Content Container
        self.tab_container = ctk.CTkFrame(c_inner, fg_color="transparent")
        self.tab_container.pack(fill="both", expand=True)
        self.tab_container.grid_rowconfigure(0, weight=1)
        self.tab_container.grid_columnconfigure(0, weight=1)

        # Tab 1: Curve Frame
        self.curve_frame = ctk.CTkFrame(self.tab_container, fg_color="transparent")
        self.curve_frame.grid(row=0, column=0, sticky="nsew")

        self.canvas = tk.Canvas(
            self.curve_frame,
            height=140,
            bg=COLOR_CARD,
            bd=0,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )
        self.canvas.pack(fill="both", expand=True, pady=(0, 4))

        summary_row = ctk.CTkFrame(self.curve_frame, fg_color="transparent")
        summary_row.pack(fill="x")

        self.exponent_label = ctk.CTkLabel(
            summary_row,
            text="Scaling Exponent: p = --  |  Fit Confidence: R² = --",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        )
        self.exponent_label.pack(side="left")

        self.empirical_big_o_badge = create_badge(summary_row, text="Complexity: --", variant="info")
        self.empirical_big_o_badge.pack(side="right")

        # Tab 2: Table Frame
        self.table_frame = ctk.CTkScrollableFrame(self.tab_container, fg_color="transparent")
        self.table_frame.grid(row=0, column=0, sticky="nsew")

        tbl_hdr = ctk.CTkFrame(self.table_frame, fg_color=COLOR_BG, corner_radius=6)
        tbl_hdr.pack(fill="x", pady=(0, 4))
        cols = [("Input Scale N", 110), ("Elapsed Time (ms)", 130), ("Ratio vs Baseline", 120), ("Status", 80)]
        for c_title, w in cols:
            ctk.CTkLabel(tbl_hdr, text=c_title, font=FONT_SMALL_BOLD, text_color=COLOR_TEXT_SECONDARY, width=w, anchor="w").pack(side="left", padx=6, pady=4)

        self.table_rows_container = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        self.table_rows_container.pack(fill="x")

        # Tab 3: Verdict Frame
        self.verdict_frame = ctk.CTkScrollableFrame(self.tab_container, fg_color="transparent")
        self.verdict_frame.grid(row=0, column=0, sticky="nsew")

        self.status_banner = ctk.CTkFrame(self.verdict_frame, fg_color=COLOR_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        self.status_banner.pack(fill="x", pady=(0, 6))

        self.status_label = ctk.CTkLabel(
            self.status_banner,
            text="Ready. Click '⚡ Run Benchmark & Measure Speed' to evaluate complexity.",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_SECONDARY,
        )
        self.status_label.pack(padx=12, pady=6, anchor="w")

        self.alert_container = ctk.CTkFrame(self.verdict_frame, fg_color="transparent")
        self.alert_container.pack(fill="x")

        # Default show curve tab
        self._switch_console_tab("curve")

    def _switch_console_tab(self, tab_id: str) -> None:
        """Elevates selected console tab frame and updates button styling."""
        frames = {
            "curve": self.curve_frame,
            "table": self.table_frame,
            "verdict": self.verdict_frame,
        }
        if tab_id in frames:
            frames[tab_id].tkraise()
            self._active_tab = tab_id
            for tid, btn in self._console_tabs.items():
                if tid == tab_id:
                    btn.configure(fg_color=COLOR_ACCENT_LIGHT, text_color=COLOR_ACCENT_BLUE)
                else:
                    btn.configure(fg_color="transparent", text_color=COLOR_TEXT_SECONDARY)

    def _set_font_size(self, size: int) -> None:
        """Clamps and updates the code editor font size."""
        self._font_size = max(9, min(24, size))
        if hasattr(self, "font_size_label"):
            self.font_size_label.configure(text=f"{self._font_size}px")
        if hasattr(self, "code_editor"):
            self.code_editor.configure(font=(FONT_FAMILY_CODE, self._font_size))

    def _increase_font(self, event: Optional[Any] = None) -> Optional[str]:
        """Increases font size by 1px (up to 24px)."""
        self._set_font_size(self._font_size + 1)
        return "break" if event else None

    def _decrease_font(self, event: Optional[Any] = None) -> Optional[str]:
        """Decreases font size by 1px (down to 9px)."""
        self._set_font_size(self._font_size - 1)
        return "break" if event else None

    def _reset_font(self, event: Optional[Any] = None) -> Optional[str]:
        """Resets font size to default 12px."""
        self._set_font_size(12)
        return "break" if event else None

    def _on_ctrl_mousewheel(self, event: Any) -> str:
        """Handles Ctrl+MouseWheel zooming."""
        delta = getattr(event, "delta", 0)
        if delta > 0:
            self._increase_font()
        elif delta < 0:
            self._decrease_font()
        return "break"

    def _set_code_mode(self, mode: str) -> None:
        """Switches between starter skeleton, naive trap, and optimal model solution."""
        self._code_mode = mode
        template_name = self.template_menu.get() if hasattr(self, "template_menu") else "Linear Sum (O(n))"
        tmpl = SANDBOX_TEMPLATES.get(template_name, {})
        code_text = tmpl.get(mode, tmpl.get("code", ""))

        if hasattr(self, "code_editor"):
            self.code_editor.delete("1.0", "end")
            self.code_editor.insert("1.0", code_text)

        # Update button highlights
        if hasattr(self, "_mode_buttons"):
            for m_key, btn in self._mode_buttons.items():
                if m_key == mode:
                    btn.configure(fg_color=COLOR_ACCENT_LIGHT, text_color=COLOR_ACCENT_BLUE)
                else:
                    btn.configure(fg_color=COLOR_CARD, text_color=COLOR_TEXT_SECONDARY)

        # Update mode badge
        if hasattr(self, "mode_status_badge"):
            badge_map = {
                "skeleton": (" ✍️ Practice ", COLOR_ACCENT_LIGHT, COLOR_ACCENT_BLUE),
                "naive": (" ⚠️ Naive Trap ", COLOR_WARNING_LIGHT, COLOR_WARNING),
                "optimal": (" 💡 Solution ", COLOR_SUCCESS_LIGHT, COLOR_SUCCESS),
            }
            lbl, bg, fg = badge_map.get(mode, (" ✍️ Practice ", COLOR_ACCENT_LIGHT, COLOR_ACCENT_BLUE))
            self.mode_status_badge.configure(text=lbl, fg_color=bg, text_color=fg)

    def _on_template_selected(self, template_name: str) -> None:
        """Loads chosen algorithm template into the editor in skeleton practice mode."""
        self._load_template(template_name, mode="skeleton")

    def _load_template(self, template_name: str, mode: Optional[str] = None) -> None:
        """Helper to populate code and claimed Big-O and update Question Card."""
        tmpl = SANDBOX_TEMPLATES.get(template_name)
        if tmpl:
            if hasattr(self, "template_menu"):
                self.template_menu.set(template_name)
            target_mode = mode or getattr(self, "_code_mode", "skeleton")
            self._set_code_mode(target_mode)
            self.claimed_menu.set(tmpl["claimed"])

            if hasattr(self, "q_title_label"):
                title = tmpl.get("title", template_name)
                self.q_title_label.configure(text=f"📌 Challenge: {title}")
                self.q_desc_label.configure(text=tmpl.get("description", "Write an optimal solution in solve(n)."))
                self.q_diff_badge.configure(text=f" {tmpl.get('difficulty', 'Medium')} ")
                comps = ", ".join(tmpl.get("companies", ["Top Tech"]))
                self.q_company_badge.configure(text=f" 🏢 {comps} ")
                self.q_goal_label.configure(text=f"🎯 Target Goal: {tmpl.get('goal', 'Optimize algorithm complexity.')}")
                self._update_left_wraplengths()

    def on_show(self) -> None:
        """Called when CodingSandbox becomes active view. Ensures dynamic wrapping matches current window/zoom scale."""
        self._update_left_wraplengths()

    def _update_left_wraplengths(self) -> None:
        """
        Dynamically recomputes and applies DPI and widget-scaling aware wraplengths.
        Corrects for Tkinter physical screen pixels vs. CustomTkinter logical units
        so text never cuts off regardless of window dimensions, DPI, or global zoom factor.
        """
        if not hasattr(self, "_left_scroll") or not hasattr(self, "q_desc_label"):
            return

        canvas = getattr(self._left_scroll, "_parent_canvas", None)
        canvas_w = canvas.winfo_width() if canvas is not None else 0
        if canvas_w <= 10:
            canvas_w = self._left_scroll.winfo_width()
        if canvas_w <= 10:
            return

        # CustomTkinter scaling factor (combines OS DPI and app zoom_factor)
        scaling = 1.0
        if hasattr(self.q_desc_label, "_get_widget_scaling"):
            scaling = self.q_desc_label._get_widget_scaling()
        if scaling <= 0.05:
            scaling = 1.0

        # Available physical space inside inner card frames:
        # Accounts for vertical scrollbar (~18px), card outer margin (~8px), and inner frame padx (~24px)
        # Total margins = 18 + 8 + 24 + 14 (breathing safety) = 64px
        phys_inner_wrap = max(100, canvas_w - 64)
        # Convert physical pixels to logical units for CustomTkinter (CTkLabel internally multiplies by scaling)
        logical_inner_wrap = max(50, int(phys_inner_wrap / scaling))

        # Title label is in the root scroll frame (no inner card padx)
        phys_title_wrap = max(120, canvas_w - 38)
        logical_title_wrap = max(60, int(phys_title_wrap / scaling))

        if hasattr(self, "q_title_label"):
            try:
                self.q_title_label.configure(wraplength=logical_title_wrap)
            except Exception:
                pass

        if hasattr(self, "_left_wrap_labels"):
            for lbl in self._left_wrap_labels:
                try:
                    lbl.configure(wraplength=logical_inner_wrap)
                except Exception:
                    pass

    def run_benchmark_action(self) -> None:
        """Initiates isolated multiprocessing execution on a non-blocking background thread."""
        code_str = self.code_editor.get("1.0", "end").strip()
        claimed_big_o = self.claimed_menu.get().strip()

        # Parse scales
        scales_str = self.scales_entry.get().strip()
        try:
            scales = [int(s.strip()) for s in scales_str.replace(";", ",").split(",") if s.strip()]
        except ValueError:
            scales = [100, 200, 400, 800]

        # Parse timeout
        try:
            timeout_sec = float(self.timeout_entry.get().strip())
        except ValueError:
            timeout_sec = 2.0

        if not code_str:
            self.status_label.configure(text="Please write Python code to benchmark.", text_color=COLOR_DANGER)
            return

        # Update UI to executing state without freezing mainloop
        self.run_btn.configure(state="disabled", text="⏳ Executing Sandbox...")
        self.status_label.configure(text="Benchmarking in isolated child multiprocessing sandbox...", text_color=COLOR_ACCENT_BLUE)

        # Worker thread
        def worker_target() -> None:
            try:
                res = run_empirical_profile(code_str, scales, timeout_sec=timeout_sec)
                # Divergence detection
                div_res = detect_divergence(claimed_big_o, res.get("estimated_p", 1.0))
            except Exception as ex:
                logger.exception("Sandbox execution exception: %s", ex)
                res = {"points": [], "estimated_p": 1.0, "empirical_big_o": "O(?)", "r_squared": 0.0, "timed_out": False}
                div_res = {"divergence": True, "diagnostic": str(ex), "alignment_score": 0.0}

            # Dispatch back to Tkinter main thread
            try:
                self.after(0, lambda: self._on_benchmark_completed(res, div_res, claimed_big_o))
            except Exception as ex:
                logger.debug("Error dispatching benchmark callback: %s", ex)

        t = threading.Thread(target=worker_target, name="SandboxRunnerThread", daemon=True)
        t.start()

    def _on_benchmark_completed(self, res: dict, div_res: dict, claimed_big_o: str) -> None:
        """Dispatched on Tkinter main thread when isolated benchmark completes."""
        # Update button and auto-elevate tab
        self.run_btn.configure(state="normal", text="⚡ Run Benchmark & Measure Speed")

        timed_out = res.get("timed_out", False)
        timeout_scale = res.get("timeout_scale")

        if timed_out:
            self.status_label.configure(text=f"Process terminated cleanly after timeout on scale N={timeout_scale}.", text_color=COLOR_DANGER)
            if hasattr(self, "_switch_console_tab"):
                self._switch_console_tab("verdict")
        else:
            self.status_label.configure(text="Benchmark complete across all input scales.", text_color=COLOR_SUCCESS)

        # 1. Update Divergence Alert Banner
        for widget in self.alert_container.winfo_children():
            widget.destroy()

        is_div = div_res.get("divergence", False)
        diagnostic = div_res.get("diagnostic", "")
        est_p = res.get("estimated_p", 0.0)
        emp_big_o = res.get("empirical_big_o", "O(?)")

        if timed_out:
            alert_card = create_card(self.alert_container, fg_color=COLOR_DANGER_LIGHT, border_color=COLOR_DANGER_BORDER)
            alert_card.pack(fill="x", pady=2)
            ctk.CTkLabel(
                alert_card,
                text=f"✗ EXECUTION TIMEOUT: Solution exceeded time limit on N={timeout_scale}. Watch out for infinite loops or unmemoized branching in technical interviews.",
                font=FONT_BODY_BOLD,
                text_color=COLOR_DANGER,
                wraplength=480,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=12, pady=10)
        elif is_div:
            if hasattr(self, "_switch_console_tab"):
                self._switch_console_tab("verdict")
            alert_card = create_card(self.alert_container, fg_color=COLOR_DANGER_LIGHT, border_color=COLOR_DANGER_BORDER)
            alert_card.pack(fill="x", pady=2)
            ctk.CTkLabel(
                alert_card,
                text=f"⚠️ DIVERGENCE DETECTED: Expected {claimed_big_o}, but runtime scaled at {emp_big_o} (p = {est_p:.2f}). In interviews, this slower complexity may cause Time Limit Exceeded (TLE). {diagnostic}",
                font=FONT_BODY_BOLD,
                text_color=COLOR_DANGER,
                wraplength=480,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=12, pady=10)
        else:
            if hasattr(self, "_switch_console_tab"):
                self._switch_console_tab("curve")
            alert_card = create_card(self.alert_container, fg_color=COLOR_SUCCESS_LIGHT, border_color=COLOR_SUCCESS_BORDER)
            alert_card.pack(fill="x", pady=2)
            ctk.CTkLabel(
                alert_card,
                text=f"✓ OPTIMAL COMPLEXITY: Execution scaling (p = {est_p:.2f}) matches target {claimed_big_o}. Meets technical interview performance standards. {diagnostic}",
                font=FONT_BODY_BOLD,
                text_color=COLOR_SUCCESS,
                wraplength=480,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=12, pady=10)

        # 2. Update Table Rows
        for widget in self.table_rows_container.winfo_children():
            widget.destroy()

        points: List[Tuple[int, float]] = res.get("points", [])
        base_time = points[0][1] if points and points[0][1] > 0 else 1.0

        for idx, (scale_n, elapsed_s) in enumerate(points):
            elapsed_ms = elapsed_s * 1000.0
            ratio = elapsed_s / base_time if base_time > 0 else 1.0

            r_frame = ctk.CTkFrame(self.table_rows_container, fg_color="transparent")
            r_frame.pack(fill="x", pady=1)

            ctk.CTkLabel(r_frame, text=f"N = {scale_n}", font=FONT_SMALL, text_color=COLOR_TEXT_PRIMARY, width=110, anchor="w").pack(side="left", padx=6)
            ctk.CTkLabel(r_frame, text=f"{elapsed_ms:.4f} ms", font=FONT_SMALL, text_color=COLOR_TEXT_PRIMARY, width=130, anchor="w").pack(side="left", padx=6)
            ctk.CTkLabel(r_frame, text=f"{ratio:.2f}x", font=FONT_SMALL, text_color=COLOR_ACCENT_BLUE, width=120, anchor="w").pack(side="left", padx=6)
            ctk.CTkLabel(r_frame, text="SUCCESS", font=FONT_SMALL_BOLD, text_color=COLOR_SUCCESS, width=80, anchor="w").pack(side="left", padx=6)

        # 3. Redraw Canvas Curve Plot
        self._render_curve_plot(points)

        # 4. Update Exponent Summary Card
        r_sq = res.get("r_squared", 0.0)
        self.exponent_label.configure(text=f"Power Exponent: p = {est_p:.3f}  |  Fit Confidence: R² = {r_sq:.4f}")
        self.empirical_big_o_badge.configure(text=f" Classified Empirical Complexity: {emp_big_o} ")

    def _render_curve_plot(self, points: List[Tuple[int, float]]) -> None:
        """Plots empirical (N, elapsed ms) coordinates on the Tkinter canvas with smooth spline and dark tooltip."""
        canvas = self.canvas
        canvas.delete("all")

        if not points:
            canvas.create_text(200, 80, text="No benchmark points to plot.", fill=COLOR_TEXT_SECONDARY, font=(FONT_BODY[0], 10))
            return

        c_w = 400
        c_h = 150
        pad_x = 44
        pad_y = 26

        # Extract values in ms
        n_vals = [p[0] for p in points]
        ms_vals = [p[1] * 1000.0 for p in points]

        min_n, max_n = min(n_vals), max(n_vals)
        min_ms, max_ms = min(ms_vals), max(ms_vals)
        if max_ms == min_ms:
            max_ms = min_ms + 1.0
        if max_n == min_n:
            max_n = min_n + 1

        # Draw subtle grid horizontal lines
        for y_tick_pct in [0.25, 0.5, 0.75]:
            grid_y = pad_y + y_tick_pct * (c_h - 2 * pad_y)
            canvas.create_line(pad_x, grid_y, c_w - pad_x, grid_y, fill=COLOR_BORDER, width=1, dash=(2, 4))

        # Draw axes
        canvas.create_line(pad_x, c_h - pad_y, c_w - pad_x, c_h - pad_y, fill=COLOR_BORDER, width=1)
        canvas.create_line(pad_x, pad_y, pad_x, c_h - pad_y, fill=COLOR_BORDER, width=1)

        # Map to canvas coordinates
        plot_coords = []
        for n, ms in zip(n_vals, ms_vals):
            px = pad_x + ((n - min_n) / (max_n - min_n)) * (c_w - 2 * pad_x)
            py = (c_h - pad_y) - ((ms - min_ms) / (max_ms - min_ms)) * (c_h - 2 * pad_y)
            plot_coords.append((px, py, n, ms))

        # Soft area wash underneath the curve (ClientRidge Warm Studio style)
        if len(plot_coords) >= 2:
            poly_coords = [plot_coords[0][0], c_h - pad_y]
            for px, py, _, _ in plot_coords:
                poly_coords.extend([px, py])
            poly_coords.extend([plot_coords[-1][0], c_h - pad_y])
            canvas.create_polygon(
                *poly_coords,
                fill=COLOR_ACCENT_LIGHT,
                outline="",
                smooth=True if len(plot_coords) >= 3 else False,
            )

        # Draw smooth spline curve
        if len(plot_coords) >= 2:
            flat_pts = []
            for px, py, _, _ in plot_coords:
                flat_pts.extend([px, py])
            canvas.create_line(
                *flat_pts,
                fill=COLOR_ACCENT_CORAL,
                width=3,
                smooth=True if len(plot_coords) >= 3 else False,
            )

        # Draw point dots and labels
        for px, py, n, ms in plot_coords:
            canvas.create_oval(px - 5, py - 5, px + 5, py + 5, fill=COLOR_CARD, outline=COLOR_ACCENT_CORAL, width=2)
            canvas.create_oval(px - 2, py - 2, px + 2, py + 2, fill=COLOR_ACCENT_CORAL, outline="")
            canvas.create_text(px, c_h - pad_y + 12, text=str(n), font=(FONT_SMALL[0], 8, "bold"), fill=COLOR_TEXT_SECONDARY)

        # Floating Dark Milestone Tooltip (ClientRidge style)
        if plot_coords:
            # Anchor tooltip on the last point or point with highest runtime
            target_pt = max(plot_coords, key=lambda pt: pt[3])
            t_px, t_py, t_n, t_ms = target_pt
            tt_w, tt_h = 110, 22
            tt_x1 = max(pad_x, min(c_w - pad_x - tt_w, t_px - tt_w // 2))
            tt_x2 = tt_x1 + tt_w
            tt_y2 = max(pad_y - 10, t_py - 12)
            tt_y1 = max(4, tt_y2 - tt_h)

            # Milestone vertical dashed guideline
            canvas.create_line(t_px, t_py, t_px, tt_y2, fill=COLOR_ACCENT_CORAL, width=1, dash=(2, 2))

            # Tooltip capsule (Dark obsidian #1E2024)
            tr = tt_h / 2.0
            canvas.create_oval(tt_x1, tt_y1, tt_x1 + 2 * tr, tt_y2, fill=COLOR_ACCENT_DARK, outline="")
            canvas.create_oval(tt_x2 - 2 * tr, tt_y1, tt_x2, tt_y2, fill=COLOR_ACCENT_DARK, outline="")
            canvas.create_rectangle(tt_x1 + tr, tt_y1, tt_x2 - tr, tt_y2, fill=COLOR_ACCENT_DARK, outline="")

            # Tooltip text
            canvas.create_text(
                (tt_x1 + tt_x2) / 2,
                (tt_y1 + tt_y2) / 2,
                text=f"N={t_n} • {t_ms:.2f}ms",
                fill=COLOR_CARD,
                font=(FONT_SMALL[0], 8, "bold"),
            )
