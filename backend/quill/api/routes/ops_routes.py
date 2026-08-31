"""Ops: health, audit log, live logs (SSE), VNC re-login (§18, §21)."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from ...config import get_settings
from ...db.engine import get_session
from ...db.models import Action, Draft, Health
from ...logging_setup import LOG_FILE
from ...ops import backup as backup_mod
from ...ops.health import latest_health
from ..auth import require_auth
from ..events import subscribe

router = APIRouter(prefix="/api/ops", tags=["ops"])


@router.get("/health")
def health(session: Session = Depends(get_session), _=Depends(require_auth)):
    h = latest_health(session)
    queue = len(session.exec(select(Draft).where(Draft.status == "queued")).all())
    from ...ops.health import stale_processes
    return {
        "session_ok": h.session_ok if h else True,
        "canary_ok": h.canary_ok if h else True,
        "worker_ok": h.worker_ok if h else True,
        "latency_ms": h.latency_ms if h else 0,
        "queue": queue,
        "stale_processes": stale_processes(session),
        "engine": get_settings().browser_engine,
    }


@router.get("/llm")
def llm_calls(_=Depends(require_auth)):
    """Generation latency + token counts per call (Z-03)."""
    from ...persona.llm import recent_calls
    return recent_calls(50)


@router.get("/actions")
def actions(kind: str = Query(default=""), outcome: str = Query(default=""),
            limit: int = 100, session: Session = Depends(get_session),
            _=Depends(require_auth)):
    q = select(Action).order_by(Action.created_at.desc()).limit(limit)
    rows = session.exec(q).all()
    out = []
    for a in rows:
        if kind and a.kind != kind:
            continue
        if outcome and a.outcome != outcome:
            continue
        out.append({"id": a.id, "kind": a.kind, "target": a.target,
                    "issuer": a.issuer, "state": a.state, "outcome": a.outcome,
                    "attempts": a.attempts, "error": a.error,
                    "screenshot_path": a.screenshot_path, "x_post_id": a.x_post_id,
                    "created_at": a.created_at.isoformat() if a.created_at else None})
    return out


@router.get("/logs")
async def logs(_=Depends(require_auth)):
    """Tail structured logs live over SSE (O-04)."""
    async def gen():
        path = LOG_FILE
        if not path or not path.exists():
            yield "event: log\ndata: {}\n\n"
            return
        with open(path, "r", encoding="utf-8") as f:
            # last ~50 lines then follow
            lines = f.readlines()[-50:]
            for ln in lines:
                yield f"event: log\ndata: {json.dumps({'line': ln.strip()})}\n\n"
            f.seek(0, 2)
            for _i in range(600):        # follow for a while
                where = f.tell()
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.5)
                    f.seek(where)
                else:
                    yield f"event: log\ndata: {json.dumps({'line': line.strip()})}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/login")
def open_vnc(_=Depends(require_auth)):
    """Open the VNC re-login surface (E-02, X-03). Loopback-only, time-limited."""
    s = get_settings()
    return {"vnc_url": s.vnc_url, "note": "loopback-only; reach via tunnel (X-03)",
            "expires_in_s": 600}


@router.get("/backups")
def backups(_=Depends(require_auth)):
    return backup_mod.list_backups()


# --- SSE events feed (U-07) --------------------------------------------
events_router = APIRouter(prefix="/api", tags=["events"])


@events_router.get("/events")
async def events(request: Request):
    async def gen():
        async for chunk in subscribe():
            if await request.is_disconnected():
                break
            yield chunk
    return StreamingResponse(gen(), media_type="text/event-stream")
