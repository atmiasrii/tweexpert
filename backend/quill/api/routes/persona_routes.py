"""Persona: voice card, archive import, playground (P-01, P-08, §18)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from ...db.engine import get_session
from ...learning import feedback
from ...persona import engine as persona
from ...persona.corpus import corpus_size, import_samples, parse_archive
from ...persona.playbook import (DEFAULT_SKILLS, EXAMPLE_TWEETS, SKILL_LABELS,
                                 load_skills, save_skills)
from ...persona.voicecard import load_voice_card, save_voice_card
from ..auth import require_auth

router = APIRouter(prefix="/api/persona", tags=["persona"])


@router.get("")
def get_persona(session: Session = Depends(get_session), _=Depends(require_auth)):
    return {"voice_card": load_voice_card(session),
            "corpus_size": corpus_size(session),
            "skills": load_skills(session),
            "skill_labels": SKILL_LABELS,
            "skill_defaults": DEFAULT_SKILLS,
            "learning": feedback.sample_counts(session)}


class SkillsBody(BaseModel):
    skills: dict


@router.get("/skills")
def get_skills(session: Session = Depends(get_session), _=Depends(require_auth)):
    return {"skills": load_skills(session), "labels": SKILL_LABELS,
            "defaults": DEFAULT_SKILLS}


@router.put("/skills")
def put_skills(body: SkillsBody, session: Session = Depends(get_session),
               _=Depends(require_auth)):
    return {"skills": save_skills(session, body.skills)}


@router.get("/examples")
def list_examples(_=Depends(require_auth)):
    """The 10 showcase posts (no replies yet — generated on demand)."""
    return {"examples": EXAMPLE_TWEETS}


@router.post("/examples/generate")
def generate_examples(session: Session = Depends(get_session), _=Depends(require_auth)):
    """Generate Quill's reply for each showcase post with the CURRENT skills.
    Runs the live model; can take a bit with a big model."""
    out = []
    for ex in EXAMPLE_TWEETS:
        try:
            reply = persona.quick_reply(session, ex["text"])
        except Exception as e:  # never fail the whole batch on one bad draft
            reply = f"(generation failed: {e})"
        out.append({**ex, "reply": reply})
    return {"examples": out, "skills": load_skills(session)}


class VoiceCardBody(BaseModel):
    voice_card: dict


@router.put("")
def put_persona(body: VoiceCardBody, session: Session = Depends(get_session),
                _=Depends(require_auth)):
    save_voice_card(session, body.voice_card)
    return {"ok": True}


@router.post("/import")
async def import_archive(file: UploadFile = File(...),
                         session: Session = Depends(get_session),
                         _=Depends(require_auth)):
    raw = await file.read()
    rows = parse_archive(raw, file.filename or "archive.txt")
    n = import_samples(session, rows)
    return {"imported": n, "corpus_size": corpus_size(session)}


class PreviewBody(BaseModel):
    tweet: str


@router.post("/preview")
def preview(body: PreviewBody, session: Session = Depends(get_session),
            _=Depends(require_auth)):
    """Playground (P-08): three candidates + all critic scores."""
    result = persona.generate(session, body.tweet, auto=False)
    return {"candidates": [{"angle": c.angle, "text": c.text,
                            "prefilter_ok": c.prefilter_ok,
                            "prefilter_reason": c.prefilter_reason,
                            "similarity_hit": c.similarity_hit,
                            "critic": c.critic} for c in result.candidates],
            "chosen_index": result.chosen_index, "reason": result.reason}
