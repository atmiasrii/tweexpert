"""The day's unattended run: start time, target, pace, restarts."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ...api.auth import require_auth
from ...db.engine import get_session
from ...db.settings_store import get_setting, set_setting
from ...ops import run_session

router = APIRouter(prefix="/api", tags=["run"])


@router.get("/run")
def run_status(session: Session = Depends(get_session), _=Depends(require_auth)):
    from ...ops import launcher
    rec = run_session.get_or_start(session)
    prog = run_session.progress(session, rec)
    return {
        "live": launcher.is_live(session),
        "day": rec["day"],
        "started_at": rec["started_at"],
        "deadline": rec["deadline"],
        "relax_level": rec.get("relax_level", 0),
        "restarts": rec.get("restarts", []),
        **prog,
    }


@router.put("/run/target")
def set_target(body: dict, session: Session = Depends(get_session),
               _=Depends(require_auth)):
    """Change what the day owes. Takes effect on the next supervisor tick."""
    rec = run_session.get_or_start(session)
    if "target" in body:
        rec["target"] = max(0, int(body["target"]))
        set_setting(session, "run_target", rec["target"])
    if "deadline" in body:
        rec["deadline"] = str(body["deadline"])
        set_setting(session, "run_deadline", rec["deadline"])
    run_session.save(session, rec)
    return {"target": rec["target"], "deadline": rec["deadline"]}


@router.get("/run/history")
def run_history(session: Session = Depends(get_session), _=Depends(require_auth)):
    return {"days": get_setting(session, run_session.RUN_HISTORY_KEY, [])}


# --- the per-run, per-tweet trace ------------------------------------------
@router.get("/runs")
def list_runs(limit: int = 40, session: Session = Depends(get_session),
              _=Depends(require_auth)):
    """Every sweep, newest first, with what it saw and what came of it."""
    from ...ops import trace
    return {"runs": trace.runs(session, limit=min(max(limit, 1), 200))}


@router.get("/runs/{run_id}")
def run_trace(run_id: int, session: Session = Depends(get_session),
              _=Depends(require_auth)):
    """One run: every post it looked at, with the journey and the reason."""
    from fastapi import HTTPException
    from ...ops import trace
    d = trace.run_detail(session, run_id)
    if d is None:
        raise HTTPException(404, "no such run")
    return d


@router.get("/trace/{x_post_id}")
def post_trace(x_post_id: str, session: Session = Depends(get_session),
               _=Depends(require_auth)):
    """Everything Quill ever did with one post, across runs."""
    from ...ops import trace
    return {"x_post_id": x_post_id, "runs": trace.for_post(session, x_post_id)}
