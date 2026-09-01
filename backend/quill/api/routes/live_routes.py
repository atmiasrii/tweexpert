"""Real-time pipeline view + For-You ingestion + following import."""
from __future__ import annotations

import random

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from ...db.engine import get_session
from ...db.models import Account
from ...db.settings_store import get_setting
from ...governor import governor
from ...pipeline import foryou_auto, live_state
from ...pipeline.following import import_following
from ..auth import require_auth

router = APIRouter(prefix="/api", tags=["live"])


@router.get("/live/activity")
def activity(session: Session = Depends(get_session), _=Depends(require_auth)):
    """Everything the dashboard flowchart needs: the fixed stages, the current
    step, and the recent trail."""
    return {
        "stages": [{"id": sid, "label": label} for sid, label in live_state.STAGES],
        "current": live_state.current(session),
        "recent": live_state.recent(session, 40),
    }


@router.post("/live/foryou")
def run_foryou(session: Session = Depends(get_session), _=Depends(require_auth)):
    """Scan the For-You feed once now and draft/reply per the current mode."""
    return foryou_auto.run(session)


@router.get("/live/foryou/config")
def foryou_config(session: Session = Depends(get_session), _=Depends(require_auth)):
    day = governor.get_day(session)
    return {**foryou_auto.config(session),
            "sent_today": day.replies_foryou,
            "cap": get_setting(session, "foryou_daily_cap", 40),
            "last_run": get_setting(session, foryou_auto.K_LAST_RUN, None)}


class ForYouConfig(BaseModel):
    foryou_enabled: bool | None = None
    foryou_interval_min: int | None = None
    foryou_per_run: int | None = None
    foryou_mode: str | None = None


@router.put("/live/foryou/config")
def set_foryou_config(body: ForYouConfig, session: Session = Depends(get_session),
                      _=Depends(require_auth)):
    return foryou_auto.set_config(session, **body.model_dump())


@router.post("/accounts/import-following")
def import_following_route(session: Session = Depends(get_session), _=Depends(require_auth)):
    """Add everyone the operator follows to the watchlist: all assisted, a random
    10 promoted to auto."""
    return import_following(session)
