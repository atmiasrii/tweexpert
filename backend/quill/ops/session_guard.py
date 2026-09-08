"""Session heartbeat + selector canary (E-03, E-07). Failures halt writes,
engage the kill switch and alert (T-10, T-11).

Auto mode is demoted here only after CANARY_FAIL_THRESHOLD consecutive canary
misses. A single miss is usually X's timeline still rendering, not a broken
registry, and one such miss once flipped 15 of 20 auto accounts to assisted.
The counter lives in the settings table so it survives restarts and is visible
to the operator (`canary_consecutive_failures`, `canary_last_failure_reason`).

The operator's stated mode per account is recorded in the settings key
`preferred_mode_by_account` (by the accounts API) and is the source of truth:
any demotion is temporary, and `restore_preferred_modes` puts it back.
"""
from __future__ import annotations

import time

from sqlmodel import Session, select

from ..browser import ChallengeDetected, SessionDead, get_engine
from ..bus.action_bus import get_bus
from ..db.models import Account
from ..db.settings_store import get_setting, set_setting
from ..defaults import SESSION_FAIL_THRESHOLD
from ..governor import governor
from ..logging_setup import get_logger
from ..notify import notifier
from . import health

log = get_logger("quill.session")

# Consecutive canary misses before auto mode is disabled. Not in defaults.py
# on purpose: it is a property of how flaky X's client-side render is, not an
# operator-tunable budget.
CANARY_FAIL_THRESHOLD = 3
CANARY_FAILS_KEY = "canary_consecutive_failures"
CANARY_REASON_KEY = "canary_last_failure_reason"
PREFERRED_MODES_KEY = "preferred_mode_by_account"
VALID_MODES = ("shadow", "assisted", "auto")

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
    failing key + screenshot. Auto mode is disabled (T-11) only once
    CANARY_FAIL_THRESHOLD consecutive runs have missed; a passing run resets
    the counter. What the canary checks is unchanged."""
    result = get_bus().submit_read("canary", "")
    if not result.ok:
        n = int(get_setting(session, CANARY_FAILS_KEY, 0) or 0) + 1
        reason = f"canary miss: {result.missing}"
        set_setting(session, CANARY_FAILS_KEY, n)
        set_setting(session, CANARY_REASON_KEY, reason)
        notifier.alert("canary_failed",
                       f"selector miss: {', '.join(result.missing)} "
                       f"({n}/{CANARY_FAIL_THRESHOLD} consecutive)")
        if n >= CANARY_FAIL_THRESHOLD:
            _disable_all_auto(session, f"{reason} x{n} consecutive")
        else:
            log.warning("canary miss %d/%d: %s; not demoting yet",
                        n, CANARY_FAIL_THRESHOLD, result.missing)
        health.record_health(session, session_ok=True, canary_ok=False,
                             worker_ok=True, note=f"missing {result.missing}")
        return {"ok": False, "missing": result.missing,
                "screenshot": result.screenshot_path,
                "consecutive_failures": n}
    if get_setting(session, CANARY_FAILS_KEY, 0):
        set_setting(session, CANARY_FAILS_KEY, 0)
    health.record_health(session, session_ok=True, canary_ok=True, worker_ok=True)
    return {"ok": True, "missing": [], "consecutive_failures": 0}


def _disable_all_auto(session: Session, reason: str) -> int:
    """Demote every auto account to assisted. Returns how many changed; the
    alert only fires when something actually changed."""
    demoted = 0
    for acc in session.exec(select(Account).where(Account.mode == "auto")).all():
        acc.mode = "assisted"
        session.add(acc)
        demoted += 1
    session.commit()
    if demoted:
        log.error("auto disabled on %d account(s): %s", demoted, reason)
        notifier.alert("auto_disabled", reason)
    return demoted


def restore_preferred_modes(session: Session) -> int:
    """Put every account back on the mode the operator last set for it
    (settings key `preferred_mode_by_account`, handle -> mode).

    A demotion by the canary, a challenge or a dead session is temporary; the
    operator's stated preference is the source of truth. Restoring a mode does
    not bypass safety: the kill switch and the governor still gate every write.
    The per-account publish-failure streak is cleared too, so a restored
    account is not re-demoted by the very next single failure.
    Returns the number of accounts whose mode changed."""
    prefs = get_setting(session, PREFERRED_MODES_KEY, {}) or {}
    restored = 0
    for acc in session.exec(select(Account)).all():
        want = prefs.get(acc.handle)
        if want not in VALID_MODES or acc.mode == want:
            continue
        log.info("restoring @%s: %s -> %s", acc.handle, acc.mode, want)
        acc.mode = want
        acc.consecutive_publish_failures = 0
        session.add(acc)
        restored += 1
    if restored:
        session.commit()
    return restored
