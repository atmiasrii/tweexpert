"""X's "Something went wrong. Try reloading." page gets one Retry click.

Seen on three profile reads in one evening: the page has a Retry button and no
articles, and the old code waited out the full feed budget and raised.
"""
from __future__ import annotations

from quill.browser.base import SelectorMiss
from quill.browser.playwright_engine import PlaywrightEngine


class _Btn:
    def __init__(self):
        self.clicked = 0

    def count(self):
        return 1

    @property
    def first(self):
        return self

    def click(self, timeout=0):
        self.clicked += 1


class _Page:
    def __init__(self, broken: bool):
        self.text = "Something went wrong. Try reloading." if broken else "Posts Replies"
        self.btn = _Btn()

    def locator(self, sel):
        page = self

        class _Loc:
            @property
            def first(self):
                return self

            def inner_text(self, timeout=0):
                return page.text
        return _Loc()

    def get_by_role(self, role, name=""):
        return self.btn


def _engine(page):
    eng = PlaywrightEngine.__new__(PlaywrightEngine)
    eng._page = page
    return eng


def test_the_broken_page_is_retried_once_and_the_feed_then_reads(monkeypatch):
    page = _Page(broken=True)
    eng = _engine(page)
    calls = []

    class _Tweets:
        def count(self):
            return 0

    def find_all(key, wait_ms=0):
        calls.append(wait_ms)
        if len(calls) == 1:
            raise SelectorMiss("tweet")
        return _Tweets(), "sel"

    monkeypatch.setattr(eng, "_find_all", find_all)
    monkeypatch.setattr(eng, "_feed_scroll", lambda: None)
    monkeypatch.setattr(eng, "_wait_for_articles", lambda *a, **k: 0)
    monkeypatch.setattr("quill.browser.playwright_engine.time.sleep", lambda s: None)

    out = eng._collect_feed(target=5, rounds=1)

    assert page.btn.clicked == 1
    assert len(calls) == 2, "one miss, one Retry, one more look"
    assert out == []


def test_a_normal_miss_still_raises(monkeypatch):
    eng = _engine(_Page(broken=False))

    def find_all(key, wait_ms=0):
        raise SelectorMiss("tweet")

    monkeypatch.setattr(eng, "_find_all", find_all)
    try:
        eng._collect_feed(target=5, rounds=1)
    except SelectorMiss:
        return
    raise AssertionError("a miss on a healthy page must still be a miss")
