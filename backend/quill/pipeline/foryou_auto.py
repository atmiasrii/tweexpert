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
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..bus.action_bus import get_bus
from ..bus.authz import ActionAuthorization, issue
from ..config import get_settings
from ..db.models import Draft, Post
from ..defaults import (CRITIC_MIN_AUTO, FORYOU_AUTHOR_COOLDOWN_H,
                        FORYOU_PER_RUN, MIN_WRITE_SPACING_S)
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
K_RELEVANCE_MIN = "foryou_relevance_min"
K_COOLDOWN_H = "foryou_author_cooldown_h"

# Both of these are calibrated by scripts/calibrate_threshold.py rather than
# guessed; these are only the starting points.
FORYOU_RELEVANCE_MIN = 55.0
FORYOU_AUTO_MIN = 18

DEFAULTS = {K_ENABLED: False, K_INTERVAL: 90, K_PER_RUN: FORYOU_PER_RUN,
            K_MODE: "assisted", K_RELEVANCE_MIN: FORYOU_RELEVANCE_MIN,
            K_COOLDOWN_H: FORYOU_AUTHOR_COOLDOWN_H}


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
    # "gm" and friends: nothing to add, so skip before spending a model call.
    from ..persona.guards import too_thin
    thin = too_thin(parsed.text)
    if thin:
        return {"ok": False, "reason": thin}

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

    # The fast path skips the critic, so it can never know whether a draft is
    # good enough to send. That is why every extension card was 1-click. When
    # auto-send is on, take the slower scored path instead.
    if fast and mode == "auto":
        fast = False

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
    axis_sum = _axis_sum(crit)
    auto_min = int(get_setting(session, "foryou_auto_min", FORYOU_AUTO_MIN))
    high_conf, _why = _confident(session, result.final_text, crit, auto_min)

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


def _cooldown_authors(session: Session, hours: int) -> set[str]:
    """Authors already answered inside the cooldown window.

    There was no author-level dedupe anywhere before this: one sweep could hand
    the same handle three replies, which is the most obvious bot tell there is.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = session.exec(
        select(Draft).where(Draft.kind == "reply",
                            Draft.status.in_(["sent", "approved", "ready", "needs_review"]),
                            Draft.created_at >= cutoff)).all()
    out: set[str] = set()
    for d in rows:
        if not d.parent_post_id:
            continue
        parent = session.get(Post, d.parent_post_id)
        if parent and parent.author_handle:
            out.add(parent.author_handle.lower())
    return out


def _pick_batch(session: Session, posts: list, mode: str, per_run: int,
                rel_min: float, cooldown_h: int) -> tuple[list, dict]:
    """Choose up to `per_run` posts, one per author, all above the threshold.

    Everything the watcher path already does and this path never did: the hard
    skip gates, a relevance floor, and one reply per author.
    """
    op = get_settings().operator_handle
    recent = _cooldown_authors(session, cooldown_h)
    tally = {"own": 0, "blocked": 0, "skipped": 0, "below_threshold": 0,
             "duplicate_author": 0, "cooldown": 0}

    best: dict[str, tuple[float, object]] = {}
    for p in posts:
        handle = (p.author_handle or "").lower()
        if handle == op.lower():
            tally["own"] += 1
            continue
        if handle in recent:
            tally["cooldown"] += 1
            continue
        if block_reason(session, p, auto=(mode == "auto")):
            tally["blocked"] += 1
            continue
        if relevance_mod.skip_reason(p):
            tally["skipped"] += 1
            continue
        rel = relevance_mod.score(session, p, None)
        if rel < rel_min:
            tally["below_threshold"] += 1
            continue
        prev = best.get(handle)
        if prev is None:
            best[handle] = (rel, p)
        else:
            tally["duplicate_author"] += 1
            if rel > prev[0]:
                best[handle] = (rel, p)

    ranked = sorted(best.values(), key=lambda x: x[0], reverse=True)
    return ranked[:per_run], tally


def _schedule_send(session: Session, draft, target_x_id: str, rel: float,
                   slot: int) -> datetime:
    """Queue a send `slot` spacing-steps out instead of firing it now.

    The old loop called submit_write inside the for-loop, so the governor's
    9-minute spacing refused reply 2 onward and every one of them fell back to
    the review queue: a batch of ten sent one. Staggering them here is what
    makes a batch actually a batch.
    """
    spacing = int(get_setting(session, "min_write_spacing_s", MIN_WRITE_SPACING_S))
    delay = slot * spacing + governor.jitter_seconds(spacing // 3)
    send_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, delay))
    # The batch spans longer than the default 1h authorization TTL, so the last
    # send would find its authorization expired. Cover the whole batch.
    ttl = int(spacing * (slot + 2) + 3600)
    authz = issue(session, draft.id, issuer="policy", mode="foryou",
                  reasons=["for-you auto reply", f"relevance {rel}"], ttl_s=ttl)
    pipeline._stash_pending(session, draft.id, authz.id, target_x_id, send_at)
    return send_at


def run(session: Session, per_run: int | None = None, mode: str | None = None) -> dict:
    """One For You sweep: read the feed, pick up to `per_run` unique authors
    above the relevance floor, draft each, and either send the confident ones on
    a spaced schedule or bin them."""
    cfg = config(session)
    per_run = per_run if per_run is not None else int(cfg[K_PER_RUN])
    mode = mode or cfg[K_MODE]
    rel_min = float(get_setting(session, K_RELEVANCE_MIN, FORYOU_RELEVANCE_MIN))
    cooldown_h = int(get_setting(session, K_COOLDOWN_H, FORYOU_AUTHOR_COOLDOWN_H))
    auto_min = int(get_setting(session, "foryou_auto_min", FORYOU_AUTO_MIN))

    out = {"scanned": 0, "picked": 0, "queued": 0, "sent": 0, "skipped": 0,
           "discarded": 0, "mode": mode, "replies": [], "why_skipped": {}}

    if governor.read_budget_left(session) <= 0:
        log.info("for-you run skipped: read budget exhausted")
        out["skipped"] = 1
        out["why_skipped"] = {"read_budget": 1}
        return out

    bus = get_bus()
    live_state.record(session, "watching", "reading your For You feed", target="For You")
    posts = bus.submit_read("presence", "home") or []
    governor.record_read(session, 1)
    out["scanned"] = len(posts)

    batch, tally = _pick_batch(session, posts, mode, per_run, rel_min, cooldown_h)
    out["why_skipped"] = tally
    slot = 0

    for rel, p in batch:
        out["picked"] += 1
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
        chosen = result.candidates[result.chosen_index]
        draft = Draft(kind="reply", parent_post_id=post_row.id, final_text=result.final_text,
                      relevance=rel, mode_at_creation="foryou",
                      candidates_json=json.dumps([_cd(c) for c in result.candidates]),
                      critic_json=json.dumps([c.critic for c in result.candidates]),
                      chosen_index=result.chosen_index or 0, status="queued")
        session.add(draft)
        session.commit()
        session.refresh(draft)

        if mode != "auto":
            out["queued"] += 1
            out["replies"].append({"author": p.author_handle, "text": draft.final_text,
                                   "status": "queued", "confidence": _axis_sum(chosen.critic)})
            live_state.record(session, "queued", "waiting for you", target=p.author_handle,
                              post_x_id=p.x_post_id, draft_id=draft.id)
            continue

        # Confidence gate. Below the bar is binned, not queued: the operator
        # asked for a hands-off system, and a queue nobody reads is a worse
        # outcome than a reply that was never written.
        confident, why = _confident(session, draft.final_text, chosen.critic, auto_min)
        if not confident:
            draft.status = "dismissed"
            session.add(draft)
            session.commit()
            out["discarded"] += 1
            live_state.record(session, "discarded", f"under the bar: {why}",
                              target=p.author_handle, post_x_id=p.x_post_id,
                              draft_id=draft.id)
            continue

        try:
            governor.check_write_allowed(session, "reply", "foryou")
        except governor.GovernorRefusal as e:
            # A spacing refusal is expected mid-batch; a cap or kill-switch
            # refusal means stop trying for this sweep.
            draft.status = "queued"
            session.add(draft)
            session.commit()
            out["queued"] += 1
            log.info("for-you send held: %s", e.reason)
            live_state.record(session, "queued", f"held: {e.reason}", target=p.author_handle,
                              post_x_id=p.x_post_id, draft_id=draft.id)
            if "spacing" not in e.reason:
                break
            continue

        send_at = _schedule_send(session, draft, p.x_post_id, rel, slot)
        slot += 1
        draft.status = "approved"
        session.add(draft)
        session.commit()
        out["sent"] += 1
        out["replies"].append({"author": p.author_handle, "text": draft.final_text,
                               "status": "scheduled", "at": send_at.isoformat(),
                               "confidence": _axis_sum(chosen.critic)})
        live_state.record(session, "sending",
                          f"queued to send to @{p.author_handle} at "
                          f"{send_at.strftime('%H:%M')}",
                          target=p.author_handle, post_x_id=p.x_post_id, draft_id=draft.id)

    # Include why posts were dropped: "picked 0 of 12" is not actionable on
    # its own, and this is the first question anyone asks.
    log.info("for-you run: %s | skipped: %s",
             {k: out[k] for k in ("scanned", "picked", "queued", "sent", "discarded")},
             {k: v for k, v in (out.get("why_skipped") or {}).items() if v})
    return out


def _axis_sum(critic: dict) -> int:
    return sum(int((critic or {}).get(a, 0)) for a in AXES)


def _confident(session: Session, text: str, critic: dict, auto_min: int) -> tuple[bool, str]:
    """The bar for sending with nobody watching."""
    if unsafe_to_send(text, session):
        return False, "unsafe content"
    if not critic:
        return False, "no critic score"
    if critic.get("followed_injected_instructions"):
        return False, "followed injected instructions"
    low = min(int(critic.get(a, 0)) for a in AXES)
    if low < CRITIC_MIN_AUTO:
        return False, f"critic axis {low} < {CRITIC_MIN_AUTO}"
    total = _axis_sum(critic)
    if total < auto_min:
        return False, f"confidence {total} < {auto_min}"
    # O-14: with nobody reviewing, an invented war story is a claim made in the
    # operator's name. Only allow first-person history the corpus can back.
    from ..persona.corpus import operator_vocabulary
    from ..persona.guards import fabricated_experience
    made_up = fabricated_experience(text, operator_vocabulary(session))
    if made_up:
        return False, made_up
    return True, ""


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
