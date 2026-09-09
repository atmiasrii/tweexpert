"""A scheduled send whose authorization ran out must not strand its draft."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from quill.bus.authz import issue
from quill.db.models import Authorization, Draft, Post
from quill.db.settings_store import get_setting, set_setting
from quill.pipeline import pipeline as pl


def _scheduled(session, ttl_s: int):
    post = Post(x_post_id="2000000000000000001", author_handle="simonw",
                text="a post", url="https://x.com/simonw/status/2000000000000000001")
    session.add(post)
    session.commit()
    session.refresh(post)
    d = Draft(kind="reply", parent_post_id=post.id, final_text="a reply",
              status="approved", mode_at_creation="auto")
    session.add(d)
    session.commit()
    session.refresh(d)
    authz = issue(session, d.id, issuer="policy", mode="auto", reasons=["t"],
                  ttl_s=ttl_s)
    due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    set_setting(session, "_pending_auto",
                [{"draft_id": d.id, "authz_id": authz.id,
                  "target": post.x_post_id, "send_at": due,
                  "permalink": post.url, "author": "simonw"}])
    return d, authz


def test_an_expired_send_dismisses_its_draft(session):
    d, authz = _scheduled(session, ttl_s=60)
    row = session.get(Authorization, authz.id)
    row.expires_at = datetime.now(timezone.utc) - timedelta(hours=12)
    session.add(row)
    session.commit()

    sent = pl.send_due_auto(session)
    session.expire_all()

    assert sent == []
    assert session.get(Draft, d.id).status == "dismissed"
    assert get_setting(session, "_pending_auto", []) == []


def test_a_live_authorization_is_still_sent(session):
    # A cap or the kill switch now bins a due send rather than queueing it, so
    # this needs an explicitly clear day to be testing what it claims to.
    from quill.governor import governor
    day = governor.get_day(session)
    day.kill_switch = False
    day.no_auto_today = False
    day.quiet_drift_min = 0
    day.replies_auto = day.replies_assisted = day.replies_foryou = 0
    day.last_write_at = None
    session.add(day)
    set_setting(session, "kill_switch", False)
    set_setting(session, "cap_replies_total", 50)
    now = governor.local_now()
    set_setting(session, "quiet_start", f"{(now.hour + 3) % 24:02d}:00")
    set_setting(session, "quiet_end", f"{(now.hour + 3) % 24:02d}:01")
    session.commit()

    d, _ = _scheduled(session, ttl_s=3600)
    pl.send_due_auto(session)
    session.expire_all()
    assert session.get(Draft, d.id).status != "dismissed"
