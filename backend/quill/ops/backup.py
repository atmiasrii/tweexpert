"""Nightly backup of database, voice card and browser profile (D-03, E-04)."""
from __future__ import annotations

import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_settings
from ..db.engine import session_scope
from ..logging_setup import get_logger
from ..persona.voicecard import load_voice_card

log = get_logger("quill.backup")


def run_backup() -> Path:
    s = get_settings()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = s.backup_dir / f"quill-backup-{ts}.tar.gz"
    s.backup_dir.mkdir(parents=True, exist_ok=True)

    # dump voice card alongside
    with session_scope() as sess:
        card = load_voice_card(sess)
    card_path = s.data_dir / "voice_card.json"
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")

    with tarfile.open(dest, "w:gz") as tar:
        if s.db_path.exists():
            tar.add(s.db_path, arcname="quill.db")
        tar.add(card_path, arcname="voice_card.json")
        if s.profile_dir.exists():
            tar.add(s.profile_dir, arcname="chrome-profile")  # E-04

    # E-04 / X-04: encrypt the archive at rest with the operator passphrase key.
    enc = _encrypt_file(dest, s.operator_passphrase)
    if enc:
        dest.unlink(missing_ok=True)
        dest = enc

    _prune(s.backup_dir, s.backup_retention)
    log.info("backup written: %s", dest)
    return dest


def _encrypt_file(path: Path, passphrase: str) -> Path | None:
    try:
        import base64
        import hashlib
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode()).digest())
        token = Fernet(key).encrypt(path.read_bytes())
        out = path.with_suffix(path.suffix + ".enc")
        out.write_bytes(token)
        return out
    except Exception as e:  # pragma: no cover
        log.warning("backup encryption failed, keeping plaintext: %s", e)
        return None


def _prune(backup_dir: Path, keep: int) -> None:
    backups = sorted(backup_dir.glob("quill-backup-*.tar.gz*"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        old.unlink(missing_ok=True)


def list_backups() -> list[dict]:
    s = get_settings()
    out = []
    for p in sorted(s.backup_dir.glob("quill-backup-*.tar.gz*"),
                    key=lambda p: p.stat().st_mtime, reverse=True):
        out.append({"name": p.name, "size": p.stat().st_size,
                    "at": datetime.fromtimestamp(p.stat().st_mtime,
                                                 tz=timezone.utc).isoformat()})
    return out
