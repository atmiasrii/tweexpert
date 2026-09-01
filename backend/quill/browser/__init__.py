"""Engine selection. `fixture` (offline) or `playwright` (real), same interface."""
from __future__ import annotations

from ..config import get_settings
from .base import (BrowserEngine, CanaryResult, ChallengeDetected, ParsedPost,
                   SelectorMiss, SessionDead)
from .fixture_engine import FixtureEngine

_engine = None


def get_engine(reset: bool = False):
    global _engine
    if _engine is None or reset:
        if reset and _engine is not None and hasattr(_engine, "close"):
            try:
                _engine.close()          # stop the old actor thread / context
            except Exception:
                pass
        s = get_settings()
        if s.browser_engine == "playwright":
            # Wrap Playwright in the single-thread actor so sync-API calls never
            # cross threads (greenlet.error). Fixture stays plain.
            from .actor import ThreadedEngine
            _engine = ThreadedEngine()
        else:
            _engine = FixtureEngine()
    return _engine


def set_engine(engine) -> None:
    global _engine
    _engine = engine


__all__ = ["get_engine", "set_engine", "BrowserEngine", "ParsedPost",
           "CanaryResult", "SessionDead", "ChallengeDetected", "SelectorMiss"]
