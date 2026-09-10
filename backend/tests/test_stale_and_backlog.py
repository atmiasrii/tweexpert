"""No reply to a post the feed has finished with, and no unbounded backlog.

Seen live the morning the bar was recalibrated: 22 sends waiting, ten already
overdue, most of them to posts 10 to 24 hours old. Two causes. A feed card
with no parsable timestamp was treated as an hour old and passed the six-hour
gate. And sweeps scheduled seven sends every ten minutes while spacing drained
two, so the queue grew by five a sweep.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from quill.browser.base import ParsedPost
from quill.bus.authz import issue
from quill.db.models import Draft, Post
from quill.db.settings_store import get_setting, set_setting
from quill.pipeline import foryou_auto
from quill.pipeline import pipeline as pl


def _parsed(pid, handle="someone", age_min=None, text="how do you handle structured output from small models?"):
    ca = None if age_min is None else datetime.now(timezone.utc) - timedelta(minutes=age_min)
    return ParsedPost(x_post_id=pid, author_handle=handle, text=text, created_at=ca, likes=5)


def test_a_card_with_no_timestamp_does_not_pass_the_age_gate(session):
    set_setting(session, foryou_auto.K_RELEVANCE_MIN, 0)
    picked, tally = foryou_auto._pick_batch(
        session, [_parsed("1", age_min=None)], "auto", 10, 0.0, 24)
    assert picked == []
    assert tally.get("no_timestamp") == 1


def test_a_missing_timestamp_is_taken_from_the_stored_post(session):
    """A later profile read may have stored the time the feed card lacked."""
    session.add(Post(x_post_id="2", author_handle="a", text="t",
                     created_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
    session.commit()
    set_setting(session, foryou_auto.K_RELEVANCE_MIN, 0)
    picked, tally = foryou_auto._pick_batch(
        session, [_parsed("2", handle="a", age_min=None)], "auto", 10, 0.0, 24)
    assert len(picked) == 1
    assert tally.get("no_timestamp", 0) == 0


def test_a_stored_post_that_is_old_is_still_skipped(session):
    session.add(Post(x_post_id="3", author_handle="b", text="t",
                     created_at=datetime.now(timezone.utc) - timedelta(hours=20)))
    session.commit()
    set_setting(session, foryou_auto.K_RELEVANCE_MIN, 0)
    picked, tally = foryou_auto._pick_batch(
        session, [_parsed("3", handle="b", age_min=None)], "auto", 10, 0.0, 24)
    assert picked == []
    assert tally.get("too_old") == 1


def test_the_watchlist_freshness_gate_fails_closed_on_unknown_age():
    assert pl._age_seconds(_parsed("4", age_min=None)) == float("inf")


def test_a_send_whose_post_aged_out_while_waiting_is_binned(session):
    old_post = Post(x_post_id="5", author_handle="c", text="t",
                    created_at=datetime.now(timezone.utc) - timedelta(hours=9))
    session.add(old_post)
    session.commit()
    session.refresh(old_post)
    d = Draft(kind="reply", parent_post_id=old_post.id, final_text="a reply",
              status="approved", mode_at_creation="foryou")
    session.add(d)
    session.commit()
    session.refresh(d)
    authz = issue(session, d.id, issuer="policy", mode="foryou", reasons=["t"])
    due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    set_setting(session, "_pending_auto",
                [{"draft_id": d.id, "authz_id": authz.id, "target": "5", "send_at": due}])
    set_setting(session, "foryou_max_age_min", 360)

    sent = pl.send_due_auto(session)
    session.expire_all()
    assert sent == []
    assert session.get(Draft, d.id).status == "dismissed"
    assert get_setting(session, "_pending_auto", []) == []


def test_a_fresh_scheduled_send_is_not_touched_by_the_stale_check(session):
    assert pl._stale_for_send(session, "no-such-post") == ""
    session.add(Post(x_post_id="6", author_handle="d", text="t",
                     created_at=datetime.now(timezone.utc) - timedelta(minutes=30)))
    session.commit()
    set_setting(session, "foryou_max_age_min", 360)
    assert pl._stale_for_send(session, "6") == ""


def test_the_sweep_drafts_only_what_the_backlog_has_room_for(session, monkeypatch):
    """Four already waiting with a cap of four means nothing new is drafted."""
    set_setting(session, "foryou_max_pending", 4)
    set_setting(session, "_pending_auto", [{"draft_id": i, "authz_id": i, "target": str(i),
                                            "send_at": "2099-01-01T00:00:00+00:00"}
                                           for i in range(4)])
    reads = []
    from quill.bus import action_bus
    bus = action_bus.get_bus()
    monkeypatch.setattr(bus, "submit_read", lambda *a, **k: reads.append(a) or [])

    out = foryou_auto.run(session, per_run=10, mode="auto")
    assert out["headroom"] == 0
    assert out["scanned"] == 0
    assert reads == [], "a full queue must not cost a feed read"
    assert out["why_skipped"] == {"send_queue_full": 1}
