"""Deterministic pre-filter (P-04). Kills generic-AI phrasing before it ever
reaches the critic — voice-card `never` list, a maintained tell-list, banned
openers, lone-emoji replies, and openers that paraphrase the parent (T-08)."""
from __future__ import annotations

import re

from ..defaults import BANNED_OPENERS, TELL_LIST
from .vectors import ngram_overlap

_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")
_HASHTAG = re.compile(r"#\w+")
_LINK = re.compile(r"https?://")
_DASH = re.compile(r"[—–]")   # em dash — / en dash – : the classic AI tell
_MAX_CHARS = 240


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _repetitive(c: str) -> bool:
    words = re.findall(r"[a-zA-Z']+", c.lower())
    if len(words) < 8:
        return False
    if len(set(words)) / len(words) < 0.5:
        return True
    grams = [tuple(words[i:i + 3]) for i in range(len(words) - 2)]
    if grams:
        from collections import Counter
        if Counter(grams).most_common(1)[0][1] >= 3:
            return True
    return False


def prefilter(candidate: str, parent_text: str, voice_card: dict) -> tuple[bool, str]:
    """Return (ok, reason). ok=False means kill this candidate."""
    c = candidate.strip()
    cl = _norm(c)
    if not cl:
        return False, "empty"

    # too long / repetitive (the degenerate-loop glitch) — hard reject
    if len(c) > _MAX_CHARS:
        return False, f"too long ({len(c)} chars)"
    if _repetitive(c):
        return False, "repetitive / degenerate output"

    # em/en dash is the single most recognisable AI-typing tell
    if _DASH.search(c):
        return False, "contains em/en dash"

    # no emoji at all — the voice card forbids them, and they read as AI-cheery
    stripped = _EMOJI.sub("", c).strip()
    if not stripped:
        return False, "emoji-only reply"
    if _EMOJI.search(c):
        return False, "contains emoji"

    # links + hashtags never allowed (also Y-02)
    if _LINK.search(c):
        return False, "contains link"
    if _HASHTAG.search(c):
        return False, "contains hashtag"

    # tell-list
    for phrase in TELL_LIST:
        if phrase in cl:
            return False, f"tell-list phrase: '{phrase}'"

    # banned openers
    for opener in BANNED_OPENERS:
        if cl.startswith(opener):
            return False, f"banned opener: '{opener.strip()}'"

    # voice-card never list
    for never in voice_card.get("never", []):
        nv = _norm(never).strip("'\"")
        if nv and nv in cl and len(nv) > 3:
            return False, f"voice-card never: '{never}'"

    # "not X, but Y" construction
    if re.search(r"\bnot\b.{1,40}\bbut\b", cl):
        return False, "'not X, but Y' construction"

    # rhetorical-question opener
    if cl.split(".")[0].strip().endswith("?") and cl.startswith(("isn't", "aren't",
            "don't", "doesn't", "why ", "what if", "ever notice")):
        return False, "rhetorical-question opener"

    # opener paraphrases the parent (first clause overlaps heavily)
    opener_clause = re.split(r"[.!?]", c)[0]
    if parent_text and ngram_overlap(opener_clause, parent_text, n=3) > 0.5:
        return False, "opener paraphrases parent"

    return True, "ok"
