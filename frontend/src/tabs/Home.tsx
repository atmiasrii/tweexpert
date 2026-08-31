import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export function Home({ go }: { go: (t: any) => void }) {
  const gov = useQuery({ queryKey: ["governor"], queryFn: () => api.get("/api/governor") });
  const health = useQuery({ queryKey: ["health"], queryFn: () => api.get("/api/ops/health") });
  const queue = useQuery({ queryKey: ["queue"], queryFn: () => api.get("/api/queue") });
  const g = gov.data; const h = health.data;
  return (
    <div className="space-y-4 max-w-2xl">
      <section className="border border-rule bg-[var(--surface)] p-4">
        <div className="text-sm text-muted mb-2">Safeguard meter (S-07)</div>
        {g?.usage && (
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Meter label="Auto replies" used={g.usage.replies_auto.used} cap={g.usage.replies_auto.cap} />
            <Meter label="Assisted replies" used={g.usage.replies_assisted.used} cap={g.usage.replies_assisted.cap} />
            <Meter label="Posts" used={g.usage.posts.used} cap={g.usage.posts.cap} />
            <Meter label="Threads" used={g.usage.threads.used} cap={g.usage.threads.cap} />
          </div>
        )}
        <div className="mt-3 text-sm text-muted">
          mode <b className="text-ink uppercase">{g?.mode}</b> · session {h?.session_ok ? "ok" : "down"} ·
          canary {h?.canary_ok ? "ok" : "fail"} · reads today {g?.usage?.reads ?? 0}
        </div>
      </section>
      <section className="border border-rule bg-[var(--surface)] p-4">
        <div className="flex items-center justify-between">
          <div className="text-sm">Needs attention</div>
          <button className="text-accent text-sm" onClick={() => go("Autopilot")}>
            {queue.data?.length ?? 0} in queue →
          </button>
        </div>
      </section>
    </div>
  );
}

function Meter({ label, used, cap }: { label: string; used: number; cap: number }) {
  const pct = cap ? Math.min(100, (used / cap) * 100) : 0;
  return (
    <div>
      <div className="flex justify-between text-xs text-muted"><span>{label}</span><span>{used}/{cap}</span></div>
      <div className="h-1.5 bg-rule mt-1"><div className="h-full bg-accent" style={{ width: `${pct}%` }} /></div>
    </div>
  );
}
