"""
tests/test_statistics_manager.py
Unit and integration tests for StatisticsManager, session history persistence,
gesture deduplication, and system action outcome tracking.
"""

from pathlib import Path
import time
import pytest

from app.config import (
    ACTION_NEXT_TRACK,
    ACTION_NONE,
    ACTION_PLAY_PAUSE,
    GESTURE_FIST,
    GESTURE_NONE,
    GESTURE_PEACE,
    GESTURE_THUMBS_UP,
    GESTURE_UNKNOWN,
    SUPPORTED_GESTURES,
)
from app.control_manager import ControlManager, MockSystemActionAdapter
from app.statistics_manager import SessionRecord, StatisticsManager


@pytest.fixture
def temp_stats_manager(tmp_path: Path) -> StatisticsManager:
    """Provide a StatisticsManager isolated to a temporary SQLite database."""
    db_file = tmp_path / "test_history.db"
    return StatisticsManager(db_path=db_file)


# ---------------------------------------------------------------------------
# Initial State & Data Model Tests
# ---------------------------------------------------------------------------
def test_statistics_manager_initial_state(temp_stats_manager: StatisticsManager):
    """Verify that a newly initialized StatisticsManager has clean zeroed metrics."""
    mgr = temp_stats_manager
    assert mgr.session_id.startswith("sess_")
    assert mgr.start_time > 0.0
    assert mgr.end_time is None
    assert mgr.total_gestures_count == 0
    assert mgr.unknown_gestures_count == 0
    assert mgr.successful_actions_count == 0
    assert mgr.blocked_actions_count == 0
    assert mgr.failed_actions_count == 0
    for g in SUPPORTED_GESTURES:
        assert mgr.gesture_counts[g] == 0
    assert mgr.get_most_used_gesture() == ("None", 0)
    assert mgr.get_session_duration() >= 0.0


def test_session_record_formatting():
    """Verify human-readable formatting properties of SessionRecord."""
    rec = SessionRecord(
        session_id="test_sess_01",
        start_time=1700000000.0,
        end_time=1700000125.0,
        duration_sec=125.0,
        total_gestures=10,
        most_used_gesture=GESTURE_PEACE,
        successful_actions=3,
        blocked_actions=1,
        failed_actions=0,
        unknown_gestures=2,
        gesture_counts={GESTURE_PEACE: 8, GESTURE_THUMBS_UP: 2},
        action_counts={"Play / Pause": 3},
    )
    assert rec.duration_formatted == "02:05"
    assert "1970" not in rec.start_time_formatted or "2023" in rec.start_time_formatted or len(rec.start_time_formatted) == 19
    d = rec.to_dict()
    assert d["session_id"] == "test_sess_01"
    assert d["duration_sec"] == 125.0


# ---------------------------------------------------------------------------
# Gesture Event Deduplication Tests
# ---------------------------------------------------------------------------
def test_gesture_deduplication_repeated_frames(temp_stats_manager: StatisticsManager):
    """
    Strict Requirement: Prevent frame-by-frame duplicate counting.
    100 consecutive frames with the same gesture must increment the count exactly once.
    """
    mgr = temp_stats_manager

    # First frame of Peace Sign -> counted
    assert mgr.record_gesture(GESTURE_PEACE) is True
    assert mgr.gesture_counts[GESTURE_PEACE] == 1
    assert mgr.total_gestures_count == 1

    # Next 99 frames of Peace Sign -> ignored
    for _ in range(99):
        assert mgr.record_gesture(GESTURE_PEACE) is False

    assert mgr.gesture_counts[GESTURE_PEACE] == 1
    assert mgr.total_gestures_count == 1


def test_gesture_transition_between_distinct_gestures(temp_stats_manager: StatisticsManager):
    """
    Verify that transitions between different valid gestures trigger distinct events.
    """
    mgr = temp_stats_manager

    # Peace Sign -> Thumbs Up -> Fist -> Thumbs Up
    assert mgr.record_gesture(GESTURE_PEACE) is True
    assert mgr.record_gesture(GESTURE_THUMBS_UP) is True
    assert mgr.record_gesture(GESTURE_FIST) is True
    assert mgr.record_gesture(GESTURE_THUMBS_UP) is True

    assert mgr.gesture_counts[GESTURE_PEACE] == 1
    assert mgr.gesture_counts[GESTURE_THUMBS_UP] == 2
    assert mgr.gesture_counts[GESTURE_FIST] == 1
    assert mgr.total_gestures_count == 4


def test_gesture_re_entry_from_none(temp_stats_manager: StatisticsManager):
    """
    Verify that when tracking is lost (GESTURE_NONE) and the hand returns,
    the same gesture can be recognized as a new event.
    """
    mgr = temp_stats_manager

    assert mgr.record_gesture(GESTURE_THUMBS_UP) is True
    assert mgr.gesture_counts[GESTURE_THUMBS_UP] == 1

    # Hand removed
    assert mgr.record_gesture(GESTURE_NONE) is False
    assert mgr.total_gestures_count == 1

    # Hand returns with Thumbs Up
    assert mgr.record_gesture(GESTURE_THUMBS_UP) is True
    assert mgr.gesture_counts[GESTURE_THUMBS_UP] == 2
    assert mgr.total_gestures_count == 2


def test_unknown_gesture_deduplication(temp_stats_manager: StatisticsManager):
    """
    Verify that Unknown Gesture increments unknown_gestures_count and deduplicates frames.
    """
    mgr = temp_stats_manager

    assert mgr.record_gesture(GESTURE_UNKNOWN) is True
    assert mgr.unknown_gestures_count == 1
    assert mgr.total_gestures_count == 0  # Only recognized gestures count toward total

    # Repeating frames
    assert mgr.record_gesture(GESTURE_UNKNOWN) is False
    assert mgr.unknown_gestures_count == 1


# ---------------------------------------------------------------------------
# Action Outcome Recording Tests
# ---------------------------------------------------------------------------
def test_action_recording_success_blocked_failed(temp_stats_manager: StatisticsManager):
    """
    Verify separate tracking of successful, blocked, and failed actions.
    """
    mgr = temp_stats_manager

    # Record 2 successful Play/Pause actions
    mgr.record_action(ACTION_PLAY_PAUSE, success=True, blocked=False)
    mgr.record_action(ACTION_PLAY_PAUSE, success=True, blocked=False)

    # Record 1 blocked action
    mgr.record_action(ACTION_NEXT_TRACK, success=False, blocked=True)

    # Record 1 failed action
    mgr.record_action("Mute", success=False, blocked=False)

    assert mgr.successful_actions_count == 2
    assert mgr.blocked_actions_count == 1
    assert mgr.failed_actions_count == 1
    assert mgr.action_counts[ACTION_PLAY_PAUSE] == 2


def test_most_used_gesture_computation(temp_stats_manager: StatisticsManager):
    """Verify most used gesture calculation."""
    mgr = temp_stats_manager
    assert mgr.get_most_used_gesture() == ("None", 0)

    mgr.record_gesture(GESTURE_PEACE)
    mgr.record_gesture(GESTURE_THUMBS_UP)
    mgr.record_gesture(GESTURE_PEACE)

    best_name, best_count = mgr.get_most_used_gesture()
    assert best_name == GESTURE_PEACE
    assert best_count == 2


# ---------------------------------------------------------------------------
# SQLite Persistence & Session History Tests
# ---------------------------------------------------------------------------
def test_save_and_load_session_history(temp_stats_manager: StatisticsManager):
    """
    Verify persisting active session to SQLite and loading it back cleanly.
    """
    mgr = temp_stats_manager

    mgr.record_gesture(GESTURE_PEACE)
    mgr.record_gesture(GESTURE_THUMBS_UP)
    mgr.record_action(ACTION_PLAY_PAUSE, success=True)
    mgr.record_action(ACTION_NEXT_TRACK, success=False, blocked=True)

    # Save session
    assert mgr.save_current_session() is True

    # Load history
    history = mgr.get_history()
    assert len(history) == 1

    rec = history[0]
    assert rec.session_id == mgr.session_id
    assert rec.total_gestures == 2
    assert rec.successful_actions == 1
    assert rec.blocked_actions == 1
    assert rec.failed_actions == 0
    assert rec.gesture_counts[GESTURE_PEACE] == 1
    assert rec.gesture_counts[GESTURE_THUMBS_UP] == 1
    assert rec.action_counts[ACTION_PLAY_PAUSE] == 1

    # Query by ID
    by_id = mgr.get_session_by_id(mgr.session_id)
    assert by_id is not None
    assert by_id.session_id == mgr.session_id


def test_duplicate_save_prevention(temp_stats_manager: StatisticsManager):
    """
    Requirement: Prevent duplicate session records when application closes or save is called repeatedly.
    """
    mgr = temp_stats_manager

    mgr.record_gesture(GESTURE_PEACE)
    assert mgr.save_current_session() is True
    # Second call
    assert mgr.save_current_session() is True

    history = mgr.get_history()
    assert len(history) == 1


def test_empty_history_handling(temp_stats_manager: StatisticsManager):
    """
    Requirement: Handle empty history gracefully without exceptions.
    """
    mgr = temp_stats_manager
    history = mgr.get_history()
    assert history == []
    assert mgr.get_session_by_id("non_existent_id") is None


def test_history_ordering_newest_first(tmp_path: Path):
    """
    Requirement: Historical sessions must be returned newest first.
    """
    db_file = tmp_path / "order_test.db"

    # Create and save session 1
    mgr1 = StatisticsManager(db_path=db_file)
    mgr1.start_time = 1000.0
    mgr1.end_time = 1100.0
    mgr1.record_gesture(GESTURE_PEACE)
    mgr1.save_current_session()

    # Create and save session 2 (newer)
    mgr2 = StatisticsManager(db_path=db_file)
    mgr2.start_time = 2000.0
    mgr2.end_time = 2100.0
    mgr2.record_gesture(GESTURE_THUMBS_UP)
    mgr2.save_current_session()

    # Load from third manager
    loader = StatisticsManager(db_path=db_file)
    history = loader.get_history()

    assert len(history) == 2
    assert history[0].session_id == mgr2.session_id
    assert history[1].session_id == mgr1.session_id
    assert history[0].start_time > history[1].start_time


def test_clear_history(temp_stats_manager: StatisticsManager):
    """Verify clearing historical sessions from SQLite."""
    mgr = temp_stats_manager
    mgr.record_gesture(GESTURE_PEACE)
    mgr.save_current_session()
    assert len(mgr.get_history()) == 1

    assert mgr.clear_history() is True
    assert mgr.get_history() == []


# ---------------------------------------------------------------------------
# ControlManager Integration with StatisticsManager
# ---------------------------------------------------------------------------
def test_control_manager_records_actions_into_statistics_manager(tmp_path: Path):
    """
    Integration: Verify ControlManager passes successful and blocked action events
    directly to StatisticsManager.
    """
    stats_mgr = StatisticsManager(db_path=tmp_path / "ctrl_stats.db")
    mock_adapter = MockSystemActionAdapter()
    ctrl_mgr = ControlManager(adapter=mock_adapter, statistics_manager=stats_mgr)

    # 1. When controls are disabled, attempting an action gesture records a blocked action
    landmarks = [(0.5, 0.5, 0.0)] * 21
    res1 = ctrl_mgr.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_THUMBS_UP,
        landmarks=landmarks,
    )
    assert res1 is None
    assert stats_mgr.blocked_actions_count == 1
    assert stats_mgr.successful_actions_count == 0

    # 2. Enable controls and fire action -> records successful action
    ctrl_mgr.enable_controls(True)
    res2 = ctrl_mgr.process_frame(
        is_camera_running=True,
        detected_hands_count=1,
        current_gesture=GESTURE_THUMBS_UP,
        landmarks=landmarks,
    )
    assert res2 is not None
    assert res2.success is True
    assert stats_mgr.successful_actions_count == 1
    assert stats_mgr.action_counts[ACTION_PLAY_PAUSE] == 1


def test_separation_of_current_and_historical_metrics(tmp_path: Path):
    """
    Requirement: Keep current-session metrics separate from historical summaries.
    """
    db_file = tmp_path / "sep_test.db"

    # Save Session 1
    s1 = StatisticsManager(db_path=db_file)
    s1.record_gesture(GESTURE_PEACE)
    s1.save_current_session()

    # Session 2 is active
    s2 = StatisticsManager(db_path=db_file)
    s2.record_gesture(GESTURE_THUMBS_UP)
    s2.record_gesture(GESTURE_FIST)

    assert s2.total_gestures_count == 2
    assert s2.gesture_counts[GESTURE_THUMBS_UP] == 1
    assert s2.gesture_counts[GESTURE_PEACE] == 0

    # History still accurately reflects Session 1
    hist = s2.get_history()
    assert len(hist) == 1
    assert hist[0].total_gestures == 1
    assert hist[0].gesture_counts[GESTURE_PEACE] == 1


def test_chart_data_generation(temp_stats_manager: StatisticsManager):
    """
    Requirement: Chart data must accurately represent distinct recognition counts,
    handle empty datasets properly, and never invent dummy data.
    """
    mgr = temp_stats_manager

    # Empty dataset
    empty_record = mgr.get_current_session_record()
    assert empty_record.total_gestures == 0
    assert all(c == 0 for c in empty_record.gesture_counts.values())

    # Add real data
    mgr.record_gesture(GESTURE_PEACE)
    mgr.record_gesture(GESTURE_THUMBS_UP)
    mgr.record_gesture(GESTURE_PEACE)

    populated_record = mgr.get_current_session_record()
    assert populated_record.total_gestures == 3
    assert populated_record.gesture_counts[GESTURE_PEACE] == 2
    assert populated_record.gesture_counts[GESTURE_THUMBS_UP] == 1
    assert populated_record.gesture_counts[GESTURE_FIST] == 0

