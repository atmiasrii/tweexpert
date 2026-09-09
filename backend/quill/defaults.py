"""Conservative defaults straight from the PRD (§3 says: don't raise them).

Every magic number the spec names lives here so the governor, policy engine
and pipeline read from one place. Overridable via the settings table.
"""
from __future__ import annotations

# --- Governor caps (S-01) ----------------------------------------------
# One ceiling across every reply path, checked in addition to the per-mode caps
# below. The per-mode numbers are deliberately loose now so that this total is
# what actually binds; without it the three paths cannot see each other and the
# real daily volume is their sum.
#
# 49 is the operator's choice. Context: X's May 2026 platform limit for a free
# account is 200 replies/day (Premium lifts it), so the platform is not the
# constraint. The ~50/day figure is the practitioner estimate of where spam and
# deboost heuristics start reacting, and Premium does not change that.
CAP_REPLIES_TOTAL = 49

# The per-mode caps exist so one path cannot monopolise the day, but the
# total above is the real ceiling, so they are set to it. Lower any of them
# via settings to ration a single path.
CAP_REPLIES_ASSISTED = CAP_REPLIES_TOTAL
CAP_REPLIES_AUTO = CAP_REPLIES_TOTAL      # (Y-04)
CAP_POSTS = 6
CAP_THREADS = 1

# --- Spacing / jitter (S-02, Q-05) -------------------------------------
MIN_WRITE_SPACING_S = 9 * 60          # 9 minutes between writes
WRITE_JITTER_FRAC = 0.40              # ±40% on scheduled sends
AUTO_DELAY_MIN_S = 4 * 60             # auto reply delay lower bound
AUTO_DELAY_MAX_S = 40 * 60            # auto reply delay upper bound

# --- Quiet hours (S-03) ------------------------------------------------
QUIET_START = "23:30"
QUIET_END = "07:30"
QUIET_DRIFT_MIN = 20                  # ± minutes random daily drift

# --- Burst guard (S-05) ------------------------------------------------
BURST_MAX_WRITES = 3
BURST_WINDOW_S = 20 * 60             # within 20 minutes

# --- Shadow gate (Y-03) ------------------------------------------------
SHADOW_MIN_DAYS = 7
SHADOW_MIN_DRAFTS = 20

# --- Relevance / freshness (R-01, R-02) --------------------------------
RELEVANCE_THRESHOLD = 60
# Measured, not guessed: on-topic fresh feed posts score 59-72, so the old 78
# auto bar was unreachable. Relevance decides "worth drafting"; the critic and
# the confidence bar decide "worth sending".
RELEVANCE_THRESHOLD_AUTO = 55
# The home/For You feed is not chronological (ages seen: 30 min to 3.7 days),
# so a 30-minute window discarded almost everything. 90 minutes matches the
# research's reply window and the hard skip gate in relevance.py.
FRESHNESS_WINDOW_S = 90 * 60
FRESHNESS_WINDOW_AUTO_S = 90 * 60

# --- Draft caps (R-03) -------------------------------------------------
PER_ACCOUNT_DAILY_DRAFT_CAP = 3
QUEUE_CAP = 60
DRAFT_TTL_S = 3 * 60 * 60            # drafts expire after 3 hours

# --- Poll intervals per tier (I-01) ------------------------------------
POLL_INTERVAL_TIER = {"A": 8 * 60, "B": 25 * 60, "C": 90 * 60}
POLL_JITTER_FRAC = 0.30

# --- Read budget (I-06) ------------------------------------------------
# Raised from 400: a 20-account watchlist plus a For You scan every 5 minutes
# burned the old budget by midday and idled the watcher.
DAILY_READ_BUDGET = 2500

# --- For You auto-replies (own daily cap) ------------------------------
# Kept so assisted + auto + foryou stays under ~50/day, the point where reply
# volume starts tripping X's spam heuristics.
CAP_REPLIES_FORYOU = CAP_REPLIES_TOTAL

# For You sweep: how many unique authors one batch answers, and how long an
# author is off-limits afterwards. Author-level cooldown did not exist before,
# so one sweep could hand the same handle three replies.
FORYOU_PER_RUN = 10
FORYOU_AUTHOR_COOLDOWN_H = 24
# Unknown For You authors are not on the watchlist, so they have no tier. The
# old code fell through to "C" (0.5), which capped their score below the auto
# threshold no matter how good the post was.
FORYOU_TIER_WEIGHT = 0.75

# --- Thread context (I-04) ---------------------------------------------
THREAD_CONTEXT_DEPTH = 3

# --- Persona (P-03, P-05, P-07) ----------------------------------------
DRAFT_TEMPERATURE = 0.85
CRITIC_TEMPERATURE = 0.2
FEWSHOT_MIN = 8
FEWSHOT_MAX = 12
CRITIC_MIN_PASS = 3                  # below 3 on any axis dropped
CRITIC_MIN_AUTO = 4                  # auto requires 4+ on all axes
SIMILARITY_COSINE_MAX = 0.90        # reject above this vs last 100
SIMILARITY_NGRAM_MAX = 0.55         # lexical n-gram overlap ceiling
SIMILARITY_HISTORY = 100

# --- Session / ops (E-03, O-02, O-06) ----------------------------------
HEARTBEAT_INTERVAL_S = 15 * 60      # session heartbeat
SESSION_FAIL_THRESHOLD = 3          # consecutive fails = session-dead
PROC_HEARTBEAT_INTERVAL_S = 60      # per-process heartbeat
WATCHDOG_STALE_S = 5 * 60           # alert if heartbeat stale beyond this
CHROMIUM_RESTART_HOUR = 4           # daily restart during quiet hours
DEBUG_RETENTION_DAYS = 7

# --- Auto-disable triggers (Y-06) --------------------------------------
CONSECUTIVE_FAIL_DISABLE = 2

# --- Authorization (Y-01) ----------------------------------------------
AUTHORIZATION_TTL_S = 60 * 60       # authorizations expire after 1h
NOTIFY_TOKEN_TTL_S = 60 * 60        # notification action tokens (K-04)

# --- Evergreen / schedule (C-06) ---------------------------------------
EVERGREEN_MIN_REPEAT_DAYS = 45

# --- Analytics decay schedule (M-01), seconds after posting ------------
METRIC_SCHEDULE_S = [1 * 3600, 6 * 3600, 24 * 3600, 72 * 3600]

# --- Tell-list (P-04): generic-AI phrasing killed deterministically ----
TELL_LIST = [
    "great point",
    "great question",
    "absolutely",
    "i couldn't agree more",
    "i couldn't agree more",
    "this is huge",
    "game-changer",
    "game changer",
    "let that sink in",
    "this.",
    "well said",
    "spot on",
    "couldn't have said it better",
    "you nailed it",
    "so true",
    "this is the way",
    "as an ai",
    "in today's fast-paced world",
    "at the end of the day",
    "needle-mover",
    "move the needle",
    # classic model giveaways
    "delve",
    "delving",
    "in a world where",
    "let's be honest",
    "the reality is",
    "it's worth noting",
    "underscores",
    "a testament to",
    "tapestry",
    "boasts",
    "elevate your",
    "seamless",
    "in today's",
    "dive into",
    "let's dive",
    "unpack this",
    "it's giving",
    "buckle up",
    "here's the kicker",
    "the takeaway",
    "in conclusion",
    "rest assured",
    "look no further",
    "when it comes to",
    "navigating the",
    "ever-evolving",
    "the bottom line",
    # puffery + weasel attribution + faux insight
    "pivotal",
    "vibrant",
    "landscape",
    "experts agree",
    "studies show",
    "research shows",
    "what nobody tells you",
    "the part everyone misses",
    "nobody talks about",
    "nobody is talking about",
    "it's already here",
    "is already here",
    "the future isn't coming",
    "game changing",
    "game-changing",
    "revolutionary",
    "unlock",
    "supercharge",
    "secret sauce",
    "hits different",
    "kudos",
    "context matters",
    "worth unpacking",
    "happens to the best of us",
    "must-have",
    "food for thought",
]

# --- Openers that read as bots (P-04) ----------------------------------
BANNED_OPENERS = ["honestly,", "honestly ", "not gonna lie", "hot take:",
                  "certainly", "moreover", "additionally", "furthermore",
                  "great ", "love this", "well said", "agreed.", "agreed!",
                  "exactly.", "exactly!", "this is so"]

# --- Compliment-only replies (worst archetype: zero reply-back value) ---
COMPLIMENT_WORDS = ["great", "love", "amazing", "awesome", "nice", "agreed",
                    "agree", "exactly", "facts", "based", "fire", "banger",
                    "brilliant", "well said", "so good", "this", "true",
                    "respect", "congrats", "huge", "incredible", "goat"]

# --- Content-safety blocked topics for R-04 default --------------------
DEFAULT_BLOCK_TOPICS = [
    "death", "died", "passed away", "illness", "cancer", "diagnosis",
    "funeral", "suicide", "politics", "election", "lawsuit", "lawyer",
    "indictment", "verdict",
]

# --- Safety gate: never auto-send these (X-06) -------------------------
UNSAFE_PATTERNS = [
    r"\bhttps?://",                 # links
    r"#\w+",                        # hashtags (also Y-02)
]

# Watcher: the home sweep covers the whole watchlist in one read; these are the
# extra direct profile reads per sweep, as a backstop for tier A posts the
# timeline buries.
DEEP_READS_PER_SWEEP = 4

# --- unattended run (S22) ------------------------------------------------
RUN_TARGET_REPLIES = 40             # replies the day owes
RUN_DEADLINE_LOCAL = "23:00"        # local; quiet hours start 23:30, so this uses the day
RUN_HISTORY_DAYS = 14               # finished run records kept for the dashboard
RELAX_STEP_INTERVAL_S = 15 * 60     # one intake step per window, either way
SUPERVISOR_INTERVAL_S = 60          # how often the API checks the run
RESTART_COOLDOWN_S = 5 * 60         # between restarts of the same process
RESTART_MAX_PER_PROC = 6            # per process per day, then hand it to a human
LOGIN_WINDOW_S = 15 * 60            # how long a hand sign-in owns the profile
