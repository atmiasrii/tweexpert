"""Voice card (§9). The single most important config for output quality."""
from __future__ import annotations

import json

from sqlmodel import Session

from ..db.settings_store import get_setting, set_setting

DEFAULT_VOICE_CARD = {
    "identity": "sharp, funny builder deep in AI and startups; ships real things",
    "stands_for": "good, new, actually-innovative AI; roots for real progress, "
                  "calls out slop and hype; likeable, never a know-it-all",
    "register": "dry, specific, funny; a point of view; understatement over hype",
    "sentence_shape": "short. fragments allowed. rarely two clauses",
    "punctuation": {"em_dash": False, "exclamation": "almost never",
                    "case": "sentence case, sometimes all lower"},
    "reply_length": {"target_chars": 120, "max_chars": 240},
    "does": ["concrete detail", "a number when there is one",
             "real disagreement", "self-deprecating aside"],
    "never": ["Great point!", "This.", "emoji strings", "hashtags",
              "rhetorical question openers", "restating the parent",
              "'not X, but Y'", "starting with 'Honestly'"],
    "topics_owned": ["inference infra", "local models", "dev tooling"],
    "topics_avoided": ["politics", "crypto prices", "anything legal"],
}

VOICE_KEY = "voice_card"


def load_voice_card(session: Session) -> dict:
    return get_setting(session, VOICE_KEY, DEFAULT_VOICE_CARD)


def save_voice_card(session: Session, card: dict) -> None:
    set_setting(session, VOICE_KEY, card)


def voice_card_prompt(card: dict) -> str:
    """Render the voice card into a system-prompt fragment."""
    return (
        "You write short replies in EXACTLY this person's voice.\n"
        f"Identity: {card.get('identity')}\n"
        + (f"Stands for: {card.get('stands_for')}\n" if card.get("stands_for") else "")
        + f"Register: {card.get('register')}\n"
        f"Sentence shape: {card.get('sentence_shape')}\n"
        f"Punctuation: {json.dumps(card.get('punctuation', {}))}\n"
        f"Length: target {card.get('reply_length', {}).get('target_chars', 120)} "
        f"chars, hard max {card.get('reply_length', {}).get('max_chars', 240)}.\n"
        f"Do: {', '.join(card.get('does', []))}\n"
        f"Never: {', '.join(card.get('never', []))}\n"
        f"Topics you own: {', '.join(card.get('topics_owned', []))}\n"
        f"Topics you avoid: {', '.join(card.get('topics_avoided', []))}\n"
    )
