"""Single-user auth (X-02). Argon2id password + optional TOTP second factor,
signed HttpOnly/Secure/SameSite=Strict session cookie, CSRF on mutations,
rate-limited login with lockout. Extension authenticates over localhost with a
per-install shared secret (A-X1)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeSerializer
from sqlmodel import Session

from ..config import get_settings
from ..db.engine import get_session
from ..db.settings_store import get_setting, set_setting
from ..security import (LoginLimiter, hash_password, make_csrf_token,
                        verify_password, verify_totp)

COOKIE = "quill_session"
_limiter: LoginLimiter | None = None


def limiter() -> LoginLimiter:
    global _limiter
    if _limiter is None:
        s = get_settings()
        _limiter = LoginLimiter(s.login_rate_limit, s.login_lockout_seconds)
    return _limiter


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().secret_key, salt="quill-session")


def ensure_operator(session: Session) -> None:
    """First-run: seed a password hash if none exists (from .env or default)."""
    if get_setting(session, "password_hash") is None:
        pw = get_settings().login_password or "quill-dev-password"
        set_setting(session, "password_hash", hash_password(pw))
        set_setting(session, "totp_enrolled", False)


def sync_login_password(session: Session) -> bool:
    """Make QUILL_LOGIN_PASSWORD in .env the source of truth, applied at startup.

    Without this, the password is hashed into the settings table on first run
    and every later edit of .env is silently ignored: the operator changes the
    file, restarts, and is told the credentials are invalid. There is no
    change-password flow anywhere else, so the file is the only way to set one.

    Only ever acts when the value is explicitly configured, so an unset or
    removed variable can never reset a working password to the default.
    Returns True when the stored hash was replaced.
    """
    pw = get_settings().login_password
    if not pw:
        return False
    stored = get_setting(session, "password_hash")
    if stored and verify_password(stored, pw):
        return False
    set_setting(session, "password_hash", hash_password(pw))
    return True


def do_login(session: Session, response: Response, ident: str,
             password: str, totp: str = "") -> str:
    lim = limiter()
    if lim.locked(ident):
        raise HTTPException(429, "locked out, try again later")
    ensure_operator(session)
    ph = get_setting(session, "password_hash")
    ok = verify_password(ph, password)
    if ok and get_setting(session, "totp_enrolled", False):
        secret = get_setting(session, "totp_secret", "")
        ok = ok and verify_totp(secret, totp)
    if not ok:
        lim.record_fail(ident)
        raise HTTPException(401, "invalid credentials")
    lim.record_success(ident)
    csrf = make_csrf_token()
    token = _serializer().dumps({"uid": "operator", "csrf": csrf})
    secure = get_settings().public_base_url.startswith("https")
    response.set_cookie(COOKIE, token, httponly=True, secure=secure,
                        samesite="strict", max_age=7 * 24 * 3600)
    return csrf


def _read_cookie(request: Request) -> dict | None:
    raw = request.cookies.get(COOKIE)
    if not raw:
        return None
    try:
        return _serializer().loads(raw)
    except BadSignature:
        return None


def current_session_data(request: Request) -> dict:
    data = _read_cookie(request)
    if not data:
        raise HTTPException(401, "not authenticated")
    return data


def require_auth(request: Request) -> dict:
    """Auth + CSRF for mutations (X-02, T-13)."""
    data = current_session_data(request)
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        header = request.headers.get("X-CSRF-Token", "")
        if not header or header != data.get("csrf"):
            raise HTTPException(403, "CSRF token missing or invalid")
    return data


def require_auth_or_extension(request: Request,
                              session: Session = Depends(get_session)) -> dict:
    """Allow the local extension via shared secret (localhost only)."""
    ext = request.headers.get("X-Extension-Secret", "")
    if ext:
        host = (request.client.host if request.client else "")
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise HTTPException(403, "extension must be local")
        if ext == get_settings().extension_shared_secret:
            return {"uid": "extension"}
        raise HTTPException(403, "bad extension secret")
    return require_auth(request)


def logout(response: Response) -> None:
    response.delete_cookie(COOKIE)
