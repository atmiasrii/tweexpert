"""A selector miss on an unattended send goes back on the schedule.

Seen live: a cold post page still on X's splash screen at the 15-second mark
missed the target article, and the bus parked the auto draft in the approval
queue, where nothing would ever pick it up. Auto means auto.
"""
from __future__ import annotations

import pytest

from quill.browser import SelectorMiss, get_engine
from quill.bus.action_bus import get_bus
from quill.bus.authz import issue
from quill.db.models import Action, Draft, Post
from quill.db.settings_store import get_setting, set_setting
from quill.governor import governor


def _clean_day(session):
    day = governor.get_day(session)
    day.kill_switch = False
    day.no_auto_today = False
    day.replies_auto = day.replies_assisted = day.replies_foryou = 0
    day.last_write_at = None
    session.add(day)
    set_setting(session, "kill_switch", False)
    set_setting(session, "cap_replies_total", 50)
    session.commit()


def _draft(session):
    post = Post(x_post_id="2200000000000000001", author_handle="simonw", text="a post",
                url="https://x.com/simonw/status/2200000000000000001")
    session.add(post)
    session.commit()
    session.refresh(post)
    d = Draft(kind="reply", parent_post_id=post.id, final_text="a careful reply",
              status="approved", mode_at_creation="foryou")
    session.add(d)
    session.commit()
    session.refresh(d)
    return d, post


def test_an_unattended_miss_is_rescheduled_not_queued(session):
    _clean_day(session)
    set_setting(session, "_pending_auto", [])
    type(get_engine()).reply_outcome = "miss"
    try:
        d, post = _draft(session)
        authz = issue(session, d.id, issuer="policy", mode="foryou", reasons=["t"])
        with pytest.raises(SelectorMiss):
            get_bus().submit_write("reply", post.x_post_id, d.final_text, authz,
                                   issuer="policy", draft_id=d.id)
        session.expire_all()
        assert session.get(Draft, d.id).status == "approved"
        pend = get_setting(session, "_pending_auto", [])
        assert [p["draft_id"] for p in pend] == [d.id]
        acts = session.exec(__import__("sqlmodel").select(Action).where(
            Action.kind == "reply")).all()
        assert acts[-1].attempts == 2, "one more look before giving up"
    finally:
        type(get_engine()).reply_outcome = "ok"


def test_a_human_approved_miss_still_returns_to_the_queue(session):
    _clean_day(session)
    type(get_engine()).reply_outcome = "miss"
    try:
        d, post = _draft(session)
        authz = issue(session, d.id, issuer="human", mode="assisted", reasons=["t"])
        with pytest.raises(SelectorMiss):
            get_bus().submit_write("reply", post.x_post_id, d.final_text, authz,
                                   issuer="human", draft_id=d.id)
        session.expire_all()
        assert session.get(Draft, d.id).status == "queued"
    finally:
        type(get_engine()).reply_outcome = "ok"
