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
from concurrent.futures import TimeoutError as FuturesTimeout
import sys
import traceback
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



class EngineWedged(RuntimeError):
    """An engine call ran past the actor's budget. The browser was killed and
    relaunched; the call that hit it may or may not have taken effect."""


def _dump_stacks() -> None:
    frames = sys._current_frames()
    for th in threading.enumerate():
        fr = frames.get(th.ident)
        if fr is None:
            continue
        stack = "".join(traceback.format_stack(fr))
        log.error("thread %s (%s):\n%s", th.name, th.ident, stack)


def _kill_driver(engine) -> None:
    """Kill the Playwright driver process under a wedged engine. Chromium
    exits with it. Done at the OS level because every Playwright object is
    bound to the thread that is stuck."""
    if engine is None:
        return
    try:
        pw = getattr(engine, "_pw", None)
        proc = pw._impl_obj._connection._transport._proc
        proc.kill()
        log.warning("killed the wedged Playwright driver (pid %s)", proc.pid)
    except Exception as e:
        log.error("could not kill the wedged Playwright driver: %s", e)

class BrowserActor:
    def __init__(self, factory: Callable[[], object]):
        self._factory = factory
        self._engine = None
        self._q: "queue.Queue" = queue.Queue()
        self._spawn_thread()

    def _spawn_thread(self) -> None:
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

    # The longest legitimate engine call is a reply: open the post, type a
    # few hundred characters at human speed, send, reload, verify, and fall
    # back to the profile. That is under three minutes. Anything past this
    # is a wedged Playwright call, and one of those used to freeze every job
    # in the process forever, sends included, with no line in the log.
    CALL_TIMEOUT_S = 300

    def submit(self, fn: Callable[[object], object], timeout: float | None = None):
        fut: Future = Future()
        self._q.put((fn, fut))
        try:
            return fut.result(timeout or self.CALL_TIMEOUT_S)
        except FuturesTimeout:
            self._recover_from_wedge()
            raise EngineWedged(f"engine call exceeded {timeout or self.CALL_TIMEOUT_S}s "
                               "and the browser has been closed and restarted")

    def _recover_from_wedge(self) -> None:
        """The actor thread is stuck inside Playwright. It cannot be
        interrupted and its engine cannot be closed from another thread, so
        record where it is stuck, kill the browser it was driving, and hand the
        queue to a fresh thread that will launch a new one."""
        log.error("browser actor wedged; thread stacks follow")
        _dump_stacks()
        wedged, self._engine = self._engine, None
        # A new queue: the stuck thread must not wake up later and start
        # serving calls against a browser that no longer exists.
        self._q = queue.Queue()
        _kill_driver(wedged)
        self._spawn_thread()
        log.warning("browser actor restarted on a fresh thread")

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
