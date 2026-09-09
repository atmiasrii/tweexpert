"""Auto mode sends. It does not build a queue for the operator to work through.

Every draft here would have landed in "waiting for you" despite the account
being on auto, which is the one thing auto mode is supposed to remove.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import select

from quill.db.models import Draft, Post
from quill.db.settings_store import get_setting, set_setting
from quill.governor import governor
from quill.pipeline import foryou_auto
from quill.pipeline import pipeline as pl


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
    return day


def _draft(session, text="constrained decoding holds the schema"):
    post = Post(x_post_id="2100000000000000001", author_handle="simonw",
                text="a post about structured output",
                url="https://x.com/simonw/status/2100000000000000001")
    session.add(post)
    session.commit()
    session.refresh(post)
    d = Draft(kind="reply", parent_post_id=post.id, final_text=text,
              status="queued", mode_at_creation="foryou")
    session.add(d)
    session.commit()
    session.refresh(d)
    return d, post


def test_spacing_is_not_yet_not_ask_a_human(session):
    """The batch is staggered by exactly this spacing, so a send scheduled now
    passes the same check when its turn comes."""
    _clean_day(session)
    set_setting(session, "min_write_spacing_s", 300)
    governor.record_write(session, "reply", "foryou")      # starts the clock

    d, post = _draft(session)
    held = foryou_auto._hold_or_schedule(session, d, post.x_post_id, 80.0, slot=1)

    assert held is None, "a spacing refusal must not stop the draft"
    session.expire_all()
    assert session.get(Draft, d.id).status != "queued"
    pend = get_setting(session, "_pending_auto", [])
    assert [p["draft_id"] for p in pend] == [d.id], "it should be on the schedule"


def test_the_daily_cap_bins_the_draft_rather_than_queueing_it(session):
    """A cap means the day is done. By the time it lifts the post is stale, and
    a queue nobody reads is worse than a reply that was never sent."""
    day = _clean_day(session)
    set_setting(session, "cap_replies_total", 2)
    day.replies_foryou = 2
    session.add(day)
    session.commit()

    d, post = _draft(session)
    held = foryou_auto._hold_or_schedule(session, d, post.x_post_id, 80.0, slot=0)

    assert held is not None, "a hard refusal stops the sweep"
    session.expire_all()
    assert session.get(Draft, d.id).status == "dismissed"
    assert get_setting(session, "_pending_auto", []) == []


def test_a_scheduled_send_that_hits_the_cap_is_not_handed_back(session):
    """send_due_auto used to park these in the queue too."""
    day = _clean_day(session)
    d, post = _draft(session)
    from quill.bus.authz import issue
    authz = issue(session, d.id, issuer="policy", mode="foryou", reasons=["t"])
    due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    set_setting(session, "_pending_auto",
                [{"draft_id": d.id, "authz_id": authz.id, "target": post.x_post_id,
                  "send_at": due, "permalink": post.url, "author": "simonw"}])
    set_setting(session, "cap_replies_total", 1)
    day.replies_foryou = 5
    session.add(day)
    session.commit()

    pl.send_due_auto(session)
    session.expire_all()
    assert session.get(Draft, d.id).status == "dismissed"


def test_assisted_mode_still_asks(session):
    """The queue is not gone, it is just not where auto-mode replies go."""
    _clean_day(session)
    d, post = _draft(session)
    held = foryou_auto._hold_or_schedule(session, d, post.x_post_id, 80.0,
                                         slot=0, mode="assisted")
    assert held is not None
    session.expire_all()
    assert session.get(Draft, d.id).status == "queued"
