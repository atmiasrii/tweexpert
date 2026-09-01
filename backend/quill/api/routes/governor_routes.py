"""Governor: caps, usage, mode, next slot; kill + panic (§11, §18)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from ...bus.action_bus import get_bus
from ...db.engine import get_session
from ...db.models import Account
from ...db.settings_store import get_setting
from ...defaults import (CAP_POSTS, CAP_REPLIES_ASSISTED, CAP_REPLIES_AUTO,
                        CAP_THREADS, DAILY_READ_BUDGET)
from ...governor import governor
from ...ops import session_guard
from ..auth import require_auth
from ..events import publish

router = APIRouter(prefix="/api/governor", tags=["governor"])


def _global_mode(session: Session) -> str:
    modes = [a.mode for a in session.exec(select(Account)).all()]
    if "auto" in modes:
        return "auto"
    if "assisted" in modes:
        return "assisted"
    return "shadow"


@router.get("")
def get_governor(session: Session = Depends(get_session), _=Depends(require_auth)):
    day = governor.get_day(session)
    from ...ops.health import latest_health
    h = latest_health(session)
    return {
        "date": day.date,
        "mode": _global_mode(session),
        "usage": {
            "replies_assisted": {"used": day.replies_assisted,
                                 "cap": get_setting(session, "cap_replies_assisted", CAP_REPLIES_ASSISTED)},
            "replies_auto": {"used": day.replies_auto,
                             "cap": get_setting(session, "cap_replies_auto", CAP_REPLIES_AUTO)},
            "posts": {"used": day.posts, "cap": get_setting(session, "cap_posts", CAP_POSTS)},
            "threads": {"used": day.threads, "cap": get_setting(session, "cap_threads", CAP_THREADS)},
            "reads": day.reads,
            # The read budget is a real ceiling: once it is spent the watcher
            # stops pulling posts for the rest of the day, so the UI has to be
            # able to say that out loud.
            "read_budget": get_setting(session, "daily_read_budget", DAILY_READ_BUDGET),
        },
        "kill_switch": day.kill_switch or get_setting(session, "kill_switch", False),
        "quiet_now": governor.in_quiet_hours(session),
        "next_slot": governor.next_available_slot(session).isoformat(),
        "session_ok": h.session_ok if h else True,
        "canary_ok": h.canary_ok if h else True,
        "no_auto_today": day.no_auto_today,
    }


class KillBody(BaseModel):
    on: bool


@router.post("/kill")
def kill(body: KillBody, session: Session = Depends(get_session),
         _=Depends(require_auth)):
    governor.set_kill(session, body.on)
    publish("kill_switch", {"on": body.on})
    return {"kill_switch": body.on}


@router.post("/panic")
def panic(session: Session = Depends(get_session), _=Depends(require_auth)):
    ids = governor.panic(session, delete_last_n=5)
    deleted = []
    for x in ids:
        if get_bus().submit_delete(x, issuer="human"):
            deleted.append(x)
    publish("panic", {"deleted": deleted})
    return {"kill_switch": True, "deleted": deleted}
