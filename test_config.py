"""
tests/test_config.py
Unit tests for application configuration, theme constants, and hand-tracking settings.
"""

import re
import pytest
from app import config


def is_valid_hex_color(color: str) -> bool:
    """Check if string is a valid 7-character hexadecimal color (#RRGGBB)."""
    return bool(re.match(r"^#[0-9a-fA-F]{6}$", color))


def test_application_metadata():
    """Verify application title, version, and subtitle are non-empty strings."""
    assert isinstance(config.APP_TITLE, str)
    assert len(config.APP_TITLE) > 0
    assert "Hand Gesture" in config.APP_TITLE

    assert isinstance(config.APP_VERSION, str)
    assert len(config.APP_VERSION) > 0
    assert ("7.0" in config.APP_VERSION) or ("6.0" in config.APP_VERSION)

    assert isinstance(config.APP_SUBTITLE, str)
    assert len(config.APP_SUBTITLE) > 0
    assert ("Phase 7" in config.APP_SUBTITLE) or ("Phase 6" in config.APP_SUBTITLE)

    assert hasattr(config, "SETTINGS_DIRNAME")
    assert hasattr(config, "SETTINGS_FILENAME")
    assert hasattr(config, "HISTORY_FILENAME")
    assert config.HISTORY_FILENAME == "history.db"


def test_window_dimensions():
    """Ensure window dimensions are positive integers with reasonable min constraints."""
    assert isinstance(config.WINDOW_WIDTH, int) and config.WINDOW_WIDTH > 0
    assert isinstance(config.WINDOW_HEIGHT, int) and config.WINDOW_HEIGHT > 0
    assert isinstance(config.MIN_WINDOW_WIDTH, int) and config.MIN_WINDOW_WIDTH > 0
    assert isinstance(config.MIN_WINDOW_HEIGHT, int) and config.MIN_WINDOW_HEIGHT > 0

    assert config.WINDOW_WIDTH >= config.MIN_WINDOW_WIDTH
    assert config.WINDOW_HEIGHT >= config.MIN_WINDOW_HEIGHT


def test_camera_configuration_defaults():
    """Validate camera parameters."""
    assert isinstance(config.DEFAULT_CAMERA_INDEX, int)
    assert config.DEFAULT_CAMERA_INDEX >= 0
    assert config.FRAME_WIDTH > 0
    assert config.FRAME_HEIGHT > 0
    assert config.TARGET_FPS > 0
    assert config.FRAME_POLL_INTERVAL_MS > 0


def test_hand_tracking_configuration():
    """Validate Phase 2 hand-tracking parameters and thresholds."""
    assert config.MAX_HANDS == 2
    assert config.MIN_DETECTION_CONFIDENCE == 0.6
    assert config.MIN_TRACKING_CONFIDENCE == 0.6
    assert config.MODEL_FILENAME == "hand_landmarker.task"

    # Status constants
    assert config.STATUS_NO_HAND == "Show your hand to the camera"
    assert config.STATUS_HAND_DETECTED == "Hand Detected"
    assert config.STATUS_TRACKING_ACTIVE == "Tracking Active"

    # Landmark BGR colors
    bgr_colors = [
        config.COLOR_BONE_BGR,
        config.COLOR_JOINT_BGR,
        config.COLOR_FINGERTIP_BGR,
        config.COLOR_WRIST_BGR,
    ]
    for c in bgr_colors:
        assert isinstance(c, tuple) and len(c) == 3
        for val in c:
            assert 0 <= val <= 255


def test_camera_statuses():
    """Verify status constants and completeness of status mapping."""
    expected_statuses = {"Stopped", "Starting", "Running", "Error"}
    actual_statuses = {
        config.STATUS_STOPPED,
        config.STATUS_STARTING,
        config.STATUS_RUNNING,
        config.STATUS_ERROR,
    }
    assert actual_statuses == expected_statuses

    for status in expected_statuses:
        assert status in config.COLOR_STATUS_MAP
        assert is_valid_hex_color(config.COLOR_STATUS_MAP[status])


def test_phase3_gesture_configuration():
    """Verify Phase 3 gesture recognition configuration, thresholds, and defaults."""
    assert len(config.SUPPORTED_GESTURES) == 9
    assert config.GESTURE_OPEN_PALM in config.SUPPORTED_GESTURES
    assert config.GESTURE_FIST in config.SUPPORTED_GESTURES
    assert config.GESTURE_THUMBS_UP in config.SUPPORTED_GESTURES
    assert config.GESTURE_PEACE in config.SUPPORTED_GESTURES
    assert config.GESTURE_ONE_FINGER in config.SUPPORTED_GESTURES
    assert config.GESTURE_TWO_FINGERS in config.SUPPORTED_GESTURES
    assert config.GESTURE_THREE_FINGERS in config.SUPPORTED_GESTURES
    assert config.GESTURE_FOUR_FINGERS in config.SUPPORTED_GESTURES
    assert config.GESTURE_FIVE_FINGERS in config.SUPPORTED_GESTURES

    assert config.GESTURE_HISTORY_LENGTH > 0
    assert config.GESTURE_MIN_CONSISTENT > 0
    assert config.GESTURE_MIN_CONSISTENT <= config.GESTURE_HISTORY_LENGTH
    assert config.GESTURE_COOLDOWN_SEC >= 0.0
    assert config.PEACE_SPREAD_RATIO > 0.0
    assert config.OPEN_PALM_SPREAD_RATIO > 0.0
    assert config.INITIAL_HANDS_COUNT == 0
    assert config.INITIAL_GESTURES_COUNT == 0
    assert config.GESTURE_PLACEHOLDER_TEXT == "Waiting for hand..."


def test_theme_colors():
    """Verify all theme colors are valid hexadecimal color strings."""
    colors = [
        config.COLOR_BG_ROOT,
        config.COLOR_BG_SURFACE,
        config.COLOR_BG_CARD_INNER,
        config.COLOR_BG_HEADER,
        config.COLOR_BG_PREVIEW,
        config.COLOR_BORDER,
        config.COLOR_BORDER_ACCENT,
        config.COLOR_ACCENT_CYAN,
        config.COLOR_ACCENT_BLUE,
        config.COLOR_BTN_START_BG,
        config.COLOR_BTN_START_HOVER,
        config.COLOR_BTN_STOP_BG,
        config.COLOR_BTN_STOP_HOVER,
        config.COLOR_TEXT_PRIMARY,
        config.COLOR_TEXT_SECONDARY,
        config.COLOR_TEXT_MUTED,
        config.COLOR_TEXT_ACCENT,
    ]
    for color in colors:
        assert is_valid_hex_color(color), f"Invalid hex color: {color}"


def test_phase4_controls_configuration():
    """Verify Phase 4 action definitions, default mappings, safety gates, and thresholds."""
    assert config.ACTION_NONE in config.SUPPORTED_ACTIONS
    assert config.ACTION_PLAY_PAUSE in config.SUPPORTED_ACTIONS
    assert config.ACTION_NEXT_TRACK in config.SUPPORTED_ACTIONS
    assert config.ACTION_PREV_TRACK in config.SUPPORTED_ACTIONS
    assert config.ACTION_VOLUME_PINCH in config.SUPPORTED_ACTIONS
    assert config.ACTION_MUTE in config.SUPPORTED_ACTIONS

    # Controls must default to disabled for safety
    assert config.CONTROLS_ENABLED_DEFAULT is False
    assert config.MOUSE_ENABLED_DEFAULT is False

    # Default gesture action map integrity
    assert isinstance(config.DEFAULT_GESTURE_ACTIONS, dict)
    assert config.DEFAULT_GESTURE_ACTIONS[config.GESTURE_THUMBS_UP] == config.ACTION_PLAY_PAUSE
    assert config.DEFAULT_GESTURE_ACTIONS[config.GESTURE_OPEN_PALM] == config.ACTION_NONE
    assert config.DEFAULT_GESTURE_ACTIONS[config.GESTURE_FIST] == config.ACTION_NONE

    # Volume and mouse parameter bounds
    assert config.ACTION_COOLDOWN_SEC > 0.0
    assert config.VOLUME_CHANGE_THRESHOLD > 0
    assert config.VOLUME_UPDATE_INTERVAL_SEC > 0.0
    assert 0.0 < config.VOLUME_PINCH_MIN_RATIO < config.VOLUME_PINCH_MAX_RATIO
    assert 0.0 < config.MOUSE_CLICK_THRESHOLD_RATIO < config.MOUSE_RELEASE_THRESHOLD_RATIO
    assert config.MOUSE_CLICK_COOLDOWN_SEC > 0.0
