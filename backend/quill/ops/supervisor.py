"""Keeps the unattended run alive.

Runs in the API process, which is the only one that outlives the worker and the
browser. The old watchdog lives inside the worker, so it can neither report a
dead worker nor restart anything; this morning `live_mode` was true with both
processes dead and nothing said so.

Restarting is deliberately reluctant. Chromium's profile directory takes
exactly one owner, and a lost X session is the one failure only a human can
undo, so the cost of restarting too eagerly is higher than the cost of
restarting late.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from ..db.settings_store import get_setting
from ..defaults import RESTART_COOLDOWN_S, RESTART_MAX_PER_PROC
from ..logging_setup import get_logger
from ..notify import notifier
from ..ops import launcher
from ..ops.health import stale_processes
from ..ops import run_session

log = get_logger("quill.supervisor")


def _login_window_open(session: Session, now: datetime) -> bool:
    """True while a hand sign-in owns the profile. `launcher.open_login` kills
    the browser process on purpose to hand Chromium over; restarting it here
    would put two processes on one profile."""
    until = get_setting(session, "login_window_until", None)
    if not until:
        return False
    try:
        when = datetime.fromisoformat(until)
    except ValueError:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return now < when


def _restarts_today(rec: dict, process: str) -> list[dict]:
    return [r for r in rec.get("restarts", []) if r.get("process") == process]


def _too_soon(rec: dict, process: str, now: datetime) -> bool:
    prior = _restarts_today(rec, process)
    if not prior:
        return False
    try:
        last = datetime.fromisoformat(prior[-1]["at"])
    except (ValueError, KeyError):
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last) < timedelta(seconds=RESTART_COOLDOWN_S)


def tick(session: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)

    # live_mode is off because a human pressed Stop. Never undo that.
    if not launcher.is_live(session):
        return {"skipped": "not live", "restarted": []}

    rec = run_session.get_or_start(session)
    restarted = _keep_alive(session, rec, now)

    prog = run_session.progress(session, rec)
    level = run_session.adjust(session, rec, prog, now=now)
    if not prog["reachable"] and not rec.get("alerted", {}).get("unreachable"):
        rec.setdefault("alerted", {})["unreachable"] = True
        log.info("target out of reach: %d sent, %d owed, room for %d before %s",
                 prog["sent"], prog["owed"], prog["capacity_left"],
                 rec.get("deadline"))

    run_session.save(session, rec)
    return {"restarted": restarted, "level": level, **prog}


def _keep_alive(session: Session, rec: dict, now: datetime) -> list[str]:
    alive = launcher.running(session)
    stale = set(stale_processes(session))
    restarted: list[str] = []

    for process, is_alive in alive.items():
        if is_alive and process not in stale:
            continue
        reason = "dead" if not is_alive else "stale heartbeat"

        if process == "browser" and _login_window_open(session, now):
            log.info("browser is %s but the login window has the profile; leaving it",
                     reason)
            continue
        if _too_soon(rec, process, now):
            continue

        prior = _restarts_today(rec, process)
        if len(prior) >= RESTART_MAX_PER_PROC:
            if process not in rec.setdefault("alerted", {}).setdefault("ceiling", []):
                rec["alerted"]["ceiling"].append(process)
                notifier.alert("worker_down",
                               f"'{process}' has been restarted "
                               f"{len(prior)} times today and is still {reason}. "
                               "Quill has stopped restarting it.")
            continue

        # A process that is alive but not beating is wedged, and start() would
        # skip it as already running. Kill it first.
        if is_alive:
            pid = launcher.pid_of(session, process)
            if pid:
                launcher.terminate(pid)

        log.warning("restarting '%s' (%s)", process, reason)
        launcher.start(session)
        rec.setdefault("restarts", []).append(
            {"at": now.isoformat(), "process": process, "reason": reason})
        restarted.append(process)

    return restarted
