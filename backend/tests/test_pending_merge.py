"""send_due_auto must not erase sends scheduled while it was running."""
from datetime import datetime, timedelta, timezone

from quill.db.settings_store import get_setting, set_setting
from quill.pipeline import pipeline as pl


def test_items_added_during_a_run_survive(session, monkeypatch):
    later = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    set_setting(session, "_pending_auto",
                [{"draft_id": 1, "authz_id": 1, "target": "1", "send_at": later}])

    # Simulate the sweep appending an item while send_due_auto iterates.
    real_get = pl.get_setting if hasattr(pl, "get_setting") else None
    calls = {"n": 0}
    from quill.db import settings_store

    orig = settings_store.get_setting

    def racy_get(sess, key, default=None):
        val = orig(sess, key, default)
        if key == "_pending_auto" and calls["n"] == 0:
            calls["n"] += 1
            settings_store.set_setting(sess, "_pending_auto", val + [
                {"draft_id": 2, "authz_id": 2, "target": "2", "send_at": later}])
        return val

    monkeypatch.setattr(settings_store, "get_setting", racy_get)
    pl.send_due_auto(session)
    ids = sorted(i["draft_id"] for i in orig(session, "_pending_auto", []))
    assert ids == [1, 2]
