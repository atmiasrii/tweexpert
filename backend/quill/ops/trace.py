"""Per-run, per-tweet trace: what happened to every post Quill looked at.

"Why did this tweet not get a reply" used to mean reading the activity trail,
the draft row, the action row and three log files, and the activity trail is
pruned to the last two hundred entries anyway. Every stage now also lands here,
keyed by run and post, and on disk as one JSON line per event so it can be
grepped after the fact.

The trace is a witness, never a participant: every call is wrapped so that a
tracing failure cannot stop a sweep or a send.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from ..config import get_settings
from ..db.models import SweepRun, TweetTrace
from ..logging_setup import get_logger

log = get_logger("quill.trace")

# Stages after which nothing else happens to a post in this run.
TERMINAL = {"sent", "scheduled", "queued", "discarded", "silent", "dismissed",
            "skipped", "failed", "needs_review"}

# The run a thread is currently inside. Sends run in their own job with no
# run open, and attach to the post's latest row instead.
_ctx = threading.local()


def current_run_id() -> int | None:
    return getattr(_ctx, "run_id", None)


def start_run(session: Session, kind: str, source: str = "") -> int:
    run = SweepRun(kind=kind, source=source)
    session.add(run)
    session.commit()
    session.refresh(run)
    _ctx.run_id = run.id
    _jsonl({"event": "run_start", "run_id": run.id, "kind": kind, "source": source})
    return run.id


def finish_run(session: Session, run_id: int | None = None, **summary) -> None:
    run_id = run_id or current_run_id()
    if run_id is None:
        return
    try:
        run = session.get(SweepRun, run_id)
        if run is not None:
            run.finished_at = datetime.now(timezone.utc)
            run.summary_json = json.dumps(summary, default=str)
            _recount(session, run)
        _jsonl({"event": "run_end", "run_id": run_id, **summary})
    except Exception as e:                       # a witness must not interfere
        log.warning("trace finish_run: %s", e)
    finally:
        if getattr(_ctx, "run_id", None) == run_id:
            _ctx.run_id = None


def seen(session: Session, post, source: str = "", run_id: int | None = None) -> None:
    """A post surfaced in this run. Creates its row with the metrics we read."""
    run_id = run_id or current_run_id()
    if run_id is None:
        return
    try:
        row = _row(session, run_id, post.x_post_id)
        if row is None:
            row = TweetTrace(run_id=run_id, x_post_id=post.x_post_id)
        row.author = post.author_handle or row.author
        row.source = source or row.source
        row.post_created_at = post.created_at or row.post_created_at
        row.likes = int(getattr(post, "likes", 0) or 0)
        row.replies = int(getattr(post, "replies", 0) or 0)
        row.views = int(getattr(post, "views", 0) or 0)
        _append(row, "seen", source)
        session.add(row)
        session.commit()
        _jsonl({"event": "seen", "run_id": run_id, "post": post.x_post_id,
                "author": row.author, "source": source, "likes": row.likes,
                "replies": row.replies, "views": row.views,
                "post_created_at": str(row.post_created_at or "")})
    except Exception as e:
        log.warning("trace seen: %s", e)


def note(session: Session, x_post_id: str, stage: str, detail: str = "",
         draft_id: int | None = None, relevance: float | None = None,
         sent_x_post_id: str = "", run_id: int | None = None) -> None:
    """Something happened to a post. Attaches to the current run, or to the
    post's most recent row when no run is open (a send, a reconcile)."""
    if not x_post_id:
        return
    try:
        run_id = run_id or current_run_id()
        if run_id:
            row = _row(session, run_id, x_post_id)
        else:
            # No run open: this is a send or a reconcile landing later. Credit
            # the run that scheduled the draft, not whichever later sweep saw
            # the same post again and skipped it as already answered.
            row = _for_draft(session, draft_id) if draft_id else None
            row = row or _latest(session, x_post_id)
        if row is None:
            if run_id is None:
                return                        # nothing to attach to
            row = TweetTrace(run_id=run_id, x_post_id=x_post_id)
        _append(row, stage, detail)
        row.stage = stage
        # "Why" is the last terminal reason. A progress note that follows one
        # ("sending", "watching") still goes on the timeline but must not
        # replace the explanation with a status.
        if detail and (stage in TERMINAL or not row.outcome):
            row.reason = detail
        if draft_id is not None:
            row.draft_id = draft_id
        if relevance is not None:
            row.relevance = relevance
        if sent_x_post_id:
            row.sent_x_post_id = sent_x_post_id
        if stage in TERMINAL:
            row.outcome = stage
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        session.commit()
        # A send lands minutes after the sweep that found the post has closed,
        # so the run's counts cannot be frozen at finish time.
        if stage in TERMINAL or draft_id is not None:
            run = session.get(SweepRun, row.run_id)
            if run is not None:
                _recount(session, run)
        _jsonl({"event": stage, "run_id": row.run_id, "post": x_post_id,
                "detail": detail, "draft_id": row.draft_id,
                "relevance": row.relevance, "sent_x_post_id": sent_x_post_id})
    except Exception as e:
        log.warning("trace note: %s", e)


# ------------------------------------------------------------- reading
def runs(session: Session, limit: int = 40) -> list[dict]:
    rows = session.exec(select(SweepRun).order_by(SweepRun.id.desc()).limit(limit)).all()
    return [_run_dict(r) for r in rows]


def run_detail(session: Session, run_id: int) -> dict | None:
    run = session.get(SweepRun, run_id)
    if run is None:
        return None
    rows = session.exec(select(TweetTrace).where(TweetTrace.run_id == run_id)
                        .order_by(TweetTrace.id)).all()
    return {**_run_dict(run), "posts": [_trace_dict(r) for r in rows]}


def for_post(session: Session, x_post_id: str) -> list[dict]:
    rows = session.exec(select(TweetTrace).where(TweetTrace.x_post_id == x_post_id)
                        .order_by(TweetTrace.id.desc())).all()
    return [_trace_dict(r) for r in rows]


# ------------------------------------------------------------- helpers
def _recount(session: Session, run: SweepRun) -> None:
    rows = session.exec(select(TweetTrace).where(TweetTrace.run_id == run.id)).all()
    run.seen = len(rows)
    # Picked means it went forward, not merely that it was scored: a post
    # binned for being under the relevance floor also carries a score.
    run.picked = sum(1 for r in rows if r.relevance is not None and r.outcome != "skipped")
    run.drafted = sum(1 for r in rows if r.draft_id)
    run.scheduled = sum(1 for r in rows if r.outcome == "scheduled")
    run.sent = sum(1 for r in rows if r.outcome == "sent")
    session.add(run)
    session.commit()


def _row(session: Session, run_id: int, x_post_id: str) -> TweetTrace | None:
    return session.exec(select(TweetTrace).where(
        TweetTrace.run_id == run_id, TweetTrace.x_post_id == x_post_id)).first()


def _for_draft(session: Session, draft_id: int) -> TweetTrace | None:
    return session.exec(select(TweetTrace).where(TweetTrace.draft_id == draft_id)
                        .order_by(TweetTrace.id.desc())).first()


def _latest(session: Session, x_post_id: str) -> TweetTrace | None:
    return session.exec(select(TweetTrace).where(TweetTrace.x_post_id == x_post_id)
                        .order_by(TweetTrace.id.desc())).first()


def _append(row: TweetTrace, stage: str, detail: str) -> None:
    try:
        events = json.loads(row.events_json or "[]")
    except ValueError:
        events = []
    events.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "stage": stage, "detail": detail})
    row.events_json = json.dumps(events)


def _run_dict(r: SweepRun) -> dict:
    try:
        summary = json.loads(r.summary_json or "{}")
    except ValueError:
        summary = {}
    return {"id": r.id, "kind": r.kind, "source": r.source,
            "started_at": r.started_at, "finished_at": r.finished_at,
            "seen": r.seen, "picked": r.picked, "drafted": r.drafted,
            "scheduled": r.scheduled, "sent": r.sent, "summary": summary}


def _trace_dict(r: TweetTrace) -> dict:
    try:
        events = json.loads(r.events_json or "[]")
    except ValueError:
        events = []
    return {"id": r.id, "run_id": r.run_id, "x_post_id": r.x_post_id,
            "author": r.author, "source": r.source,
            "post_created_at": r.post_created_at, "likes": r.likes,
            "replies": r.replies, "views": r.views, "relevance": r.relevance,
            "stage": r.stage, "outcome": r.outcome, "reason": r.reason,
            "draft_id": r.draft_id, "sent_x_post_id": r.sent_x_post_id,
            "events": events, "updated_at": r.updated_at}


def _jsonl(payload: dict) -> None:
    """One line per event under data/traces/YYYY-MM-DD.jsonl."""
    try:
        d = get_settings().data_dir / "traces"
        d.mkdir(parents=True, exist_ok=True)
        # The file is named for the operator's day, like the run record and
        # the governor, so "yesterday's trace" means the same thing everywhere.
        from ..governor.governor import local_now
        path: Path = d / (local_now().strftime("%Y-%m-%d") + ".jsonl")
        payload = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **payload}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass
