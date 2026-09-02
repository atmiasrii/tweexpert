"""Second-generation deterministic guards (the four failure modes that survived
the persona rewrite).

The prefilter kills phrasing that is obviously machine-written. These four kill
replies that are *well-written but still wrong*, which is the harder class:

1. `simile_tell`      the "X is like Y" analogy crutch. The model reaches for a
                      clever comparison roughly one reply in five; humans on X
                      almost never do. It is a cadence tell.
2. `question_rate`    the research puts questions at ~30% of replies. Asking
                      the model nicely does not hold, so the archetype decides
                      and this enforces it.
3. `punching_down`    when the author is already laughing at themselves, a
                      correction reads as smug. A mute is -74 against the +75
                      a reply-back pays, so smug is not a small mistake.
4. `generic_reply`    the reply could have been written without reading the
                      post. This is the single most common quality failure and
                      the whole point of the rewrite.
"""
from __future__ import annotations

import re

# --- 1. simile / analogy crutch ---------------------------------------------
# Only the comparison constructions, never a bare "like" (people say "I like").
_SIMILE = re.compile(
    r"\b("
    r"(is|are|was|were|feels?|felt|reads?|sounds?|looks?|acts?|behaves?)\s+"
    r"(just\s+|kind\s+of\s+|sort\s+of\s+|a\s+lot\s+)?like\b"
    r"|it'?s\s+like\b"
    r"|same\s+(energy|thing)\s+as\b"
    r"|reminds?\s+me\s+of\b"
    r"|the\s+\w+\s+equivalent\s+of\b"
    r"|imagine\s+(a|an|if)\b"
    r"|think\s+of\s+it\s+as\b"
    r")", re.I)
# "like aiming for Mars while...", as its own sentence or a trailing clause
_SIMILE_TAIL = re.compile(r"(^|[,.]\s*)like\s+(\w+ing|a|an|the)\b", re.I)


def simile_tell(text: str) -> str:
    if _SIMILE.search(text) or _SIMILE_TAIL.search(text):
        return "simile / analogy crutch"
    return ""


# --- 2. question rate --------------------------------------------------------
def question_violation(text: str, archetype: str) -> str:
    """Only the `question` archetype may ask one. Everything else states a
    thing. This makes the question rate exactly the archetype weight instead of
    whatever the model felt like."""
    has_q = "?" in text
    if archetype == "question":
        return "" if has_q else "question archetype with no question"
    return "question outside the question archetype" if has_q else ""


# --- 3. punching down --------------------------------------------------------
_FIRST_PERSON = re.compile(r"(^|\s)(i|i'?m|im|i'?ve|my|me|we|our)\b", re.I)
_SELF_BLAME = re.compile(
    r"\b("
    r"stupid|idiot|dumb|embarrass\w*|ashamed|failed|failure|broke it|broke the|"
    r"wasted|turns out|forgot|missed|my bad|screwed|messed (it |this )?up|"
    r"spent (all|the whole) (day|week|night)|still (don'?t|can'?t|do not)|"
    r"no idea|clueless|struggl\w+|rookie|skill issue|somehow|apparently"
    r")", re.I)
_CONDESCENDING = re.compile(
    r"\b(rookie|amateur|basic mistake|beginner|you should('?ve| have)?|"
    r"should have known|obviously|clearly you|everyone knows|"
    r"skill issue|classic mistake|that'?s on you|surprising for|"
    r"at \d+ years?|after \d+ years?|with \d+ years?|for someone with)\b", re.I)


def is_self_deprecating(parent_text: str) -> bool:
    """First person anywhere plus an admission of their own screw-up. Order does
    not matter: "spent all day debugging ... i have 12 years" counts."""
    t = parent_text or ""
    return bool(_FIRST_PERSON.search(t) and _SELF_BLAME.search(t))


def punching_down(text: str, parent_text: str) -> str:
    """A correction aimed at someone who already made the joke about themselves.
    Only fires when the parent is self-deprecating, so real corrections on
    confident claims still get through."""
    if not is_self_deprecating(parent_text):
        return ""
    if _CONDESCENDING.search(text):
        return "punching down on a self-deprecating post"
    return ""


# --- 4. generic reply --------------------------------------------------------
_STOP = {
    "a", "about", "after", "again", "all", "also", "an", "and", "any", "are",
    "as", "at", "back", "be", "because", "been", "before", "being", "but", "by",
    "can", "cant", "come", "could", "did", "do", "does", "doing", "dont", "down",
    "each", "even", "every", "few", "for", "from", "get", "give", "go", "going",
    "good", "got", "had", "has", "have", "he", "her", "here", "him", "his",
    "how", "i", "if", "im", "in", "into", "is", "it", "its", "just", "keep",
    "know", "like", "make", "makes", "many", "me", "might", "more", "most",
    "much", "must", "my", "never", "new", "no", "not", "now", "of", "off", "on",
    "once", "one", "only", "or", "other", "our", "out", "over", "own", "people",
    "really", "right", "said", "same", "say", "see", "she", "should", "so",
    "some", "still", "such", "take", "than", "that", "thats", "the", "their",
    "them", "then", "there", "these", "they", "thing", "things", "think",
    "this", "those", "time", "to", "too", "two", "up", "us", "use", "used",
    "very", "want", "was", "way", "we", "well", "went", "were", "what", "when",
    "where", "which", "while", "who", "why", "will", "with", "work", "would",
    "you", "your", "youre",
}
_NUM = re.compile(r"\d")


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z'\-]{2,}", (text or "").lower())
    return {w for w in words if w not in _STOP}


def generic_reply(text: str, parent_text: str) -> str:
    """Reject a reply that shares no specific vocabulary with the post it is
    answering. If you could paste it under a different tweet and nobody would
    notice, it earns nothing."""
    if not parent_text:
        return ""
    reply_words = _content_words(text)
    parent_words = _content_words(parent_text)
    if not reply_words or not parent_words:
        return ""
    shared = reply_words & parent_words
    if shared:
        return ""
    # No shared vocabulary is only forgivable if the reply carries its own
    # concrete detail (a number, or an unusual long noun the post implies).
    if _NUM.search(text):
        return ""
    if any(len(w) >= 9 for w in reply_words):
        return ""
    return "generic: could be a reply to any post"


# --- 5. invented numbers -----------------------------------------------------
# A number that is not in the post and not in the world is a fabricated receipt.
# The eval caught the worst case: a reply to the single word "shipped" that read
# "p50 dropped from 90ms to 38ms", lifted from the operator's own corpus and
# presented as a fresh claim. Saying a false specific thing under someone's post
# is the fastest route to a correction, a mute, or a screenshot.
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Numbers that carry no claim: years, times of day, ordinary counts of things.
_SAFE_NUM = re.compile(r"^(19|20)\d\d$|^[0-9]$|^1[0-2]$|^24$")


def invented_numbers(text: str, parent_text: str) -> str:
    parent_nums = set(_NUMBER.findall(parent_text or ""))
    for n in _NUMBER.findall(text):
        if n in parent_nums or _SAFE_NUM.match(n):
            continue
        return f"invented number: {n}"
    return ""


# --- 6. nothing to reply to --------------------------------------------------
# The research's hard gate: if you have nothing specific to add, skip. A post
# that says "gm" or "soon." gives you nothing, so anything you write under it
# is filler by construction.
_MIN_WORDS = 5
_MIN_CONTENT_WORDS = 2


def too_thin(parent_text: str) -> str:
    """Deliberately narrow: only the posts that are unambiguously empty ("gm",
    "soon.", "shipped"). A short post can still be worth answering, so this
    needs both a tiny word count and almost no content words before it skips."""
    words = re.findall(r"[a-zA-Z0-9']+", parent_text or "")
    if len(words) < _MIN_WORDS and len(_content_words(parent_text)) < _MIN_CONTENT_WORDS + 1:
        return "post is too thin to add anything to"
    return ""


# --- 7. answering an abstraction with more abstraction -----------------------
# The weakest category in the eval was aphorisms. Naval-style posts have no
# concrete hook, so the model answers with life advice ("leverage is about
# resources and knowledge"), which is a lecture, not a reply. The fix is two
# sided: tell the model to name one concrete case, and reject the advice shape.
_PROPER = re.compile(r"(?<![.!?]\s)(?<!^)\b(?!I\b)[A-Z][a-z]{2,}")
_CONCRETE = re.compile(
    r"\b(ms|s|k|m|mrr|arr|api|sql|gpu|cpu|db|llm|model|models|latency|deploy|"
    r"ship|shipped|code|bug|test|tests|users|customers|revenue|churn|prod|"
    r"repo|commit|server|cache|token|tokens|benchmark|migration)\b", re.I)


def is_abstract(parent_text: str) -> bool:
    t = parent_text or ""
    return not (_NUMBER.search(t) or _PROPER.search(t) or _CONCRETE.search(t))


_ADVICE = re.compile(
    r"\b(you should|you need to|you have to|you gotta|focus on|start by|"
    r"try to|the key is|the trick is|it'?s about|means (that |setting |"
    r"finding |knowing )|comes down to|remember to|make sure (you|to))\b", re.I)


def lecturing(text: str, parent_text: str) -> str:
    """Advice-shaped reply to an abstraction. Only fires when the post gave you
    nothing concrete, which is exactly when the model reaches for a platitude."""
    if not is_abstract(parent_text):
        return ""
    if _ADVICE.search(text):
        return "lecturing back at an abstract post"
    return ""


# --- 8. glued words and stray capitals ---------------------------------------
# The local model drops the space between two words and capitalises the second
# ("made the black marketObsolete"). `engine.fix_casing` repairs this on every
# draft; this is the net for anything written before that existed, or by a path
# that skipped it, so "Clear old" can find them.
_GLUED_TELL = re.compile(r"[a-z]{2}[A-Z][a-z]{2}")


def glued_words(text: str) -> str:
    from .engine import _KEEP_CAPS          # lazy: engine imports prefilter
    for tok in re.findall(r"[A-Za-z']+", text or ""):
        if _GLUED_TELL.search(tok) and tok.lower() not in _KEEP_CAPS:
            return f"glued words: '{tok}'"
    return ""


# --- combined ----------------------------------------------------------------
def check(text: str, parent_text: str, archetype: str = "") -> str:
    """Return the first failure reason, or "" when the reply is clean."""
    for reason in (simile_tell(text),
                   glued_words(text),
                   punching_down(text, parent_text),
                   invented_numbers(text, parent_text),
                   lecturing(text, parent_text),
                   generic_reply(text, parent_text),
                   question_violation(text, archetype) if archetype else ""):
        if reason:
            return reason
    return ""
