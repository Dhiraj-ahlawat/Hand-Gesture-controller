"""
tests/test_ui.py
Unit tests for the Tkinter desktop UI components, button states, hand tracking labels, and layout.
"""

import tkinter as tk
from pathlib import Path
import pytest
from app.camera import CameraService
from app.config import (
    ACTION_MUTE,
    ACTION_PLAY_PAUSE,
    APP_TITLE,
    GESTURE_PEACE,
    GESTURE_PLACEHOLDER_TEXT,
    GESTURE_THUMBS_UP,
    INITIAL_GESTURES_COUNT,
    INITIAL_HANDS_COUNT,
    STATUS_ERROR,
    STATUS_NO_HAND,
    STATUS_RUNNING,
    STATUS_STARTING,
    STATUS_STOPPED,
    STATUS_TRACKING_OFFLINE,
)
from app.settings_manager import SettingsManager
from app.statistics_manager import StatisticsManager
from app.ui import AnalyticsDialog, AppUI, SettingsDialog


@pytest.fixture
def tk_root():
    """Create and clean up a Tkinter root window for headless unit tests."""
    root = tk.Tk()
    root.withdraw()  # Do not display window during test runs
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_ui_initial_widget_hierarchy(tk_root):
    """Verify that all Phase 2 dashboard elements are created with correct defaults."""
    camera_service = CameraService(camera_index=0, enable_hand_tracking=False)
    app = AppUI(root=tk_root, camera_service=camera_service)

    # Header and title
    assert APP_TITLE in tk_root.title()
    assert app.header_status_label.cget("text") == f"Camera: {STATUS_STOPPED}"

    # Buttons initial state
    assert str(app.btn_start["state"]) == "normal"
    assert str(app.btn_stop["state"]) == "disabled"

    # Hand detection & tracking status
    assert app.hand_status_lbl.cget("text") == STATUS_NO_HAND
    assert app.tracking_state_lbl.cget("text") == STATUS_TRACKING_OFFLINE

    # Gesture status section (Phase 3 placeholder)
    assert app.gesture_status_lbl.cget("text") == GESTURE_PLACEHOLDER_TEXT

    # Statistics cards
    assert app.stat_hands_val.cget("text") == str(INITIAL_HANDS_COUNT)
    assert app.stat_gestures_val.cget("text") == str(INITIAL_GESTURES_COUNT)
    assert app.stat_fps_val.cget("text") == "0.0"
    assert app.stat_frames_val.cget("text") == "0"

    # Phase 4 System Controls
    assert app.control_manager.controls_enabled is False
    assert app.control_manager.mouse_enabled is False
    assert "Disabled" in app.control_status_lbl.cget("text")
    assert app.last_action_lbl.cget("text") == "None"

    # Test toggling controls and emergency stop
    app._toggle_controls()
    assert app.control_manager.controls_enabled is True
    assert "ACTIVE" in app.btn_toggle_controls.cget("text")

    app._emergency_stop_actions()
    assert app.control_manager.controls_enabled is False
    assert "Emergency Stopped" in app.control_status_lbl.cget("text")

    app.on_close()


def test_ui_status_transitions(tk_root):
    """Verify that _set_ui_status correctly updates badge text, colors, and button states."""
    camera_service = CameraService(camera_index=0, enable_hand_tracking=False)
    app = AppUI(root=tk_root, camera_service=camera_service)

    # Test transition to STARTING
    app._set_ui_status(STATUS_STARTING, "Starting camera...")
    assert app.card_status_lbl.cget("text") == STATUS_STARTING
    assert str(app.btn_start["state"]) == "disabled"
    assert str(app.btn_stop["state"]) == "normal"

    # Test transition to RUNNING
    app._set_ui_status(STATUS_RUNNING, "Camera live.")
    assert app.card_status_lbl.cget("text") == STATUS_RUNNING
    assert str(app.btn_start["state"]) == "disabled"
    assert str(app.btn_stop["state"]) == "normal"

    # Test transition to STOPPED
    app._set_ui_status(STATUS_STOPPED, "Camera stopped.")
    assert app.card_status_lbl.cget("text") == STATUS_STOPPED
    assert str(app.btn_start["state"]) == "normal"
    assert str(app.btn_stop["state"]) == "disabled"

    # Test transition to ERROR
    app._set_ui_status(STATUS_ERROR, "Permission denied")
    assert app.card_status_lbl.cget("text") == STATUS_ERROR
    assert str(app.btn_start["state"]) == "normal"
    assert str(app.btn_stop["state"]) == "disabled"
    assert "Permission denied" in app.status_bar_msg.cget("text")

    app.on_close()


def test_ui_settings_dialog_integration(tk_root, tmp_path: Path):
    """Verify SettingsDialog opens, displays fields, saves preferences, and resets defaults."""
    camera_service = CameraService(camera_index=0, enable_hand_tracking=False)
    app = AppUI(root=tk_root, camera_service=camera_service)

    # Use isolated test settings file
    isolated_path = tmp_path / "ui_settings_test.json"
    app.settings_manager = SettingsManager(filepath=isolated_path)

    # Header and card buttons exist
    assert hasattr(app, "btn_header_settings")
    assert hasattr(app, "btn_card_settings")
    assert "Settings" in app.btn_header_settings.cget("text")
    assert "Mappings" in app.btn_card_settings.cget("text")

    # Open dialog
    dialog = app.open_settings_dialog()
    assert isinstance(dialog, SettingsDialog)
    assert dialog.winfo_exists()

    # Switch tabs
    dialog._switch_tab("sensitivity")
    assert dialog._current_tab == "sensitivity"
    dialog._switch_tab("mappings")
    assert dialog._current_tab == "mappings"

    # Modify mapping and sensitivity
    assert GESTURE_THUMBS_UP in dialog._action_vars
    dialog._action_vars[GESTURE_THUMBS_UP].set(ACTION_MUTE)
    dialog._scale_vars["gesture_history_length"].set(14)
    dialog._scale_vars["action_cooldown_sec"].set(2.0)

    # Save
    dialog._save_settings()
    assert "saved and applied" in dialog.feedback_lbl.cget("text").lower()

    # Verify runtime components updated dynamically
    assert app.control_manager.gesture_action_map[GESTURE_THUMBS_UP] == ACTION_MUTE
    assert app.control_manager.action_cooldown_sec == pytest.approx(2.0)
    assert app.settings_manager.current_settings.gesture_history_length == 14

    # Reset to defaults
    dialog._reset_defaults()
    assert "restored" in dialog.feedback_lbl.cget("text").lower()
    assert app.control_manager.gesture_action_map[GESTURE_THUMBS_UP] == ACTION_PLAY_PAUSE

    # Clean up dialog and app
    dialog.destroy()
    app.on_close()


def test_analytics_dialog(tk_root, tmp_path):
    """Verify that AnalyticsDialog opens, displays statistics, allows switching tabs, and closes."""
    camera_service = CameraService(camera_index=0, enable_hand_tracking=False)
    isolated_db = tmp_path / "ui_history_test.db"
    stats_mgr = StatisticsManager(db_path=isolated_db)
    app = AppUI(root=tk_root, camera_service=camera_service, statistics_manager=stats_mgr)

    # Header and card analytics buttons exist
    assert hasattr(app, "btn_header_analytics")
    assert hasattr(app, "btn_card_analytics")
    assert "Analytics" in app.btn_header_analytics.cget("text")
    assert "Analytics" in app.btn_card_analytics.cget("text")

    # Open dialog
    dialog = app.open_analytics_dialog()
    assert isinstance(dialog, AnalyticsDialog)
    assert dialog.winfo_exists()

    # Verify initial overview state
    assert dialog._active_tab == "overview"
    assert dialog._selected_session_id is None
    assert hasattr(dialog, "lbl_kpi_duration")
    assert hasattr(dialog, "chart_canvas")

    # Switch tabs
    dialog._switch_tab("history")
    assert dialog._active_tab == "history"

    dialog._switch_tab("compare")
    assert dialog._active_tab == "compare"

    dialog._switch_tab("overview")
    assert dialog._active_tab == "overview"

    # Simulate recorded gestures and verify live refresh
    app.statistics_manager.record_gesture(GESTURE_THUMBS_UP)
    dialog._refresh_overview()
    assert dialog.lbl_kpi_total_gestures.cget("text") == "1"
    assert "Thumbs Up" in dialog.lbl_kpi_most_used.cget("text")

    # Return to live session helper
    dialog._return_to_live_session()
    assert dialog._selected_session_id is None

    # Verify chart renders properly on empty dataset without error
    dialog._render_bar_chart(dialog.chart_canvas, {}, 0)
    items_empty = dialog.chart_canvas.find_all()
    assert len(items_empty) > 0

    # Verify chart renders on real populated dataset
    dialog._render_bar_chart(dialog.chart_canvas, {GESTURE_THUMBS_UP: 5, GESTURE_PEACE: 2}, 7)
    items_populated = dialog.chart_canvas.find_all()
    assert len(items_populated) > len(items_empty)

    # Clean up
    dialog.destroy()
    app.on_close()

