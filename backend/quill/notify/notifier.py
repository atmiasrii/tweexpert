"""Remote approval + alerts (§16).

Push via ntfy topic and/or Telegram bot (K-01). Works without either, but
unattended operation is much worse without them. Alert-level notifications
(K-03) are always sent regardless of settings. Notification actions carry
single-use, expiring, draft-bound tokens (K-04). Approving from a notification
issues a human authorization through the SAME code path as a dashboard tap
(K-02) — see api/routes/drafts.py.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from ..config import get_settings
from ..logging_setup import get_logger
from ..security import make_action_token
from ..defaults import NOTIFY_TOKEN_TTL_S

log = get_logger("quill.notify")

ALERT_KINDS = {
    "session_dead", "challenge_detected", "canary_failed",
    "auto_disabled", "publish_failures", "worker_down",
}


@dataclass
class SentNotification:
    at: datetime
    kind: str
    title: str
    body: str
    alert: bool
    draft_id: int | None = None


# In-memory ring buffer so the dashboard and tests can inspect what fired.
SENT: list[SentNotification] = []
_lock = threading.Lock()


def _record(n: SentNotification):
    with _lock:
        SENT.append(n)
        del SENT[:-500]


def recent(n: int = 100) -> list[dict]:
    with _lock:
        return [s.__dict__ | {"at": s.at.isoformat()} for s in SENT[-n:]]


def clear() -> None:
    with _lock:
        SENT.clear()


def notify(kind: str, title: str, body: str, draft_id: int | None = None,
           actions: list[dict] | None = None) -> None:
    s = get_settings()
    alert = kind in ALERT_KINDS
    _record(SentNotification(datetime.now(timezone.utc), kind, title, body, alert, draft_id))
    # ntfy
    if s.ntfy_topic:
        try:
            headers = {"Title": title, "Tags": "warning" if alert else "speech_balloon"}
            if actions:
                headers["Actions"] = "; ".join(
                    f"http, {a['label']}, {a['url']}" for a in actions)
            httpx.post(f"{s.ntfy_base_url}/{s.ntfy_topic}", data=body.encode(),
                       headers=headers, timeout=10)
        except Exception as e:
            log.warning("ntfy send failed: %s", e)
    # telegram
    if s.telegram_bot_token and s.telegram_chat_id:
        try:
            httpx.post(
                f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                json={"chat_id": s.telegram_chat_id, "text": f"{title}\n{body}"},
                timeout=10)
        except Exception as e:
            log.warning("telegram send failed: %s", e)
    log.info("notify", extra={"kind": kind, "alert": alert, "title": title})


def alert(kind: str, message: str) -> None:
    """Alert-level notification — always sent (K-03)."""
    notify(kind, f"Quill alert: {kind}", message)


def draft_approval(draft_id: int, author: str, text: str) -> None:
    """Assisted-mode push with inline approve/skip actions (K-02/K-04)."""
    s = get_settings()
    token = make_action_token(s.secret_key, draft_id, NOTIFY_TOKEN_TTL_S)
    base = s.public_base_url
    actions = [
        {"label": "Approve",
         "url": f"{base}/api/notify/approve?draft_id={draft_id}&token={token}"},
        {"label": "Skip",
         "url": f"{base}/api/notify/skip?draft_id={draft_id}&token={token}"},
    ]
    notify("draft_ready", f"Draft for @{author}", text, draft_id=draft_id,
           actions=actions)
