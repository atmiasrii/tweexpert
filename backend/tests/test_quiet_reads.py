"""Quiet hours quiet the reads, not only the writes."""
from __future__ import annotations

from quill.db.settings_store import set_setting
from quill.governor import governor
from quill.pipeline import watcher


def _quiet_now(session, on: bool):
    now = governor.local_now()
    day = governor.get_day(session)
    day.quiet_drift_min = 0
    session.add(day)
    if on:
        set_setting(session, "quiet_start", f"{(now.hour - 1) % 24:02d}:00")
        set_setting(session, "quiet_end", f"{(now.hour + 1) % 24:02d}:59")
    else:
        set_setting(session, "quiet_start", f"{(now.hour + 3) % 24:02d}:00")
        set_setting(session, "quiet_end", f"{(now.hour + 3) % 24:02d}:01")
    session.commit()


def test_the_timeline_is_not_read_during_quiet_hours(session, monkeypatch):
    _quiet_now(session, on=True)
    called = []
    monkeypatch.setattr(watcher, "sweep_home", lambda s: called.append(1) or {})
    out = watcher.watch_all(session)
    assert out == {"skipped": "quiet hours"}
    assert called == [], "no browser read should happen at night"


def test_the_timeline_is_read_outside_quiet_hours(session, monkeypatch):
    _quiet_now(session, on=False)
    called = []
    monkeypatch.setattr(watcher, "sweep_home",
                        lambda s: called.append(1) or {"polled": 0, "queued": 0, "discarded": 0})
    watcher.watch_all(session)
    assert called == [1]
