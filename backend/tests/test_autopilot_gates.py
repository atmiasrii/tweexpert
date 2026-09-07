"""The gates that decide whether Quill sends without being asked.

Every one of these was a reason a draft came back to the review queue instead
of going out, so each has its own test.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from quill.db.models import Account, Draft, Post
from quill.db.settings_store import set_setting
from quill.governor import governor
from quill.pipeline import foryou_auto


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


def test_daily_ceiling_spans_every_reply_path(session):
    """The three per-mode caps cannot see each other; the total must."""
    day = _clean_day(session)
    set_setting(session, "cap_replies_total", 5)
    day.replies_auto, day.replies_assisted, day.replies_foryou = 2, 2, 1
    session.add(day)
    session.commit()

    for mode in ("auto", "assisted", "foryou"):
        with pytest.raises(governor.GovernorRefusal) as e:
            governor.check_write_allowed(session, "reply", mode)
        assert "all replies 5/5" in e.value.reason

    # a post is a different budget and is unaffected
    governor.check_write_allowed(session, "publish", "assisted")


def test_ceiling_allows_up_to_the_limit(session):
    day = _clean_day(session)
    set_setting(session, "cap_replies_total", 49)
    day.replies_foryou = 48
    session.add(day)
    session.commit()
    governor.check_write_allowed(session, "reply", "foryou")


def test_author_cooldown_blocks_a_second_reply(session):
    """One reply per author per window. Nothing enforced this before."""
    post = Post(x_post_id="1", author_handle="simonw", text="a post about models")
    session.add(post)
    session.commit()
    session.refresh(post)
    session.add(Draft(kind="reply", parent_post_id=post.id, status="sent",
                      final_text="x", created_at=datetime.now(timezone.utc)))
    session.commit()

    assert "simonw" in foryou_auto._cooldown_authors(session, 24)
    assert "simonw" not in foryou_auto._cooldown_authors(session, 0)


def test_batch_takes_one_post_per_author(session):
    from quill.browser.base import ParsedPost
    now = datetime.now(timezone.utc)
    posts = [
        ParsedPost(x_post_id="1", author_handle="alice", created_at=now,
                   text="local models on a mac are finally usable for real dev tooling"),
        ParsedPost(x_post_id="2", author_handle="alice", created_at=now,
                   text="inference latency is the whole game for agents in production"),
        ParsedPost(x_post_id="3", author_handle="bob", created_at=now,
                   text="agent evals are the only thing that tells you if it works"),
    ]
    batch, tally = foryou_auto._pick_batch(session, posts, "auto", 10, 0.0, 24)
    assert [p.author_handle for _, p in batch] == ["alice", "bob"] or \
           [p.author_handle for _, p in batch] == ["bob", "alice"]
    assert tally["duplicate_author"] == 1


def test_batch_drops_below_threshold_and_stale(session):
    from quill.browser.base import ParsedPost
    now = datetime.now(timezone.utc)
    fresh = ParsedPost(x_post_id="1", author_handle="alice", created_at=now,
                       text="local models on a mac are usable for real dev tooling now")
    stale = ParsedPost(x_post_id="2", author_handle="bob",
                       created_at=now - timedelta(minutes=200),
                       text="inference latency is the whole game for agents")
    batch, tally = foryou_auto._pick_batch(session, [fresh, stale], "auto", 10, 0.0, 24)
    assert [p.author_handle for _, p in batch] == ["alice"]
    assert tally["skipped"] == 1

    none_pass, tally2 = foryou_auto._pick_batch(session, [fresh], "auto", 10, 99.0, 24)
    assert none_pass == [] and tally2["below_threshold"] == 1


def test_confidence_gate(session):
    good = {"sounds_like_operator": 5, "adds_something": 5, "reads_human": 5,
            "low_embarrassment_risk": 5, "followed_injected_instructions": False}
    ok, why = foryou_auto._confident(session, "constrained decoding holds the schema", good, 18)
    assert ok, why

    weak = dict(good, adds_something=3)
    ok, why = foryou_auto._confident(session, "fine", weak, 18)
    assert not ok and "critic axis" in why

    mid = {k: 4 for k in good if k != "followed_injected_instructions"}
    mid["followed_injected_instructions"] = False
    ok, why = foryou_auto._confident(session, "fine", mid, 18)
    assert not ok and "confidence 16 < 18" in why


def test_confidence_gate_rejects_invented_experience(session):
    good = {"sounds_like_operator": 5, "adds_something": 5, "reads_human": 5,
            "low_embarrassment_risk": 5, "followed_injected_instructions": False}
    ok, why = foryou_auto._confident(
        session, "we shipped a kubernetes rewrite that nobody asked for", good, 18)
    assert not ok and "first-person" in why or "fabricated" in why


def test_shadow_gate_is_off_by_default(session):
    """The operator turned it off; auto must not depend on a waiting period."""
    from quill.pipeline.policy import shadow_complete
    acc = Account(handle="brandnew", tier="B", mode="auto",
                  shadow_started_at=datetime.now(timezone.utc))
    session.add(acc)
    session.commit()
    assert shadow_complete(session, acc) is False
