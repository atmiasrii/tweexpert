# Quill

A self-hosted X assistant for **one** account (`@barryallendgx`), running unattended
24/7 on the operator's own machine. It drives a real logged-in browser (no paid
API, ever), writes in the operator's voice with a local model, and — once it has
earned the right to — can reply on its own under a governor that cannot be bypassed.

> **Platform reality (§3).** X's rules prohibit non-API automation; this project
> does exactly that. The risk is accepted, not mitigated away. The safeguards in
> §4/§11/§12 exist to keep it *survivable*, not compliant. Don't raise the caps.

---

## Clone → populated fixture queue in five minutes

Quill runs fully offline against committed fixtures — **no X session, no GPU, no
network** (I-05, T-01). Two ways:

### A. Docker (one command)

```bash
cp .env.example .env            # edit the secrets; defaults work for a local demo
docker compose up -d --build    # api + worker + browser + one-shot seed
# open http://127.0.0.1:8000  (login password = QUILL_LOGIN_PASSWORD from .env)
```

`docker compose up` seeds the fixture watchlist and runs one pipeline pass, so the
dashboard opens with a **populated Autopilot queue and shadow log** (T-01).

### B. Local (no Docker)

```bash
make install        # venv + backend deps + frontend deps
make fe-build       # build the dashboard into frontend/dist
make seed           # create schema + populate the fixture queue/shadow log
make doctor         # verify deps, GPU, model endpoint, session, selectors, db (O-07)
make api            # http://127.0.0.1:8000   (in another shell: make worker)
```

Login with `QUILL_LOGIN_PASSWORD` (default `quill-dev-password`). Enroll TOTP from
the… actually from `POST /api/auth/totp/enroll` once logged in (X-02).

---

## Security — read before exposing anything (§22)

- **Loopback only.** Every service binds to `127.0.0.1` (X-01). The app warns if it
  detects a non-loopback bind.
- **Never forward a port.** The documented and only supported remote-access path is
  a private tunnel — **Tailscale** or **Cloudflare Tunnel** — in front of the
  loopback port. This box holds a live X session cookie; a forwarded port is a
  compromised account.
  ```bash
  # Tailscale example
  tailscale up
  tailscale serve https / http://127.0.0.1:8000
  # Cloudflare example
  cloudflared tunnel --url http://127.0.0.1:8000
  ```
- **Auth.** Argon2id password + optional TOTP, HttpOnly/Secure/SameSite=Strict
  session cookie, CSRF on every mutation, rate-limited login with lockout (X-02).
- **Secrets at rest.** Encrypted with a key derived from `QUILL_OPERATOR_PASSPHRASE`
  supplied at startup; never logged, never returned by any endpoint (X-04).
- **The browser profile is gitignored** and a pre-commit hook blocks it and `.env`
  (X-04). Install the hook:
  ```bash
  cp scripts/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
  ```
- **Prompt injection is a live attack surface.** All fetched tweet text is wrapped
  in delimiters and treated as data; the critic explicitly checks whether a draft
  obeyed instructions embedded in the source post (X-05, X-06, T-09).

---

## Going live (real X session)

1. Set `QUILL_BROWSER_ENGINE=playwright` in `.env` and `docker compose up -d`.
2. Open the **Ops** tab → **re-login (VNC)**, or browse the loopback noVNC surface
   (`http://127.0.0.1:6080/vnc.html`, reachable only through your tunnel, X-03).
   Log in to X **by hand**, including 2FA. Quill never handles the password (E-02).
3. Add accounts on **Watchlist**. New accounts start in **shadow** (mandatory).
   After the shadow period (default 7 days + 20 reviewed drafts, Y-03) you can move
   an account to **assisted**, then **auto**. Auto has its own low cap (4/day, Y-04)
   and disables itself on trouble (Y-06).

### Chrome extension (hybrid path)

Load `extension/` as an unpacked MV3 extension in the Chrome where `@barryallendgx`
is already logged in. Open its **Options**, paste `QUILL_EXTENSION_SHARED_SECRET`.
The content script reads the timeline and injects a reply-queue sidebar; the popup
shows the safeguard meter and kill switch. The extension talks **only** to
`http://127.0.0.1:8000` and is a UI surface — every write still goes through the
action bus via the authenticated dashboard (A-X1). See `ARCHITECTURE.md` for the
extension-vs-Playwright tradeoffs.

---

## Models (§23)

Three roles, independently configurable by name + base URL (OpenAI-compatible, so
Ollama or vLLM both work — never hardcode a provider, A-03/Z-01):

| Role   | Default            | Notes |
|--------|--------------------|-------|
| Draft  | `qwen3:30b-a3b`    | temp 0.85; where the LoRA lands later |
| Critic | `qwen3:32b`        | temp 0.2, strict JSON |
| Embed  | `nomic-embed-text` | retrieval + similarity guard |

Set `QUILL_LLM_AVAILABLE=true` once an endpoint is reachable. With no model, Quill
uses a deterministic offline generator so the whole pipeline still runs (fixtures).

---

## Learning & fine-tuning (§20)

Every approval/edit/dismissal is a training signal. Export and train when the
Persona tab says there's enough:

```bash
curl -s http://127.0.0.1:8000/api/learning/export/dpo > dpo.jsonl
curl -s http://127.0.0.1:8000/api/learning/export/sft > sft.jsonl
python scripts/train_lora.py --data sft.jsonl --base <hf-model> --out ./quill-lora
```

---

## Tests (§25)

```bash
make test        # 15 acceptance tests (T-00 live test is skipped by default)
```

### T-00 live account test (manual)

`@barryallendgx` is already logged into Chrome on this machine. After the fixture
tests pass:

1. `QUILL_BROWSER_ENGINE=playwright`, log in via the VNC surface.
2. Load the extension; confirm the sidebar shows a draft for a watched author.
3. Approve one **assisted** draft whose text is a clearly-labelled test string.
4. Verify it posted, then delete it immediately:
   `DELETE /api/posts/{id}` (or the one-tap delete in the after-the-fact push).

---

## Layout

```
backend/quill/    FastAPI app, action bus, browser engine, persona, governor, ops
frontend/         React + Vite + TS + Tailwind dashboard (9 tabs)
extension/        Chrome MV3 extension (reads timeline, reply-queue sidebar, popup)
selectors/        selectors.yaml — the ONLY place X DOM selectors live (E-06)
fixtures/         committed JSON so the product runs with no session/GPU/network
alembic/          migrations from the first commit (D-02)
scripts/          pre-commit hook, LoRA training script
docker/           Dockerfile + browser entrypoint (Xvfb + noVNC)
CHECKLIST.md      every requirement ID → done/not-done → file
ARCHITECTURE.md   hybrid design + tradeoffs
```

Only cost is electricity (G-01). No telemetry, no third-party analytics, outbound
traffic to x.com and the local model only (X-07).
