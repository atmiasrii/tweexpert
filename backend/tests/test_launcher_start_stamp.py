"""The run's start time survives an API restart."""
from __future__ import annotations

from quill.db.settings_store import get_setting, set_setting
from quill.ops import launcher


def test_starting_nothing_leaves_the_start_time_alone(session, monkeypatch):
    """Autostart runs on every API boot. When both processes are already up it
    starts nothing, and it must not claim the run began just now."""
    monkeypatch.setattr(launcher, "running",
                        lambda s: {"worker": True, "browser": True})
    monkeypatch.setattr(launcher, "_spawn",
                        lambda *a, **k: pytest_fail("nothing should be spawned"))
    set_setting(session, "live_started_at", "2026-09-09T08:00:00+00:00")

    launcher.start(session)

    assert get_setting(session, "live_started_at") == "2026-09-09T08:00:00+00:00"


def test_actually_starting_a_process_stamps_the_time(session, monkeypatch):
    monkeypatch.setattr(launcher, "running",
                        lambda s: {"worker": False, "browser": True})
    monkeypatch.setattr(launcher, "_spawn", lambda name, engine: 4242)
    set_setting(session, "live_started_at", "2026-09-09T08:00:00+00:00")

    launcher.start(session)

    assert get_setting(session, "live_started_at") != "2026-09-09T08:00:00+00:00"


def pytest_fail(msg):
    raise AssertionError(msg)
