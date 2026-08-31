"""Browser process (§21, A-02). The sole owner of the Playwright session.
Drains pending write intents, runs engine-touching schedules, restarts Chromium
on a schedule to bound memory (O-06). Heartbeats every minute (O-02)."""
from __future__ import annotations

import os
import signal
import time

from apscheduler.schedulers.background import BackgroundScheduler

from .bus.action_bus import get_bus
from .config import get_settings
from .db.engine import init_db, session_scope
from .defaults import (CHROMIUM_RESTART_HOUR, HEARTBEAT_INTERVAL_S,
                       PROC_HEARTBEAT_INTERVAL_S)
from .logging_setup import get_logger, setup_logging
from .ops import health as health_mod
from .ops import session_guard

log = get_logger("quill.browser_proc")


def _hb():
    with session_scope() as s:
        health_mod.beat(s, "browser")


def _drain():
    get_bus().drain_pending(limit=5)


def _restart_chromium():
    """O-06: restart Chromium during quiet hours, preserving the profile."""
    from .browser import get_engine
    eng = get_engine()
    if hasattr(eng, "close"):
        try:
            eng.close()
        except Exception:
            pass
    get_engine(reset=True)                    # re-open persistent context
    log.info("chromium restarted (profile preserved)")


def main():
    s = get_settings()
    setup_logging(s.data_dir)
    init_db()
    log.info("browser process starting (engine=%s)", s.browser_engine)

    # verify session before anything writes (O-03)
    with session_scope() as sess:
        try:
            session_guard.session_heartbeat(sess)
        except Exception as e:
            log.warning("initial session check: %s", e)

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(_hb, "interval", seconds=PROC_HEARTBEAT_INTERVAL_S, id="hb")
    scheduler.add_job(_drain, "interval", seconds=15, id="drain")

    def heartbeat():
        with session_scope() as sess:
            session_guard.session_heartbeat(sess)

    def canary():
        with session_scope() as sess:
            session_guard.run_canary(sess)

    def watch():
        from .pipeline import watcher
        with session_scope() as sess:
            watcher.watch_all(sess)

    def presence():
        from .presence import simulator
        with session_scope() as sess:
            simulator.run_presence(sess)

    def sends():
        from .pipeline import pipeline as pl, schedule as sched
        with session_scope() as sess:
            pl.send_due_auto(sess)
            sched.send_due_scheduled(sess)

    scheduler.add_job(heartbeat, "interval", seconds=HEARTBEAT_INTERVAL_S, id="session_hb")
    scheduler.add_job(canary, "interval", minutes=30, id="canary")
    scheduler.add_job(watch, "interval", minutes=3, id="watch")
    scheduler.add_job(presence, "interval", minutes=17, id="presence")
    scheduler.add_job(sends, "interval", seconds=30, id="sends")
    scheduler.add_job(_restart_chromium, "cron", hour=CHROMIUM_RESTART_HOUR, id="restart")
    scheduler.start()

    stop = {"v": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("v", True))
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("v", True))
    try:
        while not stop["v"]:
            time.sleep(1)
    finally:
        scheduler.shutdown(wait=False)
        log.info("browser process stopped")


if __name__ == "__main__":
    main()
