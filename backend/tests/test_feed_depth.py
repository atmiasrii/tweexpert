"""The 90-second watch sweep must not re-scroll the whole feed each time.

Measured: 64 feed collections in 80 minutes for 6 For You sweeps, roughly 28
seconds of scrolling each, on the single browser that sends also queue behind.
New posts arrive at the top, so at a 90-second cadence the watcher only needs
the first screen.
"""
from __future__ import annotations

from quill.browser import get_engine
from quill.bus.action_bus import get_bus
from quill.pipeline import watcher


def test_the_watch_sweep_asks_for_a_shallow_read(session, monkeypatch):
    asked = {}

    def fake_presence(kind, target=None):
        asked["kind"] = kind
        asked["target"] = target
        return []

    monkeypatch.setattr(get_engine(), "presence", fake_presence, raising=False)
    watcher.sweep_home(session)

    assert asked["kind"] == "home"
    assert asked["target"] == watcher.HOME_SWEEP_POSTS
    assert asked["target"] <= 12, "a 90-second sweep does not need a deep scroll"


def test_the_for_you_sweep_still_reads_deep(session, monkeypatch):
    """Depth is what gives the shortlist anything to choose between."""
    seen = []

    def fake_presence(kind, target=None):
        seen.append(target)
        return []

    monkeypatch.setattr(get_engine(), "presence", fake_presence, raising=False)
    get_bus().submit_read("presence", "home")
    assert seen == [None], "no explicit target means the engine's full depth"


def test_the_engine_honours_the_requested_depth(monkeypatch):
    from quill.browser.playwright_engine import PlaywrightEngine

    captured = {}

    def fake_collect(self, surface_handle="", since_id="", target=None, rounds=None):
        captured["target"] = target
        captured["rounds"] = rounds
        return []

    import contextlib
    monkeypatch.setattr(PlaywrightEngine, "_collect_feed", fake_collect)
    # Reads now happen on a parked feed tab; stub the tab swap, not navigation.
    monkeypatch.setattr(PlaywrightEngine, "_on_feed",
                        lambda self, name, url: contextlib.nullcontext())
    eng = PlaywrightEngine.__new__(PlaywrightEngine)
    eng.reg = type("R", (), {"surfaces": {"home": {"url": "https://x.com/home"}}})()

    eng.presence("home", target=8)
    assert captured["target"] == 8
    assert captured["rounds"] is not None and captured["rounds"] <= 3, \
        "a shallow read must also cap its scroll rounds, or it still scrolls"
