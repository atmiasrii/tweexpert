"""Chrome extension surface (A-X1). Localhost + shared secret only. The
extension is a UI surface, not a separate write path — all writes still go
through the action bus via /api/drafts/{id}/approve."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from ...browser.base import ParsedPost
from ...bus.authz import ActionAuthorization, consume, issue
from ...config import get_settings
from ...db.engine import get_session
from ...db.models import Account, Action, Authorization, Draft, Post
from ...db.settings_store import get_setting
from ...governor import governor
from ...pipeline import discovery, foryou_auto, live_state
from ...security import make_action_token, verify_action_token
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
    draft: bool = True          # ask the backend to draft suggestions


@router.post("/report")
def report_posts(body: ReportBody, request: Request,
                 session: Session = Depends(get_session),
                 auth: dict = Depends(require_auth_or_extension)):
    """The content script reports the live For-You feed it can see. We draft a
    suggested reply per post (hybrid: `auto` flags the high-confidence ones)."""
    mode = foryou_auto.config(session).get("foryou_mode", "assisted")
    suggestions = []
    for rp in body.posts[:12]:
        parsed = ParsedPost(x_post_id=rp.x_post_id, author_handle=rp.author_handle.lstrip("@"),
                            text=rp.text, created_at=datetime.now(timezone.utc),
                            url=rp.url, kind=rp.kind)
        if not body.draft:
            continue
        try:
            res = foryou_auto.draft_for_post(session, parsed, mode=mode, fast=True)
        except Exception as e:  # never fail the whole batch
            res = {"ok": False, "reason": str(e)[:80]}
        if res.get("ok"):
            suggestions.append({"x_post_id": rp.x_post_id, "draft_id": res["draft_id"],
                                "suggestion": res["text"], "confidence": res["confidence"],
                                "auto": res["auto"], "author": res["author"]})
    return {"processed": len(body.posts), "suggestions": suggestions, "mode": mode}


@router.get("/ready")
def ready(session: Session = Depends(get_session),
          auth: dict = Depends(require_auth_or_extension)):
    """Approved drafts waiting to be posted, with their permalinks — the
    extension opens each in a background tab and replies."""
    out = []
    for d in session.exec(select(Draft).where(Draft.status == "ready")
                          .order_by(Draft.created_at)).all():
        parent = session.get(Post, d.parent_post_id) if d.parent_post_id else None
        if not parent:
            continue
        out.append({"draft_id": d.id, "text": d.final_text,
                    "permalink": parent.url or f"https://x.com/{parent.author_handle}/status/{parent.x_post_id}",
                    "author": parent.author_handle, "x_post_id": parent.x_post_id})
    return {"ready": out}


@router.get("/feed")
def feed(ids: str = "", session: Session = Depends(get_session),
         auth: dict = Depends(require_auth_or_extension)):
    """Suggestions for the currently visible tweet ids (comma-separated)."""
    want = {i for i in ids.split(",") if i}
    out = []
    q = select(Draft).where(Draft.status.in_(["queued", "approved", "sent"]))
    for d in session.exec(q).all():
        parent = session.get(Post, d.parent_post_id) if d.parent_post_id else None
        if not parent:
            continue
        if want and parent.x_post_id not in want:
            continue
        out.append({"x_post_id": parent.x_post_id, "draft_id": d.id,
                    "suggestion": d.final_text, "status": d.status,
                    "author": parent.author_handle})
    return {"feed": out}


class AuthorizeBody(BaseModel):
    draft_id: int


@router.post("/authorize")
def authorize(body: AuthorizeBody, session: Session = Depends(get_session),
              auth: dict = Depends(require_auth_or_extension)):
    """Gate a send at the governor and issue an authorization the extension will
    consume once it has posted in the live session. Keeps caps + audit intact."""
    draft = session.get(Draft, body.draft_id)
    if not draft:
        return {"ok": False, "reason": "draft not found"}
    try:
        governor.check_write_allowed(session, "reply", "foryou")
    except governor.GovernorRefusal as e:
        return {"ok": False, "reason": e.reason}
    authz = issue(session, draft.id, issuer="policy", mode="foryou",
                  reasons=["extension live reply"])
    token = make_action_token(get_settings().secret_key, draft.id, 600)
    parent = session.get(Post, draft.parent_post_id) if draft.parent_post_id else None
    live_state.record(session, "sending", f"sending a reply to @{parent.author_handle if parent else '?'}",
                      target=parent.author_handle if parent else "", draft_id=draft.id)
    return {"ok": True, "draft_id": draft.id, "text": draft.final_text,
            "authz_id": authz.id, "token": token,
            "parent_x_id": parent.x_post_id if parent else ""}


class SentBody(BaseModel):
    draft_id: int
    authz_id: int
    token: str
    x_post_id: str = ""
    ok: bool = True
    error: str = ""


@router.post("/sent")
def sent(body: SentBody, session: Session = Depends(get_session),
         auth: dict = Depends(require_auth_or_extension)):
    """The extension reports the result of a live send. We consume the
    authorization, record the audit row and count it against the governor."""
    if not verify_action_token(get_settings().secret_key, body.token, body.draft_id):
        return {"ok": False, "reason": "bad token"}
    draft = session.get(Draft, body.draft_id)
    arow = session.get(Authorization, body.authz_id)
    if not draft or not arow:
        return {"ok": False, "reason": "unknown draft/authorization"}
    parent = session.get(Post, draft.parent_post_id) if draft.parent_post_id else None
    if body.ok:
        try:
            consume(session, ActionAuthorization(
                id=arow.id, draft_id=arow.draft_id, issuer=arow.issuer, mode=arow.mode,
                reasons=[], issued_at=arow.issued_at, expires_at=arow.expires_at))
        except Exception:
            pass
        governor.record_write(session, "reply", "foryou")
        draft.status = "sent"
        session.add(draft)
        session.add(Action(kind="reply", target=parent.author_handle if parent else "",
                           issuer="extension", state="done", outcome="done",
                           x_post_id=body.x_post_id, authorization_id=arow.id,
                           idempotency_key=f"ext-{body.draft_id}-{body.x_post_id}",
                           finished_at=datetime.now(timezone.utc)))
        session.commit()
        if parent:
            discovery.record_engagement(session, parent.author_handle)
        from ...learning import feedback
        feedback.record_approve(session, draft, draft.final_text)
        live_state.record(session, "sent", f"replied to @{parent.author_handle if parent else '?'}",
                          target=parent.author_handle if parent else "",
                          post_x_id=body.x_post_id, draft_id=draft.id)
        return {"ok": True}
    # failed send — leave the draft queued for another try / the dashboard
    draft.status = "queued"
    session.add(draft)
    session.commit()
    live_state.record(session, "queued", f"live send failed: {body.error[:60]}",
                      target=parent.author_handle if parent else "", draft_id=draft.id)
    return {"ok": False, "reason": body.error or "send failed"}


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
            "replies_foryou": day.replies_foryou, "quiet_now": governor.in_quiet_hours(session)}
