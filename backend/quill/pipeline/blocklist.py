"""Blocklist + content-safety gate (R-04, X-06)."""
from __future__ import annotations

import re

from sqlmodel import Session

from ..browser.base import ParsedPost
from ..db.settings_store import get_setting
from ..defaults import DEFAULT_BLOCK_TOPICS

_DISTRESS = re.compile(
    r"\b(rip|passed away|passed|grief|grieving|died|dying|funeral|so sad|"
    r"heartbroken|devastated|tragedy|suicide|depressed)\b", re.I)
_SLUR_PLACEHOLDER = re.compile(r"\b(slur1|slur2)\b", re.I)  # operator maintains real list
_PII = re.compile(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b|\b\d{16}\b")  # ssn/card-ish
_ADVICE = re.compile(r"\b(you should (buy|sell|invest)|guaranteed returns|"
                     r"(diagnos|prescrib)|this is not medical advice)\b", re.I)


def block_reason(session: Session, post: ParsedPost, auto: bool) -> str | None:
    """Return a reason string if the post must not be drafted on, else None."""
    text = post.text.lower()

    topics = get_setting(session, "block_topics", DEFAULT_BLOCK_TOPICS)
    for t in topics:
        if t.lower() in text:
            return f"blocked topic: {t}"

    authors = [a.lower() for a in get_setting(session, "block_authors", [])]
    if post.author_handle.lower() in authors:
        return f"blocked author: @{post.author_handle}"

    keywords = [k.lower() for k in get_setting(session, "block_keywords", [])]
    for k in keywords:
        if k in text:
            return f"blocked keyword: {k}"

    if post.lang and post.lang != "en":
        return f"non-english ({post.lang})"

    if post.media and not post.text.strip():
        return "media-only post"

    # auto mode additionally skips distressed sentiment (R-04)
    if auto and _DISTRESS.search(post.text):
        return "distressed sentiment (auto)"

    return None


def unsafe_to_send(text: str, session: Session) -> str | None:
    """Content-safety gate before any auto send (X-06)."""
    if re.search(r"https?://", text):
        return "contains link"
    if re.search(r"#\w+", text):
        return "contains hashtag"
    if _SLUR_PLACEHOLDER.search(text):
        return "contains slur"
    if _PII.search(text):
        return "contains personal data"
    if _ADVICE.search(text):
        return "financial/medical advice"
    return None
