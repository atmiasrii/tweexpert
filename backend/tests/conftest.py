"""Test harness. Fixture engine, temp DB, no network/GPU (T-01 conditions)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Configure environment BEFORE importing quill so settings pick it up.
_TMP = Path(tempfile.mkdtemp(prefix="quill-test-"))
os.environ["QUILL_DATA_DIR"] = str(_TMP)
os.environ["QUILL_DB_PATH"] = str(_TMP / "quill.db")
os.environ["QUILL_DEBUG_DIR"] = str(_TMP / "debug")
os.environ["QUILL_BACKUP_DIR"] = str(_TMP / "backups")
os.environ["QUILL_PROFILE_DIR"] = str(_TMP / "profile")
os.environ["QUILL_BROWSER_ENGINE"] = "fixture"
os.environ["QUILL_LLM_AVAILABLE"] = "false"
os.environ["QUILL_LOGIN_PASSWORD"] = "test-password"
os.environ["QUILL_SECRET_KEY"] = "test-secret-key"

from quill.config import get_settings  # noqa: E402
get_settings.cache_clear()

from quill.browser import set_engine  # noqa: E402
from quill.browser.fixture_engine import FixtureEngine  # noqa: E402
from quill.db.engine import init_db, reset_engine, session_scope  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    """Fresh schema + fresh fixture engine per test."""
    s = get_settings()
    reset_engine()
    for f in s.db_path.parent.glob("quill.db*"):
        try:
            f.unlink(missing_ok=True)
        except PermissionError:
            pass
    init_db()
    set_engine(FixtureEngine())
    # reset the process-wide bus so instrumentation is clean
    import quill.bus.action_bus as ab
    ab._BUS = None
    from quill.notify import notifier
    notifier.clear()
    yield


@pytest.fixture
def session():
    with session_scope() as s:
        yield s


@pytest.fixture
def engine():
    from quill.browser import get_engine
    return get_engine()


@pytest.fixture
def seeded(session):
    from quill.seed import seed
    seed(session)
    return session


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from quill.api.app import create_app
    app = create_app(run_startup=False)
    with session_scope() as s:
        from quill.api.auth import ensure_operator
        ensure_operator(s)
    c = TestClient(app)
    return c


@pytest.fixture
def auth_client(client):
    """Logged-in client with CSRF header set."""
    r = client.post("/api/auth/login", json={"password": "test-password"})
    assert r.status_code == 200, r.text
    csrf = r.json()["csrf"]
    client.headers.update({"X-CSRF-Token": csrf})
    return client
