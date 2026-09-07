"""Pure helpers for posting a reply and proving it landed.

Kept out of the engine so the fiddly parts — matching X's rendering of our own
text, pulling an id out of a permalink — can be tested without a browser.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

_WS = re.compile(r"\s+")
_STATUS = re.compile(r"/status/(\d+)")
# X linkifies, shortens and truncates, so an exact match is too strict.
MATCH_RATIO = 0.90


def normalize_reply_text(text: str) -> str:
    """Compare on meaning, not on how X chose to render it."""
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = re.sub(r"https?://\S+", " ", t)          # links get rewritten
    t = t.replace("…", " ")                  # the truncation ellipsis
    t = re.sub(r"[^\w\s]", " ", t)                # punctuation is unreliable
    return _WS.sub(" ", t).strip()


def texts_match(sent: str, seen: str) -> bool:
    """Is `seen` (as rendered on the page) the reply we `sent`?"""
    a, b = normalize_reply_text(sent), normalize_reply_text(seen)
    if not a or not b:
        return False
    if a == b or a.startswith(b) or b.startswith(a):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= MATCH_RATIO


def status_id_from_href(href: str) -> str:
    """The post id in a permalink, ignoring /analytics and /photo/1 suffixes."""
    m = _STATUS.search(href or "")
    return m.group(1) if m else ""


def target_article_selectors(x_post_id: str) -> list[str]:
    """Ways to point at one specific post's article, best first.

    `href$=` rather than `href*=` on purpose: it excludes /analytics and
    /photo/1, which would otherwise match several elements of the same post.
    """
    return [
        f'article[data-testid="tweet"]:has(a[href$="/status/{x_post_id}"])',
        f'article[role="article"]:has(a[href$="/status/{x_post_id}"])',
    ]
