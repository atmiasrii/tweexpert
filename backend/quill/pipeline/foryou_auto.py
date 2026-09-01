"""For-You auto-reply loop.

Every few minutes: read the For-You / home feed, take the few most relevant
posts, draft in the operator's voice, and — if they clear the critic + safety
gates — reply on their own. This is the operator's explicit, aggressive choice
(replying to strangers on the feed), so it runs on its OWN daily budget rather
than the conservative per-account auto cap, but it still honours the safeties
that actually matter for staying alive: the kill switch, quiet hours, minimum
spacing between writes, and the burst guard.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlmodel import Session

from ..bus.action_bus import get_bus
from ..bus.authz import ActionAuthorization, issue
from ..config import get_settings
from ..db.models import Draft, Post
from ..db.settings_store import get_setting, set_setting
from ..governor import governor
from ..logging_setup import get_logger
from ..persona import engine as persona
from . import live_state, pipeline, relevance as relevance_mod
from .blocklist import block_reason, unsafe_to_send

log = get_logger("quill.foryou")

# Settings keys + defaults.
K_ENABLED = "foryou_enabled"
K_INTERVAL = "foryou_interval_min"
K_PER_RUN = "foryou_per_run"
K_MODE = "foryou_mode"           # "auto" (send) | "assisted" (queue)
DEFAULTS = {K_ENABLED: False, K_INTERVAL: 5, K_PER_RUN: 5, K_MODE: "assisted"}


def config(session: Session) -> dict:
    return {k: get_setting(session, k, v) for k, v in DEFAULTS.items()}


def set_config(session: Session, **kw) -> dict:
    cur = config(session)
    for k in DEFAULTS:
        if k in kw and kw[k] is not None:
            cur[k] = kw[k]
            set_setting(session, k, kw[k])
    return cur


K_LAST_RUN = "foryou_last_run"
AXES = ["sounds_like_operator", "adds_something", "reads_human", "low_embarrassment_risk"]


def draft_for_post(session: Session, parsed, mode: str = "auto",
                   fast: bool = False) -> dict:
    """Draft one reply for a single feed post (used by the extension live feed).
    Returns the suggestion + whether it is confident enough to auto-send (hybrid).
    Never sends here — the extension or the operator does that.

    fast=True uses a single quick draft (no critic loop) so the live feed stays
    responsive; those are always 1-click (auto=False)."""
    from ..browser.base import ParsedPost  # noqa: F401 (type hint clarity)
    from sqlmodel import select
    op = get_settings().operator_handle
    if parsed.author_handle == op:
        return {"ok": False, "reason": "own post"}
    br = block_reason(session, parsed, auto=(mode == "auto"))
    if br:
        return {"ok": False, "reason": br}

    # reuse an existing fresh draft for this post if we already made one
    post_row = pipeline.upsert_post(session, parsed)
    existing = session.exec(
        select(Draft).where(
            Draft.parent_post_id == post_row.id,
            Draft.status.in_(["queued", "sent", "approved"]))).first()
    if existing:
        return {"ok": True, "draft_id": existing.id, "text": existing.final_text,
                "confidence": existing.relevance, "auto": False,
                "status": existing.status, "parent_x_id": parsed.x_post_id,
                "author": parsed.author_handle}

    live_state.record(session, "drafting", f"writing a reply to @{parsed.author_handle}",
                      target=parsed.author_handle, post_x_id=parsed.x_post_id)

    if fast:
        from ..pipeline.blocklist import unsafe_to_send
        text = persona.quick_reply(session, parsed.text)
        if not text or unsafe_to_send(text, session):
            return {"ok": False, "reason": "no clean quick draft"}
        draft = Draft(kind="reply", parent_post_id=post_row.id, final_text=text,
                      relevance=0, mode_at_creation="foryou", chosen_index=0,
                      candidates_json=json.dumps([{"angle": "quick", "text": text}]),
                      critic_json="[]", status="queued")
        session.add(draft)
        session.commit()
        session.refresh(draft)
        live_state.record(session, "queued", "drafted from your feed",
                          target=parsed.author_handle, post_x_id=parsed.x_post_id,
                          draft_id=draft.id)
        return {"ok": True, "draft_id": draft.id, "text": text, "confidence": 0,
                "auto": False, "status": "queued", "parent_x_id": parsed.x_post_id,
                "author": parsed.author_handle}

    result = persona.generate(session, parsed.text, account_handle=parsed.author_handle,
                              auto=(mode == "auto"))
    if not result.has_output:
        live_state.record(session, "silent", "no good angle", target=parsed.author_handle,
                          post_x_id=parsed.x_post_id)
        return {"ok": False, "reason": "no good angle"}

    chosen = result.candidates[result.chosen_index]
    crit = chosen.critic or {}
    axis_sum = sum(int(crit.get(a, 0)) for a in AXES)
    unsafe = unsafe_to_send(result.final_text, session)
    high_conf = (all(int(crit.get(a, 0)) >= 4 for a in AXES)
                 and axis_sum >= get_setting(session, "foryou_auto_min", 18)
                 and not unsafe)

    draft = Draft(kind="reply", parent_post_id=post_row.id, final_text=result.final_text,
                  relevance=chosen.critic and axis_sum or 0, mode_at_creation="foryou",
                  candidates_json=json.dumps([_cd(c) for c in result.candidates]),
                  critic_json=json.dumps([c.critic for c in result.candidates]),
                  chosen_index=result.chosen_index or 0, status="queued")
    session.add(draft)
    session.commit()
    session.refresh(draft)
    live_state.record(session, "queued", "drafted from your feed", target=parsed.author_handle,
                      post_x_id=parsed.x_post_id, draft_id=draft.id)
    return {"ok": True, "draft_id": draft.id, "text": draft.final_text,
            "confidence": axis_sum, "auto": high_conf and mode == "auto",
            "status": "queued", "parent_x_id": parsed.x_post_id,
            "author": parsed.author_handle}


def tick(session: Session) -> dict | None:
    """Called on a short scheduler; runs a For-You pass when enabled and the
    configured interval has elapsed."""
    cfg = config(session)
    if not cfg[K_ENABLED]:
        return None
    if governor.in_quiet_hours(session):
        return None
    last = get_setting(session, K_LAST_RUN, None)
    now = datetime.now(timezone.utc)
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            if (now - last_dt).total_seconds() < int(cfg[K_INTERVAL]) * 60:
                return None
        except ValueError:
            pass
    set_setting(session, K_LAST_RUN, now.isoformat())
    return run(session)


def run(session: Session, per_run: int | None = None, mode: str | None = None) -> dict:
    cfg = config(session)
    per_run = per_run if per_run is not None else int(cfg[K_PER_RUN])
    mode = mode or cfg[K_MODE]

    bus = get_bus()
    live_state.record(session, "watching", "reading your For You feed", target="For You")
    posts = bus.submit_read("presence", "home") or []
    governor.record_read(session, 1)

    op = get_settings().operator_handle
    scored = []
    for p in posts:
        if p.author_handle == op:
            continue
        scored.append((relevance_mod.score(session, p, None), p))
    scored.sort(key=lambda x: x[0], reverse=True)

    out = {"scanned": len(posts), "picked": 0, "queued": 0, "sent": 0,
           "skipped": 0, "mode": mode, "replies": []}

    for rel, p in scored[: per_run]:
        out["picked"] += 1
        # hard content gates first
        if block_reason(session, p, auto=(mode == "auto")):
            out["skipped"] += 1
            continue
        live_state.record(session, "drafting", f"writing a reply to @{p.author_handle}",
                          target=p.author_handle, post_x_id=p.x_post_id)
        result = persona.generate(session, p.text, account_handle=p.author_handle,
                                  auto=(mode == "auto"))
        if not result.has_output:
            out["skipped"] += 1
            live_state.record(session, "silent", "no good angle", target=p.author_handle,
                              post_x_id=p.x_post_id)
            continue

        post_row = pipeline.upsert_post(session, p)
        draft = Draft(kind="reply", parent_post_id=post_row.id, final_text=result.final_text,
                      relevance=rel, mode_at_creation="foryou",
                      candidates_json=json.dumps([_cd(c) for c in result.candidates]),
                      critic_json=json.dumps([c.critic for c in result.candidates]),
                      chosen_index=result.chosen_index or 0, status="queued")
        session.add(draft)
        session.commit()
        session.refresh(draft)

        if mode != "auto":
            # assisted: drop it in the review queue
            out["queued"] += 1
            out["replies"].append({"author": p.author_handle, "text": draft.final_text,
                                   "status": "queued"})
            live_state.record(session, "queued", "waiting for you", target=p.author_handle,
                              post_x_id=p.x_post_id, draft_id=draft.id)
            continue

        # auto: safety gate, then send on its own within the For-You budget
        unsafe = unsafe_to_send(draft.final_text, session)
        chosen = result.candidates[result.chosen_index]
        if unsafe or not chosen.critic.get("auto_ok"):
            draft.status = "queued"           # fall back to the queue, never drop
            session.add(draft)
            session.commit()
            out["queued"] += 1
            live_state.record(session, "queued", f"held for review ({unsafe or 'critic'})",
                              target=p.author_handle, post_x_id=p.x_post_id, draft_id=draft.id)
            continue
        try:
            governor.check_write_allowed(session, "reply", "foryou")
        except governor.GovernorRefusal as e:
            draft.status = "queued"
            session.add(draft)
            session.commit()
            out["queued"] += 1
            log.info("for-you send held: %s", e.reason)
            live_state.record(session, "queued", f"held: {e.reason}", target=p.author_handle,
                              post_x_id=p.x_post_id, draft_id=draft.id)
            continue

        authz = issue(session, draft.id, issuer="policy", mode="foryou",
                      reasons=["for-you auto reply", f"relevance {rel}"])
        live_state.record(session, "sending", f"sending a reply to @{p.author_handle}",
                          target=p.author_handle, post_x_id=p.x_post_id, draft_id=draft.id)
        try:
            action = bus.submit_write("reply", p.x_post_id, draft.final_text, authz,
                                      issuer="policy", draft_id=draft.id)
            out["sent"] += 1
            out["replies"].append({"author": p.author_handle, "text": draft.final_text,
                                   "status": "sent", "x_post_id": action.x_post_id})
            live_state.record(session, "sent", f"replied to @{p.author_handle}",
                              target=p.author_handle, post_x_id=action.x_post_id, draft_id=draft.id)
            _push_sent(session, draft, action.x_post_id, p.author_handle)
        except Exception as e:
            log.warning("for-you send failed: %s", e)
            out["skipped"] += 1

    log.info("for-you run: %s", {k: out[k] for k in ("picked", "queued", "sent", "skipped")})
    return out


def _cd(c) -> dict:
    return {"angle": c.angle, "text": c.text, "critic": c.critic,
            "prefilter_ok": c.prefilter_ok, "prefilter_reason": c.prefilter_reason}


def _push_sent(session, draft, x_post_id, author):
    from ..notify import notifier
    from ..security import make_action_token
    from ..defaults import NOTIFY_TOKEN_TTL_S
    s = get_settings()
    token = make_action_token(s.secret_key, draft.id, NOTIFY_TOKEN_TTL_S)
    url = f"{s.public_base_url}/api/notify/delete?x_post_id={x_post_id}&token={token}&draft_id={draft.id}"
    notifier.notify("auto_sent", f"Auto-replied to @{author}", draft.final_text,
                    draft_id=draft.id, actions=[{"label": "Delete", "url": url}])
