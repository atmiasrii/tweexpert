"""FastAPI app assembly (§18). Loopback bind + non-loopback warning (X-01)."""
from __future__ import annotations

import socket
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config import get_settings
from ..db.engine import init_db, session_scope
from ..governor.governor import GovernorRefusal
from ..logging_setup import get_logger, setup_logging
from .routes import (accounts, analytics_routes, auth_routes, autopilot,
                     extension_routes, governor_routes, launch_routes,
                     live_routes, notify_routes, ops_routes, persona_routes,
                     studio)

log = get_logger("quill.api")


def create_app(run_startup: bool = True) -> FastAPI:
    s = get_settings()
    setup_logging(s.data_dir)
    app = FastAPI(title="Quill", version="1.0", docs_url="/api/docs")

    # Extension talks over localhost only; dashboard shares origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    for r in (auth_routes.router, accounts.router, autopilot.router,
              studio.router, persona_routes.router, analytics_routes.router,
              analytics_routes.export, governor_routes.router, ops_routes.router,
              ops_routes.events_router, notify_routes.router,
              extension_routes.router, launch_routes.router,
              live_routes.router):
        app.include_router(r)

    # A governor refusal is the safeguard working, not a server fault. Without
    # this it surfaced as a 500 and the dashboard could not say which gate
    # stopped the write.
    @app.exception_handler(GovernorRefusal)
    async def _refusal(request: Request, exc: GovernorRefusal):
        log.info("write refused by the governor: %s", exc)
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get("/api/ping")
    def ping():
        return {"ok": True, "service": "quill"}

    _mount_frontend(app)

    if run_startup:
        @app.on_event("startup")
        def _startup():
            init_db()
            _warn_if_public(s)
            from ..ops.reconcile import startup_reconcile
            from ..api.auth import ensure_operator, sync_login_password
            with session_scope() as sess:
                ensure_operator(sess)
                if sync_login_password(sess):
                    log.info("login password updated from .env")
                startup_reconcile(sess)          # O-03
            log.info("Quill API started (engine=%s)", s.browser_engine)

    return app


def _warn_if_public(s) -> None:
    if s.bind_host not in ("127.0.0.1", "localhost", "::1"):
        log.warning("SECURITY: bound to %s (not loopback). Use a tunnel (X-01).",
                    s.bind_host)


def _mount_frontend(app: FastAPI) -> None:
    dist = Path(__file__).resolve().parents[2].parent / "frontend" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(dist / "index.html")

        @app.get("/{path:path}")
        def spa(path: str):
            target = dist / path
            if target.exists() and target.is_file():
                return FileResponse(target)
            return FileResponse(dist / "index.html")
    else:
        @app.get("/")
        def index_placeholder():
            return {"ok": True, "note": "frontend not built; run `npm run build` in /frontend"}


app = create_app()
