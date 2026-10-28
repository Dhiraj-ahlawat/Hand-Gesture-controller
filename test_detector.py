"""
tests/test_detector.py
Unit tests for HandDetector, landmark drawing, status formatting, and error handling.
"""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from app.config import (
    MAX_HANDS,
    MIN_DETECTION_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE,
    STATUS_HAND_DETECTED,
    STATUS_NO_HAND,
    STATUS_TRACKING_ACTIVE,
    STATUS_TRACKING_OFFLINE,
    STATUS_TRACKING_SCANNING,
)
from app.detector import (
    FINGERTIP_INDICES,
    HAND_CONNECTIONS,
    HandDetectionResult,
    HandDetector,
    format_hand_status,
)


def test_format_hand_status():
    """Verify hand status label formatting for various counts and engine states."""
    # Camera offline
    h_msg, t_msg = format_hand_status(0, is_running=False)
    assert h_msg == STATUS_NO_HAND
    assert t_msg == STATUS_TRACKING_OFFLINE

    # Camera active, no hands
    h_msg, t_msg = format_hand_status(0, is_running=True)
    assert h_msg == STATUS_NO_HAND
    assert t_msg == STATUS_TRACKING_SCANNING

    # 1 hand detected
    h_msg, t_msg = format_hand_status(1, is_running=True)
    assert "1 Hand" in h_msg
    assert t_msg == STATUS_TRACKING_ACTIVE

    # 2 hands detected
    h_msg, t_msg = format_hand_status(2, is_running=True)
    assert "2 Hands" in h_msg
    assert t_msg == STATUS_TRACKING_ACTIVE


def test_hand_connections_integrity():
    """Verify skeletal connections and fingertip indices."""
    assert len(HAND_CONNECTIONS) == 21
    for start, end in HAND_CONNECTIONS:
        assert 0 <= start <= 20
        assert 0 <= end <= 20
        assert start != end

    assert set(FINGERTIP_INDICES) == {4, 8, 12, 16, 20}


def test_hand_detector_initialization_defaults():
    """Verify detector initialization parameters match config defaults."""
    detector = HandDetector(
        max_hands=MAX_HANDS,
        min_detection_confidence=MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
    )
    assert detector.max_hands == 2
    assert detector.min_detection_confidence == 0.6
    assert detector.min_tracking_confidence == 0.6
    assert detector.is_initialized is True
    assert detector.api_type in ("tasks", "solutions")
    detector.close()


def test_process_blank_frame_no_hands():
    """Verify that processing a blank frame detects zero hands without error."""
    detector = HandDetector()
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    result = detector.process(blank_frame)

    assert isinstance(result, HandDetectionResult)
    assert result.detected_hands_count == 0
    assert len(result.landmarks_list) == 0
    assert result.status_message == STATUS_NO_HAND
    assert result.tracking_status == STATUS_TRACKING_SCANNING
    assert result.annotated_frame is not None
    assert result.annotated_frame.shape == (480, 640, 3)
    detector.close()


def test_process_empty_or_none_frame():
    """Verify that passing None or empty frame is handled safely."""
    detector = HandDetector()
    res_none = detector.process(None)
    assert res_none.detected_hands_count == 0

    res_empty = detector.process(np.array([]))
    assert res_empty.detected_hands_count == 0
    detector.close()


def test_draw_landmarks_on_image():
    """Verify landmark drawing helper executes cleanly and modifies pixel values."""
    detector = HandDetector()
    canvas = np.zeros((300, 300, 3), dtype=np.uint8)

    # Synthetic 21 landmarks
    fake_landmarks = [(50 + i * 5, 50 + i * 5) for i in range(21)]
    detector.draw_landmarks(canvas, fake_landmarks, handedness="Right")

    # Canvas should no longer be completely black
    assert np.any(canvas > 0)
    detector.close()


def test_draw_landmarks_short_list_ignored():
    """Passing fewer than 21 landmarks should safely return without drawing."""
    detector = HandDetector()
    canvas = np.zeros((100, 100, 3), dtype=np.uint8)
    short_lms = [(10, 10), (20, 20)]

    detector.draw_landmarks(canvas, short_lms)
    assert np.all(canvas == 0)
    detector.close()


def test_detector_graceful_handling_on_init_failure():
    """If MediaPipe detector initialization fails, process() should degrade gracefully."""
    with patch("mediapipe.tasks.python.vision.HandLandmarker.create_from_options", side_effect=RuntimeError("Mock Init Error")):
        detector = HandDetector(model_path="/nonexistent/model.task")
        # In case fallback also fails or isn't present
        detector._is_initialized = False
        detector._init_error = "Mock Init Error"

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = detector.process(frame)

        assert result.detected_hands_count == 0
        assert "Mock Init Error" in result.tracking_status
        assert result.annotated_frame is not None
        detector.close()
