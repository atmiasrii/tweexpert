"""A post gathering likes fast outranks one that merely has likes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from quill.browser.base import ParsedPost
from quill.pipeline import relevance


def _post(likes: int, age_min: float, text="how do you handle structured output from small models?"):
    return ParsedPost(x_post_id="1", author_handle="someone", text=text,
                      created_at=datetime.now(timezone.utc) - timedelta(minutes=age_min),
                      likes=likes)


def test_fast_and_new_beats_the_same_likes_hours_later(session):
    hot = relevance.score(session, _post(likes=30, age_min=10), None)
    cold = relevance.score(session, _post(likes=30, age_min=360), None)
    assert hot > cold


def test_momentum_is_a_rate_not_a_count(session):
    # 6 likes in 2 minutes is a faster post than 60 likes in 60 minutes.
    assert relevance._momentum(_post(6, 2), 2) > relevance._momentum(_post(60, 60), 60)


def test_momentum_saturates_and_never_exceeds_one(session):
    assert relevance._momentum(_post(10_000, 5), 5) == 1.0
    assert relevance._momentum(_post(0, 5), 5) == 0.0


def test_a_brand_new_post_is_not_punished_for_having_no_likes_yet(session):
    """Freshness still carries it; momentum only adds, never subtracts."""
    new = relevance.score(session, _post(likes=0, age_min=1), None)
    old = relevance.score(session, _post(likes=0, age_min=240), None)
    assert new > old
