"""Relevance scoring 0-100 (R-01).

Weights follow the reply research rather than intuition. The measured facts
they rest on: a host post's impressions peak ~72 seconds after it goes up and
have a median half-life of ~80 minutes, so a reply is riding a curve that is
mostly over within the hour. Replies land in the first few slots or they are
not seen at all, and on a saturated thread nobody reads past the top handful.

  topical match to what I actually know   0.30
  post is young (under ~15 min)           0.20
  the account is worth replying to        0.15   (tier stands in for the
                                                  5-20x follower band until
                                                  follower counts are scraped)
  this author answers repliers            0.10
  the post is contestable / answerable    0.20
  the thread is not saturated yet         0.05

"Do I have something specific to add" is the research's hard gate. It is not a
weight here because it cannot be known before drafting; `guards.generic_reply`
enforces it after the draft exists, which is the same gate applied later.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlmodel import Session, select

from ..browser.base import ParsedPost
from ..db.models import Account, Person
from ..persona.voicecard import load_voice_card

TIER_WEIGHT = {"A": 1.0, "B": 0.75, "C": 0.5}
_QUESTION = re.compile(r"\?\s*$|\bhow\b|\bwhy\b|\bwhat\b|\bwhich\b", re.I)
_CONTESTABLE = re.compile(r"\b(always|never|everyone|no one|the best|the worst|"
                          r"is just|nothing but|only way)\b", re.I)

FRESH_FULL_MIN = 15      # full credit inside the first quarter hour
FRESH_DEAD_MIN = 60      # no freshness credit past the hour
SKIP_AFTER_MIN = 90      # do not draft at all past this
SKIP_REPLIES = 200       # saturated thread, the slot is not visible


def score(session: Session, post: ParsedPost, account: Account | None) -> float:
    card = load_voice_card(session)
    owned = [t.lower() for t in card.get("topics_owned", [])]

    tier = account.tier if account else "C"
    tier_w = TIER_WEIGHT.get(tier, 0.5)

    # Topical match saturates fast on purpose. One clear hit on a topic the
    # operator owns is already enough to have something to say; dividing by the
    # length of the topic list punished posts for being about only one thing.
    text = post.text.lower()
    hits = sum(1 for topic in owned
               if any(word in text for word in topic.split() if len(word) > 3))
    topical = 0.0 if hits == 0 else 0.7 if hits == 1 else 1.0

    answerable = 1.0 if (_QUESTION.search(post.text) or _CONTESTABLE.search(post.text)) else 0.3

    # Freshness. Full credit inside the first 15 minutes, then a fast decay to
    # zero by the hour, because that is roughly where the host post's own
    # attention curve ends.
    age_min = _age_minutes(post)
    if age_min <= FRESH_FULL_MIN:
        fresh = 1.0
    elif age_min >= FRESH_DEAD_MIN:
        fresh = 0.0
    else:
        fresh = 1.0 - (age_min - FRESH_FULL_MIN) / (FRESH_DEAD_MIN - FRESH_FULL_MIN)

    # Thread saturation: past a few hundred replies the slot is worthless.
    sat = 1.0 if post.replies <= 25 else max(0.0, 1.0 - (post.replies - 25) / 175.0)

    # Does this author actually answer people? That is the 75-point event.
    prior = 0.0
    person = session.get(Person, post.author_handle)
    if person and person.engagements:
        prior = min(person.engagements / 10.0, 1.0)

    raw = (0.30 * topical + 0.20 * fresh + 0.15 * tier_w +
           0.20 * answerable + 0.10 * prior + 0.05 * sat)
    return round(raw * 100, 1)


def skip_reason(post: ParsedPost) -> str:
    """Hard gates from the research. Cheap, and they run before any drafting so
    a dead post never costs a model call."""
    from ..persona.guards import too_thin
    thin = too_thin(post.text)
    if thin:
        return thin
    if _age_minutes(post) > SKIP_AFTER_MIN:
        return f"post is {int(_age_minutes(post))} min old, the window has closed"
    if post.replies > SKIP_REPLIES:
        return f"thread already has {post.replies} replies, nobody reads that far"
    return ""


def _age_minutes(post: ParsedPost) -> float:
    if not post.created_at:
        return 60.0
    ca = post.created_at
    if ca.tzinfo is None:
        ca = ca.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - ca).total_seconds() / 60.0, 0.1)
