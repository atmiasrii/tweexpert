import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Header } from "./components/Header";
import { bootstrapCsrf, login, subscribeEvents } from "./lib/api";
import { Home } from "./tabs/Home";
import { Autopilot } from "./tabs/Autopilot";
import { Compose } from "./tabs/Compose";
import { Schedule } from "./tabs/Schedule";
import { Watchlist } from "./tabs/Watchlist";
import { Discover } from "./tabs/Discover";
import { Analytics } from "./tabs/Analytics";
import { Persona } from "./tabs/Persona";
import { Ops } from "./tabs/Ops";

const TABS = ["Home", "Autopilot", "Compose", "Schedule", "Watchlist",
  "Discover", "Analytics", "Persona", "Ops"] as const;
type Tab = typeof TABS[number];

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [tab, setTab] = useState<Tab>("Autopilot");
  const qc = useQueryClient();

  useEffect(() => { bootstrapCsrf().then(setAuthed); }, []);
  useEffect(() => {
    if (!authed) return;
    return subscribeEvents(() => {
      qc.invalidateQueries();  // SSE-driven refresh, no polling (U-07)
    });
  }, [authed, qc]);

  if (authed === null) return <div className="p-6 text-muted">loading…</div>;
  if (!authed) return <Login onDone={() => setAuthed(true)} />;

  return (
    <div className="min-h-full flex flex-col">
      <Header />
      <nav className="border-b border-rule bg-[var(--surface)] overflow-x-auto">
        <div className="mx-auto max-w-5xl px-2 flex gap-1 text-sm">
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-3 py-2 whitespace-nowrap border-b-2 ${
                tab === t ? "border-accent text-accent font-semibold" : "border-transparent text-muted"}`}>
              {t}
            </button>
          ))}
        </div>
      </nav>
      <main className="mx-auto max-w-5xl w-full px-3 py-4 flex-1">
        {tab === "Home" && <Home go={setTab} />}
        {tab === "Autopilot" && <Autopilot />}
        {tab === "Compose" && <Compose />}
        {tab === "Schedule" && <Schedule />}
        {tab === "Watchlist" && <Watchlist />}
        {tab === "Discover" && <Discover />}
        {tab === "Analytics" && <Analytics />}
        {tab === "Persona" && <Persona />}
        {tab === "Ops" && <Ops />}
      </main>
    </div>
  );
}

function Login({ onDone }: { onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [totp, setTotp] = useState("");
  const [err, setErr] = useState("");
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try { await login(pw, totp); onDone(); }
    catch (e: any) { setErr(String(e.message || e)); }
  };
  return (
    <div className="min-h-full grid place-items-center p-4">
      <form onSubmit={submit} className="w-full max-w-xs border border-rule bg-[var(--surface)] p-5">
        <div className="font-mono font-bold text-accent mb-3">Quill</div>
        <input type="password" placeholder="password" value={pw}
          onChange={(e) => setPw(e.target.value)}
          className="w-full mb-2 px-2 py-2 border border-rule bg-transparent" autoFocus />
        <input inputMode="numeric" placeholder="2FA code (if enrolled)" value={totp}
          onChange={(e) => setTotp(e.target.value)}
          className="w-full mb-3 px-2 py-2 border border-rule bg-transparent" />
        {err && <div className="text-risk text-xs mb-2">{err}</div>}
        <button className="w-full py-2 bg-accent text-white">Sign in</button>
      </form>
    </div>
  );
}
