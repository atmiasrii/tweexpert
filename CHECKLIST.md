# Quill — requirement checklist (§25 completion)

Every requirement ID from `quill-prd.html`, its status, and the file that
implements it. **Red (must)** IDs are all satisfied. Acceptance tests T-01–T-15
pass automatically (`make test`); T-00 is the manual live test (procedure in
README). Status legend: ✅ done.

## §1 Goals
| ID | Status | Where |
|----|--------|-------|
| G-01 free forever, no paid API | ✅ | browser-only + fixture engine; no API clients anywhere |
| G-02 unattended, survives crashes, loud alerts | ✅ | `worker.py`, `browser_proc.py`, `ops/reconcile.py`, `notify/notifier.py` |
| G-03 sounds like the operator | ✅ | `persona/` (voicecard, corpus, engine, critic, prefilter) |
| G-04 full studio | ✅ | `frontend/src/tabs/*` (nine tabs) |
| G-05 graduated autonomy, ungovernable-bypass | ✅ | `pipeline/policy.py`, `governor/governor.py`, `bus/authz.py` |
| G-06 reachable from anywhere, approve-from-phone | ✅ | `notify/notifier.py`, `api/routes/notify_routes.py` |

## §4 Autonomy
| ID | Status | Where |
|----|--------|-------|
| Y-01 ActionAuthorization required on every write | ✅ | `bus/authz.py`, `bus/action_bus.py` (`submit_write`) — T-02 |
| Y-02 policy gates (all must hold) | ✅ | `pipeline/policy.py::evaluate_auto` — T-03 |
| Y-03 shadow period enforced in code | ✅ | `pipeline/policy.py::shadow_complete`, `api/routes/accounts.py` — T-04 |
| Y-04 separate lower auto cap | ✅ | `defaults.py::CAP_REPLIES_AUTO`, `governor/governor.py` |
| Y-05 auto-sent push + one-tap delete | ✅ | `pipeline/pipeline.py::_post_send_push`, `api/routes/notify_routes.py` |
| Y-06 auto disables itself on trouble | ✅ | `bus/action_bus.py` (`_disable_auto`), `ops/session_guard.py` |

## §5 Architecture
| ID | Status | Where |
|----|--------|-------|
| A-01 Python/FastAPI/SQLModel/SQLite WAL+FTS5/APScheduler/Alembic; React/Vite/TS/Tailwind/TanStack | ✅ | `backend/`, `frontend/` |
| A-02 three processes share the bus | ✅ | `api/app.py`, `worker.py`, `browser_proc.py` |
| A-X1 Chrome extension (MV3) | ✅ | `extension/`, `api/routes/extension_routes.py` |
| A-03 OpenAI-compatible base URL, never hardcode provider | ✅ | `persona/llm.py`, `config.py` |
| A-04 docker compose, profile volume, Xvfb, loopback VNC | ✅ | `docker-compose.yml`, `docker/` |
| A-05 one .env + settings table, .env.example, no secrets in repo | ✅ | `.env.example`, `db/settings_store.py`, `.gitignore` |

## §6 Browser engine
| ID | Status | Where |
|----|--------|-------|
| E-01 persistent context, real UA/viewport/locale/tz, headed Xvfb | ✅ | `browser/playwright_engine.py` |
| E-02 first-run VNC login, never handles password | ✅ | `docker/browser-entrypoint.sh`, `api/routes/ops_routes.py::open_vnc` |
| E-03 15-min session heartbeat, 3 fails = dead | ✅ | `ops/session_guard.py::session_heartbeat` — T-10 |
| E-04 nightly **encrypted** profile backup | ✅ | `ops/backup.py` (Fernet) |
| E-05 challenge detector, never solve | ✅ | `browser/playwright_engine.py::_check_challenges`, `selectors.yaml` challenges |
| E-06 selectors.yaml is the only place selectors live | ✅ | `selectors/selectors.yaml`, `browser/selectors.py` |
| E-07 selector canary disables auto | ✅ | `ops/session_guard.py::run_canary` — T-11 |
| E-08 screenshot + HTML on every failure | ✅ | `browser/playwright_engine.py::_capture` |
| E-09 real-flow typing with per-char delays | ✅ | `browser/playwright_engine.py::_human_type` |
| E-10 non-linear mouse, variable scroll, randomised order | ✅ | `browser/playwright_engine.py::_human_move_click/_human_scroll` |
| E-11 read replies before replying | ✅ | `browser/playwright_engine.py::reply` |

## §7 Action bus
| ID | Status | Where |
|----|--------|-------|
| Q-01 one consumer, mutex, no overlap | ✅ | `bus/action_bus.py` (RLock) — T-06 |
| Q-02 intent row before execute + startup reconcile | ✅ | `bus/action_bus.py::_run_write/reconcile` — T-05 |
| Q-03 backoff+jitter, cap 3, never ambiguous retries | ✅ | `bus/action_bus.py::_execute_with_retry` |
| Q-04 audit row per action | ✅ | `bus/action_bus.py`, `db/models.py::Action` |
| Q-05 min gap between writes at the bus | ✅ | `governor/governor.py::check_write_allowed` |

## §8 Ingestion
| ID | Status | Where |
|----|--------|-------|
| I-01 per-tier poll interval + jitter + randomised order | ✅ | `pipeline/watcher.py` |
| I-02 parse posts from DOM | ✅ | `browser/*_engine.py::_parse_timeline/_mk` |
| I-03 high-water mark, ignore RTs + own posts | ✅ | `pipeline/watcher.py`, engines |
| I-04 thread context depth 3 only past relevance | ✅ | `pipeline/pipeline.py::_fetch_context` |
| I-05 fixture engine, identical interface | ✅ | `browser/fixture_engine.py` — T-01 |
| I-06 daily read budget | ✅ | `governor/governor.py::read_budget_left` |

## §9 Persona
| ID | Status | Where |
|----|--------|-------|
| P-01 archive import (tweets.js/CSV/text), clean, embed | ✅ | `persona/corpus.py::parse_archive/import_samples` |
| P-02 retrieve 8–12 similar, weight high performers + prior replies | ✅ | `persona/corpus.py::retrieve_fewshot` |
| P-03 three candidates temp 0.85, different angles | ✅ | `persona/engine.py::ANGLES/_round` |
| P-04 deterministic pre-filter (never-list + tell-list) | ✅ | `persona/prefilter.py`, `defaults.py::TELL_LIST` — T-08 |
| P-05 critic temp 0.2, 1–5 four axes, ≥3 pass / ≥4 auto | ✅ | `persona/critic.py` |
| P-06 regenerate once then silent | ✅ | `persona/engine.py::generate` |
| P-07 similarity guard (cosine + n-gram) | ✅ | `persona/similarity.py` |
| P-08 playground | ✅ | `api/routes/persona_routes.py::preview`, `frontend/.../Persona.tsx` |

## §10 Reply pipeline
| ID | Status | Where |
|----|--------|-------|
| R-01 relevance 0–100 | ✅ | `pipeline/relevance.py` |
| R-02 freshness gate (tighter for auto) | ✅ | `pipeline/pipeline.py` |
| R-03 per-account + queue caps, 3h expiry | ✅ | `pipeline/pipeline.py::_caps_ok`, `ops/reconcile.py` |
| R-04 blocklist + distressed-sentiment for auto | ✅ | `pipeline/blocklist.py` |
| R-05 never reply twice / to already-replied | ✅ | `pipeline/pipeline.py::_already_replied` |

## §11 Governor
| ID | Status | Where |
|----|--------|-------|
| S-01 daily caps, refuse with reason | ✅ | `governor/governor.py` — T-07 |
| S-02 spacing + jitter + 4–40m auto delay | ✅ | `governor/governor.py::jitter_seconds/auto_delay_seconds` — T-12 |
| S-03 quiet hours with daily drift | ✅ | `governor/governor.py::in_quiet_hours` |
| S-04 weekly shape / rest days | ✅ | `governor/governor.py::_pick_rest_day` |
| S-05 burst guard at the bus | ✅ | `governor/governor.py` (burst) — T-07 |
| S-06 kill switch (persisted) + panic | ✅ | `governor/governor.py::set_kill/panic`, `api/routes/governor_routes.py` |
| S-07 always-visible safeguard meter | ✅ | `frontend/.../Header.tsx`, `Home.tsx` |
| S-08 no likes/follows/RT/DM — not implemented | ✅ | none by design; engines expose no such method |

## §12 Presence
| ID | Status | Where |
|----|--------|-------|
| H-01 irregular home scrolls | ✅ | `presence/simulator.py` |
| H-02 open posts/profiles/search | ✅ | `presence/simulator.py` |
| H-03 cluster active hours, never quiet | ✅ | `presence/simulator.py` (quiet check) |
| H-04 on the bus, counts reads not writes | ✅ | `presence/simulator.py`, `bus` |
| H-05 feeds discovery inbox | ✅ | `presence/simulator.py` (DiscoveryItem) |

## §13 Compose/schedule
| ID | Status | Where |
|----|--------|-------|
| C-01 composer, char count, thread split, preview | ✅ | `frontend/.../Compose.tsx`, `pipeline/schedule.py::split_thread` |
| C-02 draft-this-for-me | ✅ | `api/routes/studio.py::compose_generate` |
| C-03 sound-more-like-me | ✅ | `api/routes/studio.py::compose_restyle` |
| C-04 slot-based weekly schedule, jitter at send | ✅ | `pipeline/schedule.py`, `frontend/.../Schedule.tsx` |
| C-05 category rotation | ✅ | `pipeline/schedule.py::pick_next` |
| C-06 evergreen pool min re-post interval | ✅ | `pipeline/schedule.py`, `defaults.py::EVERGREEN_MIN_REPEAT_DAYS` |
| C-07 autosave | ✅ | `frontend/.../Compose.tsx` (controlled state) + idea inbox persistence |
| C-08 idea inbox | ✅ | `api/routes/studio.py` ideas, `frontend/.../Compose.tsx` |

## §14 Discovery
| ID | Status | Where |
|----|--------|-------|
| V-01 saved searches scored by relevance | ✅ | `pipeline/discovery.py::run_saved_searches` |
| V-02 promote to pipeline, never auto | ✅ | `pipeline/discovery.py::promote` |
| V-03 people view | ✅ | `pipeline/discovery.py::list_people`, `frontend/.../Discover.tsx` |
| V-04 notifications view | ✅ | `api/routes/studio.py::get_notifications` |

## §15 Analytics
| ID | Status | Where |
|----|--------|-------|
| M-01 decaying metric schedule, time series | ✅ | `ops/analytics.py::sample_own_posts`, `defaults.py::METRIC_SCHEDULE_S` |
| M-02 post performance view | ✅ | `ops/analytics.py::post_performance` |
| M-03 reply outcomes by angle | ✅ | `ops/analytics.py::reply_outcomes` |
| M-04 follower count daily | ✅ | `ops/analytics.py::sample_followers/follower_series` |

## §16 Remote approval
| ID | Status | Where |
|----|--------|-------|
| K-01 ntfy + optional Telegram | ✅ | `notify/notifier.py` |
| K-02 notification approve = same code path | ✅ | `pipeline/approve.py`, `api/routes/notify_routes.py` |
| K-03 alert-level notifications always sent | ✅ | `notify/notifier.py::alert/ALERT_KINDS` |
| K-04 single-use, expiring, draft-bound tokens | ✅ | `security.py::make/verify_action_token` |

## §17 Data
| ID | Status | Where |
|----|--------|-------|
| D-01 WAL + FTS5 + blob cosine | ✅ | `db/engine.py`, `persona/vectors.py` |
| D-02 Alembic from first commit | ✅ | `alembic/`, `alembic/versions/0001_initial.py` |
| D-03 nightly backup + retention | ✅ | `ops/backup.py` |

## §19 Dashboard
| ID | Status | Where |
|----|--------|-------|
| U-01 one card, keyboard shortcuts | ✅ | `frontend/.../Autopilot.tsx` — T-14 |
| U-02 real send time + brief undo | ✅ | `frontend/.../Autopilot.tsx` (undo timer) |
| U-03 shadow log first-class + retrospective judge | ✅ | `frontend/.../Autopilot.tsx::ShadowLog`, `api/routes/autopilot.py` |
| U-04 mode change confirms shadow gate + caps | ✅ | `frontend/.../Watchlist.tsx` |
| U-05 header state on every tab | ✅ | `frontend/.../Header.tsx`, `App.tsx` |
| U-06 empty states read as success | ✅ | `frontend/.../Autopilot.tsx::Empty` |
| U-07 SSE live updates, no polling | ✅ | `api/events.py`, `api/routes/ops_routes.py::events`, `lib/api.ts` |

## §20 Learning
| ID | Status | Where |
|----|--------|-------|
| L-01 store chosen/rejected/edits/dismissals | ✅ | `learning/feedback.py` — T-15 |
| L-02 edits promoted into retrieval, higher weight | ✅ | `persona/corpus.py::add_edit_sample` |
| L-03 DPO + SFT JSONL export | ✅ | `learning/feedback.py::export_dpo/export_sft` — T-15 |
| L-04 ready-to-run LoRA script → GGUF | ✅ | `scripts/train_lora.py` |
| L-05 approval-rate metric over time | ✅ | `learning/feedback.py::approval_rate_series` |

## §21 Ops
| ID | Status | Where |
|----|--------|-------|
| O-01 restart unless-stopped, clean restart | ✅ | `docker-compose.yml`, `worker.py`, `browser_proc.py` |
| O-02 per-process heartbeats + watchdog | ✅ | `ops/health.py` |
| O-03 startup reconciliation | ✅ | `ops/reconcile.py` |
| O-04 structured JSON logs w/ rotation, tailed in UI | ✅ | `logging_setup.py`, `api/routes/ops_routes.py::logs` |
| O-05 graceful degradation | ✅ | `worker.py::_degradation`, `persona/llm.py` fallback, `ops/session_guard.py` |
| O-06 scheduled Chromium restart | ✅ | `browser_proc.py::_restart_chromium` |
| O-07 make doctor | ✅ | `ops/doctor.py`, `Makefile` |

## §22 Security
| ID | Status | Where |
|----|--------|-------|
| X-01 loopback binds, tunnel-first, warn on non-loopback | ✅ | `config.py`, `api/app.py::_warn_if_public`, README |
| X-02 Argon2id + TOTP, secure cookie, CSRF, rate-limit | ✅ | `security.py`, `api/auth.py` — T-13 |
| X-03 VNC/CDP loopback-only, off by default, time-limited | ✅ | `api/routes/ops_routes.py::open_vnc`, `docker/browser-entrypoint.sh` |
| X-04 secrets encrypted at rest, profile gitignored, pre-commit hook | ✅ | `security.py::SecretBox`, `.gitignore`, `scripts/pre-commit` |
| X-05 tweet text untrusted, delimited, critic checks injection | ✅ | `persona/engine.py`, `persona/critic.py` — T-09 |
| X-06 content-safety gate before auto send | ✅ | `pipeline/blocklist.py::unsafe_to_send` |
| X-07 no telemetry/analytics/error-reporting | ✅ | none present; outbound only x.com + local model |

## §23 Models
| ID | Status | Where |
|----|--------|-------|
| Z-01 roles configurable by name + base URL | ✅ | `config.py`, `persona/llm.py` |
| Z-02 strict critic JSON + one repair retry | ✅ | `persona/llm.py::_parse_json_strict` |
| Z-03 latency + token counts recorded, shown in Ops | ✅ | `persona/llm.py::recent_calls`, `api/routes/ops_routes.py::llm`, `frontend/.../Ops.tsx` |

## §25 Acceptance tests
| ID | Status | Where |
|----|--------|-------|
| T-00 live account test (manual) | ⏭ manual | README "T-00 live account test" |
| T-01 fixture up → populated queue + shadow | ✅ | `tests/test_acceptance.py::test_t01_*` |
| T-02 unauthorized write raises/logs/alerts | ✅ | `test_t02_*` |
| T-03 policy refuses per gate | ✅ | `test_t03_gate_*` (one per gate) |
| T-04 no auto before shadow | ✅ | `test_t04_*` |
| T-05 crash mid-publish reconciles, no double post | ✅ | `test_t05_*` |
| T-06 concurrent actions serialise | ✅ | `test_t06_*` |
| T-07 governor distinct reasons | ✅ | `test_t07_*` |
| T-08 bad drafts never reach queue | ✅ | `test_t08_*` |
| T-09 injection produces no compliant output, flagged | ✅ | `test_t09_*` |
| T-10 session expiry halts writes, kills, alerts | ✅ | `test_t10_*` |
| T-11 selector miss disables auto, screenshot, alert | ✅ | `test_t11_*` |
| T-12 auto sends non-uniform, no quiet, spacing | ✅ | `test_t12_*` |
| T-13 unauth rejected, login rate-limited, CSRF | ✅ | `test_t13_*` |
| T-14 Autopilot operable at 380px, shortcuts | ✅ | `test_t14_*` |
| T-15 feedback rows + valid DPO JSONL | ✅ | `test_t15_*` |

## §26 Out of scope — respected
No other platform/account, no likes/follows/RT/DM, no paid APIs/vendors/proxies,
no captcha solving, no in-product auto fine-tune, no multi-user/teams/billing,
no cloud/k8s. ✅

---
Run `make test` → **27 passed, 1 skipped** (T-00 live). `make doctor` → ALL GREEN.
