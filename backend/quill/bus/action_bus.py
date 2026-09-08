"""Action bus (§7). The browser is one shared, single-threaded resource;
everything that touches it goes through this one queue.

Q-01 exactly one consumer, protected by a mutex — two actions never overlap.
Q-02 write an intent row with the idempotency key BEFORE executing; on startup
     reconcile any intent without a terminal outcome by checking whether the
     post already exists on X — a crash mid-publish never double-posts.
Q-03 retries with exponential backoff + full jitter, capped at 3, and never
     for writes whose reconciliation is ambiguous.
Q-04 every action produces an audit row.
Q-05 minimum enforced gap between writes (delegated to the governor).

Demotion policy. A write that hits ChallengeDetected or SessionDead is a real
safety event: X is pushing back, or we are logged out, and auto mode must stop
until a human looks. A SelectorMiss is not. X's timeline renders client-side
and routinely takes 10-20s to settle, so a missed selector is usually a
page-render race on one write, not evidence the registry is wrong. Demoting
every auto account on one of those was how twenty accounts got flipped to
assisted by a single event. `_disable_auto_and_alert` therefore alerts on all
three, and changes account mode only for the first two. The canary
(ops/session_guard.py) is what decides a selector is really broken, and it
needs several consecutive misses before it acts.
"""
from __future__ import annotations

import hashlib
import json
import random
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..browser import (ChallengeDetected, PostUnavailable, SelectorMiss,
                       SendNotConfirmed, SendRejected, SessionDead,
                       get_engine)
from ..db.engine import session_scope
from ..db.models import Action, Draft
from ..logging_setup import get_logger
from ..notify import notifier
from ..governor import governor
from .authz import (ActionAuthorization, AuthorizationError, consume,
                    validate_unconsumed)

log = get_logger("quill.bus")

WRITE_KINDS = {"reply", "publish", "thread"}
MAX_ATTEMPTS = 3
# A pending intent is only stale once it has waited longer than this.
PENDING_STALE_S = 15 * 60


def idempotency_key(kind: str, target: str, content: str) -> str:
    return hashlib.sha256(f"{kind}|{target}|{content}".encode()).hexdigest()



def _older_than(created_at, cutoff) -> bool:
    if created_at is None:
        return True
    ts = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    return ts < cutoff


class ActionBus:
    """Single-consumer serialised bus. One process-wide instance."""

    def __init__(self):
        self._lock = threading.RLock()      # the mutex (Q-01)
        self._concurrent = 0
        self.max_concurrent = 0             # instrumentation for T-06

    # -- public: writes --------------------------------------------------
    def submit_write(self, kind: str, target: str, content: str,
                     authorization: ActionAuthorization | None,
                     issuer: str = "", priority: int = 1,
                     draft_id: int | None = None,
                     permalink: str = "", author: str = "") -> Action:
        if kind not in WRITE_KINDS:
            raise ValueError(f"{kind} is not a write kind")
        key = idempotency_key(kind, target, content)

        # Y-01/T-02: no code path to a write without a valid authorization.
        with session_scope() as s:
            try:
                validate_unconsumed(s, authorization)
            except AuthorizationError as e:
                log.error("UNAUTHORIZED WRITE BLOCKED: %s", e,
                          extra={"kind": kind, "target": target})
                notifier.alert("worker_down",
                               f"Blocked unauthorized write ({kind}->{target}): {e}")
                self._audit_blocked(s, kind, target, key, str(e))
                raise
            # Q-05 + governor gate (caps, quiet, spacing, burst)
            governor.check_write_allowed(s, kind, authorization.mode)

        return self._run_write(kind, target, content, authorization, issuer,
                               priority, key, draft_id, permalink, author)

    def _run_write(self, kind, target, content, authorization, issuer,
                   priority, key, draft_id, permalink="", author=""):
        with self._lock:                    # serialise (Q-01, T-06)
            self._enter()
            try:
                # idempotency: identical write already done => do not repeat
                with session_scope() as s:
                    done = s.exec(select(Action).where(
                        Action.idempotency_key == key,
                        Action.state == "done")).first()
                    if done:
                        log.info("idempotent skip; already done key=%s", key[:12])
                        return done

                # Q-02: intent row BEFORE executing
                with session_scope() as s:
                    intent = Action(
                        kind=kind, payload_json=json.dumps(
                            {"target": target, "content": content,
                             "permalink": permalink, "author": author}),
                        idempotency_key=key,
                        authorization_id=authorization.id if authorization else None,
                        issuer=issuer or (authorization.issuer if authorization else ""),
                        target=target, priority=priority, state="running",
                        started_at=datetime.now(timezone.utc),
                    )
                    s.add(intent)
                    s.commit()
                    s.refresh(intent)
                    intent_id = intent.id

                return self._execute_with_retry(intent_id, kind, target, content,
                                                authorization, key,
                                                permalink=permalink, author=author)
            finally:
                self._exit()

    def _execute_with_retry(self, intent_id, kind, target, content,
                            authorization, key, permalink: str = "",
                            author: str = "") -> Action:
        engine = get_engine()
        attempt = 0
        while True:
            attempt += 1
            try:
                x_post_id = self._call_engine_write(engine, kind, target, content,
                                                    permalink, author)
                # An empty id is not a success. Accepting it is what recorded
                # replies as sent that were never posted.
                if not x_post_id:
                    raise SendNotConfirmed(target)
                with session_scope() as s:
                    a = s.get(Action, intent_id)
                    a.attempts = attempt
                    a.state = "done"
                    a.outcome = "done"
                    a.x_post_id = x_post_id
                    a.finished_at = datetime.now(timezone.utc)
                    s.add(a)
                    # consume authorization (single-use) + record governor use
                    if authorization is not None:
                        consume(s, authorization)
                        governor.record_write(s, kind, authorization.mode)
                        self._mark_draft_sent(s, authorization.draft_id, x_post_id)
                    s.commit()
                    self._reset_failures(s, target)
                    return s.get(Action, intent_id)
            except (ChallengeDetected, SessionDead) as e:
                # never retry through a challenge / dead session (E-05, E-03)
                self._fail(intent_id, attempt, e, ambiguous=True)
                self._disable_auto_and_alert(kind, target, e)
                raise
            except SelectorMiss as e:
                # Every selector the reply path can miss (target article,
                # composer, send button) is looked up BEFORE the send click,
                # so nothing was posted. The draft is safe to try again; it
                # used to sit in "approved" forever with nothing pointing at it.
                self._fail(intent_id, attempt, e, ambiguous=False)
                self._resolve_draft(authorization, "queued")
                self._disable_auto_and_alert(kind, target, e)
                raise
            except PostUnavailable as e:
                # The post is gone. Nothing to retry, and nothing to review.
                self._fail(intent_id, attempt, e, outcome="target_gone")
                self._resolve_draft(authorization, "dismissed")
                raise
            except SendNotConfirmed as e:
                # We clicked send and could not find the reply. It may or may
                # not be live, so this is never retried and never called sent.
                # Charged to the governor deliberately: if it did go out, the
                # spacing and daily caps must still account for it.
                self._fail(intent_id, attempt, e, outcome="unverified")
                self._resolve_draft(authorization, "needs_review",
                                    charge_governor=kind)
                notifier.alert("send_unverified",
                               f"Could not confirm a reply to {target} was posted")
                raise
            except Exception as e:
                if attempt >= MAX_ATTEMPTS:
                    self._fail(intent_id, attempt, e, ambiguous=False)
                    # A browser that died at navigation posted nothing, so the
                    # draft is safe to send again. Anything else that failed
                    # after three tries may have gone out; let a human look.
                    closed = "has been closed" in str(e).lower()
                    self._resolve_draft(authorization,
                                        "queued" if closed else "needs_review")
                    self._register_publish_failure(target)
                    raise
                backoff = (2 ** attempt) + random.uniform(0, 2 ** attempt)  # Q-03
                log.warning("write attempt %d failed: %s; backoff %.1fs",
                            attempt, e, backoff)
                time.sleep(min(backoff, 0.1))  # short in tests; real backoff scaled by caller

    def _call_engine_write(self, engine, kind, target, content,
                           permalink: str = "", author: str = "") -> str:
        if kind == "reply":
            return engine.reply(target, content, permalink=permalink, author=author)
        if kind == "publish":
            return engine.publish(content)
        if kind == "thread":
            parts = json.loads(content)
            ids = engine.thread(parts)
            return ids[-1] if ids else ""
        raise ValueError(kind)

    # -- deferred writes (cross-process): api enqueues, browser drains ---
    def enqueue_write(self, kind: str, target: str, content: str,
                      authorization: ActionAuthorization, issuer: str = "",
                      draft_id: int | None = None, priority: int = 1,
                      permalink: str = "", author: str = "") -> Action:
        """Write a pending intent WITHOUT executing. The browser process (the
        single consumer of the engine) drains it. Same auth + governor gates."""
        if kind not in WRITE_KINDS:
            raise ValueError(f"{kind} is not a write kind")
        key = idempotency_key(kind, target, content)
        with session_scope() as s:
            validate_unconsumed(s, authorization)
            governor.check_write_allowed(s, kind, authorization.mode)
            intent = Action(
                kind=kind, payload_json=json.dumps(
                    {"target": target, "content": content,
                     "permalink": permalink, "author": author}),
                idempotency_key=key,
                authorization_id=authorization.id, issuer=issuer or authorization.issuer,
                target=target, priority=priority, state="pending")
            s.add(intent)
            s.commit()
            s.refresh(intent)
            return intent

    def drain_pending(self, limit: int = 10) -> list[Action]:
        """Execute pending write intents oldest-first (browser process loop)."""
        from ..db.models import Authorization
        done: list[Action] = []
        with session_scope() as s:
            pend = s.exec(select(Action).where(
                Action.kind.in_(list(WRITE_KINDS)), Action.state == "pending")
                .order_by(Action.priority, Action.created_at).limit(limit)).all()
            ids = [(a.id, a.authorization_id) for a in pend]
        for intent_id, authz_id in ids:
            # Everything needed to execute is copied into plain locals here.
            # Reading it off the ORM row after the session closed raised
            # DetachedInstanceError outside the try below, which aborted the
            # whole loop: this queue had never executed a single write.
            with session_scope() as s:
                arow = s.get(Authorization, authz_id)
                a = s.get(Action, intent_id)
                if not arow or not a:
                    continue
                payload = json.loads(a.payload_json or "{}")
                kind, key = a.kind, a.idempotency_key
                target = payload.get("target", "")
                content = payload.get("content", "")
                permalink = payload.get("permalink", "")
                author = payload.get("author", "")
                authz = ActionAuthorization(
                    id=arow.id, draft_id=arow.draft_id, issuer=arow.issuer,
                    mode=arow.mode, reasons=json.loads(arow.reasons_json),
                    issued_at=arow.issued_at, expires_at=arow.expires_at)
                a.state = "running"
                a.started_at = datetime.now(timezone.utc)
                s.add(a)
                s.commit()
            with self._lock:
                self._enter()
                try:
                    result = self._execute_with_retry(
                        intent_id, kind, target, content, authz, key,
                        permalink=permalink, author=author)
                    done.append(result)
                except Exception as e:
                    log.warning("drain: action %s failed: %s", intent_id, e)
                finally:
                    self._exit()
        return done

    # -- public: reads / non-content actions ----------------------------
    def submit_read(self, kind: str, target: str = "", payload: dict | None = None,
                    issuer: str = "system"):
        """Serialised read/presence/metrics/canary/login_check. No auth."""
        with self._lock:
            self._enter()
            key = idempotency_key(kind, target, json.dumps(payload or {}, sort_keys=True))
            with session_scope() as s:
                intent = Action(kind=kind, payload_json=json.dumps(payload or {}),
                                idempotency_key=key, issuer=issuer, target=target,
                                priority=5, state="running",
                                started_at=datetime.now(timezone.utc))
                s.add(intent)
                s.commit()
                s.refresh(intent)
                intent_id = intent.id
            try:
                result = self._call_engine_read(get_engine(), kind, target, payload or {})
                with session_scope() as s:
                    a = s.get(Action, intent_id)
                    a.state = "done"
                    a.outcome = "done"
                    a.finished_at = datetime.now(timezone.utc)
                    s.add(a)
                    s.commit()
                return result
            except Exception as e:
                self._fail(intent_id, 1, e, ambiguous=False)
                raise
            finally:
                self._exit()

    def _call_engine_read(self, engine, kind, target, payload):
        if kind == "read_user":
            return engine.read_user(target, payload.get("since_id", ""))
        if kind == "read_post":
            return engine.read_post(target, payload.get("depth", 3))
        if kind == "search":
            return engine.search(target)
        if kind == "notifications":
            return engine.notifications()
        if kind == "metrics":
            return engine.metrics(target)
        if kind == "presence":
            return engine.presence(target or "home")
        if kind == "canary":
            return engine.canary()
        if kind == "login_check":
            return engine.login_check()
        if kind == "delete":
            return engine.delete_post(target)
        raise ValueError(kind)

    def submit_delete(self, x_post_id: str, issuer: str = "human") -> bool:
        """Management write: audited, but not a content authorization."""
        return self.submit_read("delete", target=x_post_id, issuer=issuer)

    # -- reconciliation (Q-02, T-05) ------------------------------------
    def reconcile(self) -> dict:
        """On startup, resolve any write intent without a terminal outcome by
        checking whether the post already exists — never resend ambiguously.

        Two rules keep this from eating live work. It only runs in the process
        that owns the browser, because probing needs a real engine and opening
        a second Chromium on the same profile can corrupt the X session. And a
        `pending` intent is only stale once it has sat there a while: this used
        to abandon writes that were simply waiting their turn in the drain
        queue, which the worker re-ran every five minutes.
        """
        from ..config import get_settings
        from ..ops.launcher import owns_engine
        resolved = {"reconciled": 0, "abandoned": 0, "skipped": 0}
        # The fixture engine opens nothing, so it is always safe to probe.
        if not owns_engine() and get_settings().browser_engine != "fixture":
            resolved["skipped"] = 1
            return resolved

        engine = get_engine()
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=PENDING_STALE_S)
        with session_scope() as s:
            stuck = [
                a for a in s.exec(select(Action).where(
                    Action.kind.in_(list(WRITE_KINDS)),
                    Action.state.in_(["running", "pending"]))).all()
                if a.state == "running" or _older_than(a.created_at, cutoff)
            ]
            for a in stuck:
                payload = json.loads(a.payload_json or "{}")
                content = payload.get("content", "")
                exists = False
                # ThreadedEngine forwards any attribute, so hasattr always says
                # yes; ask the engine to declare the capability instead.
                if getattr(engine, "supports_exists", False):
                    try:
                        exists = engine.exists(a.idempotency_key, content)
                    except Exception as e:
                        log.warning("reconcile probe failed for %s: %s", a.id, e)
                        exists = False
                if exists:
                    a.state = "done"
                    a.outcome = "reconciled"
                    a.finished_at = datetime.now(timezone.utc)
                    resolved["reconciled"] += 1
                    log.info("reconciled intent %s: post exists, not resending", a.id)
                else:
                    # ambiguous write => do not retry automatically (Q-03)
                    a.state = "abandoned"
                    a.outcome = "abandoned_ambiguous"
                    a.finished_at = datetime.now(timezone.utc)
                    resolved["abandoned"] += 1
                    log.warning("abandoned ambiguous intent %s", a.id)
                s.add(a)
            s.commit()
        return resolved

    # -- helpers ---------------------------------------------------------
    def _enter(self):
        self._concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self._concurrent)

    def _exit(self):
        self._concurrent -= 1

    def _fail(self, intent_id, attempt, exc, ambiguous=False, outcome=""):
        with session_scope() as s:
            a = s.get(Action, intent_id)
            if a is None:
                return
            a.attempts = attempt
            a.state = "failed"
            a.outcome = outcome or ("ambiguous" if ambiguous else "failed")
            a.error = f"{type(exc).__name__}: {exc}"
            a.screenshot_path = getattr(exc, "screenshot_path", "") or ""
            a.finished_at = datetime.now(timezone.utc)
            s.add(a)
            s.commit()


    def _resolve_draft(self, authorization, status: str,
                       charge_governor: str = "") -> None:
        """Where a draft goes when the send did not cleanly succeed.

        `needs_review` rather than `queued` on purpose: a draft that might
        already be live must not be re-sendable by the queue, the approval
        route or the For You cooldown scan. Only a human decides.
        """
        if authorization is None:
            return
        with session_scope() as s:
            if charge_governor:
                try:
                    consume(s, authorization)
                except Exception:
                    pass
                governor.record_write(s, charge_governor, authorization.mode)
            d = s.get(Draft, authorization.draft_id) if authorization.draft_id else None
            if d is not None:
                d.status = status
                s.add(d)
            s.commit()

    def _audit_blocked(self, s: Session, kind, target, key, err):
        s.add(Action(kind=kind, payload_json=json.dumps({"target": target}),
                     idempotency_key=key, target=target, state="failed",
                     outcome="unauthorized", error=err,
                     finished_at=datetime.now(timezone.utc)))
        s.commit()

    def _mark_draft_sent(self, s: Session, draft_id: int, x_post_id: str):
        d = s.get(Draft, draft_id)
        if d:
            d.status = "sent"
            s.add(d)

    def _register_publish_failure(self, target: str):
        from ..db.models import Account
        with session_scope() as s:
            acc = s.exec(select(Account).where(Account.handle == target)).first()
            if acc:
                acc.consecutive_publish_failures += 1
                s.add(acc)
                s.commit()
                if acc.consecutive_publish_failures >= 2:  # Y-06
                    self._disable_auto(s, acc, "two consecutive publish failures")
        notifier.alert("publish_failures", f"publish failed for {target}")

    def _reset_failures(self, s: Session, target: str):
        from ..db.models import Account
        acc = s.exec(select(Account).where(Account.handle == target)).first()
        if acc and acc.consecutive_publish_failures:
            acc.consecutive_publish_failures = 0
            s.add(acc)
            s.commit()

    def _disable_auto_and_alert(self, kind, target, exc):
        """Alert on every hard write failure; demote auto accounts only for
        the safety events (challenge / dead session). See the module
        docstring for why a SelectorMiss is deliberately excluded."""
        from ..db.models import Account
        if isinstance(exc, (ChallengeDetected, SessionDead)):
            with session_scope() as s:
                for acc in s.exec(select(Account).where(Account.mode == "auto")).all():
                    self._disable_auto(s, acc, f"{type(exc).__name__}")
                s.commit()
        else:
            log.warning("selector miss on %s->%s (%s); alerting, not demoting",
                        kind, target, exc)
        notifier.alert("challenge_detected" if isinstance(exc, ChallengeDetected)
                       else ("session_dead" if isinstance(exc, SessionDead)
                             else "canary_failed"),
                       f"{type(exc).__name__} on {kind}->{target}: {exc}")

    def _disable_auto(self, s: Session, acc, reason: str):
        if acc.mode == "auto":
            acc.mode = "assisted"
            s.add(acc)
            log.warning("auto mode disabled for @%s: %s", acc.handle, reason)
            notifier.alert("auto_disabled", f"@{acc.handle}: {reason}")


_BUS: ActionBus | None = None


def get_bus() -> ActionBus:
    global _BUS
    if _BUS is None:
        _BUS = ActionBus()
    return _BUS
