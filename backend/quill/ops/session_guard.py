"""Session heartbeat + selector canary (E-03, E-07). Failures halt writes,
engage the kill switch and alert (T-10, T-11)."""
from __future__ import annotations

import time

from sqlmodel import Session, select

from ..browser import ChallengeDetected, SessionDead, get_engine
from ..bus.action_bus import get_bus
from ..db.models import Account
from ..defaults import SESSION_FAIL_THRESHOLD
from ..governor import governor
from ..logging_setup import get_logger
from ..notify import notifier
from . import health

log = get_logger("quill.session")

_consecutive_fail = {"n": 0}


def session_heartbeat(session: Session) -> bool:
    """E-03: load home, confirm logged-in, record latency. Three consecutive
    failures => session-dead: halt writes, engage kill switch, alert."""
    t0 = time.time()
    try:
        ok = get_bus().submit_read("login_check", "")
        latency = int((time.time() - t0) * 1000)
        _consecutive_fail["n"] = 0
        health.record_health(session, session_ok=True, canary_ok=True,
                             worker_ok=True, latency_ms=latency)
        return bool(ok)
    except (SessionDead, ChallengeDetected) as e:
        _consecutive_fail["n"] += 1
        health.record_health(session, session_ok=False, canary_ok=True,
                             worker_ok=True, note=str(e))
        if _consecutive_fail["n"] >= SESSION_FAIL_THRESHOLD or isinstance(e, ChallengeDetected):
            _engage_dead(session, str(e))
        return False


def _engage_dead(session: Session, why: str):
    governor.set_kill(session, True)                     # halt writes
    notifier.alert("session_dead",
                   f"session dead ({why}). Re-login: /api/ops/login")
    log.error("SESSION DEAD: %s", why)


def force_session_dead(session: Session) -> None:
    """Test hook (T-10): simulate expiry -> immediate halt within one heartbeat."""
    engine = get_engine()
    if hasattr(engine, "set_session_dead"):
        engine.set_session_dead(True)
    _consecutive_fail["n"] = SESSION_FAIL_THRESHOLD - 1
    session_heartbeat(session)


def run_canary(session: Session) -> dict:
    """E-07: assert every registry entry resolves. On failure: alert with the
    failing key + screenshot, and disable auto mode (T-11)."""
    result = get_bus().submit_read("canary", "")
    if not result.ok:
        notifier.alert("canary_failed",
                       f"selector miss: {', '.join(result.missing)}")
        _disable_all_auto(session, f"canary miss: {result.missing}")
        health.record_health(session, session_ok=True, canary_ok=False,
                             worker_ok=True, note=f"missing {result.missing}")
        return {"ok": False, "missing": result.missing,
                "screenshot": result.screenshot_path}
    health.record_health(session, session_ok=True, canary_ok=True, worker_ok=True)
    return {"ok": True, "missing": []}


def _disable_all_auto(session: Session, reason: str):
    for acc in session.exec(select(Account).where(Account.mode == "auto")).all():
        acc.mode = "assisted"
        session.add(acc)
    session.commit()
    notifier.alert("auto_disabled", reason)
