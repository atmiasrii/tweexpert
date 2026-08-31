# Quill architecture

```
  ┌───────────────────────────────────────────────────────────┐
  │  Chrome Extension (MV3)       Studio (React/Vite/TS)       │
  │  · service worker             · Home · Autopilot · Compose │
  │  · timeline content script    · Schedule · Watchlist ...   │
  │  · reply-queue sidebar        · Analytics · Persona · Ops  │
  └──────────────┬───────────────────────────┬────────────────┘
       localhost │ (shared secret)   REST+SSE │ (behind tunnel + auth)
  ┌──────────────┴───────────────────────────┴────────────────┐
  │  API — FastAPI  (accounts, queue, persona, governor, ops)  │
  └───────┬──────────────┬──────────────┬──────────────────────┘
   Watcher│        Persona│        Policy│+ Governor
   Notifier        retrieve         caps · jitter · quiet · kill
          │        draft×3          │
          └────────critic───────────┤
  ┌────────────────────────────────────────────────────────────┐
  │  ACTION BUS — single consumer, mutex, idempotency, audit    │
  └───────┬────────────────────────────────┬───────────────────┘
          │                                │
  ┌───────┴──────────┐          ┌──────────┴─────────────────────┐
  │ Chrome extension │          │ Playwright engine (overnight)  │
  │ (browser open)   │          │ headed Xvfb · selectors.yaml   │
  │ real fingerprint │          │ canary · heartbeat · presence  │
  └───────┬──────────┘          └──────────┬─────────────────────┘
          └──────────────┬─────────────────┘  x.com
   SQLite WAL+FTS5 · Ollama/vLLM · Supervisor/watchdog
```

## Processes (A-02)

Three backend processes share one SQLite DB and one action bus:

- **api** — FastAPI. Serves the dashboard + REST + SSE. In the container it
  enqueues writes (`QUILL_DEFER_WRITES=1`) rather than touching the engine.
- **worker** — APScheduler: reconciliation, watchdog, backups, degradation, and
  (single-box only) the engine jobs. In docker it runs no engine jobs
  (`QUILL_WORKER_RUNS_ENGINE=0`).
- **browser** — the **sole owner** of the Playwright session. Drains pending write
  intents, runs the watcher/presence/canary/heartbeat/send schedules, and restarts
  Chromium during quiet hours (O-06).

Plus a fourth surface — the **Chrome extension** — running in the operator's own
Chrome. It reports timeline posts and shows the queue, but never writes directly.

## The action bus (§7) — why it exists

The browser is one single-threaded shared resource. Two writes must never overlap
and a crash must never double-post. So **everything** that touches the engine goes
through one queue:

- **One consumer, one mutex** (Q-01). `submit_read`/`submit_write` both take the
  process lock; `max_concurrent` is instrumented and asserted `== 1` (T-06).
- **Intent before execution** (Q-02). A row is written with an idempotency key
  `sha256(kind|target|content)` *before* the engine is called. On startup,
  `reconcile()` checks whether each unfinished write already exists on X: if yes it
  is marked `reconciled` (never resent); if the outcome is ambiguous it is
  `abandoned`, never blindly retried (Q-03). That's T-05.
- **Idempotent replay.** An identical write already `done` is skipped.
- **Audit everything** (Q-04). Every action row records kind, target, issuer,
  timings, outcome, resulting post id, and a screenshot path on failure.
- **Burst + spacing** are enforced at the bus via the governor (Q-05, S-05).

## Authorization (Y-01) — autonomy as a dial

`ActionAuthorization` is a required typed parameter on every content write. It is
issued by a **human tap** (dashboard or notification — same code path, K-02) or by
the **policy engine** in auto mode when *every* gate in Y-02 holds. It is
single-use and expiring. There is no code path to a write without one; attempting
it is a hard error that is logged and alerted (T-02).

Modes run **shadow → assisted → auto**, per account. The shadow period is enforced
in code (Y-03): an account cannot switch to auto until it has spent the minimum
days and reviewed drafts (T-04).

## Hybrid — extension vs. Playwright, and the tradeoffs

Quill can reach X two ways, both behind the same bus:

| | Chrome extension (MV3) | Playwright engine |
|---|---|---|
| **Runs in** | the operator's own Chrome, while open | a headed Chromium under Xvfb, 24/7 |
| **Fingerprint** | the operator's real one | a separate clean profile |
| **Session telemetry** | real human scroll/dwell between actions | synthetic (presence simulator compensates) |
| **Availability** | only when the browser is open | overnight + scheduled |
| **Detection surface** | lower — indistinguishable from a human tab | higher — a separate automated process |
| **Role** | reads timeline, surfaces the queue; **never writes directly** | scheduled posts, overnight polling, presence, sends |

**Why both.** The extension is the *safer* automation path — a real fingerprint and
real human events are much harder for behavioural detection to flag than a clean
Playwright profile. But an extension only exists while Chrome is open; the operator
sleeps and the browser closes. The Playwright engine covers the unattended hours,
and the **presence simulator** (§12) makes that session look used because it *is*
being used — scrolling, dwelling, occasionally searching — so an account that only
ever writes on a schedule isn't misclassified as a bot at the telemetry layer.

**Cost of the hybrid.** Two code paths to the same DOM. We contain it by keeping
**all** selectors in `selectors.yaml` (E-06) with a canary job (E-07) that disables
auto mode the moment a selector moves (T-11); the extension mirrors the same
`data-testid` lookups. Writes are unified: the extension hands off to the
authenticated dashboard, which issues the authorization and posts via the bus, so
there is exactly one write path regardless of surface.

## Offline / fixture engine (I-05)

`FixtureEngine` implements the identical `BrowserEngine` interface from committed
JSON. The whole product — dashboard, pipeline, tests — runs with no session, no
network and no GPU (T-01). The same interface has test hooks to simulate session
death (T-10), challenges (E-05) and selector misses (T-11). Model calls fall back
to a deterministic offline generator, including a critic that flags prompt
injection (T-09).

## Data (§17)

SQLite in WAL mode with FTS5 over post/style text; embeddings stored as blobs with
brute-force cosine (D-01) — at single-account scale nothing else is warranted.
Alembic migrations from the first commit (D-02). Nightly encrypted backup of the
database, voice card and browser profile (D-03, E-04).

## Graceful degradation (O-05)

Model unreachable pauses drafting but not the studio (offline fallback keeps the
pipeline alive); session dead pauses everything, engages the kill switch and alerts
(E-03, T-10); low disk/memory pauses presence and analytics first.
