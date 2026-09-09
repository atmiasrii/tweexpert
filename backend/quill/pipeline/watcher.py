"""Watcher (§8). Polls accounts on a per-tier interval with jitter, parses
posts, dedupes by high-water mark, feeds the pipeline, respects read budget."""
from __future__ import annotations

import random
from datetime import datetime, timezone

from sqlmodel import Session, select

from ..browser import AccountGone, SelectorMiss
from ..bus.action_bus import get_bus
from ..config import get_settings
from ..notify import notifier
from ..db.models import Account
from ..db.settings_store import get_setting
from ..defaults import (DEEP_READS_PER_SWEEP, POLL_INTERVAL_TIER,
                        POLL_JITTER_FRAC)
from ..governor import governor
from ..logging_setup import get_logger
from . import live_state, pipeline

log = get_logger("quill.watcher")

# How many posts the 90-second timeline sweep collects. Enough to cover a busy
# minute and a half on the watchlist, shallow enough not to monopolise the one
# browser that sends also queue behind.
HOME_SWEEP_POSTS = 10


def poll_interval(account: Account) -> int:
    base = account.poll_interval_s or POLL_INTERVAL_TIER.get(account.tier, 1500)
    return int(base * (1 + random.uniform(-POLL_JITTER_FRAC, POLL_JITTER_FRAC)))


def watch_once(session: Session, account: Account) -> list[pipeline.Outcome]:
    if governor.read_budget_left(session) <= 0:      # I-06
        log.info("read budget exhausted; skipping @%s", account.handle)
        return []
    bus = get_bus()
    from ..ops import trace
    run_id = trace.start_run(session, "profile", f"@{account.handle}")
    live_state.record(session, "watching", f"reading @{account.handle}",
                      target=account.handle)
    try:
        posts = bus.submit_read("read_user", account.handle,
                                {"since_id": account.high_water_post_id})
    except Exception as e:
        trace.finish_run(session, run_id, error=str(e))
        raise
    governor.record_read(session, 1)
    for p in posts:
        trace.seen(session, p, source=f"@{account.handle}")
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
    trace.finish_run(session, run_id, new_posts=len(outcomes))
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
    # Shallow on purpose. This runs every 90 seconds and new posts arrive at
    # the top, so the first screen is all it can possibly need. Collecting
    # thirty posts with full scrolling instead cost ~28 seconds of the one
    # browser that sends also queue behind, forty times an hour.
    from ..ops import trace
    run_id = trace.start_run(session, "watch", "timeline")
    try:
        posts = bus.submit_read("presence", "home",
                                {"target": HOME_SWEEP_POSTS}) or []
    except Exception as e:
        trace.finish_run(session, run_id, error=str(e))
        raise
    governor.record_read(session, 1)
    for p in posts:
        trace.seen(session, p, source="timeline")

    op = get_settings().operator_handle.lower()
    watched = {a.handle.lower(): a for a in session.exec(
        select(Account).where(Account.active == True)).all()}  # noqa: E712

    summary = {"source": "home", "seen": len(posts), "polled": 0,
               "queued": 0, "shadow": 0, "discarded": 0, "silent": 0,
               "auto_scheduled": 0}
    # Oldest first, so the high-water mark advances monotonically.
    for post in reversed(posts):
        handle = (post.author_handle or "").lower()
        if handle == op:
            trace.note(session, post.x_post_id, "skipped", "own post")
            continue
        if handle not in watched:
            trace.note(session, post.x_post_id, "skipped", "author not on the watchlist")
            continue
        acc = watched[handle]
        if acc.high_water_post_id and post.x_post_id <= acc.high_water_post_id:
            trace.note(session, post.x_post_id, "skipped", "already seen")
            continue                                   # already seen (I-03)
        if post.kind == "retweet" and not post.text:
            trace.note(session, post.x_post_id, "skipped", "bare retweet")
            continue
        oc = pipeline.process_post(session, post, acc)
        summary["polled"] += 1
        summary[oc.status] = summary.get(oc.status, 0) + 1
        acc.high_water_post_id = post.x_post_id
        session.add(acc)
        session.commit()
    trace.finish_run(session, run_id, **{k: v for k, v in summary.items() if k != "source"})
    return summary


def watch_all(session: Session, deep_tiers: tuple[str, ...] = ("A", "B", "C")) -> dict:
    """The home sweep, plus a direct read of the highest-tier profiles.

    The direct reads are a backstop: the algorithm does not put everything a
    followed account posts on the timeline, and tier A is where missing a post
    costs the most. They are budgeted, so they stop before the sweep does.
    """
    # Quiet hours quiet the reads too. The governor already refuses writes at
    # night, but this sweep kept scrolling the timeline every 90 seconds until
    # morning: a read budget spent on posts nothing could answer, and a
    # browser scrolling at 2am is not what a person does.
    if governor.in_quiet_hours(session):
        return {"skipped": "quiet hours"}

    # The home read is one selector lookup against a client-rendered timeline,
    # so it can miss on a slow render. It used to take the whole sweep down
    # with it, deep reads included, which is a lot to lose to one bad page.
    try:
        summary = sweep_home(session)
    except SelectorMiss as e:
        log.warning("home sweep missed (%s); going straight to the deep reads", e)
        summary = {"polled": 0, "queued": 0, "discarded": 0, "home_failed": 1}
    if summary.get("skipped"):
        return summary

    accounts = [a for a in session.exec(
        select(Account).where(Account.active == True)).all()  # noqa: E712
        if a.tier in deep_tiers]
    random.shuffle(accounts)                                   # randomised order (I-01)
    budget = int(get_setting(session, "deep_reads_per_sweep", DEEP_READS_PER_SWEEP))
    for acc in accounts[:budget]:
        # One unreadable profile used to end the whole sweep, so the accounts
        # after it in the shuffle were never read and the summary was lost.
        # A dead handle and a render miss are both per-account problems.
        try:
            for oc in watch_once(session, acc):
                summary["polled"] += 1
                summary[oc.status] = summary.get(oc.status, 0) + 1
        except AccountGone as e:
            log.warning("@%s has no timeline (%s); deactivating", acc.handle, e.reason)
            acc.active = False
            session.add(acc)
            session.commit()
            summary["deactivated"] = summary.get("deactivated", 0) + 1
            notifier.alert("account_gone",
                           f"@{acc.handle} is no longer readable ({e.reason}); "
                           "removed from the watchlist")
        except SelectorMiss as e:
            log.warning("deep read of @%s missed (%s); continuing", acc.handle, e)
            summary["read_failed"] = summary.get("read_failed", 0) + 1
    return summary
