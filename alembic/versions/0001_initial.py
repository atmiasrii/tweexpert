"""initial schema — all tables + FTS5 (D-01, D-02)

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-31
"""
from __future__ import annotations

from alembic import op
from sqlmodel import SQLModel

import quill.db.models  # noqa: F401  (register tables on the shared metadata)
from quill.db.engine import FTS_SETUP

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind)
    for stmt in FTS_SETUP:
        op.execute(stmt)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP TABLE IF EXISTS post_fts")
    op.execute("DROP TABLE IF EXISTS style_fts")
    SQLModel.metadata.drop_all(bind)
