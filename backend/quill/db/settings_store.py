"""Runtime settings table (A-05). Falls back to defaults.py constants."""
from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from .models import Setting


def get_setting(session: Session, key: str, default: Any = None) -> Any:
    row = session.get(Setting, key)
    if row is None:
        return default
    try:
        return json.loads(row.value_json)
    except json.JSONDecodeError:
        return default


def set_setting(session: Session, key: str, value: Any) -> None:
    row = session.get(Setting, key)
    payload = json.dumps(value)
    if row is None:
        session.add(Setting(key=key, value_json=payload))
    else:
        row.value_json = payload
        session.add(row)
    session.commit()


def all_settings(session: Session) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in session.exec(select(Setting)).all():
        try:
            out[row.key] = json.loads(row.value_json)
        except json.JSONDecodeError:
            out[row.key] = None
    return out
