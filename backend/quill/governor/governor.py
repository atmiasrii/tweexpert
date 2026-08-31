"""Governor (§11). Cannot be bypassed (G-05). Refuses past limits with a
stated reason; never silently drops (S-01, T-07)."""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from ..config import get_settings
from ..db.models import Action, GovernorDay
from ..db.settings_store import get_setting
from ..defaults import (BURST_MAX_WRITES, BURST_WINDOW_S, CAP_POSTS,
                        CAP_REPLIES_ASSISTED, CAP_REPLIES_AUTO, CAP_THREADS,
                        AUTO_DELAY_MAX_S, AUTO_DELAY_MIN_S, MIN_WRITE_SPACING_S,
                        QUIET_DRIFT_MIN, QUIET_END, QUIET_START,
                        WRITE_JITTER_FRAC)


class GovernorRefusal(Exception):
    """Raised with a distinct, stated reason (S-01, T-07)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class GovernorState:
    date: str
    mode_usage: dict
    kill_switch: bool
    quiet_now: bool
    next_slot: datetime | None
    session_ok: bool


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().operator_timezone)


def local_now() -> datetime:
    return datetime.now(_tz())


def _today_key() -> str:
    return local_now().strftime("%Y-%m-%d")


def get_day(session: Session) -> GovernorDay:
    key = _today_key()
    day = session.get(GovernorDay, key)
    if day is None:
        day = GovernorDay(
            date=key,
            quiet_drift_min=random.randint(-QUIET_DRIFT_MIN, QUIET_DRIFT_MIN),
            no_auto_today=_pick_rest_day(),
        )
        session.add(day)
        session.commit()
        session.refresh(day)
    return day


def _pick_rest_day() -> bool:
    """Weekly shape (S-04): weekends lighter, occasional whole no-auto day."""
    wd = local_now().weekday()
    p = 0.25 if wd >= 5 else 0.08     # more likely to rest on weekends
    return random.random() < p


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def in_quiet_hours(session: Session, at: datetime | None = None) -> bool:
    day = get_day(session)
    at = at or local_now()
    start = _parse_hhmm(get_setting(session, "quiet_start", QUIET_START))
    end = _parse_hhmm(get_setting(session, "quiet_end", QUIET_END))
    drift = timedelta(minutes=day.quiet_drift_min)
    today = at.date()
    start_dt = (datetime.combine(today, start, tzinfo=at.tzinfo) + drift)
    end_dt = (datetime.combine(today, end, tzinfo=at.tzinfo) + drift)
    if start_dt <= end_dt:
        return start_dt <= at <= end_dt
    # window wraps midnight (default 23:30 -> 07:30)
    return at >= start_dt or at <= end_dt


def _cap_for(session: Session, kind: str, mode: str) -> tuple[int, str]:
    if kind in ("reply",):
        if mode == "auto":
            return get_setting(session, "cap_replies_auto", CAP_REPLIES_AUTO), "replies_auto"
        return get_setting(session, "cap_replies_assisted", CAP_REPLIES_ASSISTED), "replies_assisted"
    if kind == "thread":
        return get_setting(session, "cap_threads", CAP_THREADS), "threads"
    return get_setting(session, "cap_posts", CAP_POSTS), "posts"


def check_write_allowed(session: Session, kind: str, mode: str) -> None:
    """Full gate for a write. Raises GovernorRefusal with a distinct reason."""
    day = get_day(session)
    if day.kill_switch or get_setting(session, "kill_switch", False):
        raise GovernorRefusal("kill switch engaged")
    if in_quiet_hours(session):
        raise GovernorRefusal("quiet hours")
    if mode == "auto" and day.no_auto_today:
        raise GovernorRefusal("weekly-shape rest day: no auto activity")

    cap, field = _cap_for(session, kind, mode)
    used = getattr(day, field)
    if used >= cap:
        raise GovernorRefusal(f"daily cap reached: {field} {used}/{cap}")

    # min spacing (S-02)
    if day.last_write_at is not None:
        last = day.last_write_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        spacing = get_setting(session, "min_write_spacing_s", MIN_WRITE_SPACING_S)
        if (datetime.now(timezone.utc) - last).total_seconds() < spacing:
            raise GovernorRefusal(f"minimum spacing not elapsed ({spacing}s)")

    # burst guard (S-05) — bus-level, independent of caps
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=BURST_WINDOW_S)
    recent_writes = session.exec(
        select(Action).where(
            Action.kind.in_(["reply", "publish", "thread"]),
            Action.finished_at != None,  # noqa: E711
            Action.finished_at >= cutoff,
            Action.outcome == "done",
        )
    ).all()
    if len(recent_writes) >= BURST_MAX_WRITES:
        raise GovernorRefusal(
            f"burst guard: {len(recent_writes)} writes in last "
            f"{BURST_WINDOW_S // 60}m (max {BURST_MAX_WRITES})")


def record_write(session: Session, kind: str, mode: str) -> None:
    day = get_day(session)
    if kind == "reply":
        if mode == "auto":
            day.replies_auto += 1
        else:
            day.replies_assisted += 1
    elif kind == "thread":
        day.threads += 1
    else:
        day.posts += 1
    day.last_write_at = datetime.now(timezone.utc)
    session.add(day)
    session.commit()


def record_read(session: Session, n: int = 1) -> None:
    day = get_day(session)
    day.reads += n
    session.add(day)
    session.commit()


def read_budget_left(session: Session) -> int:
    from ..defaults import DAILY_READ_BUDGET
    day = get_day(session)
    return max(0, get_setting(session, "daily_read_budget", DAILY_READ_BUDGET) - day.reads)


# --- kill / panic (S-06) -----------------------------------------------
def set_kill(session: Session, on: bool) -> None:
    day = get_day(session)
    day.kill_switch = on
    session.add(day)
    from ..db.settings_store import set_setting
    set_setting(session, "kill_switch", on)   # persisted across restarts
    session.commit()


def panic(session: Session, delete_last_n: int = 5) -> list[str]:
    """Kill + delete the last N auto-sent replies (S-06). Returns ids queued
    for deletion (deletion executed by the caller via the bus)."""
    set_kill(session, True)
    day = get_day(session)
    day.panic_at = datetime.now(timezone.utc)
    session.add(day)
    session.commit()
    sent = session.exec(
        select(Action).where(Action.kind == "reply", Action.outcome == "done",
                             Action.issuer == "policy")
        .order_by(Action.finished_at.desc()).limit(delete_last_n)
    ).all()
    return [a.x_post_id for a in sent if a.x_post_id]


# --- jitter / delay helpers (S-02) -------------------------------------
def jitter_seconds(base_s: float) -> float:
    frac = WRITE_JITTER_FRAC
    return base_s * (1 + random.uniform(-frac, frac))


def auto_delay_seconds() -> float:
    return random.uniform(AUTO_DELAY_MIN_S, AUTO_DELAY_MAX_S)


def next_available_slot(session: Session) -> datetime:
    """Earliest time a write could land, honouring spacing + quiet hours (S-07)."""
    day = get_day(session)
    now = datetime.now(timezone.utc)
    candidate = now
    if day.last_write_at is not None:
        last = day.last_write_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        spacing = get_setting(session, "min_write_spacing_s", MIN_WRITE_SPACING_S)
        candidate = max(candidate, last + timedelta(seconds=spacing))
    # push out of quiet hours
    for _ in range(48):
        local = candidate.astimezone(_tz())
        if not in_quiet_hours(session, local):
            break
        candidate += timedelta(minutes=30)
    return candidate
