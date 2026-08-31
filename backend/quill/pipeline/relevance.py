"""Relevance scoring 0-100 (R-01)."""
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


def score(session: Session, post: ParsedPost, account: Account | None) -> float:
    card = load_voice_card(session)
    owned = [t.lower() for t in card.get("topics_owned", [])]

    tier = account.tier if account else "C"
    tier_w = TIER_WEIGHT.get(tier, 0.5)

    text = post.text.lower()
    topical = 0.0
    for topic in owned:
        for word in topic.split():
            if word in text:
                topical += 1
    topical = min(topical / max(len(owned), 1), 1.0)

    answerable = 1.0 if (_QUESTION.search(post.text) or _CONTESTABLE.search(post.text)) else 0.3

    # freshness component
    age_min = _age_minutes(post)
    fresh = max(0.0, 1.0 - age_min / 180.0)

    # engagement velocity (likes per minute, capped)
    vel = min((post.likes / max(age_min, 1)) / 20.0, 1.0)

    # prior engagement with author
    prior = 0.0
    person = session.get(Person, post.author_handle)
    if person and person.engagements:
        prior = min(person.engagements / 10.0, 1.0)

    raw = (0.28 * tier_w + 0.30 * topical + 0.18 * answerable +
           0.12 * fresh + 0.07 * vel + 0.05 * prior)
    return round(raw * 100, 1)


def _age_minutes(post: ParsedPost) -> float:
    if not post.created_at:
        return 60.0
    ca = post.created_at
    if ca.tzinfo is None:
        ca = ca.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - ca).total_seconds() / 60.0, 0.1)
