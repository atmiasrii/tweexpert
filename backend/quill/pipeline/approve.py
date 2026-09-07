"""Approve / dismiss a draft. The SAME code path serves the dashboard tap and
the notification approve (K-02) — no shortcuts."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from ..bus.action_bus import get_bus
from ..bus.authz import issue
from ..db.models import Account, Draft, Post
from ..learning import feedback
from ..logging_setup import get_logger
from ..pipeline.blocklist import unsafe_to_send
from . import discovery
from .pipeline import permalink_for

log = get_logger("quill.approve")


class ApproveError(Exception):
    pass



# The extension counts as available only if it has called us recently.
EXTENSION_STALE_S = 120


def _extension_alive(session: Session) -> bool:
    from ..db.settings_store import get_setting
    seen = get_setting(session, "ext_last_seen", None)
    if not seen:
        return False
    try:
        ts = datetime.fromisoformat(seen)
    except (TypeError, ValueError):
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() < EXTENSION_STALE_S


def approve_draft(session: Session, draft_id: int, text: str | None = None) -> dict:
    draft = session.get(Draft, draft_id)
    if not draft:
        raise ApproveError("draft not found")
    if draft.status not in ("queued", "shadow"):
        raise ApproveError(f"draft not approvable (status {draft.status})")

    final = (text if text is not None else draft.final_text).strip()
    if not final:
        raise ApproveError("empty reply")

    unsafe = unsafe_to_send(final, session)
    if unsafe:
        raise ApproveError(f"content-safety gate: {unsafe}")

    edited = text is not None and text.strip() != draft.final_text.strip()
    before = draft.final_text
    draft.final_text = final
    session.add(draft)
    session.commit()

    # feedback rows (L-01, T-15)
    if edited:
        feedback.record_edit(session, draft, before, final)
    feedback.record_approve(session, draft, final)

    parent = session.get(Post, draft.parent_post_id) if draft.parent_post_id else None
    target = parent.x_post_id if parent else ""
    kind = draft.kind if draft.kind in ("reply", "publish", "thread") else "reply"

    # Extension is the default sender: mark the draft READY (with its permalink)
    # and let the extension post it in the real session — the operator's approvals
    # actually go out even when the Playwright engine is stopped. The extension
    # issues the governor-gated authorization at send time via /api/ext/authorize.
    # Quill's own browser is the sender. The extension may take over, but only
    # when it is actually there: routing approvals to it by default meant every
    # approval sat in "ready" forever, because the extension has never once
    # called the API.
    from ..db.settings_store import get_setting
    sender = get_setting(session, "sender", "browser")
    if sender in ("extension", "auto") and _extension_alive(session):
        draft.status = "ready"
        session.add(draft)
        session.commit()
        if parent:
            discovery.record_engagement(session, parent.author_handle)
        from . import live_state as _ls
        _ls.record(session, "queued", f"ready to send to @{parent.author_handle if parent else '?'}",
                   target=parent.author_handle if parent else "", draft_id=draft.id)
        log.info("draft %s approved -> ready for extension", draft_id)
        return {"draft_id": draft_id, "status": "ready",
                "permalink": parent.url if parent else "",
                "author": parent.author_handle if parent else ""}

    # human authorization (Y-01) — identical to policy path from here on
    authz = issue(session, draft.id, issuer="human",
                  mode=draft.mode_at_creation, reasons=["operator approved"])

    from . import live_state
    live_state.record(session, "sending",
                      f"sending your reply to @{parent.author_handle if parent else '?'}",
                      target=parent.author_handle if parent else "", draft_id=draft.id)

    from ..ops.launcher import writes_deferred
    if writes_deferred(session):
        # api process: enqueue; the browser process (single engine owner) drains
        intent = get_bus().enqueue_write(
            kind, target, final, authz, issuer="human", draft_id=draft.id,
            permalink=permalink_for(parent.author_handle, target, parent.url) if parent else "",
            author=parent.author_handle if parent else "")
        draft.status = "approved"
        session.add(draft)
        session.commit()
        if parent:
            discovery.record_engagement(session, parent.author_handle)
        log.info("draft %s approved -> enqueued action %s", draft_id, intent.id)
        return {"draft_id": draft_id, "status": "queued_for_send",
                "action_id": intent.id}

    action = get_bus().submit_write(
        kind, target, final, authz, issuer="human", draft_id=draft.id,
        permalink=permalink_for(parent.author_handle, target, parent.url) if parent else "",
        author=parent.author_handle if parent else "")
    if parent:
        discovery.record_engagement(session, parent.author_handle)
    live_state.record(session, "sent",
                      f"replied to @{parent.author_handle if parent else '?'}",
                      target=parent.author_handle if parent else "",
                      post_x_id=action.x_post_id, draft_id=draft.id)
    log.info("draft %s approved -> %s", draft_id, action.x_post_id)
    return {"draft_id": draft_id, "x_post_id": action.x_post_id,
            "action_id": action.id}


def dismiss_draft(session: Session, draft_id: int, reason: str = "") -> dict:
    draft = session.get(Draft, draft_id)
    if not draft:
        raise ApproveError("draft not found")
    draft.status = "dismissed"
    session.add(draft)
    session.commit()
    feedback.record_dismiss(session, draft, reason)  # L-01, T-15
    return {"draft_id": draft_id, "status": "dismissed"}
