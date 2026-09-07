"""Rate budgets, split by where the number comes from.

Two different things get conflated when people talk about X's limits:

**Platform caps** are what the service refuses outright. Since May 2026 a free
account gets 50 posts and 200 replies a day; X Premium removes the posting
limits. These are facts about the account.

**Behavioural budget** is what we choose to do inside that. It exists because
volume and pattern, not entitlement, are what trip spam and deboost heuristics.
Premium raises the platform ceiling; it does not make X's heuristics friendlier,
and no subscription makes a templated reply look human.

So the tier sets the ceiling, and the operator sets the budget under it.
"""
from __future__ import annotations

from sqlmodel import Session

from ..config import get_settings
from ..db.settings_store import get_setting, set_setting

# What the platform itself allows. None means no cap.
PLATFORM_CAPS = {
    "free": {"replies": 200, "posts": 50},
    "premium": {"replies": None, "posts": None},
}

# What Quill will actually do. The free row is the researched safe band; the
# premium row is the operator's choice with the platform ceiling lifted, and it
# is deliberately above the ~50/day figure the research treats as the point
# where deboost heuristics start reacting.
TIER_BUDGET = {
    "free": {
        "cap_replies_total": 49,
        "cap_posts": 6,
        "min_write_spacing_s": 9 * 60,
        "burst_max_writes": 3,
        "daily_read_budget": 2500,
        "foryou_interval_min": 90,
    },
    "premium": {
        "cap_replies_total": 120,
        "cap_posts": 20,
        # 120 replies at 5-minute spacing occupies about 10 hours, which fits a
        # waking day without bunching.
        "min_write_spacing_s": 5 * 60,
        "burst_max_writes": 4,
        "daily_read_budget": 5000,
        # More batches per day, since the ceiling is no longer the binding
        # constraint. In practice the confidence bar is.
        "foryou_interval_min": 45,
    },
}

_APPLIED_KEY = "_applied_account_tier"


def account_tier(session: Session | None = None) -> str:
    """Settings win over .env, so the tier can be changed without a restart."""
    tier = None
    if session is not None:
        tier = get_setting(session, "account_tier", None)
    tier = (tier or get_settings().account_tier or "free").lower()
    return tier if tier in TIER_BUDGET else "free"


def budget(session: Session, key: str):
    """The effective value: an explicit setting, else this tier's default."""
    tier_default = TIER_BUDGET[account_tier(session)][key]
    return get_setting(session, key, tier_default)


def platform_cap(session: Session, kind: str) -> int | None:
    return PLATFORM_CAPS[account_tier(session)][kind]


def apply_tier_defaults(session: Session) -> str | None:
    """Write this tier's budget into the settings table when the tier changes.

    Without this, switching to premium would do nothing: the settings table
    already holds the free-tier numbers from the last run, and an explicit
    setting always beats a default. Returns the new tier when it changed.
    """
    tier = account_tier(session)
    if get_setting(session, _APPLIED_KEY, None) == tier:
        return None
    for key, value in TIER_BUDGET[tier].items():
        set_setting(session, key, value)
    set_setting(session, _APPLIED_KEY, tier)
    return tier
