"""
app/settings_manager.py
Centralized, persistent settings manager for Hand Gesture Controller.

Phase 5: Manages customizable gesture-to-action mappings, sensitivity controls,
atomic configuration saving (JSON), validation, and dynamic runtime reconfiguration.
"""

from dataclasses import asdict, dataclass, field
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union

from app.config import (
    ACTION_COOLDOWN_SEC,
    ACTION_MUTE,
    ACTION_NEXT_TRACK,
    ACTION_NONE,
    ACTION_PLAY_PAUSE,
    ACTION_PREV_TRACK,
    ACTION_VOLUME_PINCH,
    DEFAULT_GESTURE_ACTIONS,
    GESTURE_COOLDOWN_SEC,
    GESTURE_FIST,
    GESTURE_FIVE_FINGERS,
    GESTURE_FOUR_FINGERS,
    GESTURE_HISTORY_LENGTH,
    GESTURE_MIN_CONSISTENT,
    GESTURE_ONE_FINGER,
    GESTURE_OPEN_PALM,
    GESTURE_PEACE,
    GESTURE_THREE_FINGERS,
    GESTURE_THUMBS_UP,
    GESTURE_TWO_FINGERS,
    MOUSE_CLICK_COOLDOWN_SEC,
    MOUSE_CLICK_THRESHOLD_RATIO,
    MOUSE_RELEASE_THRESHOLD_RATIO,
    MOUSE_SMOOTHING_ALPHA,
    SUPPORTED_ACTIONS,
    SUPPORTED_GESTURES,
    VOLUME_CHANGE_THRESHOLD,
    VOLUME_SMOOTHING_ALPHA,
    VOLUME_UPDATE_INTERVAL_SEC,
)

logger = logging.getLogger(__name__)

# Directory and filename definitions
SETTINGS_DIR_NAME = "HandGestureController"
SETTINGS_FILE_NAME = "settings.json"


def get_default_settings_path() -> Path:
    """
    Return the user-writable application settings file path.
    On macOS: ~/Library/Application Support/HandGestureController/settings.json
    On other OS: ~/.hand_gesture_controller/settings.json
    """
    if sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support" / SETTINGS_DIR_NAME
    else:
        base_dir = Path.home() / f".{SETTINGS_DIR_NAME.lower()}"
    return base_dir / SETTINGS_FILE_NAME


# ---------------------------------------------------------------------------
# Setting Specifications & Constraints
# ---------------------------------------------------------------------------
SETTING_SPECS: Dict[str, Dict[str, Any]] = {
    "gesture_history_length": {
        "min": 3,
        "max": 20,
        "default": GESTURE_HISTORY_LENGTH,
        "type": int,
        "label": "Gesture History Length",
        "description": "Consecutive frames evaluated for majority-vote smoothing.",
    },
    "gesture_min_consistent": {
        "min": 2,
        "max": 15,
        "default": GESTURE_MIN_CONSISTENT,
        "type": int,
        "label": "Min Consistent Predictions",
        "description": "Minimum agreement count in history before switching gesture.",
    },
    "gesture_cooldown_sec": {
        "min": 0.1,
        "max": 3.0,
        "default": GESTURE_COOLDOWN_SEC,
        "type": float,
        "label": "Gesture Switch Debounce (s)",
        "description": "Debounce period between gesture transitions.",
    },
    "action_cooldown_sec": {
        "min": 0.1,
        "max": 5.0,
        "default": ACTION_COOLDOWN_SEC,
        "type": float,
        "label": "Action Trigger Cooldown (s)",
        "description": "Minimum cooldown between discrete action executions.",
    },
    "volume_change_threshold": {
        "min": 1,
        "max": 20,
        "default": VOLUME_CHANGE_THRESHOLD,
        "type": int,
        "label": "Volume Sensitivity Step (%)",
        "description": "Minimum percentage change required to adjust system volume.",
    },
    "volume_update_interval_sec": {
        "min": 0.05,
        "max": 1.0,
        "default": VOLUME_UPDATE_INTERVAL_SEC,
        "type": float,
        "label": "Volume Update Interval (s)",
        "description": "Rate-limit interval between system volume adjustments.",
    },
    "volume_smoothing_alpha": {
        "min": 0.05,
        "max": 0.95,
        "default": VOLUME_SMOOTHING_ALPHA,
        "type": float,
        "label": "Volume Smoothing (Alpha)",
        "description": "EMA smoothing factor (lower = smoother, higher = faster).",
    },
    "mouse_smoothing_alpha": {
        "min": 0.05,
        "max": 0.95,
        "default": MOUSE_SMOOTHING_ALPHA,
        "type": float,
        "label": "Mouse Smoothing (Alpha)",
        "description": "EMA cursor smoothing factor (lower = smoother cursor).",
    },
    "mouse_click_threshold_ratio": {
        "min": 0.10,
        "max": 0.50,
        "default": MOUSE_CLICK_THRESHOLD_RATIO,
        "type": float,
        "label": "Pinch Click Threshold",
        "description": "Normalized thumb-to-index pinch distance to trigger click.",
    },
    "mouse_release_threshold_ratio": {
        "min": 0.20,
        "max": 0.70,
        "default": MOUSE_RELEASE_THRESHOLD_RATIO,
        "type": float,
        "label": "Pinch Release Threshold",
        "description": "Normalized pinch distance required to release and rearm click.",
    },
    "mouse_click_cooldown_sec": {
        "min": 0.10,
        "max": 2.0,
        "default": MOUSE_CLICK_COOLDOWN_SEC,
        "type": float,
        "label": "Mouse Click Cooldown (s)",
        "description": "Debounce period in seconds between virtual mouse clicks.",
    },
}


# ---------------------------------------------------------------------------
# User Preferences Data Structure
# ---------------------------------------------------------------------------
@dataclass
class UserSettings:
    """Strongly typed container for user customizable settings and mappings."""

    gesture_actions: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_GESTURE_ACTIONS))
    gesture_history_length: int = GESTURE_HISTORY_LENGTH
    gesture_min_consistent: int = GESTURE_MIN_CONSISTENT
    gesture_cooldown_sec: float = GESTURE_COOLDOWN_SEC
    action_cooldown_sec: float = ACTION_COOLDOWN_SEC
    volume_change_threshold: int = VOLUME_CHANGE_THRESHOLD
    volume_update_interval_sec: float = VOLUME_UPDATE_INTERVAL_SEC
    volume_smoothing_alpha: float = VOLUME_SMOOTHING_ALPHA
    mouse_smoothing_alpha: float = MOUSE_SMOOTHING_ALPHA
    mouse_click_threshold_ratio: float = MOUSE_CLICK_THRESHOLD_RATIO
    mouse_release_threshold_ratio: float = MOUSE_RELEASE_THRESHOLD_RATIO
    mouse_click_cooldown_sec: float = MOUSE_CLICK_COOLDOWN_SEC

    def to_dict(self) -> Dict[str, Any]:
        """Serialize settings to a plain JSON-compatible dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserSettings":
        """Construct UserSettings from dictionary with validation and sanitization."""
        settings = cls()

        # 1. Custom Gesture Mappings
        raw_mappings = data.get("gesture_actions")
        if isinstance(raw_mappings, dict):
            sanitized_mappings: Dict[str, str] = {}
            for gesture in SUPPORTED_GESTURES:
                action = raw_mappings.get(gesture, DEFAULT_GESTURE_ACTIONS.get(gesture, ACTION_NONE))
                if action not in SUPPORTED_ACTIONS:
                    logger.warning("Invalid action '%s' for gesture '%s'; reverting to None.", action, gesture)
                    action = ACTION_NONE
                sanitized_mappings[gesture] = str(action)
            settings.gesture_actions = sanitized_mappings
        else:
            settings.gesture_actions = dict(DEFAULT_GESTURE_ACTIONS)

        # 2. Sensitivity and Timing Controls
        for key, spec in SETTING_SPECS.items():
            if key in data:
                try:
                    val = spec["type"](data[key])
                    # Clamp to bounds
                    val = max(spec["min"], min(spec["max"], val))
                    setattr(settings, key, val)
                except (ValueError, TypeError):
                    logger.warning("Invalid setting value for '%s': %r; using default.", key, data.get(key))
                    setattr(settings, key, spec["default"])
            else:
                setattr(settings, key, spec["default"])

        # Consistency constraints
        if settings.gesture_min_consistent > settings.gesture_history_length:
            settings.gesture_min_consistent = settings.gesture_history_length

        if settings.mouse_release_threshold_ratio <= settings.mouse_click_threshold_ratio:
            settings.mouse_release_threshold_ratio = min(
                SETTING_SPECS["mouse_release_threshold_ratio"]["max"],
                settings.mouse_click_threshold_ratio + 0.08,
            )

        return settings


# ---------------------------------------------------------------------------
# Central Settings Manager
# ---------------------------------------------------------------------------
class SettingsManager:
    """
    Loads, validates, persists, and dynamically applies user configuration.
    
    Provides atomic file writing, safe corrupted file fallback, and runtime
    propagation to GestureRecognizer and ControlManager.
    """

    def __init__(self, filepath: Optional[Union[str, Path]] = None) -> None:
        self.settings_path: Path = Path(filepath) if filepath is not None else get_default_settings_path()
        self.current_settings: UserSettings = UserSettings()
        self.load()

    def validate(self, settings: UserSettings) -> Tuple[bool, List[str], UserSettings]:
        """
        Validate settings and return (is_valid, messages, sanitized_settings).
        
        Guarantees that sanitized_settings contains only valid, clamped values
        and verified actions from SUPPORTED_ACTIONS.
        """
        messages: List[str] = []
        is_valid = True

        sanitized_dict = settings.to_dict()
        sanitized = UserSettings.from_dict(sanitized_dict)

        # Check for gesture mapping validity
        for gesture, action in settings.gesture_actions.items():
            if gesture not in SUPPORTED_GESTURES:
                messages.append(f"Gesture '{gesture}' is not recognized.")
                is_valid = False
            elif action not in SUPPORTED_ACTIONS:
                messages.append(f"Action '{action}' is not supported.")
                is_valid = False

        # Check for consistency issues
        if settings.gesture_min_consistent > settings.gesture_history_length:
            messages.append("Min consistent predictions cannot exceed gesture history length.")
            is_valid = False

        if settings.mouse_release_threshold_ratio <= settings.mouse_click_threshold_ratio:
            messages.append("Mouse release threshold must be greater than click threshold.")
            is_valid = False

        return is_valid, messages, sanitized

    def load(self) -> UserSettings:
        """
        Load user preferences from JSON file.
        
        Handles missing files by creating defaults, and malformed files by
        backing up the broken file and resetting safely to defaults.
        """
        if not self.settings_path.exists():
            logger.info("Settings file not found at %s. Creating default preferences.", self.settings_path)
            self.current_settings = UserSettings()
            self.save(self.current_settings)
            return self.current_settings

        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    raise json.JSONDecodeError("Settings file is empty", "", 0)
                data = json.loads(content)

            if not isinstance(data, dict):
                raise ValueError("Settings root must be a JSON object.")

            self.current_settings = UserSettings.from_dict(data)
            logger.info("Successfully loaded user settings from %s", self.settings_path)
            return self.current_settings

        except (json.JSONDecodeError, ValueError, OSError) as exc:
            logger.warning(
                "Failed to parse settings file at %s (%s). Creating backup and restoring defaults.",
                self.settings_path,
                exc,
            )
            # Create a backup of the corrupted file
            backup_path = self.settings_path.with_suffix(".json.bak")
            try:
                if self.settings_path.exists():
                    self.settings_path.rename(backup_path)
                    logger.info("Corrupted settings backed up to %s", backup_path)
            except Exception as backup_exc:
                logger.error("Could not create settings backup: %s", backup_exc)

            # Restore default settings
            self.current_settings = UserSettings()
            self.save(self.current_settings)
            return self.current_settings

    def save(self, settings: Optional[UserSettings] = None) -> bool:
        """
        Atomically write preferences to the settings JSON file.
        
        Writes to a temporary file in the same directory first, flushes and syncs,
        then replaces the target file to avoid partial writes or configuration corruption.
        """
        to_save = settings if settings is not None else self.current_settings
        _, _, sanitized = self.validate(to_save)

        try:
            parent_dir = self.settings_path.parent
            parent_dir.mkdir(parents=True, exist_ok=True)

            # Write atomically using a temporary file in the destination directory
            temp_file = parent_dir / f"{self.settings_path.name}.tmp.{os.getpid()}"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(sanitized.to_dict(), f, indent=2, ensure_ascii=False)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except (AttributeError, OSError):
                    pass

            # Atomic replace
            temp_file.replace(self.settings_path)
            self.current_settings = sanitized
            logger.info("Atomically saved settings to %s", self.settings_path)
            return True

        except Exception as exc:
            logger.error("Failed to save settings to %s: %s", self.settings_path, exc)
            return False

    def reset_to_defaults(self) -> UserSettings:
        """Reset preferences to factory default values and persist to disk."""
        self.current_settings = UserSettings()
        self.save(self.current_settings)
        logger.info("Settings reset to defaults and saved to %s", self.settings_path)
        return self.current_settings

    def apply_to_components(
        self,
        settings: Optional[UserSettings] = None,
        gesture_recognizer: Optional[Any] = None,
        control_manager: Optional[Any] = None,
    ) -> None:
        """
        Dynamically propagate configuration values to running perception and control components.
        
        Avoids restarting the webcam or recreating components.
        """
        active_settings = settings if settings is not None else self.current_settings

        # 1. Update Gesture Recognizer
        if gesture_recognizer is not None and hasattr(gesture_recognizer, "configure"):
            gesture_recognizer.configure(
                history_length=active_settings.gesture_history_length,
                min_consistent=active_settings.gesture_min_consistent,
                cooldown_sec=active_settings.gesture_cooldown_sec,
            )
            logger.debug("Applied settings to GestureRecognizer.")

        # 2. Update Control Manager
        if control_manager is not None and hasattr(control_manager, "configure"):
            control_manager.configure(
                gesture_action_map=active_settings.gesture_actions,
                action_cooldown_sec=active_settings.action_cooldown_sec,
                volume_change_threshold=active_settings.volume_change_threshold,
                volume_update_interval_sec=active_settings.volume_update_interval_sec,
                volume_smoothing_alpha=active_settings.volume_smoothing_alpha,
                mouse_smoothing_alpha=active_settings.mouse_smoothing_alpha,
                mouse_click_threshold_ratio=active_settings.mouse_click_threshold_ratio,
                mouse_release_threshold_ratio=active_settings.mouse_release_threshold_ratio,
                mouse_click_cooldown_sec=active_settings.mouse_click_cooldown_sec,
            )
            logger.debug("Applied settings to ControlManager.")
