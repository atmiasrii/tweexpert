"""Read a day's trace and say where the posts went.

    python scripts/trace_report.py                # today
    python scripts/trace_report.py 2026-09-10     # a given day
    python scripts/trace_report.py 2026-09-10 --posts   # every post, one line each

Reads backend/data/traces/YYYY-MM-DD.jsonl, the one-line-per-event log the
trace module writes alongside the database rows. No server needed.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACES = ROOT / "backend" / "data" / "traces"
TERMINAL = {"sent", "scheduled", "queued", "discarded", "silent", "dismissed",
            "skipped", "failed", "needs_review"}


def load(day: str) -> list[dict]:
    path = TRACES / f"{day}.jsonl"
    if not path.exists():
        sys.exit(f"no trace for {day} at {path}")
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    day = args[0] if args else date.today().isoformat()
    show_posts = "--posts" in sys.argv
    events = load(day)

    runs: dict[int, dict] = {}
    posts: dict[tuple[int, str], dict] = {}
    for e in events:
        kind = e.get("event")
        rid = e.get("run_id")
        if kind == "run_start":
            runs[rid] = {"kind": e.get("kind"), "source": e.get("source"), "at": e["at"]}
        elif kind == "seen":
            posts[(rid, e["post"])] = {"author": e.get("author"), "source": e.get("source"),
                                       "likes": e.get("likes", 0), "outcome": "", "why": "",
                                       "sent_id": ""}
        elif kind in TERMINAL or kind in ("scored", "drafting", "sending", "watching"):
            key = (rid, e.get("post"))
            row = posts.setdefault(key, {"author": "", "source": "", "likes": 0,
                                         "outcome": "", "why": "", "sent_id": ""})
            if kind in TERMINAL:
                row["outcome"] = kind
                row["why"] = e.get("detail", "")
            if e.get("sent_x_post_id"):
                row["sent_id"] = e["sent_x_post_id"]

    print(f"{day}: {len(runs)} runs, {len(posts)} post-sightings\n")

    by_kind = Counter(r["kind"] for r in runs.values())
    print("runs by kind:", dict(by_kind))

    outcomes = Counter(p["outcome"] or "(no terminal)" for p in posts.values())
    print("\noutcomes:")
    for k, v in outcomes.most_common():
        print(f"  {k:16} {v}")

    print("\nwhy posts were skipped or binned (top 15):")
    why = Counter()
    for p in posts.values():
        if p["outcome"] in ("skipped", "discarded", "dismissed"):
            # collapse numbers so "relevance 31.2 below the floor" groups
            w = "".join(ch if not ch.isdigit() else "#" for ch in p["why"])
            why[w[:70]] += 1
    for k, v in why.most_common(15):
        print(f"  {v:4d}  {k}")

    src = defaultdict(Counter)
    for p in posts.values():
        src[p["source"] or "?"][p["outcome"] or "(none)"] += 1
    print("\nby source:")
    for s, c in src.items():
        print(f"  {s:22} seen {sum(c.values()):4d}  sent {c.get('sent', 0):3d}  "
              f"scheduled {c.get('scheduled', 0):3d}  skipped {c.get('skipped', 0):3d}  "
              f"binned {c.get('discarded', 0) + c.get('dismissed', 0):3d}")

    sent = [p for p in posts.values() if p["outcome"] == "sent"]
    if sent:
        print(f"\nsent ({len(sent)}):")
        for p in sent:
            print(f"  @{p['author']:20} https://x.com/i/status/{p['sent_id']}")

    if show_posts:
        print("\nevery post:")
        for (rid, pid), p in sorted(posts.items()):
            print(f"  run {rid:4} @{p['author'] or '?':18} {p['source']:20} "
                  f"{p['outcome'] or '-':12} {p['why'][:60]}")


if __name__ == "__main__":
    main()
