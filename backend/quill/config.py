"""Central configuration. One .env plus a settings table (A-05).

Model access is through an OpenAI-compatible base URL so Ollama, vLLM or
anything else can be swapped by config — never hardcode a provider (A-03).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class Settings(BaseSettings):
    # env_file is resolved against the working directory, so a bare ".env"
    # silently loads nothing when the process starts from anywhere but the
    # repo root. Pin it to the repo so every entry point sees the same config.
    model_config = SettingsConfigDict(
        env_prefix="QUILL_", env_file=(REPO_ROOT / ".env", ".env"),
        extra="ignore"
    )

    # --- identity -------------------------------------------------------
    operator_handle: str = "barryallendgx"
    operator_timezone: str = "Asia/Kolkata"

    # Login password. Declared so .env is actually read for it; None means
    # "not configured", which leaves whatever is already stored alone.
    login_password: str | None = None

    # --- storage --------------------------------------------------------
    data_dir: Path = DATA_DIR
    db_path: Path = DATA_DIR / "quill.db"
    debug_dir: Path = DATA_DIR / "debug"          # screenshots + html (E-08)
    backup_dir: Path = DATA_DIR / "backups"       # nightly backup (D-03)
    backup_retention: int = 7
    profile_dir: Path = DATA_DIR / "chrome-profile"
    fixtures_dir: Path = REPO_ROOT / "fixtures"
    selectors_path: Path = REPO_ROOT / "selectors" / "selectors.yaml"

    # --- engine selection ----------------------------------------------
    # "fixture" runs with no session, no network, no GPU (I-05, T-01).
    # "playwright" drives a real Chromium. Extension reports come in via API.
    browser_engine: str = "fixture"
    # When set, the api process enqueues writes and the browser process (the
    # sole engine owner) drains them (A-02). Off for single-process/tests.
    defer_writes: bool = False

    # --- models (OpenAI-compatible, A-03/Z-01) -------------------------
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    draft_model: str = "qwen3:30b-a3b"
    critic_model: str = "qwen3:32b"
    embed_model: str = "nomic-embed-text"
    llm_available: bool = False  # doctor/health flips this; gates drafting (O-05)

    # --- security (§22) -------------------------------------------------
    bind_host: str = "127.0.0.1"                  # loopback only (X-01)
    bind_port: int = 8000
    secret_key: str = "dev-only-change-me"        # session signing
    operator_passphrase: str = "dev-passphrase"   # derives at-rest key (X-04)
    extension_shared_secret: str = "dev-extension-secret"  # A-X1
    login_rate_limit: int = 5                     # attempts before lockout
    login_lockout_seconds: int = 300

    # --- notifications (§16) -------------------------------------------
    ntfy_base_url: str = "https://ntfy.sh"
    ntfy_topic: str = ""                          # empty = disabled
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    public_base_url: str = "http://127.0.0.1:8000"

    # --- browser debug surface (X-03) ----------------------------------
    vnc_url: str = "http://127.0.0.1:6080/vnc.html"

    @property
    def is_fixture(self) -> bool:
        return self.browser_engine == "fixture"


@lru_cache
def get_settings() -> Settings:
    s = get_settings_uncached()
    for p in (s.data_dir, s.debug_dir, s.backup_dir):
        p.mkdir(parents=True, exist_ok=True)
    return s


def get_settings_uncached() -> Settings:
    return Settings()
