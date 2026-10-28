"""
app/gesture_recognizer.py
Rule-based hand gesture recognition engine using normalized landmark geometry.

Identifies finger extension states, palm orientations, and classifies poses into
9 standardized gestures with temporal smoothing and debouncing.
"""

import collections
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.config import (
    GESTURE_COOLDOWN_SEC,
    GESTURE_FIST,
    GESTURE_FIVE_FINGERS,
    GESTURE_FOUR_FINGERS,
    GESTURE_HISTORY_LENGTH,
    GESTURE_MIN_CONSISTENT,
    GESTURE_NONE,
    GESTURE_ONE_FINGER,
    GESTURE_OPEN_PALM,
    GESTURE_PEACE,
    GESTURE_THREE_FINGERS,
    GESTURE_THUMBS_UP,
    GESTURE_TWO_FINGERS,
    GESTURE_UNKNOWN,
    OPEN_PALM_SPREAD_RATIO,
    PEACE_SPREAD_RATIO,
    SUPPORTED_GESTURES,
)

logger = logging.getLogger(__name__)


def dist_2d(p1: Tuple[float, float, ...], p2: Tuple[float, float, ...]) -> float:
    """Calculate Euclidean distance between two points in normalized 2D space."""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


@dataclass
class GestureResult:
    """Structured classification result for a single hand gesture."""

    gesture_name: str = GESTURE_NONE
    hand_label: Optional[str] = None
    finger_states: Dict[str, bool] = field(default_factory=dict)
    confidence: Optional[float] = None
    raw_gesture: str = GESTURE_NONE
    is_valid: bool = False


class GestureRecognizer:
    """
    Geometric rule-based gesture recognizer with temporal majority-vote smoothing.
    
    Processes normalized 3D landmarks produced by MediaPipe, invariant to frame
    resolution, distance from camera, and user hand size.
    """

    def __init__(
        self,
        history_length: int = GESTURE_HISTORY_LENGTH,
        min_consistent_predictions: int = GESTURE_MIN_CONSISTENT,
        cooldown_sec: float = GESTURE_COOLDOWN_SEC,
    ) -> None:
        self.history_length: int = max(1, history_length)
        self.min_consistent: int = max(1, min_consistent_predictions)
        self.cooldown_sec: float = max(0.0, cooldown_sec)

        # Temporal smoothing buffers (keyed by hand label: "Right", "Left", or "Primary")
        self._prediction_history: collections.deque = collections.deque(maxlen=self.history_length)
        self._current_stable_gesture: str = GESTURE_NONE
        self._last_gesture_change_time: float = 0.0

    def reset(self) -> None:
        """Reset temporal smoothing history and state upon tracking loss or camera stop."""
        self._prediction_history.clear()
        self._current_stable_gesture = GESTURE_NONE
        self._last_gesture_change_time = 0.0

    def configure(
        self,
        history_length: Optional[int] = None,
        min_consistent: Optional[int] = None,
        cooldown_sec: Optional[float] = None,
    ) -> None:
        """Dynamically reconfigure smoothing parameters without restarting the camera."""
        if history_length is not None:
            self.history_length = max(1, int(history_length))
            old_items = list(self._prediction_history)
            self._prediction_history = collections.deque(old_items, maxlen=self.history_length)
        if min_consistent is not None:
            self.min_consistent = max(1, min(self.history_length, int(min_consistent)))
        if cooldown_sec is not None:
            self.cooldown_sec = max(0.0, float(cooldown_sec))


    def classify_fingers(
        self,
        landmarks: List[Tuple[float, float, float]],
        handedness: Optional[str] = None,
    ) -> Dict[str, bool]:
        """
        Determine boolean extension states for all 5 fingers based on landmark geometry.
        
        Args:
            landmarks: List of 21 (x, y, z) normalized landmarks.
            handedness: Optional 'Left' or 'Right'.
            
        Returns:
            Dictionary mapping finger names ('thumb', 'index', 'middle', 'ring', 'pinky') to bool.
        """
        if len(landmarks) < 21:
            return {"thumb": False, "index": False, "middle": False, "ring": False, "pinky": False}

        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        palm_ref = dist_2d(wrist, middle_mcp)

        if palm_ref < 1e-4:
            return {"thumb": False, "index": False, "middle": False, "ring": False, "pinky": False}

        # 4 Standard Fingers: tip, pip, mcp indices
        finger_configs = [
            ("index", 8, 6, 5),
            ("middle", 12, 10, 9),
            ("ring", 16, 14, 13),
            ("pinky", 20, 18, 17),
        ]

        states: Dict[str, bool] = {}
        for name, tip_idx, pip_idx, mcp_idx in finger_configs:
            tip = landmarks[tip_idx]
            pip = landmarks[pip_idx]
            mcp = landmarks[mcp_idx]

            # Extended condition: tip is farther from wrist than PIP joint
            # and tip is farther from MCP base than PIP joint
            d_tip_wrist = dist_2d(tip, wrist)
            d_pip_wrist = dist_2d(pip, wrist)
            d_tip_mcp = dist_2d(tip, mcp)
            d_pip_mcp = dist_2d(pip, mcp)

            is_extended = (d_tip_wrist > d_pip_wrist * 1.05) and (d_tip_mcp > d_pip_mcp * 1.1)
            states[name] = bool(is_extended)

        # Thumb Extension Analysis:
        # Landmarks: 1: CMC, 2: MCP, 3: IP, 4: TIP
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        thumb_mcp = landmarks[2]
        pinky_mcp = landmarks[17]

        # In both left and right hands, pinky base (17) is on the opposite side of palm
        d_thumb_pinky = dist_2d(thumb_tip, pinky_mcp)
        d_ip_pinky = dist_2d(thumb_ip, pinky_mcp)
        d_thumb_wrist = dist_2d(thumb_tip, wrist)
        d_mcp_wrist = dist_2d(thumb_mcp, wrist)

        thumb_extended = (d_thumb_pinky > d_ip_pinky * 1.1) and (d_thumb_wrist > d_mcp_wrist * 1.05)
        states["thumb"] = bool(thumb_extended)

        return states

    def _is_thumbs_up(
        self,
        landmarks: List[Tuple[float, float, float]],
        finger_states: Dict[str, bool],
        palm_ref: float,
    ) -> bool:
        """
        Verify if the hand posture corresponds to a valid Thumbs Up gesture.
        
        Requires:
        - Thumb extended.
        - Other 4 fingers curled.
        - Thumb tip strictly pointing upwards relative to IP, MCP, and wrist.
        """
        if not finger_states.get("thumb", False):
            return False

        # Other 4 fingers must all be curled
        if any(finger_states[k] for k in ("index", "middle", "ring", "pinky")):
            return False

        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        thumb_mcp = landmarks[2]
        wrist = landmarks[0]

        # In image coordinates, y increases downward; thumb tip must have smaller y (higher in image)
        is_pointing_up = (
            thumb_tip[1] < thumb_ip[1]
            and thumb_tip[1] < thumb_mcp[1]
            and thumb_tip[1] < wrist[1] - 0.2 * palm_ref
        )

        # Vertical orientation check: delta y should dominate delta x
        dy = abs(thumb_tip[1] - thumb_mcp[1])
        dx = abs(thumb_tip[0] - thumb_mcp[0])
        is_vertical = dy > dx * 0.7

        return is_pointing_up and is_vertical

    def classify_hand(
        self,
        landmarks: List[Tuple[float, float, float]],
        handedness: Optional[str] = None,
    ) -> GestureResult:
        """
        Classify raw gesture from normalized 21 hand landmarks without temporal smoothing.
        
        Args:
            landmarks: 21 normalized landmarks (x, y, z).
            handedness: Optional hand side ('Right' or 'Left').
            
        Returns:
            GestureResult with raw gesture name, finger states, and validity.
        """
        if len(landmarks) < 21:
            return GestureResult(gesture_name=GESTURE_NONE, is_valid=False)

        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        palm_ref = dist_2d(wrist, middle_mcp)

        if palm_ref < 1e-4:
            return GestureResult(gesture_name=GESTURE_UNKNOWN, is_valid=False)

        finger_states = self.classify_fingers(landmarks, handedness)
        extended_count = sum(1 for v in finger_states.values() if v)

        # -------------------------------------------------------------------
        # Rule Evaluation Hierarchy
        # -------------------------------------------------------------------
        raw_gesture = GESTURE_UNKNOWN

        # 1. Thumbs Up
        if self._is_thumbs_up(landmarks, finger_states, palm_ref):
            raw_gesture = GESTURE_THUMBS_UP

        # 2. Fist: all 5 fingers curled
        elif extended_count == 0:
            # Confirm finger tips are contracted close to wrist
            mid_tip = landmarks[12]
            if dist_2d(mid_tip, wrist) < palm_ref * 1.35:
                raw_gesture = GESTURE_FIST
            else:
                raw_gesture = GESTURE_UNKNOWN

        # 3. One Finger: only Index extended
        elif (
            finger_states["index"]
            and not finger_states["middle"]
            and not finger_states["ring"]
            and not finger_states["pinky"]
            and not finger_states["thumb"]
        ):
            raw_gesture = GESTURE_ONE_FINGER

        # 4. Peace Sign vs Two Fingers (Index & Middle extended, Ring & Pinky curled)
        elif (
            finger_states["index"]
            and finger_states["middle"]
            and not finger_states["ring"]
            and not finger_states["pinky"]
            and not finger_states["thumb"]
        ):
            # Check separation between Index Tip (8) and Middle Tip (12)
            d_index_middle = dist_2d(landmarks[8], landmarks[12])
            spread_ratio = d_index_middle / palm_ref

            if spread_ratio >= PEACE_SPREAD_RATIO:
                raw_gesture = GESTURE_PEACE  # Prioritize specific V-shape
            else:
                raw_gesture = GESTURE_TWO_FINGERS

        # 5. Three Fingers: Index, Middle, Ring extended
        elif (
            finger_states["index"]
            and finger_states["middle"]
            and finger_states["ring"]
            and not finger_states["pinky"]
            and not finger_states["thumb"]
        ):
            raw_gesture = GESTURE_THREE_FINGERS

        # 6. Four Fingers: 4 main fingers extended, Thumb curled across palm
        elif (
            finger_states["index"]
            and finger_states["middle"]
            and finger_states["ring"]
            and finger_states["pinky"]
            and not finger_states["thumb"]
        ):
            raw_gesture = GESTURE_FOUR_FINGERS

        # 7. Five Fingers vs Open Palm: all 5 fingers extended
        elif extended_count == 5:
            # Check spread between Thumb Tip (4) and Pinky Tip (20)
            d_thumb_pinky = dist_2d(landmarks[4], landmarks[20])
            d_index_pinky = dist_2d(landmarks[8], landmarks[20])
            spread_ratio = d_thumb_pinky / palm_ref

            if spread_ratio >= OPEN_PALM_SPREAD_RATIO and (d_index_pinky / palm_ref) > 0.5:
                raw_gesture = GESTURE_OPEN_PALM
            else:
                raw_gesture = GESTURE_FIVE_FINGERS

        else:
            raw_gesture = GESTURE_UNKNOWN

        return GestureResult(
            gesture_name=raw_gesture,
            hand_label=handedness,
            finger_states=finger_states,
            raw_gesture=raw_gesture,
            is_valid=(raw_gesture in SUPPORTED_GESTURES),
        )

    def update(
        self,
        landmarks_list: List[List[Tuple[float, float, float]]],
        handedness_list: Optional[List[str]] = None,
    ) -> List[GestureResult]:
        """
        Process current frame landmarks across all detected hands and apply temporal smoothing.
        
        Args:
            landmarks_list: List of 21-landmark lists for each detected hand.
            handedness_list: List of handedness labels ('Right', 'Left').
            
        Returns:
            List of GestureResult for each hand, with the primary hand stabilized.
        """
        if not landmarks_list:
            self.reset()
            return []

        handedness_list = handedness_list or []
        results: List[GestureResult] = []

        for idx, landmarks in enumerate(landmarks_list):
            h_label = handedness_list[idx] if idx < len(handedness_list) else None
            raw_res = self.classify_hand(landmarks, h_label)
            results.append(raw_res)

        # Primary hand smoothing (focus on first detected hand)
        primary_res = results[0]
        self._prediction_history.append(primary_res.raw_gesture)

        # Majority voting across prediction history
        counts = collections.Counter(self._prediction_history)
        most_common_gesture, freq = counts.most_common(1)[0]

        now = time.time()
        if freq >= self.min_consistent:
            if most_common_gesture != self._current_stable_gesture:
                # Cooldown check
                if (now - self._last_gesture_change_time) >= self.cooldown_sec:
                    self._current_stable_gesture = most_common_gesture
                    self._last_gesture_change_time = now
        else:
            # Fall back to Unknown if previous stable gesture is no longer present in history
            if counts.get(self._current_stable_gesture, 0) == 0:
                self._current_stable_gesture = GESTURE_UNKNOWN
            elif self._current_stable_gesture == GESTURE_NONE:
                self._current_stable_gesture = GESTURE_UNKNOWN

        # Assign smoothed gesture name to primary result
        primary_res.gesture_name = self._current_stable_gesture
        primary_res.is_valid = (self._current_stable_gesture in SUPPORTED_GESTURES)

        return results

    @property
    def current_gesture(self) -> str:
        """Return the current temporally smoothed gesture name."""
        return self._current_stable_gesture
