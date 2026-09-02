"""Analytics (§15). Scrape own posts on a decaying schedule and store time
series (M-01). Views compute performance (M-02), reply outcomes (M-03),
follower trend (M-04)."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..bus.action_bus import get_bus
from ..config import get_settings
from ..db.models import Draft, MetricSample, Post
from ..defaults import METRIC_SCHEDULE_S


def sample_own_posts(session: Session) -> int:
    """Scrape metrics for own posts whose next decay checkpoint is due."""
    bus = get_bus()
    own = session.exec(select(Post).where(Post.is_own == True)).all()  # noqa: E712
    n = 0
    for p in own:
        if not _due(session, p):
            continue
        parsed = bus.submit_read("metrics", p.x_post_id)
        if parsed:
            session.add(MetricSample(x_post_id=p.x_post_id, likes=parsed.likes,
                                     reposts=parsed.reposts, replies=parsed.replies,
                                     views=parsed.views))
            n += 1
    session.commit()
    return n


def _due(session: Session, post: Post) -> bool:
    if not post.created_at:
        return False
    created = post.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - created).total_seconds()
    samples = session.exec(
        select(MetricSample).where(MetricSample.x_post_id == post.x_post_id)).all()
    taken = len(samples)
    for i, checkpoint in enumerate(METRIC_SCHEDULE_S):
        if age >= checkpoint and taken <= i:
            return True
    return False


def register_own_post(session: Session, x_post_id: str, text: str,
                      category: str = "", kind: str = "post") -> None:
    row = session.exec(select(Post).where(Post.x_post_id == x_post_id)).first()
    if row:
        row.is_own = True
        session.add(row)
    else:
        session.add(Post(x_post_id=x_post_id, author_handle=get_settings().operator_handle,
                         text=text, created_at=datetime.now(timezone.utc), is_own=True,
                         kind=kind, metrics_json=json.dumps({"category": category})))
    session.commit()


# --- views --------------------------------------------------------------
def post_performance(session: Session) -> list[dict]:
    own = session.exec(select(Post).where(Post.is_own == True)).all()  # noqa: E712
    out = []
    for p in own:
        latest = session.exec(
            select(MetricSample).where(MetricSample.x_post_id == p.x_post_id)
            .order_by(MetricSample.at.desc())).first()
        meta = json.loads(p.metrics_json or "{}")
        out.append({
            "x_post_id": p.x_post_id, "text": p.text, "kind": p.kind,
            "category": meta.get("category", ""),
            "length": len(p.text),
            "hour": p.created_at.hour if p.created_at else None,
            "likes": latest.likes if latest else 0,
            "views": latest.views if latest else 0,
            "reposts": latest.reposts if latest else 0,
        })
    out.sort(key=lambda r: r["likes"], reverse=True)
    return out


def reply_outcomes(session: Session) -> list[dict]:
    """M-03: did the reply get engagement, by draft angle."""
    sent = session.exec(select(Draft).where(Draft.status == "sent",
                                            Draft.kind == "reply")).all()
    by_angle = defaultdict(lambda: {"count": 0, "likes": 0})
    rows = []
    for d in sent:
        cands = json.loads(d.candidates_json or "[]")
        angle = cands[d.chosen_index]["angle"] if cands and d.chosen_index < len(cands) else "?"
        by_angle[angle]["count"] += 1
        rows.append({"draft_id": d.id, "text": d.final_text, "angle": angle,
                     "relevance": d.relevance})
    return [{"angle": a, **v} for a, v in by_angle.items()] or rows


def _action_for_draft(session: Session, draft_id: int):
    """The publish Action behind a draft, found through its authorization.

    The draft row never stores the resulting post id, so the audit trail is the
    only link between "we approved this text" and "this is where it landed".
    """
    from ..db.models import Action, Authorization
    authz_ids = [a.id for a in session.exec(
        select(Authorization).where(Authorization.draft_id == draft_id)).all()]
    if not authz_ids:
        return None
    rows = session.exec(
        select(Action).where(Action.kind == "reply",
                             Action.authorization_id.in_(authz_ids))
        .order_by(Action.created_at.desc())).all()
    # Prefer one that actually produced a post id.
    for a in rows:
        if a.x_post_id:
            return a
    return rows[0] if rows else None


def _samples(session: Session, x_post_id: str) -> list:
    if not x_post_id:
        return []
    return session.exec(
        select(MetricSample).where(MetricSample.x_post_id == x_post_id)
        .order_by(MetricSample.at.asc())).all()


def _stage(draft, action, samples) -> tuple[str, str]:
    """Where this reply has got to, and one line of plain English for it."""
    if draft.status == "dismissed":
        return "skipped", "You skipped this one."
    if draft.status == "queued":
        return "waiting", "Waiting for you to approve or skip it."
    if draft.status == "shadow":
        return "practice", "Practice mode. This was never going to send."
    if draft.status in ("approved", "ready") and not (action and action.x_post_id):
        return "sending", "Approved. Waiting for your browser to post it."
    if action and action.state == "failed":
        return "failed", f"Posting failed: {action.error or 'unknown error'}"
    if not (action and action.x_post_id):
        return "sending", "Marked sent, but no post link was recorded."
    if not samples:
        return "posted", "Live on X. First measurement comes about an hour in."
    if samples[-1].replies > 0:
        return "answered", "Someone replied to it. That is the outcome worth having."
    return "measured", "Live and measured. Nobody has replied under it yet."


def sent_replies(session: Session, limit: int = 60) -> list[dict]:
    """Every reply Quill has put out, newest first, with where each one got to."""
    drafts = session.exec(
        select(Draft).where(Draft.kind == "reply",
                            Draft.status.in_(["sent", "approved", "ready"]))
        .order_by(Draft.created_at.desc()).limit(limit)).all()
    out = []
    for d in drafts:
        action = _action_for_draft(session, d.id)
        xid = action.x_post_id if action else ""
        samples = _samples(session, xid)
        latest = samples[-1] if samples else None
        parent = session.get(Post, d.parent_post_id) if d.parent_post_id else None
        stage, note = _stage(d, action, samples)
        cands = json.loads(d.candidates_json or "[]")
        angle = (cands[d.chosen_index]["angle"]
                 if cands and d.chosen_index < len(cands) else "")
        out.append({
            "draft_id": d.id,
            "x_post_id": xid,
            "text": d.final_text,
            "stage": stage,
            "note": note,
            "angle": angle,
            "mode": d.mode_at_creation,
            "auto": d.mode_at_creation in ("auto", "foryou"),
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "sent_at": (action.finished_at or action.created_at).isoformat()
                       if action and (action.finished_at or action.created_at) else None,
            "to": parent.author_handle if parent else "",
            "parent_text": parent.text if parent else "",
            "url": f"https://x.com/i/status/{xid}" if xid else "",
            "likes": latest.likes if latest else 0,
            "replies": latest.replies if latest else 0,
            "views": latest.views if latest else 0,
            "samples": len(samples),
        })
    return out


def reply_detail(session: Session, draft_id: int) -> dict:
    """One reply, in full: what it answered, where it is, and how it has moved."""
    d = session.get(Draft, draft_id)
    if not d:
        raise ValueError("draft not found")
    action = _action_for_draft(session, d.id)
    xid = action.x_post_id if action else ""
    samples = _samples(session, xid)
    parent = session.get(Post, d.parent_post_id) if d.parent_post_id else None
    stage, note = _stage(d, action, samples)

    # The timeline the operator actually cares about, in order.
    steps = [{"key": "drafted", "label": "Quill wrote it",
              "at": d.created_at.isoformat() if d.created_at else None, "done": True}]
    approved_at = action.created_at if action else None
    steps.append({"key": "approved",
                  "label": "Sent on its own" if d.mode_at_creation in ("auto", "foryou")
                           else "You approved it",
                  "at": approved_at.isoformat() if approved_at else None,
                  "done": bool(action)})
    steps.append({"key": "posted", "label": "Posted to X",
                  "at": (action.finished_at.isoformat()
                         if action and action.finished_at else None),
                  "done": bool(xid)})
    steps.append({"key": "measured", "label": "Checked how it did",
                  "at": samples[0].at.isoformat() if samples else None,
                  "done": bool(samples),
                  "detail": (f"{len(samples)} of {len(METRIC_SCHEDULE_S)} checks done"
                             if samples else "first check about an hour after posting")})
    answered = bool(samples and samples[-1].replies > 0)
    steps.append({"key": "answered", "label": "Someone replied to it",
                  "at": None, "done": answered,
                  "detail": ("worth 150 likes to the algorithm" if answered
                             else "the outcome this is all aimed at")})

    return {
        "draft_id": d.id, "x_post_id": xid, "text": d.final_text,
        "stage": stage, "note": note, "status": d.status,
        "mode": d.mode_at_creation,
        "relevance": d.relevance,
        "critic": json.loads(d.critic_json or "[]"),
        "candidates": json.loads(d.candidates_json or "[]"),
        "chosen_index": d.chosen_index,
        "to": parent.author_handle if parent else "",
        "parent_text": parent.text if parent else "",
        "parent_url": parent.url if parent else "",
        "url": f"https://x.com/i/status/{xid}" if xid else "",
        "error": action.error if action else "",
        "steps": steps,
        "series": [{"at": s.at.isoformat(), "likes": s.likes, "replies": s.replies,
                    "reposts": s.reposts, "views": s.views} for s in samples],
    }


def reply_scoreboard(session: Session) -> dict:
    """The metric the whole reply strategy is aimed at.

    A conversation continuing under your reply is the event the ranker pays
    75.0 for, against 0.5 for a like. So "how often does my reply get answered"
    is the number to steer on, and likes are close to noise.

    Caveat kept in the payload: X does not expose *who* replied, so a reply
    with `replies > 0` counted here may have been answered by a bystander
    rather than the original author. It is an upper bound on reply-backs, and
    a real one to watch over time.
    """
    own_replies = session.exec(
        select(Post).where(Post.is_own == True, Post.kind == "reply")).all()  # noqa: E712
    measured, answered, likes = 0, 0, 0
    for p in own_replies:
        latest = session.exec(
            select(MetricSample).where(MetricSample.x_post_id == p.x_post_id)
            .order_by(MetricSample.at.desc())).first()
        if not latest:
            continue
        measured += 1
        likes += latest.likes
        if latest.replies > 0:
            answered += 1
    return {
        "replies_sent": len(own_replies),
        "measured": measured,
        "answered": answered,
        "answer_rate": round(100 * answered / measured, 1) if measured else None,
        "likes_per_reply": round(likes / measured, 2) if measured else None,
        "needs_more": max(0, 10 - measured),
        "note": "A reply counts as answered when anyone replied under it. "
                "X does not say whether it was the original author, so treat "
                "this as the ceiling on your true reply-back rate.",
    }


def follower_series(session: Session) -> list[dict]:
    from ..db.settings_store import get_setting
    return get_setting(session, "follower_series", [])


def sample_followers(session: Session, count: int) -> None:
    from ..db.settings_store import get_setting, set_setting
    series = get_setting(session, "follower_series", [])
    series.append({"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                   "count": count})
    set_setting(session, "follower_series", series[-365:])
