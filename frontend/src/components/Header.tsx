// Header state — mode, usage, session health, kill switch — on every tab (U-05).
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";

export function Header() {
  const qc = useQueryClient();
  const gov = useQuery({ queryKey: ["governor"], queryFn: () => api.get("/api/governor"),
    refetchInterval: 15000 });
  const kill = useMutation({
    mutationFn: (on: boolean) => api.post("/api/governor/kill", { on }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["governor"] }),
  });
  const panic = useMutation({
    mutationFn: () => api.post("/api/governor/panic"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["governor"] }),
  });
  const g = gov.data;
  const u = g?.usage;
  return (
    <header className="sticky top-0 z-10 border-b border-rule bg-[var(--surface)]"
      style={{ paddingTop: "env(safe-area-inset-top)" }}>
      <div className="mx-auto max-w-5xl px-3 py-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px]">
        <span className="font-mono font-bold tracking-tight text-accent">Quill</span>
        <span className="uppercase font-semibold">{g?.mode ?? "…"}</span>
        {u && (
          <span className="text-muted font-mono">
            {u.replies_auto.used}/{u.replies_auto.cap} auto · {u.replies_assisted.used}/{u.replies_assisted.cap} assisted
          </span>
        )}
        <span className="text-muted">next {g?.next_slot ? new Date(g.next_slot).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}</span>
        <span className={g?.session_ok ? "text-go" : "text-risk"}>session {g?.session_ok ? "ok" : "down"}</span>
        <span className={g?.canary_ok ? "text-go" : "text-risk"}>canary {g?.canary_ok ? "ok" : "fail"}</span>
        {g?.quiet_now && <span className="text-muted">quiet</span>}
        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => kill.mutate(!g?.kill_switch)}
            className={`px-2 py-1 border rounded ${g?.kill_switch ? "border-risk text-risk" : "border-rule"}`}>
            {g?.kill_switch ? "Killed" : "Kill"}
          </button>
          <button onClick={() => { if (confirm("Panic: kill + delete last auto replies?")) panic.mutate(); }}
            className="px-2 py-1 border border-risk text-risk rounded">Panic</button>
        </div>
      </div>
    </header>
  );
}
