import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Sidebar } from "./components/Sidebar";
import { StatusBar } from "./components/StatusBar";
import { CommandPalette } from "./components/CommandPalette";
import { ShortcutHelp } from "./components/ShortcutHelp";
import { useToast } from "./components/Toast";
import { Button, Card, Field, Input, cx } from "./components/ui";
import { IconKeyboard } from "./components/Icons";
import { api, bootstrapCsrf, login, subscribeEvents } from "./lib/api";
import { TABS, TabId } from "./lib/nav";
import { Home } from "./tabs/Home";
import { Autopilot } from "./tabs/Autopilot";
import { Deck } from "./tabs/Deck";
import { Compose } from "./tabs/Compose";
import { Schedule } from "./tabs/Schedule";
import { Watchlist } from "./tabs/Watchlist";
import { Discover } from "./tabs/Discover";
import { Analytics } from "./tabs/Analytics";
import { Persona } from "./tabs/Persona";
import { Ops } from "./tabs/Ops";

const TAB_KEY = "quill.tab";

function readTab(): TabId {
  try {
    const v = localStorage.getItem(TAB_KEY) as TabId | null;
    if (v && TABS.some((t) => t.id === v)) return v;
  } catch {}
  // Nothing is set up on a first run, so an empty review queue would be a
  // confusing place to land. Overview holds the start control.
  return "Home";
}

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  useEffect(() => { bootstrapCsrf().then(setAuthed); }, []);

  // A 401 anywhere means the session lapsed — drop to the login screen instead
  // of leaving broken panels behind.
  useEffect(() => {
    const onUnauth = () => setAuthed(false);
    window.addEventListener("quill-unauth", onUnauth);
    return () => window.removeEventListener("quill-unauth", onUnauth);
  }, []);

  if (authed === null) return <Booting />;
  if (!authed) return <Login onDone={() => setAuthed(true)} />;
  return <Shell />;
}

function Booting() {
  return (
    <div className="min-h-full grid place-items-center">
      <div className="flex flex-col items-center gap-3 anim-fade">
        <div className="h-8 w-8 rounded-sm bg-[color:var(--accent)] opacity-90" />
        <span className="text-[13px] text-muted">Starting Quill…</span>
      </div>
    </div>
  );
}

function Shell() {
  const [tab, setTabRaw] = useState<TabId>(readTab);
  const [menuOpen, setMenuOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const qc = useQueryClient();
  const { toast } = useToast();
  const mainRef = useRef<HTMLElement>(null);

  const setTab = useCallback((t: TabId) => {
    setTabRaw(t);
    try { localStorage.setItem(TAB_KEY, t); } catch {}
    mainRef.current?.scrollTo({ top: 0 });
  }, []);

  // Server-sent events drive every refresh; the client never polls (U-07).
  useEffect(() => {
    return subscribeEvents((name) => {
      qc.invalidateQueries();
      if (name === "kill_switch" || name === "panic") {
        qc.invalidateQueries({ queryKey: ["governor"] });
      }
    });
  }, [qc, toast]);

  const gov = useQuery({ queryKey: ["governor"], queryFn: () => api.get("/api/governor") });
  const queue = useQuery({ queryKey: ["queue"], queryFn: () => api.get("/api/queue") });
  const queueCount = Array.isArray(queue.data) ? queue.data.length : 0;

  // Global keys. A "g" prefix jumps between tabs; the tabs keep their own keys.
  const pending = useRef<{ g: boolean; timer: number } | null>(null);
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement | null;
      const typing =
        !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);

      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setPaletteOpen((v) => !v);
        return;
      }
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === "?") { e.preventDefault(); setHelpOpen(true); return; }

      if (pending.current?.g) {
        window.clearTimeout(pending.current.timer);
        pending.current = null;
        const hit = TABS.find((t) => t.key === e.key.toLowerCase());
        if (hit) { e.preventDefault(); setTab(hit.id); }
        return;
      }
      if (e.key === "g") {
        // Wait briefly for the second key, then forget it.
        const timer = window.setTimeout(() => { pending.current = null; }, 1200);
        pending.current = { g: true, timer };
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setTab]);

  const anyOverlay = paletteOpen || helpOpen;

  return (
    <div className="min-h-full flex">
      <Sidebar
        tab={tab}
        onPick={setTab}
        queueCount={queueCount}
        mobileOpen={menuOpen}
        onCloseMobile={() => setMenuOpen(false)}
      />

      <div className="flex-1 min-w-0 flex flex-col">
        <StatusBar
          tab={tab}
          onOpenMenu={() => setMenuOpen(true)}
          onOpenPalette={() => setPaletteOpen(true)}
          onGo={setTab}
        />

        <main
          ref={mainRef}
          className="flex-1 w-full max-w-content mx-auto px-3 sm:px-5 py-5 sm:py-6"
          // The overlay owns the keyboard while it is open.
          aria-hidden={anyOverlay || undefined}
        >
          <div key={tab} className="anim-fade">
            {tab === "Home" && <Home go={setTab} />}
            {tab === "Autopilot" && <Autopilot suspendKeys={anyOverlay} go={setTab} />}
            {tab === "Deck" && <Deck />}
            {tab === "Compose" && <Compose />}
            {tab === "Schedule" && <Schedule />}
            {tab === "Watchlist" && <Watchlist />}
            {tab === "Discover" && <Discover />}
            {tab === "Analytics" && <Analytics />}
            {tab === "Persona" && <Persona />}
            {tab === "Ops" && <Ops />}
          </div>
        </main>

        <footer className="px-3 sm:px-5 py-3 border-t border-rule text-[12px] text-faint flex items-center gap-3">
          <span>Quill · loopback only</span>
          <button
            onClick={() => setHelpOpen(true)}
            className="ml-auto inline-flex items-center gap-1.5 hover:text-ink transition-colors"
          >
            <IconKeyboard size={14} />
            Shortcuts
            <span className="kbd">?</span>
          </button>
        </footer>
      </div>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onGo={setTab}
        killOn={!!gov.data?.kill_switch}
      />
      <ShortcutHelp open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

function Login({ onDone }: { onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [totp, setTotp] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try { await login(pw, totp); onDone(); }
    catch (e: any) {
      const raw = String(e?.message ?? e);
      let msg = raw;
      try { const p = JSON.parse(raw); if (p?.detail) msg = p.detail; } catch {}
      setErr(msg);
    } finally { setBusy(false); }
  }

  return (
    <div className="min-h-full grid place-items-center p-4">
      <div className="w-full max-w-[340px] anim-rise">
        <div className="flex items-center gap-2.5 mb-5">
          <span className="grid place-items-center h-9 w-9 rounded-md bg-[color:var(--accent)] text-[color:var(--accent-ink)]">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M4 20l3.2-8.5L15.5 3.2a2.2 2.2 0 0 1 3.2 3L10.3 14.7 4 20Z"
                stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
              <path d="M10.3 14.7 7.2 11.5M12 12l-2.6 6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          </span>
          <div>
            <div className="text-[17px] font-semibold tracking-tight leading-none">Quill</div>
            <div className="text-[12px] text-faint mt-1">Self-hosted · loopback only</div>
          </div>
        </div>

        <Card className="space-y-3">
          <form onSubmit={submit} className="space-y-3">
            <Field label="Password">
              <Input type="password" value={pw} onChange={(e) => setPw(e.target.value)}
                autoFocus autoComplete="current-password" placeholder="••••••••" />
            </Field>
            <Field label="Two-factor code" hint="Leave blank if you have not enrolled TOTP.">
              <Input inputMode="numeric" value={totp} onChange={(e) => setTotp(e.target.value)}
                placeholder="123456" autoComplete="one-time-code" />
            </Field>
            {err && (
              <div className={cx(
                "text-[12.5px] rounded-sm px-2.5 py-2",
                "bg-[color:var(--risk-soft)] text-risk border border-[color:var(--risk)]"
              )} role="alert">
                {err}
              </div>
            )}
            <Button type="submit" variant="primary" size="lg" loading={busy} className="w-full">
              Sign in
            </Button>
          </form>
        </Card>

        <p className="text-[11.5px] text-faint mt-3 leading-relaxed">
          This machine holds a live X session. Reach Quill through a private tunnel —
          never a forwarded port.
        </p>
      </div>
    </div>
  );
}
