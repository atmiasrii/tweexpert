"""Fixture engine (I-05, T-01). Implements the identical BrowserEngine
interface from committed JSON. No session, no network, no GPU.

It can be nudged into failure states for the acceptance tests:
  set_session_dead(True)   -> login_check/read raise SessionDead (T-10)
  set_challenge("rate_limit") -> raise ChallengeDetected (E-05)
  break_selector("tweet")  -> canary reports a miss (T-11)
"""
from __future__ import annotations

import itertools
import json
import time
from datetime import datetime, timedelta, timezone

from ..config import get_settings
from .base import CanaryResult, ChallengeDetected, ParsedPost, SessionDead
from .selectors import load_registry

_ids = itertools.count(1950000000000000000)


class FixtureEngine:
    name = "fixture"

    def __init__(self):
        self.s = get_settings()
        self._dead = False
        self._challenge: str | None = None
        self._broken: set[str] = set()
        self.posted: list[dict] = []       # writes land here
        self.deleted: list[str] = []
        self._load()

    # -- test hooks ------------------------------------------------------
    def set_session_dead(self, dead: bool) -> None:
        self._dead = dead

    def set_challenge(self, kind: str | None) -> None:
        self._challenge = kind

    def break_selector(self, key: str) -> None:
        self._broken.add(key)

    def fix_selectors(self) -> None:
        self._broken.clear()

    # -- data ------------------------------------------------------------
    def _load(self):
        d = self.s.fixtures_dir
        self._timeline = _read(d / "timeline.json", {})
        self._notifs = _read(d / "notifications.json", [])
        self._own = _read(d / "own_posts.json", [])

    def _guard(self):
        if self._dead:
            raise SessionDead("fixture session marked dead")
        if self._challenge:
            raise ChallengeDetected(self._challenge)

    def _mk(self, handle: str, raw: dict) -> ParsedPost:
        mins = raw.get("minutes_ago", 60)
        created = datetime.now(timezone.utc) - timedelta(minutes=mins)
        pid = raw["x_post_id"]
        return ParsedPost(
            x_post_id=pid,
            author_handle=handle,
            text=raw["text"],
            created_at=created,
            url=f"https://x.com/{handle}/status/{pid}",
            kind=raw.get("kind", "post"),
            likes=raw.get("likes", 0), reposts=raw.get("reposts", 0),
            replies=raw.get("replies", 0), views=raw.get("views", 0),
            media=raw.get("media", False), lang=raw.get("lang", "en"),
            parent_x_id=raw.get("parent_x_id", ""),
        )

    # -- interface -------------------------------------------------------
    def login_check(self) -> bool:
        self._guard()
        return True

    def read_user(self, handle: str, since_id: str = "") -> list[ParsedPost]:
        self._guard()
        rows = self._timeline.get(handle, [])
        out: list[ParsedPost] = []
        for raw in rows:
            if since_id and raw["x_post_id"] == since_id:
                break  # high-water mark (I-03)
            out.append(self._mk(handle, raw))
        return out

    def read_post(self, x_post_id: str, depth: int = 3) -> list[ParsedPost]:
        self._guard()
        for handle, rows in self._timeline.items():
            for raw in rows:
                if raw["x_post_id"] == x_post_id:
                    return [self._mk(handle, raw)]
        return []

    def search(self, query: str) -> list[ParsedPost]:
        self._guard()
        out = []
        for handle, rows in self._timeline.items():
            for raw in rows:
                if query.lower() in raw["text"].lower():
                    out.append(self._mk(handle, raw))
        return out

    def notifications(self) -> list[ParsedPost]:
        self._guard()
        return [self._mk(n["author_handle"], n) for n in self._notifs]

    def metrics(self, x_post_id: str) -> ParsedPost | None:
        self._guard()
        for raw in self._own:
            if raw["x_post_id"] == x_post_id:
                # simulate slow growth over time
                bump = 1 + (time.time() % 100) / 1000
                p = self._mk(get_settings().operator_handle, raw)
                p.likes = int(raw.get("likes", 0) * bump)
                p.views = int(raw.get("views", 0) * bump)
                return p
        for w in self.posted:
            if w["x_post_id"] == x_post_id:
                return ParsedPost(x_post_id, get_settings().operator_handle,
                                  w["text"], likes=2, views=50)
        return None

    def presence(self, kind: str) -> list[ParsedPost]:
        self._guard()
        # scrolling home surfaces some posts; feeds discovery (H-05)
        out = []
        for handle, rows in self._timeline.items():
            for raw in rows[:1]:
                out.append(self._mk(handle, raw))
        return out

    def canary(self) -> CanaryResult:
        reg = load_registry()
        missing = [k for k in reg.keys() if k in self._broken]
        return CanaryResult(ok=not missing, missing=missing)

    def publish(self, text: str) -> str:
        self._guard()
        pid = str(next(_ids))
        self.posted.append({"x_post_id": pid, "text": text, "kind": "post"})
        return pid

    def reply(self, parent_x_id: str, text: str) -> str:
        self._guard()
        pid = str(next(_ids))
        self.posted.append({"x_post_id": pid, "text": text, "kind": "reply",
                            "parent": parent_x_id})
        return pid

    def thread(self, texts: list[str]) -> list[str]:
        self._guard()
        ids = []
        prev = ""
        for t in texts:
            pid = str(next(_ids))
            self.posted.append({"x_post_id": pid, "text": t, "kind": "thread",
                                "parent": prev})
            prev = pid
            ids.append(pid)
        return ids

    def delete_post(self, x_post_id: str) -> bool:
        self.deleted.append(x_post_id)
        self.posted = [p for p in self.posted if p["x_post_id"] != x_post_id]
        return True

    def exists(self, idempotency_key: str, text: str) -> bool:
        """Reconciliation probe (Q-02): does a matching post exist?"""
        return any(p["text"] == text for p in self.posted)


def _read(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default
