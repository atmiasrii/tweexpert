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
        s = get_settings()
        if s.browser_engine == "playwright":
            from .playwright_engine import PlaywrightEngine
            _engine = PlaywrightEngine()
        else:
            _engine = FixtureEngine()
    return _engine


def set_engine(engine) -> None:
    global _engine
    _engine = engine


__all__ = ["get_engine", "set_engine", "BrowserEngine", "ParsedPost",
           "CanaryResult", "SessionDead", "ChallengeDetected", "SelectorMiss"]
