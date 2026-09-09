"""The supervisor keeps the unattended run alive, without thrashing Chromium."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from quill.db.settings_store import get_setting, set_setting
from quill.ops import supervisor


class _Launcher:
    """Stands in for ops.launcher so no process is ever spawned in a test."""

    def __init__(self, alive=None, live=True):
        self.alive = alive if alive is not None else {"worker": True, "browser": True}
        self.live = live
        self.started = 0
        self.terminated = []

    def is_live(self, session):
        return self.live

    def running(self, session):
        return dict(self.alive)

    def start(self, session, engine="playwright"):
        self.started += 1
        self.alive = {k: True for k in self.alive}
        return {"started": ["worker", "browser"]}

    def pid_of(self, session, name):
        return 1234

    def terminate(self, pid):
        self.terminated.append(pid)


def _wire(monkeypatch, lau, stale=()):
    monkeypatch.setattr(supervisor, "launcher", lau)
    monkeypatch.setattr(supervisor, "stale_processes", lambda s: list(stale))


def test_a_dead_process_is_restarted(session, monkeypatch):
    lau = _Launcher(alive={"worker": True, "browser": False})
    _wire(monkeypatch, lau)
    out = supervisor.tick(session)
    assert lau.started == 1
    assert out["restarted"] == ["browser"]


def test_a_wedged_process_is_terminated_before_restarting(session, monkeypatch):
    lau = _Launcher()
    _wire(monkeypatch, lau, stale=["browser"])
    supervisor.tick(session)
    assert lau.terminated == [1234], "a live but stale process must be killed first"
    assert lau.started == 1


def test_a_healthy_run_restarts_nothing(session, monkeypatch):
    lau = _Launcher()
    _wire(monkeypatch, lau)
    out = supervisor.tick(session)
    assert lau.started == 0
    assert out["restarted"] == []


def test_the_supervisor_does_nothing_when_the_operator_pressed_stop(session, monkeypatch):
    lau = _Launcher(alive={"worker": False, "browser": False}, live=False)
    _wire(monkeypatch, lau)
    out = supervisor.tick(session)
    assert lau.started == 0
    assert out.get("skipped") == "not live"


def test_the_browser_is_left_alone_while_the_login_window_is_open(session, monkeypatch):
    lau = _Launcher(alive={"worker": True, "browser": False})
    _wire(monkeypatch, lau)
    until = datetime.now(timezone.utc) + timedelta(minutes=10)
    set_setting(session, "login_window_until", until.isoformat())
    out = supervisor.tick(session)
    assert lau.started == 0, "restarting here would put two processes on the profile"
    assert out["restarted"] == []


def test_a_restart_is_not_repeated_inside_the_cooldown(session, monkeypatch):
    lau = _Launcher(alive={"worker": True, "browser": False})
    _wire(monkeypatch, lau)
    supervisor.tick(session)
    lau.alive["browser"] = False          # died again straight away
    supervisor.tick(session)
    assert lau.started == 1, "a crash loop must not become a restart loop"


def test_the_daily_ceiling_stops_restarting_and_alerts(session, monkeypatch):
    lau = _Launcher(alive={"worker": True, "browser": False})
    _wire(monkeypatch, lau)
    alerts = []
    monkeypatch.setattr(supervisor.notifier, "alert",
                        lambda kind, msg: alerts.append(kind))

    now = datetime.now(timezone.utc)
    for i in range(supervisor.RESTART_MAX_PER_PROC + 3):
        lau.alive["browser"] = False
        supervisor.tick(session, now=now + timedelta(minutes=10 * i))

    assert lau.started == supervisor.RESTART_MAX_PER_PROC
    assert alerts.count("worker_down") == 1, "the ceiling alert is sent once"


def test_the_run_record_logs_every_restart(session, monkeypatch):
    lau = _Launcher(alive={"worker": False, "browser": True})
    _wire(monkeypatch, lau)
    supervisor.tick(session)
    from quill.ops import run_session
    rec = get_setting(session, run_session.RUN_KEY, {})
    assert [r["process"] for r in rec["restarts"]] == ["worker"]
    assert rec["restarts"][0]["reason"] == "dead"
