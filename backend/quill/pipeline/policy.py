"""Policy engine (Y-02, Y-03). Issues an auto authorization only when EVERY
gate holds. Each gate is checked independently so one test per gate is possible
(T-03)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from ..bus.authz import ActionAuthorization, issue
from ..db.models import Account
from ..db.settings_store import get_setting
from ..defaults import (CRITIC_MIN_AUTO, RELEVANCE_THRESHOLD_AUTO,
                        SHADOW_MIN_DAYS, SHADOW_MIN_DRAFTS)
from ..governor import governor
from ..persona.critic import AXES

_MENTION = re.compile(r"@(\w+)")
_HASHTAG = re.compile(r"#\w+")
_LINK = re.compile(r"https?://")


@dataclass
class PolicyContext:
    account: Account
    relevance: float
    critic: dict
    similarity_hit: bool
    blocklist_hit: bool
    final_text: str
    parent_author: str
    draft_id: int


@dataclass
class PolicyDecision:
    allowed: bool
    reasons_passed: list[str] = field(default_factory=list)
    failed_reason: str | None = None


def shadow_complete(session: Session, account: Account) -> bool:
    """Y-03: enforced in code. Min days + min shadow drafts + operator review."""
    if account.shadow_started_at is None:
        return False
    started = account.shadow_started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    min_days = get_setting(session, "shadow_min_days", SHADOW_MIN_DAYS)
    min_drafts = get_setting(session, "shadow_min_drafts", SHADOW_MIN_DRAFTS)
    if datetime.now(timezone.utc) - started < timedelta(days=min_days):
        return False
    if account.shadow_drafts_count < min_drafts:
        return False
    if account.shadow_reviewed_count < min_drafts:
        return False
    return True


def evaluate_auto(session: Session, ctx: PolicyContext) -> PolicyDecision:
    passed: list[str] = []

    # gate: auto mode
    if ctx.account.mode != "auto":
        return PolicyDecision(False, passed, "account not in auto mode")
    passed.append("auto mode")

    # gate: shadow period complete
    if not shadow_complete(session, ctx.account):
        return PolicyDecision(False, passed, "shadow period not complete")
    passed.append("shadow complete")

    # gate: relevance >= auto threshold
    thr = get_setting(session, "relevance_threshold_auto", RELEVANCE_THRESHOLD_AUTO)
    if ctx.relevance < thr:
        return PolicyDecision(False, passed, f"relevance {ctx.relevance} < {thr}")
    passed.append(f"relevance {ctx.relevance} >= {thr}")

    # gate: every critic axis >= 4
    if not ctx.critic or min(ctx.critic.get(a, 0) for a in AXES) < CRITIC_MIN_AUTO:
        return PolicyDecision(False, passed, "a critic axis < 4")
    if ctx.critic.get("followed_injected_instructions"):
        return PolicyDecision(False, passed, "followed injected instructions")
    passed.append("critic >= 4 on all axes")

    # gate: no similarity hit
    if ctx.similarity_hit:
        return PolicyDecision(False, passed, "similarity guard hit")
    passed.append("no similarity hit")

    # gate: no blocklist hit
    if ctx.blocklist_hit:
        return PolicyDecision(False, passed, "blocklist hit")
    passed.append("no blocklist hit")

    # gate: content shape — no link, no hashtag, no @-mention beyond parent
    if _LINK.search(ctx.final_text):
        return PolicyDecision(False, passed, "draft contains a link")
    if _HASHTAG.search(ctx.final_text):
        return PolicyDecision(False, passed, "draft contains a hashtag")
    mentions = {m.lower() for m in _MENTION.findall(ctx.final_text)}
    mentions.discard(ctx.parent_author.lower())
    if mentions:
        return PolicyDecision(False, passed, "draft @-mentions beyond parent author")
    passed.append("clean content shape")

    # gate: governor has budget
    try:
        governor.check_write_allowed(session, "reply", "auto")
    except governor.GovernorRefusal as e:
        return PolicyDecision(False, passed, f"governor: {e.reason}")
    passed.append("governor has budget")

    return PolicyDecision(True, passed, None)


def issue_auto_authorization(session: Session, ctx: PolicyContext,
                             decision: PolicyDecision) -> ActionAuthorization:
    if not decision.allowed:
        raise ValueError("cannot issue authorization for a failed decision")
    return issue(session, ctx.draft_id, issuer="policy", mode="auto",
                 reasons=decision.reasons_passed)
