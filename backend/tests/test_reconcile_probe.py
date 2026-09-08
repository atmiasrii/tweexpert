"""A send the last run left mid-flight is settled by looking at the post."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from quill.browser import get_engine
from quill.bus.action_bus import get_bus
from quill.bus.authz import issue
from quill.db.models import Action, Draft, Post
from quill.db.settings_store import get_setting, set_setting

TEXT = "constrained decoding holds the schema"


def _stuck(session, issuer="policy", mode="auto"):
    post = Post(x_post_id="1900000000000000123", author_handle="simonw",
                text="a post", url="https://x.com/simonw/status/1900000000000000123")
    session.add(post); session.commit(); session.refresh(post)
    d = Draft(kind="reply", parent_post_id=post.id, final_text=TEXT,
              status="approved", mode_at_creation=mode)
    session.add(d); session.commit(); session.refresh(d)
    authz = issue(session, d.id, issuer=issuer, mode=mode, reasons=["t"])
    a = Action(kind="reply", target=post.x_post_id, state="running", issuer=issuer,
               authorization_id=authz.id, idempotency_key="k" + str(d.id),
               payload_json=json.dumps({"target": post.x_post_id, "content": TEXT,
                                        "permalink": post.url, "author": "simonw"}),
               started_at=datetime.now(timezone.utc))
    session.add(a); session.commit(); session.refresh(a)
    return d, a


def test_reply_found_on_the_post_is_marked_sent(session):
    d, a = _stuck(session)
    get_engine().posted.append({"x_post_id": "777", "text": TEXT, "kind": "reply",
                                "parent": "1900000000000000123"})
    out = get_bus().reconcile()
    session.expire_all()
    assert out["reconciled"] == 1
    assert session.get(Action, a.id).x_post_id == "777"
    assert session.get(Draft, d.id).status == "sent"


def test_reply_absent_goes_back_on_the_schedule(session):
    set_setting(session, "_pending_auto", [])
    d, a = _stuck(session)
    out = get_bus().reconcile()
    session.expire_all()
    assert out.get("requeued") == 1
    assert session.get(Action, a.id).outcome == "not_posted_requeued"
    pend = get_setting(session, "_pending_auto", [])
    assert [p["draft_id"] for p in pend] == [d.id]
    assert pend[0]["permalink"].endswith("/status/1900000000000000123")
    assert session.get(Draft, d.id).status == "approved"


def test_human_approval_absent_goes_back_to_the_queue(session):
    d, a = _stuck(session, issuer="human", mode="assisted")
    get_bus().reconcile()
    session.expire_all()
    assert session.get(Draft, d.id).status == "queued"
