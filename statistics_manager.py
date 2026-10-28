"""
app/statistics_manager.py
Modular Statistics and Session History Manager for Hand Gesture Controller.

Phase 6: Tracks stabilized gesture recognition events (preventing per-frame duplicates),
monitors system action success/blocked/failed outcomes, calculates session duration,
and persists historical session analytics in a local SQLite database.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from app.config import (
    GESTURE_NONE,
    GESTURE_UNKNOWN,
    SETTINGS_DIRNAME,
    SUPPORTED_ACTIONS,
    SUPPORTED_GESTURES,
)

logger = logging.getLogger(__name__)

HISTORY_DB_FILENAME = "history.db"


def get_default_history_db_path() -> Path:
    """
    Return the user-writable SQLite database path for session history.
    On macOS: ~/Library/Application Support/HandGestureController/history.db
    On other OS: ~/.hand_gesture_controller/history.db
    """
    if sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support" / SETTINGS_DIRNAME
    else:
        base_dir = Path.home() / f".{SETTINGS_DIRNAME.lower()}"
    return base_dir / HISTORY_DB_FILENAME


# ---------------------------------------------------------------------------
# Structured Session Record Data Model
# ---------------------------------------------------------------------------
@dataclass
class SessionRecord:
    """Structured immutable snapshot of an application session."""

    session_id: str
    start_time: float
    end_time: float
    duration_sec: float
    total_gestures: int
    most_used_gesture: str
    successful_actions: int
    blocked_actions: int
    failed_actions: int
    unknown_gestures: int
    gesture_counts: Dict[str, int] = field(default_factory=dict)
    action_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def start_time_formatted(self) -> str:
        """Return human-readable local datetime string for session start."""
        dt = datetime.fromtimestamp(self.start_time)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def duration_formatted(self) -> str:
        """Return session duration formatted as MM:SS or HH:MM:SS."""
        secs = int(max(0, self.duration_sec))
        hours = secs // 3600
        mins = (secs % 3600) // 60
        remaining_secs = secs % 60
        if hours > 0:
            return f"{hours:02d}:{mins:02d}:{remaining_secs:02d}"
        return f"{mins:02d}:{remaining_secs:02d}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert session record to a plain dictionary."""
        return asdict(self)

    @classmethod
    def from_row(cls, row: Tuple) -> "SessionRecord":
        """Construct a SessionRecord from an SQLite query row."""
        (
            sess_id,
            start_t,
            end_t,
            dur,
            tot_g,
            most_g,
            succ_a,
            block_a,
            fail_a,
            unk_g,
            g_json,
            a_json,
        ) = row

        try:
            g_counts = json.loads(g_json) if g_json else {}
        except Exception:
            g_counts = {}

        try:
            a_counts = json.loads(a_json) if a_json else {}
        except Exception:
            a_counts = {}

        return cls(
            session_id=str(sess_id),
            start_time=float(start_t),
            end_time=float(end_t),
            duration_sec=float(dur),
            total_gestures=int(tot_g),
            most_used_gesture=str(most_g or "None"),
            successful_actions=int(succ_a),
            blocked_actions=int(block_a),
            failed_actions=int(fail_a),
            unknown_gestures=int(unk_g),
            gesture_counts=g_counts,
            action_counts=a_counts,
        )


# ---------------------------------------------------------------------------
# Statistics and Session History Manager
# ---------------------------------------------------------------------------
class StatisticsManager:
    """
    Coordinates real-time metric collection, per-frame duplicate filtering,
    session lifecycle tracking, and SQLite persistence.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path: Path = Path(db_path) if db_path is not None else get_default_history_db_path()

        # Session identification & timing
        now = time.time()
        now_dt = datetime.fromtimestamp(now)
        self.session_id: str = f"sess_{now_dt.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.start_time: float = now
        self.end_time: Optional[float] = None
        self._is_saved: bool = False

        # Gesture event tracking & deduplication (Phase 8 Lifecycle)
        self._last_stabilized_gesture: Optional[str] = None
        self._last_counted_valid_gesture: Optional[str] = None
        self.gesture_counts: Dict[str, int] = {g: 0 for g in SUPPORTED_GESTURES}
        self.unknown_gestures_count: int = 0
        self.total_gestures_count: int = 0

        # Action execution tracking
        self.successful_actions_count: int = 0
        self.blocked_actions_count: int = 0
        self.failed_actions_count: int = 0
        self.action_counts: Dict[str, int] = {}

        # Initialize SQLite database schema
        self._init_db()

    # -----------------------------------------------------------------------
    # Database Initialization & SQLite Helpers
    # -----------------------------------------------------------------------
    def _init_db(self) -> None:
        """Create the database directory and initialize the sessions table if needed."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        start_time REAL NOT NULL,
                        end_time REAL NOT NULL,
                        duration_sec REAL NOT NULL,
                        total_gestures INTEGER NOT NULL,
                        most_used_gesture TEXT,
                        successful_actions INTEGER NOT NULL,
                        blocked_actions INTEGER NOT NULL,
                        failed_actions INTEGER NOT NULL,
                        unknown_gestures INTEGER NOT NULL,
                        gesture_counts_json TEXT NOT NULL,
                        action_counts_json TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time DESC)"
                )
                conn.commit()
            logger.debug("Initialized session history database at %s", self.db_path)
        except Exception as exc:
            logger.error("Failed to initialize SQLite history database at %s: %s", self.db_path, exc)

    # -----------------------------------------------------------------------
    # Real-Time Event Recording
    # -----------------------------------------------------------------------
    def record_gesture(self, gesture_name: str) -> bool:
        """
        Record a recognized gesture event with state-transition deduplication.

        Rules (Phase 8):
        - Only counts when transitioning into a new stabilized valid gesture.
        - Does NOT increment counts for every frame displaying the same gesture.
        - Momentary ambiguous/unknown poses do NOT re-arm the current gesture,
          preventing flicker from inflating counts while holding a gesture.
        - Confirmed tracking loss (GESTURE_NONE) resets transition state,
          allowing the same gesture to be counted again when the hand legitimately returns.
        - Transitions between distinct supported gestures count exactly once.

        Returns:
            True if a new distinct recognition event was counted, False otherwise.
        """
        if gesture_name in (GESTURE_NONE, ""):
            # Confirmed tracking loss: re-arm transition state
            self._last_stabilized_gesture = None
            self._last_counted_valid_gesture = None
            return False

        if gesture_name == GESTURE_UNKNOWN:
            if self._last_stabilized_gesture != GESTURE_UNKNOWN:
                self.unknown_gestures_count += 1
                self._last_stabilized_gesture = GESTURE_UNKNOWN
                return True
            return False

        if gesture_name in SUPPORTED_GESTURES:
            self._last_stabilized_gesture = gesture_name
            # Count only if it is a transition from no valid gesture or from a DIFFERENT valid gesture
            if gesture_name != self._last_counted_valid_gesture:
                self.gesture_counts[gesture_name] = self.gesture_counts.get(gesture_name, 0) + 1
                self.total_gestures_count += 1
                self._last_counted_valid_gesture = gesture_name
                logger.debug(
                    "Recorded gesture event '%s' (total: %d)",
                    gesture_name,
                    self.gesture_counts[gesture_name],
                )
                return True
            return False

        return False

    def record_action(self, action_name: str, success: bool, blocked: bool = False) -> None:
        """
        Record a system control action execution outcome.

        Args:
            action_name: The name of the action (e.g. "Play / Pause", "Next Track").
            success: Whether the system action adapter reported successful execution.
            blocked: Whether the action was blocked due to safety gates (controls disabled, cooldown).
        """
        if blocked:
            self.blocked_actions_count += 1
            logger.debug("Action '%s' blocked by safety checks (total blocked: %d)", action_name, self.blocked_actions_count)
            return

        if success:
            self.successful_actions_count += 1
            self.action_counts[action_name] = self.action_counts.get(action_name, 0) + 1
            logger.debug("Action '%s' executed successfully (total success: %d)", action_name, self.successful_actions_count)
        else:
            self.failed_actions_count += 1
            logger.debug("Action '%s' execution failed (total failed: %d)", action_name, self.failed_actions_count)

    # -----------------------------------------------------------------------
    # Metrics & Analytics Queries
    # -----------------------------------------------------------------------
    def get_most_used_gesture(self) -> Tuple[str, int]:
        """
        Identify the most frequently recognized gesture in the current session.

        Returns:
            Tuple of (gesture_name, count). Returns ("None", 0) if no gestures recorded.
        """
        if not self.gesture_counts:
            return ("None", 0)

        best_gesture, best_count = max(self.gesture_counts.items(), key=lambda item: item[1])
        if best_count <= 0:
            return ("None", 0)
        return (best_gesture, best_count)

    def get_session_duration(self) -> float:
        """Return current session duration in seconds."""
        if self.end_time is not None:
            return max(0.0, self.end_time - self.start_time)
        return max(0.0, time.time() - self.start_time)

    def get_current_session_record(self) -> SessionRecord:
        """Produce an immutable snapshot record of the active session."""
        now = time.time()
        duration = self.get_session_duration()
        most_gesture, _ = self.get_most_used_gesture()

        return SessionRecord(
            session_id=self.session_id,
            start_time=self.start_time,
            end_time=now if self.end_time is None else self.end_time,
            duration_sec=duration,
            total_gestures=self.total_gestures_count,
            most_used_gesture=most_gesture,
            successful_actions=self.successful_actions_count,
            blocked_actions=self.blocked_actions_count,
            failed_actions=self.failed_actions_count,
            unknown_gestures=self.unknown_gestures_count,
            gesture_counts=dict(self.gesture_counts),
            action_counts=dict(self.action_counts),
        )

    # -----------------------------------------------------------------------
    # Persistence: Save Session & History Retrieval
    # -----------------------------------------------------------------------
    def save_current_session(self) -> bool:
        """
        Persist the current session to the SQLite database upon shutdown or checkpoint.

        Prevents duplicate session insertion if called multiple times.
        """
        if self._is_saved:
            logger.debug("Session %s already saved to SQLite. Skipping duplicate.", self.session_id)
            return True

        if self.end_time is None:
            self.end_time = time.time()

        record = self.get_current_session_record()

        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO sessions (
                        id, start_time, end_time, duration_sec,
                        total_gestures, most_used_gesture,
                        successful_actions, blocked_actions, failed_actions,
                        unknown_gestures, gesture_counts_json, action_counts_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.session_id,
                        record.start_time,
                        record.end_time,
                        record.duration_sec,
                        record.total_gestures,
                        record.most_used_gesture,
                        record.successful_actions,
                        record.blocked_actions,
                        record.failed_actions,
                        record.unknown_gestures,
                        json.dumps(record.gesture_counts),
                        json.dumps(record.action_counts),
                    ),
                )
                conn.commit()

            self._is_saved = True
            logger.info("Successfully persisted session %s to history database.", self.session_id)
            return True

        except Exception as exc:
            logger.error("Failed to save session %s to SQLite: %s", self.session_id, exc)
            return False

    def get_history(self, limit: int = 50) -> List[SessionRecord]:
        """
        Load historical sessions ordered newest first.

        Handles empty databases gracefully by returning an empty list.
        """
        if not self.db_path.exists():
            return []

        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, start_time, end_time, duration_sec,
                           total_gestures, most_used_gesture,
                           successful_actions, blocked_actions, failed_actions,
                           unknown_gestures, gesture_counts_json, action_counts_json
                    FROM sessions
                    ORDER BY start_time DESC
                    LIMIT ?
                    """,
                    (max(1, int(limit)),),
                )
                rows = cursor.fetchall()

            return [SessionRecord.from_row(row) for row in rows]

        except Exception as exc:
            logger.error("Error reading session history from SQLite: %s", exc)
            return []

    def get_session_by_id(self, session_id: str) -> Optional[SessionRecord]:
        """Query and return a specific historical session by ID."""
        if not self.db_path.exists():
            return None

        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, start_time, end_time, duration_sec,
                           total_gestures, most_used_gesture,
                           successful_actions, blocked_actions, failed_actions,
                           unknown_gestures, gesture_counts_json, action_counts_json
                    FROM sessions
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (session_id,),
                )
                row = cursor.fetchone()

            if row is not None:
                return SessionRecord.from_row(row)
            return None

        except Exception as exc:
            logger.error("Error loading session %s: %s", session_id, exc)
            return None

    def clear_history(self) -> bool:
        """Clear historical sessions from database (useful for testing and reset)."""
        if not self.db_path.exists():
            return True

        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("DELETE FROM sessions")
                conn.commit()
            logger.info("Cleared session history from %s", self.db_path)
            return True
        except Exception as exc:
            logger.error("Error clearing session history: %s", exc)
            return False
