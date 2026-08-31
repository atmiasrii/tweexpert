#!/usr/bin/env python
"""Password-free login (E-02). Opens Quill's OWN persistent-profile Chromium to
the X login page, pre-fills only the (non-secret) handle, and waits for the
operator to finish sign-in BY HAND in the visible window. Quill never handles
the password. Polls until logged in, then exits 0 (the session persists in the
profile dir for the rest of the T-00 test).
"""
from __future__ import annotations

import os
import time

os.environ["QUILL_BROWSER_ENGINE"] = "playwright"

from quill.config import get_settings  # noqa: E402
get_settings.cache_clear()
from quill.browser.playwright_engine import PlaywrightEngine  # noqa: E402

HANDLE = os.environ.get("QUILL_X_HANDLE", "barryallendgx")


def logged_in(page) -> bool:
    for sel in ['[data-testid="SideNav_AccountSwitcher_Button"]',
                '[data-testid="AppTabBar_Home_Link"]',
                'a[aria-label="Profile"]']:
        try:
            if page.locator(sel).count():
                return True
        except Exception:
            pass
    return False


def main():
    eng = PlaywrightEngine()
    page = eng._page
    try:
        page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)
        if logged_in(page):
            print("[ok] already logged in"); return 0
        # pre-fill the handle only (not secret) to save the operator a step
        try:
            fld = page.locator('div[role="dialog"] input[name="text"]').first
            if fld.count() and fld.is_visible():
                fld.click(); fld.fill(HANDLE)
        except Exception:
            pass
        eng._capture("manual-login-open")
        print(f"[action needed] A Chrome window is open. Finish signing in as "
              f"@{HANDLE} BY HAND (password + any 2FA/captcha). Waiting up to 5 min…",
              flush=True)
        deadline = time.time() + 300
        while time.time() < deadline:
            if logged_in(page):
                eng._capture("manual-login-home")
                print("[ok] LOGGED IN — session saved to the profile.")
                return 0
            time.sleep(3)
        eng._capture("manual-login-timeout")
        print("[timeout] not logged in within 5 min.")
        return 3
    finally:
        eng.close()


if __name__ == "__main__":
    raise SystemExit(main())
