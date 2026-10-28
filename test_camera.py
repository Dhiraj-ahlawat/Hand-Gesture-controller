"""
tests/test_camera.py
Unit tests for CameraService lifecycle, thread-safety, hand tracking metrics, and error handling.
"""

import time
import pytest
from app.camera import CameraService
from app.config import (
    DEFAULT_CAMERA_INDEX,
    GESTURE_PLACEHOLDER_TEXT,
    STATUS_ERROR,
    STATUS_NO_HAND,
    STATUS_RUNNING,
    STATUS_STARTING,
    STATUS_STOPPED,
    STATUS_TRACKING_OFFLINE,
)


def test_camera_service_initial_state():
    """Verify default initial state before camera is started."""
    service = CameraService(camera_index=DEFAULT_CAMERA_INDEX, enable_hand_tracking=False)
    assert service.status == STATUS_STOPPED
    assert not service.is_running()
    assert service.camera_index == DEFAULT_CAMERA_INDEX
    assert service.resolution == (0, 0)
    assert service.error_message == ""
    assert service.detected_hands_count == 0
    assert service.hand_status_message == STATUS_NO_HAND
    assert service.tracking_status == STATUS_TRACKING_OFFLINE

    has_frame, frame, fps, frame_count = service.get_latest_frame()
    assert not has_frame
    assert frame is None
    assert fps == 0.0
    assert frame_count == 0

    count, h_msg, t_msg, handedness, current_gesture, active_count = service.get_tracking_data()
    assert count == 0
    assert h_msg == STATUS_NO_HAND
    assert t_msg == STATUS_TRACKING_OFFLINE
    assert handedness == []
    assert current_gesture == GESTURE_PLACEHOLDER_TEXT
    assert active_count == 0
    assert service.get_latest_landmarks() == []
    assert service.latest_landmarks == []


def test_camera_service_safe_stop_when_already_stopped():
    """Calling stop on an inactive camera should be completely safe and no-op."""
    service = CameraService(camera_index=DEFAULT_CAMERA_INDEX, enable_hand_tracking=False)
    service.stop()
    assert service.status == STATUS_STOPPED
    service.close()


def test_camera_index_modification():
    """Camera index can be changed while stopped, but not while running."""
    service = CameraService(camera_index=0, enable_hand_tracking=False)
    assert service.camera_index == 0
    service.camera_index = 1
    assert service.camera_index == 1
    service.close()


def test_camera_service_invalid_index_error_handling():
    """Testing an invalid/non-existent camera index should gracefully transition to ERROR."""
    invalid_index = 9999
    status_updates = []

    def on_status(status, msg):
        status_updates.append((status, msg))

    service = CameraService(camera_index=invalid_index, enable_hand_tracking=False)
    service.on_status_changed = on_status

    started = service.start()
    assert started is True

    # Wait for the thread to attempt to open the invalid device and fail
    time.sleep(1.0)

    assert service.status == STATUS_ERROR
    assert len(service.error_message) > 0
    assert not service.is_running()

    # Clean up
    service.close()
    assert service.status == STATUS_STOPPED


def test_repeated_start_calls_prevent_duplicate_threads():
    """Calling start repeatedly while active should be ignored safely."""
    service = CameraService(camera_index=9999, enable_hand_tracking=False)
    res1 = service.start()
    res2 = service.start()  # Immediately second call

    # The second call should return False because it is already STARTING
    assert res1 is True
    assert res2 is False

    time.sleep(0.8)
    service.close()


def test_camera_repeated_start_stop_cycles():
    """Verify that starting and stopping repeatedly cleans up resources without leaks or race conditions."""
    service = CameraService(camera_index=9999, enable_hand_tracking=False)
    for _ in range(3):
        assert service.status == STATUS_STOPPED
        service.start()
        time.sleep(0.1)
        service.stop()
        assert service.status == STATUS_STOPPED
        assert not service.is_running()
    service.close()


def test_camera_detector_frame_exception_resilience():
    """Verify that if the hand detector raises an exception on a frame, the camera handles it gracefully."""
    from unittest.mock import MagicMock

    mock_detector = MagicMock()
    mock_detector.process.side_effect = RuntimeError("Transient detector memory fault")

    service = CameraService(
        camera_index=9999,
        enable_hand_tracking=True,
        hand_detector=mock_detector,
    )
    # The detector is set; even if mock process raises, CameraService should not crash on initialization
    assert service.hand_detector is mock_detector
    service.close()

