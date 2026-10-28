"""
app/control_manager.py
Modular Gesture-to-Action Control Manager for Hand Gesture Controller.

Phase 4: Maps recognized hand gestures to macOS system actions (Media, Volume, Virtual Mouse)
with explicit safety gates, cooldown debouncing, edge-triggering, and mockable adapters.
"""

from abc import ABC, abstractmethod
import ctypes
from dataclasses import dataclass, field
import logging
import os
import subprocess
import time
from typing import Callable, Dict, List, Optional, Tuple

from app.config import (
    ACTION_COOLDOWN_SEC,
    ACTION_MUTE,
    ACTION_NEXT_TRACK,
    ACTION_NONE,
    ACTION_PLAY_PAUSE,
    ACTION_PREV_TRACK,
    ACTION_VOLUME_PINCH,
    CONTROLS_ENABLED_DEFAULT,
    DEFAULT_GESTURE_ACTIONS,
    GESTURE_NONE,
    GESTURE_UNKNOWN,
    MOUSE_ACTIVE_MARGIN_X,
    MOUSE_ACTIVE_MARGIN_Y,
    MOUSE_CLICK_COOLDOWN_SEC,
    MOUSE_CLICK_THRESHOLD_RATIO,
    MOUSE_ENABLED_DEFAULT,
    MOUSE_RELEASE_THRESHOLD_RATIO,
    MOUSE_SMOOTHING_ALPHA,
    SUPPORTED_ACTIONS,
    VOLUME_CHANGE_THRESHOLD,
    VOLUME_PINCH_MAX_RATIO,
    VOLUME_PINCH_MIN_RATIO,
    VOLUME_SMOOTHING_ALPHA,
    VOLUME_UPDATE_INTERVAL_SEC,
)
from app.gesture_recognizer import dist_2d

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured Action Result
# ---------------------------------------------------------------------------
@dataclass
class SystemActionResult:
    """Structured result of an executed or attempted system action."""

    action_type: str
    success: bool
    message: str
    timestamp: float = field(default_factory=time.time)
    details: Optional[Dict[str, str]] = None


# ---------------------------------------------------------------------------
# System Action Adapter Interface (Mockable)
# ---------------------------------------------------------------------------
class SystemActionAdapter(ABC):
    """
    Abstract interface for executing system-level actions (Media, Volume, Mouse).
    Concrete implementations target macOS or test mock recorders.
    """

    @abstractmethod
    def play_pause(self) -> SystemActionResult:
        """Toggle playback on the active media player."""
        pass

    @abstractmethod
    def next_track(self) -> SystemActionResult:
        """Skip to the next audio track."""
        pass

    @abstractmethod
    def previous_track(self) -> SystemActionResult:
        """Return to the previous audio track."""
        pass

    @abstractmethod
    def get_volume(self) -> Tuple[bool, int]:
        """Query the current macOS output volume (0-100)."""
        pass

    @abstractmethod
    def set_volume(self, volume: int) -> SystemActionResult:
        """Set the macOS output volume (0-100)."""
        pass

    @abstractmethod
    def toggle_mute(self) -> SystemActionResult:
        """Toggle macOS audio mute state."""
        pass

    @abstractmethod
    def move_mouse(self, x: int, y: int) -> SystemActionResult:
        """Move the system cursor to absolute screen coordinates (x, y)."""
        pass

    @abstractmethod
    def mouse_click(self, x: int, y: int) -> SystemActionResult:
        """Perform a left-mouse click at coordinates (x, y)."""
        pass

    @abstractmethod
    def get_screen_size(self) -> Tuple[int, int]:
        """Return primary screen dimensions (width, height)."""
        pass

    @abstractmethod
    def is_accessibility_granted(self) -> bool:
        """Check if macOS Accessibility permission is granted to this process."""
        pass


# ---------------------------------------------------------------------------
# macOS Native Implementation
# ---------------------------------------------------------------------------
class MacOSSystemActionAdapter(SystemActionAdapter):
    """
    macOS adapter using AppleScript via osascript for media/volume and
    CoreGraphics / ApplicationServices for hardware cursor control.
    """

    def __init__(self) -> None:
        self._cg = None
        self._app_services = None
        self._screen_size: Tuple[int, int] = (1280, 800)

        # Attempt to load macOS native frameworks via ctypes
        try:
            self._cg = ctypes.cdll.LoadLibrary(
                "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
            )
            self._app_services = ctypes.cdll.LoadLibrary(
                "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
            )
            self._setup_core_graphics()
        except Exception as exc:
            logger.warning("CoreGraphics/ApplicationServices not available: %s", exc)

    def _setup_core_graphics(self) -> None:
        """Configure C function signatures for CoreGraphics calls."""
        if self._cg is None:
            return

        class CGPoint(ctypes.Structure):
            _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

        class CGSize(ctypes.Structure):
            _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]

        class CGRect(ctypes.Structure):
            _fields_ = [("origin", CGPoint), ("size", CGSize)]

        self._CGPoint = CGPoint
        self._cg.CGMainDisplayID.restype = ctypes.c_uint32
        self._cg.CGDisplayBounds.restype = CGRect
        self._cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]

        self._cg.CGWarpMouseCursorPosition.restype = ctypes.c_int
        self._cg.CGWarpMouseCursorPosition.argtypes = [CGPoint]

        # Query screen size
        try:
            display_id = self._cg.CGMainDisplayID()
            bounds = self._cg.CGDisplayBounds(display_id)
            w, h = int(bounds.size.width), int(bounds.size.height)
            if w > 0 and h > 0:
                self._screen_size = (w, h)
        except Exception as exc:
            logger.debug("Failed to query CoreGraphics screen size: %s", exc)

        if self._app_services is not None:
            try:
                self._app_services.AXIsProcessTrusted.restype = ctypes.c_bool
            except Exception:
                pass

    def is_accessibility_granted(self) -> bool:
        """Check macOS Accessibility permission."""
        if self._app_services is not None:
            try:
                return bool(self._app_services.AXIsProcessTrusted())
            except Exception:
                return False
        return False

    def get_screen_size(self) -> Tuple[int, int]:
        return self._screen_size

    def _run_applescript(self, script: str, action_name: str) -> SystemActionResult:
        """Execute a predefined static AppleScript with osascript."""
        try:
            res = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=1.5,
                check=False,
            )
            output = res.stdout.strip()
            err_output = res.stderr.strip()

            if res.returncode == 0:
                if "Unavailable:" in output:
                    return SystemActionResult(
                        action_type=action_name,
                        success=False,
                        message=output,
                    )
                return SystemActionResult(
                    action_type=action_name,
                    success=True,
                    message=output or f"{action_name} executed successfully",
                )
            else:
                return SystemActionResult(
                    action_type=action_name,
                    success=False,
                    message=f"AppleScript error: {err_output or 'Failed'}",
                )
        except subprocess.TimeoutExpired:
            return SystemActionResult(
                action_type=action_name,
                success=False,
                message="AppleScript command timed out after 1.5s",
            )
        except Exception as exc:
            return SystemActionResult(
                action_type=action_name,
                success=False,
                message=f"Execution error: {exc}",
            )

    def play_pause(self) -> SystemActionResult:
        script = """
        try
            if application "Music" is running then
                tell application "Music" to playpause
                return "Music: Play/Pause toggled"
            else if application "Spotify" is running then
                tell application "Spotify" to playpause
                return "Spotify: Play/Pause toggled"
            else
                return "Unavailable: Neither Music nor Spotify is running"
            end if
        on error errMsg
            return "Unavailable: " & errMsg
        end try
        """
        return self._run_applescript(script, ACTION_PLAY_PAUSE)

    def next_track(self) -> SystemActionResult:
        script = """
        try
            if application "Music" is running then
                tell application "Music" to next track
                return "Music: Next Track"
            else if application "Spotify" is running then
                tell application "Spotify" to next track
                return "Spotify: Next Track"
            else
                return "Unavailable: Neither Music nor Spotify is running"
            end if
        on error errMsg
            return "Unavailable: " & errMsg
        end try
        """
        return self._run_applescript(script, ACTION_NEXT_TRACK)

    def previous_track(self) -> SystemActionResult:
        script = """
        try
            if application "Music" is running then
                tell application "Music" to previous track
                return "Music: Previous Track"
            else if application "Spotify" is running then
                tell application "Spotify" to previous track
                return "Spotify: Previous Track"
            else
                return "Unavailable: Neither Music nor Spotify is running"
            end if
        on error errMsg
            return "Unavailable: " & errMsg
        end try
        """
        return self._run_applescript(script, ACTION_PREV_TRACK)

    def get_volume(self) -> Tuple[bool, int]:
        script = """
        try
            return output volume of (get volume settings) as string
        on error
            return "Error"
        end try
        """
        try:
            res = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
            if res.returncode == 0:
                raw = res.stdout.strip()
                if raw.isdigit():
                    return True, int(raw)
        except Exception:
            pass
        return False, 50

    def set_volume(self, volume: int) -> SystemActionResult:
        vol = max(0, min(100, int(volume)))
        script = f"""
        try
            set volume output volume {vol}
            return "Volume set to {vol}%"
        on error errMsg
            return "Error: " & errMsg
        end try
        """
        return self._run_applescript(script, f"Volume {vol}%")

    def toggle_mute(self) -> SystemActionResult:
        script = """
        try
            set curMute to output muted of (get volume settings)
            set volume output muted (not curMute)
            if not curMute then
                return "Audio Muted"
            else
                return "Audio Unmuted"
            end if
        on error errMsg
            return "Error: " & errMsg
        end try
        """
        return self._run_applescript(script, ACTION_MUTE)

    def move_mouse(self, x: int, y: int) -> SystemActionResult:
        if self._cg is None:
            return SystemActionResult(
                action_type="Mouse Move",
                success=False,
                message="CoreGraphics library not available on this platform",
            )
        try:
            pt = self._CGPoint(x=float(x), y=float(y))
            res = self._cg.CGWarpMouseCursorPosition(pt)
            if res == 0:
                return SystemActionResult(
                    action_type="Mouse Move",
                    success=True,
                    message=f"Cursor moved to ({x}, {y})",
                )
            return SystemActionResult(
                action_type="Mouse Move",
                success=False,
                message=f"CGWarp returned status {res}",
            )
        except Exception as exc:
            return SystemActionResult(
                action_type="Mouse Move",
                success=False,
                message=f"Mouse move error: {exc}",
            )

    def mouse_click(self, x: int, y: int) -> SystemActionResult:
        if self._cg is None:
            return SystemActionResult(
                action_type="Mouse Click",
                success=False,
                message="CoreGraphics not available",
            )
        if not self.is_accessibility_granted():
            return SystemActionResult(
                action_type="Mouse Click",
                success=False,
                message="Accessibility permission required in macOS System Settings > Privacy & Security > Accessibility",
            )

        try:
            pt = self._CGPoint(x=float(x), y=float(y))
            # Constants from CGEventTypes.h
            kCGEventLeftMouseDown = 1
            kCGEventLeftMouseUp = 2
            kCGMouseButtonLeft = 0
            kCGHIDEventTap = 0

            down = self._cg.CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, pt, kCGMouseButtonLeft)
            up = self._cg.CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, pt, kCGMouseButtonLeft)

            self._cg.CGEventPost(kCGHIDEventTap, down)
            self._cg.CGEventPost(kCGHIDEventTap, up)

            self._cg.CFRelease(down)
            self._cg.CFRelease(up)

            return SystemActionResult(
                action_type="Mouse Click",
                success=True,
                message=f"Left click at ({x}, {y})",
            )
        except Exception as exc:
            return SystemActionResult(
                action_type="Mouse Click",
                success=False,
                message=f"Mouse click error: {exc}",
            )


# ---------------------------------------------------------------------------
# Mock Adapter for Camera-Independent Automated Tests
# ---------------------------------------------------------------------------
class MockSystemActionAdapter(SystemActionAdapter):
    """
    In-memory mock recorder for testing. Does not invoke shell or alter OS hardware.
    """

    def __init__(self, accessibility_granted: bool = True) -> None:
        self.accessibility_granted: bool = accessibility_granted
        self.current_volume: int = 50
        self.is_muted: bool = False
        self.mouse_position: Tuple[int, int] = (0, 0)
        self.screen_size: Tuple[int, int] = (1920, 1080)
        self.actions_history: List[SystemActionResult] = []
        self.click_history: List[Tuple[int, int]] = []

    def is_accessibility_granted(self) -> bool:
        return self.accessibility_granted

    def get_screen_size(self) -> Tuple[int, int]:
        return self.screen_size

    def play_pause(self) -> SystemActionResult:
        res = SystemActionResult(action_type=ACTION_PLAY_PAUSE, success=True, message="Mock: Play/Pause toggled")
        self.actions_history.append(res)
        return res

    def next_track(self) -> SystemActionResult:
        res = SystemActionResult(action_type=ACTION_NEXT_TRACK, success=True, message="Mock: Next track")
        self.actions_history.append(res)
        return res

    def previous_track(self) -> SystemActionResult:
        res = SystemActionResult(action_type=ACTION_PREV_TRACK, success=True, message="Mock: Previous track")
        self.actions_history.append(res)
        return res

    def get_volume(self) -> Tuple[bool, int]:
        return True, self.current_volume

    def set_volume(self, volume: int) -> SystemActionResult:
        self.current_volume = max(0, min(100, int(volume)))
        res = SystemActionResult(
            action_type=f"Volume {self.current_volume}%",
            success=True,
            message=f"Mock: Volume set to {self.current_volume}%",
        )
        self.actions_history.append(res)
        return res

    def toggle_mute(self) -> SystemActionResult:
        self.is_muted = not self.is_muted
        state = "Muted" if self.is_muted else "Unmuted"
        res = SystemActionResult(action_type=ACTION_MUTE, success=True, message=f"Mock: {state}")
        self.actions_history.append(res)
        return res

    def move_mouse(self, x: int, y: int) -> SystemActionResult:
        self.mouse_position = (x, y)
        res = SystemActionResult(action_type="Mouse Move", success=True, message=f"Mock: Cursor moved to ({x}, {y})")
        self.actions_history.append(res)
        return res

    def mouse_click(self, x: int, y: int) -> SystemActionResult:
        if not self.accessibility_granted:
            res = SystemActionResult(
                action_type="Mouse Click",
                success=False,
                message="Mock: Accessibility permission required",
            )
            self.actions_history.append(res)
            return res

        self.mouse_position = (x, y)
        self.click_history.append((x, y))
        res = SystemActionResult(action_type="Mouse Click", success=True, message=f"Mock: Click at ({x}, {y})")
        self.actions_history.append(res)
        return res


# ---------------------------------------------------------------------------
# Gesture Control Manager
# ---------------------------------------------------------------------------
class ControlManager:
    """
    Coordinates gesture-to-action dispatching, safety gates, cooldowns,
    continuous volume pinch, and virtual mouse automation.
    """

    def __init__(
        self,
        adapter: Optional[SystemActionAdapter] = None,
        gesture_action_map: Optional[Dict[str, str]] = None,
        action_cooldown_sec: float = ACTION_COOLDOWN_SEC,
        statistics_manager: Optional[Any] = None,
    ) -> None:
        self._adapter: SystemActionAdapter = adapter if adapter is not None else MacOSSystemActionAdapter()
        self._controls_enabled: bool = CONTROLS_ENABLED_DEFAULT
        self._mouse_enabled: bool = MOUSE_ENABLED_DEFAULT
        self.action_cooldown_sec: float = action_cooldown_sec
        self._action_cooldown_sec: float = action_cooldown_sec
        self.volume_change_threshold: int = VOLUME_CHANGE_THRESHOLD
        self.volume_update_interval_sec: float = VOLUME_UPDATE_INTERVAL_SEC
        self.volume_smoothing_alpha: float = VOLUME_SMOOTHING_ALPHA
        self.mouse_smoothing_alpha: float = MOUSE_SMOOTHING_ALPHA
        self.mouse_click_threshold_ratio: float = MOUSE_CLICK_THRESHOLD_RATIO
        self.mouse_release_threshold_ratio: float = MOUSE_RELEASE_THRESHOLD_RATIO
        self.mouse_click_cooldown_sec: float = MOUSE_CLICK_COOLDOWN_SEC
        self.statistics_manager: Optional[Any] = statistics_manager

        # Validate and apply gesture-action mapping
        self._gesture_action_map: Dict[str, str] = {}
        initial_map = gesture_action_map if gesture_action_map is not None else DEFAULT_GESTURE_ACTIONS
        self.set_gesture_action_map(initial_map)

        # Discrete action state tracking
        self._last_triggered_gesture: Optional[str] = None
        self._last_blocked_gesture: Optional[str] = None
        self._last_action_time: float = 0.0
        self._last_action_result: Optional[SystemActionResult] = None
        self._status_feedback: str = "Controls Disabled (Safe Mode)"

        # Continuous volume tracking
        self._last_committed_volume: int = -1
        self._smoothed_volume: float = 50.0
        self._last_volume_time: float = 0.0

        # Virtual mouse tracking
        self._last_mouse_x: float = float(self._adapter.get_screen_size()[0] // 2)
        self._last_mouse_y: float = float(self._adapter.get_screen_size()[1] // 2)
        self._is_pinched: bool = False
        self._last_click_time: float = 0.0

    def set_statistics_manager(self, statistics_manager: Optional[Any]) -> None:
        """Attach or update the statistics manager for action analytics tracking."""
        self.statistics_manager = statistics_manager

    # -----------------------------------------------------------------------
    # Configuration and Properties
    # -----------------------------------------------------------------------
    @property
    def controls_enabled(self) -> bool:
        return self._controls_enabled

    @property
    def mouse_enabled(self) -> bool:
        return self._mouse_enabled

    @property
    def status_feedback(self) -> str:
        return self._status_feedback

    @property
    def last_action_result(self) -> Optional[SystemActionResult]:
        return self._last_action_result

    @property
    def gesture_action_map(self) -> Dict[str, str]:
        return dict(self._gesture_action_map)

    def set_gesture_action_map(self, action_map: Dict[str, str]) -> None:
        """Validate and update gesture-to-action mappings."""
        validated: Dict[str, str] = {}
        for gesture, action in action_map.items():
            if action not in SUPPORTED_ACTIONS:
                logger.warning("Unrecognized action '%s' for gesture '%s'; ignoring.", action, gesture)
                validated[gesture] = ACTION_NONE
            else:
                validated[gesture] = action
        self._gesture_action_map = validated

    def configure(
        self,
        gesture_action_map: Optional[Dict[str, str]] = None,
        action_cooldown_sec: Optional[float] = None,
        volume_change_threshold: Optional[int] = None,
        volume_update_interval_sec: Optional[float] = None,
        volume_smoothing_alpha: Optional[float] = None,
        mouse_smoothing_alpha: Optional[float] = None,
        mouse_click_threshold_ratio: Optional[float] = None,
        mouse_release_threshold_ratio: Optional[float] = None,
        mouse_click_cooldown_sec: Optional[float] = None,
    ) -> None:
        """Dynamically reconfigure action mappings, sensitivity, and timing parameters."""
        if gesture_action_map is not None:
            self.set_gesture_action_map(gesture_action_map)
        if action_cooldown_sec is not None:
            self.action_cooldown_sec = max(0.05, float(action_cooldown_sec))
            self._action_cooldown_sec = self.action_cooldown_sec
        if volume_change_threshold is not None:
            self.volume_change_threshold = max(1, int(volume_change_threshold))
        if volume_update_interval_sec is not None:
            self.volume_update_interval_sec = max(0.01, float(volume_update_interval_sec))
        if volume_smoothing_alpha is not None:
            self.volume_smoothing_alpha = max(0.01, min(1.0, float(volume_smoothing_alpha)))
        if mouse_smoothing_alpha is not None:
            self.mouse_smoothing_alpha = max(0.01, min(1.0, float(mouse_smoothing_alpha)))
        if mouse_click_threshold_ratio is not None:
            self.mouse_click_threshold_ratio = max(0.05, min(0.60, float(mouse_click_threshold_ratio)))
        if mouse_release_threshold_ratio is not None:
            self.mouse_release_threshold_ratio = max(
                self.mouse_click_threshold_ratio + 0.02,
                min(0.80, float(mouse_release_threshold_ratio)),
            )
        if mouse_click_cooldown_sec is not None:
            self.mouse_click_cooldown_sec = max(0.05, float(mouse_click_cooldown_sec))

    def enable_controls(self, enable: bool) -> None:
        """Enable or disable gesture-based system controls."""
        self._controls_enabled = bool(enable)
        if not self._controls_enabled:
            self.reset_continuous_states()
            self._status_feedback = "Controls Disabled (Safe Mode)"
        else:
            self._status_feedback = "System Controls: Active"
        logger.info("Gesture Controls enabled set to: %s", self._controls_enabled)

    def enable_mouse(self, enable: bool) -> None:
        """Enable or disable virtual mouse cursor tracking."""
        self._mouse_enabled = bool(enable)
        if not self._mouse_enabled:
            self._is_pinched = False
            if self._controls_enabled:
                self._status_feedback = "System Controls: Active (Mouse Off)"
        else:
            if not self._adapter.is_accessibility_granted():
                self._status_feedback = "⚠️ Accessibility Permission Needed for Clicks"
            else:
                self._status_feedback = "Virtual Mouse: Active"
        logger.info("Virtual Mouse enabled set to: %s", self._mouse_enabled)

    def emergency_stop(self) -> None:
        """Immediately disable all system controls and reset continuous states."""
        self._controls_enabled = False
        self._mouse_enabled = False
        self.reset_continuous_states()
        self._status_feedback = "🛑 Emergency Stop Triggered — Controls Disabled"
        logger.warning("Emergency stop called: all controls disabled.")

    def reset_continuous_states(self) -> None:
        """Reset pinch, debounce, and edge-triggering locks."""
        self._last_triggered_gesture = None
        self._last_blocked_gesture = None
        self._is_pinched = False

    # -----------------------------------------------------------------------
    # Frame Processing Pipeline
    # -----------------------------------------------------------------------
    def process_frame(
        self,
        is_camera_running: bool,
        detected_hands_count: int,
        current_gesture: str,
        landmarks: Optional[List[Tuple[float, float, float]]] = None,
    ) -> Optional[SystemActionResult]:
        """
        Evaluate current perception state and dispatch system actions if eligible.

        Safety gates:
        1. Controls must be enabled.
        2. Camera must be actively running.
        3. Hand tracking must be active (count > 0).
        4. Gesture must not be unknown, none, or empty.
        5. Discrete actions require edge-triggered transition and cooldown.
        """
        # Safety Gate 1: Controls Disabled
        if not self._controls_enabled:
            if is_camera_running and detected_hands_count > 0 and landmarks and len(landmarks) >= 21:
                if current_gesture not in (GESTURE_UNKNOWN, GESTURE_NONE, ""):
                    action_name = self._gesture_action_map.get(current_gesture, ACTION_NONE)
                    if action_name != ACTION_NONE and current_gesture != self._last_blocked_gesture:
                        self._last_blocked_gesture = current_gesture
                        if self.statistics_manager is not None:
                            self.statistics_manager.record_action(action_name, success=False, blocked=True)
                else:
                    self._last_blocked_gesture = None
            return None

        # Safety Gate 2: Camera Offline or Tracking Lost
        if not is_camera_running or detected_hands_count == 0 or not landmarks or len(landmarks) < 21:
            self.reset_continuous_states()
            return None

        # Safety Gate 3: Ambiguous or Unrecognized Pose
        if current_gesture in (GESTURE_UNKNOWN, GESTURE_NONE, ""):
            # Re-arm edge trigger when hand returns to unknown / transitional pose
            self._last_triggered_gesture = None
            self._last_blocked_gesture = None
            return None

        now = time.time()
        action_name = self._gesture_action_map.get(current_gesture, ACTION_NONE)

        # -------------------------------------------------------------------
        # 1. Virtual Mouse Control (if enabled)
        # -------------------------------------------------------------------
        if self._mouse_enabled and landmarks and len(landmarks) >= 21:
            self._process_virtual_mouse(landmarks, now)

        # -------------------------------------------------------------------
        # 2. Continuous Volume Pinch
        # -------------------------------------------------------------------
        if action_name == ACTION_VOLUME_PINCH and landmarks and len(landmarks) >= 21:
            return self._process_volume_pinch(landmarks, now)

        # -------------------------------------------------------------------
        # 3. Discrete Actions (Media, Mute, etc.)
        # -------------------------------------------------------------------
        if action_name == ACTION_NONE:
            return None

        # Edge-Triggering Check: Prevent continuous firing while holding gesture
        if current_gesture == self._last_triggered_gesture:
            return None

        # Cooldown Check: Respect minimum time between discrete actions
        if (now - self._last_action_time) < self.action_cooldown_sec:
            self._status_feedback = f"Action '{action_name}' blocked (Cooldown)"
            if current_gesture != self._last_blocked_gesture:
                self._last_blocked_gesture = current_gesture
                if self.statistics_manager is not None:
                    self.statistics_manager.record_action(action_name, success=False, blocked=True)
            return None

        self._last_blocked_gesture = None

        # Execute Discrete Action
        result = self._execute_discrete_action(action_name)
        if result is not None:
            self._last_triggered_gesture = current_gesture
            self._last_action_time = now
            self._last_action_result = result
            if self.statistics_manager is not None:
                self.statistics_manager.record_action(action_name, success=result.success, blocked=False)
            if result.success:
                self._status_feedback = f"Action: {result.message}"
            else:
                self._status_feedback = f"Action Failed: {result.message}"

        return result

    # -----------------------------------------------------------------------
    # Subsystem Helpers
    # -----------------------------------------------------------------------
    def _execute_discrete_action(self, action_name: str) -> Optional[SystemActionResult]:
        """Dispatch action to the system adapter."""
        if action_name == ACTION_PLAY_PAUSE:
            return self._adapter.play_pause()
        elif action_name == ACTION_NEXT_TRACK:
            return self._adapter.next_track()
        elif action_name == ACTION_PREV_TRACK:
            return self._adapter.previous_track()
        elif action_name == ACTION_MUTE:
            return self._adapter.toggle_mute()
        return None

    def _process_volume_pinch(
        self, landmarks: List[Tuple[float, float, float]], now: float
    ) -> Optional[SystemActionResult]:
        """Calculate normalized pinch distance and adjust system volume."""
        # Calculate palm reference scale
        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        palm_ref = dist_2d(wrist, middle_mcp)
        if palm_ref < 1e-4:
            return None

        # Calculate thumb tip (4) to index tip (8) distance
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        pinch_dist = dist_2d(thumb_tip, index_tip)
        norm_pinch = pinch_dist / palm_ref

        # Map normalized pinch to 0-100% volume
        clamped = max(VOLUME_PINCH_MIN_RATIO, min(VOLUME_PINCH_MAX_RATIO, norm_pinch))
        target_pct = ((clamped - VOLUME_PINCH_MIN_RATIO) / (VOLUME_PINCH_MAX_RATIO - VOLUME_PINCH_MIN_RATIO)) * 100.0

        # Apply Exponential Moving Average (EMA) smoothing
        self._smoothed_volume = (
            self.volume_smoothing_alpha * target_pct + (1.0 - self.volume_smoothing_alpha) * self._smoothed_volume
        )
        committed_vol = int(round(self._smoothed_volume))

        # Check rate-limiting and hysteresis (difference >= threshold)
        if (now - self._last_volume_time) >= self.volume_update_interval_sec:
            if abs(committed_vol - self._last_committed_volume) >= self.volume_change_threshold:
                self._last_committed_volume = committed_vol
                self._last_volume_time = now
                res = self._adapter.set_volume(committed_vol)
                self._status_feedback = f"Volume: {committed_vol}%"
                self._last_action_result = res
                if self.statistics_manager is not None:
                    self.statistics_manager.record_action("Continuous Volume", success=res.success, blocked=False)
                return res

        return None

    def _process_virtual_mouse(
        self, landmarks: List[Tuple[float, float, float]], now: float
    ) -> None:
        """Map index fingertip to screen coordinates and handle pinch left-clicks."""
        index_tip = landmarks[8]
        thumb_tip = landmarks[4]
        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        palm_ref = dist_2d(wrist, middle_mcp)

        screen_w, screen_h = self._adapter.get_screen_size()

        # Mirror horizontally so movement aligns naturally with user hand
        norm_x = 1.0 - index_tip[0]
        norm_y = index_tip[1]

        # Active boundary normalization with margins
        margin_x = MOUSE_ACTIVE_MARGIN_X
        margin_y = MOUSE_ACTIVE_MARGIN_Y

        fx = (norm_x - margin_x) / (1.0 - 2.0 * margin_x)
        fy = (norm_y - margin_y) / (1.0 - 2.0 * margin_y)

        clamped_fx = max(0.0, min(1.0, fx))
        clamped_fy = max(0.0, min(1.0, fy))

        target_x = clamped_fx * screen_w
        target_y = clamped_fy * screen_h

        # Exponential moving average smoothing
        smooth_x = self.mouse_smoothing_alpha * target_x + (1.0 - self.mouse_smoothing_alpha) * self._last_mouse_x
        smooth_y = self.mouse_smoothing_alpha * target_y + (1.0 - self.mouse_smoothing_alpha) * self._last_mouse_y

        self._last_mouse_x = smooth_x
        self._last_mouse_y = smooth_y

        cur_x = int(round(smooth_x))
        cur_y = int(round(smooth_y))

        # Move mouse cursor
        self._adapter.move_mouse(cur_x, cur_y)

        # Evaluate Pinch Click
        if palm_ref > 1e-4:
            pinch_dist = dist_2d(thumb_tip, index_tip)
            norm_pinch = pinch_dist / palm_ref

            if norm_pinch < self.mouse_click_threshold_ratio:
                if not self._is_pinched and (now - self._last_click_time) >= self.mouse_click_cooldown_sec:
                    self._is_pinched = True
                    self._last_click_time = now
                    click_res = self._adapter.mouse_click(cur_x, cur_y)
                    self._last_action_result = click_res
                    if self.statistics_manager is not None:
                        is_blocked = not click_res.success and "Accessibility" in click_res.message
                        self.statistics_manager.record_action(
                            "Mouse Click",
                            success=click_res.success,
                            blocked=is_blocked,
                        )
                    if click_res.success:
                        self._status_feedback = f"Virtual Mouse: Click at ({cur_x}, {cur_y})"
                    else:
                        self._status_feedback = click_res.message
            elif norm_pinch > self.mouse_release_threshold_ratio:
                self._is_pinched = False
