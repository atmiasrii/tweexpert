"""ActionAuthorization — the required typed parameter on every write (Y-01).

Issued by a human tap or by the policy engine. Single-use, expiring, audited.
There is no code path to a write without one; attempting it is a hard error
that is logged and alerted (Y-01, T-02).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel
from sqlmodel import Session

from ..db.models import Authorization
from ..defaults import AUTHORIZATION_TTL_S


class ActionAuthorization(BaseModel):
    """Typed token carried on every write action."""
    id: int
    draft_id: int
    issuer: Literal["human", "policy"]
    mode: str
    reasons: list[str]
    issued_at: datetime
    expires_at: datetime


class AuthorizationError(Exception):
    """Missing / expired / already-consumed authorization (Y-01)."""


def issue(session: Session, draft_id: int, issuer: str, mode: str,
          reasons: list[str], ttl_s: int = AUTHORIZATION_TTL_S) -> ActionAuthorization:
    now = datetime.now(timezone.utc)
    row = Authorization(
        draft_id=draft_id, issuer=issuer, mode=mode,
        reasons_json=json.dumps(reasons),
        issued_at=now, expires_at=now + timedelta(seconds=ttl_s),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_model(row)


def consume(session: Session, authorization: ActionAuthorization) -> Authorization:
    """Single-use: mark consumed. Raises AuthorizationError if invalid."""
    row = session.get(Authorization, authorization.id)
    if row is None:
        raise AuthorizationError("authorization not found")
    if row.consumed_at is not None:
        raise AuthorizationError("authorization already consumed (single-use)")
    now = datetime.now(timezone.utc)
    exp = row.expires_at
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp is not None and exp < now:
        raise AuthorizationError("authorization expired")
    row.consumed_at = now
    session.add(row)
    session.commit()
    return row


def validate_unconsumed(session: Session, authorization: ActionAuthorization | None) -> None:
    """Check without consuming (used by the bus before executing)."""
    if authorization is None:
        raise AuthorizationError("write attempted with no ActionAuthorization")
    row = session.get(Authorization, authorization.id)
    if row is None:
        raise AuthorizationError("authorization not found")
    if row.consumed_at is not None:
        raise AuthorizationError("authorization already consumed (single-use)")
    exp = row.expires_at
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp is not None and exp < datetime.now(timezone.utc):
        raise AuthorizationError("authorization expired")


def _to_model(row: Authorization) -> ActionAuthorization:
    return ActionAuthorization(
        id=row.id, draft_id=row.draft_id, issuer=row.issuer, mode=row.mode,
        reasons=json.loads(row.reasons_json), issued_at=row.issued_at,
        expires_at=row.expires_at,
    )
