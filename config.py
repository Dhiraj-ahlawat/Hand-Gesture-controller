"""
app/config.py
Configuration constants and theme settings for Hand Gesture Controller.

Phase 3 implements real-time hand gesture recognition using landmark geometry,
normalized relative finger distances, and temporal prediction smoothing.
"""

from typing import Dict, Final, Tuple

# ---------------------------------------------------------------------------
# Application Metadata
# ---------------------------------------------------------------------------
APP_TITLE: Final[str] = "Hand Gesture Controller"
APP_SUBTITLE: Final[str] = "Phase 7: Final QA & College Demonstration Edition"
APP_VERSION: Final[str] = "7.0.0"

SETTINGS_DIRNAME: Final[str] = "HandGestureController"
SETTINGS_FILENAME: Final[str] = "settings.json"
HISTORY_FILENAME: Final[str] = "history.db"

# ---------------------------------------------------------------------------
# Window & Layout Dimensions
# ---------------------------------------------------------------------------
WINDOW_WIDTH: Final[int] = 1120
WINDOW_HEIGHT: Final[int] = 780
MIN_WINDOW_WIDTH: Final[int] = 880
MIN_WINDOW_HEIGHT: Final[int] = 600

PREVIEW_DEFAULT_WIDTH: Final[int] = 720
PREVIEW_DEFAULT_HEIGHT: Final[int] = 480
SIDEBAR_WIDTH: Final[int] = 340

# ---------------------------------------------------------------------------
# Camera Configuration
# ---------------------------------------------------------------------------
DEFAULT_CAMERA_INDEX: Final[int] = 0
FRAME_WIDTH: Final[int] = 1280
FRAME_HEIGHT: Final[int] = 720
TARGET_FPS: Final[int] = 30
FRAME_POLL_INTERVAL_MS: Final[int] = 16  # ~60 Hz UI refresh

# ---------------------------------------------------------------------------
# Hand Detection & Tracking Configuration
# ---------------------------------------------------------------------------
MAX_HANDS: Final[int] = 2
MIN_DETECTION_CONFIDENCE: Final[float] = 0.6
MIN_TRACKING_CONFIDENCE: Final[float] = 0.6

MODEL_FILENAME: Final[str] = "hand_landmarker.task"
MODEL_SUBDIR: Final[str] = "models"
MODEL_DOWNLOAD_URL: Final[str] = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
)

# Hand & Tracking Status Labels
STATUS_NO_HAND: Final[str] = "Show your hand to the camera"
STATUS_HAND_DETECTED: Final[str] = "Hand Detected"
STATUS_TRACKING_ACTIVE: Final[str] = "Tracking Active"
STATUS_TRACKING_SCANNING: Final[str] = "Scanning for Hands..."
STATUS_TRACKING_OFFLINE: Final[str] = "Tracking Offline"
STATUS_TRACKING_ERROR: Final[str] = "Tracker Initialization Error"

# Landmark Visualization Styling (BGR format for OpenCV drawing)
COLOR_BONE_BGR: Final[Tuple[int, int, int]] = (199, 132, 2)       # Electric Blue (#0284C7)
COLOR_JOINT_BGR: Final[Tuple[int, int, int]] = (248, 189, 56)     # Cyan Accent (#38BDF8)
COLOR_FINGERTIP_BGR: Final[Tuple[int, int, int]] = (255, 210, 0)  # Bright Highlight (#00D2FF)
COLOR_WRIST_BGR: Final[Tuple[int, int, int]] = (255, 255, 255)    # Clean White (#FFFFFF)

THICKNESS_BONE: Final[int] = 2
RADIUS_JOINT: Final[int] = 4
RADIUS_FINGERTIP: Final[int] = 6
RADIUS_WRIST: Final[int] = 5

# ---------------------------------------------------------------------------
# Gesture Recognition Configuration (Phase 3)
# ---------------------------------------------------------------------------
GESTURE_OPEN_PALM: Final[str] = "Open Palm"
GESTURE_FIST: Final[str] = "Fist"
GESTURE_THUMBS_UP: Final[str] = "Thumbs Up"
GESTURE_PEACE: Final[str] = "Peace Sign"
GESTURE_ONE_FINGER: Final[str] = "One Finger"
GESTURE_TWO_FINGERS: Final[str] = "Two Fingers"
GESTURE_THREE_FINGERS: Final[str] = "Three Fingers"
GESTURE_FOUR_FINGERS: Final[str] = "Four Fingers"
GESTURE_FIVE_FINGERS: Final[str] = "Five Fingers"
GESTURE_UNKNOWN: Final[str] = "Unknown Gesture"
GESTURE_NONE: Final[str] = "Waiting for hand..."

SUPPORTED_GESTURES: Final[Tuple[str, ...]] = (
    GESTURE_OPEN_PALM,
    GESTURE_FIST,
    GESTURE_THUMBS_UP,
    GESTURE_PEACE,
    GESTURE_ONE_FINGER,
    GESTURE_TWO_FINGERS,
    GESTURE_THREE_FINGERS,
    GESTURE_FOUR_FINGERS,
    GESTURE_FIVE_FINGERS,
)

# Temporal Smoothing & Stabilization Settings
GESTURE_HISTORY_LENGTH: Final[int] = 7       # Number of consecutive frames evaluated
GESTURE_MIN_CONSISTENT: Final[int] = 4       # Minimum agreement count to change gesture
GESTURE_COOLDOWN_SEC: Final[float] = 0.5     # Debounce period for gesture state transitions

# Tracking Loss Grace Period (Phase 8)
# Short, bounded frame count to absorb transient detection dropouts before confirming hand loss
TRACKING_LOSS_GRACE_FRAMES: Final[int] = 5   # ~160 ms at 30 FPS

# Geometric classification thresholds (normalized by palm reference distance)
PEACE_SPREAD_RATIO: Final[float] = 0.35      # Index-Middle tip separation for Peace Sign
OPEN_PALM_SPREAD_RATIO: Final[float] = 0.85  # Thumb-Pinky tip separation for Open Palm vs Five Fingers

# ---------------------------------------------------------------------------
# Gesture Action & System Control Configuration (Phase 4)
# ---------------------------------------------------------------------------
ACTION_NONE: Final[str] = "None"
ACTION_PLAY_PAUSE: Final[str] = "Play / Pause"
ACTION_NEXT_TRACK: Final[str] = "Next Track"
ACTION_PREV_TRACK: Final[str] = "Previous Track"
ACTION_VOLUME_PINCH: Final[str] = "Continuous Volume"
ACTION_MUTE: Final[str] = "Mute / Unmute"

SUPPORTED_ACTIONS: Final[Tuple[str, ...]] = (
    ACTION_NONE,
    ACTION_PLAY_PAUSE,
    ACTION_NEXT_TRACK,
    ACTION_PREV_TRACK,
    ACTION_VOLUME_PINCH,
    ACTION_MUTE,
)

# Conservative default gesture-to-action mapping
# Resting poses (Open Palm, Fist) do nothing destructive by default
DEFAULT_GESTURE_ACTIONS: Final[Dict[str, str]] = {
    GESTURE_THUMBS_UP: ACTION_PLAY_PAUSE,
    GESTURE_PEACE: ACTION_VOLUME_PINCH,
    GESTURE_THREE_FINGERS: ACTION_NEXT_TRACK,
    GESTURE_FOUR_FINGERS: ACTION_PREV_TRACK,
    GESTURE_FIST: ACTION_NONE,
    GESTURE_OPEN_PALM: ACTION_NONE,
    GESTURE_ONE_FINGER: ACTION_NONE,
    GESTURE_TWO_FINGERS: ACTION_NONE,
    GESTURE_FIVE_FINGERS: ACTION_NONE,
}

# Safety gates (Controls must default to disabled)
CONTROLS_ENABLED_DEFAULT: Final[bool] = False
MOUSE_ENABLED_DEFAULT: Final[bool] = False

# Action execution timing & cooldowns
ACTION_COOLDOWN_SEC: Final[float] = 1.0  # Seconds between discrete gesture action triggers

# Continuous Volume Pinch Configuration
VOLUME_CHANGE_THRESHOLD: Final[int] = 3          # Minimum percentage change before committing volume
VOLUME_UPDATE_INTERVAL_SEC: Final[float] = 0.15  # Minimum seconds between system volume updates
VOLUME_PINCH_MIN_RATIO: Final[float] = 0.20      # Normalized thumb-index distance corresponding to 0% volume
VOLUME_PINCH_MAX_RATIO: Final[float] = 0.90      # Normalized thumb-index distance corresponding to 100% volume
VOLUME_SMOOTHING_ALPHA: Final[float] = 0.30      # EMA smoothing factor for continuous volume

# Virtual Mouse Configuration
MOUSE_SMOOTHING_ALPHA: Final[float] = 0.35           # EMA smoothing factor for cursor positioning
MOUSE_CLICK_THRESHOLD_RATIO: Final[float] = 0.28     # Normalized pinch distance to trigger click
MOUSE_RELEASE_THRESHOLD_RATIO: Final[float] = 0.38   # Normalized pinch distance to release click
MOUSE_CLICK_COOLDOWN_SEC: Final[float] = 0.40        # Debounce seconds between clicks
MOUSE_ACTIVE_MARGIN_X: Final[float] = 0.15           # Horizontal active margin to reach screen edges easily
MOUSE_ACTIVE_MARGIN_Y: Final[float] = 0.15           # Vertical active margin

# ---------------------------------------------------------------------------
# Camera Status Constants
# ---------------------------------------------------------------------------
STATUS_STOPPED: Final[str] = "Stopped"
STATUS_STARTING: Final[str] = "Starting"
STATUS_RUNNING: Final[str] = "Running"
STATUS_ERROR: Final[str] = "Error"

VALID_CAMERA_STATUSES: Final[Tuple[str, ...]] = (
    STATUS_STOPPED,
    STATUS_STARTING,
    STATUS_RUNNING,
    STATUS_ERROR,
)

# ---------------------------------------------------------------------------
# Phase 3 UI Defaults
# ---------------------------------------------------------------------------
GESTURE_PLACEHOLDER_TEXT: Final[str] = GESTURE_NONE
GESTURE_ENGINE_STATE: Final[str] = "Engine Active (9 Gestures)"
INITIAL_HANDS_COUNT: Final[int] = 0
INITIAL_GESTURES_COUNT: Final[int] = 0

# ---------------------------------------------------------------------------
# UI Theme Palette (Dark Navy & Crisp Cyan / Blue Accents)
# ---------------------------------------------------------------------------
# Backgrounds
COLOR_BG_ROOT: Final[str] = "#0B1325"        # Main dark navy window background
COLOR_BG_SURFACE: Final[str] = "#111E38"     # Card & sidebar container surface
COLOR_BG_CARD_INNER: Final[str] = "#162544"  # Nested card / stat box background
COLOR_BG_HEADER: Final[str] = "#0E182F"      # Top app header banner
COLOR_BG_PREVIEW: Final[str] = "#060A14"     # Camera view canvas background
COLOR_BORDER: Final[str] = "#1E2E4E"         # Subtle card border
COLOR_BORDER_ACCENT: Final[str] = "#0284C7"  # Highlighted border

# Accent & Highlights
COLOR_ACCENT_CYAN: Final[str] = "#38BDF8"    # High-visibility neon cyan
COLOR_ACCENT_BLUE: Final[str] = "#0284C7"    # Professional rich blue
COLOR_ACCENT_GLOW: Final[str] = "#0EA5E9"    # Glow / hover highlight

# Buttons
COLOR_BTN_START_BG: Final[str] = "#0284C7"
COLOR_BTN_START_HOVER: Final[str] = "#0369A1"
COLOR_BTN_START_TEXT: Final[str] = "#FFFFFF"

COLOR_BTN_STOP_BG: Final[str] = "#DC2626"
COLOR_BTN_STOP_HOVER: Final[str] = "#B91C1C"
COLOR_BTN_STOP_TEXT: Final[str] = "#FFFFFF"

COLOR_BTN_DISABLED_BG: Final[str] = "#1E293B"
COLOR_BTN_DISABLED_TEXT: Final[str] = "#475569"

# Text Colors
COLOR_TEXT_PRIMARY: Final[str] = "#F8FAFC"   # Pure crisp light text
COLOR_TEXT_SECONDARY: Final[str] = "#94A3B8" # Muted slate for labels & tips
COLOR_TEXT_MUTED: Final[str] = "#64748B"     # Darker muted placeholder text
COLOR_TEXT_ACCENT: Final[str] = "#38BDF8"    # Cyan accent text

# Status Indicator Colors
COLOR_STATUS_MAP = {
    STATUS_STOPPED: "#64748B",   # Slate gray
    STATUS_STARTING: "#F59E0B",  # Amber gold
    STATUS_RUNNING: "#10B981",   # Emerald green
    STATUS_ERROR: "#EF4444",     # Coral red
}

# ---------------------------------------------------------------------------
# Typography (macOS optimized with cross-platform fallbacks)
# ---------------------------------------------------------------------------
FONT_FAMILY: Final[str] = "Helvetica Neue"
FONT_FALLBACKS: Final[Tuple[str, ...]] = ("SF Pro Display", "Arial", "sans-serif")

FONT_APP_TITLE: Final[Tuple[str, int, str]] = (FONT_FAMILY, 15, "bold")
FONT_APP_SUBTITLE: Final[Tuple[str, int]] = (FONT_FAMILY, 9)
FONT_CARD_TITLE: Final[Tuple[str, int, str]] = (FONT_FAMILY, 11, "bold")
FONT_BODY: Final[Tuple[str, int]] = (FONT_FAMILY, 10)
FONT_BODY_BOLD: Final[Tuple[str, int, str]] = (FONT_FAMILY, 10, "bold")
FONT_SMALL: Final[Tuple[str, int]] = (FONT_FAMILY, 9)
FONT_STAT_VALUE: Final[Tuple[str, int, str]] = (FONT_FAMILY, 20, "bold")
FONT_STAT_LABEL: Final[Tuple[str, int]] = (FONT_FAMILY, 9)
FONT_BADGE: Final[Tuple[str, int, str]] = (FONT_FAMILY, 9, "bold")
FONT_PREVIEW_OVERLAY: Final[Tuple[str, int, str]] = (FONT_FAMILY, 10, "bold")
