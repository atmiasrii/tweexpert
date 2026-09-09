"""The day's run record: start time, target, pace, and the relaxation ladder."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from quill.db.settings_store import get_setting, set_setting
from quill.ops import run_session


def _at(rec, hhmm: str):
    """Pin 'now' to a local time today for deterministic pace maths."""
    d = datetime.fromisoformat(rec["started_at"])
    h, m = (int(x) for x in hhmm.split(":"))
    return d.replace(hour=h, minute=m, second=0, microsecond=0)


def test_a_record_is_stamped_once_and_reused(session):
    a = run_session.get_or_start(session)
    b = run_session.get_or_start(session)
    assert a["started_at"] == b["started_at"]
    assert a["target"] == run_session.DEFAULT_TARGET
    assert a["relax_level"] == 0


def test_the_start_time_comes_from_the_launcher_not_the_first_tick(session):
    from quill.governor import governor
    started = governor.local_now().replace(hour=8, minute=0, second=0, microsecond=0)
    set_setting(session, "live_started_at", started.isoformat())
    rec = run_session.get_or_start(session)
    assert datetime.fromisoformat(rec["started_at"]).hour == 8


def test_a_new_day_archives_the_old_record(session):
    rec = run_session.get_or_start(session)
    rec["day"] = "1999-01-01"
    rec["target"] = 7
    set_setting(session, run_session.RUN_KEY, rec)

    fresh = run_session.get_or_start(session)
    assert fresh["day"] != "1999-01-01"
    assert fresh["relax_level"] == 0
    hist = get_setting(session, run_session.RUN_HISTORY_KEY, [])
    assert [h["day"] for h in hist] == ["1999-01-01"]


# ----------------------------------------------------------------- pace
def test_halfway_through_the_window_expects_half_the_target(session):
    rec = run_session.get_or_start(session)
    rec["started_at"] = _at(rec, "10:00").isoformat()
    rec["deadline"] = "22:00"
    rec["target"] = 40
    p = run_session.progress(session, rec, now=_at(rec, "16:00"))
    assert p["expected"] == pytest.approx(20.0, abs=0.5)
    assert p["sent"] == 0
    assert p["behind_by"] == pytest.approx(20.0, abs=0.5)


def test_on_pace_is_not_behind(session, monkeypatch):
    rec = run_session.get_or_start(session)
    rec["started_at"] = _at(rec, "10:00").isoformat()
    rec["target"] = 40
    monkeypatch.setattr(run_session, "verified_sends_today", lambda s: 25)
    p = run_session.progress(session, rec, now=_at(rec, "16:00"))
    assert p["behind_by"] == 0


def test_a_target_that_cannot_fit_the_time_left_is_unreachable(session, monkeypatch):
    rec = run_session.get_or_start(session)
    rec["started_at"] = _at(rec, "10:00").isoformat()
    rec["target"] = 40
    set_setting(session, "min_write_spacing_s", 300)
    monkeypatch.setattr(run_session, "verified_sends_today", lambda s: 12)
    # 21:00 -> 60 minutes left, room for 12 more at 5-minute spacing, 28 owed.
    p = run_session.progress(session, rec, now=_at(rec, "21:00"))
    assert p["reachable"] is False
    assert p["capacity_left"] == 12


def test_a_target_with_the_whole_day_ahead_is_reachable(session, monkeypatch):
    rec = run_session.get_or_start(session)
    rec["started_at"] = _at(rec, "08:00").isoformat()
    rec["target"] = 40
    set_setting(session, "min_write_spacing_s", 300)
    monkeypatch.setattr(run_session, "verified_sends_today", lambda s: 0)
    p = run_session.progress(session, rec, now=_at(rec, "08:30"))
    assert p["reachable"] is True


# ------------------------------------------------------------- relaxation
def test_being_behind_steps_the_ladder_up_one_level(session):
    rec = run_session.get_or_start(session)
    run_session.adjust(session, rec, {"behind_by": 20.0, "reachable": True},
                       now=datetime.now(timezone.utc))
    assert rec["relax_level"] == 1, "the ladder moves one step at a time"
    assert get_setting(session, "foryou_max_age_min") == 540
    assert get_setting(session, "foryou_relevance_min") == 35


def test_the_ladder_will_not_step_twice_inside_the_hysteresis_window(session):
    rec = run_session.get_or_start(session)
    now = datetime.now(timezone.utc)
    run_session.adjust(session, rec, {"behind_by": 20.0, "reachable": True}, now=now)
    run_session.adjust(session, rec, {"behind_by": 20.0, "reachable": True},
                       now=now + timedelta(minutes=5))
    assert rec["relax_level"] == 1
    run_session.adjust(session, rec, {"behind_by": 20.0, "reachable": True},
                       now=now + timedelta(minutes=16))
    assert rec["relax_level"] == 2


def test_catching_up_steps_the_ladder_back_down(session):
    rec = run_session.get_or_start(session)
    now = datetime.now(timezone.utc)
    run_session.adjust(session, rec, {"behind_by": 20.0, "reachable": True}, now=now)
    run_session.adjust(session, rec, {"behind_by": 0.0, "reachable": True},
                       now=now + timedelta(minutes=16))
    assert rec["relax_level"] == 0
    assert get_setting(session, "foryou_max_age_min") == 360


def test_the_ladder_stops_at_its_floor(session):
    rec = run_session.get_or_start(session)
    now = datetime.now(timezone.utc)
    for i in range(8):
        run_session.adjust(session, rec, {"behind_by": 99.0, "reachable": True},
                           now=now + timedelta(minutes=16 * i))
    assert rec["relax_level"] == 3
    assert get_setting(session, "foryou_relevance_min") == 25


def test_an_unreachable_target_freezes_the_ladder(session):
    rec = run_session.get_or_start(session)
    now = datetime.now(timezone.utc)
    run_session.adjust(session, rec, {"behind_by": 99.0, "reachable": True}, now=now)
    assert rec["relax_level"] == 1
    run_session.adjust(session, rec, {"behind_by": 99.0, "reachable": False},
                       now=now + timedelta(minutes=16))
    assert rec["relax_level"] == 1, "a target out of reach must not relax further"


def test_relaxation_never_touches_the_reply_quality_bar(session):
    rec = run_session.get_or_start(session)
    set_setting(session, "foryou_auto_min", 18)
    now = datetime.now(timezone.utc)
    for i in range(6):
        run_session.adjust(session, rec, {"behind_by": 99.0, "reachable": True},
                           now=now + timedelta(minutes=16 * i))
    assert get_setting(session, "foryou_auto_min") == 18
