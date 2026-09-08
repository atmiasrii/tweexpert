"""Auto mode must not be demoted by transient events, and a demotion must be
reversible from the operator's recorded preference.

Background: one `canary_failed` event flipped 15 of 20 watched accounts from
auto to assisted. A selector miss is usually X's timeline still rendering,
not a safety event. Only ChallengeDetected / SessionDead demote on a write;
the canary demotes only after three consecutive misses; and the operator's
stated mode is persisted so it can be restored.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from quill.browser import get_engine
from quill.browser.base import ChallengeDetected, SelectorMiss
from quill.bus.action_bus import get_bus
from quill.bus.authz import issue
from quill.db.models import Account, Draft, Post
from quill.db.settings_store import get_setting, set_setting
from quill.governor import governor
from quill.notify import notifier
from quill.ops import session_guard


# ------------------------------------------------------------------ helpers
@pytest.fixture(autouse=True)
def _fresh_login_limiter():
    """test_t13_login_rate_limited (test_acceptance.py) deliberately locks
    login out, and the limiter is process memory that `_fresh_db` does not
    reset. This file is the first to use `auth_client` after it, so give
    every test here a fresh limiter."""
    import quill.api.auth as auth
    auth._limiter = None
    yield
    auth._limiter = None


def _mk_account(session, handle="simonw", mode="auto"):
    acc = Account(handle=handle, display_name=handle, tier="A", mode=mode,
                  shadow_started_at=datetime.now(timezone.utc) - timedelta(days=10),
                  shadow_drafts_count=25, shadow_reviewed_count=25)
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


def _modes(session) -> dict[str, str]:
    session.expire_all()
    return {a.handle: a.mode for a in session.exec(select(Account)).all()}


def _clean_day(session):
    day = governor.get_day(session)
    day.kill_switch = False
    day.no_auto_today = False
    day.quiet_drift_min = 0
    day.replies_auto = day.replies_assisted = day.replies_foryou = 0
    day.last_write_at = None
    session.add(day)
    set_setting(session, "kill_switch", False)
    now = governor.local_now()
    set_setting(session, "quiet_start", f"{(now.hour + 3) % 24:02d}:00")
    set_setting(session, "quiet_end", f"{(now.hour + 3) % 24:02d}:01")
    session.commit()


def _draft(session, handle="simonw"):
    post = Post(x_post_id="1900000000000000123", author_handle=handle,
                text="a post about structured output",
                url=f"https://x.com/{handle}/status/1900000000000000123")
    session.add(post)
    session.commit()
    session.refresh(post)
    d = Draft(kind="reply", parent_post_id=post.id,
              final_text="constrained decoding holds the schema",
              status="queued", mode_at_creation="assisted")
    session.add(d)
    session.commit()
    session.refresh(d)
    return d, post


def _write_that_raises(session, monkeypatch, exc):
    """Drive a real write through the bus and make the engine raise `exc`."""
    _clean_day(session)
    d, post = _draft(session)
    authz = issue(session, d.id, issuer="human", mode="assisted", reasons=["t"])

    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(get_engine(), "reply", boom)
    with pytest.raises(type(exc)):
        get_bus().submit_write("reply", post.x_post_id, d.final_text, authz,
                               issuer="human", draft_id=d.id,
                               permalink=post.url, author=post.author_handle)


# ------------------------------------------------- write-path demotion policy
def test_selector_miss_on_write_alerts_but_does_not_demote(session, monkeypatch):
    for h in ("simonw", "karpathy", "swyx"):
        _mk_account(session, h, "auto")
    _mk_account(session, "someone", "assisted")

    _write_that_raises(session, monkeypatch, SelectorMiss("reply_button"))

    assert _modes(session) == {"simonw": "auto", "karpathy": "auto",
                               "swyx": "auto", "someone": "assisted"}
    kinds = [n["kind"] for n in notifier.recent()]
    assert "canary_failed" in kinds          # still alerted
    assert "auto_disabled" not in kinds      # nobody demoted


def test_challenge_on_write_still_demotes_every_auto_account(session, monkeypatch):
    for h in ("simonw", "karpathy"):
        _mk_account(session, h, "auto")
    _mk_account(session, "someone", "shadow")

    _write_that_raises(session, monkeypatch, ChallengeDetected("rate_limit"))

    assert _modes(session) == {"simonw": "assisted", "karpathy": "assisted",
                               "someone": "shadow"}
    kinds = [n["kind"] for n in notifier.recent()]
    assert "challenge_detected" in kinds
    assert "auto_disabled" in kinds


# --------------------------------------------------------- canary threshold
def test_canary_demotes_only_on_third_consecutive_failure(session):
    acc = _mk_account(session, "simonw", "auto")
    get_engine().break_selector("tweet")

    r1 = session_guard.run_canary(session)
    assert r1["ok"] is False and "tweet" in r1["missing"]
    assert r1["consecutive_failures"] == 1
    assert _modes(session)["simonw"] == "auto"

    r2 = session_guard.run_canary(session)
    assert r2["consecutive_failures"] == 2
    assert _modes(session)["simonw"] == "auto"
    assert get_setting(session, "canary_consecutive_failures") == 2
    assert "tweet" in get_setting(session, "canary_last_failure_reason")
    assert not any(n["kind"] == "auto_disabled" for n in notifier.recent())

    r3 = session_guard.run_canary(session)
    assert r3["consecutive_failures"] == 3
    assert _modes(session)["simonw"] == "assisted"
    assert any(n["kind"] == "auto_disabled" for n in notifier.recent())
    # every miss alerted, even the ones that did not demote
    assert sum(1 for n in notifier.recent() if n["kind"] == "canary_failed") == 3


def test_canary_success_resets_the_failure_counter(session):
    _mk_account(session, "simonw", "auto")
    eng = get_engine()

    eng.break_selector("tweet")
    session_guard.run_canary(session)
    session_guard.run_canary(session)
    assert get_setting(session, "canary_consecutive_failures") == 2

    eng.fix_selectors()
    ok = session_guard.run_canary(session)
    assert ok["ok"] is True
    assert get_setting(session, "canary_consecutive_failures") == 0

    # two fresh misses after a pass are still below the threshold
    eng.break_selector("tweet")
    session_guard.run_canary(session)
    session_guard.run_canary(session)
    assert get_setting(session, "canary_consecutive_failures") == 2
    assert _modes(session)["simonw"] == "auto"


def test_canary_counter_survives_a_process_restart(session):
    """The counter is in the settings table, not process memory."""
    _mk_account(session, "simonw", "auto")
    set_setting(session, "canary_consecutive_failures", 2)   # from a prior run
    get_engine().break_selector("tweet")
    session_guard.run_canary(session)
    assert _modes(session)["simonw"] == "assisted"


# ------------------------------------------------- operator intent persists
def test_set_mode_records_preference_and_restore_puts_it_back(auth_client, session):
    acc = _mk_account(session, "simonw", "shadow")
    bystander = _mk_account(session, "someone", "assisted")

    r = auth_client.post(f"/api/accounts/{acc.id}/mode", json={"mode": "auto"})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "auto"
    assert get_setting(session, "preferred_mode_by_account") == {"simonw": "auto"}

    # a temporary demotion, as the canary or a challenge would do it
    session.expire_all()
    acc = session.get(Account, acc.id)
    acc.mode = "assisted"
    acc.consecutive_publish_failures = 2
    session.add(acc)
    session.commit()
    assert _modes(session)["simonw"] == "assisted"

    r = auth_client.post("/api/accounts/restore-auto")
    assert r.status_code == 200, r.text
    assert r.json()["restored"] == 1

    modes = _modes(session)
    assert modes["simonw"] == "auto"
    assert modes["someone"] == "assisted"        # no preference: untouched
    session.refresh(acc)
    assert acc.consecutive_publish_failures == 0

    # idempotent: nothing left to restore
    assert auth_client.post("/api/accounts/restore-auto").json()["restored"] == 0


def test_restore_after_canary_demotion_end_to_end(auth_client, session):
    acc = _mk_account(session, "simonw", "shadow")
    auth_client.post(f"/api/accounts/{acc.id}/mode", json={"mode": "auto"})

    get_engine().break_selector("tweet")
    for _ in range(session_guard.CANARY_FAIL_THRESHOLD):
        session_guard.run_canary(session)
    assert _modes(session)["simonw"] == "assisted"

    assert session_guard.restore_preferred_modes(session) == 1
    assert _modes(session)["simonw"] == "auto"
