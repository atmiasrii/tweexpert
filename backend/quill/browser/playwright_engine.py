"""Playwright engine (§6). Drives a real logged-in Chromium for overnight
and scheduled work. Headed under Xvfb, persistent profile on a volume (E-01).

Human-shaped: per-character typing with pauses (E-09), non-linear mouse
paths and variable scroll (E-10), reads replies before writing (E-11).
Screenshot + HTML on every failure (E-08). Challenge detector (E-05).
Selector resolution tries primary then fallbacks; total miss => SelectorMiss.
"""
from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_settings
from ..logging_setup import get_logger
from ..pipeline.pipeline import permalink_for
from .base import (CanaryResult, ChallengeDetected, ParsedPost,
                   PostUnavailable, SelectorMiss, SendNotConfirmed,
                   SendRejected,
                   SessionDead)
from .reply_verify import (status_id_from_href, target_article_selectors,
                           texts_match)
from .selectors import SelectorEntry, load_registry

log = get_logger("quill.browser")


def feed_step(stale_rounds: int, added: int, collected: int, target: int,
              max_stale: int = 3) -> tuple[int, str]:
    """One round of the feed-collection loop's bookkeeping, kept pure so it
    can be tested without a browser.

    Returns the new stale-round counter and a stop reason: "" to keep
    scrolling, "target" once enough unique posts are in hand, "exhausted"
    after `max_stale` consecutive scrolls added nothing new.
    """
    stale = 0 if added > 0 else stale_rounds + 1
    if collected >= target:
        return stale, "target"
    if stale >= max_stale:
        return stale, "exhausted"
    return stale, ""


class PlaywrightEngine:
    name = "playwright"

    def __init__(self):
        self.s = get_settings()
        self.reg = load_registry()
        self._pw = None
        self._ctx = None
        self._page = None
        self._start()

    # Chromium shows a "Restore pages?" bubble when the profile was not closed
    # cleanly, and then restores the previous tabs. Both hurt: the bubble sits
    # over the page, and the restored tabs mean pages[0] is some stale tab
    # rather than the one we are about to drive. Quill force-kills the browser
    # process on stop, so a crashed profile is the normal case, not a rare one.
    _CLEAN_EXIT_FLAGS = [
        "--disable-blink-features=AutomationControlled",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=InfiniteSessionRestore,TranslateUI",
        "--restore-last-session=false",
    ]

    def _mark_profile_clean(self) -> None:
        """Tell Chromium the last session ended normally.

        The flags above suppress the bubble in most builds, but the profile's
        own Preferences file is what actually decides, so fix it at the source.
        """
        for name in ("Default/Preferences", "Default/Secure Preferences"):
            path = self.s.profile_dir / name
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            profile = data.setdefault("profile", {})
            if (profile.get("exit_type") == "Normal"
                    and profile.get("exited_cleanly") is True):
                continue
            profile["exit_type"] = "Normal"
            profile["exited_cleanly"] = True
            try:
                path.write_text(json.dumps(data), encoding="utf-8")
                log.info("profile marked as cleanly closed (%s)", name)
            except OSError as e:
                log.warning("could not clear the crash flag: %s", e)

    def _start(self):
        from playwright.sync_api import sync_playwright  # lazy (browser proc only)

        self.s.profile_dir.mkdir(parents=True, exist_ok=True)
        self._mark_profile_clean()
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.s.profile_dir),
            headless=False,                       # headed under Xvfb (E-01)
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id=self.s.operator_timezone,
            args=list(self._CLEAN_EXIT_FLAGS),
        )
        self._page = self._pick_page()

    def _pick_page(self):
        """One page to drive, even if a restore reopened several.

        Taking pages[0] blindly meant driving whichever tab Chromium happened to
        restore, so every selector missed on a page we were not looking at.
        """
        pages = [p for p in self._ctx.pages if not p.is_closed()]
        if not pages:
            return self._ctx.new_page()
        keep = pages[0]
        for extra in pages[1:]:
            try:
                extra.close()
            except Exception:
                pass
        if len(pages) > 1:
            log.info("closed %d restored tab(s)", len(pages) - 1)
        return keep

    def close(self):
        try:
            if self._ctx:
                self._ctx.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    # -- selector resolution (E-06/E-07) --------------------------------
    # X renders the timeline client-side and can take well over ten seconds on a
    # cold load. Looking for tweets right after domcontentloaded was a race, and
    # losing it raised SelectorMiss on a page that was simply still spinning.
    FEED_WAIT_MS = 20000
    # How many unique posts one feed sweep should bring back, how many scrolls
    # it may spend getting there, how long to let X attach new articles after
    # each scroll (the feed is virtualised, so counting straight after the
    # wheel event saw the old page), and how many empty scrolls mean the feed
    # has nothing more to give.
    FEED_TARGET = 30
    FEED_ROUNDS = 30
    FEED_SETTLE_MS = 2500
    FEED_STALE_ROUNDS = 3

    def _find_all(self, key: str, wait_ms: int = 0):
        entry: SelectorEntry = self.reg.get(key)
        deadline = time.time() + (wait_ms / 1000.0)
        while True:
            for sel in entry.all():
                try:
                    loc = self._page.locator(sel)
                    if loc.count() > 0:
                        return loc, sel
                except Exception:
                    continue
            if time.time() >= deadline:
                break
            time.sleep(0.5)
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


    def _feed_scroll(self) -> None:
        """One collection scroll: further than a reading scroll, since a tweet
        with media is taller than the 300-900px a casual wheel moves."""
        self._page.mouse.wheel(0, random.randint(1400, 2400))
        time.sleep(random.uniform(0.5, 1.4))
        if random.random() < 0.15:
            self._page.mouse.wheel(0, -random.randint(100, 300))
            time.sleep(random.uniform(0.3, 0.7))

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

        # Post age and engagement counts. Without these the freshness term of
        # the relevance score is always zero, the 90-minute skip gate never
        # fires, and the thread-saturation term is always 1.0 — which is what
        # made a real For You post unable to clear the auto threshold at all.
        created_at = None
        try:
            stamp = art.locator("time").first.get_attribute("datetime")
            if stamp:
                created_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except Exception:
            pass

        counts = self._engagement_counts(art)
        restricted = False
        try:
            blob = art.inner_text()
            restricted = ("can reply" in blob) or ("replies are limited" in blob.lower())
        except Exception:
            pass

        return ParsedPost(x_post_id=pid, author_handle=author, text=text,
                          url=link, media=media, created_at=created_at,
                          likes=counts.get("like", 0),
                          reposts=counts.get("retweet", 0),
                          replies=counts.get("reply", 0),
                          views=counts.get("views", 0),
                          reply_restricted=restricted)

    # X renders counts only in the aria-label ("12 replies, 40 reposts, 300
    # likes"), and hides the element entirely at zero, so a miss means zero.
    _COUNT_RE = re.compile(r"([\d,.]+)\s*([KMB]?)", re.I)
    _MULT = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}

    @classmethod
    def _parse_count(cls, raw: str) -> int:
        m = cls._COUNT_RE.search(raw or "")
        if not m:
            return 0
        try:
            n = float(m.group(1).replace(",", ""))
        except ValueError:
            return 0
        return int(n * cls._MULT.get(m.group(2).upper(), 1))

    def _engagement_counts(self, art) -> dict:
        out: dict[str, int] = {}
        for key, testid in (("reply", "reply"), ("retweet", "retweet"),
                            ("like", "like")):
            try:
                el = art.locator(f'[data-testid="{testid}"]').first
                out[key] = self._parse_count(el.get_attribute("aria-label") or "")
            except Exception:
                out[key] = 0
        try:
            label = art.locator('a[href*="/analytics"]').first.get_attribute("aria-label")
            out["views"] = self._parse_count(label or "")
        except Exception:
            out["views"] = 0
        return out

    def _parse_timeline(self, handle: str, since_id: str = "") -> list[ParsedPost]:
        tweets, _ = self._find_all("tweet", wait_ms=self.FEED_WAIT_MS)
        out: list[ParsedPost] = []
        for i in range(min(tweets.count(), 30)):
            p = self._extract(tweets.nth(i), surface_handle=handle)
            if p is None:
                continue
            if since_id and p.x_post_id == since_id:
                break  # high-water mark (I-03)
            out.append(p)
        return out

    def _tweet_count(self) -> int:
        """Articles currently attached, without raising or capturing on zero."""
        for sel in self.reg.get("tweet").all():
            try:
                n = self._page.locator(sel).count()
            except Exception:
                continue
            if n > 0:
                return n
        return 0

    def _wait_for_articles(self, before: int, timeout_ms: int) -> int:
        """Block until the article count moves off `before`, or give up after
        `timeout_ms`. Returns the count seen last."""
        deadline = time.time() + timeout_ms / 1000.0
        while True:
            n = self._tweet_count()
            if n != before or time.time() >= deadline:
                return n
            time.sleep(0.25)

    def _article_id(self, art) -> str:
        """Cheap post id from the permalink, so already-seen articles are not
        re-extracted on every round."""
        try:
            href = art.locator(self.reg.get("tweet_link").primary).first.get_attribute("href")
        except Exception:
            return ""
        if not href or "/status/" not in href:
            return ""
        return href.split("/status/")[1].split("?")[0].split("/")[0]

    def _collect_feed(self, surface_handle: str = "", since_id: str = "",
                      target: int | None = None,
                      rounds: int | None = None) -> list[ParsedPost]:
        """Scroll a feed incrementally, collecting unique posts until `target`
        or a known high-water id. Used for home/search where one pass misses
        most of the feed.

        X virtualises the feed: after a scroll, new articles take a moment to
        attach, and counting straight away saw the same page again. Each scroll
        is followed by a wait for the article count to move, and the sweep only
        gives up early once FEED_STALE_ROUNDS scrolls in a row add nothing.
        """
        target = self.FEED_TARGET if target is None else target
        rounds = self.FEED_ROUNDS if rounds is None else rounds
        seen: set[str] = set()
        out: list[ParsedPost] = []
        stale = 0
        reason = ""
        rnd = -1
        for rnd in range(rounds):
            try:
                tweets, _sel = self._find_all(
                    "tweet", wait_ms=self.FEED_WAIT_MS if rnd == 0 else 0)
            except SelectorMiss:
                if rnd == 0:
                    raise
                tweets = None                     # virtualiser mid-swap
            added = 0
            count = tweets.count() if tweets is not None else 0
            for i in range(count):
                art = tweets.nth(i)
                pid = self._article_id(art)
                if pid and pid in seen:
                    continue
                if since_id and pid == since_id:
                    return out[:target]           # high-water mark (I-03)
                p = self._extract(art, surface_handle=surface_handle)
                if p is None or p.x_post_id in seen:
                    continue
                if since_id and p.x_post_id == since_id:
                    return out[:target]
                seen.add(p.x_post_id)
                out.append(p)
                added += 1
            stale, reason = feed_step(stale, added, len(out), target,
                                      self.FEED_STALE_ROUNDS)
            if reason or rnd == rounds - 1:
                break                             # no scroll after the last look
            self._feed_scroll()
            self._wait_for_articles(count, self.FEED_SETTLE_MS)
        log.info("feed sweep: %d unique posts in %d round(s) (%s)",
                 len(out), rnd + 1, reason or "round limit")
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
        return self._collect_feed(surface_handle="", target=self.FEED_TARGET)

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
        """Do the registry's selectors still resolve on a live page?

        Gets the same render wait the feed reads have. It used to look once,
        immediately after domcontentloaded, so on a cold load it reported the
        layout broken while X was still drawing it, and a false miss here
        demotes every account.
        """
        missing = []
        for surface in ("home",):
            try:
                self._goto(self.reg.surfaces[surface]["url"])
            except Exception:
                pass
            # One render budget for the whole surface: the first key waits up
            # to FEED_WAIT_MS, later keys get whatever of it is left. A page
            # that is still loading never fails; a genuinely missing key
            # costs at most one wait in total.
            deadline = time.time() + self.FEED_WAIT_MS / 1000.0
            for key in self.reg.surfaces[surface].get("keys", []):
                remaining_ms = max(0, int((deadline - time.time()) * 1000))
                try:
                    self._find_all(key, wait_ms=remaining_ms)
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

    # Writes get the same patience reads got. Every lookup below used to fire
    # once, immediately, racing X's client-side render.
    WRITE_WAIT_MS = 15000
    supports_exists = True

    def _open_post(self, x_post_id: str, permalink: str = "",
                   author: str = "") -> None:
        """Navigate to one specific post and prove we arrived.

        The old code went to /i/status/{id}, which redirects; after a redirect
        there is no way to tell a loaded post from an error page, so a reply
        could be typed against whatever happened to be on screen.
        """
        url = permalink or permalink_for(author, x_post_id)
        self._goto(url)
        if f"/status/{x_post_id}" not in (self._page.url or ""):
            raise PostUnavailable(x_post_id, self._capture("post_unavailable"))

    def _target_article(self, x_post_id: str):
        """The article for this exact post, never `.first` of whatever loaded."""
        deadline = time.time() + self.WRITE_WAIT_MS / 1000.0
        while True:
            for sel in target_article_selectors(x_post_id):
                try:
                    loc = self._page.locator(sel)
                    if loc.count() > 0:
                        return loc.first
                except Exception:
                    continue
            if time.time() >= deadline:
                raise SelectorMiss("target_article", self._capture("target_miss"))
            time.sleep(0.5)

    def find_reply(self, x_post_id: str, text: str) -> str:
        """Our own reply to this post if it is already there, else "".

        Used to verify a send, and before sending so a retry cannot post the
        same thing twice.
        """
        op = (self.s.operator_handle or "").lstrip("@").lower()
        try:
            arts, _ = self._find_all("tweet", wait_ms=self.WRITE_WAIT_MS)
        except SelectorMiss:
            return ""
        for i in range(min(arts.count(), 30)):
            art = arts.nth(i)
            try:
                href = art.locator('a[href*="/' + op + '/status/"]').first.get_attribute("href")
            except Exception:
                continue
            rid = status_id_from_href(href or "")
            if not rid or rid == x_post_id:
                continue                      # that is the post we replied to
            try:
                body = art.locator(self.reg.get("tweet_text").primary).first.inner_text()
            except Exception:
                continue
            if texts_match(text, body):
                return rid
        return ""

    def exists(self, idempotency_key: str, text: str) -> bool:
        """Kept for the reconcile probe; the real work happens in find_reply."""
        return False

    def reply(self, parent_x_id: str, text: str, permalink: str = "",
              author: str = "") -> str:
        """Reply to one post and return the id of the reply actually made.

        Raises rather than returning "": an empty id used to be accepted as
        success, so a reply that never posted was recorded as sent.
        """
        self._open_post(parent_x_id, permalink, author)

        already = self.find_reply(parent_x_id, text)
        if already:
            log.info("reply already present on %s, not posting again", parent_x_id)
            return already

        target = self._target_article(parent_x_id)
        self._human_scroll(1)                    # read replies first (E-11)

        # On a status page X renders the reply box inline, bound to the focal
        # post. Using it avoids clicking a reply button on the wrong article.
        scope = self._page
        composer = self._composer_in(scope)
        if composer is None:
            self._human_move_click(target.locator(
                self.reg.get("reply_button").primary).first)
            time.sleep(random.uniform(0.5, 1.2))
            dialog = self._page.locator('[role="dialog"]')
            scope = dialog.first if dialog.count() else self._page
            # A restricted post opens "Who can reply?" here instead of a
            # composer. Nothing to retry; the author closed the door.
            try:
                if dialog.count() and "can reply" in dialog.first.inner_text():
                    raise PostUnavailable(parent_x_id, self._capture("reply_restricted"))
            except PostUnavailable:
                raise
            except Exception:
                pass
            composer = self._composer_in(scope, wait=True)
        if composer is None:
            raise SelectorMiss("composer", self._capture("composer_miss"))

        self._human_type(composer, text)

        # Check the box before sending. A mistyped reply is recoverable here
        # and not afterwards.
        try:
            typed = composer.inner_text()
        except Exception:
            typed = text
        if not texts_match(text, typed):
            raise SendRejected("composer text does not match the draft",
                               self._capture("composer_mismatch"))

        self._human_move_click(self._send_button_in(scope))
        time.sleep(random.uniform(2.0, 4.0))

        # Verify against a fresh load. An optimistic article plus a "Retry"
        # toast looks identical to success in the live DOM, and that is exactly
        # the false positive that made failed sends look sent.
        self._open_post(parent_x_id, permalink, author)
        rid = self.find_reply(parent_x_id, text)
        if rid:
            return rid

        # Deep threads hide new replies behind "show more"; check our own
        # timeline before giving up.
        try:
            self._goto("https://x.com/" + self.s.operator_handle + "/with_replies")
            rid = self.find_reply(parent_x_id, text)
            if rid:
                return rid
        except Exception:
            pass
        raise SendNotConfirmed(parent_x_id, self._capture("send_unconfirmed"))

    def _composer_in(self, scope, wait: bool = False):
        entry = self.reg.get("composer")
        deadline = time.time() + (self.WRITE_WAIT_MS / 1000.0 if wait else 0)
        while True:
            for sel in entry.all():
                try:
                    loc = scope.locator(sel)
                    if loc.count() > 0 and loc.first.is_visible():
                        return loc.first
                except Exception:
                    continue
            if time.time() >= deadline:
                return None
            time.sleep(0.5)

    def _send_button_in(self, scope):
        """The send button of the composer we are actually in.

        The inline reply box uses tweetButtonInline, but the old lookup took
        the first selector matching anywhere on the page, so a tweetButton
        elsewhere in the DOM could win.
        """
        for sel in self.reg.get("reply_post_button").all():
            try:
                loc = scope.locator(sel)
                for i in range(loc.count()):
                    btn = loc.nth(i)
                    if btn.is_visible() and btn.is_enabled():
                        return btn
            except Exception:
                continue
        raise SelectorMiss("reply_post_button", self._capture("send_button_miss"))

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
