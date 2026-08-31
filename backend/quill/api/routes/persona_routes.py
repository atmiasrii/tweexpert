"""Persona: voice card, archive import, playground (P-01, P-08, §18)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from ...db.engine import get_session
from ...learning import feedback
from ...persona import engine as persona
from ...persona.corpus import corpus_size, import_samples, parse_archive
from ...persona.voicecard import load_voice_card, save_voice_card
from ..auth import require_auth

router = APIRouter(prefix="/api/persona", tags=["persona"])


@router.get("")
def get_persona(session: Session = Depends(get_session), _=Depends(require_auth)):
    return {"voice_card": load_voice_card(session),
            "corpus_size": corpus_size(session),
            "learning": feedback.sample_counts(session)}


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
