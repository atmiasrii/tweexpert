"""A Playwright call that never returns must not freeze the process."""
import threading
import time

import pytest

from quill.browser import actor as actor_mod


class _Engine:
    def __init__(self):
        self.calls = []
        self._pw = None

    def quick(self):
        self.calls.append("quick")
        return "ok"

    def forever(self):
        threading.Event().wait()          # never returns


def test_wedged_call_times_out_and_actor_recovers(monkeypatch):
    engines = []

    def factory():
        e = _Engine()
        engines.append(e)
        return e

    monkeypatch.setattr(actor_mod.BrowserActor, "CALL_TIMEOUT_S", 0.5)
    a = actor_mod.BrowserActor(factory)
    assert a.submit(lambda e: e.quick()) == "ok"

    t0 = time.time()
    with pytest.raises(actor_mod.EngineWedged):
        a.submit(lambda e: e.forever())
    assert time.time() - t0 < 5

    # A fresh thread with a fresh engine serves the next call.
    assert a.submit(lambda e: e.quick()) == "ok"
    assert len(engines) == 2
    assert engines[1].calls == ["quick"]


def test_wedge_message_requeues_the_draft():
    # The bus keys "safe to send again" off this phrase (action_bus._execute_with_retry).
    a = actor_mod.BrowserActor(lambda: _Engine())
    a.CALL_TIMEOUT_S = 0.2
    with pytest.raises(actor_mod.EngineWedged) as ei:
        a.submit(lambda e: e.forever())
    assert "has been closed" in str(ei.value)
