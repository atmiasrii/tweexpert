"""Derive the auto-send confidence threshold from measured drafts.

`foryou_auto_min` was 16, and nobody derived that from anything. This runs the
real drafting path over a corpus, records what the critic actually scores, and
picks the cut that keeps roughly the top slice the operator asked for while
still satisfying the research bands (80-180 characters, questions near 30%,
no guard violations).

Run:  python scripts/calibrate_threshold.py [--live N] [--strictness 0.2]

  --live N      also sample N posts from the real For You feed, so the
                distribution reflects what the account actually sees rather
                than only the fixed corpus.
  --strictness  fraction of drafts allowed through (0.2 = strict, top fifth).
  --apply       write the chosen values into the settings table.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

from eval_corpus import CORPUS                                  # noqa: E402
from quill.db.engine import session_scope                       # noqa: E402
from quill.db.settings_store import set_setting                 # noqa: E402
from quill.persona import engine as persona, guards             # noqa: E402
from quill.persona.corpus import operator_vocabulary            # noqa: E402
from quill.pipeline import relevance as relevance_mod           # noqa: E402
from quill.pipeline.foryou_auto import AXES                     # noqa: E402

ANCHOR_MIN, ANCHOR_MAX = 80, 180


def _sample_live(session, n: int) -> list[dict]:
    """Real posts off the For You feed, so the numbers are about this account."""
    from quill.bus.action_bus import get_bus
    posts = get_bus().submit_read("presence", "home") or []
    out = []
    for p in posts[:n]:
        if relevance_mod.skip_reason(p):
            continue
        out.append({"h": p.author_handle, "k": "live", "t": p.text,
                    "rel": relevance_mod.score(session, p, None)})
    return out


def measure(session, items: list[dict]) -> list[dict]:
    vocab = operator_vocabulary(session)
    rows = []
    for i, it in enumerate(items, 1):
        result = persona.generate(session, it["t"], auto=True)
        if not result.has_output:
            rows.append({**it, "produced": False})
            print(f"  [{i:>3}/{len(items)}] {it['h'][:16]:<16} no angle", flush=True)
            continue
        chosen = result.candidates[result.chosen_index]
        crit = chosen.critic or {}
        axis_sum = sum(int(crit.get(a, 0)) for a in AXES)
        text = result.final_text
        flags = [f for f in (guards.simile_tell(text),
                             guards.punching_down(text, it["t"]),
                             guards.invented_numbers(text, it["t"]),
                             guards.generic_reply(text, it["t"]),
                             guards.lecturing(text, it["t"]),
                             guards.fabricated_experience(text, vocab)) if f]
        rows.append({**it, "produced": True, "text": text, "axis_sum": axis_sum,
                     "min_axis": min(int(crit.get(a, 0)) for a in AXES),
                     "len": len(text), "question": "?" in text, "flags": flags})
        print(f"  [{i:>3}/{len(items)}] {it['h'][:16]:<16} sum={axis_sum:<3} "
              f"{len(text):>3}ch {'!' + flags[0] if flags else ''}", flush=True)
    return rows


def choose(rows: list[dict], strictness: float) -> dict:
    """The lowest axis_sum whose accepted set is both small enough and clean."""
    good = [r for r in rows if r.get("produced") and not r["flags"]]
    if not good:
        return {"error": "no clean drafts to calibrate on"}
    sums = sorted(r["axis_sum"] for r in good)
    target_n = max(1, int(round(len(rows) * strictness)))

    best = None
    for cut in range(4, 21):
        accepted = [r for r in good if r["axis_sum"] >= cut and r["min_axis"] >= 4]
        if not accepted:
            break
        in_band = sum(1 for r in accepted if ANCHOR_MIN <= r["len"] <= ANCHOR_MAX)
        stats = {
            "cut": cut,
            "accepted": len(accepted),
            "accept_rate": round(100 * len(accepted) / len(rows), 1),
            "in_band_pct": round(100 * in_band / len(accepted), 1),
            "question_pct": round(100 * sum(1 for r in accepted if r["question"])
                                  / len(accepted), 1),
            "mean_len": round(statistics.mean(r["len"] for r in accepted), 1),
        }
        if best is None or abs(len(accepted) - target_n) < abs(best["accepted"] - target_n):
            best = stats
    return {"distribution": Counter(sums), "recommended": best,
            "clean": len(good), "measured": len(rows)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", type=int, default=0)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--strictness", type=float, default=0.2)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with session_scope() as session:
        items = [{"h": c["h"], "k": c["k"], "t": c["t"]} for c in CORPUS[: args.limit]]
        if args.live:
            live = _sample_live(session, args.live)
            print(f"sampled {len(live)} live For You posts")
            items += live
        print(f"measuring {len(items)} posts")
        rows = measure(session, items)
        report = choose(rows, args.strictness)

        print("\naxis_sum distribution (clean drafts only)")
        for k in sorted(report.get("distribution", {})):
            n = report["distribution"][k]
            print(f"  {k:>2} | {'#' * n} {n}")

        rec = report.get("recommended")
        if not rec:
            print(report.get("error"))
            return
        print(f"\nrecommended foryou_auto_min = {rec['cut']}")
        print(f"  accepts {rec['accepted']} of {report['measured']} "
              f"({rec['accept_rate']}%)")
        print(f"  in the 80-180 band: {rec['in_band_pct']}%   "
              f"asks a question: {rec['question_pct']}%   "
              f"mean {rec['mean_len']} ch")

        rels = [r["rel"] for r in rows if r.get("rel") is not None]
        rel_cut = round(statistics.median(rels), 1) if rels else None
        if rel_cut:
            print(f"recommended foryou_relevance_min = {rel_cut} "
                  f"(median of {len(rels)} live posts)")

        if args.apply:
            set_setting(session, "foryou_auto_min", rec["cut"])
            if rel_cut:
                set_setting(session, "foryou_relevance_min", rel_cut)
            print("\napplied to settings")

        out = ROOT / "docs" / "threshold_calibration.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(
            {"recommended": rec, "rows": rows}, indent=1, default=str), encoding="utf-8")
        print(f"detail -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
