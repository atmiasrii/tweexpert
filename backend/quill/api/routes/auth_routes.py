"""Auth endpoints (X-02)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlmodel import Session

from ...db.engine import get_session
from ...db.settings_store import get_setting, set_setting
from ...security import new_totp_secret, totp_uri
from ..auth import current_session_data, do_login, ensure_operator, logout, require_auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    password: str
    totp: str = ""


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response,
          session: Session = Depends(get_session)):
    ident = request.client.host if request.client else "unknown"
    csrf = do_login(session, response, ident, body.password, body.totp)
    return {"ok": True, "csrf": csrf}


@router.post("/logout")
def do_logout(response: Response, _=Depends(require_auth)):
    logout(response)
    return {"ok": True}


@router.get("/csrf")
def get_csrf(data: dict = Depends(current_session_data)):
    return {"csrf": data.get("csrf")}


@router.get("/status")
def status(request: Request, session: Session = Depends(get_session)):
    ensure_operator(session)
    from ..auth import _read_cookie
    return {"authenticated": _read_cookie(request) is not None,
            "totp_enrolled": get_setting(session, "totp_enrolled", False)}


@router.post("/totp/enroll")
def totp_enroll(_=Depends(require_auth), session: Session = Depends(get_session)):
    secret = new_totp_secret()
    set_setting(session, "totp_secret", secret)
    set_setting(session, "totp_enrolled", True)
    from ...config import get_settings
    return {"secret": secret,
            "uri": totp_uri(secret, get_settings().operator_handle)}
