"""
Skillora Main Application Shell (client/gui/app_window.py)
Persistent sidebar navigation, non-blocking frame switcher, socket status indicator,
and thread-safe Tkinter queue polling bridge.
"""

import json
import logging
import os
from typing import Any, Callable, Dict, Optional, Type
import customtkinter as ctk

from client.gui.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_CORAL,
    COLOR_ACCENT_DARK,
    COLOR_ACCENT_LIGHT,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_CARD_HOVER,
    COLOR_DANGER,
    COLOR_DANGER_LIGHT,
    COLOR_DANGER_BORDER,
    COLOR_NAV_ACTIVE_BG,
    COLOR_NAV_ACTIVE_TEXT,
    COLOR_NAV_HOVER,
    COLOR_NAV_IDLE,
    COLOR_NAV_IDLE_TEXT,
    COLOR_SIDEBAR_BG,
    COLOR_SIDEBAR_BORDER,
    COLOR_SUCCESS,
    COLOR_SUCCESS_LIGHT,
    COLOR_SUCCESS_BORDER,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING,
    COLOR_WARNING_LIGHT,
    COLOR_WARNING_BORDER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_DISPLAY,
    FONT_HEADING,
    FONT_SMALL,
    FONT_SMALL_BOLD,
    FONT_TITLE,
    RADIUS_BADGE,
    RADIUS_BUTTON,
    RADIUS_CARD,
    RADIUS_INPUT,
    RADIUS_PILL,
    create_button,
    enforce_light_theme,
)
from client.network.socket_client import SocketClient

logger = logging.getLogger("skillora.app_window")

# Default demo student profile for session state and offline fallback
DEFAULT_STUDENT_PROFILE = {
    "user_id": 1,
    "username": "aryan.sharma",
    "full_name": "Aryan Sharma",
    "branch": "CSE",
    "cgpa": 8.42,
    "backlogs": 0,
    "skills": ["Python", "DSA", "SQL", "Computer Networks", "System Design"],
    "dimension_scores": {
        "aptitude": 82.0,
        "coding": 70.0,
        "technical": 78.0,
        "communication": 85.0,
        "academic": 84.2,  # 8.42 * 10.0
    },
    "target_tier": "Tier1",
}


class BaseView(ctk.CTkFrame):
    """
    Abstract base class for all Skillora view screens.
    Guarantees access to app_window, socket_client, session_data, and lifecycle hooks.
    """

    def __init__(
        self,
        parent: Any,
        app_window: "AppWindow",
        socket_client: Optional[SocketClient] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, fg_color=COLOR_BG, **kwargs)
        self.app_window = app_window
        self.socket_client = socket_client
        self._build_ui()

    def _build_ui(self) -> None:
        """Override in subclasses to build widget tree."""
        pass

    def on_show(self) -> None:
        """Invoked when view is elevated to foreground via tkraise()."""
        pass

    def on_hide(self) -> None:
        """Invoked when navigating away from this view."""
        pass

    def on_connection_changed(self, connected: bool) -> None:
        """Invoked when server socket connection state changes."""
        pass

    @property
    def session_data(self) -> dict:
        """Convenience accessor to the app window's shared session state."""
        return self.app_window.session_data

    def send_request(
        self,
        action: str,
        payload: dict,
        callback: Callable[[dict], None],
        error_callback: Optional[Callable[[dict], None]] = None,
        timeout: float = 15.0,
    ) -> Optional[str]:
        """
        Sends an asynchronous request via SocketClient if connected.
        Returns request_id if sent, or None if offline / disconnected.
        """
        if self.socket_client and self.socket_client.is_connected():
            return self.socket_client.send_request(
                action=action,
                payload=payload,
                callback=callback,
                error_callback=error_callback,
                timeout=timeout,
            )
        return None


class AppWindow:
    """
    Skillora Desktop Client Shell.
    Manages main window geometry, persistent sidebar, dynamic content container,
    view switching via frame raising, and socket bridge binding.
    """

    NAV_ITEMS = [
        ("dashboard", "📊  Overview & Readiness", ""),
        ("company", "🏢  Target Companies & Cutoffs", "10"),
        ("math_studio", "🧮  Round 1: Aptitude & Quant", "42"),
        ("coding_sandbox", "⚡  Round 2: Coding & Big-O Lab", "5"),
        ("interview", "🎯  Round 3: Mock Interview", "8"),
    ]

    VIEW_BREADCRUMBS = {
        "dashboard": "Overview & Readiness",
        "company": "Target Companies & Placement Cutoffs",
        "math_studio": "Round 1: Aptitude & Quantitative Drills",
        "coding_sandbox": "Round 2: Coding & Big-O Benchmark Lab",
        "interview": "Round 3: Technical & HR Mock Interview",
    }

    def __init__(
        self,
        root: Optional[ctk.CTk] = None,
        socket_client: Optional[SocketClient] = None,
        mock_mode: bool = False,
        offline_mode: bool = False,
    ) -> None:
        enforce_light_theme()
        self.root = root or ctk.CTk()
        self.socket_client = socket_client
        self.mock_mode = mock_mode
        self.offline_mode = offline_mode
        self.session_data: Dict[str, Any] = dict(DEFAULT_STUDENT_PROFILE)

        self._current_view_key: Optional[str] = None
        self._views: Dict[str, BaseView] = {}
        self._nav_buttons: Dict[str, ctk.CTkButton] = {}

        # Global Web-Style On-Demand Zoom State
        self._zoom_factor: float = self._load_zoom_preference()
        self._zoom_hud_timer: Optional[str] = None
        self._zoom_hud: Optional[ctk.CTkFrame] = None

        if self._zoom_factor != 1.0:
            try:
                ctk.set_widget_scaling(self._zoom_factor)
            except Exception:
                pass

        self._setup_window()
        self._build_layout()
        self._setup_global_zoom_shortcuts()
        self._init_network_bridge()

    def _setup_window(self) -> None:
        """Configures responsive window dimensions, minimum limits, and center positioning."""
        self.root.title("Skillora — Campus Placement Preparation & Evaluation System")
        self.root.configure(fg_color=COLOR_BG)

        # Responsive window sizing: 1200x800 default, 1024x700 min
        width, height = 1200, 800
        min_w, min_h = 1024, 700
        self.root.minsize(min_w, min_h)

        try:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            pos_x = max(0, (screen_w - width) // 2)
            pos_y = max(0, (screen_h - height) // 2)
            self.root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        except Exception:
            self.root.geometry(f"{width}x{height}")

    def _build_layout(self) -> None:
        """Constructs 2-column shell: Column 0 Sidebar (240px), Column 1 Content Area."""
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=0, minsize=240)
        self.root.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_content_area()

    def _build_sidebar(self) -> None:
        """Constructs persistent left navigation sidebar."""
        self.sidebar_frame = ctk.CTkFrame(
            self.root,
            width=240,
            corner_radius=0,
            fg_color=COLOR_SIDEBAR_BG,
            border_color=COLOR_SIDEBAR_BORDER,
            border_width=1,
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(2, weight=1)  # Spacer pushes status pill to bottom
        self.sidebar_frame.grid_columnconfigure(0, weight=1)

        # 1. Branding Header (Linear style)
        brand_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=20, pady=(20, 14), sticky="ew")

        brand_top = ctk.CTkFrame(brand_frame, fg_color="transparent")
        brand_top.pack(fill="x")

        brand_title = ctk.CTkLabel(
            brand_top,
            text="✦ SKILLORA",
            font=FONT_DISPLAY,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        )
        brand_title.pack(side="left")

        # Linear-style micro-pill
        os_pill = ctk.CTkFrame(
            brand_top,
            fg_color=COLOR_ACCENT_LIGHT,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=RADIUS_BADGE,
        )
        os_pill.pack(side="left", padx=(8, 0))

        ctk.CTkLabel(
            os_pill,
            text="PLACEMENT OS",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_ACCENT_BLUE,
        ).pack(padx=6, pady=1)

        brand_subtitle = ctk.CTkLabel(
            brand_frame,
            text="Campus Interview Preparation Coach",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        )
        brand_subtitle.pack(fill="x", pady=(3, 0))

        # Thin divider
        divider = ctk.CTkFrame(self.sidebar_frame, height=1, fg_color=COLOR_BORDER)
        divider.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))

        # 2. Navigation Buttons Container
        self.nav_container = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.nav_container.grid(row=2, column=0, sticky="new", padx=12)

        for idx, item in enumerate(self.NAV_ITEMS):
            key = item[0]
            label = item[1]
            badge = item[2] if len(item) > 2 else ""
            btn_text = f"{label}   [{badge}]" if badge else label
            btn = ctk.CTkButton(
                self.nav_container,
                text=btn_text,
                font=FONT_BODY,
                fg_color=COLOR_NAV_IDLE,
                hover_color=COLOR_NAV_HOVER,
                text_color=COLOR_NAV_IDLE_TEXT,
                corner_radius=RADIUS_BUTTON,
                height=40,
                anchor="w",
                command=lambda k=key: self.navigate_to(k),
            )
            btn.pack(fill="x", pady=3)
            self._nav_buttons[key] = btn

        # 3. Bottom Connection Status Section
        bottom_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, sticky="sew", padx=16, pady=16)

        self.status_pill = ctk.CTkFrame(
            bottom_frame,
            corner_radius=RADIUS_PILL,
            fg_color=COLOR_WARNING_LIGHT,
            border_color=COLOR_WARNING_BORDER,
            border_width=1,
            height=30,
        )
        self.status_pill.pack(fill="x", pady=(0, 6))

        self.status_label = ctk.CTkLabel(
            self.status_pill,
            text="● Connecting...",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_WARNING,
        )
        self.status_label.pack(padx=12, pady=4)

        info_label = ctk.CTkLabel(
            bottom_frame,
            text="v1.0 • 100% Offline Capable",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
        )
        info_label.pack()

    def _build_top_header(self) -> None:
        """Constructs the sleek warm studio top command header with obsidian search bar and candidate chip."""
        self.top_header = ctk.CTkFrame(
            self.content_area,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=0,
            height=48,
        )
        self.top_header.grid(row=0, column=0, sticky="ew")
        self.top_header.grid_propagate(False)

        # Left: Clean Breadcrumbs
        bc_frame = ctk.CTkFrame(self.top_header, fg_color="transparent")
        bc_frame.pack(side="left", padx=18, pady=8)

        ctk.CTkLabel(
            bc_frame,
            text="Skillora",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(side="left")

        ctk.CTkLabel(
            bc_frame,
            text=" / ",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(side="left", padx=3)

        ctk.CTkLabel(
            bc_frame,
            text="Placement Season 2026",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_SECONDARY,
        ).pack(side="left")

        ctk.CTkLabel(
            bc_frame,
            text=" / ",
            font=FONT_SMALL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(side="left", padx=3)

        self.breadcrumb_view = ctk.CTkLabel(
            bc_frame,
            text="Overview & Readiness",
            font=FONT_BODY_BOLD,
            text_color=COLOR_ACCENT_CORAL,
        )
        self.breadcrumb_view.pack(side="left")

        # Right: Candidate Profile Chip + Status Dot
        right_box = ctk.CTkFrame(self.top_header, fg_color="transparent")
        right_box.pack(side="right", padx=16, pady=8)

        # Candidate Profile Chip (Soft Peach Capsule)
        profile_chip = ctk.CTkFrame(
            right_box,
            fg_color=COLOR_ACCENT_LIGHT,
            border_color=COLOR_BORDER,
            border_width=1,
            corner_radius=RADIUS_PILL,
            height=28,
        )
        profile_chip.pack(side="left", padx=(0, 10))

        self.profile_chip_label = ctk.CTkLabel(
            profile_chip,
            text="🎓 Aryan Sharma • Tier 1 Product",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_ACCENT_CORAL,
        )
        self.profile_chip_label.pack(padx=10, pady=3)

        # Top Status Dot
        self.status_dot = ctk.CTkLabel(
            right_box,
            text="● Online",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_SUCCESS,
        )
        self.status_dot.pack(side="left", padx=(4, 0))

    def _build_content_area(self) -> None:
        """Constructs right main content area with top command header, alert banner, and view stack."""
        self.content_area = ctk.CTkFrame(self.root, fg_color=COLOR_BG, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(2, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

        # 1. Top Linear/Vercel Command Bar
        self._build_top_header()

        # 2. Top Offline Alert Banner (hidden by default)
        self.offline_banner = ctk.CTkFrame(
            self.content_area,
            fg_color=COLOR_DANGER_LIGHT,
            border_color=COLOR_DANGER_BORDER,
            border_width=1,
            corner_radius=8,
            height=40,
        )
        banner_content = ctk.CTkFrame(self.offline_banner, fg_color="transparent")
        banner_content.pack(fill="both", expand=True, padx=16, pady=8)

        self.banner_text = ctk.CTkLabel(
            banner_content,
            text="⚠️ Server socket offline (port 9999). Operating in standalone/offline mode.",
            font=FONT_BODY_BOLD,
            text_color=COLOR_DANGER,
        )
        self.banner_text.pack(side="left")

        # Reconnect trigger button in banner
        self.reconnect_btn = create_button(
            banner_content,
            text="Reconnect",
            variant="outline",
            height=28,
            command=self._on_reconnect_clicked,
        )
        self.reconnect_btn.pack(side="right")

        # 3. View Container Frame (holds gridded view frames)
        self.views_container = ctk.CTkFrame(self.content_area, fg_color=COLOR_BG, corner_radius=0)
        self.views_container.grid(row=2, column=0, sticky="nsew", padx=14, pady=(10, 14))
        self.views_container.grid_rowconfigure(0, weight=1)
        self.views_container.grid_columnconfigure(0, weight=1)

        # 4. Floating On-Demand Zoom Capsule HUD (hidden by default)
        self._build_zoom_hud()

    def register_view(self, key: str, view_cls: Type[BaseView]) -> BaseView:
        """Instantiates and registers a view class into the stacked container."""
        view_instance = view_cls(
            parent=self.views_container,
            app_window=self,
            socket_client=self.socket_client,
        )
        # All views stack at row=0, column=0 for zero-flicker tkraise() transitions
        view_instance.grid(row=0, column=0, sticky="nsew")
        self._views[key] = view_instance
        logger.debug("Registered view: %s", key)
        return view_instance

    def navigate_to(self, view_key: str) -> None:
        """Switches active view via tkraise() without recreating widgets."""
        if view_key not in self._views:
            logger.warning("Attempted navigation to unknown view: %s", view_key)
            return

        if self._current_view_key == view_key:
            return

        # Hide current view hook
        if self._current_view_key and self._current_view_key in self._views:
            try:
                self._views[self._current_view_key].on_hide()
            except Exception as ex:
                logger.debug("Error in view on_hide: %s", ex)

        # Elevate new view
        target_view = self._views[view_key]
        target_view.tkraise()
        self._current_view_key = view_key

        # Update breadcrumbs
        if hasattr(self, "breadcrumb_view"):
            view_title = self.VIEW_BREADCRUMBS.get(view_key, view_key.capitalize())
            self.breadcrumb_view.configure(text=view_title)

        # Update sidebar button active styling
        for key, btn in self._nav_buttons.items():
            if key == view_key:
                btn.configure(
                    fg_color=COLOR_NAV_ACTIVE_BG,
                    text_color=COLOR_NAV_ACTIVE_TEXT,
                    font=FONT_BODY_BOLD,
                )
            else:
                btn.configure(
                    fg_color=COLOR_NAV_IDLE,
                    text_color=COLOR_NAV_IDLE_TEXT,
                    font=FONT_BODY,
                )

        # Fire on_show lifecycle hook
        try:
            target_view.on_show()
        except Exception as ex:
            logger.exception("Error in view on_show (%s): %s", view_key, ex)

    def _init_network_bridge(self) -> None:
        """Integrates SocketClient with Tkinter polling and connection listener."""
        if self.socket_client is None:
            self._update_connection_ui("DISCONNECTED", {"reason": "No socket client configured"})
            return

        # Bind non-blocking polling loop to Tk main thread (50ms interval)
        self.socket_client.bind_to_tk(self.root, interval_ms=50)

        # Register status listener for reactive status pill & offline banner updates
        self.socket_client.register_status_listener(self._on_connection_status_changed)

    def _on_connection_status_changed(self, status: str, data: dict) -> None:
        """Dispatched on Tkinter main thread when connection state shifts."""
        self._update_connection_ui(status, data)
        # Broadcast to all registered views
        is_conn = (status == "CONNECTED")
        if is_conn:
            try:
                self.reconnect_btn.configure(text="Reconnect", state="normal")
            except Exception:
                pass

        for view in self._views.values():
            try:
                view.on_connection_changed(is_conn)
            except Exception as ex:
                logger.debug("Error in view on_connection_changed: %s", ex)

        # Seamlessly reload active view data when connection is restored
        if is_conn and self._current_view_key and self._current_view_key in self._views:
            try:
                self._views[self._current_view_key].on_show()
            except Exception as ex:
                logger.debug("Error refreshing active view on reconnect: %s", ex)

    def _update_connection_ui(self, status: str, data: dict) -> None:
        """Updates status pill colors and banner visibility."""
        port = data.get("port", 9999) if isinstance(data, dict) else 9999
        if status == "CONNECTED":
            self.status_pill.configure(fg_color=COLOR_SUCCESS_LIGHT, border_color=COLOR_SUCCESS_BORDER)
            self.status_label.configure(text=f"● Online ({port})", text_color=COLOR_SUCCESS)
            if hasattr(self, "status_dot"):
                self.status_dot.configure(text=f"● Online ({port})", text_color=COLOR_SUCCESS)
            self.offline_banner.grid_forget()
        elif status in ("CONNECTING", "RECONNECTING"):
            self.status_pill.configure(fg_color=COLOR_WARNING_LIGHT, border_color=COLOR_WARNING_BORDER)
            self.status_label.configure(text=f"● {status.capitalize()}...", text_color=COLOR_WARNING)
            if hasattr(self, "status_dot"):
                self.status_dot.configure(text=f"● {status.capitalize()}...", text_color=COLOR_WARNING)
            self.offline_banner.grid(row=1, column=0, sticky="ew", padx=16, pady=(12, 0))
        else:  # DISCONNECTED
            self.status_pill.configure(fg_color=COLOR_DANGER_LIGHT, border_color=COLOR_DANGER_BORDER)
            self.status_label.configure(text="● Offline", text_color=COLOR_DANGER)
            if hasattr(self, "status_dot"):
                self.status_dot.configure(text="● Offline", text_color=COLOR_DANGER)
            self.offline_banner.grid(row=1, column=0, sticky="ew", padx=16, pady=(12, 0))

    def _on_reconnect_clicked(self) -> None:
        """Triggers manual reconnect attempt from offline banner."""
        if self.socket_client and not self.socket_client.is_connected():
            self.reconnect_btn.configure(text="Connecting...", state="disabled")
            self.status_pill.configure(fg_color=COLOR_WARNING_LIGHT, border_color=COLOR_WARNING_BORDER)
            self.status_label.configure(text="● Connecting...", text_color=COLOR_WARNING)
            try:
                if hasattr(self.socket_client, "reconnect_now"):
                    self.socket_client.reconnect_now()
                else:
                    self.socket_client.start()
            except Exception as ex:
                logger.warning("Error reconnecting socket client: %s", ex)

            # Re-enable button after 2.5 seconds if still offline
            def _reset_btn():
                if self.socket_client and not self.socket_client.is_connected():
                    try:
                        self.reconnect_btn.configure(text="Reconnect", state="normal")
                    except Exception:
                        pass
            self.root.after(2500, _reset_btn)

    # ==============================================================================
    # Global Web-Style On-Demand Zoom Engine (Invisible-by-Default HUD)
    # ==============================================================================
    def _load_zoom_preference(self) -> float:
        """Reads saved zoom preference from local user preferences if present."""
        try:
            pref_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "user_preferences.json",
            )
            if os.path.exists(pref_path):
                with open(pref_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    val = float(data.get("zoom_factor", 1.0))
                    return max(0.80, min(1.80, val))
        except Exception as ex:
            logger.debug("Could not load zoom preference: %s", ex)
        return 1.0

    def _save_zoom_preference(self) -> None:
        """Persists current zoom factor to local disk for seamless cross-session recall."""
        try:
            pref_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "user_preferences.json",
            )
            data = {}
            if os.path.exists(pref_path):
                try:
                    with open(pref_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data["zoom_factor"] = round(self._zoom_factor, 2)
            with open(pref_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as ex:
            logger.debug("Could not save zoom preference: %s", ex)

    def _build_zoom_hud(self) -> None:
        """Constructs the floating on-demand zoom capsule (hidden by default)."""
        self._zoom_hud = ctk.CTkFrame(
            self.content_area,
            corner_radius=18,
            fg_color=COLOR_CARD,
            border_color=COLOR_BORDER,
            border_width=1,
        )
        h_inner = ctk.CTkFrame(self._zoom_hud, fg_color="transparent")
        h_inner.pack(padx=8, pady=4)

        ctk.CTkLabel(
            h_inner,
            text="🔍",
            font=FONT_SMALL,
            text_color=COLOR_ACCENT_BLUE,
        ).pack(side="left", padx=(2, 4))

        self._zoom_down_btn = ctk.CTkButton(
            h_inner,
            text="−",
            width=26,
            height=24,
            corner_radius=6,
            font=FONT_BODY_BOLD,
            fg_color=COLOR_CARD_HOVER,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_BORDER,
            command=self._zoom_out,
        )
        self._zoom_down_btn.pack(side="left", padx=(0, 4))

        self._zoom_percent_label = ctk.CTkLabel(
            h_inner,
            text=f"{int(round(self._zoom_factor * 100))}%",
            font=FONT_SMALL_BOLD,
            text_color=COLOR_ACCENT_BLUE,
            width=42,
        )
        self._zoom_percent_label.pack(side="left", padx=(0, 4))

        self._zoom_up_btn = ctk.CTkButton(
            h_inner,
            text="+",
            width=26,
            height=24,
            corner_radius=6,
            font=FONT_BODY_BOLD,
            fg_color=COLOR_CARD_HOVER,
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_BORDER,
            command=self._zoom_in,
        )
        self._zoom_up_btn.pack(side="left", padx=(0, 6))

        self._zoom_reset_btn = ctk.CTkButton(
            h_inner,
            text="Reset",
            width=42,
            height=24,
            corner_radius=6,
            font=FONT_SMALL_BOLD,
            fg_color=COLOR_ACCENT_LIGHT,
            hover_color=COLOR_BORDER,
            text_color=COLOR_ACCENT_BLUE,
            command=self._zoom_reset,
        )
        self._zoom_reset_btn.pack(side="left", padx=(0, 4))

        self._zoom_close_btn = ctk.CTkButton(
            h_inner,
            text="✕",
            width=22,
            height=24,
            corner_radius=6,
            font=FONT_SMALL_BOLD,
            fg_color="transparent",
            hover_color=COLOR_CARD_HOVER,
            text_color=COLOR_TEXT_MUTED,
            command=self._hide_zoom_hud,
        )
        self._zoom_close_btn.pack(side="left", padx=(2, 0))

    def _setup_global_zoom_shortcuts(self) -> None:
        """Binds universal Ctrl+Scroll, Ctrl++, Ctrl+-, Ctrl+0 shortcuts across the entire app."""
        try:
            self.root.bind_all("<Control-MouseWheel>", self._on_global_ctrl_mousewheel, add="+")
            self.root.bind_all("<Control-plus>", self._on_global_zoom_in, add="+")
            self.root.bind_all("<Control-equal>", self._on_global_zoom_in, add="+")
            self.root.bind_all("<Control-KP_Add>", self._on_global_zoom_in, add="+")
            self.root.bind_all("<Control-minus>", self._on_global_zoom_out, add="+")
            self.root.bind_all("<Control-KP_Subtract>", self._on_global_zoom_out, add="+")
            self.root.bind_all("<Control-0>", self._on_global_zoom_reset, add="+")
            self.root.bind_all("<Control-Key-0>", self._on_global_zoom_reset, add="+")
            self.root.bind_all("<Escape>", self._on_global_escape, add="+")
        except Exception as ex:
            logger.debug("Could not bind global zoom shortcuts: %s", ex)

    def _show_zoom_hud(self) -> None:
        """Reveals the floating zoom HUD and schedules auto-dismissal after 3 seconds."""
        if not hasattr(self, "_zoom_hud") or self._zoom_hud is None:
            return

        pct = int(round(self._zoom_factor * 100))
        self._zoom_percent_label.configure(text=f"{pct}%")
        self._zoom_hud.place(relx=0.98, y=56, anchor="ne")
        self._zoom_hud.lift()

        # Reset 3-second auto-dismiss watchdog
        if self._zoom_hud_timer is not None:
            try:
                self.root.after_cancel(self._zoom_hud_timer)
            except Exception:
                pass
        self._zoom_hud_timer = self.root.after(3000, self._hide_zoom_hud)

    def _hide_zoom_hud(self) -> None:
        """Dismisses the floating zoom HUD."""
        if self._zoom_hud_timer is not None:
            try:
                self.root.after_cancel(self._zoom_hud_timer)
            except Exception:
                pass
            self._zoom_hud_timer = None

        if hasattr(self, "_zoom_hud") and self._zoom_hud is not None:
            try:
                self._zoom_hud.place_forget()
            except Exception:
                pass

    def _apply_zoom(self, new_scale: float, reveal_hud: bool = True) -> None:
        """Applies global widget scaling across the application."""
        self._zoom_factor = max(0.80, min(1.80, round(new_scale, 2)))
        try:
            ctk.set_widget_scaling(self._zoom_factor)
        except Exception as ex:
            logger.debug("Error setting widget scaling: %s", ex)

        self._save_zoom_preference()

        if reveal_hud:
            self._show_zoom_hud()

    def _zoom_in(self) -> None:
        """Increases global scaling by +10%."""
        self._apply_zoom(self._zoom_factor + 0.10, reveal_hud=True)

    def _zoom_out(self) -> None:
        """Decreases global scaling by -10%."""
        self._apply_zoom(self._zoom_factor - 0.10, reveal_hud=True)

    def _zoom_reset(self) -> None:
        """Resets global scaling back to 100%."""
        self._apply_zoom(1.00, reveal_hud=True)

    def _on_global_ctrl_mousewheel(self, event: Any) -> Optional[str]:
        """Global Ctrl + MouseWheel event handler."""
        delta = getattr(event, "delta", 0)
        if delta > 0:
            self._zoom_in()
        elif delta < 0:
            self._zoom_out()
        return "break"

    def _on_global_zoom_in(self, event: Optional[Any] = None) -> Optional[str]:
        """Global Ctrl + Plus event handler."""
        self._zoom_in()
        return "break"

    def _on_global_zoom_out(self, event: Optional[Any] = None) -> Optional[str]:
        """Global Ctrl + Minus event handler."""
        self._zoom_out()
        return "break"

    def _on_global_zoom_reset(self, event: Optional[Any] = None) -> Optional[str]:
        """Global Ctrl + 0 event handler."""
        self._zoom_reset()
        return "break"

    def _on_global_escape(self, event: Optional[Any] = None) -> None:
        """Dismisses HUD on Escape key."""
        self._hide_zoom_hud()
