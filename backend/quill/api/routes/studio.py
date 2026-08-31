"""Compose, schedule, discovery, searches, people, ideas (§13, §14)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ...db.engine import get_session
from ...db.models import IdeaNote, QueuedPost, SavedSearch, ScheduleSlot
from ...persona import engine as persona
from ...persona.voicecard import load_voice_card, voice_card_prompt
from ...persona.corpus import retrieve_fewshot
from ...persona.llm import LLM
from ...pipeline import discovery, schedule as sched
from ..auth import require_auth

router = APIRouter(prefix="/api", tags=["studio"])


# --- compose (C-02, C-03) ----------------------------------------------
class GenBody(BaseModel):
    idea: str


@router.post("/compose/generate")
def compose_generate(body: GenBody, session: Session = Depends(get_session),
                     _=Depends(require_auth)):
    result = persona.generate(session, body.idea, auto=False)
    return {"candidates": [{"angle": c.angle, "text": c.text,
                            "prefilter_ok": c.prefilter_ok,
                            "prefilter_reason": c.prefilter_reason,
                            "critic": c.critic} for c in result.candidates],
            "chosen_index": result.chosen_index, "reason": result.reason}


class RestyleBody(BaseModel):
    text: str


@router.post("/compose/restyle")
def compose_restyle(body: RestyleBody, session: Session = Depends(get_session),
                    _=Depends(require_auth)):
    card = load_voice_card(session)
    vp = voice_card_prompt(card)
    fewshot = retrieve_fewshot(session, body.text)
    shots = "\n".join(f"- {s}" for s in fewshot)
    system = f"{vp}\nRewrite the user's text in this voice. Keep the meaning. Change only voice."
    user = f"Examples of the voice:\n{shots}\nRewrite this without changing meaning:\n{body.text}"
    out = LLM().draft(system, user, 0.6)
    return {"text": out.strip().strip('"')}


# --- ideas (C-08) -------------------------------------------------------
class IdeaBody(BaseModel):
    text: str


@router.get("/ideas")
def list_ideas(session: Session = Depends(get_session), _=Depends(require_auth)):
    return session.exec(select(IdeaNote).where(IdeaNote.promoted == False)).all()  # noqa: E712


@router.post("/ideas")
def add_idea(body: IdeaBody, session: Session = Depends(get_session),
             _=Depends(require_auth)):
    note = IdeaNote(text=body.text)
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


@router.post("/ideas/{idea_id}/promote")
def promote_idea(idea_id: int, session: Session = Depends(get_session),
                 _=Depends(require_auth)):
    note = session.get(IdeaNote, idea_id)
    if not note:
        raise HTTPException(404)
    result = persona.generate(session, note.text, auto=False)
    note.promoted = True
    session.add(note)
    session.commit()
    return {"candidates": [{"angle": c.angle, "text": c.text, "critic": c.critic}
                           for c in result.candidates]}


# --- schedule (C-04, C-05, C-06) ---------------------------------------
class QueuedBody(BaseModel):
    text: str
    category: str = ""
    evergreen: bool = False


class SlotBody(BaseModel):
    weekday: int
    hour: int
    minute: int = 0
    category: str = ""


@router.get("/schedule")
def get_schedule(session: Session = Depends(get_session), _=Depends(require_auth)):
    slots = session.exec(select(ScheduleSlot)).all()
    queued = session.exec(select(QueuedPost).order_by(QueuedPost.order_index)).all()
    return {"slots": [s.model_dump() for s in slots],
            "queued": [q.model_dump() for q in queued]}


@router.post("/schedule")
def add_queued(body: QueuedBody, session: Session = Depends(get_session),
               _=Depends(require_auth)):
    qp = sched.enqueue_post(session, body.text, body.category, body.evergreen)
    return qp


@router.post("/schedule/slots")
def add_slot(body: SlotBody, session: Session = Depends(get_session),
             _=Depends(require_auth)):
    slot = ScheduleSlot(weekday=body.weekday, hour=body.hour, minute=body.minute,
                        category=body.category)
    session.add(slot)
    session.commit()
    session.refresh(slot)
    sched.assign_slots(session)
    return slot


class ReorderBody(BaseModel):
    ids: list[int]


@router.patch("/schedule/reorder")
def reorder(body: ReorderBody, session: Session = Depends(get_session),
            _=Depends(require_auth)):
    sched.reorder(session, body.ids)
    return {"ok": True}


@router.delete("/schedule/{queued_id}")
def del_queued(queued_id: int, session: Session = Depends(get_session),
               _=Depends(require_auth)):
    qp = session.get(QueuedPost, queued_id)
    if qp:
        session.delete(qp)
        session.commit()
    return {"ok": True}


# --- searches (V-01) ---------------------------------------------------
class SearchBody(BaseModel):
    query: str
    interval_s: int = 3600


@router.get("/searches")
def list_searches(session: Session = Depends(get_session), _=Depends(require_auth)):
    return session.exec(select(SavedSearch)).all()


@router.post("/searches")
def add_search(body: SearchBody, session: Session = Depends(get_session),
               _=Depends(require_auth)):
    s = SavedSearch(query=body.query, interval_s=body.interval_s)
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


@router.delete("/searches/{search_id}")
def del_search(search_id: int, session: Session = Depends(get_session),
               _=Depends(require_auth)):
    s = session.get(SavedSearch, search_id)
    if s:
        session.delete(s)
        session.commit()
    return {"ok": True}


# --- discover / notifications / people (§14) ---------------------------
@router.get("/discover")
def get_discover(session: Session = Depends(get_session), _=Depends(require_auth)):
    return discovery.list_discovery(session)


@router.post("/discover/{item_id}/promote")
def promote_discover(item_id: int, session: Session = Depends(get_session),
                     _=Depends(require_auth)):
    outcome = discovery.promote(session, item_id)
    return {"status": outcome.status, "draft_id": outcome.draft_id,
            "reason": outcome.reason}


@router.get("/notifications")
def get_notifications(session: Session = Depends(get_session), _=Depends(require_auth)):
    from ...db.models import Notification
    rows = session.exec(select(Notification).order_by(Notification.fetched_at.desc())).all()
    return [r.model_dump() for r in rows]


@router.get("/people")
def get_people(session: Session = Depends(get_session), _=Depends(require_auth)):
    return discovery.list_people(session)
