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
