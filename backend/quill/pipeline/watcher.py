"""Watcher (§8). Polls accounts on a per-tier interval with jitter, parses
posts, dedupes by high-water mark, feeds the pipeline, respects read budget."""
from __future__ import annotations

import random
from datetime import datetime, timezone

from sqlmodel import Session, select

from ..bus.action_bus import get_bus
from ..db.models import Account
from ..defaults import POLL_INTERVAL_TIER, POLL_JITTER_FRAC
from ..governor import governor
from ..logging_setup import get_logger
from . import pipeline

log = get_logger("quill.watcher")


def poll_interval(account: Account) -> int:
    base = account.poll_interval_s or POLL_INTERVAL_TIER.get(account.tier, 1500)
    return int(base * (1 + random.uniform(-POLL_JITTER_FRAC, POLL_JITTER_FRAC)))


def watch_once(session: Session, account: Account) -> list[pipeline.Outcome]:
    if governor.read_budget_left(session) <= 0:      # I-06
        log.info("read budget exhausted; skipping @%s", account.handle)
        return []
    bus = get_bus()
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


def watch_all(session: Session) -> dict:
    accounts = session.exec(
        select(Account).where(Account.active == True)).all()  # noqa: E712
    random.shuffle(accounts)                                   # randomised order (I-01)
    summary = {"polled": 0, "queued": 0, "shadow": 0, "discarded": 0, "silent": 0}
    for acc in accounts:
        for oc in watch_once(session, acc):
            summary["polled"] += 1
            summary[oc.status] = summary.get(oc.status, 0) + 1
    return summary
