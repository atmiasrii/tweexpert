"""Model access through an OpenAI-compatible base URL (A-03, Z-01).

Ollama by default; vLLM by pointing at its endpoint. When no model is
reachable (fixture mode / no GPU, I-05) a deterministic offline generator
stands in so the whole pipeline — draft, critic, embed — still runs and the
dashboard populates (T-01). Latency + token counts recorded per call (Z-03).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

import httpx

from ..config import get_settings
from ..defaults import CRITIC_TEMPERATURE
from ..logging_setup import get_logger
from .vectors import hash_embed

log = get_logger("quill.llm")


@dataclass
class LLMCall:
    role: str
    model: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    offline: bool = False


_CALLS: list[LLMCall] = []


def recent_calls(n: int = 50) -> list[dict]:
    return [c.__dict__ for c in _CALLS[-n:]]


class LLM:
    def __init__(self):
        self.s = get_settings()

    # -- low level -------------------------------------------------------
    def _chat(self, model: str, messages: list[dict], temperature: float,
              role: str, json_mode: bool = False) -> str:
        t0 = time.time()
        if not self.s.llm_available:
            out = _offline_chat(messages, json_mode)
            self._record(role, model, t0, messages, out, offline=True)
            return out
        try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            r = httpx.post(
                f"{self.s.llm_base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.s.llm_api_key}"},
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()
            out = data["choices"][0]["message"]["content"]
            self._record(role, model, t0, messages, out, offline=False,
                         usage=data.get("usage"))
            return out
        except Exception as e:  # graceful degradation (O-05)
            log.warning("llm chat failed, using offline: %s", e)
            out = _offline_chat(messages, json_mode)
            self._record(role, model, t0, messages, out, offline=True)
            return out

    def _record(self, role, model, t0, messages, out, offline, usage=None):
        pt = usage.get("prompt_tokens") if usage else _approx_tokens(messages)
        ct = usage.get("completion_tokens") if usage else _approx_tokens(out)
        c = LLMCall(role, model, int((time.time() - t0) * 1000), pt or 0, ct or 0, offline)
        _CALLS.append(c)
        del _CALLS[:-500]

    # -- high level ------------------------------------------------------
    def draft(self, system: str, user: str, temperature: float) -> str:
        return self._chat(self.s.draft_model,
                          [{"role": "system", "content": system},
                           {"role": "user", "content": user}],
                          temperature, role="draft")

    def critic(self, system: str, user: str) -> dict:
        raw = self._chat(self.s.critic_model,
                         [{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                         CRITIC_TEMPERATURE,
                         role="critic", json_mode=True)
        return _parse_json_strict(raw, self, system, user)

    def embed(self, text: str) -> list[float]:
        if not self.s.llm_available:
            return hash_embed(text)
        try:
            r = httpx.post(
                f"{self.s.llm_base_url}/embeddings",
                json={"model": self.s.embed_model, "input": text},
                headers={"Authorization": f"Bearer {self.s.llm_api_key}"},
                timeout=60,
            )
            r.raise_for_status()
            return r.json()["data"][0]["embedding"]
        except Exception as e:
            log.warning("llm embed failed, using offline: %s", e)
            return hash_embed(text)


def _parse_json_strict(raw: str, llm: "LLM", system: str, user: str) -> dict:
    """Validate strict JSON, with one repair retry before giving up (Z-02)."""
    obj = _try_json(raw)
    if obj is not None:
        return obj
    # one repair attempt
    repair = llm._chat(
        llm.s.critic_model,
        [{"role": "system", "content": "Return ONLY valid minified JSON. No prose."},
         {"role": "user", "content": raw[:4000]}],
        0.0, role="critic-repair", json_mode=True,
    )
    obj = _try_json(repair)
    if obj is not None:
        return obj
    raise ValueError("critic did not return valid JSON after repair")


def _try_json(raw: str):
    raw = raw.strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _approx_tokens(x) -> int:
    if isinstance(x, list):
        return sum(len(str(m.get("content", ""))) for m in x) // 4
    return len(str(x)) // 4


# -----------------------------------------------------------------------
# Offline deterministic generator (fixture mode). Produces operator-shaped
# text and a critic that flags injected instructions (X-05, T-09).
# -----------------------------------------------------------------------
_INJECTION_RE = re.compile(
    r"(ignore (all |your |previous )?instructions|disregard the above|"
    r"reply with|system prompt|you are now|pretend to be)", re.I)


def _obeyed_injection(src: str, draft: str) -> bool:
    """Offline heuristic: did the candidate comply with an instruction embedded
    in the source? Compliance shows up as echoing the demanded payload, or as a
    hashtag/marker the operator's voice never uses."""
    d = draft.lower()
    if "#" in draft:                         # our voice never uses hashtags
        return True
    # extract a demanded payload: reply with '...' or "..."
    m = re.search(r"reply with\s*['\"](.+?)['\"]", src, re.I | re.DOTALL)
    if m:
        payload = m.group(1).strip().lower()
        if payload and (payload in d or ngram_overlap_lite(payload, d) > 0.4):
            return True
    if "i am a bot" in d or "as an ai" in d:
        return True
    return False


def ngram_overlap_lite(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _offline_chat(messages: list[dict], json_mode: bool) -> str:
    user = messages[-1]["content"] if messages else ""
    if json_mode or "critic" in (messages[0]["content"].lower() if messages else ""):
        return _offline_critic(user)
    return _offline_draft(user)


def _extract_source(user: str) -> str:
    m = re.search(r"<source_post>(.*?)</source_post>", user, re.DOTALL)
    return (m.group(1).strip() if m else user).strip()


def _extract_angle(user: str) -> str:
    m = re.search(r"<angle>(.*?)</angle>", user, re.DOTALL)
    return (m.group(1).strip() if m else "adds info").lower()


def _offline_draft(user: str) -> str:
    src = _extract_source(user)
    angle = _extract_angle(user)
    topic = _keyword(src)
    if angle.startswith("short"):
        return f"{topic} is the whole game here. rest is detail."
    if "disagree" in angle or "complic" in angle or "push" in angle:
        return (f"not sure that holds. {topic} breaks down once you hit real "
                f"traffic. measured it last week and the numbers went the other way.")
    return (f"the {topic} part matters more than it looks. constrained decoding "
            f"plus a tight schema got mine stable at about 40ms p50.")


def _keyword(text: str) -> str:
    words = [w for w in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{3,}", text)
             if w.lower() not in _STOP]
    return words[0].lower() if words else "this"


_STOP = {"this", "that", "with", "from", "have", "just", "about", "your",
         "they", "what", "when", "which", "there", "their", "would", "could",
         "spent", "morning", "trying", "harder", "looks", "than", "them"}


def _offline_critic(user: str) -> str:
    src = _extract_source(user)
    draft = ""
    m = re.search(r"<candidate>(.*?)</candidate>", user, re.DOTALL)
    if m:
        draft = m.group(1)
    injected = bool(_INJECTION_RE.search(src))
    obeyed = injected and _obeyed_injection(src, draft)
    # score axes 1-5: voice, adds, human, embarrassment(inverted risk->high good)
    base = {"sounds_like_operator": 4, "adds_something": 4,
            "reads_human": 4, "low_embarrassment_risk": 4}
    if obeyed:
        base = {k: 1 for k in base}
    return json.dumps({
        **base,
        "followed_injected_instructions": bool(obeyed),
        "notes": "offline critic" + (" — injection detected" if injected else ""),
    })
