"""
app/ui.py
Tkinter & ttk graphical user interface for Hand Gesture Controller.

Implements a modern, dark navy dashboard with cyan/blue accents, live webcam
feed canvas with aspect-ratio preservation, statistics cards, and Phase 1 placeholders.
"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageTk
from pathlib import Path
import sys

# Allow direct script execution (e.g., python app/ui.py)
if __name__ == '__main__' and __package__ is None:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from app.camera import CameraService
from app.control_manager import ControlManager, SystemActionResult
from app.settings_manager import SETTING_SPECS, SettingsManager, UserSettings
from app.statistics_manager import SessionRecord, StatisticsManager
from app.config import (
    ACTION_NONE,
    APP_SUBTITLE,
    APP_TITLE,
    APP_VERSION,
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_CYAN,
    COLOR_ACCENT_GLOW,
    COLOR_BG_CARD_INNER,
    COLOR_BG_HEADER,
    COLOR_BG_PREVIEW,
    COLOR_BG_ROOT,
    COLOR_BG_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_ACCENT,
    COLOR_BTN_DISABLED_BG,
    COLOR_BTN_DISABLED_TEXT,
    COLOR_BTN_START_BG,
    COLOR_BTN_START_HOVER,
    COLOR_BTN_START_TEXT,
    COLOR_BTN_STOP_BG,
    COLOR_BTN_STOP_HOVER,
    COLOR_BTN_STOP_TEXT,
    COLOR_STATUS_MAP,
    COLOR_TEXT_ACCENT,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    DEFAULT_CAMERA_INDEX,
    FONT_APP_SUBTITLE,
    FONT_APP_TITLE,
    FONT_BADGE,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CARD_TITLE,
    FONT_FAMILY,
    FONT_PREVIEW_OVERLAY,
    FONT_SMALL,
    FONT_STAT_LABEL,
    FONT_STAT_VALUE,
    FRAME_POLL_INTERVAL_MS,
    GESTURE_ENGINE_STATE,
    GESTURE_FIST,
    GESTURE_FIVE_FINGERS,
    GESTURE_FOUR_FINGERS,
    GESTURE_NONE,
    GESTURE_ONE_FINGER,
    GESTURE_OPEN_PALM,
    GESTURE_PEACE,
    GESTURE_PLACEHOLDER_TEXT,
    GESTURE_THREE_FINGERS,
    GESTURE_THUMBS_UP,
    GESTURE_TWO_FINGERS,
    GESTURE_UNKNOWN,
    INITIAL_GESTURES_COUNT,
    INITIAL_HANDS_COUNT,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    PREVIEW_DEFAULT_HEIGHT,
    PREVIEW_DEFAULT_WIDTH,
    SIDEBAR_WIDTH,
    STATUS_ERROR,
    STATUS_HAND_DETECTED,
    STATUS_NO_HAND,
    STATUS_RUNNING,
    STATUS_STARTING,
    STATUS_STOPPED,
    STATUS_TRACKING_ACTIVE,
    STATUS_TRACKING_OFFLINE,
    STATUS_TRACKING_SCANNING,
    SUPPORTED_ACTIONS,
    SUPPORTED_GESTURES,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)

logger = logging.getLogger(__name__)


class ModernButton(tk.Button):
    """A customized flat button with hover transitions and dark theme colors."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        bg_color: str,
        hover_color: str,
        fg_color: str = "#FFFFFF",
        command=None,
        **kwargs,
    ) -> None:
        btn_font = kwargs.pop("font", (FONT_FAMILY, 10, "bold"))
        btn_padx = kwargs.pop("padx", 16)
        btn_pady = kwargs.pop("pady", 8)
        super().__init__(
            parent,
            text=text,
            bg=bg_color,
            fg=fg_color,
            activebackground=hover_color,
            activeforeground=fg_color,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=btn_padx,
            pady=btn_pady,
            font=btn_font,
            command=command,
            **kwargs,
        )
        self._default_bg = bg_color
        self._hover_bg = hover_color
        self._default_fg = fg_color
        self._is_enabled = True

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, event=None) -> None:
        if self._is_enabled and str(self["state"]) != "disabled":
            self.configure(bg=self._hover_bg)

    def _on_leave(self, event=None) -> None:
        if self._is_enabled and str(self["state"]) != "disabled":
            self.configure(bg=self._default_bg)

    def set_colors(self, bg_color: str, hover_color: str, fg_color: str = "#FFFFFF") -> None:
        """Update button colors dynamically."""
        self._default_bg = bg_color
        self._hover_bg = hover_color
        self._default_fg = fg_color
        self.configure(
            bg=bg_color,
            fg=fg_color,
            activebackground=hover_color,
            activeforeground=fg_color,
        )

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the button with matching theme aesthetics."""
        self._is_enabled = enabled
        if enabled:
            self.configure(
                state="normal",
                bg=self._default_bg,
                fg=self._default_fg,
                cursor="hand2",
            )
        else:
            self.configure(
                state="disabled",
                bg=COLOR_BTN_DISABLED_BG,
                fg=COLOR_BTN_DISABLED_TEXT,
                cursor="arrow",
            )


# ---------------------------------------------------------------------------
# Gesture Descriptive Metadata
# ---------------------------------------------------------------------------
GESTURE_DESCRIPTIONS: Dict[str, str] = {
    GESTURE_THUMBS_UP: "Thumb pointing upward, other 4 fingers curled.",
    GESTURE_PEACE: "Index & middle fingers extended in a V-shape.",
    GESTURE_THREE_FINGERS: "Index, middle, and ring fingers extended.",
    GESTURE_FOUR_FINGERS: "Four fingers extended, thumb folded across palm.",
    GESTURE_OPEN_PALM: "All five fingers fully extended with wide spread.",
    GESTURE_FIST: "All five fingers curled tightly into a fist.",
    GESTURE_ONE_FINGER: "Only index finger extended pointing upward.",
    GESTURE_TWO_FINGERS: "Index and middle fingers extended together.",
    GESTURE_FIVE_FINGERS: "All five fingers extended with standard spacing.",
}


class SettingsDialog(tk.Toplevel):
    """
    Modal settings and customization dialog for Hand Gesture Controller (Phase 5).
    
    Provides custom gesture-to-action mapping dropdowns, sensitivity and timing sliders,
    validation feedback, and atomic persistence.
    """

    def __init__(
        self,
        parent: tk.Tk,
        settings_manager: SettingsManager,
        control_manager: ControlManager,
        camera_service: CameraService,
        on_settings_applied: Optional[Callable[[UserSettings], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.parent = parent
        self.settings_manager = settings_manager
        self.control_manager = control_manager
        self.camera_service = camera_service
        self.on_settings_applied = on_settings_applied

        # Window properties
        self.title("Hand Gesture Controller — Settings & Preferences")
        self.geometry("700x660")
        self.minsize(620, 520)
        self.configure(bg=COLOR_BG_ROOT)
        self.transient(parent)

        # Center dialog relative to parent window
        try:
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            if pw > 100 and ph > 100:
                cx = px + (pw - 700) // 2
                cy = py + (ph - 660) // 2
                self.geometry(f"+{max(0, cx)}+{max(0, cy)}")
        except Exception:
            pass

        try:
            self.grab_set()
        except Exception:
            pass

        # State storage for widgets
        self._action_vars: Dict[str, tk.StringVar] = {}
        self._scale_vars: Dict[str, tk.Variable] = {}
        self._scale_labels: Dict[str, tk.Label] = {}
        self._current_tab: str = "mappings"

        self._build_header()
        self._build_tab_bar()
        self._build_content_panels()
        self._build_bottom_bar()

        # Load current values into widgets
        self._populate_fields(self.settings_manager.current_settings)

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=COLOR_BG_HEADER, height=56)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        accent_line = tk.Frame(self, bg=COLOR_BORDER, height=1)
        accent_line.pack(side="top", fill="x")

        title_box = tk.Frame(header, bg=COLOR_BG_HEADER)
        title_box.pack(side="left", padx=16, pady=8)

        lbl = tk.Label(
            title_box,
            text="⚙  PREFERENCES & CUSTOMIZATION",
            font=FONT_APP_TITLE,
            bg=COLOR_BG_HEADER,
            fg=COLOR_ACCENT_CYAN,
        )
        lbl.pack(side="top", anchor="w")

        sub = tk.Label(
            title_box,
            text="Phase 5: Configurable gesture mappings, sensitivity thresholds, and persistent settings.",
            font=FONT_SMALL,
            bg=COLOR_BG_HEADER,
            fg=COLOR_TEXT_SECONDARY,
        )
        sub.pack(side="top", anchor="w")

    def _build_tab_bar(self) -> None:
        tab_frame = tk.Frame(self, bg=COLOR_BG_ROOT, height=44)
        tab_frame.pack(side="top", fill="x", padx=16, pady=(10, 4))

        self.btn_tab_mappings = ModernButton(
            tab_frame,
            text="🎯 Gesture Mappings",
            bg_color=COLOR_BG_CARD_INNER,
            hover_color="#1E2E4E",
            fg_color=COLOR_ACCENT_CYAN,
            font=(FONT_FAMILY, 10, "bold"),
            padx=14,
            pady=6,
            command=lambda: self._switch_tab("mappings"),
        )
        self.btn_tab_mappings.pack(side="left", padx=(0, 8))

        self.btn_tab_sensitivity = ModernButton(
            tab_frame,
            text="⚡ Sensitivity & Timing",
            bg_color=COLOR_BG_SURFACE,
            hover_color="#1E2E4E",
            fg_color=COLOR_TEXT_SECONDARY,
            font=(FONT_FAMILY, 10, "bold"),
            padx=14,
            pady=6,
            command=lambda: self._switch_tab("sensitivity"),
        )
        self.btn_tab_sensitivity.pack(side="left")

    def _build_content_panels(self) -> None:
        self.container = tk.Frame(self, bg=COLOR_BG_ROOT)
        self.container.pack(side="top", fill="both", expand=True, padx=16, pady=6)

        # Tab 1: Gesture Mappings Panel
        self.panel_mappings = tk.Frame(self.container, bg=COLOR_BG_ROOT)
        self._build_mappings_panel(self.panel_mappings)

        # Tab 2: Sensitivity Controls Panel
        self.panel_sensitivity = tk.Frame(self.container, bg=COLOR_BG_ROOT)
        self._build_sensitivity_panel(self.panel_sensitivity)

        # Show initial tab
        self._switch_tab("mappings")

    def _switch_tab(self, tab_name: str) -> None:
        self._current_tab = tab_name
        if tab_name == "mappings":
            self.panel_sensitivity.pack_forget()
            self.panel_mappings.pack(fill="both", expand=True)
            self.btn_tab_mappings.set_colors(COLOR_BG_CARD_INNER, "#1E2E4E", COLOR_ACCENT_CYAN)
            self.btn_tab_sensitivity.set_colors(COLOR_BG_SURFACE, "#1E2E4E", COLOR_TEXT_SECONDARY)
        else:
            self.panel_mappings.pack_forget()
            self.panel_sensitivity.pack(fill="both", expand=True)
            self.btn_tab_mappings.set_colors(COLOR_BG_SURFACE, "#1E2E4E", COLOR_TEXT_SECONDARY)
            self.btn_tab_sensitivity.set_colors(COLOR_BG_CARD_INNER, "#1E2E4E", COLOR_ACCENT_CYAN)

    def _build_mappings_panel(self, parent: tk.Frame) -> None:
        canvas = tk.Canvas(parent, bg=COLOR_BG_ROOT, bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLOR_BG_ROOT)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _configure_width(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", _configure_width)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Instruction note banner
        note_box = tk.Frame(
            scrollable_frame,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
        )
        note_box.pack(side="top", fill="x", pady=(0, 8), padx=2)
        tk.Label(
            note_box,
            text="Assign a supported system action to each recognized gesture. Select 'None' to disable a mapping.",
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
            padx=10,
            pady=6,
        ).pack(side="left")

        # Build card for each supported gesture
        for gesture in SUPPORTED_GESTURES:
            card = tk.Frame(
                scrollable_frame,
                bg=COLOR_BG_SURFACE,
                highlightbackground=COLOR_BORDER,
                highlightthickness=1,
            )
            card.pack(side="top", fill="x", pady=4, padx=2)

            left_box = tk.Frame(card, bg=COLOR_BG_SURFACE)
            left_box.pack(side="left", fill="y", padx=12, pady=8)

            tk.Label(
                left_box,
                text=gesture,
                font=FONT_BODY_BOLD,
                bg=COLOR_BG_SURFACE,
                fg=COLOR_TEXT_PRIMARY,
            ).pack(side="top", anchor="w")

            desc = GESTURE_DESCRIPTIONS.get(gesture, "Recognized hand pose.")
            tk.Label(
                left_box,
                text=desc,
                font=FONT_SMALL,
                bg=COLOR_BG_SURFACE,
                fg=COLOR_TEXT_MUTED,
            ).pack(side="top", anchor="w")

            right_box = tk.Frame(card, bg=COLOR_BG_SURFACE)
            right_box.pack(side="right", padx=12, pady=8)

            var = tk.StringVar(value=ACTION_NONE)
            self._action_vars[gesture] = var

            combo = ttk.Combobox(
                right_box,
                textvariable=var,
                values=list(SUPPORTED_ACTIONS),
                state="readonly",
                width=18,
                font=FONT_SMALL,
            )
            combo.pack(side="right")

    def _build_sensitivity_panel(self, parent: tk.Frame) -> None:
        canvas = tk.Canvas(parent, bg=COLOR_BG_ROOT, bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLOR_BG_ROOT)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _configure_width(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", _configure_width)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Section 1: Recognition & Filtering
        sec1 = self._create_setting_section(scrollable_frame, "GESTURE RECOGNITION & SMOOTHING")
        self._add_slider_row(sec1, "gesture_history_length")
        self._add_slider_row(sec1, "gesture_min_consistent")
        self._add_slider_row(sec1, "gesture_cooldown_sec")

        # Section 2: Action Cooldown & Continuous Volume
        sec2 = self._create_setting_section(scrollable_frame, "ACTION TIMING & VOLUME SENSITIVITY")
        self._add_slider_row(sec2, "action_cooldown_sec")
        self._add_slider_row(sec2, "volume_change_threshold")
        self._add_slider_row(sec2, "volume_update_interval_sec")
        self._add_slider_row(sec2, "volume_smoothing_alpha")

        # Section 3: Virtual Mouse
        sec3 = self._create_setting_section(scrollable_frame, "VIRTUAL MOUSE SENSITIVITY")
        self._add_slider_row(sec3, "mouse_smoothing_alpha")
        self._add_slider_row(sec3, "mouse_click_threshold_ratio")
        self._add_slider_row(sec3, "mouse_release_threshold_ratio")
        self._add_slider_row(sec3, "mouse_click_cooldown_sec")

    def _create_setting_section(self, parent: tk.Widget, title: str) -> tk.Frame:
        card = tk.Frame(
            parent,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
        )
        card.pack(side="top", fill="x", pady=5, padx=2)

        hdr = tk.Frame(card, bg=COLOR_BG_CARD_INNER)
        hdr.pack(side="top", fill="x", padx=10, pady=(8, 4))
        tk.Label(
            hdr,
            text=title,
            font=FONT_CARD_TITLE,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_ACCENT_CYAN,
        ).pack(side="left")

        tk.Frame(card, bg=COLOR_BORDER, height=1).pack(side="top", fill="x", padx=8, pady=(2, 6))
        return card

    def _add_slider_row(self, parent: tk.Widget, key: str) -> None:
        spec = SETTING_SPECS[key]
        row = tk.Frame(parent, bg=COLOR_BG_CARD_INNER)
        row.pack(side="top", fill="x", padx=10, pady=4)

        top_line = tk.Frame(row, bg=COLOR_BG_CARD_INNER)
        top_line.pack(side="top", fill="x")

        tk.Label(
            top_line,
            text=spec["label"],
            font=FONT_BODY_BOLD,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_PRIMARY,
        ).pack(side="left")

        val_lbl = tk.Label(
            top_line,
            text=str(spec["default"]),
            font=FONT_BODY_BOLD,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_ACCENT_CYAN,
        )
        val_lbl.pack(side="right")
        self._scale_labels[key] = val_lbl

        # Description
        tk.Label(
            row,
            text=spec["description"],
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
        ).pack(side="top", anchor="w", pady=(1, 2))

        # Scale slider
        is_int = spec["type"] is int
        var = tk.IntVar() if is_int else tk.DoubleVar()
        self._scale_vars[key] = var

        resolution = 1 if is_int else (0.01 if "ratio" in key or "alpha" in key else 0.05)

        def _on_val_changed(val_str: str) -> None:
            try:
                num = float(val_str)
                display_str = f"{int(num)}" if is_int else f"{num:.2f}"
                val_lbl.configure(text=display_str)
            except Exception:
                pass

        scale = tk.Scale(
            row,
            from_=spec["min"],
            to=spec["max"],
            resolution=resolution,
            orient="horizontal",
            variable=var,
            showvalue=False,
            bg=COLOR_BG_CARD_INNER,
            troughcolor=COLOR_BG_ROOT,
            activebackground=COLOR_ACCENT_BLUE,
            highlightthickness=0,
            bd=0,
            command=_on_val_changed,
        )
        scale.pack(side="top", fill="x", pady=(1, 4))

    def _build_bottom_bar(self) -> None:
        # Feedback banner
        self.feedback_banner = tk.Frame(self, bg=COLOR_BG_ROOT)
        self.feedback_banner.pack(side="top", fill="x", padx=16, pady=(4, 2))

        self.feedback_lbl = tk.Label(
            self.feedback_banner,
            text="",
            font=FONT_SMALL,
            bg=COLOR_BG_ROOT,
            fg=COLOR_TEXT_MUTED,
            padx=10,
            pady=4,
        )
        self.feedback_lbl.pack(side="top", fill="x")

        # Button row
        bottom_frame = tk.Frame(self, bg=COLOR_BG_HEADER, height=52)
        bottom_frame.pack(side="bottom", fill="x")
        bottom_frame.pack_propagate(False)

        top_border = tk.Frame(self, bg=COLOR_BORDER, height=1)
        top_border.pack(side="bottom", fill="x")

        btn_box = tk.Frame(bottom_frame, bg=COLOR_BG_HEADER)
        btn_box.pack(side="top", fill="x", padx=16, pady=8)

        self.btn_reset = ModernButton(
            btn_box,
            text="↺ Reset Defaults",
            bg_color="#334155",
            hover_color="#475569",
            fg_color="#F8FAFC",
            font=(FONT_FAMILY, 9),
            padx=10,
            pady=5,
            command=self._reset_defaults,
        )
        self.btn_reset.pack(side="left")

        self.btn_save = ModernButton(
            btn_box,
            text="💾 Save & Apply Settings",
            bg_color=COLOR_BTN_START_BG,
            hover_color=COLOR_BTN_START_HOVER,
            fg_color="#FFFFFF",
            font=(FONT_FAMILY, 9, "bold"),
            padx=14,
            pady=5,
            command=self._save_settings,
        )
        self.btn_save.pack(side="right", padx=(8, 0))

        self.btn_cancel = ModernButton(
            btn_box,
            text="Cancel",
            bg_color=COLOR_BG_CARD_INNER,
            hover_color="#1E2E4E",
            fg_color=COLOR_TEXT_SECONDARY,
            font=(FONT_FAMILY, 9),
            padx=10,
            pady=5,
            command=self.destroy,
        )
        self.btn_cancel.pack(side="right")

    def _populate_fields(self, settings: UserSettings) -> None:
        """Populate comboboxes and sliders with values from UserSettings."""
        for gesture, var in self._action_vars.items():
            action = settings.gesture_actions.get(gesture, ACTION_NONE)
            var.set(action)

        for key, var in self._scale_vars.items():
            val = getattr(settings, key, SETTING_SPECS[key]["default"])
            var.set(val)
            is_int = SETTING_SPECS[key]["type"] is int
            display_str = f"{int(val)}" if is_int else f"{val:.2f}"
            if key in self._scale_labels:
                self._scale_labels[key].configure(text=display_str)

    def _save_settings(self) -> None:
        """Gather values, validate, persist atomically, and apply to components."""
        # 1. Gather gesture actions
        new_mappings: Dict[str, str] = {}
        for gesture, var in self._action_vars.items():
            new_mappings[gesture] = var.get()

        # 2. Gather sensitivity values
        kwargs: Dict[str, Any] = {"gesture_actions": new_mappings}
        for key, var in self._scale_vars.items():
            spec = SETTING_SPECS[key]
            kwargs[key] = spec["type"](var.get())

        proposed_settings = UserSettings(**kwargs)
        is_valid, messages, sanitized = self.settings_manager.validate(proposed_settings)

        if not is_valid:
            error_msg = "⚠️ " + " | ".join(messages)
            self.feedback_lbl.configure(text=error_msg, bg="#7F1D1D", fg="#FECACA")
            # Update fields to sanitized
            self._populate_fields(sanitized)
            return

        # Persist atomically
        success = self.settings_manager.save(sanitized)
        if success:
            # Dynamically apply to components
            self.settings_manager.apply_to_components(
                sanitized,
                gesture_recognizer=(
                    self.camera_service.hand_detector.gesture_recognizer
                    if self.camera_service.hand_detector is not None
                    else None
                ),
                control_manager=self.control_manager,
            )

            self.feedback_lbl.configure(
                text="✓ Settings saved and applied dynamically!",
                bg="#064E3B",
                fg="#A7F3D0",
            )
            self._populate_fields(sanitized)

            if self.on_settings_applied is not None:
                self.on_settings_applied(sanitized)
        else:
            self.feedback_lbl.configure(
                text="❌ Failed to save configuration to disk.",
                bg="#7F1D1D",
                fg="#FECACA",
            )

    def _reset_defaults(self) -> None:
        """Reset to factory defaults, save, and update widgets."""
        defaults = self.settings_manager.reset_to_defaults()
        self.settings_manager.apply_to_components(
            defaults,
            gesture_recognizer=(
                self.camera_service.hand_detector.gesture_recognizer
                if self.camera_service.hand_detector is not None
                else None
            ),
            control_manager=self.control_manager,
        )
        self._populate_fields(defaults)
        self.feedback_lbl.configure(
            text="↺ Factory defaults restored and applied successfully.",
            bg="#065F46",
            fg="#A7F3D0",
        )
        if self.on_settings_applied is not None:
            self.on_settings_applied(defaults)


# ---------------------------------------------------------------------------
# Analytics & Session History Dialog (Phase 6)
# ---------------------------------------------------------------------------
class AnalyticsDialog(tk.Toplevel):
    """
    Modal or modeless Analytics and Session History dialog for Hand Gesture Controller (Phase 6).

    Presents real-time session duration, gesture recognition frequencies with native Tkinter Canvas
    bar chart, action outcome metrics (successful/blocked/failed), past sessions history log from SQLite,
    and side-by-side comparative analytics.
    """

    def __init__(
        self,
        parent: tk.Tk,
        statistics_manager: StatisticsManager,
    ) -> None:
        super().__init__(parent)
        self.parent = parent
        self.statistics_manager = statistics_manager

        # Window properties
        self.title("Hand Gesture Controller — Session History & Analytics")
        self.geometry("800x700")
        self.minsize(720, 600)
        self.configure(bg=COLOR_BG_ROOT)
        self.transient(parent)

        # Center dialog relative to parent window
        try:
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            if pw > 100 and ph > 100:
                cx = px + (pw - 800) // 2
                cy = py + (ph - 700) // 2
                self.geometry(f"+{max(0, cx)}+{max(0, cy)}")
        except Exception:
            pass

        self._active_tab: str = "overview"
        self._selected_session_id: Optional[str] = None  # None indicates Live active session
        self._refresh_timer_job: Optional[str] = None
        self._is_closed: bool = False
        self._history_id_map: Dict[str, Optional[str]] = {}

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_header()
        self._build_tab_bar()
        self._build_content_panels()

        # Initial populate
        self._refresh_overview()
        self._schedule_periodic_refresh()

    def _on_close(self) -> None:
        """Cancel pending timer and destroy dialog."""
        self._is_closed = True
        if self._refresh_timer_job is not None:
            try:
                self.after_cancel(self._refresh_timer_job)
            except Exception:
                pass
            self._refresh_timer_job = None
        try:
            self.destroy()
        except Exception:
            pass

    def _schedule_periodic_refresh(self) -> None:
        """Schedule periodic 1-second refresh for live active session metrics."""
        if not self._is_closed:
            self._refresh_timer_job = self.after(1000, self._periodic_refresh)

    def _periodic_refresh(self) -> None:
        """Timer callback that refreshes live statistics if currently viewing active session."""
        if self._is_closed:
            return
        try:
            if self._active_tab == "overview" and self._selected_session_id is None:
                self._refresh_overview()
        except Exception as exc:
            logger.debug("Analytics periodic refresh skipped: %s", exc)
        finally:
            self._schedule_periodic_refresh()

    def _manual_refresh(self) -> None:
        """Explicit refresh button callback."""
        if self._active_tab == "overview":
            self._refresh_overview()
        elif self._active_tab == "history":
            self._refresh_history()
        elif self._active_tab == "compare":
            self._refresh_compare()

    # -----------------------------------------------------------------------
    # Header & Tabs
    # -----------------------------------------------------------------------
    def _build_header(self) -> None:
        header = tk.Frame(self, bg=COLOR_BG_HEADER, height=58)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        accent_line = tk.Frame(self, bg=COLOR_BORDER, height=1)
        accent_line.pack(side="top", fill="x")

        title_box = tk.Frame(header, bg=COLOR_BG_HEADER)
        title_box.pack(side="left", padx=16, pady=8)

        lbl = tk.Label(
            title_box,
            text="📊  SESSION HISTORY & VISUAL ANALYTICS",
            font=FONT_APP_TITLE,
            bg=COLOR_BG_HEADER,
            fg=COLOR_ACCENT_CYAN,
        )
        lbl.pack(side="top", anchor="w")

        sub = tk.Label(
            title_box,
            text="Phase 6: Live gesture recognition counts, native visual charts, action logs, and SQLite history.",
            font=FONT_SMALL,
            bg=COLOR_BG_HEADER,
            fg=COLOR_TEXT_SECONDARY,
        )
        sub.pack(side="top", anchor="w")

        right_box = tk.Frame(header, bg=COLOR_BG_HEADER)
        right_box.pack(side="right", padx=16, pady=12)

        self.btn_refresh = ModernButton(
            right_box,
            text="🔄 Refresh",
            bg_color=COLOR_BG_CARD_INNER,
            hover_color="#1E2E4E",
            fg_color=COLOR_ACCENT_CYAN,
            font=(FONT_FAMILY, 9, "bold"),
            padx=10,
            pady=4,
            command=self._manual_refresh,
        )
        self.btn_refresh.pack(side="right")

    def _build_tab_bar(self) -> None:
        tab_frame = tk.Frame(self, bg=COLOR_BG_ROOT, height=44)
        tab_frame.pack(side="top", fill="x", padx=16, pady=(10, 4))

        self.btn_tab_overview = ModernButton(
            tab_frame,
            text="📊 Overview & Charts",
            bg_color=COLOR_BG_CARD_INNER,
            hover_color="#1E2E4E",
            fg_color=COLOR_ACCENT_CYAN,
            font=(FONT_FAMILY, 10, "bold"),
            padx=14,
            pady=6,
            command=lambda: self._switch_tab("overview"),
        )
        self.btn_tab_overview.pack(side="left", padx=(0, 8))

        self.btn_tab_history = ModernButton(
            tab_frame,
            text="🕒 Session History",
            bg_color=COLOR_BG_SURFACE,
            hover_color="#1E2E4E",
            fg_color=COLOR_TEXT_SECONDARY,
            font=(FONT_FAMILY, 10, "bold"),
            padx=14,
            pady=6,
            command=lambda: self._switch_tab("history"),
        )
        self.btn_tab_history.pack(side="left", padx=(0, 8))

        self.btn_tab_compare = ModernButton(
            tab_frame,
            text="⚖️ Compare Sessions",
            bg_color=COLOR_BG_SURFACE,
            hover_color="#1E2E4E",
            fg_color=COLOR_TEXT_SECONDARY,
            font=(FONT_FAMILY, 10, "bold"),
            padx=14,
            pady=6,
            command=lambda: self._switch_tab("compare"),
        )
        self.btn_tab_compare.pack(side="left")

    def _build_content_panels(self) -> None:
        self.container = tk.Frame(self, bg=COLOR_BG_ROOT)
        self.container.pack(side="top", fill="both", expand=True, padx=16, pady=6)

        # Tab 1: Overview Panel
        self.panel_overview = tk.Frame(self.container, bg=COLOR_BG_ROOT)
        self._build_overview_panel(self.panel_overview)

        # Tab 2: History Panel
        self.panel_history = tk.Frame(self.container, bg=COLOR_BG_ROOT)
        self._build_history_panel(self.panel_history)

        # Tab 3: Compare Panel
        self.panel_compare = tk.Frame(self.container, bg=COLOR_BG_ROOT)
        self._build_compare_panel(self.panel_compare)

        # Default display
        self._switch_tab("overview")

    def _switch_tab(self, tab_name: str) -> None:
        self._active_tab = tab_name
        self.panel_overview.pack_forget()
        self.panel_history.pack_forget()
        self.panel_compare.pack_forget()

        # Reset button styling
        self.btn_tab_overview.set_colors(COLOR_BG_SURFACE, "#1E2E4E", COLOR_TEXT_SECONDARY)
        self.btn_tab_history.set_colors(COLOR_BG_SURFACE, "#1E2E4E", COLOR_TEXT_SECONDARY)
        self.btn_tab_compare.set_colors(COLOR_BG_SURFACE, "#1E2E4E", COLOR_TEXT_SECONDARY)

        if tab_name == "overview":
            self.panel_overview.pack(fill="both", expand=True)
            self.btn_tab_overview.set_colors(COLOR_BG_CARD_INNER, "#1E2E4E", COLOR_ACCENT_CYAN)
            self._refresh_overview()
        elif tab_name == "history":
            self.panel_history.pack(fill="both", expand=True)
            self.btn_tab_history.set_colors(COLOR_BG_CARD_INNER, "#1E2E4E", COLOR_ACCENT_CYAN)
            self._refresh_history()
        elif tab_name == "compare":
            self.panel_compare.pack(fill="both", expand=True)
            self.btn_tab_compare.set_colors(COLOR_BG_CARD_INNER, "#1E2E4E", COLOR_ACCENT_CYAN)
            self._refresh_compare()

    # -----------------------------------------------------------------------
    # Tab 1: Overview & Bar Chart
    # -----------------------------------------------------------------------
    def _build_overview_panel(self, parent: tk.Frame) -> None:
        # 1. Top Session Selector Bar
        selector_frame = tk.Frame(
            parent,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=12,
            pady=8,
        )
        selector_frame.pack(side="top", fill="x", pady=(0, 10))

        tk.Label(
            selector_frame,
            text="Viewing Session:",
            font=FONT_BODY_BOLD,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_PRIMARY,
        ).pack(side="left", padx=(0, 8))

        self.session_var = tk.StringVar(value="● Active Session (Live)")
        self.combo_session = ttk.Combobox(
            selector_frame,
            textvariable=self.session_var,
            state="readonly",
            width=46,
            font=FONT_SMALL,
        )
        self.combo_session.pack(side="left", padx=(0, 10))
        self.combo_session.bind("<<ComboboxSelected>>", self._on_session_dropdown_change)

        self.btn_return_live = ModernButton(
            selector_frame,
            text="↺ Live Session",
            bg_color="#1E293B",
            hover_color="#334155",
            fg_color=COLOR_ACCENT_CYAN,
            font=(FONT_FAMILY, 9, "bold"),
            padx=10,
            pady=4,
            command=self._return_to_live_session,
        )
        self.btn_return_live.pack(side="left")

        self.lbl_session_badge = tk.Label(
            selector_frame,
            text="● LIVE ACTIVE",
            font=FONT_BADGE,
            bg="#064E3B",
            fg="#6EE7B7",
            padx=8,
            pady=2,
        )
        self.lbl_session_badge.pack(side="right")

        # 2. KPI Metrics Grid (4 cards)
        kpi_frame = tk.Frame(parent, bg=COLOR_BG_ROOT)
        kpi_frame.pack(side="top", fill="x", pady=(0, 10))
        for col_idx in range(4):
            kpi_frame.columnconfigure(col_idx, weight=1)

        self.lbl_kpi_duration = self._create_kpi_card(
            kpi_frame, 0, "SESSION DURATION", "00:00", COLOR_ACCENT_CYAN
        )
        self.lbl_kpi_total_gestures = self._create_kpi_card(
            kpi_frame, 1, "TOTAL GESTURES", "0", COLOR_TEXT_PRIMARY
        )
        self.lbl_kpi_most_used = self._create_kpi_card(
            kpi_frame, 2, "MOST-USED GESTURE", "None (0)", COLOR_TEXT_PRIMARY
        )
        self.lbl_kpi_actions = self._create_kpi_card(
            kpi_frame, 3, "ACTIONS SUCCESS", "0 / 0", "#10B981"
        )

        # 3. Bar Chart Frame
        chart_box = tk.Frame(
            parent,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        chart_box.pack(side="top", fill="both", expand=True, pady=(0, 10))

        chart_header = tk.Frame(chart_box, bg=COLOR_BG_CARD_INNER)
        chart_header.pack(side="top", fill="x", pady=(0, 6))

        tk.Label(
            chart_header,
            text="GESTURE FREQUENCY DISTRIBUTION",
            font=FONT_CARD_TITLE,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_PRIMARY,
        ).pack(side="left")

        tk.Label(
            chart_header,
            text="Distinct Stabilized Recognition Events",
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
        ).pack(side="right")

        self.chart_canvas = tk.Canvas(
            chart_box,
            bg=COLOR_BG_SURFACE,
            bd=0,
            highlightthickness=0,
            height=230,
        )
        self.chart_canvas.pack(side="top", fill="both", expand=True)

        # 4. Action Summary Breakdown
        actions_box = tk.Frame(
            parent,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        actions_box.pack(side="top", fill="x")

        act_header = tk.Frame(actions_box, bg=COLOR_BG_CARD_INNER)
        act_header.pack(side="top", fill="x", pady=(0, 6))

        tk.Label(
            act_header,
            text="SYSTEM ACTIONS & SAFETY OUTCOMES",
            font=FONT_CARD_TITLE,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_PRIMARY,
        ).pack(side="left")

        pills_frame = tk.Frame(act_header, bg=COLOR_BG_CARD_INNER)
        pills_frame.pack(side="right")

        self.pill_success = tk.Label(
            pills_frame,
            text="Successful: 0",
            font=FONT_BADGE,
            bg="#064E3B",
            fg="#6EE7B7",
            padx=8,
            pady=2,
        )
        self.pill_success.pack(side="left", padx=4)

        self.pill_blocked = tk.Label(
            pills_frame,
            text="Blocked: 0",
            font=FONT_BADGE,
            bg="#78350F",
            fg="#FDE68A",
            padx=8,
            pady=2,
        )
        self.pill_blocked.pack(side="left", padx=4)

        self.pill_failed = tk.Label(
            pills_frame,
            text="Failed: 0",
            font=FONT_BADGE,
            bg="#7F1D1D",
            fg="#FECACA",
            padx=8,
            pady=2,
        )
        self.pill_failed.pack(side="left", padx=4)

        self.lbl_actions_detail = tk.Label(
            actions_box,
            text="No system actions attempted in this session.",
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
            anchor="w",
            justify="left",
        )
        self.lbl_actions_detail.pack(side="top", fill="x", pady=(4, 0))

    def _create_kpi_card(
        self, parent: tk.Frame, col: int, label_text: str, default_val: str, val_color: str
    ) -> tk.Label:
        box = tk.Frame(
            parent,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=10,
            pady=8,
        )
        box.grid(row=0, column=col, sticky="nsew", padx=3)

        tk.Label(
            box,
            text=label_text,
            font=FONT_STAT_LABEL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
        ).pack(side="top", anchor="w")

        val_lbl = tk.Label(
            box,
            text=default_val,
            font=(FONT_FAMILY, 15, "bold"),
            bg=COLOR_BG_CARD_INNER,
            fg=val_color,
        )
        val_lbl.pack(side="top", anchor="w", pady=(2, 0))
        return val_lbl

    def _on_session_dropdown_change(self, event=None) -> None:
        val = self.session_var.get()
        self._selected_session_id = self._history_id_map.get(val, None)
        self._refresh_overview()

    def _return_to_live_session(self) -> None:
        self._selected_session_id = None
        self._refresh_overview()

    def _select_session_by_id(self, session_id: str) -> None:
        self._selected_session_id = session_id
        self._switch_tab("overview")

    def _refresh_overview(self) -> None:
        """Update KPI metrics, chart, and action summary for the active or selected session."""
        history = self.statistics_manager.get_history(limit=50)

        # Update combobox values
        combo_items = ["● Active Session (Live)"]
        id_map: Dict[str, Optional[str]] = {"● Active Session (Live)": None}
        for s in history:
            label = f"[{s.start_time_formatted}] {s.session_id} • Dur: {s.duration_formatted} • {s.total_gestures} Gestures"
            combo_items.append(label)
            id_map[label] = s.session_id
        self._history_id_map = id_map

        # Keep current combobox selection
        if self._selected_session_id is None:
            self.session_var.set("● Active Session (Live)")
            self.lbl_session_badge.configure(text="● LIVE ACTIVE", bg="#064E3B", fg="#6EE7B7")
            record = self.statistics_manager.get_current_session_record()
        else:
            record = self.statistics_manager.get_session_by_id(self._selected_session_id)
            if record is None:
                self._selected_session_id = None
                self.session_var.set("● Active Session (Live)")
                self.lbl_session_badge.configure(text="● LIVE ACTIVE", bg="#064E3B", fg="#6EE7B7")
                record = self.statistics_manager.get_current_session_record()
            else:
                self.lbl_session_badge.configure(text="ARCHIVED SESSION", bg="#1E293B", fg=COLOR_TEXT_SECONDARY)
                for lbl_text, sid in id_map.items():
                    if sid == self._selected_session_id:
                        self.session_var.set(lbl_text)
                        break

        self.combo_session["values"] = combo_items

        # Populate KPI tiles
        self.lbl_kpi_duration.configure(text=record.duration_formatted)
        self.lbl_kpi_total_gestures.configure(text=str(record.total_gestures))
        most_name = record.most_used_gesture
        most_cnt = record.gesture_counts.get(most_name, 0)
        self.lbl_kpi_most_used.configure(text=f"{most_name} ({most_cnt})")
        tot_acts = record.successful_actions + record.blocked_actions + record.failed_actions
        self.lbl_kpi_actions.configure(text=f"{record.successful_actions} / {tot_acts}")

        # Update Action Pills
        self.pill_success.configure(text=f"Successful: {record.successful_actions}")
        self.pill_blocked.configure(text=f"Blocked: {record.blocked_actions}")
        self.pill_failed.configure(text=f"Failed: {record.failed_actions}")

        if record.action_counts:
            breakdown_str = " • ".join(
                f"{act}: {c}" for act, c in sorted(record.action_counts.items(), key=lambda x: -x[1])
            )
            self.lbl_actions_detail.configure(
                text=f"Action execution counts: {breakdown_str}",
                fg=COLOR_TEXT_PRIMARY,
            )
        else:
            self.lbl_actions_detail.configure(
                text="No successful system actions registered in this session.",
                fg=COLOR_TEXT_MUTED,
            )

        # Draw chart
        self._render_bar_chart(self.chart_canvas, record.gesture_counts, record.total_gestures)

    def _render_bar_chart(
        self, canvas: tk.Canvas, gesture_counts: Dict[str, int], total_gestures: int
    ) -> None:
        canvas.delete("all")
        canvas.update_idletasks()
        w = max(500, canvas.winfo_width())
        h = max(200, canvas.winfo_height())

        if total_gestures <= 0 or not any(c > 0 for c in gesture_counts.values()):
            cx = w // 2
            cy = h // 2
            canvas.create_oval(cx - 24, cy - 40, cx + 24, cy + 8, outline=COLOR_BORDER, fill="#1E293B", width=2)
            canvas.create_text(cx, cy - 16, text="📊", font=(FONT_FAMILY, 16))
            canvas.create_text(
                cx,
                cy + 22,
                text="No gestures recognized in this session yet",
                fill=COLOR_TEXT_SECONDARY,
                font=(FONT_FAMILY, 11, "bold"),
            )
            canvas.create_text(
                cx,
                cy + 42,
                text="Show gestures to the camera to see real-time frequency distribution.",
                fill=COLOR_TEXT_MUTED,
                font=FONT_SMALL,
            )
            return

        # Render bars
        max_val = max(1, max(gesture_counts.values()))
        left_margin = 115
        right_margin = 95
        top_margin = 12
        max_bar_w = max(100, w - left_margin - right_margin)
        row_h = 22

        for idx, gesture in enumerate(SUPPORTED_GESTURES):
            y = top_margin + idx * row_h
            cnt = gesture_counts.get(gesture, 0)
            pct = (cnt / total_gestures * 100.0) if total_gestures > 0 else 0.0

            # Label on left
            canvas.create_text(
                left_margin - 10,
                y + 8,
                text=gesture,
                anchor="e",
                fill=COLOR_TEXT_PRIMARY if cnt > 0 else COLOR_TEXT_SECONDARY,
                font=FONT_SMALL,
            )

            # Background bar track
            canvas.create_rectangle(
                left_margin,
                y + 2,
                left_margin + max_bar_w,
                y + 15,
                fill=COLOR_BG_CARD_INNER,
                outline=COLOR_BORDER,
            )

            # Filled bar
            if cnt > 0:
                bar_w = int((cnt / max_val) * max_bar_w)
                canvas.create_rectangle(
                    left_margin,
                    y + 2,
                    left_margin + bar_w,
                    y + 15,
                    fill=COLOR_ACCENT_BLUE,
                    outline=COLOR_ACCENT_CYAN,
                )

            # Percentage & count on right
            canvas.create_text(
                left_margin + max_bar_w + 10,
                y + 8,
                text=f"{cnt} ({pct:.1f}%)",
                anchor="w",
                fill=COLOR_TEXT_ACCENT if cnt > 0 else COLOR_TEXT_MUTED,
                font=FONT_SMALL,
            )

    # -----------------------------------------------------------------------
    # Tab 2: Session History Panel
    # -----------------------------------------------------------------------
    def _build_history_panel(self, parent: tk.Frame) -> None:
        # Header banner
        header_bar = tk.Frame(
            parent,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=12,
            pady=8,
        )
        header_bar.pack(side="top", fill="x", pady=(0, 10))

        self.lbl_history_count = tk.Label(
            header_bar,
            text="Completed Sessions Log (Newest First):",
            font=FONT_CARD_TITLE,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_PRIMARY,
        )
        self.lbl_history_count.pack(side="left")

        # Scrollable container for session cards
        canvas_container = tk.Frame(parent, bg=COLOR_BG_ROOT)
        canvas_container.pack(side="top", fill="both", expand=True)

        self.hist_canvas = tk.Canvas(canvas_container, bg=COLOR_BG_ROOT, bd=0, highlightthickness=0)
        self.hist_scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=self.hist_canvas.yview)
        self.hist_scroll_frame = tk.Frame(self.hist_canvas, bg=COLOR_BG_ROOT)

        self.hist_scroll_frame.bind(
            "<Configure>", lambda e: self.hist_canvas.configure(scrollregion=self.hist_canvas.bbox("all"))
        )
        self._hist_win = self.hist_canvas.create_window((0, 0), window=self.hist_scroll_frame, anchor="nw")

        def _conf_w(e):
            self.hist_canvas.itemconfig(self._hist_win, width=e.width)

        self.hist_canvas.bind("<Configure>", _conf_w)
        self.hist_canvas.configure(yscrollcommand=self.hist_scrollbar.set)

        self.hist_canvas.pack(side="left", fill="both", expand=True)
        self.hist_scrollbar.pack(side="right", fill="y")

        # Bottom Bar: Path & Clear Button
        bottom_bar = tk.Frame(
            parent,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=12,
            pady=8,
        )
        bottom_bar.pack(side="bottom", fill="x", pady=(10, 0))

        tk.Label(
            bottom_bar,
            text=f"SQLite Database: {self.statistics_manager.db_path}",
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
        ).pack(side="left")

        self.btn_clear_hist = ModernButton(
            bottom_bar,
            text="🗑 Clear History",
            bg_color="#7F1D1D",
            hover_color="#991B1B",
            fg_color="#FECACA",
            font=(FONT_FAMILY, 9, "bold"),
            padx=10,
            pady=4,
            command=self._clear_history,
        )
        self.btn_clear_hist.pack(side="right")

    def _refresh_history(self) -> None:
        """Populate the historical sessions list."""
        for child in self.hist_scroll_frame.winfo_children():
            child.destroy()

        history = self.statistics_manager.get_history(limit=50)
        self.lbl_history_count.configure(
            text=f"Completed Sessions Log ({len(history)} stored, newest first):"
        )

        if not history:
            empty_box = tk.Frame(
                self.hist_scroll_frame,
                bg=COLOR_BG_CARD_INNER,
                highlightbackground=COLOR_BORDER,
                highlightthickness=1,
                padx=20,
                pady=30,
            )
            empty_box.pack(side="top", fill="x", pady=20, padx=10)

            tk.Label(
                empty_box,
                text="No historical sessions stored yet.",
                font=(FONT_FAMILY, 12, "bold"),
                bg=COLOR_BG_CARD_INNER,
                fg=COLOR_TEXT_PRIMARY,
            ).pack(side="top", pady=(0, 6))

            tk.Label(
                empty_box,
                text="When you close the application, your current session will be automatically\nand safely persisted to the local SQLite database.",
                font=FONT_SMALL,
                bg=COLOR_BG_CARD_INNER,
                fg=COLOR_TEXT_SECONDARY,
                justify="center",
            ).pack(side="top")
            return

        for rec in history:
            card = tk.Frame(
                self.hist_scroll_frame,
                bg=COLOR_BG_CARD_INNER,
                highlightbackground=COLOR_BORDER,
                highlightthickness=1,
                padx=12,
                pady=8,
            )
            card.pack(side="top", fill="x", pady=4, padx=2)

            top_row = tk.Frame(card, bg=COLOR_BG_CARD_INNER)
            top_row.pack(side="top", fill="x")

            tk.Label(
                top_row,
                text=f"🗓 {rec.start_time_formatted}",
                font=FONT_BODY_BOLD,
                bg=COLOR_BG_CARD_INNER,
                fg=COLOR_TEXT_PRIMARY,
            ).pack(side="left")

            tk.Label(
                top_row,
                text=f"ID: {rec.session_id}",
                font=FONT_SMALL,
                bg=COLOR_BG_ROOT,
                fg=COLOR_TEXT_MUTED,
                padx=6,
                pady=1,
            ).pack(side="left", padx=10)

            btn_inspect = ModernButton(
                top_row,
                text="🔍 View Details",
                bg_color=COLOR_ACCENT_BLUE,
                hover_color="#0369A1",
                fg_color="#FFFFFF",
                font=(FONT_FAMILY, 9, "bold"),
                padx=8,
                pady=2,
                command=lambda sid=rec.session_id: self._select_session_by_id(sid),
            )
            btn_inspect.pack(side="right")

            bot_row = tk.Frame(card, bg=COLOR_BG_CARD_INNER)
            bot_row.pack(side="top", fill="x", pady=(4, 0))

            tk.Label(
                bot_row,
                text=f"Duration: {rec.duration_formatted}  •  Total Gestures: {rec.total_gestures}  •  Top: {rec.most_used_gesture}  •  Actions: {rec.successful_actions} succ, {rec.blocked_actions} blocked, {rec.failed_actions} failed",
                font=FONT_SMALL,
                bg=COLOR_BG_CARD_INNER,
                fg=COLOR_TEXT_SECONDARY,
            ).pack(side="left")

    def _clear_history(self) -> None:
        """Reset historical SQLite sessions."""
        self.statistics_manager.clear_history()
        self._refresh_history()
        if self._selected_session_id is not None:
            self._selected_session_id = None
        self._refresh_overview()

    # -----------------------------------------------------------------------
    # Tab 3: Compare Sessions Panel
    # -----------------------------------------------------------------------
    def _build_compare_panel(self, parent: tk.Frame) -> None:
        # Session A & Session B Selection Bar
        selector_frame = tk.Frame(
            parent,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=12,
            pady=8,
        )
        selector_frame.pack(side="top", fill="x", pady=(0, 10))

        # Session A
        tk.Label(
            selector_frame,
            text="Session A:",
            font=FONT_BODY_BOLD,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_ACCENT_CYAN,
        ).pack(side="left", padx=(0, 4))

        self.compare_a_var = tk.StringVar(value="● Active Session (Live)")
        self.combo_compare_a = ttk.Combobox(
            selector_frame,
            textvariable=self.compare_a_var,
            state="readonly",
            width=28,
            font=FONT_SMALL,
        )
        self.combo_compare_a.pack(side="left", padx=(0, 12))
        self.combo_compare_a.bind("<<ComboboxSelected>>", lambda e: self._refresh_compare())

        # Session B
        tk.Label(
            selector_frame,
            text="Session B:",
            font=FONT_BODY_BOLD,
            bg=COLOR_BG_CARD_INNER,
            fg="#F59E0B",
        ).pack(side="left", padx=(0, 4))

        self.compare_b_var = tk.StringVar()
        self.combo_compare_b = ttk.Combobox(
            selector_frame,
            textvariable=self.compare_b_var,
            state="readonly",
            width=28,
            font=FONT_SMALL,
        )
        self.combo_compare_b.pack(side="left", padx=(0, 10))
        self.combo_compare_b.bind("<<ComboboxSelected>>", lambda e: self._refresh_compare())

        ModernButton(
            selector_frame,
            text="⚡ Compare",
            bg_color=COLOR_BG_CARD_INNER,
            hover_color="#1E2E4E",
            fg_color=COLOR_ACCENT_CYAN,
            font=(FONT_FAMILY, 9, "bold"),
            padx=8,
            pady=3,
            command=self._refresh_compare,
        ).pack(side="left")

        # Side by side KPI cards
        kpi_grid = tk.Frame(parent, bg=COLOR_BG_ROOT)
        kpi_grid.pack(side="top", fill="x", pady=(0, 10))
        kpi_grid.columnconfigure(0, weight=1)
        kpi_grid.columnconfigure(1, weight=1)

        # Card A
        self.box_comp_a = tk.Frame(
            kpi_grid,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground=COLOR_ACCENT_CYAN,
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        self.box_comp_a.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.lbl_comp_a_title = tk.Label(
            self.box_comp_a,
            text="SESSION A (Active Live)",
            font=FONT_CARD_TITLE,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_ACCENT_CYAN,
        )
        self.lbl_comp_a_title.pack(side="top", anchor="w")
        self.lbl_comp_a_stats = tk.Label(
            self.box_comp_a,
            text="Duration: 00:00\nGestures: 0\nTop: None\nActions: 0 succ",
            font=FONT_BODY,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_PRIMARY,
            justify="left",
        )
        self.lbl_comp_a_stats.pack(side="top", anchor="w", pady=(4, 0))

        # Card B
        self.box_comp_b = tk.Frame(
            kpi_grid,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground="#F59E0B",
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        self.box_comp_b.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.lbl_comp_b_title = tk.Label(
            self.box_comp_b,
            text="SESSION B (Select Above)",
            font=FONT_CARD_TITLE,
            bg=COLOR_BG_CARD_INNER,
            fg="#F59E0B",
        )
        self.lbl_comp_b_title.pack(side="top", anchor="w")
        self.lbl_comp_b_stats = tk.Label(
            self.box_comp_b,
            text="Duration: 00:00\nGestures: 0\nTop: None\nActions: 0 succ",
            font=FONT_BODY,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_PRIMARY,
            justify="left",
        )
        self.lbl_comp_b_stats.pack(side="top", anchor="w", pady=(4, 0))

        # Comparison Table
        table_frame = tk.Frame(
            parent,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        table_frame.pack(side="top", fill="both", expand=True)

        tk.Label(
            table_frame,
            text="GESTURE FREQUENCY COMPARISON",
            font=FONT_CARD_TITLE,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_PRIMARY,
        ).pack(side="top", anchor="w", pady=(0, 6))

        # Table header
        th = tk.Frame(table_frame, bg=COLOR_BG_SURFACE, padx=6, pady=4)
        th.pack(side="top", fill="x")
        th.columnconfigure(0, weight=3)
        th.columnconfigure(1, weight=2)
        th.columnconfigure(2, weight=2)
        th.columnconfigure(3, weight=2)

        tk.Label(th, text="Gesture", font=FONT_BODY_BOLD, bg=COLOR_BG_SURFACE, fg=COLOR_TEXT_PRIMARY, anchor="w").grid(row=0, column=0, sticky="w")
        tk.Label(th, text="Session A", font=FONT_BODY_BOLD, bg=COLOR_BG_SURFACE, fg=COLOR_ACCENT_CYAN, anchor="center").grid(row=0, column=1, sticky="ew")
        tk.Label(th, text="Session B", font=FONT_BODY_BOLD, bg=COLOR_BG_SURFACE, fg="#F59E0B", anchor="center").grid(row=0, column=2, sticky="ew")
        tk.Label(th, text="Difference", font=FONT_BODY_BOLD, bg=COLOR_BG_SURFACE, fg=COLOR_TEXT_SECONDARY, anchor="e").grid(row=0, column=3, sticky="e")

        # Table rows container
        self.compare_rows_frame = tk.Frame(table_frame, bg=COLOR_BG_CARD_INNER)
        self.compare_rows_frame.pack(side="top", fill="both", expand=True, pady=(4, 0))

    def _refresh_compare(self) -> None:
        """Update side-by-side comparison between Session A and Session B."""
        history = self.statistics_manager.get_history(limit=50)
        curr_rec = self.statistics_manager.get_current_session_record()

        options_map: Dict[str, SessionRecord] = {"● Active Session (Live)": curr_rec}
        for s in history:
            lbl = f"[{s.start_time_formatted}] {s.session_id[:12]}"
            options_map[lbl] = s

        combo_values = list(options_map.keys())
        self.combo_compare_a["values"] = combo_values
        self.combo_compare_b["values"] = combo_values

        if not self.compare_a_var.get() or self.compare_a_var.get() not in options_map:
            self.compare_a_var.set("● Active Session (Live)")

        if not self.compare_b_var.get() or self.compare_b_var.get() not in options_map:
            if len(combo_values) > 1:
                self.compare_b_var.set(combo_values[1])
            else:
                self.compare_b_var.set("● Active Session (Live)")

        recA = options_map.get(self.compare_a_var.get(), curr_rec)
        recB = options_map.get(self.compare_b_var.get(), curr_rec)

        # Update Card A
        self.lbl_comp_a_title.configure(text=f"SESSION A: {recA.session_id[:16]}")
        self.lbl_comp_a_stats.configure(
            text=(
                f"Duration: {recA.duration_formatted}\n"
                f"Total Gestures: {recA.total_gestures}\n"
                f"Top Gesture: {recA.most_used_gesture} ({recA.gesture_counts.get(recA.most_used_gesture, 0)})\n"
                f"Actions: {recA.successful_actions} succ • {recA.blocked_actions} blocked • {recA.failed_actions} failed"
            )
        )

        # Update Card B
        self.lbl_comp_b_title.configure(text=f"SESSION B: {recB.session_id[:16]}")
        self.lbl_comp_b_stats.configure(
            text=(
                f"Duration: {recB.duration_formatted}\n"
                f"Total Gestures: {recB.total_gestures}\n"
                f"Top Gesture: {recB.most_used_gesture} ({recB.gesture_counts.get(recB.most_used_gesture, 0)})\n"
                f"Actions: {recB.successful_actions} succ • {recB.blocked_actions} blocked • {recB.failed_actions} failed"
            )
        )

        # Update comparison rows
        for child in self.compare_rows_frame.winfo_children():
            child.destroy()

        for g in SUPPORTED_GESTURES:
            cntA = recA.gesture_counts.get(g, 0)
            pctA = (cntA / recA.total_gestures * 100.0) if recA.total_gestures > 0 else 0.0
            cntB = recB.gesture_counts.get(g, 0)
            pctB = (cntB / recB.total_gestures * 100.0) if recB.total_gestures > 0 else 0.0

            diff = cntA - cntB
            diff_str = f"+{diff}" if diff > 0 else str(diff)
            diff_color = "#10B981" if diff > 0 else ("#EF4444" if diff < 0 else COLOR_TEXT_MUTED)

            row_frame = tk.Frame(self.compare_rows_frame, bg=COLOR_BG_CARD_INNER, pady=2)
            row_frame.pack(side="top", fill="x")
            row_frame.columnconfigure(0, weight=3)
            row_frame.columnconfigure(1, weight=2)
            row_frame.columnconfigure(2, weight=2)
            row_frame.columnconfigure(3, weight=2)

            tk.Label(row_frame, text=g, font=FONT_SMALL, bg=COLOR_BG_CARD_INNER, fg=COLOR_TEXT_PRIMARY, anchor="w").grid(row=0, column=0, sticky="w")
            tk.Label(row_frame, text=f"{cntA} ({pctA:.0f}%)", font=FONT_SMALL, bg=COLOR_BG_CARD_INNER, fg=COLOR_ACCENT_CYAN, anchor="center").grid(row=0, column=1, sticky="ew")
            tk.Label(row_frame, text=f"{cntB} ({pctB:.0f}%)", font=FONT_SMALL, bg=COLOR_BG_CARD_INNER, fg="#F59E0B", anchor="center").grid(row=0, column=2, sticky="ew")
            tk.Label(row_frame, text=diff_str, font=(FONT_FAMILY, 9, "bold"), bg=COLOR_BG_CARD_INNER, fg=diff_color, anchor="e").grid(row=0, column=3, sticky="e")


class AppUI:
    """
    Main user interface controller for Hand Gesture Controller desktop application.
    """

    def __init__(
        self,
        root: tk.Tk,
        camera_service: CameraService,
        statistics_manager: Optional[StatisticsManager] = None,
    ) -> None:
        self.root: tk.Tk = root
        self.camera_service: CameraService = camera_service

        # State tracking & Phase 5/6 managers
        self.settings_manager: SettingsManager = SettingsManager()
        self.statistics_manager: StatisticsManager = (
            statistics_manager if statistics_manager is not None else StatisticsManager()
        )
        self.control_manager: ControlManager = ControlManager()
        self.control_manager.set_statistics_manager(self.statistics_manager)
        self._settings_dialog: Optional[SettingsDialog] = None
        self._analytics_dialog: Optional[AnalyticsDialog] = None
        self._photo_image: Optional[ImageTk.PhotoImage] = None
        self._is_closing: bool = False
        self._last_status: str = STATUS_STOPPED
        self._poll_job: Optional[str] = None
        self._last_processed_frame_count: int = -1

        # Dynamically apply loaded persistent settings to active components
        self.settings_manager.apply_to_components(
            self.settings_manager.current_settings,
            gesture_recognizer=(
                self.camera_service.hand_detector.gesture_recognizer
                if self.camera_service.hand_detector is not None
                else None
            ),
            control_manager=self.control_manager,
        )

        # Configure root window
        self._setup_root_window()

        # Build UI layout
        self._build_header()
        self._build_main_container()
        self._build_status_bar()

        # Draw initial offline screen
        self._draw_offline_preview()

        # Start non-blocking polling loop
        self._schedule_poll()

    # -----------------------------------------------------------------------
    # Window Initialization
    # -----------------------------------------------------------------------
    def _setup_root_window(self) -> None:
        """Set up main window properties, title, size, and close handlers."""
        self.root.title(f"{APP_TITLE} — {APP_SUBTITLE}")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.root.configure(bg=COLOR_BG_ROOT)

        # Handle window close gracefully
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Keyboard shortcuts
        self.root.bind("<space>", lambda event: self._toggle_camera())
        self.root.bind("<Escape>", lambda event: (self._emergency_stop_actions(), self._stop_camera()))

    # -----------------------------------------------------------------------
    # Header Bar
    # -----------------------------------------------------------------------
    def _build_header(self) -> None:
        """Build the top title and branding banner."""
        header_frame = tk.Frame(self.root, bg=COLOR_BG_HEADER, height=64)
        header_frame.pack(side="top", fill="x")
        header_frame.pack_propagate(False)

        # Bottom accent border line
        accent_line = tk.Frame(self.root, bg=COLOR_BORDER, height=1)
        accent_line.pack(side="top", fill="x")

        # Left branding block
        branding_box = tk.Frame(header_frame, bg=COLOR_BG_HEADER)
        branding_box.pack(side="left", fill="y", padx=20, pady=8)

        title_row = tk.Frame(branding_box, bg=COLOR_BG_HEADER)
        title_row.pack(side="top", anchor="w")

        # Cyan indicator dot
        dot_canvas = tk.Canvas(title_row, width=12, height=12, bg=COLOR_BG_HEADER, bd=0, highlightthickness=0)
        dot_canvas.pack(side="left", padx=(0, 8), pady=2)
        dot_canvas.create_oval(2, 2, 10, 10, fill=COLOR_ACCENT_CYAN, outline="")

        title_lbl = tk.Label(
            title_row,
            text=APP_TITLE,
            font=FONT_APP_TITLE,
            bg=COLOR_BG_HEADER,
            fg=COLOR_TEXT_PRIMARY,
        )
        title_lbl.pack(side="left")

        version_pill = tk.Label(
            title_row,
            text=f"v{APP_VERSION}",
            font=FONT_BADGE,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_ACCENT_CYAN,
            padx=6,
            pady=1,
        )
        version_pill.pack(side="left", padx=8)

        subtitle_lbl = tk.Label(
            branding_box,
            text=APP_SUBTITLE,
            font=FONT_APP_SUBTITLE,
            bg=COLOR_BG_HEADER,
            fg=COLOR_TEXT_SECONDARY,
        )
        subtitle_lbl.pack(side="top", anchor="w", pady=(1, 0))

        # Right status badge block
        right_box = tk.Frame(header_frame, bg=COLOR_BG_HEADER)
        right_box.pack(side="right", fill="y", padx=20, pady=12)

        # Analytics Button in Header (Phase 6)
        self.btn_header_analytics = ModernButton(
            right_box,
            text="📊 Analytics",
            bg_color=COLOR_BG_CARD_INNER,
            hover_color="#1E2E4E",
            fg_color=COLOR_ACCENT_CYAN,
            font=(FONT_FAMILY, 9, "bold"),
            padx=10,
            pady=4,
            command=self.open_analytics_dialog,
        )
        self.btn_header_analytics.pack(side="right", padx=(10, 0))

        # Settings Button in Header (Phase 5)
        self.btn_header_settings = ModernButton(
            right_box,
            text="⚙ Settings",
            bg_color=COLOR_BG_CARD_INNER,
            hover_color="#1E2E4E",
            fg_color=COLOR_ACCENT_CYAN,
            font=(FONT_FAMILY, 9, "bold"),
            padx=10,
            pady=4,
            command=self.open_settings_dialog,
        )
        self.btn_header_settings.pack(side="right", padx=(10, 0))

        mac_badge = tk.Label(
            right_box,
            text="macOS Vision Engine",
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
            padx=8,
            pady=4,
        )
        mac_badge.pack(side="right", padx=(10, 0))

        # Live Camera Status Pill in Header
        self.header_status_frame = tk.Frame(right_box, bg=COLOR_BG_CARD_INNER, padx=10, pady=4)
        self.header_status_frame.pack(side="right")

        self.status_dot_canvas = tk.Canvas(
            self.header_status_frame, width=10, height=10, bg=COLOR_BG_CARD_INNER, bd=0, highlightthickness=0
        )
        self.status_dot_canvas.pack(side="left", padx=(0, 6))
        self._dot_id = self.status_dot_canvas.create_oval(1, 1, 9, 9, fill=COLOR_STATUS_MAP[STATUS_STOPPED], outline="")

        self.header_status_label = tk.Label(
            self.header_status_frame,
            text=f"Camera: {STATUS_STOPPED}",
            font=FONT_BADGE,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_STATUS_MAP[STATUS_STOPPED],
        )
        self.header_status_label.pack(side="left")

    # -----------------------------------------------------------------------
    # Main Container (Camera Preview + Control Sidebar)
    # -----------------------------------------------------------------------
    def _build_main_container(self) -> None:
        """Create two-column layout with left camera preview and right sidebar."""
        self.main_container = tk.Frame(self.root, bg=COLOR_BG_ROOT)
        self.main_container.pack(side="top", fill="both", expand=True, padx=16, pady=14)

        # Configure responsive grid weights
        self.main_container.columnconfigure(0, weight=1)  # Camera Preview expands
        self.main_container.columnconfigure(1, weight=0)  # Sidebar fixed
        self.main_container.rowconfigure(0, weight=1)

        # Build Camera Preview Column
        self._build_camera_preview_panel(self.main_container)

        # Build Sidebar Control Column
        self._build_sidebar_panel(self.main_container)

    # -----------------------------------------------------------------------
    # Left Column: Camera Preview Panel
    # -----------------------------------------------------------------------
    def _build_camera_preview_panel(self, parent: tk.Widget) -> None:
        """Build the left camera preview frame and drawing canvas."""
        preview_container = tk.Frame(parent, bg=COLOR_BG_SURFACE, bd=1, relief="solid")
        # Give border color via container background trick
        preview_container.configure(highlightbackground=COLOR_BORDER, highlightthickness=1)
        preview_container.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        # Top bar of preview box
        preview_header = tk.Frame(preview_container, bg=COLOR_BG_CARD_INNER, height=36)
        preview_header.pack(side="top", fill="x")
        preview_header.pack_propagate(False)

        lbl_cam_title = tk.Label(
            preview_header,
            text="LIVE CAMERA FEED",
            font=FONT_CARD_TITLE,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_ACCENT_CYAN,
        )
        lbl_cam_title.pack(side="left", padx=12, pady=8)

        self.preview_res_lbl = tk.Label(
            preview_header,
            text="Offline • Standby",
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
        )
        self.preview_res_lbl.pack(side="right", padx=12)

        # Canvas for video rendering
        self.preview_canvas = tk.Canvas(
            preview_container,
            bg=COLOR_BG_PREVIEW,
            bd=0,
            highlightthickness=0,
            cursor="crosshair",
        )
        self.preview_canvas.pack(side="top", fill="both", expand=True)
        self.preview_canvas.bind("<Configure>", self._on_canvas_resize)

    # -----------------------------------------------------------------------
    # Right Column: Sidebar Control Panel
    # -----------------------------------------------------------------------
    def _build_sidebar_panel(self, parent: tk.Widget) -> None:
        """Build the structured sidebar with control cards and statistics."""
        sidebar_frame = tk.Frame(
            parent,
            bg=COLOR_BG_SURFACE,
            width=SIDEBAR_WIDTH,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
        )
        sidebar_frame.grid(row=0, column=1, sticky="nsew")
        sidebar_frame.grid_propagate(False)

        # Pack internal cards with clean spacing
        self._build_camera_control_card(sidebar_frame)
        self._build_gesture_status_card(sidebar_frame)
        self._build_stats_card(sidebar_frame)
        self._build_system_controls_card(sidebar_frame)
        self._build_guide_card(sidebar_frame)

    # Card 1: Camera Controls
    def _build_camera_control_card(self, parent: tk.Widget) -> None:
        card = self._create_card_container(parent, "CAMERA CONTROL")

        # Status text row inside card
        status_row = tk.Frame(card, bg=COLOR_BG_CARD_INNER)
        status_row.pack(side="top", fill="x", padx=10, pady=(6, 10))

        tk.Label(
            status_row,
            text="Device Status:",
            font=FONT_BODY,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
        ).pack(side="left")

        self.card_status_lbl = tk.Label(
            status_row,
            text=STATUS_STOPPED,
            font=FONT_BODY_BOLD,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_STATUS_MAP[STATUS_STOPPED],
        )
        self.card_status_lbl.pack(side="right")

        # Action Buttons Row
        btn_row = tk.Frame(card, bg=COLOR_BG_CARD_INNER)
        btn_row.pack(side="top", fill="x", padx=10, pady=(0, 10))

        self.btn_start = ModernButton(
            btn_row,
            text="▶ Start Camera",
            bg_color=COLOR_BTN_START_BG,
            hover_color=COLOR_BTN_START_HOVER,
            command=self._start_camera,
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.btn_stop = ModernButton(
            btn_row,
            text="⏹ Stop Camera",
            bg_color=COLOR_BTN_STOP_BG,
            hover_color=COLOR_BTN_STOP_HOVER,
            command=self._stop_camera,
        )
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=(5, 0))
        self.btn_stop.set_enabled(False)  # Disabled initially

        # Device index info
        dev_info_row = tk.Frame(card, bg=COLOR_BG_CARD_INNER)
        dev_info_row.pack(side="top", fill="x", padx=10, pady=(0, 8))

        tk.Label(
            dev_info_row,
            text="Input Source:",
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
        ).pack(side="left")

        tk.Label(
            dev_info_row,
            text=f"Default Webcam (Index {DEFAULT_CAMERA_INDEX})",
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_ACCENT,
        ).pack(side="right")

    # Card 2: Hand Tracking & Gesture Status
    def _build_gesture_status_card(self, parent: tk.Widget) -> None:
        card = self._create_card_container(parent, "HAND TRACKING & GESTURES", badge_text="Phase 3 Live")

        # Main Hand Detection Status Box
        status_box = tk.Frame(card, bg=COLOR_BG_ROOT, highlightbackground=COLOR_BORDER, highlightthickness=1)
        status_box.pack(side="top", fill="x", padx=10, pady=(6, 6))

        self.hand_status_lbl = tk.Label(
            status_box,
            text=STATUS_NO_HAND,
            font=(FONT_FAMILY, 10, "bold"),
            bg=COLOR_BG_ROOT,
            fg=COLOR_TEXT_SECONDARY,
            pady=8,
        )
        self.hand_status_lbl.pack(side="top")

        # Tracking state row
        state_row = tk.Frame(card, bg=COLOR_BG_CARD_INNER)
        state_row.pack(side="top", fill="x", padx=10, pady=(0, 4))

        tk.Label(
            state_row,
            text="Tracking Status:",
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
        ).pack(side="left")

        self.tracking_state_lbl = tk.Label(
            state_row,
            text=STATUS_TRACKING_OFFLINE,
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_MUTED,
        )
        self.tracking_state_lbl.pack(side="right")

        # Gesture status row (Active gesture classification)
        gesture_row = tk.Frame(card, bg=COLOR_BG_CARD_INNER)
        gesture_row.pack(side="top", fill="x", padx=10, pady=(0, 6))

        tk.Label(
            gesture_row,
            text="Active Gesture:",
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
        ).pack(side="left")

        self.gesture_status_lbl = tk.Label(
            gesture_row,
            text=GESTURE_PLACEHOLDER_TEXT,
            font=(FONT_FAMILY, 9, "italic"),
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_MUTED,
        )
        self.gesture_status_lbl.pack(side="right")

        # Informative college project demo disclaimer
        info_lbl = tk.Label(
            card,
            text="ℹ Phase 3: 9 gestures classified in real time (Palm, Fist, Thumbs Up, Peace, 1-5 Fingers) with temporal smoothing.",
            font=(FONT_FAMILY, 8),
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_MUTED,
            wraplength=SIDEBAR_WIDTH - 44,
            justify="left",
        )
        info_lbl.pack(side="top", anchor="w", padx=10, pady=(0, 8))

    # Card 3: Small Statistics Cards
    def _build_stats_card(self, parent: tk.Widget) -> None:
        card = self._create_card_container(parent, "METRICS & STATISTICS")

        # Grid of 4 compact metric boxes (2 rows x 2 columns)
        grid_frame = tk.Frame(card, bg=COLOR_BG_CARD_INNER)
        grid_frame.pack(side="top", fill="x", padx=10, pady=(4, 10))
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        # 1. Detected Hands (Real-Time Live Count)
        self.stat_hands_val = self._create_stat_tile(
            grid_frame,
            row=0,
            col=0,
            label="Detected Hands\n(Live)",
            val_text=str(INITIAL_HANDS_COUNT),
            color=COLOR_TEXT_SECONDARY,
        )

        # 2. Recognized Gestures (Phase 3/8 Session Metric)
        self.stat_gestures_val = self._create_stat_tile(
            grid_frame,
            row=0,
            col=1,
            label="Gesture Events\n(Session)",
            val_text=str(INITIAL_GESTURES_COUNT),
            color=COLOR_TEXT_SECONDARY,
        )

        # 3. Live FPS
        self.stat_fps_val = self._create_stat_tile(
            grid_frame,
            row=1,
            col=0,
            label="Camera FPS",
            val_text="0.0",
            color=COLOR_ACCENT_CYAN,
        )

        # 4. Captured Frames
        self.stat_frames_val = self._create_stat_tile(
            grid_frame,
            row=1,
            col=1,
            label="Frames Processed",
            val_text="0",
            color=COLOR_TEXT_PRIMARY,
        )

        # Phase 6: Session Analytics & History Button
        self.btn_card_analytics = ModernButton(
            card,
            text="📊 View Analytics & History",
            bg_color="#1E293B",
            hover_color="#334155",
            fg_color=COLOR_ACCENT_CYAN,
            font=(FONT_FAMILY, 9, "bold"),
            command=self.open_analytics_dialog,
        )
        self.btn_card_analytics.pack(side="top", fill="x", padx=10, pady=(0, 8))

    # Card 4: System Controls (Phase 4)
    def _build_system_controls_card(self, parent: tk.Widget) -> None:
        card = self._create_card_container(parent, "SYSTEM CONTROLS", badge_text="Phase 4")

        # Row 1: Enable Controls & Enable Mouse Buttons
        btn_row = tk.Frame(card, bg=COLOR_BG_CARD_INNER)
        btn_row.pack(side="top", fill="x", padx=10, pady=(4, 5))

        self.btn_toggle_controls = ModernButton(
            btn_row,
            text="Enable Controls",
            bg_color="#1E293B",
            hover_color="#334155",
            fg_color=COLOR_TEXT_SECONDARY,
            command=self._toggle_controls,
        )
        self.btn_toggle_controls.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_toggle_mouse = ModernButton(
            btn_row,
            text="Enable Mouse",
            bg_color="#1E293B",
            hover_color="#334155",
            fg_color=COLOR_TEXT_SECONDARY,
            command=self._toggle_mouse,
        )
        self.btn_toggle_mouse.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # Row 2: Status feedback text
        status_box = tk.Frame(card, bg=COLOR_BG_ROOT, highlightbackground=COLOR_BORDER, highlightthickness=1)
        status_box.pack(side="top", fill="x", padx=10, pady=(2, 4))

        self.control_status_lbl = tk.Label(
            status_box,
            text="Controls: Disabled (Safe Mode)",
            font=FONT_SMALL,
            bg=COLOR_BG_ROOT,
            fg=COLOR_TEXT_MUTED,
            pady=3,
        )
        self.control_status_lbl.pack(side="top")

        # Row 3: Last action triggered feedback
        action_row = tk.Frame(card, bg=COLOR_BG_CARD_INNER)
        action_row.pack(side="top", fill="x", padx=10, pady=(1, 5))

        tk.Label(
            action_row,
            text="Last Action:",
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_SECONDARY,
        ).pack(side="left")

        self.last_action_lbl = tk.Label(
            action_row,
            text="None",
            font=FONT_SMALL,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_MUTED,
        )
        self.last_action_lbl.pack(side="right")

        # Row 4: Emergency Stop Button
        self.btn_emergency_stop = ModernButton(
            card,
            text="🛑 Emergency Stop Actions",
            bg_color="#7F1D1D",
            hover_color="#991B1B",
            fg_color="#FCA5A5",
            command=self._emergency_stop_actions,
        )
        self.btn_emergency_stop.pack(side="top", fill="x", padx=10, pady=(1, 4))

        # Row 5: Configure Settings & Custom Mappings Button (Phase 5)
        self.btn_card_settings = ModernButton(
            card,
            text="⚙ Configure Mappings & Sensitivity",
            bg_color=COLOR_BG_ROOT,
            hover_color="#1E2E4E",
            fg_color=COLOR_ACCENT_CYAN,
            font=(FONT_FAMILY, 9),
            padx=8,
            pady=4,
            command=self.open_settings_dialog,
        )
        self.btn_card_settings.pack(side="top", fill="x", padx=10, pady=(1, 6))

    def _toggle_controls(self) -> None:
        """Toggle system control state."""
        new_state = not self.control_manager.controls_enabled
        self.control_manager.enable_controls(new_state)
        if new_state:
            self.btn_toggle_controls.set_colors(bg_color="#065F46", hover_color="#047857", fg_color="#6EE7B7")
            self.btn_toggle_controls.configure(text="Controls: ACTIVE")
            self.control_status_lbl.configure(text="System Controls: Active", fg="#10B981")
        else:
            self.btn_toggle_controls.set_colors(bg_color="#1E293B", hover_color="#334155", fg_color=COLOR_TEXT_SECONDARY)
            self.btn_toggle_controls.configure(text="Enable Controls")
            self.control_status_lbl.configure(text="Controls: Disabled (Safe Mode)", fg=COLOR_TEXT_MUTED)

    def _toggle_mouse(self) -> None:
        """Toggle virtual mouse state."""
        new_state = not self.control_manager.mouse_enabled
        self.control_manager.enable_mouse(new_state)
        if new_state:
            self.btn_toggle_mouse.set_colors(bg_color="#0369A1", hover_color="#0284C7", fg_color="#7DD3FC")
            self.btn_toggle_mouse.configure(text="Mouse: ACTIVE")
            self.control_status_lbl.configure(text=self.control_manager.status_feedback, fg=COLOR_ACCENT_CYAN)
        else:
            self.btn_toggle_mouse.set_colors(bg_color="#1E293B", hover_color="#334155", fg_color=COLOR_TEXT_SECONDARY)
            self.btn_toggle_mouse.configure(text="Enable Mouse")
            self.control_status_lbl.configure(text=self.control_manager.status_feedback, fg=COLOR_TEXT_MUTED)

    def _emergency_stop_actions(self) -> None:
        """Emergency disable all gesture actions."""
        self.control_manager.emergency_stop()
        self.btn_toggle_controls.set_colors(bg_color="#1E293B", hover_color="#334155", fg_color=COLOR_TEXT_SECONDARY)
        self.btn_toggle_controls.configure(text="Enable Controls")
        self.btn_toggle_mouse.set_colors(bg_color="#1E293B", hover_color="#334155", fg_color=COLOR_TEXT_SECONDARY)
        self.btn_toggle_mouse.configure(text="Enable Mouse")
        self.control_status_lbl.configure(text="🛑 Emergency Stopped", fg="#EF4444")
        self.last_action_lbl.configure(text="Stopped", fg=COLOR_TEXT_MUTED)

    # Card 5: Demo Instructions & Tips
    def _build_guide_card(self, parent: tk.Widget) -> None:
        card = self._create_card_container(parent, "DEMO INSTRUCTIONS")

        instructions = [
            "1. Press 'Start Camera' to open default webcam.",
            "2. Controls default to DISABLED for safety. Click to enable.",
            "3. Thumbs Up = Play/Pause | Peace = Continuous Volume.",
            "4. 3 Fingers = Next Track | 4 Fingers = Previous Track.",
            "5. Press Escape or 'Emergency Stop' to halt actions instantly.",
            "6. Click '⚙ Settings' to customize gesture mappings & sensitivity.",
        ]

        for text in instructions:
            bullet_lbl = tk.Label(
                card,
                text=text,
                font=FONT_SMALL,
                bg=COLOR_BG_CARD_INNER,
                fg=COLOR_TEXT_SECONDARY,
                anchor="w",
                justify="left",
            )
            bullet_lbl.pack(side="top", fill="x", padx=10, pady=1)

    # Helper: Generic Card Box
    def _create_card_container(
        self, parent: tk.Widget, title: str, badge_text: Optional[str] = None
    ) -> tk.Frame:
        """Create a stylized card container with header and rounded aesthetics."""
        card_outer = tk.Frame(
            parent,
            bg=COLOR_BG_CARD_INNER,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
        )
        card_outer.pack(side="top", fill="x", padx=10, pady=6)

        card_header = tk.Frame(card_outer, bg=COLOR_BG_CARD_INNER)
        card_header.pack(side="top", fill="x", padx=10, pady=(8, 4))

        tk.Label(
            card_header,
            text=title,
            font=FONT_CARD_TITLE,
            bg=COLOR_BG_CARD_INNER,
            fg=COLOR_TEXT_PRIMARY,
        ).pack(side="left")

        if badge_text:
            badge = tk.Label(
                card_header,
                text=badge_text,
                font=FONT_BADGE,
                bg=COLOR_BG_ROOT,
                fg=COLOR_ACCENT_CYAN,
                padx=6,
                pady=1,
            )
            badge.pack(side="right")

        divider = tk.Frame(card_outer, bg=COLOR_BORDER, height=1)
        divider.pack(side="top", fill="x", padx=8, pady=(2, 6))

        return card_outer

    # Helper: Generic Statistic Tile
    def _create_stat_tile(
        self, parent: tk.Widget, row: int, col: int, label: str, val_text: str, color: str
    ) -> tk.Label:
        tile = tk.Frame(parent, bg=COLOR_BG_ROOT, highlightbackground=COLOR_BORDER, highlightthickness=1)
        tile.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)

        val_lbl = tk.Label(
            tile,
            text=val_text,
            font=FONT_STAT_VALUE,
            bg=COLOR_BG_ROOT,
            fg=color,
        )
        val_lbl.pack(side="top", pady=(6, 0))

        tk.Label(
            tile,
            text=label,
            font=FONT_STAT_LABEL,
            bg=COLOR_BG_ROOT,
            fg=COLOR_TEXT_SECONDARY,
            justify="center",
        ).pack(side="top", pady=(2, 6))

        return val_lbl

    # -----------------------------------------------------------------------
    # Bottom Status Bar
    # -----------------------------------------------------------------------
    def _build_status_bar(self) -> None:
        """Create the bottom application status bar."""
        self.status_bar = tk.Frame(self.root, bg=COLOR_BG_HEADER, height=28)
        self.status_bar.pack(side="bottom", fill="x")
        self.status_bar.pack_propagate(False)

        top_line = tk.Frame(self.status_bar, bg=COLOR_BORDER, height=1)
        top_line.pack(side="top", fill="x")

        self.status_bar_msg = tk.Label(
            self.status_bar,
            text="Ready. Press 'Start Camera' to initiate video capture.",
            font=FONT_SMALL,
            bg=COLOR_BG_HEADER,
            fg=COLOR_TEXT_SECONDARY,
        )
        self.status_bar_msg.pack(side="left", padx=16, pady=4)

        sys_hint = tk.Label(
            self.status_bar,
            text="MacBook Webcam • Python 3.14 • OpenCV Core",
            font=FONT_SMALL,
            bg=COLOR_BG_HEADER,
            fg=COLOR_TEXT_MUTED,
        )
        sys_hint.pack(side="right", padx=16, pady=4)

    # -----------------------------------------------------------------------
    # Camera Control Actions
    # -----------------------------------------------------------------------
    def _start_camera(self) -> None:
        """Handle Start Camera button click."""
        if self.camera_service.is_running():
            return

        self._set_ui_status(STATUS_STARTING, "Starting camera stream...")
        self.btn_start.set_enabled(False)
        self.btn_stop.set_enabled(True)

        success = self.camera_service.start(camera_index=DEFAULT_CAMERA_INDEX)
        if not success:
            logger.warning("Camera service refused start request (already running).")
        else:
            if self.camera_service.hand_detector is not None:
                self.settings_manager.apply_to_components(
                    self.settings_manager.current_settings,
                    gesture_recognizer=self.camera_service.hand_detector.gesture_recognizer,
                    control_manager=self.control_manager,
                )

    def _stop_camera(self) -> None:
        """Handle Stop Camera button click."""
        self.btn_start.set_enabled(True)
        self.btn_stop.set_enabled(False)
        self.camera_service.stop()
        self.control_manager.reset_continuous_states()
        self._last_processed_frame_count = -1
        self._set_ui_status(STATUS_STOPPED, "Camera stopped by user.")
        self._draw_offline_preview()
        self.preview_res_lbl.configure(text="Offline • Standby")
        self.stat_fps_val.configure(text="0.0")
        self.stat_hands_val.configure(text="0", fg=COLOR_TEXT_SECONDARY)
        self.stat_gestures_val.configure(
            text=str(self.statistics_manager.total_gestures_count), fg=COLOR_TEXT_SECONDARY
        )
        self.hand_status_lbl.configure(text=STATUS_NO_HAND, fg=COLOR_TEXT_SECONDARY)
        self.tracking_state_lbl.configure(text=STATUS_TRACKING_OFFLINE, fg=COLOR_TEXT_MUTED)
        self.gesture_status_lbl.configure(text=GESTURE_NONE, fg=COLOR_TEXT_MUTED, font=(FONT_FAMILY, 9, "italic"))
        if not self.control_manager.controls_enabled:
            self.control_status_lbl.configure(text="Controls: Disabled (Safe Mode)", fg=COLOR_TEXT_MUTED)

    def _toggle_camera(self) -> None:
        """Toggle camera state via keyboard shortcut (Space)."""
        if self.camera_service.is_running():
            self._stop_camera()
        else:
            self._start_camera()

    # -----------------------------------------------------------------------
    # Status and State Synchronization
    # -----------------------------------------------------------------------
    def _on_camera_status_update(self, status: str, message: str) -> None:
        """Callback invoked by camera service thread."""
        # Use root.after to safely marshal callback to Tkinter GUI thread
        if not self._is_closing and self.root.winfo_exists():
            self.root.after(0, lambda: self._set_ui_status(status, message))

    def _set_ui_status(self, status: str, message: str) -> None:
        """Update status pills, badges, buttons, and status bar text on UI thread."""
        self._last_status = status
        color = COLOR_STATUS_MAP.get(status, COLOR_TEXT_SECONDARY)

        # Update header badge
        self.header_status_label.configure(text=f"Camera: {status}", fg=color)
        self.status_dot_canvas.itemconfig(self._dot_id, fill=color)

        # Update card status
        self.card_status_lbl.configure(text=status, fg=color)

        # Update buttons
        if status == STATUS_RUNNING:
            self.btn_start.set_enabled(False)
            self.btn_stop.set_enabled(True)
        elif status == STATUS_STARTING:
            self.btn_start.set_enabled(False)
            self.btn_stop.set_enabled(True)
        elif status in (STATUS_STOPPED, STATUS_ERROR):
            self.btn_start.set_enabled(True)
            self.btn_stop.set_enabled(False)

        # Update bottom status bar message
        if status == STATUS_ERROR:
            err_msg = self.camera_service.error_message or message
            self.status_bar_msg.configure(
                text=f"⚠️ Camera Error: {err_msg}",
                fg=COLOR_STATUS_MAP[STATUS_ERROR],
            )
            self._draw_error_preview(err_msg)
        else:
            self.status_bar_msg.configure(text=message, fg=COLOR_TEXT_SECONDARY)

    # -----------------------------------------------------------------------
    # Frame Polling & Video Rendering
    # -----------------------------------------------------------------------
    def _schedule_poll(self) -> None:
        """Schedule the next frame check in Tkinter event loop."""
        if not self._is_closing:
            self._poll_job = self.root.after(FRAME_POLL_INTERVAL_MS, self._update_frame_loop)

    def _update_frame_loop(self) -> None:
        """Periodic loop that pulls newest frame from camera service and renders."""
        try:
            # Safely drain status queue on Tkinter main thread
            while not self.camera_service.status_queue.empty():
                try:
                    q_status, q_msg = self.camera_service.status_queue.get_nowait()
                    self._set_ui_status(q_status, q_msg)
                except Exception:
                    break

            if self.camera_service.is_running():
                has_frame, frame_bgr, fps, frame_count = self.camera_service.get_latest_frame()
                hands_count, hand_status, tracking_status, handedness, current_gesture, active_g_count = (
                    self.camera_service.get_tracking_data()
                )

                if has_frame and frame_bgr is not None:
                    # Skip duplicate rendering and duplicate action evaluations on identical frames
                    if frame_count == self._last_processed_frame_count and self._last_processed_frame_count != -1:
                        return
                    self._last_processed_frame_count = frame_count

                    self._render_frame(frame_bgr)
                    self.stat_fps_val.configure(text=f"{fps:.1f}")
                    self.stat_frames_val.configure(text=str(frame_count))

                    # Update hand tracking metrics in real-time
                    self.stat_hands_val.configure(
                        text=str(hands_count),
                        fg=COLOR_ACCENT_CYAN if hands_count > 0 else COLOR_TEXT_SECONDARY,
                    )
                    self.stat_gestures_val.configure(
                        text=str(self.statistics_manager.total_gestures_count),
                        fg=COLOR_ACCENT_CYAN if self.statistics_manager.total_gestures_count > 0 else COLOR_TEXT_SECONDARY,
                    )

                    if hands_count > 0:
                        # Phase 6: Record stabilized gesture transition event
                        self.statistics_manager.record_gesture(current_gesture)

                        detail = f"Hand Detected ({hands_count})"
                        if handedness:
                            detail += f" • {', '.join(handedness)}"
                        self.hand_status_lbl.configure(text=detail, fg=COLOR_STATUS_MAP[STATUS_RUNNING])
                        self.tracking_state_lbl.configure(text=tracking_status, fg=COLOR_STATUS_MAP[STATUS_RUNNING])

                        # Gesture label display
                        if current_gesture in SUPPORTED_GESTURES:
                            self.gesture_status_lbl.configure(
                                text=current_gesture,
                                fg=COLOR_ACCENT_CYAN,
                                font=(FONT_FAMILY, 10, "bold"),
                            )
                        elif current_gesture == GESTURE_UNKNOWN:
                            self.gesture_status_lbl.configure(
                                text=GESTURE_UNKNOWN,
                                fg=COLOR_STATUS_MAP[STATUS_STARTING],
                                font=(FONT_FAMILY, 9, "italic"),
                            )
                        else:
                            self.gesture_status_lbl.configure(
                                text=current_gesture,
                                fg=COLOR_TEXT_MUTED,
                                font=(FONT_FAMILY, 9, "italic"),
                            )
                        # Phase 4: Process Gesture-Based System Controls
                        lms_list = self.camera_service.get_latest_landmarks()
                        primary_lms = (
                            lms_list[0] if (lms_list and len(lms_list) > 0 and len(lms_list[0]) >= 21) else None
                        )
                        action_res = self.control_manager.process_frame(
                            is_camera_running=True,
                            detected_hands_count=hands_count,
                            current_gesture=current_gesture,
                            landmarks=primary_lms,
                        )
                        if action_res is not None:
                            if action_res.success:
                                self.last_action_lbl.configure(text=action_res.action_type, fg=COLOR_ACCENT_CYAN)
                            else:
                                self.last_action_lbl.configure(
                                    text=action_res.action_type, fg=COLOR_STATUS_MAP[STATUS_STARTING]
                                )
                    else:
                        # Reset continuous control states immediately when hand is absent
                        self.control_manager.reset_continuous_states()

                        # Only confirm tracking loss and reset gesture state after grace period expires
                        if self.camera_service.tracking_confirmed_lost:
                            self.statistics_manager.record_gesture(GESTURE_NONE)
                            self.hand_status_lbl.configure(text=STATUS_NO_HAND, fg=COLOR_TEXT_SECONDARY)
                            self.tracking_state_lbl.configure(
                                text=STATUS_TRACKING_SCANNING, fg=COLOR_STATUS_MAP[STATUS_STARTING]
                            )
                            self.gesture_status_lbl.configure(
                                text=GESTURE_NONE,
                                fg=COLOR_TEXT_MUTED,
                                font=(FONT_FAMILY, 9, "italic"),
                            )
                        else:
                            # Grace period (temporary frame drop) - maintain scanning indication
                            self.hand_status_lbl.configure(text=STATUS_NO_HAND, fg=COLOR_TEXT_SECONDARY)
                            self.tracking_state_lbl.configure(
                                text=STATUS_TRACKING_SCANNING, fg=COLOR_STATUS_MAP[STATUS_STARTING]
                            )

                    # Update system control status indicator
                    if self.control_manager.controls_enabled:
                        fb = self.control_manager.status_feedback
                        if "Blocked" in fb or "Failed" in fb:
                            self.control_status_lbl.configure(text=fb, fg=COLOR_STATUS_MAP[STATUS_STARTING])
                        elif "Emergency" in fb:
                            self.control_status_lbl.configure(text=fb, fg="#EF4444")
                        else:
                            self.control_status_lbl.configure(text=fb, fg="#10B981")
                    else:
                        self.control_status_lbl.configure(
                            text=self.control_manager.status_feedback, fg=COLOR_TEXT_MUTED
                        )

                    # Update resolution pill
                    w, h = self.camera_service.resolution
                    self.preview_res_lbl.configure(text=f"{w}x{h} • Live")

            elif self._last_status == STATUS_ERROR:
                # Keep error screen active
                pass

        except Exception as exc:
            logger.error("Error in UI frame update loop: %s", exc)

        finally:
            self._schedule_poll()

    def _render_frame(self, frame_bgr: np.ndarray) -> None:
        """Scale and display an OpenCV BGR frame on the Tkinter canvas."""
        canvas_w = self.preview_canvas.winfo_width()
        canvas_h = self.preview_canvas.winfo_height()

        if canvas_w < 50 or canvas_h < 50:
            return  # Canvas not fully laid out yet

        frame_h, frame_w = frame_bgr.shape[:2]

        # Calculate aspect-ratio preserving dimensions (fit inside canvas)
        scale = min(canvas_w / frame_w, canvas_h / frame_h)
        target_w = max(1, int(frame_w * scale))
        target_h = max(1, int(frame_h * scale))

        # Resize with OpenCV (fast bilinear interpolation)
        resized_bgr = cv2.resize(frame_bgr, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

        # Convert OpenCV BGR to RGB for Pillow
        rgb_frame = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2RGB)

        # Convert to PIL Image and ImageTk.PhotoImage
        image = Image.fromarray(rgb_frame)
        self._photo_image = ImageTk.PhotoImage(image=image)

        # Draw centered on canvas
        center_x = canvas_w // 2
        center_y = canvas_h // 2

        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(center_x, center_y, image=self._photo_image, anchor="center")

        # Subtle live indicator watermark overlay
        self.preview_canvas.create_text(
            18,
            18,
            text="● LIVE FEED",
            anchor="nw",
            font=FONT_PREVIEW_OVERLAY,
            fill=COLOR_ACCENT_CYAN,
        )

    def _on_canvas_resize(self, event) -> None:
        """Redraw placeholder screen if camera is stopped when window resizes."""
        if not self.camera_service.is_running() and self._last_status != STATUS_ERROR:
            self._draw_offline_preview()

    # -----------------------------------------------------------------------
    # Canvas Graphic Screens (Offline & Error)
    # -----------------------------------------------------------------------
    def _draw_offline_preview(self) -> None:
        """Render modern dark offline placeholder graphics on canvas."""
        self.preview_canvas.delete("all")
        w = max(self.preview_canvas.winfo_width(), PREVIEW_DEFAULT_WIDTH)
        h = max(self.preview_canvas.winfo_height(), PREVIEW_DEFAULT_HEIGHT)

        cx, cy = w // 2, h // 2

        # Draw subtle cyber grid lines
        grid_color = "#0B1528"
        for gx in range(0, w, 40):
            self.preview_canvas.create_line(gx, 0, gx, h, fill=grid_color)
        for gy in range(0, h, 40):
            self.preview_canvas.create_line(0, gy, w, gy, fill=grid_color)

        # Draw camera viewfinder crosshairs
        ch_color = "#1E2E4E"
        ch_len = 24
        # Center target
        self.preview_canvas.create_oval(cx - 50, cy - 50, cx + 50, cy + 50, outline=ch_color, width=1)
        self.preview_canvas.create_line(cx - 60, cy, cx - 40, cy, fill=ch_color, width=1)
        self.preview_canvas.create_line(cx + 40, cy, cx + 60, cy, fill=ch_color, width=1)
        self.preview_canvas.create_line(cx, cy - 60, cx, cy - 40, fill=ch_color, width=1)
        self.preview_canvas.create_line(cx, cy + 40, cx, cy + 60, fill=ch_color, width=1)

        # Camera Glyph Box
        self.preview_canvas.create_rectangle(
            cx - 24, cy - 70, cx + 24, cy - 30, outline=COLOR_ACCENT_CYAN, width=2
        )
        self.preview_canvas.create_oval(
            cx - 12, cy - 62, cx + 12, cy - 38, outline=COLOR_ACCENT_CYAN, width=2
        )
        self.preview_canvas.create_rectangle(
            cx - 8, cy - 75, cx + 8, cy - 70, fill=COLOR_ACCENT_CYAN, outline=""
        )

        # Main typography
        self.preview_canvas.create_text(
            cx,
            cy + 8,
            text="Camera Stream Offline",
            font=(FONT_FAMILY, 15, "bold"),
            fill=COLOR_TEXT_PRIMARY,
        )
        self.preview_canvas.create_text(
            cx,
            cy + 36,
            text="Click '▶ Start Camera' in the sidebar or press [Space] to begin video feed",
            font=FONT_BODY,
            fill=COLOR_TEXT_SECONDARY,
        )

        # Device hint pill
        self.preview_canvas.create_text(
            cx,
            cy + 75,
            text="● Default Device Index 0 (MacBook FaceTime HD / Webcam)",
            font=FONT_SMALL,
            fill=COLOR_ACCENT_CYAN,
        )

    def _draw_error_preview(self, error_message: str) -> None:
        """Render informative error diagnostic display on canvas."""
        self.preview_canvas.delete("all")
        w = max(self.preview_canvas.winfo_width(), PREVIEW_DEFAULT_WIDTH)
        h = max(self.preview_canvas.winfo_height(), PREVIEW_DEFAULT_HEIGHT)

        cx, cy = w // 2, h // 2

        # Error Icon (Warning Triangle)
        self.preview_canvas.create_polygon(
            cx, cy - 70, cx - 40, cy - 10, cx + 40, cy - 10,
            outline=COLOR_STATUS_MAP[STATUS_ERROR],
            fill="#2A1215",
            width=2,
        )
        self.preview_canvas.create_text(
            cx, cy - 32, text="!", font=(FONT_FAMILY, 24, "bold"), fill=COLOR_STATUS_MAP[STATUS_ERROR]
        )

        # Error Heading
        self.preview_canvas.create_text(
            cx,
            cy + 16,
            text="Camera Connection Error",
            font=(FONT_FAMILY, 14, "bold"),
            fill=COLOR_STATUS_MAP[STATUS_ERROR],
        )

        # Error message detail
        self.preview_canvas.create_text(
            cx,
            cy + 46,
            text=error_message,
            font=FONT_BODY,
            fill=COLOR_TEXT_PRIMARY,
            width=min(w - 60, 500),
            justify="center",
        )

        # Remediation hint
        self.preview_canvas.create_text(
            cx,
            cy + 85,
            text="Troubleshooting: Open macOS System Settings > Privacy & Security > Camera\nand ensure VS Code / Terminal has Camera access permitted.",
            font=FONT_SMALL,
            fill=COLOR_TEXT_SECONDARY,
            justify="center",
        )

    # -----------------------------------------------------------------------
    # Analytics & Session History Dialog (Phase 6)
    # -----------------------------------------------------------------------
    def open_analytics_dialog(self) -> AnalyticsDialog:
        """Open or focus the modal Session History & Analytics window."""
        if self._analytics_dialog is not None and self._analytics_dialog.winfo_exists():
            self._analytics_dialog.lift()
            self._analytics_dialog.focus_force()
            return self._analytics_dialog

        self._analytics_dialog = AnalyticsDialog(
            parent=self.root,
            statistics_manager=self.statistics_manager,
        )
        return self._analytics_dialog

    # -----------------------------------------------------------------------
    # Settings & Customization Dialog (Phase 5)
    # -----------------------------------------------------------------------
    def open_settings_dialog(self) -> SettingsDialog:
        """Open or focus the modal Settings & Customization window."""
        if self._settings_dialog is not None and self._settings_dialog.winfo_exists():
            self._settings_dialog.lift()
            return self._settings_dialog

        self._settings_dialog = SettingsDialog(
            parent=self.root,
            settings_manager=self.settings_manager,
            control_manager=self.control_manager,
            camera_service=self.camera_service,
            on_settings_applied=self._on_settings_applied,
        )
        return self._settings_dialog

    def _on_settings_applied(self, new_settings: UserSettings) -> None:
        """Callback triggered when settings are saved or reset in the dialog."""
        self.status_bar_msg.configure(
            text="Preferences saved and applied dynamically.", fg=COLOR_ACCENT_CYAN
        )

    # -----------------------------------------------------------------------
    # Application Shutdown
    # -----------------------------------------------------------------------
    def on_close(self) -> None:
        """Gracefully terminate background threads and destroy Tkinter root."""
        if self._is_closing:
            return

        self._is_closing = True
        logger.info("Application closing: stopping camera service...")

        # Close analytics dialog if open
        if self._analytics_dialog is not None and self._analytics_dialog.winfo_exists():
            try:
                self._analytics_dialog.destroy()
            except Exception:
                pass

        # Close settings dialog if open
        if self._settings_dialog is not None and self._settings_dialog.winfo_exists():
            try:
                self._settings_dialog.destroy()
            except Exception:
                pass

        # Persist session statistics cleanly to local SQLite database
        try:
            self.statistics_manager.save_current_session()
        except Exception as exc:
            logger.warning("Error saving session statistics on shutdown: %s", exc)

        # Emergency stop system actions immediately
        self.control_manager.emergency_stop()

        # Cancel pending after callbacks
        if self._poll_job is not None:
            try:
                self.root.after_cancel(self._poll_job)
            except Exception:
                pass

        # Stop camera worker and release detector resources safely
        try:
            self.camera_service.close()
        except Exception as exc:
            logger.warning("Error releasing camera service on window exit: %s", exc)

        # Destroy GUI
        try:
            self.root.destroy()
        except Exception:
            pass
        logger.info("Application terminated cleanly.")


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger('main')
    logger.info("Starting %s from app/ui.py...", APP_TITLE)
    root = tk.Tk()
    camera_service = CameraService()
    app = AppUI(root=root, camera_service=camera_service)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        camera_service.close()
