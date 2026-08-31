#!/usr/bin/env python
"""Live read-path validation against real x.com using Quill's logged-in profile.
Runs login_check, the selector canary (E-07), and parses a real profile + the
home timeline. Screenshots to data/debug. No writes."""
from __future__ import annotations

import os

os.environ["QUILL_BROWSER_ENGINE"] = "playwright"

from quill.config import get_settings  # noqa: E402
get_settings.cache_clear()
from quill.browser.playwright_engine import PlaywrightEngine  # noqa: E402
from quill.browser.base import SessionDead, ChallengeDetected  # noqa: E402

WATCH = os.environ.get("QUILL_WATCH", "simonw")


def main():
    eng = PlaywrightEngine()
    try:
        # 1) session
        try:
            ok = eng.login_check()
            print(f"[login_check] logged_in={ok}")
        except (SessionDead, ChallengeDetected) as e:
            eng._capture("live-session-fail")
            print(f"[login_check] FAILED: {e}")
            return 1

        # 2) canary — do the live selectors still resolve? (E-07)
        can = eng.canary()
        print(f"[canary] ok={can.ok} missing={can.missing}")

        # 3) read a real profile
        posts = eng.read_user(WATCH)
        print(f"[read_user @{WATCH}] parsed {len(posts)} posts")
        for p in posts[:3]:
            print(f"   - {p.x_post_id} :: {p.text[:80]!r}")
        eng._capture("live-read-profile")

        # 4) read the home timeline (presence path)
        home = eng.presence("home")
        print(f"[presence home] parsed {len(home)} posts")
        eng._capture("live-read-home")
        return 0
    finally:
        eng.close()


if __name__ == "__main__":
    raise SystemExit(main())
