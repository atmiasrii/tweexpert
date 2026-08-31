"""Watchlist + per-account mode (§18). Mode switch is guarded (Y-03, T-04)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ...db.engine import get_session
from ...db.models import Account, Draft
from ...pipeline.policy import shadow_complete
from ..auth import require_auth
from ..events import publish

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountBody(BaseModel):
    handle: str
    display_name: str = ""
    tier: str = "B"
    notes: str = ""


class ModeBody(BaseModel):
    mode: str


@router.get("")
def list_accounts(session: Session = Depends(get_session), _=Depends(require_auth)):
    out = []
    for a in session.exec(select(Account)).all():
        drafts = session.exec(select(Draft).where(Draft.account_id == a.id)).all()
        out.append({**a.model_dump(),
                    "draft_count": len(drafts),
                    "shadow_complete": shadow_complete(session, a)})
    return out


@router.post("")
def add_account(body: AccountBody, session: Session = Depends(get_session),
                _=Depends(require_auth)):
    if session.exec(select(Account).where(Account.handle == body.handle)).first():
        raise HTTPException(409, "account exists")
    acc = Account(handle=body.handle, display_name=body.display_name,
                  tier=body.tier, notes=body.notes, mode="shadow",
                  shadow_started_at=datetime.now(timezone.utc))
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


@router.patch("/{account_id}")
def update_account(account_id: int, body: AccountBody,
                   session: Session = Depends(get_session), _=Depends(require_auth)):
    acc = session.get(Account, account_id)
    if not acc:
        raise HTTPException(404)
    acc.display_name = body.display_name or acc.display_name
    acc.tier = body.tier
    acc.notes = body.notes
    session.add(acc)
    session.commit()
    return acc


@router.delete("/{account_id}")
def delete_account(account_id: int, session: Session = Depends(get_session),
                   _=Depends(require_auth)):
    acc = session.get(Account, account_id)
    if acc:
        session.delete(acc)
        session.commit()
    return {"ok": True}


@router.post("/{account_id}/mode")
def set_mode(account_id: int, body: ModeBody,
             session: Session = Depends(get_session), _=Depends(require_auth)):
    acc = session.get(Account, account_id)
    if not acc:
        raise HTTPException(404)
    if body.mode not in ("shadow", "assisted", "auto"):
        raise HTTPException(400, "invalid mode")
    # T-04 / Y-03: cannot enter auto before shadow period completes
    if body.mode == "auto" and not shadow_complete(session, acc):
        raise HTTPException(
            409, "shadow period not complete: needs configured days + reviewed drafts")
    acc.mode = body.mode
    session.add(acc)
    session.commit()
    publish("account_mode", {"account_id": account_id, "mode": body.mode})
    return acc
