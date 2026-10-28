"""
app/camera.py
Thread-safe OpenCV camera service for Hand Gesture Controller.

Provides non-blocking video capture, integrated MediaPipe hand tracking,
real-time gesture recognition, and clean lifecycle management.
"""

import logging
import queue
import threading
import time
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

from app.config import (
    DEFAULT_CAMERA_INDEX,
    FRAME_HEIGHT,
    FRAME_WIDTH,
    GESTURE_NONE,
    STATUS_ERROR,
    STATUS_NO_HAND,
    STATUS_RUNNING,
    STATUS_STARTING,
    STATUS_STOPPED,
    STATUS_TRACKING_OFFLINE,
    STATUS_TRACKING_SCANNING,
)
from app.detector import HandDetectionResult, HandDetector

logger = logging.getLogger(__name__)


class CameraService:
    """
    Manages webcam capture in a dedicated background worker thread with real-time
    MediaPipe hand detection and gesture recognition.
    
    Ensures the Tkinter UI main thread remains completely responsive, prevents
    multiple simultaneous capture loops, and guarantees camera release on shutdown.
    """

    def __init__(
        self,
        camera_index: int = DEFAULT_CAMERA_INDEX,
        hand_detector: Optional[HandDetector] = None,
        enable_hand_tracking: bool = True,
    ) -> None:
        self._camera_index: int = camera_index
        self._status: str = STATUS_STOPPED
        self._status_message: str = "Camera stopped."
        self._error_message: str = ""

        # Hand tracking and gesture engine integration
        self._enable_hand_tracking: bool = enable_hand_tracking
        self._owns_detector: bool = False
        if hand_detector is not None:
            self._hand_detector: Optional[HandDetector] = hand_detector
        elif enable_hand_tracking:
            try:
                self._hand_detector = HandDetector()
                self._owns_detector = True
            except Exception as exc:
                logger.error("Failed to instantiate HandDetector: %s", exc)
                self._hand_detector = None
        else:
            self._hand_detector = None

        # Threading synchronization primitives
        self._thread: Optional[threading.Thread] = None
        self._stop_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()
        self._status_queue: queue.Queue = queue.Queue()

        # Frame and metrics buffers (protected by _lock)
        self._latest_frame: Optional[np.ndarray] = None
        self._fps: float = 0.0
        self._frame_count: int = 0
        self._actual_width: int = 0
        self._actual_height: int = 0

        # Hand tracking & gesture metrics
        self._detected_hands_count: int = 0
        self._hand_status_message: str = STATUS_NO_HAND
        self._tracking_status: str = STATUS_TRACKING_OFFLINE
        self._handedness_list: List[str] = []
        self._current_gesture: str = GESTURE_NONE
        self._active_gestures_count: int = 0
        self._latest_landmarks_list: List[List[Tuple[float, float, float]]] = []
        self._tracking_confirmed_lost: bool = True

        # Optional observer callback for status updates: fn(status: str, message: str)
        self.on_status_changed: Optional[Callable[[str, str], None]] = None

    # -----------------------------------------------------------------------
    # Public Properties & State Queries
    # -----------------------------------------------------------------------
    @property
    def status(self) -> str:
        """Return the current camera status (Stopped, Starting, Running, Error)."""
        with self._lock:
            return self._status

    @property
    def status_message(self) -> str:
        """Return the current status message."""
        with self._lock:
            return self._status_message

    @property
    def status_queue(self) -> queue.Queue:
        """Return the thread-safe status queue for main-thread event draining."""
        return self._status_queue

    @property
    def error_message(self) -> str:
        """Return the last error message, if any."""
        with self._lock:
            return self._error_message

    @property
    def camera_index(self) -> int:
        """Return the target camera index."""
        return self._camera_index

    @camera_index.setter
    def camera_index(self, index: int) -> None:
        """Set a new camera index (only effective when stopped)."""
        with self._lock:
            if self._status in (STATUS_RUNNING, STATUS_STARTING):
                raise RuntimeError("Cannot change camera index while camera is active.")
            self._camera_index = int(index)

    @property
    def resolution(self) -> Tuple[int, int]:
        """Return the captured frame resolution (width, height)."""
        with self._lock:
            return (self._actual_width, self._actual_height)

    @property
    def detected_hands_count(self) -> int:
        """Return the number of currently detected hands (0, 1, or 2)."""
        with self._lock:
            return self._detected_hands_count

    @property
    def hand_status_message(self) -> str:
        """Return the hand detection status label."""
        with self._lock:
            return self._hand_status_message

    @property
    def tracking_status(self) -> str:
        """Return the tracking state label (Active, Scanning, Offline)."""
        with self._lock:
            return self._tracking_status

    @property
    def current_gesture(self) -> str:
        """Return the currently recognized gesture name."""
        with self._lock:
            return self._current_gesture

    @property
    def active_gestures_count(self) -> int:
        """Return count of currently recognized gestures."""
        with self._lock:
            return self._active_gestures_count

    @property
    def handedness_list(self) -> List[str]:
        """Return list of detected hand labels ('Left', 'Right')."""
        with self._lock:
            return list(self._handedness_list)

    @property
    def tracking_confirmed_lost(self) -> bool:
        """Return True if hand absence is confirmed beyond the grace period."""
        with self._lock:
            return self._tracking_confirmed_lost

    @property
    def hand_detector(self) -> Optional[HandDetector]:
        """Return the attached HandDetector instance, if any."""
        return self._hand_detector

    def is_running(self) -> bool:
        """Check if camera is currently capturing frames."""
        with self._lock:
            return self._status == STATUS_RUNNING

    # -----------------------------------------------------------------------
    # Lifecycle Control (Start / Stop / Close)
    # -----------------------------------------------------------------------
    def start(self, camera_index: Optional[int] = None) -> bool:
        """
        Start the background webcam capture and tracking thread safely.
        
        Ignores repeated calls if already starting or running.
        Returns True if thread was launched, False if already active.
        """
        with self._lock:
            if self._status in (STATUS_STARTING, STATUS_RUNNING):
                logger.warning("Camera start requested, but camera is already %s.", self._status)
                return False

            if camera_index is not None:
                self._camera_index = int(camera_index)

            self._status = STATUS_STARTING
            self._error_message = ""
            self._fps = 0.0
            self._frame_count = 0
            self._detected_hands_count = 0
            self._hand_status_message = STATUS_NO_HAND
            self._tracking_status = STATUS_TRACKING_SCANNING
            self._current_gesture = GESTURE_NONE
            self._active_gestures_count = 0
            self._latest_landmarks_list = []
            self._tracking_confirmed_lost = True
            self._stop_event.clear()

        self._notify_status(STATUS_STARTING, f"Connecting to camera {self._camera_index}...")

        # Spawn daemon worker thread so it does not block application exit
        self._thread = threading.Thread(
            target=self._capture_worker,
            name="CameraCaptureWorker",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """
        Signal the capture worker thread to stop and release the camera device safely.
        """
        with self._lock:
            if self._status == STATUS_STOPPED and (self._thread is None or not self._thread.is_alive()):
                return
            self._stop_event.set()

        # Wait briefly for worker thread to finish releasing OpenCV resource
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        with self._lock:
            self._status = STATUS_STOPPED
            self._latest_frame = None
            self._fps = 0.0
            self._detected_hands_count = 0
            self._hand_status_message = STATUS_NO_HAND
            self._tracking_status = STATUS_TRACKING_OFFLINE
            self._current_gesture = GESTURE_NONE
            self._active_gestures_count = 0
            self._handedness_list = []
            self._latest_landmarks_list = []
            self._tracking_confirmed_lost = True

        if self._hand_detector is not None:
            self._hand_detector.gesture_recognizer.reset()

        self._notify_status(STATUS_STOPPED, "Camera stopped.")
        logger.info("Camera service successfully stopped and released.")

    def close(self) -> None:
        """Completely release camera service and underlying detector resources."""
        self.stop()
        if self._owns_detector and self._hand_detector is not None:
            self._hand_detector.close()
            self._hand_detector = None

    # -----------------------------------------------------------------------
    # Frame and Metric Retrieval
    # -----------------------------------------------------------------------
    def get_latest_frame(self) -> Tuple[bool, Optional[np.ndarray], float, int]:
        """
        Retrieve the latest frame from the buffer in a non-blocking, thread-safe manner.
        
        Returns:
            Tuple of (has_frame: bool, frame: Optional[np.ndarray], fps: float, frame_count: int)
        """
        with self._lock:
            if self._latest_frame is None:
                return False, None, self._fps, self._frame_count
            return True, self._latest_frame.copy(), self._fps, self._frame_count

    def get_tracking_data(self) -> Tuple[int, str, str, List[str], str, int]:
        """
        Retrieve latest hand tracking and gesture recognition metrics.
        
        Returns:
            Tuple of (detected_hands_count, hand_status_message, tracking_status,
                      handedness_list, current_gesture, active_gestures_count)
        """
        with self._lock:
            return (
                self._detected_hands_count,
                self._hand_status_message,
                self._tracking_status,
                list(self._handedness_list),
                self._current_gesture,
                self._active_gestures_count,
            )

    def get_latest_landmarks(self) -> List[List[Tuple[float, float, float]]]:
        """
        Retrieve a copy of the latest normalized 3D landmarks for active hands.
        """
        with self._lock:
            return [list(lms) for lms in self._latest_landmarks_list]

    @property
    def latest_landmarks(self) -> List[List[Tuple[float, float, float]]]:
        """Property returning latest normalized landmarks."""
        return self.get_latest_landmarks()

    # -----------------------------------------------------------------------
    # Internal Worker Loop
    # -----------------------------------------------------------------------
    def _capture_worker(self) -> None:
        """Worker thread entry point for video capture, tracking, and gesture recognition."""
        cap = None
        try:
            logger.info("Opening OpenCV VideoCapture at index %d...", self._camera_index)
            cap = cv2.VideoCapture(self._camera_index)

            # Request configured frame dimensions
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

            if not cap.isOpened():
                raise RuntimeError(
                    f"Camera device {self._camera_index} could not be opened. "
                    "Ensure no other application is using it and macOS Camera permissions are granted."
                )

            # Minimize buffer size to eliminate frame latency buildup
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            # Initial warm-up frame read
            ret, frame = cap.read()
            if not ret or frame is None:
                raise RuntimeError(
                    f"Unable to read initial frame from camera {self._camera_index}. "
                    "Please check macOS System Settings > Privacy & Security > Camera."
                )

            h, w = frame.shape[:2]

            # Initial detection pass
            annotated_frame = frame
            hands_count = 0
            hand_status = STATUS_NO_HAND
            tracking_status = STATUS_TRACKING_SCANNING
            handedness = []
            gesture = GESTURE_NONE
            active_g_count = 0
            tracking_confirmed_lost = True

            landmarks_list = []
            if self._enable_hand_tracking and self._hand_detector is not None:
                try:
                    det_res = self._hand_detector.process(frame)
                    annotated_frame = det_res.annotated_frame if det_res.annotated_frame is not None else frame
                    hands_count = det_res.detected_hands_count
                    hand_status = det_res.status_message
                    tracking_status = det_res.tracking_status
                    handedness = det_res.handedness_list
                    gesture = det_res.current_gesture
                    active_g_count = det_res.active_gestures_count
                    landmarks_list = det_res.landmarks_list
                    tracking_confirmed_lost = det_res.tracking_confirmed_lost
                except Exception as det_exc:
                    logger.warning("Hand detector error on initial frame: %s", det_exc)
                    annotated_frame = frame
                    hands_count = 0
                    hand_status = STATUS_NO_HAND
                    tracking_status = STATUS_TRACKING_SCANNING
                    handedness = []
                    gesture = GESTURE_NONE
                    active_g_count = 0
                    landmarks_list = []
                    tracking_confirmed_lost = True

            with self._lock:
                self._actual_width = w
                self._actual_height = h
                self._status = STATUS_RUNNING
                self._latest_frame = annotated_frame
                self._frame_count = 1
                self._detected_hands_count = hands_count
                self._hand_status_message = hand_status
                self._tracking_status = tracking_status
                self._handedness_list = handedness
                self._current_gesture = gesture
                self._active_gestures_count = active_g_count
                self._latest_landmarks_list = landmarks_list
                self._tracking_confirmed_lost = tracking_confirmed_lost

            self._notify_status(STATUS_RUNNING, f"Camera live ({w}x{h}).")
            logger.info("Camera successfully running at %dx%d.", w, h)

            last_time = time.perf_counter()
            fps_window = []
            consecutive_failures = 0

            # Continuous frame capture, tracking, and gesture recognition loop
            while not self._stop_event.is_set():
                ret, frame = cap.read()
                current_time = time.perf_counter()

                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures > 15:
                        raise RuntimeError("Lost connection to camera stream.")
                    time.sleep(0.02)
                    continue

                consecutive_failures = 0

                # Compute rolling FPS
                delta = current_time - last_time
                last_time = current_time
                if delta > 0:
                    fps_window.append(1.0 / delta)
                    if len(fps_window) > 20:
                        fps_window.pop(0)
                    computed_fps = sum(fps_window) / len(fps_window)
                else:
                    computed_fps = 30.0

                # Run Hand Detection & Gesture Recognition
                landmarks_list = []
                tracking_confirmed_lost = True
                if self._enable_hand_tracking and self._hand_detector is not None:
                    try:
                        det_res = self._hand_detector.process(frame)
                        processed_frame = det_res.annotated_frame if det_res.annotated_frame is not None else frame
                        hands_count = det_res.detected_hands_count
                        hand_status = det_res.status_message
                        tracking_status = det_res.tracking_status
                        handedness = det_res.handedness_list
                        gesture = det_res.current_gesture
                        active_g_count = det_res.active_gestures_count
                        landmarks_list = det_res.landmarks_list
                        tracking_confirmed_lost = det_res.tracking_confirmed_lost
                    except Exception as det_exc:
                        logger.warning("Hand detector error on frame: %s", det_exc)
                        processed_frame = frame
                        hands_count = 0
                        hand_status = STATUS_NO_HAND
                        tracking_status = STATUS_TRACKING_SCANNING
                        handedness = []
                        gesture = GESTURE_NONE
                        active_g_count = 0
                        landmarks_list = []
                        tracking_confirmed_lost = True
                else:
                    processed_frame = frame
                    hands_count = 0
                    hand_status = STATUS_NO_HAND
                    tracking_status = STATUS_TRACKING_OFFLINE
                    handedness = []
                    gesture = GESTURE_NONE
                    active_g_count = 0
                    landmarks_list = []
                    tracking_confirmed_lost = True

                with self._lock:
                    self._latest_frame = processed_frame
                    self._fps = computed_fps
                    self._frame_count += 1
                    self._detected_hands_count = hands_count
                    self._hand_status_message = hand_status
                    self._tracking_status = tracking_status
                    self._handedness_list = handedness
                    self._current_gesture = gesture
                    self._active_gestures_count = active_g_count
                    self._latest_landmarks_list = landmarks_list
                    self._tracking_confirmed_lost = tracking_confirmed_lost

                # Slight sleep to yield CPU
                time.sleep(0.005)

        except Exception as exc:
            logger.error("Camera worker encountered error: %s", exc, exc_info=True)
            with self._lock:
                self._status = STATUS_ERROR
                self._error_message = str(exc)
                self._latest_frame = None
                self._fps = 0.0
                self._detected_hands_count = 0
                self._hand_status_message = STATUS_NO_HAND
                self._tracking_status = STATUS_TRACKING_OFFLINE
                self._handedness_list = []
                self._current_gesture = GESTURE_NONE
                self._active_gestures_count = 0
                self._tracking_confirmed_lost = True
            self._notify_status(STATUS_ERROR, str(exc))

        finally:
            if cap is not None:
                try:
                    cap.release()
                    logger.debug("OpenCV VideoCapture released.")
                except Exception as release_exc:
                    logger.warning("Error releasing VideoCapture: %s", release_exc)

            with self._lock:
                if self._status != STATUS_ERROR:
                    self._status = STATUS_STOPPED

    def _notify_status(self, status: str, message: str) -> None:
        """Store status message, enqueue for UI thread, and invoke callback safely."""
        with self._lock:
            self._status_message = message
        self._status_queue.put((status, message))
        if self.on_status_changed is not None:
            try:
                self.on_status_changed(status, message)
            except Exception as exc:
                logger.warning("Error in on_status_changed callback: %s", exc)
