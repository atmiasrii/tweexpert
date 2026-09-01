// API client. Same-origin; CSRF header on mutations (X-02).
let csrf = "";

export function setCsrf(token: string) { csrf = token; (window as any).__csrf = token; }
export function getCsrf() { return csrf; }

async function req(method: string, path: string, body?: unknown) {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = csrf;
  const res = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    // Session expired or the signing key changed under us. Bounce to login
    // rather than spraying "unauthenticated" toasts across every panel.
    if (path !== "/api/auth/csrf" && path !== "/api/auth/login") {
      try { window.dispatchEvent(new Event("quill-unauth")); } catch {}
    }
    throw new Error("Session expired — please sign in again.");
  }
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

export const api = {
  get: (p: string) => req("GET", p),
  post: (p: string, b?: unknown) => req("POST", p, b),
  put: (p: string, b?: unknown) => req("PUT", p, b),
  patch: (p: string, b?: unknown) => req("PATCH", p, b),
  del: (p: string) => req("DELETE", p),
};

export async function login(password: string, totp = "") {
  const r = await req("POST", "/api/auth/login", { password, totp });
  setCsrf(r.csrf);
  return r;
}

export async function bootstrapCsrf() {
  try {
    const r = await req("GET", "/api/auth/csrf");
    if (r?.csrf) setCsrf(r.csrf);
    return true;
  } catch {
    return false;
  }
}

// SSE — no client polling (U-07)
export function subscribeEvents(onEvent: (name: string, data: any) => void) {
  const es = new EventSource("/api/events");
  const names = ["draft_sent", "draft_dismissed", "post_deleted", "kill_switch",
    "panic", "account_mode", "hello"];
  for (const n of names) es.addEventListener(n, (e: MessageEvent) => {
    try { onEvent(n, JSON.parse(e.data)); } catch { onEvent(n, {}); }
  });
  return () => es.close();
}
