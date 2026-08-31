"""SQLite in WAL mode with FTS5 (A-01, D-01)."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from ..config import get_settings
from . import models as _models  # noqa: F401  (register tables on metadata)

_engine: Engine | None = None


def _configure_sqlite(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


def reset_engine() -> None:
    """Dispose the pooled connections (needed before deleting the DB file on
    Windows, and to re-read a changed db_path in tests)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        s = get_settings()
        s.db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{s.db_path}",
            connect_args={"check_same_thread": False},
        )
        event.listen(_engine, "connect", _configure_sqlite)
    return _engine


FTS_SETUP = [
    # FTS5 over post text (D-01)
    """CREATE VIRTUAL TABLE IF NOT EXISTS post_fts USING fts5(
         text, author_handle, content='post', content_rowid='id')""",
    """CREATE TRIGGER IF NOT EXISTS post_ai AFTER INSERT ON post BEGIN
         INSERT INTO post_fts(rowid, text, author_handle)
         VALUES (new.id, new.text, new.author_handle); END""",
    """CREATE TRIGGER IF NOT EXISTS post_ad AFTER DELETE ON post BEGIN
         INSERT INTO post_fts(post_fts, rowid, text, author_handle)
         VALUES('delete', old.id, old.text, old.author_handle); END""",
    """CREATE TRIGGER IF NOT EXISTS post_au AFTER UPDATE ON post BEGIN
         INSERT INTO post_fts(post_fts, rowid, text, author_handle)
         VALUES('delete', old.id, old.text, old.author_handle);
         INSERT INTO post_fts(rowid, text, author_handle)
         VALUES (new.id, new.text, new.author_handle); END""",
    # FTS5 over style_sample text (D-01)
    """CREATE VIRTUAL TABLE IF NOT EXISTS style_fts USING fts5(
         text, content='style_sample', content_rowid='id')""",
    """CREATE TRIGGER IF NOT EXISTS style_ai AFTER INSERT ON style_sample BEGIN
         INSERT INTO style_fts(rowid, text) VALUES (new.id, new.text); END""",
]


def init_db() -> None:
    """Create tables + FTS. Alembic owns migrations (D-02); this is the
    idempotent bootstrap used at startup and in tests."""
    eng = get_engine()
    SQLModel.metadata.create_all(eng)
    with eng.begin() as conn:
        for stmt in FTS_SETUP:
            conn.execute(text(stmt))


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine()) as s:
        yield s


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as s:
        yield s
