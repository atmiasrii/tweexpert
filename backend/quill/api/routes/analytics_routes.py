"""Analytics + learning exports (§15, §20)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from ...db.engine import get_session
from ...learning import feedback
from ...ops import analytics
from ..auth import require_auth

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/posts")
def posts(session: Session = Depends(get_session), _=Depends(require_auth)):
    return analytics.post_performance(session)


@router.get("/replies")
def replies(session: Session = Depends(get_session), _=Depends(require_auth)):
    return analytics.reply_outcomes(session)


@router.get("/sent")
def sent(session: Session = Depends(get_session), _=Depends(require_auth)):
    """Every reply Quill has put out, with where each one got to."""
    return analytics.sent_replies(session)


@router.get("/sent/{draft_id}")
def sent_detail(draft_id: int, session: Session = Depends(get_session),
                _=Depends(require_auth)):
    try:
        return analytics.reply_detail(session, draft_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/scoreboard")
def scoreboard(session: Session = Depends(get_session), _=Depends(require_auth)):
    """How often a reply gets answered: the number the strategy is aimed at."""
    return analytics.reply_scoreboard(session)


@router.get("/followers")
def followers(session: Session = Depends(get_session), _=Depends(require_auth)):
    return {"series": analytics.follower_series(session)}


@router.get("/approval-rate")
def approval_rate(session: Session = Depends(get_session), _=Depends(require_auth)):
    return {"series": feedback.approval_rate_series(session)}


# --- learning exports (L-03) -------------------------------------------
export = APIRouter(prefix="/api/learning", tags=["learning"])


@export.get("/export/dpo", response_class=PlainTextResponse)
def export_dpo(session: Session = Depends(get_session), _=Depends(require_auth)):
    return feedback.export_dpo(session)


@export.get("/export/sft", response_class=PlainTextResponse)
def export_sft(session: Session = Depends(get_session), _=Depends(require_auth)):
    return feedback.export_sft(session)


@export.get("/counts")
def counts(session: Session = Depends(get_session), _=Depends(require_auth)):
    return feedback.sample_counts(session)
