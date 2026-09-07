"""Watcher (§8). Polls accounts on a per-tier interval with jitter, parses
posts, dedupes by high-water mark, feeds the pipeline, respects read budget."""
from __future__ import annotations

import random
from datetime import datetime, timezone

from sqlmodel import Session, select

from ..bus.action_bus import get_bus
from ..config import get_settings
from ..db.models import Account
from ..db.settings_store import get_setting
from ..defaults import (DEEP_READS_PER_SWEEP, POLL_INTERVAL_TIER,
                        POLL_JITTER_FRAC)
from ..governor import governor
from ..logging_setup import get_logger
from . import live_state, pipeline

log = get_logger("quill.watcher")


def poll_interval(account: Account) -> int:
    base = account.poll_interval_s or POLL_INTERVAL_TIER.get(account.tier, 1500)
    return int(base * (1 + random.uniform(-POLL_JITTER_FRAC, POLL_JITTER_FRAC)))


def watch_once(session: Session, account: Account) -> list[pipeline.Outcome]:
    if governor.read_budget_left(session) <= 0:      # I-06
        log.info("read budget exhausted; skipping @%s", account.handle)
        return []
    bus = get_bus()
    live_state.record(session, "watching", f"reading @{account.handle}",
                      target=account.handle)
    posts = bus.submit_read("read_user", account.handle,
                            {"since_id": account.high_water_post_id})
    governor.record_read(session, 1)
    outcomes: list[pipeline.Outcome] = []
    newest = account.high_water_post_id
    for i, post in enumerate(posts):
        if i == 0:
            newest = post.x_post_id                   # advance high-water (I-03)
        if post.kind == "retweet" and not post.text:
            continue                                  # ignore bare retweets
        from ..config import get_settings
        if post.author_handle == get_settings().operator_handle:
            continue                                  # ignore the operator's own posts
        outcomes.append(pipeline.process_post(session, post, account))
    if newest:
        account.high_water_post_id = newest
        session.add(account)
        session.commit()
    return outcomes


def watch_foryou(session: Session, limit: int = 15) -> dict:
    """Read the For-You / home feed and draft replies to those posts too, not
    just the watchlist. These come in as assisted (no account = draft-only)."""
    if governor.read_budget_left(session) <= 0:
        return {"skipped": "read budget"}
    bus = get_bus()
    live_state.record(session, "watching", "reading your For You feed", target="For You")
    posts = bus.submit_read("presence", "home") or []
    governor.record_read(session, 1)
    from ..config import get_settings
    op = get_settings().operator_handle
    summary = {"source": "foryou", "polled": 0, "queued": 0, "shadow": 0,
               "discarded": 0, "silent": 0, "auto_scheduled": 0}
    for post in posts[:limit]:
        if post.author_handle == op:
            continue
        # If the author is a watched account, honour that account's mode.
        acc = session.exec(select(Account).where(
            Account.handle == post.author_handle)).first()
        oc = pipeline.process_post(session, post, acc)
        summary["polled"] += 1
        summary[oc.status] = summary.get(oc.status, 0) + 1
    return summary


def sweep_home(session: Session) -> dict:
    """One read of the home timeline, routed to every watched author in it.

    This replaces polling each account separately. Twenty accounts at one read
    each every three minutes is 400 reads an hour, which is what kept emptying
    the daily budget by lunchtime. The home timeline already contains posts from
    everyone the operator follows, so a single read covers the whole watchlist
    and detection is as fast as the sweep interval.
    """
    if governor.read_budget_left(session) <= 0:
        return {"skipped": "read budget"}
    bus = get_bus()
    live_state.record(session, "watching", "checking your timeline for new posts",
                      target="timeline")
    posts = bus.submit_read("presence", "home") or []
    governor.record_read(session, 1)

    op = get_settings().operator_handle.lower()
    watched = {a.handle.lower(): a for a in session.exec(
        select(Account).where(Account.active == True)).all()}  # noqa: E712

    summary = {"source": "home", "seen": len(posts), "polled": 0,
               "queued": 0, "shadow": 0, "discarded": 0, "silent": 0,
               "auto_scheduled": 0}
    # Oldest first, so the high-water mark advances monotonically.
    for post in reversed(posts):
        handle = (post.author_handle or "").lower()
        if handle == op or handle not in watched:
            continue
        acc = watched[handle]
        if acc.high_water_post_id and post.x_post_id <= acc.high_water_post_id:
            continue                                   # already seen (I-03)
        if post.kind == "retweet" and not post.text:
            continue
        oc = pipeline.process_post(session, post, acc)
        summary["polled"] += 1
        summary[oc.status] = summary.get(oc.status, 0) + 1
        acc.high_water_post_id = post.x_post_id
        session.add(acc)
        session.commit()
    return summary


def watch_all(session: Session, deep_tiers: tuple[str, ...] = ("A",)) -> dict:
    """The home sweep, plus a direct read of the highest-tier profiles.

    The direct reads are a backstop: the algorithm does not put everything a
    followed account posts on the timeline, and tier A is where missing a post
    costs the most. They are budgeted, so they stop before the sweep does.
    """
    summary = sweep_home(session)
    if summary.get("skipped"):
        return summary

    accounts = [a for a in session.exec(
        select(Account).where(Account.active == True)).all()  # noqa: E712
        if a.tier in deep_tiers]
    random.shuffle(accounts)                                   # randomised order (I-01)
    budget = int(get_setting(session, "deep_reads_per_sweep", DEEP_READS_PER_SWEEP))
    for acc in accounts[:budget]:
        for oc in watch_once(session, acc):
            summary["polled"] += 1
            summary[oc.status] = summary.get(oc.status, 0) + 1
    return summary
