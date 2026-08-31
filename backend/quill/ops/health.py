"""Heartbeats, watchdog, health rows (O-02)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..db.models import Health, Heartbeat
from ..defaults import WATCHDOG_STALE_S
from ..notify import notifier


def beat(session: Session, process: str) -> None:
    row = session.get(Heartbeat, process)
    now = datetime.now(timezone.utc)
    if row is None:
        session.add(Heartbeat(process=process, at=now))
    else:
        row.at = now
        session.add(row)
    session.commit()


def stale_processes(session: Session) -> list[str]:
    now = datetime.now(timezone.utc)
    stale = []
    for hb in session.exec(select(Heartbeat)).all():
        at = hb.at.replace(tzinfo=timezone.utc) if hb.at.tzinfo is None else hb.at
        if (now - at).total_seconds() > WATCHDOG_STALE_S:
            stale.append(hb.process)
    return stale


def watchdog(session: Session) -> list[str]:
    stale = stale_processes(session)
    for proc in stale:
        notifier.alert("worker_down", f"heartbeat stale for '{proc}'")
    return stale


def record_health(session: Session, session_ok: bool, canary_ok: bool,
                  worker_ok: bool, latency_ms: int = 0, note: str = "") -> Health:
    h = Health(session_ok=session_ok, canary_ok=canary_ok, worker_ok=worker_ok,
               latency_ms=latency_ms, note=note)
    session.add(h)
    session.commit()
    session.refresh(h)
    return h


def latest_health(session: Session) -> Health | None:
    return session.exec(select(Health).order_by(Health.at.desc())).first()
