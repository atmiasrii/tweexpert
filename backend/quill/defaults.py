"""Conservative defaults straight from the PRD (§3 says: don't raise them).

Every magic number the spec names lives here so the governor, policy engine
and pipeline read from one place. Overridable via the settings table.
"""
from __future__ import annotations

# --- Governor caps (S-01) ----------------------------------------------
CAP_REPLIES_ASSISTED = 10
CAP_REPLIES_AUTO = 4          # separate, lower global cap (Y-04)
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
RELEVANCE_THRESHOLD_AUTO = 78
FRESHNESS_WINDOW_S = 75 * 60
FRESHNESS_WINDOW_AUTO_S = 30 * 60

# --- Draft caps (R-03) -------------------------------------------------
PER_ACCOUNT_DAILY_DRAFT_CAP = 1
QUEUE_CAP = 12
DRAFT_TTL_S = 3 * 60 * 60            # drafts expire after 3 hours

# --- Poll intervals per tier (I-01) ------------------------------------
POLL_INTERVAL_TIER = {"A": 8 * 60, "B": 25 * 60, "C": 90 * 60}
POLL_JITTER_FRAC = 0.30

# --- Read budget (I-06) ------------------------------------------------
# Raised from 400: a 20-account watchlist plus a For You scan every 5 minutes
# burned the old budget by midday and idled the watcher.
DAILY_READ_BUDGET = 1500

# --- For You auto-replies (own daily cap) ------------------------------
# Kept so assisted + auto + foryou stays under ~50/day, the point where reply
# volume starts tripping X's spam heuristics.
CAP_REPLIES_FORYOU = 30

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
