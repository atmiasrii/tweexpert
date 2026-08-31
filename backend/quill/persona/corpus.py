"""Style corpus + retrieval (P-01, P-02, L-02).

Import the operator's archive (tweets.js / CSV / plain text), clean, embed,
store as style samples. For each draft, retrieve 8-12 of the operator's own
posts most similar to the target, weighted toward high performers, plus prior
replies to the same account. Edits are stored with higher weight (L-02).
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone

from sqlmodel import Session, select

from ..db.models import StyleSample
from ..defaults import FEWSHOT_MAX, FEWSHOT_MIN
from .llm import LLM
from .vectors import cosine, pack, unpack

_URL = re.compile(r"https?://\S+")
_WS = re.compile(r"\s+")


def clean_text(t: str) -> str:
    t = _URL.sub("", t)
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return _WS.sub(" ", t).strip()


def parse_archive(raw: bytes, filename: str) -> list[dict]:
    """Accept tweets.js, CSV, or a plain text file (one post per line)."""
    text = raw.decode("utf-8", errors="ignore")
    name = filename.lower()
    if name.endswith(".js") or "window.YTD" in text or text.lstrip().startswith("["):
        return _parse_tweets_js(text)
    if name.endswith(".csv"):
        return _parse_csv(text)
    if name.endswith(".json"):
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "posts" in data:
                return [{"text": p["text"], "metrics": {"likes": p.get("likes", 0)}}
                        for p in data["posts"]]
        except json.JSONDecodeError:
            pass
    # plain text
    return [{"text": line, "metrics": {}} for line in text.splitlines() if line.strip()]


def _parse_tweets_js(text: str) -> list[dict]:
    # tweets.js is `window.YTD.tweets.part0 = [ ... ]`
    start = text.find("[")
    try:
        data = json.loads(text[start:]) if start >= 0 else json.loads(text)
    except json.JSONDecodeError:
        return []
    out = []
    for item in data:
        tw = item.get("tweet", item)
        t = tw.get("full_text") or tw.get("text", "")
        if t.startswith("RT @"):
            continue
        out.append({"text": t, "metrics": {
            "likes": int(tw.get("favorite_count", 0)),
            "reposts": int(tw.get("retweet_count", 0))}})
    return out


def _parse_csv(text: str) -> list[dict]:
    out = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        t = row.get("text") or row.get("Tweet text") or row.get("tweet") or ""
        if t:
            out.append({"text": t, "metrics": {"likes": int(row.get("likes", 0) or 0)}})
    return out


def import_samples(session: Session, rows: list[dict], source: str = "archive",
                   weight: float = 1.0) -> int:
    llm = LLM()
    n = 0
    for row in rows:
        text = clean_text(row["text"])
        if len(text) < 12:
            continue
        emb = llm.embed(text)
        session.add(StyleSample(
            text=text, created_at=datetime.now(timezone.utc),
            metrics_json=json.dumps(row.get("metrics", {})),
            embedding=pack(emb), source=source, weight=weight))
        n += 1
    session.commit()
    return n


def add_edit_sample(session: Session, text: str) -> None:
    """Promote an operator edit into the retrieval pool at higher weight (L-02)."""
    import_samples(session, [{"text": text, "metrics": {}}], source="edit", weight=2.5)


def retrieve_fewshot(session: Session, target_text: str,
                     account_handle: str = "") -> list[str]:
    llm = LLM()
    q = unpack(pack(llm.embed(target_text)))
    samples = session.exec(select(StyleSample)).all()
    scored = []
    for sm in samples:
        sim = cosine(q, unpack(sm.embedding))
        metrics = json.loads(sm.metrics_json or "{}")
        perf = 1.0 + min(metrics.get("likes", 0), 1000) / 1000.0  # weight to high performers
        scored.append((sim * perf * sm.weight, sm.text, sm.source))
    scored.sort(key=lambda x: x[0], reverse=True)
    # prior replies to the same account come first (P-02)
    priors = [t for _, t, src in scored if src == "reply"][:2]
    picks = priors + [t for _, t, _ in scored]
    seen, out = set(), []
    for t in picks:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= FEWSHOT_MAX:
            break
    return out[:max(FEWSHOT_MIN, min(len(out), FEWSHOT_MAX))] if out else out


def corpus_size(session: Session) -> int:
    return len(session.exec(select(StyleSample)).all())
