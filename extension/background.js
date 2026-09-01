// Quill extension service worker (A-X1). Talks ONLY to the local Quill backend
// with a per-install shared secret. The backend owns every decision (drafting,
// governor caps, authorization, audit); the content script performs the actual
// human-shaped reply in the operator's live session and reports the result.
//
// Two send paths, both in the real session:
//   1. inline — the content script replies to a tweet visible in the feed.
//   2. ready-drain — approved drafts are posted by opening each post in a hidden
//      background tab, replying, and closing it, so the operator's tab is never
//      disturbed and approvals actually go out.

const DEFAULT_API = "http://127.0.0.1:8770";
const DEFAULT_SECRET = "local-ext-secret";

async function cfg() {
  const { sharedSecret, apiBase } = await chrome.storage.local.get(["sharedSecret", "apiBase"]);
  return { secret: sharedSecret || DEFAULT_SECRET, api: apiBase || DEFAULT_API };
}
async function apiFetch(path, opts = {}) {
  const { secret, api } = await cfg();
  const headers = Object.assign({ "X-Extension-Secret": secret }, opts.headers || {});
  if (opts.body) headers["Content-Type"] = "application/json";
  const res = await fetch(api + path, { ...opts, headers });
  if (!res.ok) throw new Error("api " + res.status);
  return res.json();
}
const POST = (p, b) => apiFetch(p, { method: "POST", body: JSON.stringify(b || {}) });
const GET = (p) => apiFetch(p);

// ── messages from content scripts ──────────────────────────────
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    try {
      switch (msg.type) {
        case "report":    sendResponse(await POST("/api/ext/report", { posts: msg.posts })); break;
        case "authorize": sendResponse(await POST("/api/ext/authorize", { draft_id: msg.draft_id })); break;
        case "sent":      sendResponse(await POST("/api/ext/sent", msg.payload)); break;
        case "safeguard": sendResponse(await GET("/api/ext/safeguard")); break;
        case "kill":      sendResponse(await POST("/api/ext/kill", { on: msg.on })); break;
        case "setConfig":
          await chrome.storage.local.set({ sharedSecret: msg.secret ?? "", apiBase: msg.apiBase || DEFAULT_API });
          sendResponse({ ok: true }); break;
        case "getConfig": sendResponse(await cfg()); break;
        default: sendResponse({ error: "unknown" });
      }
    } catch (e) { sendResponse({ error: String(e.message || e) }); }
  })();
  return true;
});

// ── ready-drain: post approved drafts via hidden background tabs ───
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let draining = false;
let lastDrain = 0;

async function drainReady() {
  if (draining) return;
  draining = true;
  try {
    const { ready } = await GET("/api/ext/ready").catch(() => ({ ready: [] }));
    for (const d of ready || []) {
      // one at a time; the backend's authorize enforces spacing / caps
      const auth = await POST("/api/ext/authorize", { draft_id: d.draft_id }).catch((e) => ({ ok: false, reason: String(e) }));
      if (!auth?.ok) continue;                 // held by governor — try next cycle
      const result = await sendInTab(d.permalink, {
        draft_id: d.draft_id, text: auth.text || d.text, token: auth.token,
        authz_id: auth.authz_id, x_post_id: d.x_post_id });
      await POST("/api/ext/sent", {
        draft_id: d.draft_id, authz_id: auth.authz_id, token: auth.token,
        x_post_id: d.x_post_id, ok: !!result.ok, error: result.error || "" }).catch(() => {});
      await sleep(4000);                       // gentle gap between tabs
      break;                                   // one per drain pass; spacing does the rest
    }
  } finally {
    draining = false;
    lastDrain = Date.now();
  }
}

async function sendInTab(permalink, payload) {
  let tab;
  try {
    tab = await chrome.tabs.create({ url: permalink + "#quillsend", active: false });
    // wait for the content script to answer a ping
    for (let i = 0; i < 40; i++) {
      await sleep(500);
      const pong = await pingTab(tab.id);
      if (pong) break;
      if (i === 39) return { ok: false, error: "tab never ready" };
    }
    await sleep(1500);                         // let the tweet render
    const res = await chrome.tabs.sendMessage(tab.id, { type: "sendReply", ...payload }).catch((e) => ({ ok: false, error: String(e) }));
    return res || { ok: false, error: "no result" };
  } catch (e) {
    return { ok: false, error: String(e.message || e) };
  } finally {
    if (tab) { try { await chrome.tabs.remove(tab.id); } catch {} }
  }
}
async function pingTab(tabId) {
  try { const r = await chrome.tabs.sendMessage(tabId, { type: "ping" }); return r && r.pong; }
  catch { return false; }
}

chrome.alarms.create("quill-drain", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "quill-drain") drainReady(); });
