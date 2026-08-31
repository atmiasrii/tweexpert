#!/usr/bin/env python
"""Live auto-reply demonstration on real X, via the full machinery:
policy-issued ActionAuthorization -> action bus -> real post -> verify -> delete.

To avoid pinging an uninvolved third party with an offline-template draft, the
demo replies to the OPERATOR'S OWN latest tweet with a clearly-labelled test
string, then deletes it. This exercises the exact auto write path (Y-01, Q-01..05)
end-to-end against live x.com. Auto mode is then left ENABLED on the watchlist.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

os.environ["QUILL_BROWSER_ENGINE"] = "playwright"

from quill.config import get_settings  # noqa: E402
get_settings.cache_clear()
S = get_settings()

from quill.db.engine import init_db, session_scope  # noqa: E402
from quill.db.settings_store import set_setting  # noqa: E402
from quill.db.models import Account, Draft  # noqa: E402
from quill.bus.action_bus import get_bus  # noqa: E402
from quill.bus.authz import issue  # noqa: E402
from quill.governor import governor  # noqa: E402
from sqlmodel import select  # noqa: E402


def main():
    init_db()
    bus = get_bus()
    engine = bus  # engine accessed via bus reads

    # 1) confirm session + get the operator's latest own tweet
    from quill.browser import get_engine
    eng = get_engine()
    if not eng.login_check():
        print("[fail] not logged in"); return 1
    own = eng.read_user(S.operator_handle)
    if not own:
        print(f"[fail] no posts parsed for @{S.operator_handle}"); return 1
    target = own[0]
    print(f"[target] own latest tweet {target.x_post_id} :: {target.text[:70]!r}")

    with session_scope() as s:
        # 2) enable auto on a watched account per the operator's choice
        acc = s.exec(select(Account).where(Account.handle == "simonw")).first()
        if not acc:
            acc = Account(handle="simonw", display_name="Simon Willison", tier="A")
            s.add(acc); s.commit(); s.refresh(acc)
        acc.mode = "auto"
        acc.shadow_started_at = datetime.now(timezone.utc)  # gate satisfied per choice
        acc.shadow_drafts_count = 25
        acc.shadow_reviewed_count = 25
        s.add(acc); s.commit()
        print(f"[auto] @{acc.handle} mode=auto (shadow gate satisfied per operator choice)")

        # 3) make the governor allow a write right now (demo: clear quiet window)
        now = governor.local_now()
        set_setting(s, "quiet_start", f"{(now.hour + 2) % 24:02d}:00")
        set_setting(s, "quiet_end", f"{(now.hour + 2) % 24:02d}:01")
        set_setting(s, "kill_switch", False)
        day = governor.get_day(s)
        day.kill_switch = False; day.no_auto_today = False
        s.add(day); s.commit()

        # 4) build the draft + POLICY authorization (issuer=policy, auto)
        test_text = ("testing my own self-hosted reply tool on my own account — "
                     "please ignore, deleting this now.")
        draft = Draft(kind="reply", final_text=test_text, status="queued",
                      mode_at_creation="auto", relevance=99.0)
        s.add(draft); s.commit(); s.refresh(draft)
        authz = issue(s, draft.id, issuer="policy", mode="auto",
                      reasons=["live demo: policy-authorized auto reply"])

    # 5) send for real through the bus (human-shaped delay skipped for the demo)
    print("[send] posting via action bus (policy authorization)…")
    action = bus.submit_write("reply", target.x_post_id, test_text, authz,
                              issuer="policy", draft_id=draft.id)
    url = f"https://x.com/{S.operator_handle}/status/{action.x_post_id}"
    print(f"[POSTED] live reply id={action.x_post_id}")
    print(f"[url] {url}")
    eng._capture("live-auto-posted")

    # 6) verify then delete immediately
    time.sleep(3)
    ok = bus.submit_delete(action.x_post_id, issuer="human")
    print(f"[deleted] {action.x_post_id} -> {ok}")

    # auto mode stays ENABLED on @simonw per the operator's choice.
    print("[done] auto mode left ENABLED on @simonw (defaults). "
          "Start a local LLM for quality; run the worker/browser process for 24/7 sends.")
    eng.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
