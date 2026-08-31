"""Learning loop (§20). Every approval/edit/dismissal is a training signal
(L-01). Edits are promoted into the few-shot pool at higher weight (L-02).
Export produces DPO + SFT JSONL (L-03)."""
from __future__ import annotations

import json

from sqlmodel import Session, select

from ..db.models import Draft, Feedback
from ..persona.corpus import add_edit_sample


def _prompt_for(draft: Draft) -> dict:
    return {"kind": draft.kind, "relevance": draft.relevance,
            "candidates": json.loads(draft.candidates_json or "[]")}


def record_approve(session: Session, draft: Draft, final_text: str) -> None:
    cands = json.loads(draft.candidates_json or "[]")
    chosen = final_text
    rejected = [c["text"] for i, c in enumerate(cands) if i != draft.chosen_index]
    session.add(Feedback(draft_id=draft.id, action="approve",
                         original_text=cands[draft.chosen_index]["text"] if cands else "",
                         final_text=final_text, chosen_text=chosen,
                         rejected_json=json.dumps(rejected),
                         prompt_json=json.dumps(_prompt_for(draft))))
    session.commit()


def record_edit(session: Session, draft: Draft, before: str, after: str) -> None:
    session.add(Feedback(draft_id=draft.id, action="edit", original_text=before,
                         final_text=after, chosen_text=after,
                         rejected_json=json.dumps([before]),
                         prompt_json=json.dumps(_prompt_for(draft))))
    session.commit()
    add_edit_sample(session, after)     # L-02: promote edit into retrieval


def record_dismiss(session: Session, draft: Draft, reason: str) -> None:
    session.add(Feedback(draft_id=draft.id, action="dismiss", reason=reason,
                         prompt_json=json.dumps(_prompt_for(draft))))
    session.commit()


def record_shadow_judgement(session: Session, draft: Draft, approve: bool) -> None:
    session.add(Feedback(draft_id=draft.id, action="shadow_judge",
                         reason="would_approve" if approve else "would_reject",
                         final_text=draft.final_text,
                         prompt_json=json.dumps(_prompt_for(draft))))
    session.commit()


# --- exports (L-03) -----------------------------------------------------
def export_dpo(session: Session) -> str:
    """DPO JSONL: {prompt, chosen, rejected}."""
    lines = []
    fbs = session.exec(select(Feedback).where(
        Feedback.action.in_(["approve", "edit"]))).all()
    for fb in fbs:
        rejected = json.loads(fb.rejected_json or "[]")
        if not fb.chosen_text or not rejected:
            continue
        for rej in rejected:
            lines.append(json.dumps({
                "prompt": json.loads(fb.prompt_json or "{}"),
                "chosen": fb.chosen_text, "rejected": rej}))
    return "\n".join(lines) + ("\n" if lines else "")


def export_sft(session: Session) -> str:
    """SFT JSONL from edits: {prompt, completion}."""
    lines = []
    fbs = session.exec(select(Feedback).where(Feedback.action == "edit")).all()
    for fb in fbs:
        lines.append(json.dumps({
            "prompt": json.loads(fb.prompt_json or "{}"),
            "completion": fb.final_text}))
    return "\n".join(lines) + ("\n" if lines else "")


def sample_counts(session: Session) -> dict:
    fbs = session.exec(select(Feedback)).all()
    return {
        "approve": sum(1 for f in fbs if f.action == "approve"),
        "edit": sum(1 for f in fbs if f.action == "edit"),
        "dismiss": sum(1 for f in fbs if f.action == "dismiss"),
        "shadow_judge": sum(1 for f in fbs if f.action == "shadow_judge"),
        "dpo_pairs": export_dpo(session).count("\n"),
        "sft_examples": export_sft(session).count("\n"),
        "enough_to_train": len(fbs) >= 50,
    }


def approval_rate_series(session: Session) -> list[dict]:
    """L-05: approval rate over time (headline quality metric)."""
    fbs = session.exec(select(Feedback).where(
        Feedback.action.in_(["approve", "edit", "dismiss"]))
        .order_by(Feedback.created_at)).all()
    by_week: dict[str, list[int]] = {}
    for fb in fbs:
        wk = fb.created_at.strftime("%Y-W%W")
        approved_unedited = 1 if fb.action == "approve" else 0
        by_week.setdefault(wk, []).append(approved_unedited)
    return [{"week": wk, "rate": round(sum(v) / len(v), 3) if v else 0,
             "n": len(v)} for wk, v in by_week.items()]
