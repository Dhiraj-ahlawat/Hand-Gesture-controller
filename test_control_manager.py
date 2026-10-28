"""
tests/test_control_manager.py
Automated unit tests for ControlManager, system action dispatching, cooldowns,
volume pinch normalization, virtual mouse debouncing, and accessibility handling.

Uses MockSystemActionAdapter so NO real OS hardware, volume, media, or mouse events are touched.
"""

import time
import pytest

from app.config import (
    ACTION_COOLDOWN_SEC,
    ACTION_MUTE,
    ACTION_NEXT_TRACK,
    ACTION_NONE,
    ACTION_PLAY_PAUSE,
    ACTION_PREV_TRACK,
    ACTION_VOLUME_PINCH,
    GESTURE_FIST,
    GESTURE_FIVE_FINGERS,
    GESTURE_FOUR_FINGERS,
    GESTURE_NONE,
    GESTURE_ONE_FINGER,
    GESTURE_OPEN_PALM,
    GESTURE_PEACE,
    GESTURE_THREE_FINGERS,
    GESTURE_THUMBS_UP,
    GESTURE_TWO_FINGERS,
    GESTURE_UNKNOWN,
)
from app.control_manager import (
    ControlManager,
    MockSystemActionAdapter,
    SystemActionResult,
)
from tests.test_gesture_recognizer import build_synthetic_hand


# ---------------------------------------------------------------------------
# Test Fixtures & Helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_adapter():
    """Create a fresh in-memory MockSystemActionAdapter."""
    return MockSystemActionAdapter(accessibility_granted=True)


@pytest.fixture
def manager(mock_adapter):
    """Create a ControlManager backed by the mock adapter."""
    return ControlManager(adapter=mock_adapter, action_cooldown_sec=0.2)


def build_hand_with_pinch_distance(pinch_distance: float) -> list:
    """
    Construct synthetic hand landmarks with a specified distance between thumb tip and index tip.
    Wrist at (0.5, 0.8), Middle MCP at (0.5, 0.5) -> palm_ref = 0.3.
    """
    hand = build_synthetic_hand(thumb_ext=True, index_ext=True)
    # Thumb tip at landmark 4
    # Index tip at landmark 8
    # Place index tip at (0.5, 0.5) and thumb tip at (0.5, 0.5 + pinch_distance)
    hand[8] = (0.5, 0.40, 0.0)
    hand[4] = (0.5, 0.40 + pinch_distance, 0.0)
    return hand


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------
def test_controls_disabled_by_default(manager, mock_adapter):
    """Controls must default to disabled for safety; no actions should execute."""
    assert manager.controls_enabled is False
    assert manager.mouse_enabled is False
    assert "Disabled" in manager.status_feedback

    hand = build_synthetic_hand(thumbs_up=True)
    res = manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_THUMBS_UP,
        landmarks=hand,
    )
    assert res is None
    assert len(mock_adapter.actions_history) == 0


def test_no_action_when_controls_disabled_even_with_valid_gesture(manager, mock_adapter):
    """Even if gestures are recognized, disabled controls prevent any action."""
    manager.enable_controls(False)
    hand = build_synthetic_hand(thumbs_up=True)

    for _ in range(5):
        res = manager.process_frame(
            is_camera_running=True,
            detected_hands_count=1,
            current_gesture=GESTURE_THUMBS_UP,
            landmarks=hand,
        )
        assert res is None

    assert len(mock_adapter.actions_history) == 0


def test_no_action_when_camera_stopped_or_tracking_lost(manager, mock_adapter):
    """No actions should execute if camera is stopped or hand count drops to 0."""
    manager.enable_controls(True)
    hand = build_synthetic_hand(thumbs_up=True)

    # Camera not running
    res1 = manager.process_frame(
        is_camera_running=False,
        detected_hands_count=1,
        current_gesture=GESTURE_THUMBS_UP,
        landmarks=hand,
    )
    assert res1 is None

    # Zero hands detected
    res2 = manager.process_frame(
        is_camera_running=True,
        detected_hands_count=0,
        current_gesture=GESTURE_THUMBS_UP,
        landmarks=[],
    )
    assert res2 is None
    assert len(mock_adapter.actions_history) == 0


def test_no_action_for_unknown_or_none_gestures(manager, mock_adapter):
    """Unknown gestures or Waiting for hand states should never trigger actions."""
    manager.enable_controls(True)
    hand = build_synthetic_hand()

    for invalid_gesture in (GESTURE_UNKNOWN, GESTURE_NONE, ""):
        res = manager.process_frame(
            is_camera_running=True,
            detected_hands_count=1,
            current_gesture=invalid_gesture,
            landmarks=hand,
        )
        assert res is None

    assert len(mock_adapter.actions_history) == 0


def test_discrete_action_execution_and_edge_triggering(manager, mock_adapter):
    """
    Verify discrete action triggers once on gesture onset, and does NOT
    repeatedly fire on consecutive frames while the gesture is held.
    """
    manager.enable_controls(True)
    hand = build_synthetic_hand(thumbs_up=True)

    # Frame 1: Onset of Thumbs Up -> triggers Play/Pause
    res1 = manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_THUMBS_UP,
        landmarks=hand,
    )
    assert res1 is not None
    assert res1.action_type == ACTION_PLAY_PAUSE
    assert res1.success is True
    assert len(mock_adapter.actions_history) == 1

    # Frames 2, 3, 4: Holding Thumbs Up -> Edge-trigger prevents duplicate execution
    for _ in range(3):
        res_held = manager.process_frame(
            is_camera_running=True,
            detected_hands_count=1,
            current_gesture=GESTURE_THUMBS_UP,
            landmarks=hand,
        )
        assert res_held is None

    assert len(mock_adapter.actions_history) == 1


def test_action_cooldown_and_rearm_after_pose_change(manager, mock_adapter):
    """Transitioning to a new gesture respects the cooldown period before triggering."""
    manager.enable_controls(True)
    hand_thumbs = build_synthetic_hand(thumbs_up=True)
    hand_fist = build_synthetic_hand(thumb_ext=False, index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)
    hand_three = build_synthetic_hand(thumb_ext=False, index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=False)

    # Trigger action 1: Thumbs Up -> Play/Pause
    res1 = manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_THUMBS_UP,
        landmarks=hand_thumbs,
    )
    assert res1 is not None
    assert len(mock_adapter.actions_history) == 1

    # Hand transitions to Fist (mapped to None)
    manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_FIST,
        landmarks=hand_fist,
    )

    # Immediate transition to Three Fingers before cooldown expires (cooldown is 0.2s)
    res_immediate = manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_THREE_FINGERS,
        landmarks=hand_three,
    )
    assert res_immediate is None  # Blocked by cooldown
    assert "Cooldown" in manager.status_feedback

    # Wait for cooldown to expire
    time.sleep(0.25)

    # Now Three Fingers executes Next Track successfully
    res_after_cooldown = manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_THREE_FINGERS,
        landmarks=hand_three,
    )
    assert res_after_cooldown is not None
    assert res_after_cooldown.action_type == ACTION_NEXT_TRACK
    assert len(mock_adapter.actions_history) == 2


def test_custom_and_invalid_action_mappings(manager, mock_adapter):
    """Custom mappings are supported; invalid action strings fall back to None."""
    custom_map = {
        GESTURE_FOUR_FINGERS: ACTION_MUTE,
        GESTURE_TWO_FINGERS: "INVALID_ACTION_NAME",
    }
    manager.set_gesture_action_map(custom_map)
    assert manager.gesture_action_map[GESTURE_FOUR_FINGERS] == ACTION_MUTE
    assert manager.gesture_action_map[GESTURE_TWO_FINGERS] == ACTION_NONE

    manager.enable_controls(True)
    hand = build_synthetic_hand()

    # Four fingers triggers Mute
    res_mute = manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_FOUR_FINGERS,
        landmarks=hand,
    )
    assert res_mute is not None
    assert res_mute.action_type == ACTION_MUTE
    assert mock_adapter.is_muted is True


def test_continuous_volume_pinch_normalization_and_smoothing(manager, mock_adapter):
    """Continuous volume pinch normalizes distance by palm_ref and updates volume smoothly."""
    manager.enable_controls(True)
    # Map Peace sign to Continuous Volume
    manager.set_gesture_action_map({GESTURE_PEACE: ACTION_VOLUME_PINCH})

    # Palm ref is 0.3 (wrist at 0.8, middle MCP at 0.5)
    # A pinch distance of 0.24 -> ratio = 0.24 / 0.3 = 0.80 (high volume)
    wide_hand = build_hand_with_pinch_distance(0.24)

    # Process frame with wide pinch
    res_vol = manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_PEACE,
        landmarks=wide_hand,
    )
    # First update commits smoothed volume
    assert res_vol is not None
    assert "Volume" in res_vol.action_type
    assert mock_adapter.current_volume > 50


def test_virtual_mouse_movement_and_smoothing(manager, mock_adapter):
    """Virtual mouse maps index fingertip to screen coordinates when enabled."""
    manager.enable_controls(True)
    manager.enable_mouse(True)

    hand = build_synthetic_hand(index_ext=True)
    # Index tip at landmark 8 is (0.42, 0.20)
    manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_ONE_FINGER,
        landmarks=hand,
    )

    # Verify mouse move was dispatched to adapter
    move_actions = [a for a in mock_adapter.actions_history if a.action_type == "Mouse Move"]
    assert len(move_actions) > 0
    assert mock_adapter.mouse_position != (0, 0)


def test_virtual_mouse_click_debouncing_and_release(manager, mock_adapter):
    """Pinching below threshold triggers left click; requires release before re-clicking."""
    manager.enable_controls(True)
    manager.enable_mouse(True)

    # Palm ref is 0.3. A pinch distance of 0.05 gives ratio = 0.05 / 0.3 = 0.166 (< 0.28 threshold)
    pinch_hand = build_hand_with_pinch_distance(0.05)
    open_hand = build_hand_with_pinch_distance(0.25)

    # Frame 1: Pinch down -> triggers click
    manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_ONE_FINGER,
        landmarks=pinch_hand,
    )
    assert len(mock_adapter.click_history) == 1

    # Frame 2: Still pinched -> debounced, no second click
    manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_ONE_FINGER,
        landmarks=pinch_hand,
    )
    assert len(mock_adapter.click_history) == 1

    # Release pinch
    manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_ONE_FINGER,
        landmarks=open_hand,
    )
    time.sleep(0.45)  # Wait for click cooldown

    # Pinch again -> second click triggers
    manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_ONE_FINGER,
        landmarks=pinch_hand,
    )
    assert len(mock_adapter.click_history) == 2


def test_missing_macos_accessibility_permissions_handled_gracefully(manager, mock_adapter):
    """When macOS Accessibility permission is not granted, click reports clear status without crashing."""
    mock_adapter.accessibility_granted = False
    manager.enable_controls(True)
    manager.enable_mouse(True)

    pinch_hand = build_hand_with_pinch_distance(0.05)
    manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_ONE_FINGER,
        landmarks=pinch_hand,
    )

    # Click should fail gracefully with accessibility message
    assert len(mock_adapter.click_history) == 0
    assert "Accessibility permission required" in manager.status_feedback


def test_emergency_stop_mechanism(manager, mock_adapter):
    """Emergency stop immediately disables controls, mouse, and resets states."""
    manager.enable_controls(True)
    manager.enable_mouse(True)
    assert manager.controls_enabled is True
    assert manager.mouse_enabled is True

    manager.emergency_stop()
    assert manager.controls_enabled is False
    assert manager.mouse_enabled is False
    assert "Emergency Stop" in manager.status_feedback

    # Processing a valid gesture after emergency stop produces no action
    hand = build_synthetic_hand(thumbs_up=True)
    res = manager.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_THUMBS_UP,
        landmarks=hand,
    )
    assert res is None
    assert len(mock_adapter.actions_history) == 0


def test_arbitrary_commands_in_mapping_fail_safely(manager, mock_adapter):
    """Ensure malicious command strings or arbitrary shell syntax in mappings are safely rejected."""
    manager.enable_controls(True)

    malicious_inputs = [
        "rm -rf /",
        "; cat /etc/passwd",
        "$(whoami)",
        "`id`",
        "import os; os.system('echo pwned')",
        "osascript -e 'display dialog \"pwned\"'",
    ]

    for evil_cmd in malicious_inputs:
        manager.set_gesture_action_map({GESTURE_THUMBS_UP: evil_cmd})
        # The mapping should sanitize the action to ACTION_NONE
        assert manager.gesture_action_map.get(GESTURE_THUMBS_UP) == ACTION_NONE

        hand = build_synthetic_hand(thumbs_up=True)
        res = manager.process_frame(
            is_camera_running=True,
            detected_hands_count=1,
            current_gesture=GESTURE_THUMBS_UP,
            landmarks=hand,
        )
        assert res is None
        assert len(mock_adapter.actions_history) == 0

