"""Persona evaluation harness: 100 tweets, two arms, one report.

Run:  python scripts/eval_replies.py [--limit N] [--out docs/PERSONA_EVAL.md]

Two arms over the same corpus:

  A  baseline   the persona as committed in e6510f4: no per-draft directives,
                no second-generation guards.
  B  guarded    the current stack: warmth / no-simile / no-question directives
                in the draft prompt, plus guards.py in the prefilter.

Both arms retry across archetypes exactly like the live fast path, so the
numbers are what the operator would actually see, not best-of-N cherry picks.

Everything scored here is deterministic. No model judges another model: the
point is to find failures the model cannot see in itself.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Windows consoles default to cp1252 and the drafts are full of characters it
# cannot encode; the run must not die on a progress line.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from eval_corpus import CORPUS                                  # noqa: E402
from quill.db.engine import session_scope                     # noqa: E402
from quill.persona import guards                                # noqa: E402
from quill.persona.corpus import retrieve_fewshot               # noqa: E402
from quill.persona.engine import (_draft_one, _looks_english,   # noqa: E402
                                  _system_prompt, is_degenerate,
                                  pick_archetype)
from quill.persona.llm import LLM                               # noqa: E402
from quill.persona.playbook import ARCHETYPES, load_skills      # noqa: E402
from quill.persona.prefilter import prefilter                   # noqa: E402
from quill.persona.voicecard import load_voice_card, voice_card_prompt  # noqa: E402

TARGET_MIN, TARGET_MAX = 80, 180


# ---------------------------------------------------------------- generation
def run_arm(session, tweets: list[dict], *, guarded: bool) -> list[dict]:
    voice = load_voice_card(session)
    skills = load_skills(session)
    llm = LLM()
    arche = dict(ARCHETYPES)
    rows = []

    for i, tw in enumerate(tweets, 1):
        post = tw["t"]
        fewshot = retrieve_fewshot(session, post)
        system = _system_prompt(voice_card_prompt(voice), fewshot, skills)
        first = pick_archetype(post, skills)
        order = [first] + [n for n, _ in ARCHETYPES[:3] if n != first]

        t0 = time.time()
        attempts, text, chosen, why = [], "", "", "no attempt"
        for name in order:
            draft = _draft_one(llm, system, post, name, arche[name],
                               reasons="" if not attempts else why,
                               directives=guarded)
            ok, why = prefilter(draft, post, voice,
                                archetype=name if guarded else "",
                                strict=guarded)
            if ok and not _looks_english(draft):
                ok, why = False, "not English"
            if ok and is_degenerate(draft):
                ok, why = False, "degenerate"
            attempts.append({"archetype": name, "text": draft, "ok": ok, "why": why})
            if ok:
                text, chosen = draft, name
                break

        rows.append({
            "handle": tw["h"], "kind": tw["k"], "post": post,
            "archetype_first": first, "archetype_used": chosen,
            "text": text, "attempts": attempts,
            "tries": len(attempts), "seconds": round(time.time() - t0, 1),
        })
        print(f"  [{i:>3}/{len(tweets)}] {tw['k']:<9} {tw['h']:<16} "
              f"{'OK ' if text else 'FAIL'} {len(text):>3}ch "
              f"{rows[-1]['seconds']:>5}s  {text[:64]}", flush=True)
    return rows


# ------------------------------------------------------------------- scoring
def score(rows: list[dict]) -> dict:
    produced = [r for r in rows if r["text"]]
    n = len(rows)
    lens = [len(r["text"]) for r in produced]

    def pct(k: int) -> float:
        return round(100 * k / max(1, n), 1)

    # Template-ness: how much vocabulary each reply shares with the others.
    # A persona that says the same thing in different words shows up here.
    vocab = [guards._content_words(r["text"]) for r in produced]
    overlaps = []
    for i in range(len(vocab)):
        for j in range(i + 1, len(vocab)):
            u = vocab[i] | vocab[j]
            if u:
                overlaps.append(len(vocab[i] & vocab[j]) / len(u))
    # Openers: a persona with three stock openers is a template, not a voice.
    openers = Counter(" ".join(r["text"].lower().split()[:2]) for r in produced)

    fails = Counter()
    for r in rows:
        for a in r["attempts"]:
            if not a["ok"]:
                fails[a["why"].split(":")[0].split("(")[0].strip()] += 1

    # Residual tells the arm did not catch, measured the same way in both arms
    # so the comparison is fair.
    residual = Counter()
    for r in produced:
        if guards.simile_tell(r["text"]):
            residual["simile"] += 1
        if guards.punching_down(r["text"], r["post"]):
            residual["punching down"] += 1
        if guards.generic_reply(r["text"], r["post"]):
            residual["generic"] += 1
        if "—" in r["text"] or "–" in r["text"]:
            residual["em dash"] += 1

    specific = sum(1 for r in produced
                   if not guards.generic_reply(r["text"], r["post"]))

    return {
        "n": n,
        "produced": len(produced),
        "silence_pct": pct(n - len(produced)),
        "len_mean": round(statistics.mean(lens), 1) if lens else 0,
        "len_min": min(lens) if lens else 0,
        "len_max": max(lens) if lens else 0,
        "in_band_pct": pct(sum(1 for L in lens if TARGET_MIN <= L <= TARGET_MAX)),
        "question_pct": pct(sum(1 for r in produced if "?" in r["text"])),
        "specific_pct": pct(specific),
        "tries_mean": round(statistics.mean([r["tries"] for r in rows]), 2),
        "seconds_mean": round(statistics.mean([r["seconds"] for r in rows]), 1),
        "vocab_overlap_mean": round(statistics.mean(overlaps), 4) if overlaps else 0,
        "top_openers": openers.most_common(5),
        "reject_reasons": fails.most_common(12),
        "residual_tells": residual.most_common(),
    }


def by_kind(rows: list[dict]) -> dict:
    out = {}
    for r in rows:
        out.setdefault(r["kind"], []).append(r)
    return {k: score(v) for k, v in sorted(out.items())}


# -------------------------------------------------------------------- report
def md_table(rows: list[list], head: list[str]) -> str:
    lines = ["| " + " | ".join(head) + " |",
             "|" + "|".join("---" for _ in head) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def report(a: list[dict], b: list[dict]) -> str:
    sa, sb = score(a), score(b)
    ka, kb = by_kind(a), by_kind(b)

    def row(label, key, fmt="{}"):
        return [label, fmt.format(sa[key]), fmt.format(sb[key])]

    out = [
        "# Persona evaluation, 100 tweets",
        "",
        f"_Generated {time.strftime('%Y-%m-%d %H:%M')}, local model, "
        f"{sa['n']} posts per arm._",
        "",
        "**Arm A (baseline)**: persona as of `e6510f4`, no per-draft directives, "
        "no second-generation guards.  ",
        "**Arm B (guarded)**: adds the warmth / no-simile / no-question draft "
        "directives and `guards.py`.",
        "",
        "## Headline",
        "",
        md_table([
            row("Replies produced", "produced"),
            row("Gave up (silence)", "silence_pct", "{}%"),
            row("In the 80-180 band", "in_band_pct", "{}%"),
            row("Mean length", "len_mean", "{} ch"),
            row("Ends up asking a question", "question_pct", "{}%"),
            row("Specific to the post", "specific_pct", "{}%"),
            row("Drafts per reply", "tries_mean"),
            row("Seconds per reply", "seconds_mean"),
            row("Vocabulary overlap between replies", "vocab_overlap_mean"),
        ], ["Metric", "A baseline", "B guarded"]),
        "",
        "## Tells that survived into the final reply",
        "",
        md_table(
            [[k, dict(sa["residual_tells"]).get(k, 0), dict(sb["residual_tells"]).get(k, 0)]
             for k in sorted(set(dict(sa["residual_tells"])) | set(dict(sb["residual_tells"])))]
            or [["none", 0, 0]],
            ["Tell", "A", "B"]),
        "",
        "## Why drafts were rejected (arm B)",
        "",
        md_table([[k, v] for k, v in sb["reject_reasons"]] or [["none", 0]],
                 ["Reason", "Count"]),
        "",
        "## By situation (arm B)",
        "",
        md_table([[k, s["produced"], f"{s['silence_pct']}%", f"{s['in_band_pct']}%",
                   f"{s['question_pct']}%", f"{s['specific_pct']}%", s["len_mean"]]
                  for k, s in kb.items()],
                 ["Situation", "Made", "Silent", "In band", "Question", "Specific", "Mean ch"]),
        "",
        "## Most repeated openers (arm B)",
        "",
        md_table([[f"`{o}`", c] for o, c in sb["top_openers"]] or [["none", 0]],
                 ["Opener", "Count"]),
        "",
        "## Every reply, arm B",
        "",
    ]
    for r in b:
        out.append(f"**@{r['handle']}** ({r['kind']}) · {r['post']}")
        if r["text"]:
            flags = [f for f in (guards.simile_tell(r["text"]),
                                 guards.punching_down(r["text"], r["post"]),
                                 guards.generic_reply(r["text"], r["post"])) if f]
            out.append(f"> {r['text']}")
            out.append(f"`{r['archetype_used']}` · {len(r['text'])} ch · "
                       f"{r['tries']} draft(s)"
                       + (f" · **{', '.join(flags)}**" if flags else ""))
        else:
            out.append("> _(no reply: " +
                       "; ".join(a["why"] for a in r["attempts"]) + ")_")
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="docs/PERSONA_EVAL.md")
    ap.add_argument("--json", default="docs/persona_eval.json")
    ap.add_argument("--arm", choices=["a", "b", "both"], default="both")
    args = ap.parse_args()

    tweets = CORPUS[: args.limit] if args.limit else CORPUS
    with session_scope() as session:
        a: list[dict] = []
        b: list[dict] = []
        if args.arm in ("a", "both"):
            print(f"arm A (baseline), {len(tweets)} posts")
            a = run_arm(session, tweets, guarded=False)
        if args.arm in ("b", "both"):
            print(f"arm B (guarded), {len(tweets)} posts")
            b = run_arm(session, tweets, guarded=True)

    (ROOT / args.json).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / args.json).write_text(json.dumps({"a": a, "b": b}, indent=1),
                                  encoding="utf-8")
    if a and b:
        (ROOT / args.out).write_text(report(a, b), encoding="utf-8")
        print(f"\nreport -> {args.out}")
        sa, sb = score(a), score(b)
        for k in ("produced", "silence_pct", "in_band_pct", "question_pct",
                  "specific_pct", "vocab_overlap_mean"):
            print(f"  {k:<22} A={sa[k]:<8} B={sb[k]}")


if __name__ == "__main__":
    main()
