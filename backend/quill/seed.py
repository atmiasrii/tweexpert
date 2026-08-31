"""Seed the database from committed fixtures so a fresh `docker compose up`
yields a working dashboard with a populated queue and shadow log (T-01)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from .config import get_settings
from .db.engine import init_db, session_scope
from .db.models import Account, Post, SavedSearch
from .logging_setup import get_logger, setup_logging
from .persona.corpus import corpus_size, import_samples

log = get_logger("quill.seed")


def seed(session: Session) -> dict:
    s = get_settings()

    # --- accounts ------------------------------------------------------
    accounts = json.loads((s.fixtures_dir / "accounts.json").read_text("utf-8"))
    modes = {"simonw": "assisted", "karpathy": "auto", "thorstenball": "shadow"}
    for a in accounts:
        if session.exec(select(Account).where(Account.handle == a["handle"])).first():
            continue
        mode = modes.get(a["handle"], "shadow")
        acc = Account(handle=a["handle"], display_name=a["display_name"],
                      tier=a["tier"], mode=mode,
                      shadow_started_at=datetime.now(timezone.utc) - timedelta(days=10)
                      if mode != "auto" else datetime.now(timezone.utc) - timedelta(days=10),
                      shadow_drafts_count=25, shadow_reviewed_count=25)
        session.add(acc)
    session.commit()

    # --- style corpus from the operator's archive ----------------------
    if corpus_size(session) == 0:
        archive = json.loads((s.fixtures_dir / "archive.json").read_text("utf-8"))
        import_samples(session, [{"text": p["text"], "metrics": {"likes": p.get("likes", 0)}}
                                 for p in archive["posts"]])

    # --- own posts for analytics --------------------------------------
    own = json.loads((s.fixtures_dir / "own_posts.json").read_text("utf-8"))
    for p in own:
        if session.exec(select(Post).where(Post.x_post_id == p["x_post_id"])).first():
            continue
        created = datetime.now(timezone.utc) - timedelta(hours=p.get("hours_ago", 24))
        session.add(Post(x_post_id=p["x_post_id"], author_handle=s.operator_handle,
                         text=p["text"], created_at=created, is_own=True,
                         kind=p.get("kind", "post"),
                         metrics_json=json.dumps({"category": p.get("category", ""),
                                                  **{k: p.get(k, 0) for k in
                                                     ("likes", "reposts", "replies", "views")}})))
    session.commit()

    # --- a saved search + follower sample ------------------------------
    if not session.exec(select(SavedSearch)).first():
        session.add(SavedSearch(query="local models", interval_s=3600))
    from .ops.analytics import sample_followers
    sample_followers(session, 1284)
    session.commit()

    return {"accounts": len(accounts), "corpus": corpus_size(session)}


def populate_pipeline(session: Session) -> dict:
    """Run one watch pass so the queue + shadow log have content."""
    from .pipeline import discovery, watcher
    summary = watcher.watch_all(session)
    discovery.run_saved_searches(session)
    discovery.ingest_notifications(session)      # V-04
    return summary


def main():
    s = get_settings()
    setup_logging(s.data_dir)
    init_db()
    with session_scope() as session:
        info = seed(session)
        summary = populate_pipeline(session)
    log.info("seeded: %s; pipeline: %s", info, summary)
    print(json.dumps({"seed": info, "pipeline": summary}, indent=2))


if __name__ == "__main__":
    main()
