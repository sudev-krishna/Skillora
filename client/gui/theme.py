"""
Skillora Modern Light Theme Design System (client/gui/theme.py)
Strictly Light Theme (NO Dark Mode). Slate background, white cards, blue/indigo accents.
All font constants are immutable tuples to avoid premature root creation crashes.
"""

from typing import Any, Callable, Dict, Optional, Tuple, Union
import customtkinter as ctk

# ==============================================================================
# Theme Enforcement (Strictly Light Mode)
# ==============================================================================
def enforce_light_theme() -> None:
    """Enforces CustomTkinter light appearance mode and blue theme."""
    ctk.set_appearance_mode("Light")
    ctk.set_default_color_theme("blue")

# Run enforcement on module import
enforce_light_theme()

# ==============================================================================
# Color Palette (Warm Minimalist Studio / ClientRidge Aesthetic)
# ==============================================================================
# Canvas & Surfaces
COLOR_BG = "#FAF9F5"              # Warm Studio Canvas
COLOR_CARD = "#FFFFFF"            # Pure White (Card surface)
COLOR_CARD_HOVER = "#F5F3ED"      # Soft Warm Cream Hover
COLOR_BORDER = "#EAE6DF"          # Warm Divider Border
COLOR_BORDER_FOCUS = "#FFB09C"    # Coral-tinted focus border

# Typography
COLOR_TEXT_PRIMARY = "#191C1F"    # Deep Obsidian Charcoal
COLOR_TEXT_SECONDARY = "#686B6F"  # Medium Slate Gray
COLOR_TEXT_MUTED = "#9E9E9C"      # Soft Muted Gray
COLOR_TEXT_INVERTED = "#FFFFFF"   # White (Text on dark/accent buttons)

# Accents (Warm Terracotta / Coral & Obsidian)
COLOR_ACCENT_CORAL = "#FF6442"    # Primary Vibrant Coral
COLOR_ACCENT_HOVER = "#E85433"    # Deep Coral Hover
COLOR_ACCENT_LIGHT = "#FFF2EE"    # Soft Peach/Coral Pill Tint
COLOR_ACCENT_BLUE = "#FF6442"     # Mapped to vibrant coral for unified brand identity
COLOR_ACCENT_INDIGO = "#FF7A59"   # Warm peach secondary accent
COLOR_ACCENT_INDIGO_HOVER = "#E85433"
COLOR_ACCENT_INDIGO_LIGHT = "#FFF0EB"
COLOR_ACCENT_DARK = "#1E2024"     # Dark Obsidian Command Bar & Search Pill

# Semantic Status
COLOR_SUCCESS = "#10B981"         # Emerald Green (Eligible, pass, connected)
COLOR_SUCCESS_LIGHT = "#ECFDF5"   # Emerald Soft Pill
COLOR_SUCCESS_BORDER = "#A7F3D0"  # Green 200
COLOR_WARNING = "#F59E0B"         # Warm Amber (Caution, reconnecting)
COLOR_WARNING_LIGHT = "#FFFBEB"   # Amber Soft Pill
COLOR_WARNING_BORDER = "#FDE68A"  # Amber 200
COLOR_DANGER = "#EF4444"          # Rose Red (Error, disconnected, ineligible)
COLOR_DANGER_LIGHT = "#FEF2F2"    # Rose Soft Pill
COLOR_DANGER_BORDER = "#FECACA"   # Red 200

# Sidebar Navigation
COLOR_SIDEBAR_BG = "#FFFFFF"      # White persistent sidebar
COLOR_SIDEBAR_BORDER = "#EAE6DF"  # Warm vertical divider
COLOR_NAV_IDLE = "transparent"
COLOR_NAV_HOVER = "#F5F3ED"       # Soft cream hover
COLOR_NAV_ACTIVE_BG = "#FFF2EE"   # Soft peach active pill
COLOR_NAV_ACTIVE_TEXT = "#FF6442" # Vibrant coral active text
COLOR_NAV_IDLE_TEXT = "#475569"   # Slate 600 idle text

# ==============================================================================
# Radii & Dimensions
# ==============================================================================
RADIUS_CARD = 12
RADIUS_BUTTON = 8
RADIUS_BADGE = 12
RADIUS_INPUT = 8
RADIUS_PILL = 16

BORDER_WIDTH_CARD = 1
BORDER_WIDTH_INPUT = 1

# ==============================================================================
# Typography Hierarchy (Tuple Definitions for Zero-Root Safety)
# ==============================================================================
FONT_FAMILY_MAIN = "Segoe UI"
FONT_FAMILY_CODE = "Consolas"

FONT_HERO_LARGE = (FONT_FAMILY_MAIN, 34, "bold")
FONT_HERO = (FONT_FAMILY_MAIN, 28, "bold")
FONT_DISPLAY = (FONT_FAMILY_MAIN, 20, "bold")
FONT_TITLE = (FONT_FAMILY_MAIN, 18, "bold")
FONT_SUBTITLE = (FONT_FAMILY_MAIN, 14, "bold")
FONT_HEADING = (FONT_FAMILY_MAIN, 13, "bold")
FONT_BODY = (FONT_FAMILY_MAIN, 12, "normal")
FONT_BODY_BOLD = (FONT_FAMILY_MAIN, 12, "bold")
FONT_SMALL = (FONT_FAMILY_MAIN, 10, "normal")
FONT_SMALL_BOLD = (FONT_FAMILY_MAIN, 10, "bold")
FONT_CODE = (FONT_FAMILY_CODE, 11, "normal")
FONT_CODE_BOLD = (FONT_FAMILY_CODE, 11, "bold")


def get_font(
    font_spec: Union[Tuple[str, int, str], str],
    size: Optional[int] = None,
    weight: Optional[str] = None,
) -> Union[ctk.CTkFont, Tuple[str, int, str]]:
    """
    Lazy font helper that returns a CTkFont instance if a Tk root exists,
    or falls back to an immutable font tuple for zero-root safety.
    """
    if isinstance(font_spec, tuple) and len(font_spec) == 3:
        family, default_size, default_weight = font_spec
        f_size = size if size is not None else default_size
        f_weight = weight if weight is not None else default_weight
    else:
        family = str(font_spec)
        f_size = size or 12
        f_weight = weight or "normal"

    try:
        return ctk.CTkFont(family=family, size=f_size, weight=f_weight)
    except Exception:
        return (family, f_size, f_weight)


# ==============================================================================
# Styling Helpers & Factory Functions
# ==============================================================================
def create_card(parent: Any, **kwargs) -> ctk.CTkFrame:
    """Creates a standardized modern rounded card frame."""
    defaults = {
        "corner_radius": RADIUS_CARD,
        "fg_color": COLOR_CARD,
        "border_color": COLOR_BORDER,
        "border_width": BORDER_WIDTH_CARD,
    }
    defaults.update(kwargs)
    return ctk.CTkFrame(parent, **defaults)


def create_button(
    parent: Any,
    text: str,
    command: Optional[Callable[[], None]] = None,
    variant: str = "primary",
    **kwargs,
) -> ctk.CTkButton:
    """Creates a styled button with defined variant dynamics."""
    variant_styles = {
        "primary": {
            "fg_color": COLOR_ACCENT_BLUE,
            "hover_color": COLOR_ACCENT_HOVER,
            "text_color": COLOR_TEXT_INVERTED,
            "border_width": 0,
        },
        "secondary": {
            "fg_color": COLOR_ACCENT_INDIGO,
            "hover_color": COLOR_ACCENT_INDIGO_HOVER,
            "text_color": COLOR_TEXT_INVERTED,
            "border_width": 0,
        },
        "outline": {
            "fg_color": "transparent",
            "hover_color": COLOR_CARD_HOVER,
            "text_color": COLOR_TEXT_PRIMARY,
            "border_color": COLOR_BORDER,
            "border_width": 1,
        },
        "danger": {
            "fg_color": COLOR_DANGER,
            "hover_color": "#B91C1C",
            "text_color": COLOR_TEXT_INVERTED,
            "border_width": 0,
        },
    }
    style = variant_styles.get(variant, variant_styles["primary"]).copy()
    style.update({
        "corner_radius": RADIUS_BUTTON,
        "font": FONT_BODY_BOLD,
        "text": text,
        "command": command,
    })
    style.update(kwargs)
    return ctk.CTkButton(parent, **style)


def create_badge(
    parent: Any,
    text: str,
    variant: str = "neutral",
    **kwargs,
) -> ctk.CTkLabel:
    """Creates a lightweight rounded status badge / tag using CTkLabel."""
    badge_palettes = {
        "success": (COLOR_SUCCESS_LIGHT, COLOR_SUCCESS),
        "warning": (COLOR_WARNING_LIGHT, COLOR_WARNING),
        "danger": (COLOR_DANGER_LIGHT, COLOR_DANGER),
        "info": (COLOR_ACCENT_LIGHT, COLOR_ACCENT_BLUE),
        "indigo": (COLOR_ACCENT_INDIGO_LIGHT, COLOR_ACCENT_INDIGO),
        "coral": (COLOR_ACCENT_LIGHT, COLOR_ACCENT_CORAL),
        "peach": (COLOR_ACCENT_INDIGO_LIGHT, COLOR_ACCENT_INDIGO),
        "dark": (COLOR_ACCENT_DARK, COLOR_TEXT_INVERTED),
        "neutral": (COLOR_CARD_HOVER, COLOR_TEXT_SECONDARY),
    }
    bg_col, text_col = badge_palettes.get(variant, badge_palettes["neutral"])
    defaults = {
        "corner_radius": RADIUS_BADGE,
        "fg_color": bg_col,
        "text_color": text_col,
        "font": FONT_SMALL_BOLD,
        "text": f" {text} ",
        "padx": 8,
        "pady": 3,
    }
    defaults.update(kwargs)
    return ctk.CTkLabel(parent, **defaults)


def create_status_pill(
    parent: Any,
    text: str,
    variant: str = "info",
    **kwargs,
) -> ctk.CTkFrame:
    """Creates a rounded pill frame containing a status text."""
    pill_palettes = {
        "success": (COLOR_SUCCESS_LIGHT, COLOR_SUCCESS_BORDER, COLOR_SUCCESS),
        "warning": (COLOR_WARNING_LIGHT, COLOR_WARNING_BORDER, COLOR_WARNING),
        "danger": (COLOR_DANGER_LIGHT, COLOR_DANGER_BORDER, COLOR_DANGER),
        "info": (COLOR_ACCENT_LIGHT, COLOR_BORDER_FOCUS, COLOR_ACCENT_BLUE),
        "neutral": (COLOR_CARD_HOVER, COLOR_BORDER, COLOR_TEXT_SECONDARY),
    }
    bg_col, border_col, text_col = pill_palettes.get(variant, pill_palettes["neutral"])
    pill_frame = ctk.CTkFrame(
        parent,
        corner_radius=RADIUS_PILL,
        fg_color=bg_col,
        border_color=border_col,
        border_width=1,
        **kwargs,
    )
    lbl = ctk.CTkLabel(
        pill_frame,
        text=text,
        font=FONT_SMALL_BOLD,
        text_color=text_col,
    )
    lbl.pack(padx=12, pady=4)
    return pill_frame


def create_entry(parent: Any, placeholder_text: str = "", **kwargs) -> ctk.CTkEntry:
    """Creates a clean, styled light-mode text entry."""
    defaults = {
        "corner_radius": RADIUS_INPUT,
        "fg_color": COLOR_CARD,
        "border_color": COLOR_BORDER,
        "border_width": BORDER_WIDTH_INPUT,
        "text_color": COLOR_TEXT_PRIMARY,
        "placeholder_text_color": COLOR_TEXT_MUTED,
        "placeholder_text": placeholder_text,
        "font": FONT_BODY,
    }
    defaults.update(kwargs)
    return ctk.CTkEntry(parent, **defaults)
