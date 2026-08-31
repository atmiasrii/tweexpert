// Content script (A-X1). Reads the timeline DOM directly, reports new posts to
// the backend, and injects a sidebar showing the pending draft queue for the
// current page's author. It carries the operator's real fingerprint, cookies
// and human scroll events between automated actions (safer automation path).

// NOTE: DOM selectors here mirror selectors.yaml. The backend canary owns the
// authoritative registry; the extension uses resilient data-testid lookups.

function parseTweets() {
  const out = [];
  const articles = document.querySelectorAll('article[data-testid="tweet"]');
  articles.forEach((art) => {
    const textEl = art.querySelector('[data-testid="tweetText"]');
    const linkEl = art.querySelector('a[href*="/status/"]');
    if (!textEl || !linkEl) return;
    const href = linkEl.getAttribute("href") || "";
    const m = href.match(/\/([^/]+)\/status\/(\d+)/);
    if (!m) return;
    out.push({
      x_post_id: m[2],
      author_handle: m[1],
      text: textEl.innerText,
      url: "https://x.com" + href,
      kind: "post",
    });
  });
  return out;
}

function currentAuthor() {
  const m = location.pathname.match(/^\/([A-Za-z0-9_]+)(\/|$)/);
  const reserved = ["home", "search", "notifications", "messages", "explore", "i", "compose"];
  if (m && !reserved.includes(m[1])) return m[1];
  return "";
}

let lastReport = 0;
async function reportAndRefresh() {
  const now = Date.now();
  if (now - lastReport < 8000) return; // throttle
  lastReport = now;
  const posts = parseTweets().slice(0, 20);
  if (posts.length) {
    try { await chrome.runtime.sendMessage({ type: "report", posts }); } catch {}
  }
  refreshSidebar();
}

async function refreshSidebar() {
  try {
    const author = currentAuthor();
    const queue = await chrome.runtime.sendMessage({ type: "queue", author });
    renderSidebar(Array.isArray(queue) ? queue : []);
  } catch {}
}

function renderSidebar(items) {
  let el = document.getElementById("quill-sidebar");
  if (!el) {
    el = document.createElement("div");
    el.id = "quill-sidebar";
    document.body.appendChild(el);
  }
  el.innerHTML = `
    <div class="quill-head">Quill · queue (${items.length})</div>
    ${items.map((d) => `
      <div class="quill-card">
        <div class="quill-meta">@${d.author ?? ""} · rel ${d.relevance ?? ""}</div>
        <div class="quill-text">${escapeHtml(d.final_text || "")}</div>
        <button class="quill-approve" data-id="${d.id}">Approve →</button>
      </div>`).join("") || '<div class="quill-empty">nothing to send. all clear.</div>'}
    <div class="quill-foot">approve opens the dashboard (auth + CSRF)</div>`;
  el.querySelectorAll(".quill-approve").forEach((b) => {
    b.addEventListener("click", () => {
      // The extension never writes directly; it hands off to the authenticated
      // dashboard which issues the ActionAuthorization and posts via the bus.
      window.open("http://127.0.0.1:8000/#autopilot", "_blank");
    });
  });
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;",
    '"': "&quot;", "'": "&#39;" }[c]));
}

const observer = new MutationObserver(() => reportAndRefresh());
observer.observe(document.body, { childList: true, subtree: true });
setInterval(reportAndRefresh, 15000);
reportAndRefresh();
