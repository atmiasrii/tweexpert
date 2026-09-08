"""Browser engine interface. Fixture and Playwright engines implement it
identically so the product runs offline with no session/GPU (I-05, T-01)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol


@dataclass
class ParsedPost:
    x_post_id: str
    author_handle: str
    text: str
    created_at: Optional[datetime] = None
    url: str = ""
    kind: str = "post"                    # post|reply|quote|retweet
    likes: int = 0
    reposts: int = 0
    replies: int = 0
    views: int = 0
    media: bool = False
    lang: str = "en"
    parent_x_id: str = ""
    # "Who can reply? Only some accounts can reply." X lets an author
    # restrict replies; clicking Reply then opens a permissions dialog
    # instead of a composer. Caught in the feed so it is never drafted.
    reply_restricted: bool = False

    def metrics(self) -> dict:
        return {"likes": self.likes, "reposts": self.reposts,
                "replies": self.replies, "views": self.views}


@dataclass
class CanaryResult:
    ok: bool
    missing: list[str] = field(default_factory=list)
    screenshot_path: str = ""


# --- exceptions ---------------------------------------------------------
class BrowserError(Exception):
    screenshot_path: str = ""


class SessionDead(BrowserError):
    """Logged-out / heartbeat failed (E-03)."""


class ChallengeDetected(BrowserError):
    """Login wall, unusual-activity, captcha or rate-limit (E-05)."""

    def __init__(self, kind: str, screenshot_path: str = ""):
        super().__init__(f"challenge: {kind}")
        self.kind = kind
        self.screenshot_path = screenshot_path


class SelectorMiss(BrowserError):
    """A registry entry no longer resolves (E-07, T-11)."""

    def __init__(self, key: str, screenshot_path: str = ""):
        super().__init__(f"selector miss: {key}")
        self.key = key
        self.screenshot_path = screenshot_path


class PostUnavailable(BrowserError):
    """The post we were told to reply to is gone, protected, or redirected."""

    def __init__(self, x_post_id: str, screenshot_path: str = ""):
        super().__init__(f"post unavailable: {x_post_id}")
        self.x_post_id = x_post_id
        self.screenshot_path = screenshot_path


class SendRejected(BrowserError):
    """Observed not to have sent, before or instead of posting. Safe to retry."""

    def __init__(self, reason: str, screenshot_path: str = ""):
        super().__init__(f"send rejected: {reason}")
        self.screenshot_path = screenshot_path


class SendNotConfirmed(BrowserError):
    """Clicked send, could not find the reply afterwards.

    Deliberately distinct from a failure: the reply may or may not be live, so
    it must never be retried automatically and must never be recorded as sent.
    """

    def __init__(self, x_post_id: str, screenshot_path: str = ""):
        super().__init__(f"send not confirmed for {x_post_id}")
        self.x_post_id = x_post_id
        self.screenshot_path = screenshot_path


class BrowserEngine(Protocol):
    name: str

    def login_check(self) -> bool: ...
    def read_user(self, handle: str, since_id: str = "") -> list[ParsedPost]: ...
    def read_post(self, x_post_id: str, depth: int = 3) -> list[ParsedPost]: ...
    def search(self, query: str) -> list[ParsedPost]: ...
    def notifications(self) -> list[ParsedPost]: ...
    def metrics(self, x_post_id: str) -> ParsedPost | None: ...
    def presence(self, kind: str) -> list[ParsedPost]: ...
    def canary(self) -> CanaryResult: ...
    def publish(self, text: str) -> str: ...
    def reply(self, parent_x_id: str, text: str,
              permalink: str = "", author: str = "") -> str: ...
    def thread(self, texts: list[str]) -> list[str]: ...
    def delete_post(self, x_post_id: str) -> bool: ...
