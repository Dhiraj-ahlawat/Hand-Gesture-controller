"""
tests/test_gesture_recognizer.py
Comprehensive unit tests for GestureRecognizer geometry, gestures, and temporal smoothing.
"""

import pytest
from app.config import (
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
from app.gesture_recognizer import GestureRecognizer, GestureResult, dist_2d


def build_synthetic_hand(
    thumb_ext: bool = True,
    index_ext: bool = True,
    middle_ext: bool = True,
    ring_ext: bool = True,
    pinky_ext: bool = True,
    peace_spread: bool = False,
    palm_spread: bool = True,
    thumbs_up: bool = False,
    handedness: str = "Right",
) -> list:
    """Construct synthetic normalized 21-landmark hand coordinates for testing."""
    # Base wrist at (0.5, 0.8)
    lms = [(0.5, 0.8)] * 21
    lms[0] = (0.5, 0.8)
    lms[9] = (0.5, 0.5)      # Middle MCP -> palm_ref = 0.3
    lms[5] = (0.42, 0.52)    # Index MCP
    lms[13] = (0.58, 0.52)   # Ring MCP
    lms[17] = (0.65, 0.55)   # Pinky MCP
    lms[1] = (0.45, 0.72)    # Thumb CMC
    lms[2] = (0.40, 0.65)    # Thumb MCP

    # Left hand mirror
    mirror = -1 if handedness == "Left" else 1

    # Thumb
    if thumbs_up:
        # Pointing straight up
        lms[3] = (0.5 - 0.10 * mirror, 0.45)
        lms[4] = (0.5 - 0.10 * mirror, 0.28)
    elif thumb_ext:
        # Extended outward
        if palm_spread:
            lms[3] = (0.5 - 0.18 * mirror, 0.60)
            lms[4] = (0.5 - 0.26 * mirror, 0.54)
        else:
            # Parallel extension
            lms[3] = (0.5 - 0.12 * mirror, 0.58)
            lms[4] = (0.5 - 0.16 * mirror, 0.48)
    else:
        # Curled across palm
        lms[3] = (0.5 - 0.05 * mirror, 0.58)
        lms[4] = (0.5 + 0.02 * mirror, 0.55)

    # Index
    if index_ext:
        lms[6] = (0.42, 0.40)
        lms[7] = (0.40, 0.30)
        lms[8] = (0.33 if peace_spread else 0.42, 0.20)
    else:
        lms[6] = (0.42, 0.45)
        lms[7] = (0.42, 0.52)
        lms[8] = (0.42, 0.55)

    # Middle
    if middle_ext:
        lms[10] = (0.50, 0.38)
        lms[11] = (0.50, 0.28)
        lms[12] = (0.57 if peace_spread else 0.50, 0.18)
    else:
        lms[10] = (0.50, 0.45)
        lms[11] = (0.50, 0.52)
        lms[12] = (0.50, 0.55)

    # Ring
    if ring_ext:
        lms[14] = (0.58, 0.40)
        lms[15] = (0.58, 0.30)
        lms[16] = (0.58, 0.20)
    else:
        lms[14] = (0.58, 0.45)
        lms[15] = (0.58, 0.52)
        lms[16] = (0.58, 0.55)

    # Pinky
    if pinky_ext:
        lms[18] = (0.65, 0.42)
        lms[19] = (0.65, 0.33)
        lms[20] = (0.67 if palm_spread else 0.65, 0.24)
    else:
        lms[18] = (0.65, 0.47)
        lms[19] = (0.65, 0.53)
        lms[20] = (0.65, 0.56)

    return [(x, y, 0.0) for (x, y) in lms]


# ---------------------------------------------------------------------------
# Gesture Rule Verification Tests
# ---------------------------------------------------------------------------
def test_gesture_open_palm():
    """Verify Open Palm recognition with all 5 fingers spread."""
    recognizer = GestureRecognizer()
    lms = build_synthetic_hand(thumb_ext=True, index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True, palm_spread=True)
    res = recognizer.classify_hand(lms, handedness="Right")
    assert res.gesture_name == GESTURE_OPEN_PALM
    assert res.is_valid is True


def test_gesture_five_fingers():
    """Verify Five Fingers recognition when all 5 fingers are extended together."""
    recognizer = GestureRecognizer()
    lms = build_synthetic_hand(thumb_ext=True, index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True, palm_spread=False)
    res = recognizer.classify_hand(lms, handedness="Right")
    assert res.gesture_name in (GESTURE_FIVE_FINGERS, GESTURE_OPEN_PALM)
    assert res.is_valid is True


def test_gesture_fist():
    """Verify Fist recognition with all 5 fingers curled."""
    recognizer = GestureRecognizer()
    lms = build_synthetic_hand(thumb_ext=False, index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)
    res = recognizer.classify_hand(lms, handedness="Right")
    assert res.gesture_name == GESTURE_FIST
    assert res.is_valid is True


def test_gesture_thumbs_up():
    """Verify Thumbs Up recognition with thumb pointing upward and other 4 curled."""
    recognizer = GestureRecognizer()
    lms = build_synthetic_hand(thumbs_up=True, index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)
    res = recognizer.classify_hand(lms, handedness="Right")
    assert res.gesture_name == GESTURE_THUMBS_UP
    assert res.is_valid is True


def test_gesture_peace_sign_priority():
    """Verify Peace Sign priority over Two Fingers when fingers form a V-shape."""
    recognizer = GestureRecognizer()
    peace_lms = build_synthetic_hand(thumb_ext=False, index_ext=True, middle_ext=True, ring_ext=False, pinky_ext=False, peace_spread=True)
    res_peace = recognizer.classify_hand(peace_lms, handedness="Right")
    assert res_peace.gesture_name == GESTURE_PEACE
    assert res_peace.is_valid is True


def test_gesture_two_fingers():
    """Verify Two Fingers recognition when index & middle are held parallel without V-spread."""
    recognizer = GestureRecognizer()
    two_lms = build_synthetic_hand(thumb_ext=False, index_ext=True, middle_ext=True, ring_ext=False, pinky_ext=False, peace_spread=False)
    res_two = recognizer.classify_hand(two_lms, handedness="Right")
    assert res_two.gesture_name == GESTURE_TWO_FINGERS
    assert res_two.is_valid is True


def test_gesture_one_finger():
    """Verify One Finger recognition with only Index finger extended."""
    recognizer = GestureRecognizer()
    lms = build_synthetic_hand(thumb_ext=False, index_ext=True, middle_ext=False, ring_ext=False, pinky_ext=False)
    res = recognizer.classify_hand(lms, handedness="Right")
    assert res.gesture_name == GESTURE_ONE_FINGER
    assert res.is_valid is True


def test_gesture_three_fingers():
    """Verify Three Fingers recognition with Index, Middle, and Ring extended."""
    recognizer = GestureRecognizer()
    lms = build_synthetic_hand(thumb_ext=False, index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=False)
    res = recognizer.classify_hand(lms, handedness="Right")
    assert res.gesture_name == GESTURE_THREE_FINGERS
    assert res.is_valid is True


def test_gesture_four_fingers():
    """Verify Four Fingers recognition with 4 fingers extended and thumb folded."""
    recognizer = GestureRecognizer()
    lms = build_synthetic_hand(thumb_ext=False, index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True)
    res = recognizer.classify_hand(lms, handedness="Right")
    assert res.gesture_name == GESTURE_FOUR_FINGERS
    assert res.is_valid is True


def test_gesture_unknown_pose():
    """Ambiguous or unmapped finger combinations should classify as Unknown Gesture."""
    recognizer = GestureRecognizer()
    # Pinky finger only extended
    lms = build_synthetic_hand(thumb_ext=False, index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=True)
    res = recognizer.classify_hand(lms, handedness="Right")
    assert res.gesture_name == GESTURE_UNKNOWN
    assert res.is_valid is False


def test_left_and_right_handedness():
    """Verify both Left and Right hands are supported seamlessly."""
    recognizer = GestureRecognizer()
    r_lms = build_synthetic_hand(thumbs_up=True, index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False, handedness="Right")
    l_lms = build_synthetic_hand(thumbs_up=True, index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False, handedness="Left")

    res_r = recognizer.classify_hand(r_lms, handedness="Right")
    res_l = recognizer.classify_hand(l_lms, handedness="Left")

    assert res_r.gesture_name == GESTURE_THUMBS_UP
    assert res_l.gesture_name == GESTURE_THUMBS_UP


def test_malformed_or_missing_landmarks():
    """Malformed or insufficient landmark arrays should safely return invalid without crashing."""
    recognizer = GestureRecognizer()

    # Empty list
    res_empty = recognizer.classify_hand([])
    assert res_empty.gesture_name == GESTURE_NONE
    assert res_empty.is_valid is False

    # Incomplete list (10 landmarks)
    res_short = recognizer.classify_hand([(0.5, 0.5, 0.0)] * 10)
    assert res_short.gesture_name == GESTURE_NONE
    assert res_short.is_valid is False

    # Degenerate palm (all coordinates at origin)
    res_zero = recognizer.classify_hand([(0.0, 0.0, 0.0)] * 21)
    assert res_zero.gesture_name == GESTURE_UNKNOWN


# ---------------------------------------------------------------------------
# Temporal Smoothing & Stability Tests
# ---------------------------------------------------------------------------
def test_temporal_smoothing_consistency_threshold():
    """Verify gesture transitions only take effect once min_consistent is met."""
    recognizer = GestureRecognizer(history_length=5, min_consistent_predictions=3, cooldown_sec=0.0)

    fist_lms = build_synthetic_hand(thumb_ext=False, index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)
    peace_lms = build_synthetic_hand(thumb_ext=False, index_ext=True, middle_ext=True, ring_ext=False, pinky_ext=False, peace_spread=True)

    # Establish initial stable state (Fist) with 3 frames
    for _ in range(3):
        results = recognizer.update([fist_lms])
    assert recognizer.current_gesture == GESTURE_FIST

    # 1st and 2nd frame of Peace Sign: should NOT flip yet (below threshold of 3)
    recognizer.update([peace_lms])
    assert recognizer.current_gesture == GESTURE_FIST

    recognizer.update([peace_lms])
    assert recognizer.current_gesture == GESTURE_FIST

    # 3rd frame of Peace Sign: hits threshold of 3 -> switches to Peace Sign!
    recognizer.update([peace_lms])
    assert recognizer.current_gesture == GESTURE_PEACE


def test_tracking_loss_resets_history():
    """Verify that losing hand tracking resets prediction history."""
    recognizer = GestureRecognizer(history_length=5, min_consistent_predictions=3)
    fist_lms = build_synthetic_hand(thumb_ext=False, index_ext=False, middle_ext=False, ring_ext=False, pinky_ext=False)

    for _ in range(4):
        recognizer.update([fist_lms])
    assert recognizer.current_gesture == GESTURE_FIST

    # Hand tracking lost (empty list)
    empty_results = recognizer.update([])
    assert empty_results == []
    assert recognizer.current_gesture == GESTURE_NONE
