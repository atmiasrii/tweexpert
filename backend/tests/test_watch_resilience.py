"""One unreadable profile must not end the whole watch sweep."""
from __future__ import annotations

import pytest

from quill.browser import AccountGone, SelectorMiss
from quill.db.models import Account
from quill.pipeline import watcher


def _accounts(session, n=3, tier="A"):
    made = []
    for i in range(n):
        a = Account(handle=f"user{i}", tier=tier, mode="assisted", active=True)
        session.add(a)
        made.append(a)
    session.commit()
    for a in made:
        session.refresh(a)
    return made


def _no_home_sweep(monkeypatch):
    monkeypatch.setattr(watcher, "sweep_home",
                        lambda s: {"polled": 0, "queued": 0, "discarded": 0})


def test_a_dead_handle_is_deactivated_and_the_sweep_continues(session, monkeypatch):
    _no_home_sweep(monkeypatch)
    _accounts(session)
    monkeypatch.setattr(watcher, "DEEP_READS_PER_SWEEP", 3, raising=False)
    seen = []

    def fake_watch_once(sess, acc):
        seen.append(acc.handle)
        if acc.handle == "user1":
            raise AccountGone("user1", "this account doesn't exist")
        return []

    monkeypatch.setattr(watcher, "watch_once", fake_watch_once)
    summary = watcher.watch_all(session)

    assert len(seen) == 3, "the sweep stopped early"
    assert summary["deactivated"] == 1
    gone = session.exec(
        __import__("sqlmodel").select(Account).where(Account.handle == "user1")).first()
    assert gone.active is False


def test_a_render_miss_does_not_stop_the_sweep(session, monkeypatch):
    _no_home_sweep(monkeypatch)
    _accounts(session)
    seen = []

    def fake_watch_once(sess, acc):
        seen.append(acc.handle)
        if acc.handle == "user0":
            raise SelectorMiss("tweet")
        return []

    monkeypatch.setattr(watcher, "watch_once", fake_watch_once)
    summary = watcher.watch_all(session)

    assert len(seen) == 3
    assert summary["read_failed"] == 1
    still_on = session.exec(
        __import__("sqlmodel").select(Account).where(Account.handle == "user0")).first()
    assert still_on.active is True, "a render miss must not deactivate an account"


def test_a_failed_home_read_still_runs_the_deep_reads(session, monkeypatch):
    """The home read is one lookup against a client-rendered timeline. Losing
    the whole sweep to it costs every deep read behind it."""
    _accounts(session)
    seen = []

    def boom(_s):
        raise SelectorMiss("tweet")

    monkeypatch.setattr(watcher, "sweep_home", boom)
    monkeypatch.setattr(watcher, "watch_once",
                        lambda s, acc: seen.append(acc.handle) or [])
    summary = watcher.watch_all(session)

    assert summary["home_failed"] == 1
    assert len(seen) == 3, "the deep reads must still happen"


@pytest.mark.parametrize("body,expected", [
    ("This account doesn’t exist Try searching for another.", True),
    ("Account suspended X suspends accounts that violate", True),
    ("These posts are protected", True),
    ("Simon Willison @simonw Joined 2007 12.3K Following", False),
])
def test_dead_profile_markers(body, expected):
    from quill.browser.playwright_engine import PlaywrightEngine
    hits = [m for m in PlaywrightEngine._DEAD_PROFILE if m in body.lower()]
    assert bool(hits) is expected
