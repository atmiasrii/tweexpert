// Quill content script — the live For-You feed + human-shaped replier.
//
// Runs in the operator's OWN Chrome on x.com, so every read and every reply
// carries the real fingerprint, cookies and human scroll events. It reads the
// feed the operator is looking at, streams it to the local backend for drafting,
// shows Quill's suggested reply inline under each tweet, and posts on one click.
// It also handles being opened in a hidden background tab to post an approved
// reply on a specific post (the ready-drain), then reports back so the worker
// can close the tab.
//
// The backend owns every decision (drafting, governor caps, authorization,
// audit); this script only performs the keystrokes in the live session.

const bg = (msg) => new Promise((res) => chrome.runtime.sendMessage(msg, res));
const SEND_MODE = location.hash.includes("quillsend");   // opened to post one reply

const seen = new Map();
const decorated = new WeakSet();
let busy = false;

// ── utils ──────────────────────────────────────────────────────
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rand = (a, b) => a + Math.random() * (b - a);
function waitFor(sel, ms) {
  return new Promise((res) => {
    const end = Date.now() + ms;
    const t = setInterval(() => {
      const el = document.querySelector(sel);
      if (el) { clearInterval(t); res(el); }
      else if (Date.now() > end) { clearInterval(t); res(null); }
    }, 120);
  });
}
function waitGone(sel, ms) {
  return new Promise((res) => {
    const end = Date.now() + ms;
    const t = setInterval(() => {
      if (!document.querySelector(sel)) { clearInterval(t); res(true); }
      else if (Date.now() > end) { clearInterval(t); res(false); }
    }, 150);
  });
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ── the reply, single clean insert ─────────────────────────────
async function postReply(art, text) {
  if (busy) return { ok: false, error: "busy" };
  busy = true;
  try {
    const replyBtn = art.querySelector('[data-testid="reply"]');
    if (!replyBtn) return { ok: false, error: "no reply button" };
    replyBtn.click();
    const box = await waitFor('[data-testid="tweetTextarea_0"], div[role="textbox"][contenteditable="true"]', 8000);
    if (!box) return { ok: false, error: "no composer" };
    box.focus();
    await sleep(rand(250, 600));
    // clear anything already in the box, then insert the whole (short) text ONCE
    document.execCommand("selectAll", false, null);
    document.execCommand("delete", false, null);
    await sleep(120);
    document.execCommand("insertText", false, text);
    await sleep(rand(500, 1000));
    // guard: composer must ~match the text — never send a stacked/degenerate blob
    const got = (box.innerText || "").replace(/\s+/g, " ").trim();
    if (got.length > text.length + 25 || got.length < Math.min(5, text.length)) {
      // clear it so nothing bad is left in the box
      box.focus(); document.execCommand("selectAll", false, null); document.execCommand("delete", false, null);
      return { ok: false, error: `insert mismatch (${got.length} vs ${text.length})` };
    }
    const sendBtn = await waitFor('[data-testid="tweetButton"]', 4000);
    if (!sendBtn) return { ok: false, error: "no send button" };
    sendBtn.click();
    const gone = await waitGone('[data-testid="tweetTextarea_0"]', 8000);
    return { ok: gone, error: gone ? "" : "composer stuck" };
  } catch (e) {
    return { ok: false, error: String(e.message || e).slice(0, 60) };
  } finally {
    busy = false;
  }
}

// ── background-tab send (ready-drain) ──────────────────────────
chrome.runtime.onMessage.addListener((msg, _s, resp) => {
  if (msg.type === "ping") { resp({ pong: true }); return true; }
  if (msg.type === "sendReply") {
    (async () => {
      const art = document.querySelector('article[data-testid="tweet"]');
      if (!art) { resp({ ok: false, error: "no tweet on page" }); return; }
      resp(await postReply(art, msg.text));
    })();
    return true;
  }
});

// In pure send mode we do nothing else — no feed scanning, no cards.
if (!SEND_MODE) initFeed();

// ── the live feed (interactive) ────────────────────────────────
function initFeed() {
  const obs = new MutationObserver(() => { clearTimeout(obs._t); obs._t = setTimeout(reportLoop, 800); });
  obs.observe(document.body, { childList: true, subtree: true });
  setInterval(reportLoop, 6000);
  reportLoop();
}

function parseArticle(art) {
  const textEl = art.querySelector('[data-testid="tweetText"]');
  const link = art.querySelector('a[href*="/status/"]');
  if (!link) return null;
  const href = link.getAttribute("href") || "";
  const m = href.match(/^\/([^/]+)\/status\/(\d+)/);
  if (!m) return null;
  return { x_post_id: m[2], author_handle: m[1], text: textEl ? textEl.innerText : "",
           url: "https://x.com" + href, kind: "post" };
}

let reporting = false;
async function reportLoop() {
  if (reporting) return;
  reporting = true;
  try {
    const arts = document.querySelectorAll('article[data-testid="tweet"]');
    const fresh = [];
    arts.forEach((art) => {
      const p = parseArticle(art);
      if (!p || !p.text) return;
      art.__quillId = p.x_post_id;
      if (!seen.has(p.x_post_id)) fresh.push(p);
    });
    if (fresh.length) {
      fresh.slice(0, 8).forEach((p) => seen.set(p.x_post_id, { pending: true }));
      const r = await bg({ type: "report", posts: fresh.slice(0, 8) });
      (r?.suggestions || []).forEach((s) =>
        seen.set(s.x_post_id, { draft_id: s.draft_id, suggestion: s.suggestion, sent: false }));
    }
    decorate();
    updateStatus();
  } catch (e) {
    updateStatus("backend offline — reload the extension");
  } finally {
    reporting = false;
  }
}

function decorate() {
  document.querySelectorAll('article[data-testid="tweet"]').forEach((art) => {
    const id = art.__quillId;
    const info = id && seen.get(id);
    if (!info || info.pending || !info.suggestion || decorated.has(art)) return;
    decorated.add(art);
    const card = document.createElement("div");
    card.className = "quill-suggest";
    card.innerHTML = `
      <div class="quill-s-head"><span class="quill-dot"></span> Quill reply <span class="quill-badge">draft</span></div>
      <div class="quill-s-text">${escapeHtml(info.suggestion)}</div>
      <div class="quill-s-actions">
        <button class="quill-btn quill-send">Reply</button>
        <button class="quill-btn quill-edit">Edit</button>
        <span class="quill-s-status"></span>
      </div>`;
    card.querySelector(".quill-send").addEventListener("click", () => doReply(art, id, card));
    card.querySelector(".quill-edit").addEventListener("click", () => {
      const t = prompt("Edit the reply:", info.suggestion);
      if (t != null) { info.suggestion = t; card.querySelector(".quill-s-text").textContent = t; }
    });
    art.appendChild(card);
  });
}

async function doReply(art, id, card) {
  const info = seen.get(id);
  if (!info || info.sent) return;
  const statusEl = card && card.querySelector(".quill-s-status");
  const btn = card && card.querySelector(".quill-send");
  const setS = (t) => { if (statusEl) statusEl.textContent = t; };
  if (btn) btn.disabled = true;
  try {
    const safe = await bg({ type: "safeguard" });
    if (safe?.kill_switch) { setS("kill switch on"); return; }
    if (safe?.quiet_now) { setS("quiet hours"); return; }
    setS("authorizing…");
    const auth = await bg({ type: "authorize", draft_id: info.draft_id });
    if (!auth?.ok) { setS(auth?.reason || "held"); return; }
    setS("replying…");
    const posted = await postReply(art, auth.text || info.suggestion);
    await bg({ type: "sent", payload: {
      draft_id: info.draft_id, authz_id: auth.authz_id, token: auth.token,
      x_post_id: "", ok: posted.ok, error: posted.error || "" } });
    if (posted.ok) { info.sent = true; setS("sent ✓"); if (card) card.classList.add("done"); }
    else setS(posted.error || "send failed");
  } catch (e) {
    setS(String(e.message || e).slice(0, 40));
  } finally {
    if (btn) btn.disabled = false;
    updateStatus();
  }
}

// ── status pill ────────────────────────────────────────────────
let pill;
function updateStatus(msg) {
  if (!pill) { pill = document.createElement("div"); pill.id = "quill-pill"; document.body.appendChild(pill); }
  const drafted = [...seen.values()].filter((v) => v.suggestion).length;
  const sent = [...seen.values()].filter((v) => v.sent).length;
  pill.textContent = msg || `Quill · ${drafted} drafted · ${sent} sent`;
}
