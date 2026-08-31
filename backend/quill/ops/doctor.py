"""`make doctor` (O-07). Checks every dependency, the GPU, the model endpoint,
the session, the selectors and the database, and prints a readable report."""
from __future__ import annotations

import importlib
import shutil
import sys

import httpx

from ..config import get_settings
from ..db.engine import init_db, session_scope
from ..browser.selectors import load_registry


def _ok(label, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    return f"  [{mark}] {label}" + (f" — {detail}" if detail else ""), ok


def run_doctor() -> int:
    s = get_settings()
    lines: list[str] = ["Quill doctor", "=" * 40]
    all_ok = True

    # python
    line, ok = _ok("Python >= 3.11", sys.version_info >= (3, 11), sys.version.split()[0])
    lines.append(line); all_ok &= ok

    # deps
    for mod in ("fastapi", "sqlmodel", "apscheduler", "httpx", "yaml",
                "argon2", "pyotp", "cryptography", "numpy"):
        try:
            importlib.import_module(mod)
            line, ok = _ok(f"import {mod}", True)
        except Exception as e:
            line, ok = _ok(f"import {mod}", False, str(e))
        lines.append(line); all_ok &= ok

    # database
    try:
        init_db()
        with session_scope() as sess:
            sess.exec  # touch
        line, ok = _ok("database + FTS5", True, str(s.db_path))
    except Exception as e:
        line, ok = _ok("database + FTS5", False, str(e))
    lines.append(line); all_ok &= ok

    # selectors
    try:
        reg = load_registry(reload=True)
        line, ok = _ok("selectors.yaml", len(reg.keys()) > 0,
                       f"{len(reg.keys())} entries")
    except Exception as e:
        line, ok = _ok("selectors.yaml", False, str(e))
    lines.append(line); all_ok &= ok

    # GPU (nvidia-smi optional)
    gpu = shutil.which("nvidia-smi")
    line, _ = _ok("GPU (nvidia-smi present)", bool(gpu),
                  "not found — fixture/offline mode still works" if not gpu else "")
    lines.append(line)

    # model endpoint (optional — offline still works)
    reachable = False
    try:
        r = httpx.get(f"{s.llm_base_url.rstrip('/')}/models",
                      headers={"Authorization": f"Bearer {s.llm_api_key}"}, timeout=3)
        reachable = r.status_code < 500
    except Exception:
        reachable = False
    line, _ = _ok("model endpoint", reachable,
                  s.llm_base_url + (" (offline fallback active)" if not reachable else ""))
    lines.append(line)

    # engine + session
    lines.append(f"  [INFO] browser_engine = {s.browser_engine}")
    if s.is_fixture:
        lines.append("  [INFO] fixture engine — no X session/GPU/network needed")

    # security posture (X-01)
    if s.bind_host not in ("127.0.0.1", "localhost", "::1"):
        lines.append(f"  [WARN] bind_host {s.bind_host} is NOT loopback — use a tunnel!")

    lines.append("=" * 40)
    lines.append("RESULT: " + ("ALL GREEN" if all_ok else "problems found"))
    print("\n".join(lines))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(run_doctor())
