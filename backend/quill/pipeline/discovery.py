"""Discovery, saved searches, people (§14)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..bus.action_bus import get_bus
from ..db.models import Account, DiscoveryItem, Person, Post
from ..governor import governor
from . import pipeline, relevance as relevance_mod
from ..db.models import SavedSearch


def run_saved_searches(session: Session) -> int:
    bus = get_bus()
    now = datetime.now(timezone.utc)
    n = 0
    for s in session.exec(select(SavedSearch).where(SavedSearch.active == True)).all():  # noqa: E712
        last = s.last_run_at
        if last and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last and (now - last).total_seconds() < s.interval_s:
            continue
        if governor.read_budget_left(session) <= 0:
            break
        posts = bus.submit_read("search", s.query)
        governor.record_read(session, 1)
        for p in posts:
            post = pipeline.upsert_post(session, p)
            rel = relevance_mod.score(session, p, None)
            session.add(DiscoveryItem(post_id=post.id, source="search",
                                      query=s.query, relevance=rel))
            n += 1
        s.last_run_at = now
        session.add(s)
    session.commit()
    return n


def promote(session: Session, item_id: int) -> pipeline.Outcome:
    """V-02: promote a discovery item into the reply pipeline (never auto)."""
    item = session.get(DiscoveryItem, item_id)
    if not item:
        raise ValueError("discovery item not found")
    post = session.get(Post, item.post_id)
    account = session.exec(select(Account).where(
        Account.handle == post.author_handle)).first()
    from ..browser.base import ParsedPost
    parsed = ParsedPost(x_post_id=post.x_post_id, author_handle=post.author_handle,
                        text=post.text, created_at=post.created_at, url=post.url,
                        kind=post.kind)
    # discovery never auto-replies (V-02): force assisted path
    forced = account
    if forced and forced.mode == "auto":
        # evaluate as assisted regardless of account mode
        parsed_account = Account(handle=forced.handle, mode="assisted", tier=forced.tier,
                                 id=forced.id)
        outcome = pipeline.process_post(session, parsed, parsed_account)
    else:
        outcome = pipeline.process_post(session, parsed, forced)
    item.status = "promoted"
    session.add(item)
    session.commit()
    return outcome


def list_discovery(session: Session) -> list[dict]:
    items = session.exec(select(DiscoveryItem).where(
        DiscoveryItem.status == "new").order_by(DiscoveryItem.relevance.desc())).all()
    out = []
    for it in items:
        post = session.get(Post, it.post_id)
        out.append({"id": it.id, "source": it.source, "query": it.query,
                    "relevance": it.relevance,
                    "text": post.text if post else "",
                    "author": post.author_handle if post else ""})
    return out


def record_engagement(session: Session, handle: str) -> None:
    person = session.get(Person, handle)
    if person is None:
        person = Person(handle=handle, first_seen=datetime.now(timezone.utc))
    person.engagements += 1
    person.last_engaged_at = datetime.now(timezone.utc)
    session.add(person)
    session.commit()


def ingest_notifications(session: Session) -> int:
    """V-04: scrape mentions/replies to the operator's posts on a schedule."""
    from ..db.models import Notification
    bus = get_bus()
    rows = bus.submit_read("notifications", "")
    n = 0
    for p in rows or []:
        exists = session.exec(select(Notification).where(
            Notification.x_post_id == p.x_post_id)).first()
        if exists:
            continue
        session.add(Notification(x_post_id=p.x_post_id, author_handle=p.author_handle,
                                 text=p.text, kind=p.kind or "mention",
                                 created_at=p.created_at))
        n += 1
    session.commit()
    return n


def list_people(session: Session) -> list[dict]:
    people = session.exec(select(Person).order_by(Person.engagements.desc())).all()
    return [{"handle": p.handle, "engagements": p.engagements,
             "last_engaged_at": p.last_engaged_at.isoformat() if p.last_engaged_at else None,
             "avg_reply_likes": p.avg_reply_likes, "notes": p.notes} for p in people]
