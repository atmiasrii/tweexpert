# Quill — what it is and what it is for

The intent behind the project, in one place: what it should do, how it should
behave, and the decisions taken along the way. `ARCHITECTURE.md` describes how
the code is laid out; this describes *why*, and what "working" means.

---

## The one-sentence goal

Quill runs unattended on this machine and replies on X as `@barryallendgx`, in
the operator's own voice, well enough that nobody can tell it is software, and
without ever needing the operator to approve anything.

Three parts of that sentence are load-bearing:

- **Unattended.** Press Start once and leave. If it stops, it restarts itself.
  It should not need supervision, and it should not build a queue of work for
  the operator to get through.
- **In the operator's voice.** A reply that reads as generated is worse than no
  reply. Quality is enforced by machine, not by a human reviewer.
- **Without approval.** Auto mode means auto. A draft either goes out or is
  binned. The review queue exists for assisted mode and for genuine
  "a human must look at this" cases, and nothing else.

---

## What the operator asked for, across sessions

Recorded because these are the requirements, not suggestions.

| Ask | Decision |
|---|---|
| Persona rewritten to match the X reply research | Objective changed from "sounds good" to "earns a reply from the author". Four ranked archetypes, an 80-180 character band, a tell-list of AI phrasing, a critic that judges reply-back odds |
| Reply quality bar | **Strict. Only clearly good replies.** Silence is an acceptable output |
| Rate limits | Written for an **X Premium** account: 120 replies/day ceiling, 5-minute minimum spacing, burst 4 per 20 min |
| The shadow-period gate before auto | **Removed entirely** at the operator's request |
| Approval | **Never required in auto mode.** A queue nobody reads is worse than a reply that was never sent |
| Sending | Quill's own browser is the sender. The Chrome extension is optional and nothing depends on it |
| Proof of sending | A reply counts as sent only when it is **found on the page afterwards** |
| Daily target | **40 replies by 23:00 local**, with the run supervising itself toward it |
| Falling behind | Widen what gets *considered*, never lower the bar on what gets *said* |
| Post selection | Prefer fresh posts and high-engagement authors, including brand-new posts |
| Writing style | **No em dashes** in generated replies, ever |
| Secrets | `.env`, the browser profile and credentials are never committed. The X password is never handled by Quill; sign-in is done by hand |

---

## How it is supposed to behave, minute to minute

1. **Press Start.** The API launches two processes and records the time. The
   day's run record opens with its target and deadline.
2. **Read the For You feed first**, not after a timer. Collect ~30 posts,
   merged with a live "Following, newest first" search.
3. **Shortlist.** Drop posts that are too old, too thin, saturated with
   replies, reply-restricted, from a blocked author, from an author already
   answered inside the cooldown, or below the relevance floor. One post per
   author per sweep.
4. **Draft** each survivor with the local model: several candidate angles, a
   critic, then guards for similes, questions, invented numbers, fabricated
   experience, lecturing, generic filler and glued words.
5. **Decide.** Above the confidence bar it is scheduled; below it, binned. No
   third option.
6. **Send** on a stagger of one reply per spacing interval, by opening the
   post's stored permalink, replying in place, then reloading to confirm the
   reply exists and reading back its real id.
7. **Watch** the timeline in between for new posts from the watchlist.
8. **Supervise.** Every minute, check that both processes are alive and
   beating, restart what is not, and compare progress against the target.
9. **Stop at quiet hours** (23:30 to 07:30 local, with daily drift).

---

## The safety model, and why it is not negotiable

Quill drives a real, logged-in X account. Three things protect it:

- **The governor** is the single authority on how much gets written: daily
  ceiling, per-mode caps, minimum spacing, burst guard, quiet hours, rest days
  and a kill switch. Nothing writes without asking it first.
- **Authorizations** are single-use and expiring. There is no code path from a
  draft to a post that does not consume one.
- **One process owns Chromium.** The profile directory takes exactly one
  owner. A second process opening it can corrupt the profile and cost the
  signed-in X session, which is the one failure only a human can undo. This is
  why the supervisor refuses to restart the browser while a manual login window
  is open, and why the worker runs with the engine disabled.

The behavioural budget sits *under* the platform ceiling on purpose. Premium
lifts X's own limits; it does not make X's spam heuristics friendlier, and no
subscription makes a templated reply look human.

---

## What actually limits output

Measured, not assumed. In order of cost:

1. **Re-reading the same feed.** The watch sweep collected thirty posts with
   full scrolling every ninety seconds, roughly 28 seconds of scrolling each
   time, on the single browser everything else queues behind. In one measured
   80-minute window there were 64 feed collections for 6 For You sweeps.
2. **Model time.** Ten posts drafted per sweep, several candidates each plus a
   critic. Around 87 chat calls per sweep.
3. **The quality bar.** On 9 September, 100 drafts were written and 23 sent.
   That is 71% of all model work discarded by design. It is the strict setting
   working, and it is the largest remaining lever if volume matters more.
4. **Write spacing.** Five minutes between replies caps the day at ~120. This
   has never been the binding constraint.

A fixed embedding bug is worth recording: the similarity guard re-embedded all
one hundred past replies for every candidate, 6,631 embedding calls against 636
writing calls in one evening. Caching them cut For You sweeps from 27 minutes
apart to 9.

---

## What is built

- **Processes.** `api` (owns no browser, supervises), `worker` (scheduler, no
  engine), `browser` (sole Playwright owner, drains writes, reads feeds, sends).
- **Pipeline.** Detect, gate, score, draft, guard, decide, schedule, send,
  verify.
- **Persona.** Four archetypes with dials, a voice card, a critic, nine guards,
  a similarity check against recent replies.
- **Governor.** Tier-driven budgets, caps, spacing, quiet hours, kill switch.
- **Run supervisor.** Start time, target, deadline, pace, an intake ladder, and
  process restart with cooldown, a daily ceiling and two hard suppressions.
- **Dashboard.** Live pipeline view, sent replies with per-reply progress,
  today's run card, watchlist, analytics.
- **Recovery.** Engine rebuild on a dropped page, a call budget that kills a
  wedged Playwright driver, startup reconcile that settles sends left in
  flight, dead-handle detection, and a home-read guard.

---

## Known gaps

- Feed reading is far more expensive than it needs to be, and every read is
  serialised behind one browser page.
- Post selection does not yet use author follower counts or a post's own
  engagement velocity; account tier stands in for both.
- The confidence bar bins roughly seven in ten drafts. Whether that is the
  right trade is an open product question.
- One reply on 8 September contained a fabricated anecdote. The guard that
  catches those runs on the unattended path only.

---

## House rules for anyone working on this

- Never commit `.env`, the browser profile, or anything with a credential in it.
- Never write a reply containing an em dash.
- A test that proves the bug is part of the fix, not optional.
- If a change could cause two processes to touch the Chrome profile, it is
  wrong until proven otherwise.
- Report what actually happened. If a run fell short, say by how much and why.
