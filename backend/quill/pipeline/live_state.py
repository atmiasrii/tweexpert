"""Live pipeline state for the dashboard flowchart.

Every meaningful step the pipeline takes is recorded to the `activity` table so
the dashboard can highlight, in real time, exactly what Quill is doing right now
— reading whom, drafting for what post, sending to whom — regardless of which
process (api, worker, browser) is doing it. Also publishes an in-process SSE
event so the api's own actions update instantly.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from ..db.models import Activity

# The fixed stages the flowchart draws, in order.
STAGES = [
    ("watching", "Reading timelines"),
    ("scoring", "Scoring relevance"),
    ("drafting", "Writing replies"),
    ("reviewing", "Critic + safety"),
    ("queued", "Waiting for you"),
    ("sending", "Posting to X"),
    ("sent", "Sent"),
]
TERMINAL = {"sent", "queued", "discarded", "silent"}


def record(session: Session, stage: str, detail: str = "", target: str = "",
           post_x_id: str = "", draft_id: int | None = None, ok: bool = True) -> None:
    row = Activity(stage=stage, detail=detail, target=target,
                   post_x_id=post_x_id, draft_id=draft_id, ok=ok)
    session.add(row)
    session.commit()
    _prune(session)
    _publish(stage, detail, target, post_x_id, draft_id, ok)


def _prune(session: Session, keep: int = 200) -> None:
    rows = session.exec(select(Activity).order_by(Activity.id.desc())
                        .offset(keep)).all()
    for r in rows:
        session.delete(r)
    if rows:
        session.commit()


def _publish(stage, detail, target, post_x_id, draft_id, ok) -> None:
    try:
        from ..api.events import publish
        publish("activity", {"stage": stage, "detail": detail, "target": target,
                             "post_x_id": post_x_id, "draft_id": draft_id, "ok": ok,
                             "at": datetime.now(timezone.utc).isoformat()})
    except Exception:
        pass  # events hub only exists in the api process; DB row is the source of truth


def recent(session: Session, limit: int = 40) -> list[dict]:
    rows = session.exec(select(Activity).order_by(Activity.id.desc())
                        .limit(limit)).all()
    return [{"id": r.id, "stage": r.stage, "detail": r.detail, "target": r.target,
             "post_x_id": r.post_x_id, "draft_id": r.draft_id, "ok": r.ok,
             "at": (r.at.replace(tzinfo=timezone.utc) if r.at.tzinfo is None
                    else r.at).isoformat()} for r in rows]


def current(session: Session) -> dict:
    rows = recent(session, 1)
    return rows[0] if rows else {"stage": "idle", "detail": "", "target": ""}
