// Quill extension service worker (A-X1). Authenticates to the LOCAL API with a
// per-install shared secret. Never stores credentials — only the secret. All
// writes go through the action bus via the backend; the extension is a UI
// surface, not a separate write path.

const API = "http://127.0.0.1:8000";

async function getSecret() {
  const { sharedSecret } = await chrome.storage.local.get("sharedSecret");
  return sharedSecret || "";
}

async function apiFetch(path, opts = {}) {
  const secret = await getSecret();
  const headers = Object.assign({ "X-Extension-Secret": secret }, opts.headers || {});
  if (opts.body) headers["Content-Type"] = "application/json";
  const res = await fetch(API + path, { ...opts, headers });
  if (!res.ok) throw new Error("api " + res.status);
  return res.json();
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === "report") {
        sendResponse(await apiFetch("/api/ext/report", {
          method: "POST", body: JSON.stringify({ posts: msg.posts }) }));
      } else if (msg.type === "queue") {
        sendResponse(await apiFetch("/api/ext/queue?author=" + encodeURIComponent(msg.author || "")));
      } else if (msg.type === "safeguard") {
        sendResponse(await apiFetch("/api/ext/safeguard"));
      } else if (msg.type === "kill") {
        sendResponse(await apiFetch("/api/ext/kill", {
          method: "POST", body: JSON.stringify({ on: msg.on }) }));
      } else if (msg.type === "setSecret") {
        await chrome.storage.local.set({ sharedSecret: msg.secret });
        sendResponse({ ok: true });
      } else {
        sendResponse({ error: "unknown" });
      }
    } catch (e) {
      sendResponse({ error: String(e.message || e) });
    }
  })();
  return true; // async
});
