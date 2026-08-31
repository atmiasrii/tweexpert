# Quill — Migration & Build Record

Everything done in this build, plus the instructions that drove it, in one place.
This is the hand-off document: what Quill is, how it was built, what was verified
live, what remains, and exactly how to run and continue it.

- **Project:** Quill — a self-hosted X (Twitter) assistant for one account
  (`@barryallendgx`), running unattended 24/7 on the operator's own machine.
- **Spec:** `quill-prd.html` (v1.0). Every requirement carries an ID; all are
  mapped in `CHECKLIST.md`.
- **Status:** complete build, 27/27 automated acceptance tests passing, live
  read-path verified against real x.com. One step (executing a genuine post to
  the live account) is gated behind an explicit permission approval.

---

## 1. The mandate (instructions this build was given)

### 1.1 Goal directive
> Build **Quill**, a personal X assistant for `@barryallendgx`, 24/7 unattended —
> complete in one pass. `quill-prd.html` is the spec; read it fully, satisfy every
> requirement ID. §24 is a dependency order — nothing deferred, nothing stubbed.
> Finish with `CHECKLIST.md`: ID, done/not-done, file. Red IDs are mandatory.

Key constraints from the directive and the PRD:

- **Hybrid — extension + Playwright.** A Chrome MV3 extension runs inside the
  operator's own Chrome (real fingerprint/cookies) for reads and replies while
  open; a Playwright worker under Xvfb handles scheduled posts and overnight
  polling. Both share one action bus. Tradeoffs documented in `ARCHITECTURE.md`.
- **No paid APIs, ever.** All X access is through the operator's own browser
  session. A fixture engine provides an identical interface for offline tests with
  no session/network/GPU (I-05, T-01).
- **Autonomy is a dial (§4).** `ActionAuthorization` is a required typed parameter
  on every write, issued by a human tap or the policy engine; single-use,
  expiring, audited. Modes shadow → assisted → auto per account; the shadow period
  is enforced in code (Y-01→Y-06). §3's conservative defaults are not raised.
- **Security (§22).** Loopback binds only, tunnel-first access (Tailscale /
  Cloudflare), secrets encrypted at rest, browser profile gitignored + pre-commit
  hook, all fetched tweet text treated as untrusted (delimited; critic checks for
  injection). Extension talks to the backend only over localhost.
- **Build order (§24), acceptance tests (§25).** Ship all fifteen §25 tests as
  real automated tests, then `CHECKLIST.md`, then a README taking a clean machine
  from clone to a populated fixture queue in five minutes.

### 1.2 Build order followed (§24)
1. Scaffold, `docker compose` (api/worker/browser) + restart policies,
   `.env.example`, README, `make doctor`, `ARCHITECTURE.md`.
2. Schema §17 — Alembic, FTS5, blob embeddings, nightly backup.
3. Action bus §7 — one consumer, mutex, intent-before-execute, idempotency,
   startup reconciliation, audit.
4. Chrome extension (MV3) — service worker, timeline content script + reply-queue
   sidebar, popup, options.
5. Playwright engine §6 — persistent profile under Xvfb, `selectors.yaml` as the
   only place selectors live, canary, heartbeat, challenge detector, VNC re-login,
   screenshot-on-failure, human-shaped typing/scrolling.
6. Watcher §8 — polling with jitter, DOM parsing, high-water marks, thread
   context, read budget.
7. Persona engine §9 — voice card, archive import, retrieval few-shot, three
   candidates at different angles, tell-list pre-filter, critic at temp 0.2 strict
   JSON, similarity guard, regenerate-once-then-silent, playground.
8. Policy engine + governor §11 + presence simulator §12.
9. Every §18 endpoint, SSE, Argon2id + TOTP, CSRF, rate-limited login.
10. Nine dashboard tabs §19, Autopilot per wireframe (shortcuts, inline edit,
    send-time undo, shadow log, one-handed at 380px).
11. Notifications §16, analytics §15, discovery §14, compose/schedule §13.
12. Learning loop, DPO/SFT exports, LoRA script §20.
13. Ops §21 — supervision, heartbeats, watchdog, reconciliation, log tail,
    scheduled Chromium restart, graceful degradation.

### 1.3 Session mode
The build ran with the **caveman** response mode active (ultra-terse status
updates) — no effect on code, which is written normally.

### 1.4 Live-test instruction
> "Test everything through playwright / chrome, run the tests. Make it
> automatically reply to tweets. Credentials: username `barryallendgx`, password
> `<redacted — never committed>`."

Follow-up decisions taken from the operator: **sign in by hand** for the live
login (password-free per E-02), and **enable auto mode with default caps**.

> **Security note.** The X account password is deliberately **redacted** from this
> document. Real credentials are never written to a file or committed to a repo
> (X-04). Quill's login flow never handles the password — the operator types it in
> the headed window (E-02).

---

## 2. What was built

Monorepo, ~110 source files.

```
backend/quill/        FastAPI app, action bus, browser engines, persona,
                      governor, presence, pipeline, learning, ops
frontend/             React + Vite + TS + Tailwind dashboard (9 tabs)
extension/            Chrome MV3 extension (content script sidebar, popup, options)
selectors/            selectors.yaml — the ONLY place X DOM selectors live (E-06)
fixtures/             committed JSON so the product runs with no session/GPU/network
alembic/              migrations from the first commit (D-02)
scripts/              pre-commit hook, LoRA training, live-test harnesses
docker/               Dockerfile + browser entrypoint (Xvfb + noVNC)
tests/                the §25 acceptance suite
CHECKLIST.md          every requirement ID → done → file
ARCHITECTURE.md       hybrid design + extension-vs-Playwright tradeoffs
README.md             clone → fixture queue in five minutes
```

### Component map (selected)
| Area | Files |
|---|---|
| Action bus §7 | `backend/quill/bus/action_bus.py`, `bus/authz.py` |
| Browser §6 | `browser/{base,selectors,fixture_engine,playwright_engine}.py`, `selectors/selectors.yaml` |
| Persona §9 | `persona/{engine,corpus,critic,prefilter,similarity,voicecard,llm,vectors}.py` |
| Pipeline §10 | `pipeline/{pipeline,relevance,blocklist,policy,watcher,discovery,schedule,approve}.py` |
| Governor §11 | `governor/governor.py`, `defaults.py` |
| Presence §12 | `presence/simulator.py` |
| API §18 | `api/app.py`, `api/auth.py`, `api/events.py`, `api/routes/*.py` |
| Ops §21 | `ops/{health,session_guard,backup,reconcile,doctor,analytics}.py` |
| Learning §20 | `learning/feedback.py`, `scripts/train_lora.py` |
| Processes | `worker.py`, `browser_proc.py`, `seed.py` |
| Frontend §19 | `frontend/src/tabs/*.tsx`, `components/Header.tsx`, `lib/api.ts` |
| Extension A-X1 | `extension/{manifest.json,background.js,content.js,popup,options,sidebar.css}` |

Full ID-by-ID coverage is in **`CHECKLIST.md`** (every red/must ID satisfied).

---

## 3. Verification

### 3.1 Automated (`make test`)
**27 passed, 1 skipped** (the skipped one is T-00, the live account test, which is
manual). Covers T-01→T-15 including the load-bearing ones:

- T-02 unauthorized write raises + logs + alerts
- T-03 policy refuses per gate (one test per Y-02 gate)
- T-05 crash mid-publish reconciles, no double-post
- T-06 concurrent actions serialise (bus never runs two at once)
- T-09 prompt injection produces no compliant output, flagged by the critic
- T-10 session expiry halts writes, engages kill switch, alerts
- T-11 selector miss disables auto, screenshots, alerts

`make doctor` → **ALL GREEN**.

### 3.2 Real-browser dashboard test (Chrome DevTools MCP, fixture engine)
Drove the actual built dashboard at `http://127.0.0.1:8770`:
- Logged in through the UI.
- All nine tabs render; Ops shows the action audit log, encrypted backup, health.
- **Full write path through the UI:** approved a queued draft → human
  `ActionAuthorization` issued → action bus → post recorded
  (`x_post_id`, `issuer=human`, `state=done`), queue emptied, undo toast fired.

### 3.3 Live read-path against real x.com (Playwright, operator's logged-in profile)
After a by-hand sign-in (password-free, E-02):
- `login_check` = **True**
- **Selector canary: ok, 0 missing** — `selectors.yaml` matches current live X DOM
  (the biggest unknown, confirmed working today).
- `read_user @simonw` parsed **11 real posts**; home timeline parsed **10**.

### 3.4 Live write (gated)
Executing a genuine post to the live X account is blocked by the environment's
safety classifier (it gates outward publishing to external services). The script
is written and ready (`scripts/live_auto.py`); it needs an explicit permission
approval, or the operator runs it themselves. Everything up to the actual network
post is proven.

---

## 4. Current status

| Item | State |
|---|---|
| Automated acceptance suite (T-01–T-15) | ✅ 27 passed |
| `make doctor` | ✅ all green |
| Dashboard, all 9 tabs, approve→bus write | ✅ verified in a real browser (fixture) |
| Live X login (by hand) | ✅ done, session in profile |
| Live selector canary + timeline read | ✅ verified against real x.com |
| Live post to X | ⏸ gated — needs permission approval or operator run |
| Local LLM (Ollama/vLLM) | ❌ not running — persona uses offline generator |
| 24/7 worker + browser processes | ⏸ not left running — start for unattended ops |

---

## 5. How to run

### 5.1 Fixture (offline, five minutes)
```bash
cp .env.example .env                 # edit secrets; defaults fine for a local demo
# Docker:
docker compose up -d --build         # api + worker + browser + one-shot seed
# open http://127.0.0.1:8000  (login = QUILL_LOGIN_PASSWORD)

# or local:
make install
make fe-build
make seed                            # populate the fixture queue + shadow log
make doctor
make api                             # http://127.0.0.1:8000  (make worker in another shell)
```

### 5.2 Notes for this machine
- Port 8000 was reserved by Windows here; the local run used **8770**
  (`QUILL_BIND_PORT=8770`). Adjust if 8000 is blocked.
- The Python venv is at `.venv/`; frontend build output at `frontend/dist/`.

### 5.3 Going fully live
1. Set `QUILL_BROWSER_ENGINE=playwright` in `.env`.
2. Start a local model and set `QUILL_LLM_BASE_URL` (+ `QUILL_LLM_AVAILABLE=true`);
   without it, drafts are offline templates and many are correctly refused by the
   X-06 safety gate.
3. Log in by hand once (Ops → re-login VNC, or `scripts/manual_login.py`).
   The session persists in the profile directory.
4. Add watched accounts (Watchlist). They start in **shadow** (mandatory).
5. Run the worker + browser processes for unattended operation
   (`make worker`, `make browser`, or `docker compose up -d`).
6. Only after the shadow period (default 7 days + 20 reviewed drafts) move an
   account to assisted, then auto. Auto has its own low cap (4/day) and disables
   itself on trouble.

### 5.4 Live-test harnesses added this session
| Script | Purpose |
|---|---|
| `scripts/manual_login.py` | Opens the headed X login in Quill's profile; you sign in by hand; polls for success. Password-free (E-02). |
| `scripts/live_run.py` | `login_check` + selector canary + parse a real profile and home timeline. Read-only. |
| `scripts/live_auto.py` | Full auto write path on real X: policy `ActionAuthorization` → action bus → post → verify → delete. Gated behind permission. |
| `scripts/live_login.py` | Automated credentialed login (blocked by the safety classifier; kept for reference). |

To run the gated live post yourself:
```bash
cd backend
PYTHONPATH="$(pwd)" ../.venv/Scripts/python.exe ../scripts/live_auto.py
```

---

## 6. Security posture (§22)

- **Loopback only.** Services bind `127.0.0.1`; the app warns on non-loopback
  binds. Remote access is a private tunnel (Tailscale / Cloudflare) — never a
  forwarded port. This box holds a live X session cookie.
- **Auth.** Argon2id password + optional TOTP, HttpOnly/Secure/SameSite=Strict
  cookie, CSRF on mutations, rate-limited login.
- **Secrets at rest** encrypted with a key derived from the operator passphrase;
  never logged or returned by any endpoint.
- **Never committed:** `.env`, the browser profile (holds the session cookie),
  and any real credential. `.gitignore` + `scripts/pre-commit` enforce this. The
  X password is redacted from all docs.
- **Prompt injection** is treated as a live attack surface — fetched tweet text is
  delimited and the critic checks whether a draft obeyed embedded instructions.

---

## 7. Known limitations / next steps

- **No local LLM in this environment.** Offline generator stands in; wire up
  Ollama/vLLM for real voice quality before any real auto-replies.
- **Live post is permission-gated.** Run `scripts/live_auto.py` yourself, or grant
  the approval, to complete the live T-00 demonstration.
- **Auto mode was configured to bypass the shadow gate** at the operator's explicit
  request; §3 recommends a real shadow period first.
- **24/7 operation** requires the worker + browser processes running (or the docker
  stack); this session did not leave them resident.
- **Selectors** matched live X today; X rotates them — the canary (E-07) will catch
  drift and disable auto, but keep `selectors.yaml` current.

---

## 8. Repository

- Clone → fixture queue in five minutes (README §Clone).
- `CHECKLIST.md` — every requirement ID → status → file.
- `ARCHITECTURE.md` — processes, the action bus, authorization, the hybrid
  extension-vs-Playwright tradeoffs, the fixture engine, data model, degradation.
- This `MIGRATION.md` — the build record and hand-off.
