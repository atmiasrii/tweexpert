"""The similarity guard must not re-embed the same history on every candidate.

Measured on a live evening: 6,631 embedding calls against 636 chat calls, and
sweeps 27 minutes apart when they were configured for 10. Every past reply was
being embedded again for every candidate, and past replies never change.
"""
from __future__ import annotations

from quill.db.models import Draft
from quill.persona import similarity


def _sent(session, *texts):
    for t in texts:
        session.add(Draft(kind="reply", final_text=t, status="sent",
                          mode_at_creation="auto"))
    session.commit()


def test_history_is_embedded_once_not_once_per_candidate(session, monkeypatch):
    _sent(session, "one past reply", "another past reply", "a third past reply")
    calls = []

    # Orthogonal vectors, so nothing matches and the loop runs to the end.
    space = {}

    class _LLM:
        def embed(self, text):
            calls.append(text)
            i = space.setdefault(text, len(space))
            return [1.0 if j == i else 0.0 for j in range(8)]

    monkeypatch.setattr(similarity, "LLM", _LLM)
    similarity.clear_embedding_cache()

    similarity.similarity_hit(session, "a brand new candidate")
    first = len(calls)
    assert first == 4, "one candidate plus three history entries"

    similarity.similarity_hit(session, "a different candidate")
    # Only the new candidate should cost a call; the history is unchanged.
    assert len(calls) - first == 1, f"history re-embedded: {calls[first:]}"


def test_the_same_candidate_twice_costs_nothing_extra(session, monkeypatch):
    _sent(session, "one past reply")
    calls = []

    class _LLM:
        def embed(self, text):
            calls.append(text)
            return [1.0, 0.0]

    monkeypatch.setattr(similarity, "LLM", _LLM)
    similarity.clear_embedding_cache()

    similarity.similarity_hit(session, "same text")
    n = len(calls)
    similarity.similarity_hit(session, "same text")
    assert len(calls) == n


def test_an_identical_reply_is_still_caught(session, monkeypatch):
    """Caching must not blunt the guard it is speeding up."""
    _sent(session, "constrained decoding holds the schema")

    class _LLM:
        def embed(self, text):
            # Same text embeds identically, so cosine is 1.0.
            return [float(sum(map(ord, text))), 1.0]

    monkeypatch.setattr(similarity, "LLM", _LLM)
    similarity.clear_embedding_cache()

    hit, why = similarity.similarity_hit(session, "constrained decoding holds the schema")
    assert hit is True
    assert why
