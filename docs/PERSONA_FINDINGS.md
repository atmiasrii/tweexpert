# Persona findings log

Running notebook of everything wrong with Quill's replies, what was done about
it, and what is still open. Newest observations at the top of each section.
Every claim here comes from a run of `scripts/eval_replies.py` or a live
generation, never from guessing.

The scoring target comes from the X reply research: the author replying to your
reply is worth 75.0 against 0.5 for a like, a mute is -74 and a report -369.
So the ranking of sins is: **generic > smug > flat**. A reply that earns
nothing costs an impression. A reply that earns a mute costs 150 good replies.

---

## Open problems

| # | Problem | Evidence | Status |
|---|---------|----------|--------|
| O-1 | Simile crutch: "X is like Y" analogies | 2/10 showcase replies, 2026-09-02 | guarded, watch for residue |
| O-2 | Question rate ran at 50%, research says ~30% | 5/10 showcase, 2026-09-02 | archetype now enforces it |
| O-3 | Punches down on self-deprecating posts | dan_abramov "rookie mistake at 12 years in" | guarded |
| O-4 | Generic replies that ignore the specific post | naval reply, 2026-09-02 | guarded by lexical overlap |
| O-5 | Model ceiling: `qwen2.5:14b` produces flat lines on abstract posts | aphorism category | open, no fix yet |
| O-6 | No timing signal: replies are drafted without knowing post age | research: reply inside 5-15 min, host post half-life ~80 min | open |
| O-7 | No account tiering: every watched account treated the same | research: target 5-20x own follower count | open |
| O-8 | Retrieval few-shot is thin, so voice leans on the static examples | corpus size on Persona tab | open |
| O-9 | No reply-back attribution: X does not expose who replied | scoreboard counts any replier | open, upper bound only |
| O-10 | Aphorisms turn into generic life advice instead of a reply | eval run 1, aphorism category | open, worst category |
| O-11 | Corpus leakage: the operator's own past post reused as a fresh claim | "shipped" -> "p50 dropped from 90ms to 38ms" | guarded |
| O-12 | Question rate lands at 36%, target 30% | eval run 1 | partly open, see below |
| O-13 | Long replies drift over 180 chars in the selfdep and product categories | eval run 1 in-band 62.5% / 80% | open |

---

## Fixed

### 2026-09-02, second pass (`guards.py`)

**O-1 simile crutch.** The model reaches for a clever comparison when it has
nothing concrete: *"Like aiming for Mars while your rocket's still in the
garage."* Humans on X do this rarely; a bot does it every fifth reply, which
makes it a cadence tell. `guards.simile_tell` blocks comparison constructions
(`is/feels/reads/sounds like`, `reminds me of`, `think of it as`, `the X
equivalent of`, sentence-initial `like <gerund>`) while leaving plain "I like
this" alone.

**O-2 question rate.** Telling the model "about a third of replies" does not
hold: it asked a question in 10/10, then 5/10. Fixed structurally instead. The
archetype is chosen per post from a weighted draw, and
`guards.question_violation` rejects a question from any archetype except
`question`. The rate is now exactly the archetype weight (~29%), not a mood.

**O-3 punching down.** dan_abramov posted a self-deprecating bug story and Quill
replied *"missing await is a rookie mistake at 12 years in"*. Correcting someone
who already made the joke about themselves is the fastest route to a mute, and a
mute is -74 against the +75 a reply-back pays. Two-part fix: detect a
self-deprecating parent (first person plus an admission) and swap the draft
directive to warmth, then reject condescending vocabulary in that context.

**O-4 generic replies.** The Naval reply (*"leveraging skills well means
choosing projects that need them"*) could sit under a thousand different posts.
`guards.generic_reply` requires the reply to share at least one non-stopword
with the post, unless it carries its own concrete detail (a number, or an
unusual long noun). Crude, but it catches the exact failure and is cheap.

### 2026-09-02, eval run 1 (100 tweets, A/B)

Full report in `PERSONA_EVAL_run1.md`. The guards did what they were built to
do, and the report immediately turned up three failures nobody had seen.

| | A baseline | B guarded |
|---|---|---|
| simile in the final reply | 9 | **0** |
| generic reply | 3 | **0** |
| punching down | 1 | **0** |
| specific to the post | 97% | **100%** |
| asks a question | 45% | 36% |
| gave up entirely | 0% | 0% |
| drafts per reply | 1.07 | 1.21 |

The cost of the guards is 0.14 extra drafts per reply and half a second. They
reject 21 drafts per 100, led by similes (10) and questions from the wrong
archetype (4). Nothing was lost to silence, so the guards are not starving the
pipeline.

Openers were all unique across 100 replies, so the persona has not collapsed
into a few stock moves. Vocabulary overlap between replies is 0.0067, flat
between arms.

**What run 1 exposed:**

- **O-11, the worst one. Corpus leakage inventing a receipt.** Reply to the
  single word "shipped": *"shipped and p50 dropped from 90ms to 38ms with
  batching and killing a dumb lock."* Those numbers are from the operator's own
  past post, retrieved as a few-shot and re-emitted as a fresh claim. A false
  specific number under a stranger's post is exactly what earns a correction or
  a mute. Now blocked by `guards.invented_numbers`: a number that is not in the
  post it answers, and is not a year or a small ordinary count, is rejected.
  Note this contradicted acceptance test T-08, whose "good" example was
  *"constrained decoding holds schema at 7B. measured 40ms."* The voice card
  already forbids exactly that ("no fake 'I measured 40ms p50'"), so the test
  example was violating the spec it tested; it was replaced.
- **Thin posts should be silence, not a reply.** "gm", "soon.", "shipped",
  "big if true" all got replies. The research's hard gate is: no specific value
  to add, skip. `guards.too_thin` now skips them, deliberately narrow so a
  short but real post still gets answered.
- **"not just X, it's Y" was slipping through** in the form "isn't just X,
  it's Y", which the old regex missed.
- **O-10, aphorisms are the weakest category.** Naval, paulg and wisdom_acct
  all drew generic advice back ("leverage isn't just about connections, it's
  about resources and knowledge"). Technically specific enough to pass the
  guards, but it lectures instead of replying. No fix yet.

### 2026-09-02, observations from the live queue

Walking the real queue in the UI, not the corpus, turned up three things:

- **The simile rate was worse than the showcase suggested: 6 of 17 queued
  drafts (35%) used one.** "like shipping software on crack", "like aiming for
  the applause of a half-empty room", "templates in a trench coat", "sounds
  like overkill", "feels like the wildcard". Running the new guards over the
  queue removed 7 drafts (5 similes, 1 @-mention) and kept 10.
- **Words getting glued together**: "made the black marketObsolete". Fixed in
  `normalize` with a lower-to-upper split that leaves OpenAI, PyTorch and
  iPhone alone.
- **The Discovery inbox was showing every post twice.** Each saved-search run
  re-inserted the same posts as new `DiscoveryItem` rows. Fixed at insert time
  and de-duplicated in the listing for rows already in the table.

### 2026-09-02, first pass (`e6510f4`)

Rewrote the objective from "sounds good" to "earns a reply from the author".
New register (operator with receipts), four ranked archetypes, the 80-180
character anchor band, compliment-only rejection, ~20 new tell-list phrases,
critic rewritten to judge reply-back odds. Read budget 400 to 1500 (it was
exhausting by midday and idling the watcher); For You cap 40 to 30 so the day
total stays under the ~50 mark where X's spam heuristics start.

---

## Observations that are not bugs

- **Silence is the correct output** when nothing clean survives three
  archetypes. `quick_reply` now returns `""` rather than shipping the last
  rejected draft, which it used to do.
- **Thin posts** ("gm", "soon.", "shipped") have nothing to add to. High
  silence in that category is the system working, not failing.
- **Vocabulary overlap between replies** is the template detector. If it climbs,
  the persona has collapsed into a few stock moves regardless of how good any
  single reply reads.
