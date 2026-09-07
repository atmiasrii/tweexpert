"""A reply is only 'sent' when we can point at it.

Every test here corresponds to a way replies were silently not being posted:
approvals routed to an extension that never existed, a drain loop that could
not execute, a reconcile that deleted fresh work, and an empty post id being
accepted as success.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from quill.browser import get_engine
from quill.browser.reply_verify import (normalize_reply_text, status_id_from_href,
                                        target_article_selectors, texts_match)
from quill.bus.action_bus import get_bus
from quill.bus.authz import issue
from quill.db.models import Action, Draft, Post
from quill.db.settings_store import get_setting, set_setting
from quill.governor import governor
from quill.pipeline.approve import approve_draft
from quill.pipeline.pipeline import backfill_post_urls, permalink_for, upsert_post


# ------------------------------------------------------------------ helpers
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


def _draft(session, text="constrained decoding holds the schema", handle="simonw"):
    post = Post(x_post_id="1900000000000000123", author_handle=handle,
                text="a post about structured output",
                url=f"https://x.com/{handle}/status/1900000000000000123")
    session.add(post)
    session.commit()
    session.refresh(post)
    d = Draft(kind="reply", parent_post_id=post.id, final_text=text,
              status="queued", mode_at_creation="assisted")
    session.add(d)
    session.commit()
    session.refresh(d)
    return d, post


def _reset_engine(outcome="ok"):
    eng = get_engine()
    type(eng).reply_outcome = outcome
    type(eng).reply_calls = 0
    return eng


# ------------------------------------------------------- permalink handling
def test_permalink_prefers_the_stored_link():
    assert permalink_for("simonw", "12", "https://x.com/simonw/status/12") == \
        "https://x.com/simonw/status/12"


def test_permalink_is_rebuilt_when_missing():
    """Never /i/status/, which redirects and so cannot be verified."""
    assert permalink_for("simonw", "12") == "https://x.com/simonw/status/12"
    assert permalink_for("", "12") == "https://x.com/i/status/12"


def test_upsert_backfills_a_missing_url_and_never_blanks_one(session):
    from quill.browser.base import ParsedPost
    session.add(Post(x_post_id="55", author_handle="simonw", text="x", url=""))
    session.commit()

    upsert_post(session, ParsedPost(x_post_id="55", author_handle="simonw",
                                    text="x", url="https://x.com/simonw/status/55"))
    row = session.exec(select(Post).where(Post.x_post_id == "55")).first()
    assert row.url == "https://x.com/simonw/status/55"

    upsert_post(session, ParsedPost(x_post_id="55", author_handle="simonw", text="x"))
    row = session.exec(select(Post).where(Post.x_post_id == "55")).first()
    assert row.url == "https://x.com/simonw/status/55", "a thinner read blanked it"


def test_backfill_gives_every_post_a_link(session):
    session.add(Post(x_post_id="77", author_handle="karpathy", text="x", url=""))
    session.commit()
    assert backfill_post_urls(session) >= 1
    row = session.exec(select(Post).where(Post.x_post_id == "77")).first()
    assert row.url == "https://x.com/karpathy/status/77"


# ---------------------------------------------------------------- routing
def test_approval_goes_to_the_browser_not_a_missing_extension(session):
    """The default used to be an extension that had never called the API."""
    _clean_day(session)
    _reset_engine("ok")
    d, post = _draft(session)

    result = approve_draft(session, d.id)

    assert result.get("status") != "ready", "approval parked for the extension"
    session.refresh(d)
    assert d.status == "sent"
    action = session.exec(select(Action).where(Action.kind == "reply")).first()
    assert action is not None and action.x_post_id


def test_approval_uses_the_extension_only_when_it_is_alive(session):
    _clean_day(session)
    _reset_engine("ok")
    set_setting(session, "sender", "auto")

    d, _ = _draft(session)
    assert approve_draft(session, d.id).get("status") != "ready"   # stale/absent

    set_setting(session, "ext_last_seen", datetime.now(timezone.utc).isoformat())
    d2, _ = _draft(session, text="a second distinct reply about schemas")
    assert approve_draft(session, d2.id).get("status") == "ready"


def test_the_send_is_given_the_permalink(session):
    _clean_day(session)
    eng = _reset_engine("ok")
    d, post = _draft(session)
    approve_draft(session, d.id)
    assert eng.last_reply["permalink"] == post.url
    assert eng.last_reply["author"] == "simonw"


# ------------------------------------------------------- failure semantics
def test_unverified_send_is_never_recorded_as_sent(session):
    """The bug that made this necessary: an empty id counted as success."""
    _clean_day(session)
    _reset_engine("unverified")
    d, _ = _draft(session)

    with pytest.raises(Exception):
        approve_draft(session, d.id)

    session.refresh(d)
    assert d.status == "needs_review"
    action = session.exec(select(Action).where(Action.kind == "reply")).first()
    assert action.state == "failed" and action.outcome == "unverified"


def test_unverified_send_still_costs_governor_budget(session):
    """It may have gone out, so spacing and caps must assume it did."""
    _clean_day(session)
    _reset_engine("unverified")
    before = governor.get_day(session).replies_assisted
    d, _ = _draft(session)
    with pytest.raises(Exception):
        approve_draft(session, d.id)
    assert governor.get_day(session).replies_assisted == before + 1


def test_unverified_send_is_not_retried(session):
    _clean_day(session)
    eng = _reset_engine("unverified")
    d, _ = _draft(session)
    with pytest.raises(Exception):
        approve_draft(session, d.id)
    assert type(eng).reply_calls == 1, "an ambiguous send must not be repeated"


def test_a_deleted_target_is_dismissed_not_reviewed(session):
    _clean_day(session)
    _reset_engine("unavailable")
    d, _ = _draft(session)
    with pytest.raises(Exception):
        approve_draft(session, d.id)
    session.refresh(d)
    assert d.status == "dismissed"
    action = session.exec(select(Action).where(Action.kind == "reply")).first()
    assert action.outcome == "target_gone"


# ------------------------------------------------------------ the queue
def test_drain_pending_actually_executes(session):
    """Regression: reading the ORM row after its session closed raised
    DetachedInstanceError and aborted the loop, so nothing ever drained."""
    _clean_day(session)
    _reset_engine("ok")
    d, post = _draft(session)
    authz = issue(session, d.id, issuer="human", mode="assisted", reasons=["t"])

    intent = get_bus().enqueue_write("reply", post.x_post_id, d.final_text, authz,
                                     issuer="human", draft_id=d.id,
                                     permalink=post.url, author=post.author_handle)
    assert intent.state == "pending"

    done = get_bus().drain_pending(limit=5)
    assert len(done) == 1
    assert done[0].state == "done" and done[0].x_post_id


def test_reconcile_leaves_a_fresh_pending_intent_alone(session):
    """The worker re-ran this every 5 minutes and abandoned queued work."""
    _clean_day(session)
    _reset_engine("ok")
    d, post = _draft(session)
    authz = issue(session, d.id, issuer="human", mode="assisted", reasons=["t"])
    intent = get_bus().enqueue_write("reply", post.x_post_id, d.final_text, authz,
                                     issuer="human", draft_id=d.id)

    get_bus().reconcile()

    row = session.get(Action, intent.id)
    session.refresh(row)
    assert row.state == "pending", "a fresh intent was abandoned before its turn"


def test_reconcile_still_abandons_a_stale_one(session):
    _clean_day(session)
    _reset_engine("ok")
    d, post = _draft(session)
    authz = issue(session, d.id, issuer="human", mode="assisted", reasons=["t"])
    intent = get_bus().enqueue_write("reply", post.x_post_id, d.final_text, authz,
                                     issuer="human", draft_id=d.id)
    row = session.get(Action, intent.id)
    row.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    session.add(row)
    session.commit()

    get_bus().reconcile()
    session.refresh(row)
    assert row.state in ("abandoned", "done")


# ------------------------------------------------- verification primitives
def test_reply_text_matching_survives_how_x_renders_it():
    assert texts_match("constrained decoding holds the schema",
                       "constrained decoding holds the schema")
    assert texts_match("the eval set is the product, everything else is vibes",
                       "the eval set is the product, everything else is vibes…")
    assert texts_match("see https://example.com for the numbers",
                       "see  for the numbers")
    assert not texts_match("constrained decoding holds the schema",
                           "most startups fail because of marketing")


def test_status_id_extraction_ignores_suffixes():
    assert status_id_from_href("/barryallendgx/status/2096/analytics") == "2096"
    assert status_id_from_href("/a/status/12/photo/1") == "12"
    assert status_id_from_href("/home") == ""


def test_target_selectors_are_anchored_to_the_exact_post():
    sels = target_article_selectors("12345")
    assert all('href$="/status/12345"' in s for s in sels)


def test_normalize_is_case_and_space_insensitive():
    assert normalize_reply_text("  The   Eval Set!! ") == "the eval set"
