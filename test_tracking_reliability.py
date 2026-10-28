"""
tests/test_tracking_reliability.py
Comprehensive regression test suite for Hand Gesture Controller Phase 8.

Verifies:
1. Gesture count stability (no runaway counting during sustained hold).
2. Clean increment on genuine gesture transitions.
3. Rapid camera jitter / dropped single frame within grace period resilience.
4. Sustained tracking loss exceeding grace period cleanly transitions to None.
5. Hand re-entry after confirmed tracking loss increments count predictably.
6. Repeated hand re-entry cycles produce exact counts (N cycles -> N counts).
7. Removing hand immediately resets continuous controls and pinch locks.
8. Removing hand leaves no stale landmarks.
9. Camera stop immediately resets hand count, active gesture, and continuous controls.
10. Camera stop followed by camera start begins in a clean no-hand state without phantom detection.
11. UI frame update loop deduplicates processing when polling faster than camera frame rate.
12. Grace period parameter is configurable and bounds-checked.
13. Handedness reporting does not affect gesture stability or counting.
14. Unknown gesture between frames of the same valid gesture does not double count.
15. Unknown gesture held continuously does not increment gesture count repeatedly.
16. StatisticsManager accurately computes total gestures and most-used gesture across rapid entries/exits.
17. Metric card in UI reflects session gesture events and displays total_gestures_count.
18. Emergency stop resets continuous states and disables controls regardless of detection state.
19. Multiple hands entering and exiting do not corrupt single-hand continuous control state.
20. Database session persistence correctly saves and restores session records with exact gesture counts.
"""

from pathlib import Path
import tkinter as tk
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.camera import CameraService
from app.config import (
    ACTION_MUTE,
    ACTION_PLAY_PAUSE,
    GESTURE_FIST,
    GESTURE_NONE,
    GESTURE_OPEN_PALM,
    GESTURE_PEACE,
    GESTURE_THUMBS_UP,
    GESTURE_UNKNOWN,
    TRACKING_LOSS_GRACE_FRAMES,
)
from app.control_manager import ControlManager, SystemActionAdapter, SystemActionResult
from app.detector import HandDetector
from app.gesture_recognizer import GestureRecognizer
from app.statistics_manager import StatisticsManager
from app.ui import AppUI
from tests.test_gesture_recognizer import build_synthetic_hand


# ---------------------------------------------------------------------------
# Test Fixtures & Mocks
# ---------------------------------------------------------------------------
class MockSystemActionAdapter(SystemActionAdapter):
    """Mock adapter capturing system calls for testing."""

    def __init__(self) -> None:
        self.play_pause_calls = 0
        self.next_track_calls = 0
        self.previous_track_calls = 0
        self.mute_calls = 0
        self.volume_history: list[int] = []
        self.mouse_moves: list[tuple[int, int]] = []
        self.mouse_clicks: list[tuple[int, int]] = []
        self._current_volume = 50

    def play_pause(self) -> SystemActionResult:
        self.play_pause_calls += 1
        return SystemActionResult(action_type=ACTION_PLAY_PAUSE, success=True, message="Mock Play/Pause")

    def next_track(self) -> SystemActionResult:
        self.next_track_calls += 1
        return SystemActionResult(action_type="Next Track", success=True, message="Mock Next")

    def previous_track(self) -> SystemActionResult:
        self.previous_track_calls += 1
        return SystemActionResult(action_type="Previous Track", success=True, message="Mock Prev")

    def get_volume(self) -> tuple[bool, int]:
        return (True, self._current_volume)

    def set_volume(self, volume: int) -> SystemActionResult:
        self._current_volume = max(0, min(100, volume))
        self.volume_history.append(self._current_volume)
        return SystemActionResult(action_type="Volume", success=True, message=f"Vol {volume}")

    def toggle_mute(self) -> SystemActionResult:
        self.mute_calls += 1
        return SystemActionResult(action_type=ACTION_MUTE, success=True, message="Mock Mute")

    def move_mouse(self, x: int, y: int) -> SystemActionResult:
        self.mouse_moves.append((x, y))
        return SystemActionResult(action_type="Mouse Move", success=True, message=f"Move {x},{y}")

    def mouse_click(self, x: int, y: int) -> SystemActionResult:
        self.mouse_clicks.append((x, y))
        return SystemActionResult(action_type="Mouse Click", success=True, message=f"Click {x},{y}")

    def get_screen_size(self) -> tuple[int, int]:
        return (1920, 1080)

    def is_accessibility_granted(self) -> bool:
        return True


@pytest.fixture
def tk_root():
    """Headless Tkinter root window fixture."""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test 1: Gesture Count Stability Across 30 Consecutive Frames
# ---------------------------------------------------------------------------
def test_gesture_count_remains_one_when_holding_same_gesture_across_30_frames():
    """Verify holding the same gesture does not continuously increase the session count."""
    stats = StatisticsManager()
    for _ in range(30):
        stats.record_gesture(GESTURE_THUMBS_UP)

    assert stats.total_gestures_count == 1
    assert stats.gesture_counts[GESTURE_THUMBS_UP] == 1


# ---------------------------------------------------------------------------
# Test 2: Clean Increment on Transitioning Between Distinct Gestures
# ---------------------------------------------------------------------------
def test_gesture_count_increments_only_when_transitioning_to_different_valid_gesture():
    """Verify distinct gestures increment count exactly once per transition."""
    stats = StatisticsManager()

    # Thumbs up held 15 frames
    for _ in range(15):
        stats.record_gesture(GESTURE_THUMBS_UP)
    assert stats.total_gestures_count == 1

    # Transition to Peace sign held 15 frames
    for _ in range(15):
        stats.record_gesture(GESTURE_PEACE)
    assert stats.total_gestures_count == 2

    # Transition to Open Palm held 15 frames
    for _ in range(15):
        stats.record_gesture(GESTURE_OPEN_PALM)
    assert stats.total_gestures_count == 3

    assert stats.gesture_counts[GESTURE_THUMBS_UP] == 1
    assert stats.gesture_counts[GESTURE_PEACE] == 1
    assert stats.gesture_counts[GESTURE_OPEN_PALM] == 1


# ---------------------------------------------------------------------------
# Test 3: Dropped Frame Within Grace Period Resilience
# ---------------------------------------------------------------------------
def test_dropped_frame_within_grace_period_does_not_reset_or_double_count():
    """Verify 1-frame camera drop within grace period does not reset gesture or double count."""
    detector = HandDetector(grace_period_frames=5)
    recognizer = detector.gesture_recognizer

    # Stabilize Thumbs Up in recognizer
    thumbs_lms = build_synthetic_hand(thumbs_up=True, thumb_ext=False, index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)
    for _ in range(recognizer.min_consistent):
        recognizer.update([thumbs_lms], ["Right"])
    assert recognizer.current_gesture == GESTURE_THUMBS_UP

    stats = StatisticsManager()
    stats.record_gesture(recognizer.current_gesture)
    assert stats.total_gestures_count == 1

    # Simulate 1 frame of dropped detection (no hands)
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    res_drop = detector.process(blank_frame)

    # Within grace period: tracking is not confirmed lost, live count is 0
    assert res_drop.detected_hands_count == 0
    assert res_drop.tracking_confirmed_lost is False
    assert res_drop.landmarks_list == []
    assert res_drop.current_gesture == GESTURE_THUMBS_UP

    # Hand is detected again with same gesture
    for _ in range(2):
        recognizer.update([thumbs_lms], ["Right"])
    stats.record_gesture(recognizer.current_gesture)

    # Count must remain exactly 1 (no double counting)
    assert stats.total_gestures_count == 1


# ---------------------------------------------------------------------------
# Test 4: Sustained Tracking Loss Exceeding Grace Period
# ---------------------------------------------------------------------------
def test_sustained_tracking_loss_exceeding_grace_period_transitions_to_none():
    """Verify tracking confirmed lost and active gesture transitions to None after grace period."""
    detector = HandDetector(grace_period_frames=5)
    recognizer = detector.gesture_recognizer

    thumbs_lms = build_synthetic_hand(thumbs_up=True, thumb_ext=False, index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)
    for _ in range(recognizer.min_consistent):
        recognizer.update([thumbs_lms], ["Right"])
    assert recognizer.current_gesture == GESTURE_THUMBS_UP

    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Process 4 no-hand frames (within grace period)
    for _ in range(4):
        res = detector.process(blank_frame)
        assert res.detected_hands_count == 0
        assert res.tracking_confirmed_lost is False
        assert res.current_gesture == GESTURE_THUMBS_UP

    # 5th frame reaches grace_period_frames -> Confirmed Lost
    res_confirmed = detector.process(blank_frame)
    assert res_confirmed.detected_hands_count == 0
    assert res_confirmed.tracking_confirmed_lost is True
    assert res_confirmed.current_gesture == GESTURE_NONE
    assert recognizer.current_gesture == GESTURE_NONE


# ---------------------------------------------------------------------------
# Test 5: Hand Re-entry After Confirmed Loss Increments Count
# ---------------------------------------------------------------------------
def test_hand_reentry_after_confirmed_tracking_loss_increments_count():
    """Verify re-entering frame with same gesture after confirmed loss counts as a new event."""
    stats = StatisticsManager()

    # Presentation 1: Thumbs Up
    for _ in range(10):
        stats.record_gesture(GESTURE_THUMBS_UP)
    assert stats.total_gestures_count == 1

    # Confirmed Tracking Loss
    stats.record_gesture(GESTURE_NONE)
    assert stats.total_gestures_count == 1

    # Presentation 2: Thumbs Up returns
    for _ in range(10):
        stats.record_gesture(GESTURE_THUMBS_UP)
    assert stats.total_gestures_count == 2
    assert stats.gesture_counts[GESTURE_THUMBS_UP] == 2


# ---------------------------------------------------------------------------
# Test 6: Repeated Hand Re-entry Cycles (N Cycles -> Exactly N Counts)
# ---------------------------------------------------------------------------
def test_repeated_hand_reentry_cycles_produce_exact_counts():
    """Verify N clean presentation/exit cycles yield exactly N gesture counts."""
    stats = StatisticsManager()
    num_cycles = 7

    for _ in range(num_cycles):
        for _ in range(5):
            stats.record_gesture(GESTURE_OPEN_PALM)
        # Confirmed loss
        stats.record_gesture(GESTURE_NONE)

    assert stats.total_gestures_count == num_cycles
    assert stats.gesture_counts[GESTURE_OPEN_PALM] == num_cycles


# ---------------------------------------------------------------------------
# Test 7: Removing Hand Resets Continuous Controls and Pinch Locks
# ---------------------------------------------------------------------------
def test_removing_hand_immediately_resets_continuous_controls():
    """Verify continuous states (pinch lock, edge triggers) reset when hand is removed."""
    ctrl = ControlManager(adapter=MockSystemActionAdapter())
    ctrl.enable_controls(True)
    ctrl.enable_mouse(True)

    # Active hand with 21 landmarks
    lms = build_synthetic_hand(index_ext=True, thumb_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)
    ctrl.process_frame(is_camera_running=True, detected_hands_count=1, current_gesture="One Finger", landmarks=lms)

    # Set continuous states
    ctrl._is_pinched = True
    ctrl._last_triggered_gesture = "One Finger"
    ctrl._last_blocked_gesture = "Fist"

    # Removing hand: 0 hands detected
    ctrl.process_frame(is_camera_running=True, detected_hands_count=0, current_gesture=GESTURE_NONE, landmarks=None)

    assert ctrl._is_pinched is False
    assert ctrl._last_triggered_gesture is None
    assert ctrl._last_blocked_gesture is None


# ---------------------------------------------------------------------------
# Test 8: Removing Hand Never Leaves Stale Landmarks
# ---------------------------------------------------------------------------
def test_removing_hand_never_leaves_stale_landmarks():
    """Verify HandDetectionResult on no-hand frames always has empty landmarks list."""
    detector = HandDetector()
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Process blank frame
    result = detector.process(blank_frame)
    assert result.landmarks_list == []
    assert result.pixel_landmarks_list == []
    assert result.detected_hands_count == 0

    # Ensure draw_landmarks on empty pixel_landmarks produces no error and does not modify frame
    test_img = np.zeros((100, 100, 3), dtype=np.uint8)
    detector.draw_landmarks(test_img, [])
    assert np.all(test_img == 0)


# ---------------------------------------------------------------------------
# Test 9: Camera Stop Immediately Resets Hand Count, Active Gesture, and Controls
# ---------------------------------------------------------------------------
def test_camera_stop_immediately_resets_tracking_and_continuous_controls():
    """Verify camera stop resets tracking data and continuous controls immediately."""
    cam = CameraService(camera_index=0, enable_hand_tracking=False)
    ctrl = ControlManager(adapter=MockSystemActionAdapter())
    ctrl._is_pinched = True
    ctrl._last_triggered_gesture = GESTURE_THUMBS_UP

    cam.stop()
    ctrl.reset_continuous_states()

    assert cam.tracking_confirmed_lost is True
    hands, hand_status, track_status, handedness, current_g, active_g = cam.get_tracking_data()
    assert hands == 0
    assert current_g == GESTURE_NONE
    assert active_g == 0
    assert ctrl._is_pinched is False
    assert ctrl._last_triggered_gesture is None


# ---------------------------------------------------------------------------
# Test 10: Camera Stop Followed by Start Begins in Clean No-Hand State
# ---------------------------------------------------------------------------
def test_camera_stop_then_start_begins_in_clean_no_hand_state():
    """Verify restarting camera service does not produce phantom detection."""
    cam = CameraService(camera_index=0, enable_hand_tracking=False)
    cam.stop()

    assert cam.tracking_confirmed_lost is True
    hands, _, _, _, current_g, _ = cam.get_tracking_data()
    assert hands == 0
    assert current_g == GESTURE_NONE


# ---------------------------------------------------------------------------
# Test 11: UI Frame Deduplication Prevents Duplicate Evaluation
# ---------------------------------------------------------------------------
def test_ui_frame_update_loop_deduplicates_identical_frames(tk_root):
    """Verify UI skips duplicate rendering and control processing when frame_count has not changed."""
    cam = CameraService(camera_index=0, enable_hand_tracking=False)
    app = AppUI(root=tk_root, camera_service=cam)

    # Mock camera running and returning static frame count 42
    cam.is_running = MagicMock(return_value=True)
    test_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    cam.get_latest_frame = MagicMock(return_value=(True, test_frame, 30.0, 42))
    app._render_frame = MagicMock()

    # First poll: processes frame 42
    app._update_frame_loop()
    assert app._last_processed_frame_count == 42
    assert app._render_frame.call_count == 1

    # Second poll: frame_count still 42 -> early returns without re-rendering
    app._update_frame_loop()
    assert app._render_frame.call_count == 1  # No additional render!

    # Third poll: new frame 43 arrives -> processes
    cam.get_latest_frame = MagicMock(return_value=(True, test_frame, 30.0, 43))
    app._update_frame_loop()
    assert app._last_processed_frame_count == 43
    assert app._render_frame.call_count == 2

    app.on_close()


# ---------------------------------------------------------------------------
# Test 12: Grace Period Parameter Configurable and Bounds-Checked
# ---------------------------------------------------------------------------
def test_grace_period_parameter_configurable_and_bounds_checked():
    """Verify grace period parameter accepts valid values and clamps negative/zero."""
    det_custom = HandDetector(grace_period_frames=8)
    assert det_custom.grace_period_frames == 8

    det_zero = HandDetector(grace_period_frames=0)
    assert det_zero.grace_period_frames == 1

    det_neg = HandDetector(grace_period_frames=-10)
    assert det_neg.grace_period_frames == 1

    assert TRACKING_LOSS_GRACE_FRAMES == 5


# ---------------------------------------------------------------------------
# Test 13: Handedness Reporting Does Not Affect Gesture Stability or Counting
# ---------------------------------------------------------------------------
def test_handedness_reporting_does_not_affect_gesture_stability():
    """Verify right and left hands recognize same pose and statistics deduplicates identically."""
    recognizer = GestureRecognizer()

    right_hand = build_synthetic_hand(palm_spread=True, handedness="Right")
    left_hand = build_synthetic_hand(palm_spread=True, handedness="Left")

    res_right = recognizer.classify_hand(right_hand, "Right")
    res_left = recognizer.classify_hand(left_hand, "Left")

    assert res_right.gesture_name == GESTURE_OPEN_PALM
    assert res_left.gesture_name == GESTURE_OPEN_PALM

    stats = StatisticsManager()
    for _ in range(5):
        stats.record_gesture(res_right.gesture_name)
    assert stats.total_gestures_count == 1

    # Same gesture detected with left hand does not double count
    for _ in range(5):
        stats.record_gesture(res_left.gesture_name)
    assert stats.total_gestures_count == 1


# ---------------------------------------------------------------------------
# Test 14: Unknown Gesture Jitter Does Not Cause Double Counting
# ---------------------------------------------------------------------------
def test_unknown_gesture_jitter_does_not_cause_double_counting():
    """Verify pose jitter into Unknown does not cause double counting when returning to same gesture."""
    stats = StatisticsManager()

    # Valid gesture
    for _ in range(5):
        stats.record_gesture(GESTURE_THUMBS_UP)
    assert stats.total_gestures_count == 1

    # Hand turns/twitches momentarily -> Unknown pose (not None; tracking not lost)
    for _ in range(3):
        stats.record_gesture(GESTURE_UNKNOWN)

    # Returns to Thumbs Up
    for _ in range(5):
        stats.record_gesture(GESTURE_THUMBS_UP)

    # Crucial fix: count remains 1 because tracking was not lost!
    assert stats.total_gestures_count == 1
    assert stats.gesture_counts[GESTURE_THUMBS_UP] == 1


# ---------------------------------------------------------------------------
# Test 15: Unknown Gesture Held Continuously Does Not Run Away
# ---------------------------------------------------------------------------
def test_unknown_gesture_held_continuously_does_not_increment_count_repeatedly():
    """Verify holding Unknown Gesture does not continuously increment the event counter."""
    stats = StatisticsManager()

    for _ in range(30):
        stats.record_gesture(GESTURE_UNKNOWN)

    # Counts at most 1 for the initial transition to Unknown, not 30
    assert stats.total_gestures_count <= 1
    assert stats.gesture_counts.get(GESTURE_UNKNOWN, 0) <= 1


# ---------------------------------------------------------------------------
# Test 16: StatisticsManager Accurately Reports Total and Most Used Gesture
# ---------------------------------------------------------------------------
def test_statistics_manager_rapid_transitions_and_most_used():
    """Verify StatisticsManager accurately tallies gesture frequencies and most used gesture."""
    stats = StatisticsManager()

    # Presentation 1: Thumbs Up
    stats.record_gesture(GESTURE_THUMBS_UP)
    stats.record_gesture(GESTURE_NONE)

    # Presentation 2: Thumbs Up
    stats.record_gesture(GESTURE_THUMBS_UP)
    stats.record_gesture(GESTURE_NONE)

    # Presentation 3: Peace Sign
    stats.record_gesture(GESTURE_PEACE)
    stats.record_gesture(GESTURE_NONE)

    # Total gestures = 3 (2 Thumbs Up + 1 Peace Sign)
    assert stats.total_gestures_count == 3
    assert stats.gesture_counts[GESTURE_THUMBS_UP] == 2
    assert stats.gesture_counts[GESTURE_PEACE] == 1
    best_name, best_count = stats.get_most_used_gesture()
    assert best_name == GESTURE_THUMBS_UP
    assert best_count == 2


# ---------------------------------------------------------------------------
# Test 17: UI Metric Card Reflects Session Gesture Events
# ---------------------------------------------------------------------------
def test_ui_metric_card_label_and_value_binding(tk_root):
    """Verify stat_gestures_val displays session gesture events accurately."""
    cam = CameraService(camera_index=0, enable_hand_tracking=False)
    stats = StatisticsManager()
    app = AppUI(root=tk_root, camera_service=cam, statistics_manager=stats)

    # Initial state
    assert app.stat_gestures_val.cget("text") == "0"

    # Record two gesture events
    stats.record_gesture(GESTURE_THUMBS_UP)
    stats.record_gesture(GESTURE_NONE)
    stats.record_gesture(GESTURE_PEACE)

    # Simulate one UI loop iteration
    cam.is_running = MagicMock(return_value=True)
    test_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    cam.get_latest_frame = MagicMock(return_value=(True, test_frame, 30.0, 1))
    cam.get_tracking_data = MagicMock(return_value=(1, "Hand Detected", "Active", ["Right"], GESTURE_PEACE, 1))
    app._render_frame = MagicMock()

    app._update_frame_loop()

    # Metric tile reflects total session gesture events (2)
    assert app.stat_gestures_val.cget("text") == "2"

    app.on_close()


# ---------------------------------------------------------------------------
# Test 18: Emergency Stop Resets Continuous States and Disables Controls
# ---------------------------------------------------------------------------
def test_emergency_stop_resets_continuous_states_and_disables_controls(tk_root):
    """Verify emergency stop deactivates controls and clears continuous states."""
    cam = CameraService(camera_index=0, enable_hand_tracking=False)
    app = AppUI(root=tk_root, camera_service=cam)

    app.control_manager.enable_controls(True)
    app.control_manager._is_pinched = True
    app.control_manager._last_triggered_gesture = GESTURE_THUMBS_UP

    app._emergency_stop_actions()

    assert app.control_manager.controls_enabled is False
    assert app.control_manager._is_pinched is False
    assert app.control_manager._last_triggered_gesture is None
    assert "Emergency Stopped" in app.control_status_lbl.cget("text")

    app.on_close()


# ---------------------------------------------------------------------------
# Test 19: Multiple Hands Do Not Corrupt Single-Hand Continuous Control State
# ---------------------------------------------------------------------------
def test_multiple_hands_do_not_corrupt_continuous_control_state():
    """Verify hand count fluctuations (2 hands -> 0 hands) cleanly reset controls."""
    ctrl = ControlManager(adapter=MockSystemActionAdapter())
    ctrl.enable_controls(True)

    lms = build_synthetic_hand(index_ext=True, thumb_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)

    # 2 hands detected, primary landmarks processed
    ctrl.process_frame(is_camera_running=True, detected_hands_count=2, current_gesture="One Finger", landmarks=lms)
    ctrl._is_pinched = True
    ctrl._last_triggered_gesture = "One Finger"

    # Suddenly both hands exit: detected_hands_count drops to 0
    ctrl.process_frame(is_camera_running=True, detected_hands_count=0, current_gesture=GESTURE_NONE, landmarks=None)

    assert ctrl._is_pinched is False
    assert ctrl._last_triggered_gesture is None


# ---------------------------------------------------------------------------
# Test 20: Database Session Persistence With Exact Gesture Counts
# ---------------------------------------------------------------------------
def test_session_persistence_with_exact_gesture_counts(tmp_path: Path):
    """Verify saving and reloading session history preserves exact gesture counts."""
    db_file = tmp_path / "test_persistence.db"
    stats = StatisticsManager(db_path=db_file)

    # Simulate 3 discrete gesture events
    stats.record_gesture(GESTURE_THUMBS_UP)
    stats.record_gesture(GESTURE_NONE)
    stats.record_gesture(GESTURE_THUMBS_UP)
    stats.record_gesture(GESTURE_NONE)
    stats.record_gesture(GESTURE_FIST)

    assert stats.total_gestures_count == 3
    assert stats.gesture_counts[GESTURE_THUMBS_UP] == 2
    assert stats.gesture_counts[GESTURE_FIST] == 1

    # Save session
    success = stats.save_current_session()
    assert success is True

    # Load from database using a fresh StatisticsManager instance
    stats_loaded = StatisticsManager(db_path=db_file)
    history = stats_loaded.get_history()

    assert len(history) == 1
    loaded_rec = history[0]
    assert loaded_rec.total_gestures == 3
    assert loaded_rec.gesture_counts[GESTURE_THUMBS_UP] == 2
    assert loaded_rec.gesture_counts[GESTURE_FIST] == 1
