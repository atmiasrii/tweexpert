"""Every post Quill looks at leaves a row saying what happened to it and why."""
from __future__ import annotations

from datetime import datetime, timezone

from quill.browser.base import ParsedPost
from quill.ops import trace


def _post(pid="2100000000000000001", handle="simonw", likes=12):
    return ParsedPost(x_post_id=pid, author_handle=handle, text="a post",
                      created_at=datetime.now(timezone.utc), likes=likes, replies=3,
                      views=900)


def test_a_seen_post_gets_a_row_with_its_metrics(session):
    rid = trace.start_run(session, "foryou", "For You")
    trace.seen(session, _post(), source="For You")
    trace.finish_run(session, rid)

    d = trace.run_detail(session, rid)
    assert d["seen"] == 1
    p = d["posts"][0]
    assert p["author"] == "simonw" and p["likes"] == 12 and p["views"] == 900
    assert p["stage"] == "seen" and p["outcome"] == ""


def test_notes_build_the_journey_and_the_last_terminal_is_the_outcome(session):
    rid = trace.start_run(session, "foryou")
    trace.seen(session, _post())
    trace.note(session, "2100000000000000001", "scored", "relevance 61", relevance=61.0)
    trace.note(session, "2100000000000000001", "drafting", "writing a reply")
    trace.note(session, "2100000000000000001", "discarded", "under the bar: too generic",
               draft_id=7)
    trace.finish_run(session, rid)

    p = trace.run_detail(session, rid)["posts"][0]
    assert [e["stage"] for e in p["events"]] == ["seen", "scored", "drafting", "discarded"]
    assert p["outcome"] == "discarded"
    assert p["reason"] == "under the bar: too generic"
    assert p["relevance"] == 61.0 and p["draft_id"] == 7
    assert trace.run_detail(session, rid)["drafted"] == 1


def test_a_note_with_no_run_open_attaches_to_the_latest_row(session):
    """Sends happen in their own job, long after the sweep that found the post."""
    rid = trace.start_run(session, "foryou")
    trace.seen(session, _post())
    trace.note(session, "2100000000000000001", "scheduled", "send at 10:05")
    trace.finish_run(session, rid)
    assert trace.current_run_id() is None

    trace.note(session, "2100000000000000001", "sent", "verified",
               sent_x_post_id="2100000000000000099")

    rows = trace.for_post(session, "2100000000000000001")
    assert rows[0]["outcome"] == "sent"
    assert rows[0]["sent_x_post_id"] == "2100000000000000099"
    assert trace.run_detail(session, rid)["sent"] == 1


def test_a_post_unseen_by_the_run_is_created_on_first_note(session):
    """The watchlist path processes posts it never announced as seen."""
    rid = trace.start_run(session, "watch", "timeline")
    trace.note(session, "2100000000000000002", "discarded", "freshness gate: too old")
    trace.finish_run(session, rid)
    p = trace.run_detail(session, rid)["posts"][0]
    assert p["x_post_id"] == "2100000000000000002"
    assert p["outcome"] == "discarded"


def test_runs_are_listed_newest_first_with_counts(session):
    a = trace.start_run(session, "foryou")
    trace.seen(session, _post("1"))
    trace.seen(session, _post("2"))
    trace.finish_run(session, a, why_skipped={"too_old": 1})
    b = trace.start_run(session, "watch")
    trace.finish_run(session, b)

    listed = trace.runs(session)
    assert [r["id"] for r in listed] == [b, a]
    assert listed[1]["seen"] == 2
    assert listed[1]["summary"] == {"why_skipped": {"too_old": 1}}


def test_tracing_never_breaks_the_caller(session, monkeypatch):
    rid = trace.start_run(session, "foryou")

    def boom(*a, **k):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(trace, "_append", boom)
    trace.seen(session, _post())                       # must not raise
    trace.note(session, "2100000000000000001", "scored", "x")
    trace.finish_run(session, rid)


def test_events_also_land_on_disk_as_jsonl(session, tmp_path, monkeypatch):
    from quill import config
    s = config.get_settings()
    monkeypatch.setattr(s, "data_dir", tmp_path)
    rid = trace.start_run(session, "foryou")
    trace.seen(session, _post())
    trace.finish_run(session, rid)
    files = list((tmp_path / "traces").glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert [__import__("json").loads(l)["event"] for l in lines] == \
        ["run_start", "seen", "run_end"]


def test_a_send_is_credited_to_the_run_that_scheduled_it(session):
    """A later sweep sees the same post again and skips it. The send that
    lands afterwards must not be booked against that later run."""
    a = trace.start_run(session, "foryou")
    trace.seen(session, _post())
    trace.note(session, "2100000000000000001", "scheduled", "send at 10:05", draft_id=42)
    trace.finish_run(session, a)

    b = trace.start_run(session, "foryou")
    trace.seen(session, _post())
    trace.note(session, "2100000000000000001", "skipped", "author answered inside the cooldown")
    trace.finish_run(session, b)

    trace.note(session, "2100000000000000001", "sent", "verified", draft_id=42,
               sent_x_post_id="2100000000000000099")

    assert trace.run_detail(session, a)["sent"] == 1
    assert trace.run_detail(session, b)["sent"] == 0
    assert trace.run_detail(session, b)["posts"][0]["outcome"] == "skipped"
