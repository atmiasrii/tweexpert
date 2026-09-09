"""Similarity guard (P-07). Cosine against the last 100 sent replies plus a
lexical n-gram overlap check. Repetitive phrasing across replies is a
documented detection signal, so anything above threshold is rejected."""
from __future__ import annotations

import json
from collections import OrderedDict

import numpy as np
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


# Text to vector, remembered. The history this guard compares against is the
# last hundred replies we have already sent, so their embeddings are identical
# on every call and were being recomputed for every candidate: 6,631 embedding
# calls in one evening against 636 chat calls, which stretched For You sweeps
# from the configured ten minutes to twenty-seven and was the real reason the
# day's target went unmet. Bounded, and keyed by the exact text.
_CACHE: "OrderedDict[str, np.ndarray]" = OrderedDict()
_CACHE_MAX = 512


def _embedding(text: str) -> np.ndarray:
    vec = _CACHE.get(text)
    if vec is None:
        vec = unpack(pack(LLM().embed(text)))
        _CACHE[text] = vec
        if len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    else:
        _CACHE.move_to_end(text)
    return vec


def clear_embedding_cache() -> None:
    _CACHE.clear()


def similarity_hit(session: Session, candidate: str) -> tuple[bool, str]:
    history = recent_sent_texts(session)
    if not history:
        return False, ""
    cvec = _embedding(candidate)
    for prev in history:
        cos = cosine(cvec, _embedding(prev))
        if cos >= SIMILARITY_COSINE_MAX:
            return True, f"cosine {cos:.2f} vs a recent reply"
        ng = ngram_overlap(candidate, prev, n=3)
        if ng >= SIMILARITY_NGRAM_MAX:
            return True, f"n-gram overlap {ng:.2f} vs a recent reply"
    return False, ""
