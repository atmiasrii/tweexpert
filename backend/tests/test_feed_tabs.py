"""Feeds live in their own tabs; replies never navigate them away."""
from __future__ import annotations

from quill.browser.playwright_engine import PlaywrightEngine


class _Page:
    def __init__(self, name):
        self.name = name
        self.url = ""
        self.gotos = 0
        self.reloads = 0
        self.closed = False

    def goto(self, url, **kw):
        self.url = url
        self.gotos += 1

    def reload(self, **kw):
        self.reloads += 1

    def is_closed(self):
        return self.closed


class _Ctx:
    def __init__(self):
        self.made = []

    def new_page(self):
        p = _Page(f"tab{len(self.made) + 1}")
        self.made.append(p)
        return p


def _engine(monkeypatch):
    eng = PlaywrightEngine.__new__(PlaywrightEngine)
    eng._ctx = _Ctx()
    eng._page = eng._work = _Page("work")
    eng._feeds = {}
    eng.reg = type("R", (), {"surfaces": {
        "home": {"url": "https://x.com/home"},
        "search": {"url_template": "https://x.com/search?q={query}&f=live"},
    }})()
    monkeypatch.setattr(eng, "_check_challenges", lambda: None)
    monkeypatch.setattr("quill.browser.playwright_engine.time.sleep", lambda s: None)
    monkeypatch.setattr(eng, "_collect_feed", lambda **kw: [])
    return eng


def test_the_home_feed_gets_its_own_tab_and_the_work_page_is_untouched(monkeypatch):
    eng = _engine(monkeypatch)
    eng.presence("home")
    assert len(eng._ctx.made) == 1
    assert eng._ctx.made[0].url == "https://x.com/home"
    assert eng._work.gotos == 0, "the write page must not be navigated for a read"
    assert eng._page is eng._work, "self._page is restored after the read"


def test_a_second_read_reloads_the_parked_tab_instead_of_navigating(monkeypatch):
    eng = _engine(monkeypatch)
    eng.presence("home")
    eng.presence("home")
    tab = eng._ctx.made[0]
    assert len(eng._ctx.made) == 1
    assert tab.gotos == 1 and tab.reloads == 1


def test_the_latest_search_is_a_separate_parked_tab(monkeypatch):
    eng = _engine(monkeypatch)
    eng.presence("home")
    eng.search("filter:follows -filter:replies")
    assert len(eng._ctx.made) == 2
    assert "f=live" in eng._ctx.made[1].url
    assert eng._feeds["home"] is not eng._feeds["latest"]


def test_a_dropped_tab_is_opened_again(monkeypatch):
    eng = _engine(monkeypatch)
    eng.presence("home")
    eng._ctx.made[0].closed = True
    eng.presence("home")
    assert len(eng._ctx.made) == 2
    assert eng._feeds["home"] is eng._ctx.made[1]


def test_the_page_is_restored_even_when_the_read_fails(monkeypatch):
    eng = _engine(monkeypatch)

    def boom(**kw):
        raise RuntimeError("render")

    monkeypatch.setattr(eng, "_collect_feed", boom)
    try:
        eng.presence("home")
    except RuntimeError:
        pass
    assert eng._page is eng._work
