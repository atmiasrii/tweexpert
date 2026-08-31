"""Chrome extension surface (A-X1). Localhost + shared secret only. The
extension is a UI surface, not a separate write path — all writes still go
through the action bus via /api/drafts/{id}/approve."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from ...browser.base import ParsedPost
from ...db.engine import get_session
from ...db.models import Account, Draft, Post
from ...pipeline import pipeline
from ..auth import require_auth_or_extension

router = APIRouter(prefix="/api/ext", tags=["extension"])


class ReportedPost(BaseModel):
    x_post_id: str
    author_handle: str
    text: str
    url: str = ""
    kind: str = "post"


class ReportBody(BaseModel):
    posts: list[ReportedPost]


@router.post("/report")
def report_posts(body: ReportBody, request: Request,
                 session: Session = Depends(get_session),
                 auth: dict = Depends(require_auth_or_extension)):
    """Content script reports posts it read from the live timeline DOM."""
    processed = 0
    for rp in body.posts:
        account = session.exec(select(Account).where(
            Account.handle == rp.author_handle)).first()
        parsed = ParsedPost(x_post_id=rp.x_post_id, author_handle=rp.author_handle,
                            text=rp.text, created_at=datetime.now(timezone.utc),
                            url=rp.url, kind=rp.kind)
        pipeline.process_post(session, parsed, account)
        processed += 1
    return {"processed": processed}


@router.get("/queue")
def queue_for_author(author: str = "", session: Session = Depends(get_session),
                     auth: dict = Depends(require_auth_or_extension)):
    """Sidebar queue for the current page's author (A-X1)."""
    q = select(Draft).where(Draft.status == "queued")
    drafts = session.exec(q).all()
    out = []
    for d in drafts:
        parent = session.get(Post, d.parent_post_id) if d.parent_post_id else None
        if author and (not parent or parent.author_handle != author):
            continue
        out.append({"id": d.id, "final_text": d.final_text,
                    "relevance": d.relevance,
                    "author": parent.author_handle if parent else None,
                    "parent_text": parent.text if parent else None})
    return out


class ExtKillBody(BaseModel):
    on: bool


@router.post("/kill")
def ext_kill(body: ExtKillBody, session: Session = Depends(get_session),
             auth: dict = Depends(require_auth_or_extension)):
    from ...governor import governor
    from ..events import publish
    governor.set_kill(session, body.on)
    publish("kill_switch", {"on": body.on})
    return {"kill_switch": body.on}


@router.get("/safeguard")
def safeguard(session: Session = Depends(get_session),
              auth: dict = Depends(require_auth_or_extension)):
    """Popup safeguard meter + kill switch state."""
    from ...governor import governor
    from ...db.settings_store import get_setting
    day = governor.get_day(session)
    return {"kill_switch": day.kill_switch or get_setting(session, "kill_switch", False),
            "replies_auto": day.replies_auto, "replies_assisted": day.replies_assisted,
            "quiet_now": governor.in_quiet_hours(session)}
