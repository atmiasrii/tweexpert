"""The day's unattended run: when it started, what it owes, how it is doing.

Quill had no notion of a target, so "behind" was not a state it could be in and
there was nothing for a supervisor to act on. This is that notion, plus the one
lever it is allowed to pull.

The lever widens what the For You sweep will *consider*. It never touches what
the sweep will *send*: `foryou_auto_min`, the persona guards, the write spacing
and every governor cap are outside this module on purpose. Volume is bought by
looking at more posts, never by lowering the bar on what gets said.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..db.models import Action
from ..db.settings_store import get_setting, set_setting
from ..defaults import (RUN_DEADLINE_LOCAL, RUN_HISTORY_DAYS, RUN_TARGET_REPLIES,
                        RELAX_STEP_INTERVAL_S)
from ..governor import governor
from ..logging_setup import get_logger

log = get_logger("quill.run")

RUN_KEY = "run_session"
RUN_HISTORY_KEY = "run_history"

DEFAULT_TARGET = RUN_TARGET_REPLIES
DEFAULT_DEADLINE = RUN_DEADLINE_LOCAL

# Widening the intake, in order. The thresholds are how many replies behind the
# run has to be before that step is allowed. The three settings are the largest
# sources of loss in the measured sweeps: of 55 posts scanned, typically 17-21
# go as too old, 8-12 below the relevance floor and 8-9 on author cooldown.
LADDER = [
    {"behind": 0,  "foryou_max_age_min": 360,  "foryou_relevance_min": 40, "foryou_cooldown_h": 24},
    {"behind": 3,  "foryou_max_age_min": 540,  "foryou_relevance_min": 35, "foryou_cooldown_h": 18},
    {"behind": 8,  "foryou_max_age_min": 720,  "foryou_relevance_min": 30, "foryou_cooldown_h": 12},
    {"behind": 15, "foryou_max_age_min": 1440, "foryou_relevance_min": 25, "foryou_cooldown_h": 8},
]


def _today() -> str:
    return governor.local_now().strftime("%Y-%m-%d")


def verified_sends_today(session: Session) -> int:
    """Replies we can point at. Counted the way the dashboard counts them: a
    finished reply action carrying a real post id, not a governor charge."""
    start = governor.local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = session.exec(select(Action).where(
        Action.kind == "reply", Action.state == "done",
        Action.created_at >= start.astimezone(timezone.utc).replace(tzinfo=None))).all()
    return len([a for a in rows if a.x_post_id])


def get_or_start(session: Session) -> dict:
    """Today's record, created and stamped on first use."""
    rec = get_setting(session, RUN_KEY, None)
    today = _today()
    if rec and rec.get("day") == today:
        return rec

    if rec:
        hist = get_setting(session, RUN_HISTORY_KEY, [])
        hist.append(rec)
        set_setting(session, RUN_HISTORY_KEY, hist[-RUN_HISTORY_DAYS:])
        # A new day starts at level 0, and the settings must say so too. The
        # record used to reset its level while the widened age window,
        # relevance floor and cooldown from the night before stayed applied,
        # so the card read "level 0" while the sweep replied to day-old posts.
        if int(rec.get("relax_level", 0) or 0) != 0:
            apply_level(session, 0)
            log.info("new day: intake back to level 0 from level %s", rec.get("relax_level"))

    # Prefer the launcher's own stamp: the supervisor's first tick can be a
    # minute after the start, and the operator asked for the real start time.
    started = governor.local_now()
    stamped = get_setting(session, "live_started_at", None)
    if stamped:
        try:
            when = datetime.fromisoformat(stamped)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            when = when.astimezone(started.tzinfo)
            if when.strftime("%Y-%m-%d") == today:
                started = when
        except ValueError:
            pass

    rec = {"day": today, "started_at": started.isoformat(),
           "target": int(get_setting(session, "run_target", DEFAULT_TARGET)),
           "deadline": get_setting(session, "run_deadline", DEFAULT_DEADLINE),
           "relax_level": 0, "relax_changed_at": None,
           "restarts": [], "alerted": {}}
    set_setting(session, RUN_KEY, rec)
    log.info("run started %s, target %d replies by %s",
             rec["started_at"][:16], rec["target"], rec["deadline"])
    return rec


def save(session: Session, rec: dict) -> None:
    set_setting(session, RUN_KEY, rec)


def progress(session: Session, rec: dict, now: datetime | None = None) -> dict:
    now = now or governor.local_now()
    started = datetime.fromisoformat(rec["started_at"])
    if started.tzinfo is None:
        started = started.replace(tzinfo=now.tzinfo)

    # Quiet hours are not run time. A record that rolls over at midnight would
    # otherwise read as seven hours behind the moment the window lifts, and
    # would widen the intake at breakfast to catch up on a night when sending
    # was forbidden.
    started = max(started, _active_start(session, now))

    hh, mm = (int(x) for x in str(rec.get("deadline", DEFAULT_DEADLINE)).split(":"))
    deadline = now.replace(hour=hh, minute=mm, second=0, microsecond=0)

    target = int(rec.get("target", DEFAULT_TARGET))
    sent = verified_sends_today(session)

    window = (deadline - started).total_seconds()
    elapsed = max(0.0, min((now - started).total_seconds(), window))
    frac = (elapsed / window) if window > 0 else 1.0
    expected = round(target * frac, 1)

    # Can the rest still fit? Spacing is the binding constraint: no amount of
    # widening the intake buys a reply the governor will not let us write yet.
    spacing = max(1, int(get_setting(session, "min_write_spacing_s", 300)))
    left_s = max(0.0, (deadline - now).total_seconds())
    capacity = int(left_s // spacing)
    owed = max(0, target - sent)

    return {"sent": sent, "target": target, "expected": expected,
            "behind_by": round(max(0.0, expected - sent), 1),
            "capacity_left": capacity, "owed": owed,
            "reachable": capacity >= owed,
            "deadline_at": deadline.isoformat(),
            "started_at": rec["started_at"]}


def _active_start(session: Session, now: datetime) -> datetime:
    """When today's sending window opened: the end of the quiet hours."""
    from ..defaults import QUIET_END
    raw = str(get_setting(session, "quiet_end", QUIET_END))
    try:
        hh, mm = (int(x) for x in raw.split(":"))
    except ValueError:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    drift = timedelta(minutes=int(getattr(governor.get_day(session),
                                          "quiet_drift_min", 0) or 0))
    return now.replace(hour=hh, minute=mm, second=0, microsecond=0) + drift


def _level_for(behind: float) -> int:
    level = 0
    for i, step in enumerate(LADDER):
        if behind >= step["behind"]:
            level = i
    return level


def apply_level(session: Session, level: int) -> None:
    for key, value in LADDER[level].items():
        if key == "behind":
            continue
        set_setting(session, key, value)


def adjust(session: Session, rec: dict, prog: dict,
           now: datetime | None = None) -> int:
    """Move the intake one step toward what the pace calls for.

    One step per window in either direction, so a slow half hour does not slam
    the intake to its floor and one burst does not snap it back.
    """
    now = now or datetime.now(timezone.utc)
    current = int(rec.get("relax_level", 0))
    wanted = _level_for(float(prog.get("behind_by", 0.0)))

    # Freeze only when nothing more can go out today at all. The first version
    # froze whenever the target was arithmetically out of reach, which on a
    # late start meant it froze within the hour and never widened the intake
    # once: 16 sent against 40 with the one lever untouched all evening. That
    # reasoning assumed send slots were the scarce thing. They were not; usable
    # candidates were. Widening intake cannot lower reply quality either, since
    # the confidence bar sits downstream of it and is never touched here.
    if int(prog.get("capacity_left", 1)) <= 0 and wanted > current:
        return current

    if wanted == current:
        return current

    changed_at = rec.get("relax_changed_at")
    if changed_at:
        try:
            last = datetime.fromisoformat(changed_at)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if (now - last).total_seconds() < RELAX_STEP_INTERVAL_S:
                return current
        except ValueError:
            pass

    step = 1 if wanted > current else -1
    level = current + step
    apply_level(session, level)
    rec["relax_level"] = level
    rec["relax_changed_at"] = now.isoformat()
    log.info("intake level %d -> %d (behind by %.1f)", current, level,
             prog.get("behind_by", 0.0))
    return level
