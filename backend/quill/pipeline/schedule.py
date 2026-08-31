"""Compose, schedule, evergreen (§13)."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..bus.action_bus import get_bus
from ..bus.authz import issue
from ..db.models import Draft, QueuedPost, ScheduleSlot
from ..defaults import EVERGREEN_MIN_REPEAT_DAYS
from ..governor import governor
from ..logging_setup import get_logger

log = get_logger("quill.schedule")


def split_thread(text: str, delimiter: str = "---", auto_number: bool = False) -> list[str]:
    parts = [p.strip() for p in text.split(delimiter) if p.strip()]
    if auto_number and len(parts) > 1:
        parts = [f"{p} ({i+1}/{len(parts)})" for i, p in enumerate(parts)]
    return parts


def enqueue_post(session: Session, text: str, category: str = "",
                 evergreen: bool = False, scheduled_for: datetime | None = None) -> QueuedPost:
    order = len(session.exec(select(QueuedPost)).all())
    qp = QueuedPost(text=text, category=category, evergreen=evergreen,
                    min_repeat_days=EVERGREEN_MIN_REPEAT_DAYS,
                    scheduled_for=scheduled_for, order_index=order)
    session.add(qp)
    session.commit()
    session.refresh(qp)
    return qp


def reorder(session: Session, ordered_ids: list[int]) -> None:
    for idx, qid in enumerate(ordered_ids):
        qp = session.get(QueuedPost, qid)
        if qp:
            qp.order_index = idx
            session.add(qp)
    session.commit()


def _last_category(session: Session) -> str:
    last = session.exec(select(QueuedPost).where(QueuedPost.status == "sent")
                        .order_by(QueuedPost.last_posted_at.desc())).first()
    return last.category if last else ""


def pick_next(session: Session) -> QueuedPost | None:
    """Fill a slot: next fresh queued post, category rotation (C-05), else
    evergreen if due (C-06)."""
    last_cat = _last_category(session)
    fresh = session.exec(select(QueuedPost).where(
        QueuedPost.status == "queued", QueuedPost.evergreen == False)  # noqa: E712
        .order_by(QueuedPost.order_index)).all()
    for qp in fresh:
        if qp.category != last_cat or not last_cat:
            return qp
    if fresh:
        return fresh[0]
    # evergreen fallback
    now = datetime.now(timezone.utc)
    evergreens = session.exec(select(QueuedPost).where(
        QueuedPost.evergreen == True)).all()  # noqa: E712
    for qp in evergreens:
        if qp.last_posted_at is None:
            return qp
        lp = qp.last_posted_at
        if lp.tzinfo is None:
            lp = lp.replace(tzinfo=timezone.utc)
        if (now - lp).days >= qp.min_repeat_days:
            return qp
    return None


def send_due_scheduled(session: Session) -> list[str]:
    """Send queued posts whose slot time has arrived, with jitter (C-04)."""
    now = datetime.now(timezone.utc)
    due = session.exec(select(QueuedPost).where(
        QueuedPost.status == "queued", QueuedPost.scheduled_for != None,  # noqa: E711
        QueuedPost.scheduled_for <= now)).all()
    sent = []
    bus = get_bus()
    for qp in due:
        try:
            governor.check_write_allowed(session, "post", "assisted")
        except governor.GovernorRefusal as e:
            log.info("scheduled post held: %s", e.reason)
            continue
        draft = Draft(kind="post", final_text=qp.text, status="approved",
                      mode_at_creation="assisted")
        session.add(draft)
        session.commit()
        session.refresh(draft)
        authz = issue(session, draft.id, "human", "assisted", ["scheduled slot"])
        action = bus.submit_write("publish", "", qp.text, authz, issuer="human",
                                  draft_id=draft.id)
        qp.status = "sent"
        qp.last_posted_at = now
        session.add(qp)
        session.commit()
        from ..ops.analytics import register_own_post
        register_own_post(session, action.x_post_id, qp.text, qp.category, "post")
        sent.append(action.x_post_id)
    return sent


def assign_slots(session: Session) -> int:
    """Map queued posts to upcoming slot times, honouring quiet hours + jitter."""
    slots = session.exec(select(ScheduleSlot).where(
        ScheduleSlot.active == True).order_by(ScheduleSlot.weekday, ScheduleSlot.hour)).all()  # noqa: E712
    unscheduled = session.exec(select(QueuedPost).where(
        QueuedPost.status == "queued", QueuedPost.scheduled_for == None,  # noqa: E711
        QueuedPost.evergreen == False)  # noqa: E712
        .order_by(QueuedPost.order_index)).all()
    if not slots or not unscheduled:
        return 0
    n = 0
    base = datetime.now(timezone.utc)
    for i, qp in enumerate(unscheduled):
        slot = slots[i % len(slots)]
        target = base + timedelta(days=1 + i)
        target = target.replace(hour=slot.hour, minute=slot.minute, second=0)
        target += timedelta(seconds=random.uniform(-600, 600))  # ±10m jitter at send (C-04)
        qp.scheduled_for = target
        if not qp.category:
            qp.category = slot.category
        session.add(qp)
        n += 1
    session.commit()
    return n
