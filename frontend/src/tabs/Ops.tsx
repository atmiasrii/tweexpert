// Ops. The console you open when something looks wrong: health first, then the
// action audit log (every write Quill has ever attempted), then the live log
// tail, model calls and backups.
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useToast } from "../components/Toast";
import {
  Badge, Button, Card, ErrorState, SectionTitle, Skeleton, StatusDot, Table, Td, Tr, cx,
} from "../components/ui";
import { IconCamera, IconExternal, IconX } from "../components/Icons";

export function Ops() {
  return (
    <div className="space-y-4 max-w-[980px]">
      <Health />
      <AuditLog />
      <div className="grid gap-4 lg:grid-cols-2 items-start">
        <LiveLogs />
        <div className="space-y-4">
          <ModelCalls />
          <Backups />
        </div>
      </div>
    </div>
  );
}

function Health() {
  const { toast, reportError } = useToast();
  const health = useQuery({ queryKey: ["health"], queryFn: () => api.get("/api/ops/health") });
  const relogin = useMutation({
    mutationFn: () => api.post("/api/ops/login"),
    onSuccess: (d: any) => {
      if (d?.vnc_url) {
        window.open(d.vnc_url, "_blank", "noopener");
        toast({ title: "Opened the browser view", detail: "Sign in by hand — Quill never handles the password." });
      } else {
        toast({ title: "No browser view available", detail: "The browser process may not be running." });
      }
    },
    onError: (e) => reportError(e, "Could not open the login view"),
  });

  if (health.isError) return <ErrorState error={health.error} onRetry={health.refetch} />;
  const h = health.data;

  return (
    <Card>
      <SectionTitle
        action={
          <Button size="sm" variant="default" icon={<IconExternal size={14} />}
            loading={relogin.isPending} onClick={() => relogin.mutate()}>
            Re-login (VNC)
          </Button>
        }
      >
        Health
      </SectionTitle>

      {health.isPending ? (
        <Skeleton className="h-10" />
      ) : (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <span className="flex items-center gap-2 text-[13px]">
            engine <Badge tone={h?.engine === "playwright" ? "accent" : "neutral"}>{h?.engine}</Badge>
          </span>
          <StatusDot ok={h?.session_ok} label={`session ${h?.session_ok ? "ok" : "down"}`} />
          <StatusDot ok={h?.canary_ok} label={`canary ${h?.canary_ok ? "ok" : "fail"}`} />
          <StatusDot ok={h?.worker_ok} label={`worker ${h?.worker_ok ? "ok" : "down"}`} />
          <span className="num text-[13px] text-muted">queue {h?.queue ?? 0}</span>
          {h?.latency_ms != null && (
            <span className="num text-[13px] text-muted">latency {h.latency_ms}ms</span>
          )}
          {h?.stale_processes?.length > 0 && (
            <Badge tone="risk">stale: {h.stale_processes.join(", ")}</Badge>
          )}
        </div>
      )}

      {h?.canary_ok === false && (
        <p className="text-[12.5px] text-risk mt-3">
          The selector canary is failing: X changed its DOM. Auto is disabled until
          <span className="mono mx-1">selectors.yaml</span> matches again.
        </p>
      )}
    </Card>
  );
}

function AuditLog() {
  const [onlyFailed, setOnlyFailed] = useState(false);
  const actions = useQuery({ queryKey: ["actions"], queryFn: () => api.get("/api/ops/actions?limit=50") });

  const rows: any[] = useMemo(() => {
    const r = actions.data ?? [];
    return onlyFailed ? r.filter((a: any) => a.outcome !== "done") : r;
  }, [actions.data, onlyFailed]);

  if (actions.isError) return <ErrorState error={actions.error} onRetry={actions.refetch} />;

  return (
    <section>
      <SectionTitle
        hint="every write, whoever issued it"
        action={
          <Button size="sm" variant={onlyFailed ? "primary" : "ghost"} onClick={() => setOnlyFailed((v) => !v)}>
            Failures only
          </Button>
        }
      >
        Action audit log
      </SectionTitle>

      {actions.isPending ? (
        <Card><Skeleton className="h-40" /></Card>
      ) : rows.length === 0 ? (
        <Card><p className="text-[13px] text-muted">{onlyFailed ? "No failures. " : "Nothing has run yet."}</p></Card>
      ) : (
        <div className="max-h-[340px] overflow-y-auto rounded-md">
          <Table head={["When", "Action", "Issued by", "State", "Result", ""]}>
            {rows.map((a: any) => (
              <Tr key={a.id}>
                <Td>
                  <span className="num text-[12px] text-muted whitespace-nowrap">
                    {a.created_at
                      ? new Date(a.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
                      : "—"}
                  </span>
                </Td>
                <Td><span className="font-medium">{a.kind}</span></Td>
                <Td>
                  <Badge tone={a.issuer === "human" ? "accent" : "neutral"}>{a.issuer}</Badge>
                </Td>
                <Td>
                  <span className={cx("text-[12.5px]",
                    a.outcome === "done" ? "text-go" : a.error ? "text-risk" : "text-muted")}>
                    {a.state}{a.outcome ? ` / ${a.outcome}` : ""}
                  </span>
                </Td>
                <Td className="max-w-[280px]">
                  {a.error
                    ? <span className="text-[12.5px] text-risk break-words">{a.error}</span>
                    : a.x_post_id
                      ? <span className="mono text-muted">{a.x_post_id}</span>
                      : <span className="text-faint">—</span>}
                  {a.attempts > 0 && <span className="ml-2 text-[11.5px] text-faint">{a.attempts} attempts</span>}
                </Td>
                <Td>
                  {a.screenshot_path && (
                    <span title={a.screenshot_path} className="text-faint"><IconCamera size={14} /></span>
                  )}
                </Td>
              </Tr>
            ))}
          </Table>
        </div>
      )}
    </section>
  );
}

const LINK_STATE = ["reconnecting…", "streaming", "disconnected"] as const;

function LiveLogs() {
  const [logs, setLogs] = useState<string[]>([]);
  const [paused, setPaused] = useState(false);
  // EventSource reconnects on its own, so a momentary close is not a failure.
  // Report the live readyState rather than latching on the first error.
  const [link, setLink] = useState<number>(0);
  const boxRef = useRef<HTMLPreElement>(null);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    const es = new EventSource("/api/ops/logs");
    es.addEventListener("log", (e: MessageEvent) => {
      if (pausedRef.current) return;
      try {
        const d = JSON.parse(e.data);
        if (d.line) setLogs((l) => [...l.slice(-300), d.line]);
      } catch { /* a malformed frame is not worth killing the tail for */ }
    });
    const poll = window.setInterval(() => setLink(es.readyState), 700);
    setLink(es.readyState);
    return () => { window.clearInterval(poll); es.close(); };
  }, []);

  // Follow the tail unless the operator has scrolled up to read something.
  useEffect(() => {
    const el = boxRef.current;
    if (!el || paused) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
    if (nearBottom) el.scrollTop = el.scrollHeight;
  }, [logs, paused]);

  return (
    <section>
      <SectionTitle
        hint={LINK_STATE[link] ?? "unknown"}
        action={
          <div className="flex gap-1.5">
            <Button size="sm" variant={paused ? "primary" : "ghost"} onClick={() => setPaused((v) => !v)}>
              {paused ? "Resume" : "Pause"}
            </Button>
            <Button size="sm" variant="ghost" icon={<IconX size={13} />} onClick={() => setLogs([])}
              aria-label="Clear log view" />
          </div>
        }
      >
        Live logs
      </SectionTitle>
      <pre ref={boxRef}
        className="mono h-[260px] overflow-auto rounded-md border border-rule bg-surface p-3
          text-[11.5px] leading-[1.6] whitespace-pre-wrap break-words shadow-1">
        {logs.length ? logs.join("\n") : link === 2 ? "stream closed" : "waiting for output…"}
      </pre>
    </section>
  );
}

function ModelCalls() {
  const llm = useQuery({
    queryKey: ["llm"],
    queryFn: () => api.get("/api/ops/llm"),
    refetchInterval: 10000,
  });
  const calls: any[] = (llm.data ?? []).slice(-10).reverse();

  return (
    <Card>
      <SectionTitle hint="latency and tokens per role">Model calls</SectionTitle>
      {llm.isPending ? (
        <Skeleton className="h-16" />
      ) : calls.length === 0 ? (
        <p className="text-[13px] text-muted">
          No calls yet. With no model endpoint reachable, Quill uses its offline generator.
        </p>
      ) : (
        <ul className="divide-y divide-[color:var(--rule)] -my-1.5">
          {calls.map((c: any, i: number) => (
            <li key={i} className="py-1.5 flex items-baseline gap-2 text-[12.5px]">
              <Badge tone={c.offline ? "neutral" : "accent"}>{c.role}</Badge>
              <span className="mono text-muted truncate">{c.model}</span>
              <span className="num text-muted ml-auto shrink-0">{c.latency_ms}ms</span>
              <span className="num text-faint shrink-0">
                {c.prompt_tokens}+{c.completion_tokens}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Backups() {
  const backups = useQuery({ queryKey: ["backups"], queryFn: () => api.get("/api/ops/backups") });
  const list: any[] = backups.data ?? [];
  return (
    <Card>
      <SectionTitle hint="nightly, encrypted">Backups</SectionTitle>
      {backups.isPending ? (
        <Skeleton className="h-12" />
      ) : list.length === 0 ? (
        <p className="text-[13px] text-muted">None taken yet.</p>
      ) : (
        <ul className="space-y-1">
          {list.map((b: any) => (
            <li key={b.name} className="flex items-baseline gap-2 text-[12.5px]">
              <span className="mono truncate">{b.name}</span>
              <span className="num text-muted ml-auto shrink-0">{Math.round(b.size / 1024)} KB</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
