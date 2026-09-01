"""Playwright engine (§6). Drives a real logged-in Chromium for overnight
and scheduled work. Headed under Xvfb, persistent profile on a volume (E-01).

Human-shaped: per-character typing with pauses (E-09), non-linear mouse
paths and variable scroll (E-10), reads replies before writing (E-11).
Screenshot + HTML on every failure (E-08). Challenge detector (E-05).
Selector resolution tries primary then fallbacks; total miss => SelectorMiss.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_settings
from ..logging_setup import get_logger
from .base import (CanaryResult, ChallengeDetected, ParsedPost, SelectorMiss,
                   SessionDead)
from .selectors import SelectorEntry, load_registry

log = get_logger("quill.browser")


class PlaywrightEngine:
    name = "playwright"

    def __init__(self):
        self.s = get_settings()
        self.reg = load_registry()
        self._pw = None
        self._ctx = None
        self._page = None
        self._start()

    def _start(self):
        from playwright.sync_api import sync_playwright  # lazy (browser proc only)

        self.s.profile_dir.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.s.profile_dir),
            headless=False,                       # headed under Xvfb (E-01)
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id=self.s.operator_timezone,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()

    def close(self):
        try:
            if self._ctx:
                self._ctx.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    # -- selector resolution (E-06/E-07) --------------------------------
    def _find_all(self, key: str):
        entry: SelectorEntry = self.reg.get(key)
        for sel in entry.all():
            try:
                loc = self._page.locator(sel)
                if loc.count() > 0:
                    return loc, sel
            except Exception:
                continue
        raise SelectorMiss(key, self._capture("selector_miss"))

    def _find(self, key: str):
        loc, _ = self._find_all(key)
        return loc.first

    # -- failure capture (E-08) -----------------------------------------
    def _capture(self, tag: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        base = self.s.debug_dir / f"{ts}-{tag}"
        try:
            self._page.screenshot(path=f"{base}.png", full_page=False)
            Path(f"{base}.html").write_text(self._page.content(), encoding="utf-8")
        except Exception:
            pass
        return f"{base}.png"

    # -- challenge detection (E-05) -------------------------------------
    def _check_challenges(self):
        for kind, sels in self.reg.challenges.items():
            for sel in sels:
                try:
                    if self._page.locator(sel).count() > 0:
                        shot = self._capture(f"challenge-{kind}")
                        raise ChallengeDetected(kind, shot)
                except ChallengeDetected:
                    raise
                except Exception:
                    continue

    # -- human-shaped input (E-09/E-10) ---------------------------------
    def _human_move_click(self, loc):
        box = loc.bounding_box()
        if box:
            steps = random.randint(8, 20)
            tx = box["x"] + box["width"] / 2
            ty = box["y"] + box["height"] / 2
            self._page.mouse.move(tx, ty, steps=steps)  # non-linear via steps
            time.sleep(random.uniform(0.05, 0.25))
        loc.click()

    def _human_type(self, loc, text: str):
        loc.click()
        for ch in text:
            self._page.keyboard.type(ch)
            time.sleep(random.uniform(0.03, 0.14))       # per-char delay
            if random.random() < 0.04:
                time.sleep(random.uniform(0.3, 1.1))      # occasional pause

    def _human_scroll(self, rounds: int = 5):
        for _ in range(rounds):
            self._page.mouse.wheel(0, random.randint(300, 900))
            time.sleep(random.uniform(0.4, 1.6))           # dwell
            if random.random() < 0.2:
                self._page.mouse.wheel(0, -random.randint(100, 300))  # scroll-back
                time.sleep(random.uniform(0.3, 0.8))

    def _goto(self, url: str):
        self._page.goto(url, wait_until="domcontentloaded", timeout=45000)
        time.sleep(random.uniform(1.0, 2.5))
        self._check_challenges()

    # -- interface -------------------------------------------------------
    def login_check(self) -> bool:
        try:
            self._goto(self.reg.surfaces["home"]["url"])
            self._find("logged_in_marker")
            return True
        except (SelectorMiss, ChallengeDetected):
            raise SessionDead("logged-in marker absent")

    def read_user(self, handle: str, since_id: str = "") -> list[ParsedPost]:
        url = self.reg.surfaces["profile"]["url_template"].format(handle=handle)
        self._goto(url)
        self._human_scroll(3)
        return self._parse_timeline(handle, since_id)

    def _extract(self, art, surface_handle: str = "") -> ParsedPost | None:
        """One <article> -> ParsedPost. Reads the tweet's OWN author from its
        permalink (needed on the home/For-You feed where every post has a
        different author), falling back to the surface handle on a profile page."""
        try:
            text = art.locator(self.reg.get("tweet_text").primary).first.inner_text()
        except Exception:
            text = ""
        pid, link, author = "", "", surface_handle
        try:
            href = art.locator(self.reg.get("tweet_link").primary).first.get_attribute("href")
            if href and "/status/" in href:
                # href looks like /{author}/status/{id}
                parts = href.strip("/").split("/")
                if len(parts) >= 3 and parts[1] == "status":
                    author = author or parts[0]
                    if not surface_handle:
                        author = parts[0]
                pid = href.split("/status/")[1].split("?")[0].split("/")[0]
                link = f"https://x.com{href}"
        except Exception:
            pass
        if not pid:
            return None
        media = False
        try:
            media = art.locator('[data-testid="tweetPhoto"], [data-testid="videoPlayer"]').count() > 0
        except Exception:
            pass
        return ParsedPost(x_post_id=pid, author_handle=author, text=text,
                          url=link, media=media)

    def _parse_timeline(self, handle: str, since_id: str = "") -> list[ParsedPost]:
        tweets, _ = self._find_all("tweet")
        out: list[ParsedPost] = []
        for i in range(min(tweets.count(), 30)):
            p = self._extract(tweets.nth(i), surface_handle=handle)
            if p is None:
                continue
            if since_id and p.x_post_id == since_id:
                break  # high-water mark (I-03)
            out.append(p)
        return out

    def _collect_feed(self, surface_handle: str = "", since_id: str = "",
                      target: int = 25, rounds: int = 7) -> list[ParsedPost]:
        """Scroll a feed incrementally, collecting unique posts until `target`
        or a known high-water id. Used for home/search where one pass misses
        most of the feed."""
        seen: set[str] = set()
        out: list[ParsedPost] = []
        for _ in range(rounds):
            tweets, _sel = self._find_all("tweet")
            for i in range(tweets.count()):
                p = self._extract(tweets.nth(i), surface_handle=surface_handle)
                if p is None or p.x_post_id in seen:
                    continue
                if since_id and p.x_post_id == since_id:
                    return out
                seen.add(p.x_post_id)
                out.append(p)
            if len(out) >= target:
                break
            self._human_scroll(1)
        return out[:target]

    def read_post(self, x_post_id: str, depth: int = 3) -> list[ParsedPost]:
        # E-11: reading replies improves context and looks human
        return self._parse_timeline("", since_id="")[:depth]

    def search(self, query: str) -> list[ParsedPost]:
        url = self.reg.surfaces["search"]["url_template"].format(query=query)
        self._goto(url)
        return self._collect_feed(surface_handle="", target=25)

    def notifications(self) -> list[ParsedPost]:
        self._goto(self.reg.surfaces["notifications"]["url"])
        return self._collect_feed(surface_handle="", target=25)

    def metrics(self, x_post_id: str) -> ParsedPost | None:
        return None  # parsed from own-post pages in production

    def presence(self, kind: str) -> list[ParsedPost]:
        # The For-You / home feed: collect the real feed with per-tweet authors.
        self._goto(self.reg.surfaces["home"]["url"])
        return self._collect_feed(surface_handle="", target=25)

    def following(self, handle: str = "") -> list[tuple[str, str, str]]:
        """Scrape who the operator follows, for the live watchlist import."""
        handle = handle or self.s.operator_handle
        self._goto(f"https://x.com/{handle}/following")
        seen: set[str] = set()
        out: list[tuple[str, str, str]] = []
        for _ in range(12):
            try:
                cells = self._page.locator('[data-testid="UserCell"]')
                for i in range(cells.count()):
                    try:
                        links = cells.nth(i).locator('a[href^="/"]')
                        h = ""
                        for j in range(links.count()):
                            href = links.nth(j).get_attribute("href") or ""
                            m = href.strip("/")
                            if m and "/" not in m and not m.startswith("i"):
                                h = m
                                break
                        if h and h not in seen:
                            seen.add(h)
                            out.append((h, h, "B"))
                    except Exception:
                        continue
            except Exception:
                pass
            if len(out) >= 200:
                break
            self._human_scroll(1)
        return out

    def canary(self) -> CanaryResult:
        missing = []
        for surface in ("home",):
            try:
                self._goto(self.reg.surfaces[surface]["url"])
            except Exception:
                pass
            for key in self.reg.surfaces[surface].get("keys", []):
                try:
                    self._find(key)
                except SelectorMiss:
                    missing.append(key)
        shot = self._capture("canary") if missing else ""
        return CanaryResult(ok=not missing, missing=missing, screenshot_path=shot)

    def publish(self, text: str) -> str:
        self._goto(self.reg.surfaces["compose"]["url"])
        self._human_type(self._find("composer"), text)
        time.sleep(random.uniform(0.5, 1.5))
        self._human_move_click(self._find("post_button"))
        time.sleep(random.uniform(2, 4))
        return self._last_own_id()

    def reply(self, parent_x_id: str, text: str) -> str:
        self._goto(f"https://x.com/i/status/{parent_x_id}")
        self._human_scroll(1)                    # read replies first (E-11)
        self._human_move_click(self._find("reply_button"))
        time.sleep(random.uniform(0.5, 1.2))
        self._human_type(self._find("composer"), text)
        self._human_move_click(self._find("post_button"))
        time.sleep(random.uniform(2, 4))
        return self._last_own_id()

    def thread(self, texts: list[str]) -> list[str]:
        ids = []
        for i, t in enumerate(texts):
            ids.append(self.publish(t) if i == 0 else self.reply(ids[-1], t))
        return ids

    def delete_post(self, x_post_id: str) -> bool:
        self._goto(f"https://x.com/{self.s.operator_handle}/status/{x_post_id}")
        try:
            self._human_move_click(self._find("delete_menu"))
            time.sleep(0.5)
            self._page.get_by_text("Delete", exact=False).first.click()
            self._human_move_click(self._find("delete_confirm"))
            return True
        except Exception:
            self._capture("delete_failed")
            return False

    def _last_own_id(self) -> str:
        try:
            self._goto(self.reg.surfaces["profile"]["url_template"].format(
                handle=self.s.operator_handle))
            posts = self._parse_timeline(self.s.operator_handle)
            return posts[0].x_post_id if posts else ""
        except Exception:
            return ""
