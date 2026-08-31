"""Notification actions (K-02, K-04). Token-authenticated (single-use, expiring,
draft-bound) because the notification channel is less trusted than the
dashboard. Approving here issues a HUMAN authorization via the SAME code path."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from ...bus.action_bus import get_bus
from ...config import get_settings
from ...db.engine import get_session
from ...pipeline.approve import ApproveError, approve_draft, dismiss_draft
from ...security import verify_action_token
from ..events import publish

router = APIRouter(prefix="/api/notify", tags=["notify"])


def _check(draft_id: int, token: str):
    if not verify_action_token(get_settings().secret_key, token, draft_id):
        raise HTTPException(403, "invalid or expired notification token")


@router.get("/approve")
@router.post("/approve")
def approve(draft_id: int = Query(...), token: str = Query(...),
            session: Session = Depends(get_session)):
    _check(draft_id, token)
    try:
        result = approve_draft(session, draft_id, None)
    except ApproveError as e:
        raise HTTPException(400, str(e))
    publish("draft_sent", result)
    return {"ok": True, **result}


@router.get("/skip")
@router.post("/skip")
def skip(draft_id: int = Query(...), token: str = Query(...),
         session: Session = Depends(get_session)):
    _check(draft_id, token)
    try:
        result = dismiss_draft(session, draft_id, "skipped from notification")
    except ApproveError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, **result}


@router.get("/delete")
@router.post("/delete")
def delete(x_post_id: str = Query(...), token: str = Query(...),
           draft_id: int = Query(default=0), session: Session = Depends(get_session)):
    # Y-05: one-tap delete of an auto-sent reply
    if draft_id and not verify_action_token(get_settings().secret_key, token, draft_id):
        raise HTTPException(403, "invalid token")
    ok = get_bus().submit_delete(x_post_id, issuer="human")
    publish("post_deleted", {"x_post_id": x_post_id, "ok": ok})
    return {"ok": ok}
