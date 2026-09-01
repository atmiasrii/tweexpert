"""Live mode: one control that starts the unattended work (S21).

Start is deliberately allowed even when checks are outstanding. It brings up
everything it can and the status payload names what is still missing, which is
more useful than a disabled button with no explanation.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ...db.engine import get_session
from ...ops import launcher
from ..auth import require_auth

router = APIRouter(prefix="/api/launch", tags=["launch"])


@router.get("")
def status(session: Session = Depends(get_session), _=Depends(require_auth)):
    return launcher.status(session)


@router.post("/start")
def start(session: Session = Depends(get_session),
          _=Depends(require_auth)):
    """Go live: hand the engine to the browser process and start the schedulers."""
    result = launcher.start(session)
    result["status"] = launcher.status(session)
    return result


@router.post("/stop")
def stop(session: Session = Depends(get_session),
         _=Depends(require_auth)):
    """Stop the unattended processes. Nothing queued or drafted is lost."""
    result = launcher.stop(session)
    result["status"] = launcher.status(session)
    return result


@router.post("/login")
def login(session: Session = Depends(get_session),
          _=Depends(require_auth)):
    """Open a real browser window for a by-hand X sign-in (E-02)."""
    try:
        return launcher.open_login(session)
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
