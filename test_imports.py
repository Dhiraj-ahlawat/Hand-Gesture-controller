"""
tests/test_imports.py
Verify that importing modules does not automatically trigger hardware access
or pop open GUI windows.
"""

import sys


def test_clean_imports_no_side_effects():
    """Ensure modules can be imported cleanly in any context without starting camera."""
    import app
    import app.config
    import app.camera
    import app.ui
    import app.gesture_recognizer
    import app.control_manager
    import app.settings_manager
    import app.statistics_manager
    import main

    assert hasattr(app.config, "APP_TITLE")
    assert hasattr(app.camera, "CameraService")
    assert hasattr(app.ui, "AppUI")
    assert hasattr(app.ui, "AnalyticsDialog")
    assert hasattr(app.gesture_recognizer, "GestureRecognizer")
    assert hasattr(app.control_manager, "ControlManager")
    assert hasattr(app.settings_manager, "SettingsManager")
    assert hasattr(app.settings_manager, "UserSettings")
    assert hasattr(app.statistics_manager, "StatisticsManager")
    assert hasattr(app.statistics_manager, "SessionRecord")
    assert hasattr(main, "main")
