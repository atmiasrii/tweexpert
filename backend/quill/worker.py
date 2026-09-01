"""Worker process (§21). Scheduler + pipeline. Supervised; restarts clean,
re-reading state from the DB. Heartbeats every minute (O-02). In a single-box
dev run it also drives the engine jobs; in docker the browser service owns
those (QUILL_WORKER_RUNS_ENGINE=0)."""
from __future__ import annotations

import os
import signal
import time

from apscheduler.schedulers.background import BackgroundScheduler

from .config import get_settings
from .db.engine import init_db, session_scope
from .defaults import (HEARTBEAT_INTERVAL_S, PROC_HEARTBEAT_INTERVAL_S)
from .logging_setup import get_logger, setup_logging
from .ops import backup as backup_mod
from .ops import health as health_mod
from .ops.reconcile import startup_reconcile

log = get_logger("quill.worker")

RUNS_ENGINE = os.environ.get("QUILL_WORKER_RUNS_ENGINE", "1") == "1"


def _hb():
    with session_scope() as s:
        health_mod.beat(s, "worker")


def _watchdog():
    with session_scope() as s:
        health_mod.watchdog(s)


def _expiry_tick():
    with session_scope() as s:
        startup_reconcile(s)


def _degradation():
    """Graceful degradation checks (O-05)."""
    import shutil
    s = get_settings()
    total, used, free = shutil.disk_usage(s.data_dir)
    if free < 200 * 1024 * 1024:            # < 200MB free
        from .db.settings_store import set_setting
        with session_scope() as sess:
            set_setting(sess, "pause_presence_analytics", True)
        log.warning("low disk: pausing presence + analytics first")


def _engine_jobs(scheduler: BackgroundScheduler):
    from .ops import session_guard
    from .pipeline import discovery, pipeline as pl, watcher
    from .presence import simulator

    def heartbeat():
        with session_scope() as s:
            session_guard.session_heartbeat(s)

    def canary():
        with session_scope() as s:
            session_guard.run_canary(s)

    def watch():
        with session_scope() as s:
            watcher.watch_all(s)

    def presence():
        with session_scope() as s:
            simulator.run_presence(s)

    def sends():
        with session_scope() as s:
            pl.send_due_auto(s)
            from .pipeline import schedule as sched
            sched.send_due_scheduled(s)

    def foryou():
        from .pipeline import foryou_auto
        with session_scope() as s:
            foryou_auto.tick(s)

    def searches():
        with session_scope() as s:
            discovery.run_saved_searches(s)
            discovery.ingest_notifications(s)       # V-04

    def analytics():
        with session_scope() as s:
            from .ops.analytics import sample_own_posts
            sample_own_posts(s)

    scheduler.add_job(heartbeat, "interval", seconds=HEARTBEAT_INTERVAL_S, id="session_hb")
    scheduler.add_job(canary, "interval", minutes=30, id="canary")
    scheduler.add_job(watch, "interval", minutes=3, id="watch")
    scheduler.add_job(presence, "interval", minutes=17, id="presence")
    scheduler.add_job(sends, "interval", seconds=30, id="sends")
    scheduler.add_job(searches, "interval", minutes=5, id="searches")
    scheduler.add_job(foryou, "interval", minutes=1, id="foryou")   # checks interval itself
    scheduler.add_job(analytics, "interval", minutes=20, id="analytics")


def main():
    s = get_settings()
    setup_logging(s.data_dir)
    init_db()
    with session_scope() as sess:
        startup_reconcile(sess)
    log.info("worker starting (runs_engine=%s)", RUNS_ENGINE)

    _hb()                                  # first beat now, not in a minute
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(_hb, "interval", seconds=PROC_HEARTBEAT_INTERVAL_S, id="hb")
    scheduler.add_job(_watchdog, "interval", minutes=1, id="watchdog")
    scheduler.add_job(_expiry_tick, "interval", minutes=5, id="expiry")
    scheduler.add_job(_degradation, "interval", minutes=5, id="degradation")
    scheduler.add_job(backup_mod.run_backup, "cron", hour=4, minute=15, id="backup")
    if RUNS_ENGINE:
        _engine_jobs(scheduler)
    scheduler.start()

    stop = {"v": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("v", True))
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("v", True))
    try:
        while not stop["v"]:
            time.sleep(1)
    finally:
        scheduler.shutdown(wait=False)
        log.info("worker stopped")


if __name__ == "__main__":
    main()
