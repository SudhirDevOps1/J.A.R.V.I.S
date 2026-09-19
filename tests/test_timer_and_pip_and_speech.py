"""
Test suite for Active Timer Countdown, PiP Dragging, Screen Troubleshooter, and EdgeTTS Speech Integration.
"""
from datetime import datetime, timedelta
import pytest

def test_timer_manager_lifecycle():
    from core.timer_manager import TimerManager, ActiveTimer
    
    tm = TimerManager.get_instance()
    
    # 1. Add timer
    now = datetime.now()
    tgt = now + timedelta(seconds=120)
    timer = tm.add_timer("test_timer_1", "Tea break", tgt, total_seconds=120, category="timer")
    
    assert timer.id == "test_timer_1"
    assert timer.message == "Tea break"
    assert timer.remaining_seconds > 0
    assert 0 <= timer.progress_percent <= 100
    assert ":" in timer.format_countdown()
    
    primary = tm.get_primary_countdown()
    assert primary is not None
    assert primary.id == "test_timer_1"
    
    # Clean up
    tm.cancel_timer("test_timer_1")
    assert tm.get_primary_countdown() is None or tm.get_primary_countdown().id != "test_timer_1"


def test_timer_manager_expiry():
    from core.timer_manager import TimerManager
    
    tm = TimerManager.get_instance()
    now = datetime.now()
    # Timer in the past (already expired)
    past_tgt = now - timedelta(seconds=2)
    tm.add_timer("test_expired_1", "Take medicine", past_tgt, total_seconds=10, category="alarm")
    
    expired = tm.check_and_trigger_expired()
    expired_ids = [t.id for t in expired]
    assert "test_expired_1" in expired_ids
    
    # Clean up
    tm.cancel_timer("test_expired_1")


def test_reminder_registers_active_timer():
    from actions.reminder import reminder
    from core.timer_manager import get_timer_manager
    
    res = reminder({"message": "Drink water", "time": "2 minutes"})
    assert "Reminder/Alarm set" in res
    
    active = get_timer_manager().get_active_timers()
    assert len(active) > 0
    found = any("Drink water" in t.message for t in active)
    assert found
    
    # Clean up created timer
    for t in active:
        if "Drink water" in t.message:
            get_timer_manager().cancel_timer(t.id)


def test_pip_window_has_draggable_header():
    from PyQt6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    
    from ui import PipWindow
    pip = PipWindow()
    
    assert hasattr(pip, "_header_bar")
    assert hasattr(pip, "_grip")
    assert hasattr(pip, "_pip_timer")
    assert hasattr(pip, "update_timer")
    assert hasattr(pip, "eventFilter")
    
    # Test update_timer
    pip.update_timer("04:30", True)
    assert not pip._pip_timer.isHidden()
    assert "04:30" in pip._pip_timer.text()
    
    pip.update_timer("", False)
    assert pip._pip_timer.isHidden()
    
    pip.close()


def test_screen_troubleshooter_active_window_integration():
    from actions.screen_troubleshooter import troubleshoot_screen
    
    # Should safely handle missing keys and active window detection without throwing
    res = troubleshoot_screen({"query": "Check code"})
    assert isinstance(res, str)
    assert len(res) > 0
