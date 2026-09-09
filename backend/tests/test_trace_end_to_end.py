"""A whole For You sweep on the fixture engine leaves a complete trace.

The rule this enforces: no post leaves a run without a reason. Whatever path
a post takes, its row ends with a terminal outcome or at least a recorded
reason, and the run row carries the skip tally.
"""
from __future__ import annotations

from quill.db.settings_store import set_setting
from quill.ops import trace
from quill.persona.engine import Candidate, PersonaResult
from quill.pipeline import foryou_auto


def _fake_generate(session, text, account_handle="", auto=False):
    crit = {"sounds_like_operator": 5, "adds_something": 5, "reads_human": 5,
            "low_embarrassment_risk": 5, "auto_ok": True, "passes": True,
            "min_axis": 5}
    c = Candidate(angle="adds info", text="constrained decoding holds the schema",
                  critic=crit)
    return PersonaResult(candidates=[c], chosen_index=0, final_text=c.text, reason="ok")


def test_a_sweep_traces_every_post_it_saw(session, monkeypatch):
    monkeypatch.setattr(foryou_auto.persona, "generate", _fake_generate)
    # Let the fixture posts, which are days old, through the age gate so the
    # run exercises the scoring and drafting stages too.
    set_setting(session, foryou_auto.K_MAX_AGE_MIN, 10 ** 6)
    set_setting(session, foryou_auto.K_RELEVANCE_MIN, 0)
    set_setting(session, foryou_auto.K_MODE, "auto")

    out = foryou_auto.run(session, per_run=3, mode="auto")

    runs = [r for r in trace.runs(session) if r["kind"] == "foryou"]
    assert len(runs) == 1
    run = runs[0]
    assert run["seen"] == out["scanned"] > 0
    assert run["finished_at"] is not None
    assert run["summary"]["why_skipped"] == out["why_skipped"]

    detail = trace.run_detail(session, run["id"])
    for p in detail["posts"]:
        assert p["outcome"] or p["reason"], f"{p['x_post_id']} left the run unexplained"
        assert p["events"][0]["stage"] == "seen"
        assert p["source"] in ("For You", "Following (latest)")

    # Something was scored, and everything scored either got a draft or a reason.
    scored = [p for p in detail["posts"] if p["relevance"] is not None]
    assert scored, "the relevance floor is zero, so something must have scored"
    assert trace.current_run_id() is None, "the run must be closed afterwards"


def test_a_scheduled_send_is_visible_on_its_post(session, monkeypatch):
    monkeypatch.setattr(foryou_auto.persona, "generate", _fake_generate)
    set_setting(session, foryou_auto.K_MAX_AGE_MIN, 10 ** 6)
    set_setting(session, foryou_auto.K_RELEVANCE_MIN, 0)
    # A clear governor so the drafts schedule rather than stand down.
    from quill.governor import governor
    day = governor.get_day(session)
    day.kill_switch = False
    day.no_auto_today = False
    day.quiet_drift_min = 0
    day.replies_auto = day.replies_assisted = day.replies_foryou = 0
    day.last_write_at = None
    session.add(day)
    set_setting(session, "kill_switch", False)
    set_setting(session, "cap_replies_total", 50)
    now = governor.local_now()
    set_setting(session, "quiet_start", f"{(now.hour + 3) % 24:02d}:00")
    set_setting(session, "quiet_end", f"{(now.hour + 3) % 24:02d}:01")
    session.commit()

    out = foryou_auto.run(session, per_run=2, mode="auto")
    assert out["sent"] >= 1

    run = [r for r in trace.runs(session) if r["kind"] == "foryou"][0]
    assert run["scheduled"] == out["sent"]
    scheduled = [p for p in trace.run_detail(session, run["id"])["posts"]
                 if p["outcome"] == "scheduled"]
    assert scheduled and all(p["draft_id"] for p in scheduled)
    assert all("send at" in p["reason"] for p in scheduled)
