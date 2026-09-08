"""Feed-collection loop, tested without a browser.

`feed_step` is the loop's pure decision; `_collect_feed` is driven here with
a scripted page so the scroll/settle/stop behaviour is covered end to end.
"""
from __future__ import annotations

from quill.browser.base import ParsedPost
from quill.browser.playwright_engine import PlaywrightEngine, feed_step


# -- pure decision ---------------------------------------------------------

def _run(added_per_round: list[int], target: int = 30, max_stale: int = 3):
    """Replay the loop's bookkeeping; return (rounds used, stop reason)."""
    stale, collected = 0, 0
    for rnd, added in enumerate(added_per_round, start=1):
        collected += added
        stale, reason = feed_step(stale, added, collected, target, max_stale)
        if reason:
            return rnd, reason
    return len(added_per_round), ""


def test_stops_after_three_consecutive_empty_scrolls():
    rounds, reason = _run([8, 5, 0, 0, 0, 4, 4])
    assert (rounds, reason) == (5, "exhausted")


def test_a_fresh_post_resets_the_stale_counter():
    # two empty scrolls, one that finds something, two more empty: not yet
    # exhausted, because the empties were never three in a row.
    rounds, reason = _run([8, 0, 0, 3, 0, 0])
    assert (rounds, reason) == (6, "")
    rounds, reason = _run([8, 0, 0, 3, 0, 0, 0])
    assert (rounds, reason) == (7, "exhausted")


def test_target_wins_over_exhaustion():
    rounds, reason = _run([12, 10, 8], target=30)
    assert (rounds, reason) == (3, "target")
    # reaching the target on a round that also happens to be stale-free
    # reports "target", never "exhausted".
    stale, reason = feed_step(2, 0, 30, 30, 3)
    assert reason == "target"


def test_defaults():
    assert PlaywrightEngine.FEED_TARGET == 30
    assert PlaywrightEngine.FEED_ROUNDS == 30
    assert PlaywrightEngine.FEED_STALE_ROUNDS == 3


# -- the loop itself, on a scripted page ------------------------------------

class _Loc:
    def __init__(self, ids):
        self.ids = list(ids)

    def count(self):
        return len(self.ids)

    def nth(self, i):
        return self.ids[i]


def _engine(pages: list[list[str]]):
    """A PlaywrightEngine whose page shows `pages[k]` after k scrolls."""
    eng = object.__new__(PlaywrightEngine)
    state = {"scrolls": 0, "settles": 0}

    def find_all(key, wait_ms=0):
        k = min(state["scrolls"], len(pages) - 1)
        return _Loc(pages[k]), "sel"

    def scroll(rounds=1):
        state["scrolls"] += rounds

    def settle(before, timeout_ms):
        state["settles"] += 1
        return before

    eng._find_all = find_all
    eng._feed_scroll = scroll
    eng._wait_for_articles = settle
    eng._article_id = lambda art: art
    eng._extract = lambda art, surface_handle="": ParsedPost(
        x_post_id=art, author_handle="a", text=art, url="")
    return eng, state


def test_collect_feed_keeps_scrolling_until_target():
    # each scroll reveals five more; 30 needs six pages.
    pages = [[str(n) for n in range(5 * (k + 1))] for k in range(10)]
    eng, state = _engine(pages)
    out = eng._collect_feed(target=30)
    assert [p.x_post_id for p in out] == [str(n) for n in range(30)]
    assert state["scrolls"] == 5
    assert state["settles"] == 5          # a settle follows every scroll


def test_collect_feed_gives_up_after_three_stale_scrolls():
    pages = [["1", "2"], ["1", "2", "3"]]   # then nothing new, ever
    eng, state = _engine(pages)
    out = eng._collect_feed(target=30)
    assert [p.x_post_id for p in out] == ["1", "2", "3"]
    # round 1 (fresh), round 2 (fresh), then three empty rounds -> 4 scrolls
    assert state["scrolls"] == 4


def test_collect_feed_stops_at_high_water_mark():
    pages = [["9", "8", "7"], ["9", "8", "7", "6", "5", "4"]]
    eng, _ = _engine(pages)
    out = eng._collect_feed(target=30, since_id="5")
    assert [p.x_post_id for p in out] == ["9", "8", "7", "6"]


def test_collect_feed_respects_round_limit():
    pages = [[str(n) for n in range(k + 1)] for k in range(50)]
    eng, state = _engine(pages)
    out = eng._collect_feed(target=30, rounds=4)
    assert len(out) == 4
    assert state["scrolls"] == 3
