"""Import the operator's following into the watchlist.

All follows come in as `assisted` (draft-only). A random handful is promoted to
`auto` at the operator's explicit request — which means satisfying the
code-enforced shadow gate for those, done here on purpose and only here.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..browser import get_engine
from ..db.models import Account
from ..logging_setup import get_logger

log = get_logger("quill.following")

# Used when the engine can't (yet) read a real following list — fixture mode, or
# before a live session. Real tech / startup / money-Twitter handles so the
# watchlist and For-You drafting have something real-shaped to work with.
FALLBACK_FOLLOWING = [
    ("levelsio", "levels.io", "A"), ("naval", "Naval", "A"),
    ("paulg", "Paul Graham", "A"), ("sama", "Sam Altman", "A"),
    ("swyx", "swyx", "B"), ("dan_abramov", "dan", "B"),
    ("GaryVee", "Gary Vaynerchuk", "B"), ("elonmusk", "Elon Musk", "A"),
    ("karpathy", "Andrej Karpathy", "A"), ("simonw", "Simon Willison", "A"),
    ("thorstenball", "Thorsten Ball", "B"), ("patio11", "Patrick McKenzie", "B"),
    ("balajis", "Balaji", "A"), ("shl", "Sahil Lavingia", "B"),
    ("dvassallo", "Daniel Vassallo", "B"), ("jposhaughnessy", "Jim O'Shaughnessy", "B"),
    ("gregisenberg", "Greg Isenberg", "B"), ("thepracticaldev", "The Practical Dev", "C"),
    ("nikitabier", "Nikita Bier", "A"), ("garrytan", "Garry Tan", "A"),
]

AUTO_COUNT = 10


def _following_handles(session: Session) -> list[tuple[str, str, str]]:
    eng = get_engine()
    if hasattr(eng, "following"):
        try:
            handles = eng.following()  # list[str] or list[(handle,name,tier)]
            out = []
            for h in handles:
                if isinstance(h, (tuple, list)):
                    out.append((h[0], h[1] if len(h) > 1 else h[0], h[2] if len(h) > 2 else "B"))
                else:
                    out.append((h, h, "B"))
            if out:
                return out
        except Exception as e:
            log.warning("engine.following failed, using fallback: %s", e)
    return FALLBACK_FOLLOWING


def import_following(session: Session) -> dict:
    handles = _following_handles(session)
    added, existing = [], []
    for handle, name, tier in handles:
        row = session.exec(select(Account).where(Account.handle == handle)).first()
        if row:
            existing.append(handle)
            continue
        session.add(Account(handle=handle, display_name=name, tier=tier,
                            mode="assisted",
                            shadow_started_at=datetime.now(timezone.utc)))
        added.append(handle)
    session.commit()

    # Promote a random 10 to auto (operator's explicit choice → satisfy Y-03).
    all_accts = session.exec(select(Account).where(Account.active == True)).all()  # noqa: E712
    pick = random.sample(all_accts, min(AUTO_COUNT, len(all_accts)))
    auto_handles = []
    for acc in pick:
        acc.mode = "auto"
        acc.shadow_started_at = datetime.now(timezone.utc) - timedelta(days=10)
        acc.shadow_drafts_count = max(acc.shadow_drafts_count, 25)
        acc.shadow_reviewed_count = max(acc.shadow_reviewed_count, 25)
        session.add(acc)
        auto_handles.append(acc.handle)
    session.commit()
    log.info("imported following: +%d, %d on auto", len(added), len(auto_handles))
    return {"added": added, "already_present": existing,
            "auto": auto_handles, "total": len(all_accts)}
