"""Deterministic pre-filter (P-04). Kills generic-AI phrasing before it ever
reaches the critic — voice-card `never` list, a maintained tell-list, banned
openers, lone-emoji replies, and openers that paraphrase the parent (T-08)."""
from __future__ import annotations

import re

from ..defaults import BANNED_OPENERS, COMPLIMENT_WORDS, TELL_LIST
from .vectors import ngram_overlap

_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")
_HASHTAG = re.compile(r"#\w+")
_LINK = re.compile(r"https?://")
_MENTION = re.compile(r"(^|\s)@\w+")
_DASH = re.compile(r"[—–]")   # em dash — / en dash – : the classic AI tell
_CURLY = re.compile(r"[“”‘’]")
# "the best part: it learns" style reveal; a colon followed by a short clause
_COLON_REVEAL = re.compile(r"\b(the )?(best|worst|real|hard|fun|crazy|wild|scary) "
                           r"(part|thing|bit|truth|kicker)\s*:", re.I)
# maxed-out replies underperform; 180-220 is the mini-essay ceiling
_MAX_CHARS = 220
_COMPLIMENT_MAX = 60


def _compliment_only(cl: str) -> bool:
    """Short reply that is nothing but praise: no question, no content words
    beyond the compliment vocabulary."""
    if len(cl) > _COMPLIMENT_MAX or "?" in cl:
        return False
    words = re.findall(r"[a-z']+", cl)
    if not words:
        return False
    filler = {"i", "so", "this", "is", "a", "the", "it", "and", "to", "of", "you",
              "your", "that", "just", "really", "very", "such", "what", "one",
              "an", "with", "for", "man", "bro", "lol", "haha", "omg", "wow"}
    content = [w for w in words if w not in filler]
    if not content:
        return True
    praise = sum(1 for w in content if any(w.startswith(p.split()[0])
                                            for p in COMPLIMENT_WORDS))
    return praise >= max(1, len(content) - 1)


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


def prefilter(candidate: str, parent_text: str, voice_card: dict,
              archetype: str = "", strict: bool = True) -> tuple[bool, str]:
    """Return (ok, reason). ok=False means kill this candidate.

    `strict` runs the second-generation guards (simile crutch, question rate,
    punching down, generic reply). It is on everywhere; the flag exists so the
    eval harness can A/B the guards against the same drafts."""
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
    if _CURLY.search(c):
        return False, "curly quotes"

    # praise with nothing in it earns no reply-back; worst archetype
    if _compliment_only(cl):
        return False, "compliment-only reply"

    # "the best part: it learns"
    if _COLON_REVEAL.search(c):
        return False, "colon reveal"

    # @-mentions are automatic on replies and read as tagging spam in the body
    if _MENTION.search(c):
        return False, "contains @-mention"

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

    # "not X, but Y" and its variants ("isn't just X, it's Y", "not only")
    if re.search(r"\bnot\b.{1,40}\bbut\b", cl):
        return False, "'not X, but Y' construction"
    if re.search(r"\b(is|are|was|were)n'?t (just|only)\b|\bnot only\b", cl):
        return False, "'not just X, it's Y' construction"

    # rhetorical-question opener
    if cl.split(".")[0].strip().endswith("?") and cl.startswith(("isn't", "aren't",
            "don't", "doesn't", "why ", "what if", "ever notice")):
        return False, "rhetorical-question opener"

    # opener paraphrases the parent (first clause overlaps heavily)
    opener_clause = re.split(r"[.!?]", c)[0]
    if parent_text and ngram_overlap(opener_clause, parent_text, n=3) > 0.5:
        return False, "opener paraphrases parent"

    if strict:
        from .guards import check
        why = check(c, parent_text, archetype)
        if why:
            return False, why

    return True, "ok"
