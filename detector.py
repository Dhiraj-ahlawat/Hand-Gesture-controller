"""
app/detector.py
Real-time hand detection, landmark tracking, and gesture recognition visualization.

Integrates MediaPipe HandLandmarker with GestureRecognizer to detect up to two hands,
track 21 3D landmarks, and classify hand gestures in real time with sleek HUD rendering.
"""

import logging
import os
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

from app.config import (
    COLOR_BONE_BGR,
    COLOR_FINGERTIP_BGR,
    COLOR_JOINT_BGR,
    COLOR_WRIST_BGR,
    GESTURE_NONE,
    GESTURE_UNKNOWN,
    MAX_HANDS,
    MIN_DETECTION_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE,
    MODEL_DOWNLOAD_URL,
    MODEL_FILENAME,
    MODEL_SUBDIR,
    RADIUS_FINGERTIP,
    RADIUS_JOINT,
    RADIUS_WRIST,
    STATUS_HAND_DETECTED,
    STATUS_NO_HAND,
    STATUS_TRACKING_ACTIVE,
    STATUS_TRACKING_ERROR,
    STATUS_TRACKING_OFFLINE,
    STATUS_TRACKING_SCANNING,
    SUPPORTED_GESTURES,
    THICKNESS_BONE,
    TRACKING_LOSS_GRACE_FRAMES,
)
from app.gesture_recognizer import GestureRecognizer, GestureResult

logger = logging.getLogger(__name__)

# Standard 21 MediaPipe hand connections connecting 21 landmarks
HAND_CONNECTIONS: Tuple[Tuple[int, int], ...] = (
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index finger
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle finger
    (5, 9), (9, 10), (10, 11), (11, 12),
    # Ring finger
    (9, 13), (13, 14), (14, 15), (15, 16),
    # Pinky finger
    (13, 17), (17, 18), (18, 19), (19, 20),
    # Palm closure
    (0, 17),
)

FINGERTIP_INDICES: Tuple[int, ...] = (4, 8, 12, 16, 20)


@dataclass
class HandDetectionResult:
    """Structured result from hand detection, tracking, and gesture recognition."""

    detected_hands_count: int = 0
    landmarks_list: List[List[Tuple[float, float, float]]] = field(default_factory=list)
    pixel_landmarks_list: List[List[Tuple[int, int]]] = field(default_factory=list)
    handedness_list: List[str] = field(default_factory=list)
    annotated_frame: Optional[np.ndarray] = None
    status_message: str = STATUS_NO_HAND
    tracking_status: str = STATUS_TRACKING_SCANNING
    current_gesture: str = GESTURE_NONE
    gesture_results: List[GestureResult] = field(default_factory=list)
    active_gestures_count: int = 0
    tracking_confirmed_lost: bool = False


def format_hand_status(count: int, is_running: bool = True) -> Tuple[str, str]:
    """
    Format user-facing status messages for the UI dashboard.
    
    Returns:
        Tuple of (hand_status_label, tracking_status_label)
    """
    if not is_running:
        return STATUS_NO_HAND, STATUS_TRACKING_OFFLINE

    if count == 0:
        return STATUS_NO_HAND, STATUS_TRACKING_SCANNING
    elif count == 1:
        return f"{STATUS_HAND_DETECTED} (1 Hand)", STATUS_TRACKING_ACTIVE
    else:
        return f"{STATUS_HAND_DETECTED} ({count} Hands)", STATUS_TRACKING_ACTIVE


class HandDetector:
    """
    Manages MediaPipe hand landmark detection and real-time visualization.
    
    Initializes once on startup and processes video frames sequentially within
    the existing camera pipeline.
    """

    def __init__(
        self,
        max_hands: int = MAX_HANDS,
        min_detection_confidence: float = MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence: float = MIN_TRACKING_CONFIDENCE,
        model_path: Optional[str] = None,
        gesture_recognizer: Optional[GestureRecognizer] = None,
        grace_period_frames: int = TRACKING_LOSS_GRACE_FRAMES,
    ) -> None:
        self.max_hands: int = max_hands
        self.min_detection_confidence: float = min_detection_confidence
        self.min_tracking_confidence: float = min_tracking_confidence
        self._model_path: Optional[str] = model_path
        self.grace_period_frames: int = max(1, grace_period_frames)
        self._consecutive_no_hand_frames: int = 0

        self._detector = None
        self._api_type: Optional[str] = None  # "tasks" or "solutions"
        self._is_initialized: bool = False
        self._init_error: Optional[str] = None

        # Gesture recognizer integration
        self._gesture_recognizer: GestureRecognizer = (
            gesture_recognizer if gesture_recognizer is not None else GestureRecognizer()
        )

        self._init_detector()

    @property
    def is_initialized(self) -> bool:
        """Check if MediaPipe hand detector initialized successfully."""
        return self._is_initialized

    @property
    def init_error(self) -> Optional[str]:
        """Return the initialization error message if one occurred."""
        return self._init_error

    @property
    def api_type(self) -> Optional[str]:
        """Return the active MediaPipe API backend ('tasks' or 'solutions')."""
        return self._api_type

    @property
    def gesture_recognizer(self) -> GestureRecognizer:
        """Return the attached gesture recognition engine."""
        return self._gesture_recognizer

    def _resolve_model_path(self) -> str:
        """Locate or download the hand_landmarker.task model file."""
        if self._model_path and os.path.exists(self._model_path):
            return self._model_path

        base_dir = os.path.dirname(os.path.abspath(__file__))
        models_dir = os.path.join(base_dir, MODEL_SUBDIR)
        os.makedirs(models_dir, exist_ok=True)
        local_path = os.path.join(models_dir, MODEL_FILENAME)

        if not os.path.exists(local_path) or os.path.getsize(local_path) < 1000:
            logger.info("Downloading %s to %s...", MODEL_FILENAME, local_path)
            req = urllib.request.Request(MODEL_DOWNLOAD_URL, headers={"User-Agent": "HandGestureController/1.0"})
            with urllib.request.urlopen(req, timeout=20) as response, open(local_path, "wb") as out_file:
                out_file.write(response.read())
            logger.info("Model downloaded successfully (%d bytes).", os.path.getsize(local_path))

        self._model_path = local_path
        return local_path

    def _init_detector(self) -> None:
        """Initialize the MediaPipe Hand Landmarker detector."""
        try:
            # 1. Attempt Modern MediaPipe Tasks API (MediaPipe 0.10+ / 1.x)
            try:
                from mediapipe.tasks import python as mp_python
                from mediapipe.tasks.python import vision

                model_path = self._resolve_model_path()
                base_options = mp_python.BaseOptions(model_asset_path=model_path)
                options = vision.HandLandmarkerOptions(
                    base_options=base_options,
                    num_hands=self.max_hands,
                    min_hand_detection_confidence=self.min_detection_confidence,
                    min_hand_presence_confidence=self.min_detection_confidence,
                    min_tracking_confidence=self.min_tracking_confidence,
                    running_mode=vision.RunningMode.IMAGE,
                )
                self._detector = vision.HandLandmarker.create_from_options(options)
                self._api_type = "tasks"
                self._is_initialized = True
                logger.info("Initialized MediaPipe Tasks HandLandmarker successfully.")
                return
            except Exception as task_exc:
                logger.warning("MediaPipe Tasks API init failed: %s. Checking Solutions API...", task_exc)

            # 2. Fallback: Legacy Solutions API (MediaPipe < 0.10)
            try:
                import mediapipe as mp
                if hasattr(mp, "solutions") and hasattr(mp.solutions, "hands"):
                    self._detector = mp.solutions.hands.Hands(
                        static_image_mode=False,
                        max_num_hands=self.max_hands,
                        min_detection_confidence=self.min_detection_confidence,
                        min_tracking_confidence=self.min_tracking_confidence,
                    )
                    self._api_type = "solutions"
                    self._is_initialized = True
                    logger.info("Initialized MediaPipe Solutions Hands successfully.")
                    return
            except Exception as sol_exc:
                logger.warning("MediaPipe Solutions API init failed: %s.", sol_exc)

            raise RuntimeError("Neither MediaPipe Tasks nor Solutions API is available in this environment.")

        except Exception as exc:
            self._is_initialized = False
            self._init_error = str(exc)
            logger.error("Failed to initialize MediaPipe HandDetector: %s", exc)

    def process(self, frame_bgr: np.ndarray) -> HandDetectionResult:
        """
        Process a single BGR frame, detecting hands, tracking landmarks, and classifying gestures.
        
        Args:
            frame_bgr: OpenCV BGR image numpy array.
            
        Returns:
            HandDetectionResult containing annotated frame, hand count, landmarks, gesture, and status.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            self._consecutive_no_hand_frames += 1
            if self._consecutive_no_hand_frames >= self.grace_period_frames:
                self._gesture_recognizer.reset()
            return HandDetectionResult(
                detected_hands_count=0,
                status_message=STATUS_NO_HAND,
                tracking_status=STATUS_TRACKING_SCANNING,
                current_gesture=GESTURE_NONE,
                tracking_confirmed_lost=(self._consecutive_no_hand_frames >= self.grace_period_frames),
            )

        if not self._is_initialized or self._detector is None:
            # Graceful degradation if detector couldn't initialize
            self._consecutive_no_hand_frames += 1
            self._gesture_recognizer.reset()
            return HandDetectionResult(
                detected_hands_count=0,
                annotated_frame=frame_bgr.copy(),
                status_message=STATUS_NO_HAND,
                tracking_status=f"{STATUS_TRACKING_ERROR}: {self._init_error or 'Unknown'}",
                current_gesture=GESTURE_NONE,
                tracking_confirmed_lost=True,
            )

        h, w = frame_bgr.shape[:2]
        annotated = frame_bgr.copy()
        landmarks_list: List[List[Tuple[float, float, float]]] = []
        pixel_landmarks_list: List[List[Tuple[int, int]]] = []
        handedness_list: List[str] = []

        try:
            # MediaPipe requires RGB color format
            rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

            if self._api_type == "tasks":
                import mediapipe as mp
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                result = self._detector.detect(mp_image)

                if result and result.hand_landmarks:
                    for i, hand_lms in enumerate(result.hand_landmarks):
                        label = "Hand"
                        if result.handedness and i < len(result.handedness):
                            cat_list = result.handedness[i]
                            if cat_list and len(cat_list) > 0:
                                label = cat_list[0].category_name

                        handedness_list.append(label)
                        lms_norm = [(lm.x, lm.y, getattr(lm, "z", 0.0)) for lm in hand_lms]
                        lms_px = [(int(lm.x * w), int(lm.y * h)) for lm in hand_lms]
                        landmarks_list.append(lms_norm)
                        pixel_landmarks_list.append(lms_px)

            elif self._api_type == "solutions":
                results = self._detector.process(rgb_frame)
                if results and results.multi_hand_landmarks:
                    for i, hand_lms in enumerate(results.multi_hand_landmarks):
                        label = "Hand"
                        if results.multi_handedness and i < len(results.multi_handedness):
                            label = results.multi_handedness[i].classification[0].label
                        handedness_list.append(label)

                        lms_norm = [(lm.x, lm.y, lm.z) for lm in hand_lms.landmark]
                        lms_px = [(int(lm.x * w), int(lm.y * h)) for lm in hand_lms.landmark]
                        landmarks_list.append(lms_norm)
                        pixel_landmarks_list.append(lms_px)

        except Exception as exc:
            logger.error("Error during frame hand detection: %s", exc)
            landmarks_list = []
            pixel_landmarks_list = []
            handedness_list = []

        hand_count = len(landmarks_list)
        if hand_count > 0:
            self._consecutive_no_hand_frames = 0
            status_msg, tracking_msg = format_hand_status(hand_count, is_running=True)

            # Phase 3 Gesture Recognition & Visualization
            gesture_results = self._gesture_recognizer.update(landmarks_list, handedness_list)
            primary_gesture = self._gesture_recognizer.current_gesture

            active_gestures_count = 0
            for i in range(hand_count):
                lms_px = pixel_landmarks_list[i]
                label = handedness_list[i] if i < len(handedness_list) else None
                g_name = gesture_results[i].gesture_name if i < len(gesture_results) else primary_gesture

                if g_name in SUPPORTED_GESTURES:
                    active_gestures_count += 1

                self.draw_landmarks(annotated, lms_px, label, gesture_name=g_name)

            return HandDetectionResult(
                detected_hands_count=hand_count,
                landmarks_list=landmarks_list,
                pixel_landmarks_list=pixel_landmarks_list,
                handedness_list=handedness_list,
                annotated_frame=annotated,
                status_message=status_msg,
                tracking_status=tracking_msg,
                current_gesture=primary_gesture,
                gesture_results=gesture_results,
                active_gestures_count=active_gestures_count,
                tracking_confirmed_lost=False,
            )
        else:
            self._consecutive_no_hand_frames += 1
            status_msg, tracking_msg = format_hand_status(0, is_running=True)
            is_confirmed_lost = (self._consecutive_no_hand_frames >= self.grace_period_frames)
            if is_confirmed_lost:
                self._gesture_recognizer.reset()
                primary_gesture = GESTURE_NONE
            else:
                # During grace period, hold gesture prediction for short transient jitter
                primary_gesture = self._gesture_recognizer.current_gesture

            return HandDetectionResult(
                detected_hands_count=0,
                landmarks_list=[],
                pixel_landmarks_list=[],
                handedness_list=[],
                annotated_frame=annotated,
                status_message=status_msg,
                tracking_status=tracking_msg,
                current_gesture=primary_gesture,
                gesture_results=[],
                active_gestures_count=0,
                tracking_confirmed_lost=is_confirmed_lost,
            )

    def draw_landmarks(
        self,
        image: np.ndarray,
        pixel_landmarks: List[Tuple[int, int]],
        handedness: Optional[str] = None,
        gesture_name: Optional[str] = None,
    ) -> None:
        """
        Draw high-contrast, modern aesthetic hand landmarks, joints, and gesture label badge.
        
        Args:
            image: BGR frame to modify in-place.
            pixel_landmarks: List of 21 (x, y) coordinates.
            handedness: Optional string ('Left' or 'Right').
            gesture_name: Optional recognized gesture label.
        """
        if len(pixel_landmarks) < 21:
            return

        # 1. Draw connection bones
        for start_idx, end_idx in HAND_CONNECTIONS:
            pt1 = pixel_landmarks[start_idx]
            pt2 = pixel_landmarks[end_idx]
            cv2.line(
                image,
                pt1,
                pt2,
                color=COLOR_BONE_BGR,
                thickness=THICKNESS_BONE,
                lineType=cv2.LINE_AA,
            )

        # 2. Draw standard finger joints
        for idx, (px, py) in enumerate(pixel_landmarks):
            if idx in FINGERTIP_INDICES:
                # Fingertip glow highlight: outer circle + inner bright dot
                cv2.circle(image, (px, py), RADIUS_FINGERTIP, COLOR_FINGERTIP_BGR, -1, lineType=cv2.LINE_AA)
                cv2.circle(image, (px, py), 2, (255, 255, 255), -1, lineType=cv2.LINE_AA)
            elif idx == 0:
                # Wrist anchor: distinct white ring
                cv2.circle(image, (px, py), RADIUS_WRIST, COLOR_WRIST_BGR, -1, lineType=cv2.LINE_AA)
                cv2.circle(image, (px, py), RADIUS_WRIST + 2, COLOR_BONE_BGR, 1, lineType=cv2.LINE_AA)
            else:
                # Standard knuckle joint
                cv2.circle(image, (px, py), RADIUS_JOINT, COLOR_JOINT_BGR, -1, lineType=cv2.LINE_AA)
                cv2.circle(image, (px, py), 1, (255, 255, 255), -1, lineType=cv2.LINE_AA)

        # 3. Draw gesture badge near wrist
        wrist_x, wrist_y = pixel_landmarks[0]
        if gesture_name and gesture_name in SUPPORTED_GESTURES:
            badge_text = f"{handedness}: {gesture_name}" if handedness else gesture_name
            border_color = (81, 185, 16)  # Emerald green (BGR for #10B981)
            text_color = (255, 255, 255)
        elif gesture_name == GESTURE_UNKNOWN:
            badge_text = f"{handedness}: Unknown" if handedness else "Unknown Gesture"
            border_color = (11, 158, 245)  # Amber gold (BGR for #F59E0B)
            text_color = (200, 200, 200)
        elif handedness:
            badge_text = f"{handedness} Hand"
            border_color = COLOR_BONE_BGR
            text_color = (248, 189, 56)
        else:
            return

        label_pos = (max(10, wrist_x - 45), max(24, wrist_y + 26))
        (txt_w, txt_h), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)

        # Background pill with dark navy fill and colored border
        cv2.rectangle(
            image,
            (label_pos[0] - 6, label_pos[1] - txt_h - 5),
            (label_pos[0] + txt_w + 6, label_pos[1] + 5),
            (14, 24, 47),  # Dark navy pill
            -1,
        )
        cv2.rectangle(
            image,
            (label_pos[0] - 6, label_pos[1] - txt_h - 5),
            (label_pos[0] + txt_w + 6, label_pos[1] + 5),
            border_color,
            1,
        )
        cv2.putText(
            image,
            badge_text,
            label_pos,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            text_color,
            1,
            cv2.LINE_AA,
        )

    def close(self) -> None:
        """Release MediaPipe resources safely."""
        self._consecutive_no_hand_frames = 0
        self._gesture_recognizer.reset()
        if self._detector is not None:
            try:
                self._detector.close()
                logger.info("MediaPipe HandDetector closed successfully.")
            except Exception as exc:
                logger.warning("Error releasing MediaPipe detector: %s", exc)
            finally:
                self._detector = None
                self._is_initialized = False
