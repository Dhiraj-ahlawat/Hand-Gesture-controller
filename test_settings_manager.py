"""
tests/test_settings_manager.py
Automated tests for Phase 5 Central Settings Manager, UserSettings dataclass,
JSON persistence, atomic file saving, validation, and dynamic runtime reconfiguration.
"""

import json
from pathlib import Path
import pytest

from app.config import (
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
    SUPPORTED_ACTIONS,
    SUPPORTED_GESTURES,
)
from app.control_manager import ControlManager, MockSystemActionAdapter
from app.gesture_recognizer import GestureRecognizer
from app.settings_manager import (
    SETTING_SPECS,
    SettingsManager,
    UserSettings,
    get_default_settings_path,
)


@pytest.fixture
def temp_settings_path(tmp_path: Path) -> Path:
    """Provide a temporary settings JSON file path isolated from real user settings."""
    return tmp_path / "test_settings.json"


# ---------------------------------------------------------------------------
# 1. Default Settings on First Launch
# ---------------------------------------------------------------------------
def test_default_settings_on_first_launch(temp_settings_path: Path):
    """Verify that default settings are created and saved on first launch when missing."""
    assert not temp_settings_path.exists()

    mgr = SettingsManager(filepath=temp_settings_path)
    assert temp_settings_path.exists()

    settings = mgr.current_settings
    assert isinstance(settings, UserSettings)
    assert settings.gesture_history_length == GESTURE_HISTORY_LENGTH
    assert settings.gesture_min_consistent == GESTURE_MIN_CONSISTENT
    assert settings.gesture_cooldown_sec == GESTURE_COOLDOWN_SEC

    # Check that default mappings match
    for gesture, expected_action in DEFAULT_GESTURE_ACTIONS.items():
        assert settings.gesture_actions.get(gesture) == expected_action


# ---------------------------------------------------------------------------
# 2. Saving and Reloading Preferences
# ---------------------------------------------------------------------------
def test_save_and_reload_preferences(temp_settings_path: Path):
    """Verify that modified settings are saved and reloaded faithfully."""
    mgr = SettingsManager(filepath=temp_settings_path)

    # Modify settings
    custom = mgr.current_settings
    custom.gesture_history_length = 12
    custom.gesture_min_consistent = 8
    custom.gesture_cooldown_sec = 1.2
    custom.action_cooldown_sec = 2.5
    custom.volume_change_threshold = 7
    custom.mouse_smoothing_alpha = 0.50
    custom.gesture_actions[GESTURE_THUMBS_UP] = ACTION_MUTE
    custom.gesture_actions[GESTURE_OPEN_PALM] = ACTION_PLAY_PAUSE

    save_success = mgr.save(custom)
    assert save_success is True

    # Reload in a completely separate SettingsManager instance
    reloaded_mgr = SettingsManager(filepath=temp_settings_path)
    reloaded = reloaded_mgr.current_settings

    assert reloaded.gesture_history_length == 12
    assert reloaded.gesture_min_consistent == 8
    assert reloaded.gesture_cooldown_sec == pytest.approx(1.2)
    assert reloaded.action_cooldown_sec == pytest.approx(2.5)
    assert reloaded.volume_change_threshold == 7
    assert reloaded.mouse_smoothing_alpha == pytest.approx(0.50)
    assert reloaded.gesture_actions[GESTURE_THUMBS_UP] == ACTION_MUTE
    assert reloaded.gesture_actions[GESTURE_OPEN_PALM] == ACTION_PLAY_PAUSE


# ---------------------------------------------------------------------------
# 3. Malformed, Missing, or Incompatible JSON Files
# ---------------------------------------------------------------------------
def test_malformed_json_fallback_and_backup(temp_settings_path: Path):
    """Ensure malformed JSON files are backed up and healthy defaults are restored."""
    # Write corrupted syntax
    temp_settings_path.parent.mkdir(parents=True, exist_ok=True)
    temp_settings_path.write_text("{this is not valid json! bad syntax: 12345", encoding="utf-8")

    mgr = SettingsManager(filepath=temp_settings_path)
    # Must not raise an exception; must restore valid defaults
    assert mgr.current_settings.gesture_history_length == GESTURE_HISTORY_LENGTH

    # Backup file should have been generated
    backup_file = temp_settings_path.with_suffix(".json.bak")
    assert backup_file.exists()
    assert "{this is not valid json!" in backup_file.read_text(encoding="utf-8")

    # Settings file itself should now be valid JSON
    with open(temp_settings_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "gesture_history_length" in data


def test_empty_json_file_handling(temp_settings_path: Path):
    """Handle 0-byte or whitespace-only files gracefully."""
    temp_settings_path.parent.mkdir(parents=True, exist_ok=True)
    temp_settings_path.write_text("   \n\t", encoding="utf-8")

    mgr = SettingsManager(filepath=temp_settings_path)
    assert mgr.current_settings.gesture_history_length == GESTURE_HISTORY_LENGTH


def test_non_dict_json_root_handling(temp_settings_path: Path):
    """Ensure JSON files with arrays or primitives at root revert to defaults."""
    temp_settings_path.parent.mkdir(parents=True, exist_ok=True)
    temp_settings_path.write_text(json.dumps(["some", "array", "values"]), encoding="utf-8")

    mgr = SettingsManager(filepath=temp_settings_path)
    assert isinstance(mgr.current_settings, UserSettings)
    assert mgr.current_settings.gesture_actions[GESTURE_THUMBS_UP] == ACTION_PLAY_PAUSE


# ---------------------------------------------------------------------------
# 4. Out-of-Range and Invalid Value Sanitization
# ---------------------------------------------------------------------------
def test_out_of_range_numerical_values_clamped(temp_settings_path: Path):
    """Verify that numerical values exceeding bounds are clamped safely."""
    raw_bad_data = {
        "gesture_history_length": 9999,      # Max is 20
        "gesture_min_consistent": -50,       # Min is 2
        "gesture_cooldown_sec": 100.0,       # Max is 3.0
        "action_cooldown_sec": -10.0,        # Min is 0.1
        "volume_change_threshold": 99,       # Max is 20
        "volume_update_interval_sec": 0.001, # Min is 0.05
        "volume_smoothing_alpha": 5.0,       # Max is 0.95
        "mouse_smoothing_alpha": -1.0,       # Min is 0.05
        "mouse_click_threshold_ratio": 2.0,  # Max is 0.50
        "mouse_release_threshold_ratio": 0.01, # Too low; must exceed click threshold
        "mouse_click_cooldown_sec": 10.0,    # Max is 2.0
    }
    temp_settings_path.write_text(json.dumps(raw_bad_data), encoding="utf-8")

    mgr = SettingsManager(filepath=temp_settings_path)
    s = mgr.current_settings

    assert s.gesture_history_length == 20
    assert s.gesture_min_consistent >= 2
    assert s.gesture_cooldown_sec == pytest.approx(3.0)
    assert s.action_cooldown_sec == pytest.approx(0.1)
    assert s.volume_change_threshold == 20
    assert s.volume_update_interval_sec == pytest.approx(0.05)
    assert s.volume_smoothing_alpha == pytest.approx(0.95)
    assert s.mouse_smoothing_alpha == pytest.approx(0.05)
    assert s.mouse_click_threshold_ratio == pytest.approx(0.50)
    assert s.mouse_release_threshold_ratio > s.mouse_click_threshold_ratio
    assert s.mouse_click_cooldown_sec == pytest.approx(2.0)


def test_consistency_constraint_min_cannot_exceed_history():
    """Verify min_consistent is clamped if it exceeds history_length."""
    data = {
        "gesture_history_length": 5,
        "gesture_min_consistent": 10,
    }
    settings = UserSettings.from_dict(data)
    assert settings.gesture_min_consistent == 5


# ---------------------------------------------------------------------------
# 5. Unsupported Gesture / Action Mapping Rejection
# ---------------------------------------------------------------------------
def test_unsupported_actions_and_malicious_commands_rejected():
    """Verify arbitrary shell strings or unsupported actions cannot be saved."""
    data = {
        "gesture_actions": {
            GESTURE_THUMBS_UP: "rm -rf /",
            GESTURE_OPEN_PALM: "import os; os.system('echo hacked')",
            GESTURE_PEACE: "curl http://malicious.site",
            GESTURE_FIST: "Invalid Action",
            "Unsupported Gesture Name": ACTION_PLAY_PAUSE,
        }
    }
    settings = UserSettings.from_dict(data)

    # Any action not in SUPPORTED_ACTIONS must be converted to ACTION_NONE
    assert settings.gesture_actions[GESTURE_THUMBS_UP] == ACTION_NONE
    assert settings.gesture_actions[GESTURE_OPEN_PALM] == ACTION_NONE
    assert settings.gesture_actions[GESTURE_PEACE] == ACTION_NONE
    assert settings.gesture_actions[GESTURE_FIST] == ACTION_NONE

    # Non-supported gesture key must not exist in final mapping
    assert "Unsupported Gesture Name" not in settings.gesture_actions

    # All 9 supported gestures must be present
    for g in SUPPORTED_GESTURES:
        assert g in settings.gesture_actions
        assert settings.gesture_actions[g] in SUPPORTED_ACTIONS


def test_validation_reports_errors_for_illegal_values():
    """Verify validate() returns is_valid=False and descriptive messages."""
    mgr = SettingsManager(filepath=Path("/tmp/nonexistent_test_settings.json"))
    bad_settings = UserSettings(
        gesture_actions={
            GESTURE_THUMBS_UP: "DangerousCommand",
            "FakeGesture": ACTION_PLAY_PAUSE,
        },
        gesture_history_length=5,
        gesture_min_consistent=8,  # > history_length
    )

    is_valid, messages, sanitized = mgr.validate(bad_settings)
    assert is_valid is False
    assert any("not supported" in m or "DangerousCommand" in m for m in messages)
    assert any("not recognized" in m or "FakeGesture" in m for m in messages)

    # Sanitized object should be clean and compliant
    assert sanitized.gesture_actions[GESTURE_THUMBS_UP] == ACTION_NONE
    assert "FakeGesture" not in sanitized.gesture_actions
    assert sanitized.gesture_min_consistent <= sanitized.gesture_history_length


# ---------------------------------------------------------------------------
# 6. Reset to Defaults
# ---------------------------------------------------------------------------
def test_reset_to_defaults(temp_settings_path: Path):
    """Verify reset_to_defaults() reverts all settings to original factory values."""
    mgr = SettingsManager(filepath=temp_settings_path)

    # Mutate settings
    mgr.current_settings.gesture_history_length = 18
    mgr.current_settings.gesture_actions[GESTURE_THUMBS_UP] = ACTION_NONE
    mgr.save()

    # Reset
    reset_settings = mgr.reset_to_defaults()
    assert reset_settings.gesture_history_length == GESTURE_HISTORY_LENGTH
    assert reset_settings.gesture_actions[GESTURE_THUMBS_UP] == ACTION_PLAY_PAUSE

    # Confirm persisted on disk
    reloaded = SettingsManager(filepath=temp_settings_path).current_settings
    assert reloaded.gesture_history_length == GESTURE_HISTORY_LENGTH
    assert reloaded.gesture_actions[GESTURE_THUMBS_UP] == ACTION_PLAY_PAUSE


# ---------------------------------------------------------------------------
# 7. Independent Safety Controls & Non-Persistence of Session Activation
# ---------------------------------------------------------------------------
def test_safety_controls_remain_disabled_on_launch():
    """Ensure controls and mouse are always disabled on initialization for user safety."""
    mock_adapter = MockSystemActionAdapter()
    ctrl_mgr = ControlManager(adapter=mock_adapter)

    # Both modes must be disabled by default
    assert ctrl_mgr.controls_enabled is False
    assert ctrl_mgr.mouse_enabled is False

    # Activating controls in session works independently
    ctrl_mgr.enable_controls(True)
    assert ctrl_mgr.controls_enabled is True
    assert ctrl_mgr.mouse_enabled is False

    ctrl_mgr.enable_mouse(True)
    assert ctrl_mgr.controls_enabled is True
    assert ctrl_mgr.mouse_enabled is True

    # Emergency stop disables both immediately
    ctrl_mgr.emergency_stop()
    assert ctrl_mgr.controls_enabled is False
    assert ctrl_mgr.mouse_enabled is False


# ---------------------------------------------------------------------------
# 8. Dynamic Application to Running Components
# ---------------------------------------------------------------------------
def test_dynamic_settings_application_without_restart(temp_settings_path: Path):
    """Verify apply_to_components updates recognizer and control manager in-place."""
    mgr = SettingsManager(filepath=temp_settings_path)

    recognizer = GestureRecognizer(history_length=5, min_consistent_predictions=3, cooldown_sec=0.2)
    mock_adapter = MockSystemActionAdapter()
    ctrl_mgr = ControlManager(adapter=mock_adapter, action_cooldown_sec=0.5)

    # Initial states
    assert recognizer.history_length == 5
    assert recognizer.min_consistent == 3
    assert ctrl_mgr.action_cooldown_sec == pytest.approx(0.5)

    # Update settings
    custom = mgr.current_settings
    custom.gesture_history_length = 15
    custom.gesture_min_consistent = 10
    custom.gesture_cooldown_sec = 1.5
    custom.action_cooldown_sec = 3.0
    custom.volume_change_threshold = 8
    custom.mouse_smoothing_alpha = 0.65
    custom.gesture_actions[GESTURE_FIST] = ACTION_MUTE

    mgr.apply_to_components(custom, gesture_recognizer=recognizer, control_manager=ctrl_mgr)

    # Verify recognizer was updated dynamically
    assert recognizer.history_length == 15
    assert recognizer.min_consistent == 10
    assert recognizer.cooldown_sec == pytest.approx(1.5)
    assert recognizer._prediction_history.maxlen == 15

    # Verify control manager was updated dynamically
    assert ctrl_mgr.action_cooldown_sec == pytest.approx(3.0)
    assert ctrl_mgr.volume_change_threshold == 8
    assert ctrl_mgr.mouse_smoothing_alpha == pytest.approx(0.65)
    assert ctrl_mgr.gesture_action_map[GESTURE_FIST] == ACTION_MUTE


# ---------------------------------------------------------------------------
# 9. Cross-Platform Default Path Discovery
# ---------------------------------------------------------------------------
def test_default_settings_path_validity():
    """Verify default path is an absolute, predictable path under user home directory."""
    path = get_default_settings_path()
    assert isinstance(path, Path)
    assert path.is_absolute()
    assert str(Path.home()) in str(path)
    assert path.name == "settings.json"


def test_user_settings_to_dict_and_from_dict_roundtrip():
    """Verify serialization to dict and deserialization from dict preserve all properties."""
    original = UserSettings(
        gesture_history_length=11,
        gesture_min_consistent=7,
        gesture_cooldown_sec=0.8,
        action_cooldown_sec=1.7,
        volume_change_threshold=5,
        volume_update_interval_sec=0.25,
        volume_smoothing_alpha=0.45,
        mouse_smoothing_alpha=0.55,
        mouse_click_threshold_ratio=0.22,
        mouse_release_threshold_ratio=0.35,
        mouse_click_cooldown_sec=0.45,
        gesture_actions={g: ACTION_NONE for g in SUPPORTED_GESTURES},
    )
    data = original.to_dict()
    assert isinstance(data, dict)
    recreated = UserSettings.from_dict(data)

    assert recreated.gesture_history_length == 11
    assert recreated.gesture_min_consistent == 7
    assert recreated.gesture_cooldown_sec == pytest.approx(0.8)
    assert recreated.action_cooldown_sec == pytest.approx(1.7)
    assert recreated.volume_change_threshold == 5
    assert recreated.volume_update_interval_sec == pytest.approx(0.25)
    assert recreated.volume_smoothing_alpha == pytest.approx(0.45)
    assert recreated.mouse_smoothing_alpha == pytest.approx(0.55)
    assert recreated.mouse_click_threshold_ratio == pytest.approx(0.22)
    assert recreated.mouse_release_threshold_ratio == pytest.approx(0.35)
    assert recreated.mouse_click_cooldown_sec == pytest.approx(0.45)
    for g in SUPPORTED_GESTURES:
        assert recreated.gesture_actions[g] == ACTION_NONE


def test_apply_to_components_with_none_components():
    """Ensure apply_to_components does not raise an exception when components are None."""
    mgr = SettingsManager(filepath=Path("/tmp/safe_mock_settings.json"))
    # Should safely complete without error
    mgr.apply_to_components(gesture_recognizer=None, control_manager=None)


def test_mouse_release_threshold_adjusted_if_less_than_click_threshold():
    """Ensure release threshold is automatically pushed above click threshold for hysteresis."""
    data = {
        "mouse_click_threshold_ratio": 0.35,
        "mouse_release_threshold_ratio": 0.20,  # Invalid: less than click threshold
    }
    settings = UserSettings.from_dict(data)
    assert settings.mouse_release_threshold_ratio > settings.mouse_click_threshold_ratio


def test_negative_and_extreme_cooldowns_clamped():
    """Ensure negative and extreme cooldown values are safely clamped to spec boundaries."""
    data = {
        "action_cooldown_sec": -10.0,
        "gesture_cooldown_sec": 999.0,
        "volume_change_threshold": -5,
    }
    settings = UserSettings.from_dict(data)
    assert settings.action_cooldown_sec == pytest.approx(0.1)
    assert settings.gesture_cooldown_sec == pytest.approx(3.0)
    assert settings.volume_change_threshold == 1


def test_invalid_type_settings_fallback_to_defaults():
    """Ensure strings or illegal objects for numeric settings gracefully fall back to defaults."""
    data = {
        "action_cooldown_sec": "not_a_number",
        "gesture_history_length": [1, 2, 3],
        "volume_smoothing_alpha": {"invalid": True},
    }
    settings = UserSettings.from_dict(data)
    assert settings.action_cooldown_sec == pytest.approx(SETTING_SPECS["action_cooldown_sec"]["default"])
    assert settings.gesture_history_length == SETTING_SPECS["gesture_history_length"]["default"]
    assert settings.volume_smoothing_alpha == pytest.approx(SETTING_SPECS["volume_smoothing_alpha"]["default"])

