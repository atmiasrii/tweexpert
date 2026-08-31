"""Presence simulator (§12). Makes the account look used, because it is being
used. Read-only; runs on the same bus; counts toward read budget, never toward
write caps (H-04). Clusters around active hours, never in quiet hours (H-03)."""
from __future__ import annotations

import random
from datetime import datetime, timezone

from sqlmodel import Session

from ..bus.action_bus import get_bus
from ..db.models import DiscoveryItem, Post
from ..governor import governor
from ..logging_setup import get_logger
from ..persona.voicecard import load_voice_card

log = get_logger("quill.presence")

ACTIVITIES = ["scroll_home", "read_post", "open_profile", "search_topic"]


def run_presence(session: Session) -> dict:
    if governor.in_quiet_hours(session):            # H-03
        return {"skipped": "quiet hours"}
    if governor.read_budget_left(session) <= 0:     # H-04
        return {"skipped": "read budget"}

    bus = get_bus()
    activity = random.choices(ACTIVITIES, weights=[5, 2, 1, 2])[0]
    surfaced: list = []

    if activity == "scroll_home":
        surfaced = bus.submit_read("presence", "home") or []
    elif activity == "read_post":
        surfaced = bus.submit_read("presence", "post") or []
    elif activity == "search_topic":
        card = load_voice_card(session)
        topic = random.choice(card.get("topics_owned", ["local models"]))
        surfaced = bus.submit_read("search", topic) or []
    else:
        surfaced = bus.submit_read("presence", "profile") or []

    governor.record_read(session, 1)

    # H-05: content encountered feeds the discovery inbox (real value)
    added = 0
    for p in surfaced[:5]:
        post = _upsert(session, p)
        session.add(DiscoveryItem(post_id=post.id, source="presence",
                                  query=activity, relevance=0.0))
        added += 1
    session.commit()
    log.info("presence %s surfaced=%d", activity, added)
    return {"activity": activity, "surfaced": added}


def _upsert(session: Session, p) -> Post:
    from sqlmodel import select
    row = session.exec(select(Post).where(Post.x_post_id == p.x_post_id)).first()
    if row:
        return row
    row = Post(x_post_id=p.x_post_id, author_handle=p.author_handle, text=p.text,
               created_at=p.created_at, url=p.url, kind=p.kind)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
