"""Similarity guard (P-07). Cosine against the last 100 sent replies plus a
lexical n-gram overlap check. Repetitive phrasing across replies is a
documented detection signal, so anything above threshold is rejected."""
from __future__ import annotations

import json

from sqlmodel import Session, select

from ..db.models import Draft
from ..defaults import (SIMILARITY_COSINE_MAX, SIMILARITY_HISTORY,
                        SIMILARITY_NGRAM_MAX)
from .llm import LLM
from .vectors import cosine, ngram_overlap, pack, unpack


def recent_sent_texts(session: Session, limit: int = SIMILARITY_HISTORY) -> list[str]:
    rows = session.exec(
        select(Draft).where(Draft.status == "sent")
        .order_by(Draft.created_at.desc()).limit(limit)).all()
    return [r.final_text for r in rows if r.final_text]


def similarity_hit(session: Session, candidate: str) -> tuple[bool, str]:
    history = recent_sent_texts(session)
    if not history:
        return False, ""
    llm = LLM()
    cvec = unpack(pack(llm.embed(candidate)))
    for prev in history:
        cos = cosine(cvec, unpack(pack(llm.embed(prev))))
        if cos >= SIMILARITY_COSINE_MAX:
            return True, f"cosine {cos:.2f} vs a recent reply"
        ng = ngram_overlap(candidate, prev, n=3)
        if ng >= SIMILARITY_NGRAM_MAX:
            return True, f"n-gram overlap {ng:.2f} vs a recent reply"
    return False, ""
