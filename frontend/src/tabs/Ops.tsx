import { useQuery, useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

export function Ops() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api.get("/api/ops/health") });
  const actions = useQuery({ queryKey: ["actions"], queryFn: () => api.get("/api/ops/actions?limit=50") });
  const backups = useQuery({ queryKey: ["backups"], queryFn: () => api.get("/api/ops/backups") });
  const llm = useQuery({ queryKey: ["llm"], queryFn: () => api.get("/api/ops/llm"), refetchInterval: 10000 });
  const [logs, setLogs] = useState<string[]>([]);
  const relogin = useMutation({ mutationFn: () => api.post("/api/ops/login"),
    onSuccess: (d: any) => window.open(d.vnc_url, "_blank") });

  useEffect(() => {
    const es = new EventSource("/api/ops/logs");
    es.addEventListener("log", (e: MessageEvent) => {
      try { const d = JSON.parse(e.data); if (d.line) setLogs((l) => [...l.slice(-200), d.line]); } catch {}
    });
    return () => es.close();
  }, []);

  const h = health.data;
  return (
    <div className="max-w-4xl space-y-4">
      <section className="flex flex-wrap gap-4 text-sm">
        <span>engine <b>{h?.engine}</b></span>
        <span className={h?.session_ok ? "text-go" : "text-risk"}>session {h?.session_ok ? "ok" : "down"}</span>
        <span className={h?.canary_ok ? "text-go" : "text-risk"}>canary {h?.canary_ok ? "ok" : "fail"}</span>
        <span>queue {h?.queue}</span>
        <button onClick={() => relogin.mutate()} className="px-3 py-1 border border-rule">re-login (VNC)</button>
      </section>
      <section>
        <div className="text-sm text-muted mb-2">Action audit log (Q-04)</div>
        <div className="max-h-64 overflow-auto border border-rule">
          <table className="w-full text-xs font-mono">
            <tbody>
              {(actions.data ?? []).map((a: any) => (
                <tr key={a.id} className="border-b border-rule">
                  <td className="px-2 py-1">{a.kind}</td><td>{a.issuer}</td>
                  <td className={a.outcome === "done" ? "text-go" : a.outcome ? "text-risk" : ""}>{a.state}/{a.outcome}</td>
                  <td className="max-w-xs truncate">{a.x_post_id || a.error}</td>
                  <td>{a.screenshot_path ? "📷" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <div className="text-sm text-muted mb-2">Live logs (O-04)</div>
        <pre className="max-h-56 overflow-auto border border-rule p-2 text-[11px] font-mono bg-[var(--surface)]">
          {logs.join("\n") || "…"}
        </pre>
      </section>
      <section>
        <div className="text-sm text-muted mb-2">Model calls · latency + tokens (Z-03)</div>
        <ul className="text-xs font-mono max-h-32 overflow-auto">
          {(llm.data ?? []).slice(-8).reverse().map((c: any, i: number) => (
            <li key={i} className={c.offline ? "text-muted" : ""}>
              {c.role} · {c.model} · {c.latency_ms}ms · {c.prompt_tokens}+{c.completion_tokens} tok
              {c.offline ? " · offline" : ""}
            </li>
          ))}
          {(llm.data ?? []).length === 0 && <li className="text-muted">no calls yet</li>}
        </ul>
      </section>
      <section>
        <div className="text-sm text-muted mb-2">Backups (D-03)</div>
        <ul className="text-xs font-mono">
          {(backups.data ?? []).map((b: any) => <li key={b.name}>{b.name} · {Math.round(b.size / 1024)}KB</li>)}
        </ul>
      </section>
    </div>
  );
}
