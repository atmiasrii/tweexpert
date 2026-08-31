"""Autopilot: queue, approve/dismiss/regenerate, shadow log, delete post."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ...bus.authz import issue
from ...bus.action_bus import get_bus
from ...db.engine import get_session
from ...db.models import Account, Draft, Post
from ...learning import feedback
from ...pipeline import pipeline
from ...pipeline.approve import ApproveError, approve_draft, dismiss_draft
from ..auth import require_auth
from ..events import publish

router = APIRouter(prefix="/api", tags=["autopilot"])


def _draft_view(session: Session, d: Draft) -> dict:
    parent = session.get(Post, d.parent_post_id) if d.parent_post_id else None
    acc = session.get(Account, d.account_id) if d.account_id else None
    return {
        "id": d.id, "kind": d.kind, "status": d.status,
        "relevance": d.relevance, "final_text": d.final_text,
        "chosen_index": d.chosen_index,
        "candidates": json.loads(d.candidates_json or "[]"),
        "critic": json.loads(d.critic_json or "[]"),
        "mode_at_creation": d.mode_at_creation,
        "would_have_sent_at": d.would_have_sent_at.isoformat() if d.would_have_sent_at else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "parent": {"author": parent.author_handle, "text": parent.text,
                   "x_post_id": parent.x_post_id} if parent else None,
        "account": acc.handle if acc else None,
    }


@router.get("/queue")
def get_queue(session: Session = Depends(get_session), _=Depends(require_auth)):
    drafts = session.exec(select(Draft).where(Draft.status == "queued")
                          .order_by(Draft.relevance.desc())).all()
    return [_draft_view(session, d) for d in drafts]


class ApproveBody(BaseModel):
    text: str | None = None


@router.post("/drafts/{draft_id}/approve")
def approve(draft_id: int, body: ApproveBody,
            session: Session = Depends(get_session), _=Depends(require_auth)):
    try:
        result = approve_draft(session, draft_id, body.text)
    except ApproveError as e:
        raise HTTPException(400, str(e))
    publish("draft_sent", result)
    return result


class DismissBody(BaseModel):
    reason: str = ""


@router.post("/drafts/{draft_id}/dismiss")
def dismiss(draft_id: int, body: DismissBody,
            session: Session = Depends(get_session), _=Depends(require_auth)):
    try:
        result = dismiss_draft(session, draft_id, body.reason)
    except ApproveError as e:
        raise HTTPException(400, str(e))
    publish("draft_dismissed", result)
    return result


@router.post("/drafts/{draft_id}/regenerate")
def regenerate(draft_id: int, session: Session = Depends(get_session),
               _=Depends(require_auth)):
    draft = session.get(Draft, draft_id)
    if not draft:
        raise HTTPException(404)
    parent = session.get(Post, draft.parent_post_id) if draft.parent_post_id else None
    if not parent:
        raise HTTPException(400, "no parent post to regenerate against")
    acc = session.get(Account, draft.account_id) if draft.account_id else None
    from ...browser.base import ParsedPost
    p = ParsedPost(x_post_id=parent.x_post_id, author_handle=parent.author_handle,
                   text=parent.text, created_at=parent.created_at, kind=parent.kind)
    draft.status = "dismissed"
    session.add(draft)
    session.commit()
    outcome = pipeline.process_post(session, p, acc)
    return {"outcome": outcome.status, "draft_id": outcome.draft_id,
            "reason": outcome.reason}


@router.get("/shadow")
def shadow_log(session: Session = Depends(get_session), _=Depends(require_auth)):
    drafts = session.exec(select(Draft).where(Draft.status == "shadow")
                          .order_by(Draft.created_at.desc())).all()
    return [_draft_view(session, d) for d in drafts]


class JudgeBody(BaseModel):
    approve: bool


@router.post("/shadow/{draft_id}/judge")
def shadow_judge(draft_id: int, body: JudgeBody,
                 session: Session = Depends(get_session), _=Depends(require_auth)):
    draft = session.get(Draft, draft_id)
    if not draft:
        raise HTTPException(404)
    draft.shadow_verdict = "approve" if body.approve else "reject"
    # count operator review toward the shadow gate (Y-03)
    acc = session.get(Account, draft.account_id) if draft.account_id else None
    if acc:
        acc.shadow_reviewed_count += 1
        session.add(acc)
    session.add(draft)
    session.commit()
    feedback.record_shadow_judgement(session, draft, body.approve)
    return {"ok": True, "verdict": draft.shadow_verdict}


@router.delete("/posts/{x_post_id}")
def delete_post(x_post_id: str, session: Session = Depends(get_session),
                _=Depends(require_auth)):
    ok = get_bus().submit_delete(x_post_id, issuer="human")
    publish("post_deleted", {"x_post_id": x_post_id, "ok": ok})
    return {"ok": ok, "x_post_id": x_post_id}
