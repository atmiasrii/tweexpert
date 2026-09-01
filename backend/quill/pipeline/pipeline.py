"""Reply pipeline (§10). post detected -> gates -> relevance -> context ->
persona -> policy -> shadow | assisted | auto."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..browser.base import ParsedPost
from ..bus.action_bus import get_bus
from ..bus.authz import issue
from ..db.models import Account, Draft, Person, Post
from ..db.settings_store import get_setting
from ..defaults import (DRAFT_TTL_S, FRESHNESS_WINDOW_AUTO_S, FRESHNESS_WINDOW_S,
                        PER_ACCOUNT_DAILY_DRAFT_CAP, QUEUE_CAP,
                        RELEVANCE_THRESHOLD, RELEVANCE_THRESHOLD_AUTO)
from ..governor import governor
from ..logging_setup import get_logger
from ..notify import notifier
from ..persona import engine as persona
from . import relevance as relevance_mod
from .blocklist import block_reason, unsafe_to_send
from .policy import PolicyContext, evaluate_auto, issue_auto_authorization
from ..persona.similarity import similarity_hit

log = get_logger("quill.pipeline")


@dataclass
class Outcome:
    status: str        # discarded|silent|shadow|queued|auto_scheduled|auto_sent
    reason: str = ""
    draft_id: int | None = None
    send_at: datetime | None = None


def upsert_post(session: Session, post: ParsedPost) -> Post:
    row = session.exec(select(Post).where(Post.x_post_id == post.x_post_id)).first()
    if row:
        return row
    row = Post(x_post_id=post.x_post_id, author_handle=post.author_handle,
               text=post.text, created_at=post.created_at, url=post.url,
               kind=post.kind, metrics_json=json.dumps(post.metrics()),
               media=post.media, lang=post.lang, parent_x_id=post.parent_x_id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _age_seconds(post: ParsedPost) -> float:
    if not post.created_at:
        return 0.0
    ca = post.created_at
    if ca.tzinfo is None:
        ca = ca.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ca).total_seconds()


def _already_replied(session: Session, post_row: Post) -> bool:
    # R-05: never reply twice in the same thread / to a post already replied
    existing = session.exec(
        select(Draft).where(Draft.parent_post_id == post_row.id,
                            Draft.status.in_(["sent", "approved"]))).first()
    return existing is not None


def _caps_ok(session: Session, account: Account | None) -> str | None:
    # queue cap (R-03)
    queued = session.exec(select(Draft).where(Draft.status == "queued")).all()
    if len(queued) >= get_setting(session, "queue_cap", QUEUE_CAP):
        return "queue cap reached"
    if account:
        today = datetime.now(timezone.utc) - timedelta(hours=24)
        per_acct = session.exec(select(Draft).where(
            Draft.account_id == account.id, Draft.created_at >= today)).all()
        cap = get_setting(session, "per_account_daily_draft_cap", PER_ACCOUNT_DAILY_DRAFT_CAP)
        if len(per_acct) >= cap:
            return f"per-account daily draft cap ({cap})"
    return None


def process_post(session: Session, post: ParsedPost,
                 account: Account | None) -> Outcome:
    """Public entry: runs the pipeline and records the terminal step for the
    live flowchart."""
    from . import live_state
    outcome = _process_post(session, post, account)
    live_state.record(session, outcome.status, outcome.reason,
                      target=post.author_handle, post_x_id=post.x_post_id,
                      draft_id=outcome.draft_id,
                      ok=outcome.status not in ("discarded",))
    return outcome


def _process_post(session: Session, post: ParsedPost,
                  account: Account | None) -> Outcome:
    from . import live_state
    mode = account.mode if account else "assisted"
    auto = mode == "auto"

    post_row = upsert_post(session, post)

    # --- gates (blocklist / language / media / age) --------------------
    br = block_reason(session, post, auto)
    if br:
        return Outcome("discarded", br)

    window = get_setting(session, "freshness_window_auto_s", FRESHNESS_WINDOW_AUTO_S) \
        if auto else get_setting(session, "freshness_window_s", FRESHNESS_WINDOW_S)
    if _age_seconds(post) > window:
        return Outcome("discarded", "freshness gate: too old")

    if _already_replied(session, post_row):
        return Outcome("discarded", "already replied in thread")

    # --- relevance -----------------------------------------------------
    rel = relevance_mod.score(session, post, account)
    threshold = get_setting(session, "relevance_threshold_auto", RELEVANCE_THRESHOLD_AUTO) \
        if auto else get_setting(session, "relevance_threshold", RELEVANCE_THRESHOLD)
    if rel < threshold:
        return Outcome("discarded", f"relevance {rel} < {threshold}")

    caps = _caps_ok(session, account)
    if caps:
        return Outcome("discarded", caps)

    # --- thread context (I-04): only now that it cleared relevance -----
    context = _fetch_context(post)

    # --- persona -------------------------------------------------------
    live_state.record(session, "drafting", f"writing a reply to @{post.author_handle}",
                      target=post.author_handle, post_x_id=post.x_post_id)
    result = persona.generate(session, _with_context(post.text, context),
                              account.handle if account else "", auto=auto)

    draft = Draft(
        kind="reply", parent_post_id=post_row.id,
        account_id=account.id if account else None,
        candidates_json=json.dumps([_cand_dict(c) for c in result.candidates]),
        critic_json=json.dumps([c.critic for c in result.candidates]),
        chosen_index=result.chosen_index if result.chosen_index is not None else 0,
        final_text=result.final_text or "",
        relevance=rel, mode_at_creation=mode,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=DRAFT_TTL_S),
    )

    if not result.has_output:
        draft.status = "no_angle"
        session.add(draft)
        session.commit()
        return Outcome("silent", "no good angle", draft.id)

    # --- policy branch -------------------------------------------------
    if mode == "shadow":
        return _do_shadow(session, draft, account)
    if mode == "assisted":
        return _do_assisted(session, draft, post, account)
    return _do_auto(session, draft, result, post, account, rel)


def _do_shadow(session, draft, account) -> Outcome:
    draft.status = "shadow"
    draft.would_have_sent_at = governor.next_available_slot(session)
    session.add(draft)
    if account:
        account.shadow_drafts_count += 1
        if account.shadow_started_at is None:
            account.shadow_started_at = datetime.now(timezone.utc)
        session.add(account)
    session.commit()
    return Outcome("shadow", "logged, nothing sent", draft.id,
                   draft.would_have_sent_at)


def _do_assisted(session, draft, post, account) -> Outcome:
    draft.status = "queued"
    session.add(draft)
    session.commit()
    notifier.draft_approval(draft.id, post.author_handle, draft.final_text)
    return Outcome("queued", "in assisted queue", draft.id)


def _do_auto(session, draft, result, post, account, rel) -> Outcome:
    chosen = result.candidates[result.chosen_index]
    hit, _ = similarity_hit(session, draft.final_text)
    unsafe = unsafe_to_send(draft.final_text, session)
    ctx = PolicyContext(
        account=account, relevance=rel, critic=chosen.critic,
        similarity_hit=hit or chosen.similarity_hit,
        blocklist_hit=bool(unsafe), final_text=draft.final_text,
        parent_author=post.author_handle, draft_id=0)
    session.add(draft)
    session.commit()
    session.refresh(draft)
    ctx.draft_id = draft.id

    decision = evaluate_auto(session, ctx)
    if not decision.allowed:
        # fall back to the queue (§10)
        draft.status = "queued"
        session.add(draft)
        session.commit()
        notifier.draft_approval(draft.id, post.author_handle, draft.final_text)
        return Outcome("queued", f"auto gate failed: {decision.failed_reason}", draft.id)

    authz = issue_auto_authorization(session, ctx, decision)
    send_at = datetime.now(timezone.utc) + timedelta(
        seconds=governor.jitter_seconds(governor.auto_delay_seconds()))
    draft.status = "approved"
    draft.would_have_sent_at = send_at
    session.add(draft)
    session.commit()
    # store the pending send; worker sends when due (kept in draft.would_have_sent_at)
    _stash_pending(session, draft.id, authz.id, post.x_post_id, send_at)
    return Outcome("auto_scheduled", "authorized by policy", draft.id, send_at)


# --- pending auto sends (worker drains these) --------------------------
def _stash_pending(session, draft_id, authz_id, target_x_id, send_at):
    from ..db.settings_store import get_setting, set_setting
    pend = get_setting(session, "_pending_auto", [])
    pend.append({"draft_id": draft_id, "authz_id": authz_id,
                 "target": target_x_id, "send_at": send_at.isoformat()})
    set_setting(session, "_pending_auto", pend)


def send_due_auto(session: Session) -> list[str]:
    """Send auto drafts whose delay has elapsed. Returns sent x_post_ids."""
    from ..bus.authz import ActionAuthorization
    from ..db.models import Authorization
    from ..db.settings_store import get_setting, set_setting
    pend = get_setting(session, "_pending_auto", [])
    now = datetime.now(timezone.utc)
    remaining, sent = [], []
    bus = get_bus()
    for item in pend:
        send_at = datetime.fromisoformat(item["send_at"])
        if send_at.tzinfo is None:
            send_at = send_at.replace(tzinfo=timezone.utc)
        if send_at > now:
            remaining.append(item)
            continue
        arow = session.get(Authorization, item["authz_id"])
        draft = session.get(Draft, item["draft_id"])
        if not arow or not draft or arow.consumed_at is not None:
            continue
        authz = ActionAuthorization(
            id=arow.id, draft_id=arow.draft_id, issuer=arow.issuer, mode=arow.mode,
            reasons=json.loads(arow.reasons_json), issued_at=arow.issued_at,
            expires_at=arow.expires_at)
        try:
            action = bus.submit_write("reply", item["target"], draft.final_text,
                                      authz, issuer="policy", draft_id=draft.id)
            sent.append(action.x_post_id)
            _post_send_push(session, draft, action.x_post_id)
        except Exception as e:
            log.warning("auto send failed: %s", e)
    set_setting(session, "_pending_auto", remaining)
    return sent


def _post_send_push(session, draft, x_post_id):
    # Y-05: after-the-fact push with one-tap delete
    from ..security import make_action_token
    from ..config import get_settings
    from ..defaults import NOTIFY_TOKEN_TTL_S
    s = get_settings()
    token = make_action_token(s.secret_key, draft.id, NOTIFY_TOKEN_TTL_S)
    url = f"{s.public_base_url}/api/notify/delete?x_post_id={x_post_id}&token={token}"
    notifier.notify("auto_sent", "Auto-reply sent", draft.final_text,
                    draft_id=draft.id,
                    actions=[{"label": "Delete", "url": url}])


# --- helpers -----------------------------------------------------------
def _fetch_context(post: ParsedPost) -> list[str]:
    from ..defaults import THREAD_CONTEXT_DEPTH
    try:
        bus = get_bus()
        parents = bus.submit_read("read_post", post.x_post_id,
                                  {"depth": THREAD_CONTEXT_DEPTH})
        return [p.text for p in (parents or []) if p.text and p.text != post.text]
    except Exception:
        return []


def _with_context(text: str, context: list[str]) -> str:
    if not context:
        return text
    ctx = "\n".join(f"- {c}" for c in context[:3])
    return f"{text}\n(thread context:\n{ctx})"


def _cand_dict(c) -> dict:
    return {"angle": c.angle, "text": c.text, "prefilter_ok": c.prefilter_ok,
            "prefilter_reason": c.prefilter_reason, "critic": c.critic,
            "similarity_hit": c.similarity_hit}
