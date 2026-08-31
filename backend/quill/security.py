"""Auth + secrets at rest (§22).

- Argon2id password hashing + TOTP second factor (X-02).
- Secrets encrypted at rest with a key derived from the operator passphrase
  supplied at startup; never logged, never returned by any endpoint (X-04).
- Rate-limited login with lockout (X-02).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

_ph = PasswordHasher()


# --- password -----------------------------------------------------------
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


# --- TOTP ---------------------------------------------------------------
def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, handle: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=handle, issuer_name="Quill")


def verify_totp(secret: str, code: str) -> bool:
    if not secret:
        return True  # not yet enrolled
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=1)
    except Exception:
        return False


# --- secrets at rest (X-04) --------------------------------------------
def _key_from_passphrase(passphrase: str) -> bytes:
    digest = hashlib.sha256(passphrase.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class SecretBox:
    """Symmetric encryption for secrets stored in the DB. Key never persisted."""

    def __init__(self, passphrase: str):
        self._f = Fernet(_key_from_passphrase(passphrase))

    def encrypt(self, plaintext: str) -> str:
        return self._f.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        try:
            return self._f.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken:
            raise ValueError("cannot decrypt secret (wrong passphrase?)")


# --- signed single-use tokens for notification actions (K-04) ----------
def make_action_token(secret_key: str, draft_id: int, ttl_s: int) -> str:
    exp = int(time.time()) + ttl_s
    nonce = secrets.token_urlsafe(8)
    payload = f"{draft_id}.{exp}.{nonce}"
    sig = hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"


def verify_action_token(secret_key: str, token: str, draft_id: int) -> bool:
    try:
        did, exp, nonce, sig = token.split(".")
    except ValueError:
        return False
    payload = f"{did}.{exp}.{nonce}"
    expect = hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expect):
        return False
    if int(did) != draft_id:
        return False
    if int(exp) < int(time.time()):
        return False
    return True


# --- CSRF (X-02) --------------------------------------------------------
def make_csrf_token() -> str:
    return secrets.token_urlsafe(32)


# --- login rate limiter (X-02) -----------------------------------------
@dataclass
class LoginLimiter:
    limit: int
    lockout_s: int
    _attempts: dict[str, list[float]] = field(default_factory=dict)
    _locked: dict[str, float] = field(default_factory=dict)

    def locked(self, ident: str) -> bool:
        until = self._locked.get(ident, 0)
        if until and until > time.time():
            return True
        if until:
            self._locked.pop(ident, None)
        return False

    def record_fail(self, ident: str) -> None:
        now = time.time()
        window = [t for t in self._attempts.get(ident, []) if now - t < self.lockout_s]
        window.append(now)
        self._attempts[ident] = window
        if len(window) >= self.limit:
            self._locked[ident] = now + self.lockout_s

    def record_success(self, ident: str) -> None:
        self._attempts.pop(ident, None)
        self._locked.pop(ident, None)


def new_extension_secret() -> str:
    return secrets.token_urlsafe(24)
