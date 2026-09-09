"""Structured JSON logs with rotation, tailable from the Ops tab (O-04)."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pythonjsonlogger import jsonlogger

_CONFIGURED = False
LOG_FILE: Path | None = None


def setup_logging(data_dir: Path, level: int = logging.INFO) -> Path:
    global _CONFIGURED, LOG_FILE
    log_file = data_dir / "quill.jsonl"
    LOG_FILE = log_file
    if _CONFIGURED:
        return log_file

    fmt = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "at", "levelname": "level", "name": "logger"},
    )
    root = logging.getLogger()
    root.setLevel(level)
    # Two libraries drown the log. httpx prints every model call, thousands a
    # day, and the trace records what those calls decided. APScheduler warns
    # each time a one-minute checker overlaps a ten-minute sweep, which is the
    # design, not a fault. Real errors from both still come through.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.executors").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.scheduler").setLevel(logging.ERROR)

    fh = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=5)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)

    _CONFIGURED = True
    return log_file


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
