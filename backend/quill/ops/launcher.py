"""Live-mode launcher (S21).

One control turns Quill on: it starts the two supervised processes that do the
unattended work and reports, in plain terms, everything still standing between
here and real replies going out.

Process topology on a single box is the same one docker uses (A-02):

  api            this process. Owns no browser. While live it enqueues writes.
  worker         scheduler, backups, watchdog, reconciliation. No engine.
  browser        the SOLE owner of the Playwright session: drains write intents,
                 polls timelines, runs the canary, sends what is due.

Exactly one process may touch the Chromium profile directory, so the worker is
started with QUILL_WORKER_RUNS_ENGINE=0 and the browser process owns the engine.

What this deliberately does NOT do: promote accounts to auto. The shadow period
is the safeguard the whole design rests on (Y-03); the launcher reports which
accounts will only draft, and leaves the decision on the Watchlist tab where it
carries a confirmation.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from ..config import get_settings
from ..db.models import Account, Draft, Heartbeat
from ..db.settings_store import get_setting, set_setting
from ..defaults import WATCHDOG_STALE_S
from ..logging_setup import get_logger

log = get_logger("quill.launcher")

LIVE_KEY = "live_mode"
PIDS_KEY = "live_pids"

# The processes the launcher owns, and the env each one needs.
PROCS: dict[str, dict[str, str]] = {
    # Scheduler only. Must not open a browser: the profile takes one owner.
    "worker": {"QUILL_WORKER_RUNS_ENGINE": "0"},
    # The engine owner.
    "browser": {},
}
MODULES = {"worker": "quill.worker", "browser": "quill.browser_proc"}


@dataclass
class Check:
    id: str
    label: str
    state: str          # "ok" | "blocked" | "warn"
    detail: str
    action: str = ""    # a hint the dashboard turns into a button


# -- live flag ---------------------------------------------------------

def is_live(session: Session) -> bool:
    return bool(get_setting(session, LIVE_KEY, False))


def writes_deferred(session: Session) -> bool:
    """True when some other process owns the engine and this one must enqueue.

    Either the process was configured that way, or the launcher has handed the
    engine to the browser process.
    """
    return bool(get_settings().defer_writes) or is_live(session)


# -- process control ---------------------------------------------------

def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True,
        ).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _pids(session: Session) -> dict[str, int]:
    raw = get_setting(session, PIDS_KEY, {}) or {}
    return {k: int(v) for k, v in raw.items() if str(v).isdigit()}


def running(session: Session) -> dict[str, bool]:
    pids = _pids(session)
    return {name: _alive(pids.get(name, 0)) for name in PROCS}


def _spawn(name: str, engine: str) -> int:
    s = get_settings()
    env = dict(os.environ)
    env["QUILL_BROWSER_ENGINE"] = engine
    env.update(PROCS[name])
    # The worker and browser are started as modules from the backend package
    # root, exactly as `make worker` would.
    cwd = Path(__file__).resolve().parents[2]
    log_path = s.data_dir / f"{name}.out"
    s.data_dir.mkdir(parents=True, exist_ok=True)
    out = open(log_path, "ab", buffering=0)
    kwargs: dict = {"cwd": str(cwd), "env": env, "stdout": out, "stderr": out}
    if os.name == "nt":
        # Detach so the child survives an API reload and never inherits the
        # console's Ctrl-C.
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen([sys.executable, "-m", MODULES[name]], **kwargs)
    log.info("started %s pid=%s engine=%s", name, proc.pid, engine)
    return proc.pid


def _terminate(pid: int) -> None:
    if not _alive(pid):
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True)
        else:
            os.kill(pid, 15)
    except Exception as e:      # a process that is already gone is a success
        log.warning("terminate %s: %s", pid, e)


def start(session: Session, engine: str = "playwright") -> dict:
    """Start live mode. Idempotent: already-running processes are left alone."""
    pids = _pids(session)
    alive = running(session)
    started = []
    for name in PROCS:
        if alive.get(name):
            continue
        pids[name] = _spawn(name, engine)
        started.append(name)

    set_setting(session, PIDS_KEY, pids)
    set_setting(session, LIVE_KEY, True)
    set_setting(session, "live_started_at", datetime.now(timezone.utc).isoformat())
    set_setting(session, "live_engine", engine)
    log.info("live mode ON (engine=%s, started=%s)", engine, started)
    return {"live": True, "started": started, "pids": pids, "engine": engine}


def stop(session: Session) -> dict:
    """Stop live mode. Drafts and the queue survive; nothing is deleted."""
    pids = _pids(session)
    for name, pid in pids.items():
        _terminate(pid)
    set_setting(session, PIDS_KEY, {})
    set_setting(session, LIVE_KEY, False)
    log.info("live mode OFF (stopped %s)", list(pids))
    return {"live": False, "stopped": list(pids)}


def open_login(session: Session) -> dict:
    """Open Quill's own browser at the X login page for a hand sign-in (E-02).

    Quill never handles the password. The browser process is stopped first: the
    persistent profile takes exactly one owner, and the login window must be it.
    """
    pids = _pids(session)
    if pids.get("browser") and _alive(pids["browser"]):
        _terminate(pids["browser"])
        pids.pop("browser", None)
        set_setting(session, PIDS_KEY, pids)
        time.sleep(1.5)                 # let the profile lock clear

    script = Path(__file__).resolve().parents[3] / "scripts" / "manual_login.py"
    if not script.exists():
        raise FileNotFoundError(f"login helper missing: {script}")

    s = get_settings()
    env = dict(os.environ)
    env["QUILL_BROWSER_ENGINE"] = "playwright"
    env["QUILL_X_HANDLE"] = s.operator_handle
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    s.data_dir.mkdir(parents=True, exist_ok=True)
    out = open(s.data_dir / "login.out", "ab", buffering=0)
    kwargs: dict = {"env": env, "stdout": out, "stderr": out}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen([sys.executable, str(script)], **kwargs)

    pids["login"] = proc.pid
    set_setting(session, PIDS_KEY, pids)
    log.info("login window opened pid=%s handle=%s", proc.pid, s.operator_handle)
    return {
        "opened": True,
        "pid": proc.pid,
        "handle": s.operator_handle,
        "note": ("A browser window is opening on this machine. Sign in by hand - "
                 "Quill never sees your password. It waits up to five minutes."),
    }


# -- readiness ---------------------------------------------------------

def _heartbeat_fresh(session: Session, process: str) -> bool:
    hb = session.get(Heartbeat, process)
    if hb is None:
        return False
    at = hb.at.replace(tzinfo=timezone.utc) if hb.at.tzinfo is None else hb.at
    return (datetime.now(timezone.utc) - at).total_seconds() <= WATCHDOG_STALE_S


def session_logged_in() -> tuple[bool, str]:
    """Does Quill's own browser profile hold a live X session?

    Checked without opening a browser: the API process must never take the
    profile lock away from the browser process. The profile directory having
    real cookie state is the strongest signal available from here.
    """
    s = get_settings()
    profile = Path(s.profile_dir)
    if not profile.exists():
        return False, "Quill has no browser profile yet"
    cookies = profile / "Default" / "Network" / "Cookies"
    if not cookies.exists():
        cookies = profile / "Default" / "Cookies"
    if not cookies.exists() or cookies.stat().st_size < 4096:
        return False, "no saved X session in the profile"
    age_days = (time.time() - cookies.stat().st_mtime) / 86400
    if age_days > 30:
        return False, f"session last touched {int(age_days)} days ago"
    return True, "session saved in Quill's browser profile"


def readiness(session: Session) -> list[Check]:
    s = get_settings()
    live = is_live(session)
    procs = running(session)
    checks: list[Check] = []

    # 1. Which X are we talking to?
    engine = get_setting(session, "live_engine", s.browser_engine)
    if live and engine == "playwright":
        checks.append(Check("engine", "Connected to real X", "ok",
                            "The browser process drives your logged-in profile."))
    else:
        checks.append(Check(
            "engine", "Not connected to X yet", "blocked",
            "Quill is running on offline fixtures - nothing it does is real. "
            "Starting connects it to your logged-in browser profile."))

    # 2. The one thing only a human can do (E-02).
    ok, why = session_logged_in()
    checks.append(Check(
        "session", "Signed in to X", "ok" if ok else "blocked", why,
        "" if ok else "login"))

    # 3. Anything to read.
    accounts = session.exec(select(Account)).all()
    if not accounts:
        checks.append(Check("watchlist", "Accounts to watch", "blocked",
                            "No accounts watched - Quill has nothing to read.",
                            "watchlist"))
    else:
        checks.append(Check("watchlist", "Accounts to watch", "ok",
                            f"{len(accounts)} watched"))

    # 4. Will anything actually be sent without you?
    auto = [a for a in accounts if a.mode == "auto"]
    drafting_only = [a for a in accounts if a.mode != "auto"]
    if accounts and not auto:
        checks.append(Check(
            "autonomy", "Replying on its own", "warn",
            f"{len(drafting_only)} account(s) will draft for your approval, not send. "
            "Auto unlocks per account once its shadow period is served.",
            "watchlist"))
    elif auto:
        checks.append(Check(
            "autonomy", "Replying on its own", "ok",
            f"{len(auto)} account(s) on auto; {len(drafting_only)} drafting only."))

    # 5. Voice quality. Not a blocker - the pipeline runs without a model.
    if not s.llm_available:
        checks.append(Check(
            "llm", "Local language model", "warn",
            "No model reachable, so drafts come from the offline template "
            "generator and the safety gate refuses many of them. "
            f"Point QUILL_LLM_BASE_URL at Ollama or vLLM ({s.llm_base_url}).",
            ""))
    else:
        checks.append(Check("llm", "Local language model", "ok", s.draft_model))

    # 6. Are the processes actually up?
    if live:
        for name in ("worker", "browser"):
            alive_now = procs.get(name)
            beating = _heartbeat_fresh(session, name)
            if alive_now and beating:
                state, detail, action = "ok", "running", ""
            elif alive_now:
                # Up, but has not reported in yet. Starting, not broken.
                state, detail, action = "warn", "starting", ""
            else:
                state, detail, action = "blocked", "not running", "start"
            checks.append(Check(f"proc_{name}", f"{name.capitalize()} process",
                                state, detail, action))

    # 7. The stop controls, surfaced as state rather than hidden in the header.
    if get_setting(session, "kill_switch", False):
        checks.append(Check("kill", "Kill switch", "blocked",
                            "Engaged - every write is refused.", "release_kill"))

    return checks


def status(session: Session) -> dict:
    checks = readiness(session)
    blocking = [c.id for c in checks if c.state == "blocked"]
    queued = len(session.exec(select(Draft).where(Draft.status == "queued")).all())
    started_at = get_setting(session, "live_started_at", None)
    return {
        "live": is_live(session),
        # The dashboard renders true-to-X previews and needs the handle.
        "operator": get_settings().operator_handle,
        "engine": get_setting(session, "live_engine", get_settings().browser_engine),
        "processes": running(session),
        "started_at": started_at,
        "queued_drafts": queued,
        "checks": [asdict(c) for c in checks],
        "blocking": blocking,
        # "start" is always offered: the point of one button is that it does
        # everything it can and then tells you what is left.
        "ready": not blocking,
    }
