#!/usr/bin/env python
"""Live login harness for the T-00 test. Drives Quill's OWN persistent-profile
Chromium (so Quill later posts as this session). Reads creds from env
(QUILL_X_HANDLE / QUILL_X_PASSWORD) — never written to disk. Screenshots every
step to data/debug so we can see where it is. On any challenge/2FA it stops and
reports, leaving the headed window open for the operator to finish by hand (E-02).
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ["QUILL_BROWSER_ENGINE"] = "playwright"

from quill.config import get_settings  # noqa: E402
get_settings.cache_clear()
from quill.browser.playwright_engine import PlaywrightEngine  # noqa: E402


def shot(eng, tag):
    p = eng._capture(tag)
    print(f"[shot] {tag} -> {p}", flush=True)


def find_first(page, selectors, timeout=8000):
    from playwright.sync_api import TimeoutError as PWTimeout
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if loc.count() and loc.first.is_visible():
                    return loc.first
            except Exception:
                pass
        time.sleep(0.4)
    return None


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


def challenge_present(page) -> str:
    fp = {
        "arkose/captcha": ['iframe[src*="arkoselabs"]', 'iframe[title*="challenge"]'],
        "2fa/verification": ['input[data-testid="ocfEnterTextTextInput"]',
                             'input[name="text"][data-testid="ocfEnterTextTextInput"]'],
        "unusual_activity": ['text=unusual', 'text=Verify'],
    }
    for kind, sels in fp.items():
        for sel in sels:
            try:
                if page.locator(sel).count():
                    return kind
            except Exception:
                pass
    return ""


def main():
    handle = os.environ.get("QUILL_X_HANDLE", "")
    password = os.environ.get("QUILL_X_PASSWORD", "")
    if not handle or not password:
        print("set QUILL_X_HANDLE and QUILL_X_PASSWORD", file=sys.stderr)
        return 2

    eng = PlaywrightEngine()
    page = eng._page

    def dlg(sel):
        # scope inside the login modal to avoid the faded background page's fields
        return f'div[role="dialog"] {sel}'

    try:
        page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)
        shot(eng, "login-01-open")

        if logged_in(page):
            print("[ok] already logged in (profile had a session)")
            return 0

        # step 1: username / email
        user_in = find_first(page, [dlg('input[autocomplete="username"]'),
                                    dlg('input[name="text"]'),
                                    'input[autocomplete="username"]'])
        if user_in:
            user_in.click()
            user_in.fill(handle)
            time.sleep(0.6)
            adv = find_first(page, [dlg('button:has-text("Next")'),
                                    dlg('button:has-text("Continue")'),
                                    dlg('div[role="button"]:has-text("Next")'),
                                    dlg('div[role="button"]:has-text("Continue")')], 6000)
            if adv:
                adv.click()
            time.sleep(3)
            shot(eng, "login-03-after-username")

        # step 2: password (may be preceded by a verify-identity interstitial)
        pw_in = find_first(page, [dlg('input[name="password"]'),
                                  dlg('input[type="password"]'),
                                  'input[name="password"]'], 12000)
        if pw_in:
            pw_in.click()
            pw_in.fill(password)
            time.sleep(0.6)
            login_btn = find_first(page, ['button[data-testid="LoginForm_Login_Button"]',
                                          dlg('button:has-text("Log in")'),
                                          dlg('div[role="button"]:has-text("Log in")')], 6000)
            if login_btn:
                login_btn.click()
            time.sleep(4)
            shot(eng, "login-05-after-password")
        else:
            shot(eng, "login-04-verify-step")
            print("[note] no password field yet — X inserted a verify step "
                  "(phone/username/2FA). Complete it in the OPEN WINDOW.")

        # poll for success up to ~3 min so any challenge/2FA can be solved by hand
        deadline = time.time() + 170
        last_ch = ""
        while time.time() < deadline:
            if logged_in(page):
                shot(eng, "login-06-home")
                print("[ok] LOGGED IN — profile now has a live session")
                return 0
            ch = challenge_present(page)
            if ch and ch != last_ch:
                last_ch = ch
                shot(eng, f"login-challenge-{ch}")
                print(f"[waiting] challenge visible: {ch} — solve it in the open window", flush=True)
            time.sleep(3)
        shot(eng, "login-06-timeout")
        print("[timeout] login not confirmed in 3min — see screenshot / finish in window")
        return 3
    finally:
        eng.close()


if __name__ == "__main__":
    raise SystemExit(main())
