"""Startup reconciliation (O-03). Unfinished actions resolved, expired drafts
cleaned, governor day-state rebuilt, session verified before anything writes."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from ..bus.action_bus import get_bus
from ..db.models import Draft
from ..logging_setup import get_logger
from ..governor import governor

log = get_logger("quill.reconcile")


def startup_reconcile(session: Session) -> dict:
    # 1. unfinished actions (Q-02) — bus reconciles against X
    bus_result = get_bus().reconcile()

    # 2. expire stale drafts (R-03)
    now = datetime.now(timezone.utc)
    expired = 0
    for d in session.exec(select(Draft).where(Draft.status.in_(["queued"]))).all():
        exp = d.expires_at
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp and exp < now:
            d.status = "expired"
            session.add(d)
            expired += 1
    session.commit()

    # 3. rebuild governor day-state (kill switch persists across restarts, S-06)
    day = governor.get_day(session)
    from ..db.settings_store import get_setting
    if get_setting(session, "kill_switch", False):
        day.kill_switch = True
        session.add(day)
        session.commit()

    result = {"expired_drafts": expired, **bus_result,
              "kill_switch": day.kill_switch}
    log.info("startup reconcile: %s", result)
    return result
