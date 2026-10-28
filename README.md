# Hand Gesture Controller 🖐️💻
### Phase 8: Gesture Persistence Fix, Tracking Loss Grace Lifecycle & Reliability Audit

A production-grade, highly modular desktop application built in Python that interfaces with your webcam to track 21 hand landmarks across up to two hands in real time, classifies hand poses with temporal stabilization, safely maps recognized gestures to macOS system controls, provides persistent settings and sensitivity tuning, and tracks comprehensive real-time gesture statistics and historical session analytics in a local SQLite database.

Developed on macOS (MacBook) using **OpenCV**, **Google MediaPipe**, **Tkinter**, **SQLite3**, and **CoreGraphics / AppleScript**.

> **Comprehensive Academic Report:** For the full college examination and project documentation, see [PROJECT_REPORT.md](file:///Users/dheerajahlawat/Desktop/hand%20gesture%20mini%20project%20python/PROJECT_REPORT.md).

---

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [Project Architecture](#project-architecture)
3. [Phase 7 Final QA & Bug Fixes](#phase-7-final-qa--bug-fixes)
4. [Phase 6 Statistics & Visual Analytics](#phase-6-statistics--visual-analytics)
5. [Session History & SQLite Storage](#session-history--sqlite-storage)
6. [Privacy & Performance Architecture](#privacy--performance-architecture)
7. [Phase 5 Customization & Persistent Settings](#phase-5-customization--persistent-settings)
8. [Supported System Actions & Default Mappings](#supported-system-actions--default-mappings)
9. [How to Enable, Disable, and Emergency Stop Controls](#how-to-enable-disable-and-emergency-stop-controls)
10. [macOS Permissions & Requirements](#macos-permissions--requirements)
11. [Setup & Installation](#setup--installation)
12. [Running the Application](#running-the-application)
13. [Testing & Verification (109 Tests)](#testing--verification)
14. [Phase 8 Reliability Audit & Performance](#phase-8-reliability-audit--performance)
15. [College Demonstration Workflow & Viva Prep](#college-demonstration-workflow)
16. [Known Limitations](#known-limitations)

---

## 🚀 Project Overview

The **Hand Gesture Controller** allows users to interact with their computer using natural hand movements captured by a webcam.

- **Phase 1** established the non-blocking camera capture pipeline, Tkinter desktop dashboard, and safe lifecycle architecture.
- **Phase 2** added real-time AI perception (dual-API MediaPipe, 21 3D landmarks per hand, neon cyan skeletal rendering).
- **Phase 3** implemented the **Gesture Recognition Engine** (9 gestures, Euclidean spread ratio disambiguation, temporal majority-voting smoothing).
- **Phase 4** introduced modular **Gesture-Based System Controls** (safety-first defaults, edge-triggering, cooldown debouncing, volume pinch, virtual mouse, emergency stop).
- **Phase 5** introduced **Customization & Persistent Settings** (atomic JSON persistence, corrupted file recovery with `.json.bak`, dynamic runtime updates).
- **Phase 6** introduced **Statistics, Session History & Visual Analytics** (strict event deduplication, distinct metric tracking, SQLite database persistence, native Canvas bar chart).
- **Phase 7** delivered **Final QA, Bug Fixes & College Viva Documentation** (89 unit/integration tests, edge case hardening).
- **Phase 8** resolves **Gesture Persistence & Tracking Loss** (tracking loss grace period lifecycle of 5 frames / 160ms, driver buffer queue latency fix with `CAP_PROP_BUFFERSIZE = 1`, UI frame update deduplication, metric label clarification, and 20 dedicated reliability regression tests totaling 109 passing tests).
- **Phase 7 (Current & Final)** delivers **Final QA, Bug Fixes, Security Audit & Viva Preparation**:
  - **Camera Stream Fault Tolerance:** Wrapped frame hand detector calls in isolated try/except blocks so transient MediaPipe processing exceptions on isolated frames do not abort the camera capture worker.
  - **Security Audit:** Certified that gesture mappings and action parameters strictly reject arbitrary shell commands, subshells (`$(...)`, `` `...` ``), and code injection.
  - **Full Regression Testing:** Expanded test suite to **89 automated tests** with 100% pass rate.
  - **Demonstration & Viva Documentation:** Created comprehensive [PROJECT_REPORT.md](file:///Users/dheerajahlawat/Desktop/hand%20gesture%20mini%20project%20python/PROJECT_REPORT.md) containing architecture breakdowns, theoretical foundations, demo workflows, and expected viva Q&A.

---

## 📁 Project Architecture

The codebase maintains strict separation of concerns across all modules:

```
hand gesture mini project python/
├── main.py                     # Application entry point & CLI parser
├── requirements.txt            # Python dependencies (OpenCV, MediaPipe, Pillow, NumPy, Pytest)
├── README.md                   # Project documentation & macOS guide
├── .gitignore                  # Git ignore configuration
│
├── app/
│   ├── __init__.py             # Package initializer
│   ├── config.py               # UI dimensions, theme colors, action thresholds & settings
│   ├── camera.py               # Non-blocking OpenCV CameraService & worker thread
│   ├── detector.py             # MediaPipe HandDetector (Tasks & Solutions dual-support)
│   ├── gesture_recognizer.py   # Normalized geometric classifier & temporal stabilizer
│   ├── control_manager.py      # Action dispatching, safety gates, volume & virtual mouse
│   ├── settings_manager.py     # Persistent settings manager, JSON storage, validation
│   ├── statistics_manager.py   # Phase 6: Session metrics, deduplication & SQLite history
│   ├── ui.py                   # Modern dark Tkinter GUI, canvas renderer, Settings & Analytics dialogs
│   └── models/                 # Local MediaPipe task models
│       └── hand_landmarker.task
│
└── tests/
    ├── __init__.py
    ├── test_config.py          # Config constants, thresholds, & hex color validation
    ├── test_camera.py          # Camera lifecycle, tracking metrics & safe shutdown
    ├── test_detector.py        # HandDetector, status formatting, connections & blank frame tests
    ├── test_gesture_recognizer.py # 14 tests: 9 gestures, unknown poses, smoothing, priority
    ├── test_control_manager.py # 13 tests: actions, edge-triggering, cooldowns, volume, mouse
    ├── test_settings_manager.py# 14 tests: default settings, atomic saves, malformed fallback, validation
    ├── test_statistics_manager.py # 16 tests: deduplication, duration, SQLite persistence, history, charts
    ├── test_imports.py         # Ensures importing modules has zero side-effects
    └── test_ui.py              # Widget hierarchy, action toggles, settings & analytics dialogs
```

---

## 🎮 Phase 4 System Controls Engine

The `ControlManager` (`app/control_manager.py`) enforces strict safety checks before any system action is dispatched:

1. **Safety Gates**:
   - **Controls Enabled Check**: Controls default to `False`. No actions execute until explicitly toggled on.
   - **Active Stream Check**: Camera must be running and actively tracking a hand (`detected_hands_count > 0`).
   - **Valid Gesture Check**: Actions never fire for `Unknown Gesture` or `Waiting for hand...`.
2. **Edge-Triggered Execution & Cooldown**:
   - **Edge-Triggering**: Holding a gesture only fires the action **once**. The user must release or transition to another pose before the action can re-arm.
   - **Action Cooldown**: Configurable debouncing period (`ACTION_COOLDOWN_SEC = 1.0s`) prevents accidental double-triggers.
3. **Continuous Volume Pinch**:
   - Computes normalized Euclidean pinch distance between thumb tip (landmark 4) and index tip (landmark 8) divided by palm reference scale ($\text{palm\_ref} = \|\text{landmark}_0 - \text{landmark}_9\|_2$).
   - Linearly maps normalized ratio $[0.20, 0.90]$ to $0\%-100\%$ volume.
   - Applies Exponential Moving Average (EMA) smoothing ($\alpha = 0.30$).
   - Hysteresis filter: Updates macOS volume only when change $\ge 3\%$ and rate-limited to at most once per $150\text{ms}$.
4. **Virtual Mouse**:
   - Maps normalized index fingertip position to screen resolution with horizontal mirroring.
   - Active boundary margins ($15\%$ margins) allow comfortable navigation to all corners without moving hand off camera.
   - Left-click detected via thumb-index pinch ($\text{ratio} < 0.28$) with release threshold ($\text{ratio} > 0.38$) to prevent repeated clicks.
   - Requires macOS Accessibility permissions. If permissions are missing, reports clear user instructions without crashing.

---

## 📊 Phase 6 Statistics, Session History & Visual Analytics

Phase 6 provides comprehensive session telemetry, visual analytics, and historical session logs to evaluate gesture recognition frequency, system action reliability, and user interaction patterns.

### 1. Available Statistics
The `StatisticsManager` (`app/statistics_manager.py`) tracks:
- **Total Recognized Gestures**: Count of distinct gesture recognition events across all 9 supported gestures.
- **Per-Gesture Counts**: Frequency breakdown for each individual gesture (`Open Palm`, `Fist`, `Thumbs Up`, `Peace Sign`, `One Finger`, `Two Fingers`, `Three Fingers`, `Four Fingers`, `Five Fingers`).
- **Most Frequently Recognized Gesture**: Automatically computed gesture and count (e.g. `Peace Sign (18)`).
- **Session Duration**: Real-time timer calculation from session start to shutdown (formatted as `MM:SS` or `HH:MM:SS`).
- **System Action Execution Outcomes**:
  - **Successful Actions**: System control events confirmed executed by the action adapter (e.g., media playback toggled, track changed, volume updated, or virtual mouse clicked).
  - **Blocked Actions**: Actions requested by recognized gestures that were prevented due to safety gates (controls disabled by the user) or cooldown debounce locks.
  - **Failed Actions**: Action execution attempts where the underlying operating system returned an error.
- **Unknown Gesture Count**: Transitional or ambiguous hand poses recognized before stabilization.

### 2. Strict Event Deduplication (No Per-Frame Counting)
A critical rule of the statistics engine is that **webcam frames are never counted as separate gesture events**:
- Holding a static gesture for 30 seconds at 30 FPS displays 900 consecutive video frames, but increments the gesture count **only once**.
- A new event is counted only when the stabilized recognition state changes to another valid gesture.
- When the hand is retracted or tracking is temporarily lost (`Waiting for hand...`), the deduplication state resets. When the hand returns to the camera view, it is accurately registered as a new recognition event.

### 3. Session History & Local SQLite Storage
Session data is persisted locally across application restarts using standard Python `sqlite3`:
- **Storage Location (macOS)**: `~/Library/Application Support/HandGestureController/history.db`
- **Linux/Cross-Platform**: `~/.hand_gesture_controller/history.db`
- **Database Schema**:
  - `sessions` table storing: `id`, `start_time`, `end_time`, `duration_sec`, `total_gestures`, `most_used_gesture`, `successful_actions`, `blocked_actions`, `failed_actions`, `unknown_gestures`, `gesture_counts_json`, `action_counts_json`.
  - Indexed by `start_time DESC` for instant newest-first retrieval.
- **Duplicate-Save Prevention**: The manager utilizes an internal `_is_saved` atomic flag ensuring multiple calls to `save_current_session()` never write duplicate session rows.
- **Safe Graceful Shutdown**: The active session is automatically checkpointed to SQLite during normal window exit (`on_close`).

### 4. Visual Analytics Dashboard
Accessible via the **`📊 Analytics`** button in the header bar or the **`📊 View Analytics & History`** button in the Metrics card:
- **Overview & Charts Tab**:
  - **Session Selector Dropdown**: Switch between the live active session and any past recorded session with a single click.
  - **Quick Action**: Click `↺ Return to Live Session` to immediately return to real-time monitoring.
  - **KPI Metrics Tiles**: Instant visual cards for Duration, Total Gestures, Top Gesture, and Action Success/Blocked totals.
  - **Native Canvas Bar Chart**: Custom-rendered horizontal bar distribution showing frequencies and percentages for all 9 gestures.
    - *Zero Dummy Data*: Displays true collected statistics; shows an elegant empty state message when no gestures have been recorded yet.
  - **Actions Summary & Safety Breakdown**: Visual status badges for Successful (green), Blocked (amber), and Failed (red) action executions.
- **Session History Tab**:
  - Chronological list of completed past sessions with date, time, duration, top gesture, and actions summary.
  - Click `🔍 View Details` on any historical card to inspect its full gesture breakdown and chart.
  - Empty history fallback banner when first launched.
  - Database path display and `🗑 Clear History` maintenance button.
- **Compare Sessions Tab**:
  - Compare any two sessions (e.g. Session A vs Session B).
  - Side-by-side KPI cards and a comparative gesture frequency table showing exact count differences (`+N` / `-N`).

### 5. Privacy & Performance Guarantees
- **No Video Recording or Image Storage**: Webcam frames are strictly processed in volatile memory for MediaPipe perception and discarded immediately. No photos, video files, or screenshots are ever stored.
- **Zero Frame-by-Frame Database Writes**: Statistics collection occurs entirely in RAM during video streaming. SQLite disk writes occur only on graceful application shutdown, keeping the camera stream at a rock-solid 30 FPS.
- **No Keylogging or Background Desktop Surveillance**: The controller only interacts with the macOS operating system when recognized gestures map to user-configured actions.

---

## ⚙️ Phase 5 Customization & Persistent Settings

Phase 5 introduces a centralized preference architecture that lets users tailor the controller to their environment, webcam characteristics, and personal gesture habits.

### 1. Where Preferences Are Stored
Preferences are serialized in clean, human-readable JSON format and stored in the user-writable application data directory:
- **macOS**: `~/Library/Application Support/HandGestureController/settings.json`
- **Linux/Cross-Platform**: `~/.hand_gesture_controller/settings.json`

**Key Persistence Features**:
- **Atomic File Writing**: Configuration changes are written to a temporary file (`.settings.json.tmp.<pid>`) in the target directory and atomically swapped into place via `os.replace`. This eliminates corrupted or partial writes.
- **Auto-Recovery & Corruption Protection**: If a settings file is missing, empty, or corrupted by manual editing, the application automatically preserves the damaged file as `settings.json.bak` and regenerates a clean configuration with safe defaults.
- **Privacy & Security**: Only numerical sensitivity bounds and mapped action strings are stored. No passwords, credentials, or personal telemetry are ever written.

---

### 2. How to Customize Gesture Mappings
1. Open the Settings dialog by clicking **`⚙ Settings`** in the top navigation header, or **`⚙ Configure Mappings & Sensitivity`** inside the **SYSTEM CONTROLS** card.
2. Select the **`🎯 Gesture Mappings`** tab.
3. Every recognized gesture has an individual dropdown menu listing all supported system actions:
   - `None` (Disables action execution for this gesture)
   - `Play / Pause` (Toggles playback in Apple Music / Spotify)
   - `Next Track` (Skips to the next track)
   - `Previous Track` (Returns to previous track)
   - `Continuous Volume` (Enables thumb-index volume pinch)
   - `Mute / Unmute` (Toggles system audio mute)
4. Select your preferred action for each gesture and click **`💾 Save & Apply Settings`**.
5. The mappings are validated and applied immediately to the active recognition and control pipeline without restarting the camera or application.

---

### 3. How to Reset Settings to Factory Defaults
- Open the Settings dialog.
- Click the **`↺ Reset Defaults`** button in the lower-left corner.
- All 9 gesture mappings and all 11 sensitivity sliders will immediately revert to conservative factory default values and persist to disk.

---

## ⚡ Sensitivity & Cooldown Settings Explained

The **`⚡ Sensitivity & Timing`** tab allows fine-grained calibration across three critical subsystems:

### 1. Gesture Recognition & Filtering
- **Gesture History Length** (`3` – `20` frames, default: `7`):
  Number of recent consecutive frames stored in the temporal majority-vote buffer. Higher values provide maximum stabilization against camera noise or lighting flickers, while lower values offer snappier response.
- **Min Consistent Predictions** (`2` – `15` frames, default: `4`):
  Agreement threshold required within the history buffer before the engine accepts a gesture transition. Prevents transitional hand poses from misfiring.
- **Gesture Switch Debounce** (`0.10` – `3.00`s, default: `0.50`s):
  Minimum time delay enforced before the stable gesture state can transition to a new gesture.

### 2. Action Timing & Volume Sensitivity
- **Action Trigger Cooldown** (`0.10` – `5.00`s, default: `1.00`s):
  Debounce period between discrete action executions (e.g. Next Track or Play/Pause). Enforces edge-triggered safety so holding a pose does not flood commands.
- **Volume Sensitivity Step** (`1%` – `20%`, default: `3%`):
  Hysteresis threshold. The system output volume is only updated when the smoothed volume changes by at least this percentage.
- **Volume Update Interval** (`0.05` – `1.00`s, default: `0.15`s):
  Rate-limiting throttle period between consecutive macOS volume adjustments.
- **Volume Smoothing (Alpha)** (`0.05` – `0.95`, default: `0.30`):
  Exponential Moving Average (EMA) coefficient for continuous pinch volume. Lower values produce buttery smooth transitions; higher values yield instantaneous tracking.

### 3. Virtual Mouse Sensitivity
- **Mouse Smoothing (Alpha)** (`0.05` – `0.95`, default: `0.35`):
  EMA smoothing factor for desktop cursor positioning. Mitigates natural physiological hand tremors.
- **Pinch Click Threshold** (`0.10` – `0.50`, default: `0.28`):
  Normalized thumb-to-index Euclidean distance relative to palm size that triggers a left-click.
- **Pinch Release Threshold** (`0.20` – `0.70`, default: `0.38`):
  Normalized pinch distance required to release and re-arm the click mechanism. Enforces hysteresis to prevent click stutter.
- **Mouse Click Cooldown** (`0.10` – `2.00`s, default: `0.40`s):
  Minimum delay between consecutive hardware mouse clicks.

---

## 🎛️ Supported System Actions & Default Mappings

To minimize accidental activation, resting poses (`Open Palm`, `Fist`) do **not** trigger destructive actions by default:

| Gesture | Default Mapped Action | Subsystem | Behavior |
|---|---|---|---|
| **Thumbs Up** | `Play / Pause` | macOS Media | Toggles playback in Apple Music or Spotify |
| **Three Fingers** | `Next Track` | macOS Media | Skips to the next track in Music or Spotify |
| **Four Fingers** | `Previous Track` | macOS Media | Skips to previous track in Music or Spotify |
| **Peace Sign** | `Continuous Volume` | macOS Audio | Pinch thumb and index to adjust system volume smoothly |
| **One Finger** | *(Cursor Pointer)* | Virtual Mouse | When Mouse is enabled, moves cursor; pinch to click |
| **Fist** | `None` | Safe Rest | Resting pose (no action fired) |
| **Open Palm** | `None` | Safe Rest | Resting pose (no action fired) |
| **Two Fingers** | `None` | Configurable | Available for custom user mapping |
| **Five Fingers** | `None` | Safe Rest | Resting pose (no action fired) |

---

## 🛡️ How to Enable, Disable, and Emergency Stop Controls

1. **Controls Default to Disabled**:
   - When the application starts, system controls and virtual mouse are disabled (`Safe Mode`).
2. **Enabling Controls**:
   - In Card 4 (**SYSTEM CONTROLS**), click **Enable Controls**. The button turns emerald green (`Controls: ACTIVE`).
   - To activate the cursor pointer, click **Enable Mouse**. The button turns cyan (`Mouse: ACTIVE`).
3. **Emergency Stop Actions**:
   - Click the red **🛑 Emergency Stop Actions** button in Card 4, or
   - Press the **`Escape`** key on your keyboard.
   - This immediately disables all system controls, turns off virtual mouse, and resets continuous volume/pinch states.

---

## 🔐 macOS Permissions & Requirements

macOS security requires explicit permissions for camera, automation, and accessibility:

1. **Camera Permission**:
   - Required to capture webcam frames.
   - Location: **System Settings > Privacy & Security > Camera** -> Enable for **Visual Studio Code** or **Terminal**.
2. **Automation / AppleScript Permission**:
   - Required for media player playback control (Music / Spotify) and volume adjustments.
   - Handled automatically via `osascript`. If prompted by macOS, select **Allow**.
3. **Accessibility Permission (for Virtual Mouse clicks)**:
   - Required by macOS for hardware mouse click generation (`CGEventPost`).
   - Location: **System Settings > Privacy & Security > Accessibility** -> Enable for **Visual Studio Code** or **Terminal**.
   - If Accessibility is not enabled, the UI displays a clear notice: `⚠️ Accessibility Permission Needed for Clicks`. Cursor movement remains functional.

---

## 💻 Prerequisites & Environment

- **Operating System**: macOS 12+ (tested on Apple Silicon MacBook M2).
- **Python Version**: Python 3.10+ (tested on Python 3.14.9).
- **Webcam**: Built-in FaceTime HD Camera or external USB webcam.
- **Virtual Environment**: Python `venv`.

---

## ⚙️ Setup & Installation

### 1. Open the project folder
```bash
cd "/Users/dheerajahlawat/Desktop/hand gesture mini project python"
```

### 2. Activate Virtual Environment
```bash
source .venv/bin/activate
```
*(Your terminal prompt should show `(.venv)`).*

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## ▶️ Running the Application

Ensure the virtual environment is activated:
```bash
source .venv/bin/activate
```

### Run with default webcam (Device 0):
```bash
python main.py
```

### Run with a specific camera index:
```bash
python main.py --camera-index 1
```

### Run with debug logging:
```bash
python main.py --debug
```

### Keyboard Shortcuts:
- **`Spacebar`**: Toggle Start / Stop Camera.
- **`Escape`**: Stop Camera & Emergency Stop all System Controls.

---

## 🧪 Testing & Verification

Run the full automated test suite (84 tests) using `pytest`:

```bash
source .venv/bin/activate
pytest -v
```

### Test Suite Coverage (84 Tests, 100% Passing):
1. `tests/test_statistics_manager.py` (14 tests):
   - Initial state clean initialization (zero counts, valid session ID, non-negative duration).
   - SessionRecord formatting (`duration_formatted` as MM:SS, start timestamp formatted).
## 🧪 Testing & Verification

Run the full automated test suite (89 tests) using `pytest`:

```bash
source .venv/bin/activate
pytest -v
```

### Test Suite Coverage (89 Tests, 100% Passing):
1. `tests/test_camera.py` (7 tests):
   - Initial state clean initialization (zero counts, stopped status, empty landmark buffers).
   - Safe no-op stop when camera is already inactive.
   - Camera device index modification while stopped.
   - Invalid or disconnected camera index graceful error handling.
   - Prevention of duplicate background capture threads on rapid repeated starts.
   - Repeated start/stop stress cycling without resource leaks.
   - Hand detector frame exception resilience (transient processing errors degrade to scanning rather than terminating capture thread).
2. `tests/test_control_manager.py` (14 tests):
   - System controls disabled by default (safe mode).
   - Virtual mouse disabled by default.
   - No actions execute when controls are disabled, even with valid gestures.
   - Camera stopped or tracking loss safety gates.
   - Rejection of unknown poses and empty gestures.
   - Discrete action execution and edge-triggering (holding gesture does not repeatedly fire).
   - Action cooldown and re-arming after gesture transitions.
   - Custom mappings and fallback for invalid action names.
   - Continuous volume pinch normalization, palm reference scaling, and smoothing.
   - Virtual mouse coordinate mapping and smoothing.
   - Virtual mouse click debouncing, release hysteresis, and cooldown.
   - Graceful handling of missing macOS Accessibility permissions.
   - Emergency stop mechanism immediately disables all controls and resets states.
   - Arbitrary shell commands, subshell injections (`$(...)`, `` `...` ``), and code strings in mappings strictly rejected.
3. `tests/test_settings_manager.py` (16 tests):
   - First launch creates and persists clean default settings.
   - Saving preferences and reloading in isolated manager instances.
   - Malformed/corrupted JSON handling, automatic `.json.bak` generation, and safe fallback.
   - Empty file handling and non-dict JSON root handling.
   - Out-of-bounds numerical value clamping.
   - Consistency constraints (min_consistent cannot exceed history_length).
   - Rejection of unsupported actions and malicious command strings.
   - Validation reporting of illegal values with descriptive error messages.
   - Reset-to-defaults functionality and persistent file update.
   - Independent safety controls non-persistence (controls default to disabled on launch).
   - Dynamic application to running GestureRecognizer and ControlManager in-place.
   - Default settings path cross-platform resolution.
   - Roundtrip serialization/deserialization between `to_dict()` and `from_dict()`.
   - Automatic adjustment of mouse release threshold above click threshold.
   - Negative and extreme cooldown values safely clamped to boundaries.
   - Non-numeric / invalid type setting values gracefully fallback to defaults.
4. `tests/test_statistics_manager.py` (16 tests):
   - Initial state clean initialization (zero counts, valid session ID, non-negative duration).
   - SessionRecord formatting (`duration_formatted` as MM:SS, start timestamp formatted).
   - Strict gesture event deduplication (100 consecutive frames of same gesture increment count only once).
   - Transition between distinct recognized gestures.
   - Gesture re-entry after tracking loss (`Waiting for hand...` resets state to allow returning gesture).
   - Unknown gesture count tracking and frame deduplication.
   - Separate tracking of successful, blocked, and failed system action outcomes.
   - Most frequently recognized gesture computation.
   - SQLite session persistence, retrieval, and querying by session ID.
   - Prevention of duplicate session row insertion on repeated save calls.
   - Graceful handling of empty session history database.
   - Historical sessions ordering newest-first (`ORDER BY start_time DESC`).
   - SQLite history reset (`clear_history`).
   - Integration with `ControlManager` recording action results into `StatisticsManager`.
   - Complete separation between active in-memory session and historical database records.
   - Accurate chart data generation without dummy/invented data.
5. `tests/test_gesture_recognizer.py` (14 tests):
   - All 9 supported gestures tested using synthetic landmark geometry.
   - Priority disambiguation (Peace Sign vs. Two Fingers, Open Palm vs. Five Fingers).
   - Ambiguous poses classified as Unknown Gesture.
   - Left-hand and right-hand mirror calculations.
   - Temporal majority voting consistency threshold transitions and history resets.
6. `tests/test_detector.py` (8 tests):
   - Hand detector initialization and landmark drawing.
   - Blank and empty frame safety.
   - Skeletal connections integrity.
   - Short-list and malformed landmark safety.
7. `tests/test_config.py` (9 tests):
   - Theme hex colors, window dimensions, and camera defaults.
   - Phase 7 metadata, constants, and history/settings file paths.
   - Supported gestures and actions registration.
8. `tests/test_ui.py` (4 tests):
   - Initial widget hierarchy and Phase 6/7 analytics buttons.
   - Camera status badge transitions and colors.
   - SettingsDialog modal integration, tab switching, custom mapping changes, live slider updates, saving, and defaults reset.
   - AnalyticsDialog modal integration, tab switching, live metric refresh, session return, and Canvas bar chart rendering for empty and populated datasets.
9. `tests/test_imports.py` (1 test):
   - Clean imports with zero side-effects across all modules.
10. `tests/test_tracking_reliability.py` (20 tests):
   - Gesture count stability across 30 sustained hold frames (zero runaway accumulation).
   - Clean increment on transition to different valid gestures.
   - 1-frame camera drop resilience within grace period (no double-counting on return).
   - Sustained tracking loss exceeding grace period cleanly transitions active gesture to None.
   - Hand re-entry after confirmed tracking loss increments count predictably (+1).
   - N repeated hand re-entry cycles yield exactly N gesture counts.
   - Hand removal immediately resets continuous controls (virtual mouse dragging, volume pinch).
   - Hand removal leaves zero stale landmarks drawn on preview canvas.
   - Camera stop cleanly resets tracking metrics, active gesture, and continuous locks.
   - Camera restart initializes in a clean no-hand state without phantom detection.
   - UI frame polling deduplication skips duplicate renders on unchanged camera frames.
   - Grace period parameter configurability and boundary clamping.
   - Handedness invariance (both hands recognized and deduplicated identically).
   - Unknown pose jitter does not cause double-counting on recovery.
   - Continuous unknown pose does not runaway accumulate event counts.
   - StatisticsManager rapid transitions and most-used gesture computation.
   - UI metric tile binding to session total gestures count.
   - Emergency stop continuous control reset and immediate lockout.
   - Multi-hand tracking fluctuation safety.
   - SQLite session persistence with exact gesture counts.

```bash
# Run the complete test suite (109 passing tests)
./.venv/bin/pytest -v
```

---

## ⚡ Phase 8 Reliability Audit & Performance

### Bug 1 Root Cause Analysis & Architecture Fixes
1. **Flicker Double-Counting:** Previously, single-frame detection drops immediately sent `GESTURE_NONE` to `StatisticsManager`, resetting transition memory and double-counting when the hand reappeared 16 ms later. Fixed via `TRACKING_LOSS_GRACE_FRAMES = 5` (~160 ms): live hand count is 0 immediately, but transition state is preserved during brief transient drops.
2. **Recognizer Sticky Gestures:** Majority voting fallback now switches to `Unknown Gesture` if the active gesture has 0 votes remaining in history, preventing stale poses from persisting indefinitely.
3. **OpenCV Buffer Queue Buildup:** Enforced `cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)` to eliminate driver frame queue latency on macOS AVFoundation.
4. **UI Polling Loop Duplication:** `AppUI._update_frame_loop()` now checks `_last_processed_frame_count` to skip duplicate processing and rendering when camera frames have not updated.
5. **Metric Semantics Clarity:** Metric card Tile 2 is now explicitly labeled `"Gesture Events (Session)"` showing `self.statistics_manager.total_gestures_count`, while live classifier status is clearly indicated by `"Active Gesture Status"`.

### Apple M2 Silicon Real Hardware Benchmarks
- **Average Inference Latency:** `15.56 ms` (~64 FPS inference capability)
- **Minimum Inference Latency:** `13.19 ms`
- **Frame Retrieval Latency:** `0.14 ms`
- **Webcam Resolution:** `1280x720` / `1920x1080` at native `30.0 FPS`
- **Total Passing Automated Tests:** **109 passed in 9.04s** (0 failures, 0 warnings)

---

## 🎓 College Demonstration Workflow & Viva Prep

### 7-Step Demonstration Plan:
1. **Launch:** Run `python main.py`. Point out that the camera is completely OFF on launch (Privacy-First default).
2. **Start Camera:** Click **"Start Camera"** (or press `Spacebar`). Demonstrate live 30 FPS webcam preview and dark navy dashboard layout.
3. **Skeletal Tracking:** Hold your hand up. Point out the neon cyan joint circles and electric blue bone connections tracking all 21 3D landmarks in real time.
4. **Gesture Disambiguation:** Sequentially demonstrate distinct gestures:
   - *Fist* $\rightarrow$ *One Finger* $\rightarrow$ *Peace Sign* (fingers apart) vs. *Two Fingers* (fingers together) $\rightarrow$ *Open Palm* (fingers spread) vs. *Five Fingers* $\rightarrow$ *Thumbs Up*.
   - Emphasize that majority-vote smoothing eliminates flickering.
5. **System Controls & Safety:**
   - Make a gesture with controls disabled: show that nothing fires.
   - Click **"Enable System Controls"** and demonstrate Play/Pause or Volume Pinch.
   - Press `Escape` to demonstrate the instant **Emergency Stop**.
6. **Custom Settings:** Open **Preferences**. Change a gesture mapping or slider, save, and show that changes apply immediately without restarting.
7. **Session Analytics:** Open **Session Analytics**. Show the KPI cards, the horizontal frequency bar chart on the native Tkinter Canvas, and the persistent SQLite session history.

> **Full Viva Guide:** For detailed theory, algorithmic formulas, and comprehensive Q&A, refer to [PROJECT_REPORT.md](file:///Users/dheerajahlawat/Desktop/hand%20gesture%20mini%20project%20python/PROJECT_REPORT.md).

---

## ⚠️ Known Limitations

1. **macOS Accessibility Sandbox**: Generating hardware mouse clicks via CoreGraphics requires Accessibility permissions in macOS System Settings. If not granted, clicks are safely blocked with clear UI feedback.
2. **Third-Party Media Players**: Native AppleScript media commands support Apple Music and Spotify. Web browser media players (e.g., YouTube in Safari/Chrome) require active browser tab focus.
3. **Lighting & Extreme Angles**: Severe hand rotation ($>60^\circ$) or extreme depth tilt can degrade MediaPipe landmark tracking precision below the 0.6 confidence threshold.
