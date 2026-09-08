"""Single-threaded browser actor.

Playwright's sync API is thread-affine: every call must happen on the thread that
created the context, or it raises `greenlet.error: Cannot switch to a different
thread`. The browser process drives the engine from APScheduler's thread pool
(watch, foryou, sends…), so calls land on many threads and crash.

The actor fixes this by owning ONE worker thread that creates and holds the
Playwright engine. Every engine call is marshalled onto that thread and the
caller blocks for the result. This is also exactly the "browser is one
single-threaded shared resource" model the design already assumes.
"""
from __future__ import annotations

import queue
import threading
from concurrent.futures import Future
from typing import Callable

from ..logging_setup import get_logger

log = get_logger("quill.actor")

_STOP = object()



def _target_closed(exc: BaseException) -> bool:
    """Playwright's 'Target page, context or browser has been closed', by name
    or by message, so a version bump in the class name does not blind us."""
    name = type(exc).__name__
    msg = str(exc).lower()
    return (name == "TargetClosedError"
            or "has been closed" in msg
            or "browser has been closed" in msg
            or "connection closed" in msg)


class BrowserActor:
    def __init__(self, factory: Callable[[], object]):
        self._factory = factory
        self._engine = None
        self._q: "queue.Queue" = queue.Queue()
        self._thread = threading.Thread(target=self._loop, name="browser-actor", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while True:
            item = self._q.get()
            if item is _STOP:
                self._teardown()
                return
            fn, fut = item
            try:
                if self._engine is None:
                    self._engine = self._factory()   # created ON this thread
                fut.set_result(fn(self._engine))
            except BaseException as e:
                # Chromium can drop the page or the whole context under us
                # (a crash, a tab X closes, a navigation that kills the
                # target). The old actor kept the dead engine forever, so
                # every call after that failed until the process restarted.
                # Rebuild once and retry; if that fails too, report it.
                if _target_closed(e):
                    log.warning("browser target closed (%s); rebuilding the engine", e)
                    self._teardown()
                    try:
                        self._engine = self._factory()
                        fut.set_result(fn(self._engine))
                        continue
                    except BaseException as e2:
                        fut.set_exception(e2)
                        continue
                fut.set_exception(e)                  # propagate to the caller

    def _teardown(self) -> None:
        try:
            if self._engine is not None and hasattr(self._engine, "close"):
                self._engine.close()
        except Exception as e:
            log.warning("actor teardown: %s", e)
        finally:
            self._engine = None

    def submit(self, fn: Callable[[object], object]):
        fut: Future = Future()
        self._q.put((fn, fut))
        return fut.result()          # blocks until the actor thread finishes it

    def stop(self) -> None:
        self._q.put(_STOP)


class ThreadedEngine:
    """Engine facade that runs every real engine call on the actor thread.
    Implements the BrowserEngine interface transparently via __getattr__."""

    name = "playwright"

    def __init__(self):
        from .playwright_engine import PlaywrightEngine
        self._actor = BrowserActor(PlaywrightEngine)

    def __getattr__(self, item: str):
        # Only reached for names not set on the instance/class (i.e. engine
        # methods). Never route private/dunder lookups (avoids recursion on
        # self._actor before init, and pickling/hasattr surprises).
        if item.startswith("_"):
            raise AttributeError(item)
        def call(*args, **kwargs):
            return self._actor.submit(lambda e: getattr(e, item)(*args, **kwargs))
        return call

    def close(self) -> None:
        try:
            self._actor.submit(lambda e: e.close())
        except Exception:
            pass
        self._actor.stop()
