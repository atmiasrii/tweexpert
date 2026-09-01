// The one control. Press it and Quill starts doing the unattended work: it
// hands the browser to the engine-owning process, starts the schedulers, and
// then says plainly what is still in the way.
//
// It never promotes an account to auto. The shadow period is the safeguard the
// rest of the design leans on, so this panel reports which accounts will only
// draft and sends you to the Watchlist, where that change carries a warning.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { TabId } from "../lib/nav";
import { useToast } from "./Toast";
import { Badge, Button, Card, Skeleton, cx } from "./ui";
import {
  IconAlert, IconCheck, IconExternal, IconInfo, IconKill, IconSpark, IconX,
} from "./Icons";

export type LaunchCheck = {
  id: string;
  label: string;
  state: "ok" | "blocked" | "warn";
  detail: string;
  action?: string;
};

export type LaunchStatus = {
  live: boolean;
  engine: string;
  /** The X handle Quill posts as; used by the previews. */
  operator?: string;
  processes: Record<string, boolean>;
  started_at: string | null;
  queued_drafts: number;
  checks: LaunchCheck[];
  blocking: string[];
  ready: boolean;
};

export function useLaunchStatus() {
  return useQuery<LaunchStatus>({
    queryKey: ["launch"],
    queryFn: () => api.get("/api/launch"),
    // Process state changes underneath us; this is the one thing worth polling.
    refetchInterval: 5000,
  });
}

function uptime(iso: string | null) {
  if (!iso) return "";
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 90) return `${Math.round(secs)}s`;
  if (secs < 5400) return `${Math.round(secs / 60)}m`;
  return `${Math.round(secs / 3600)}h`;
}

export function LaunchPanel({ go }: { go: (t: TabId) => void }) {
  const qc = useQueryClient();
  const { toast, reportError, confirm } = useToast();
  const q = useLaunchStatus();

  const start = useMutation({
    mutationFn: () => api.post("/api/launch/start"),
    onSuccess: () => {
      qc.invalidateQueries();
      toast({
        tone: "success",
        title: "Quill is live",
        detail: "It is watching your accounts and will draft as posts come in.",
      });
    },
    onError: (e) => reportError(e, "Could not start"),
  });

  const stop = useMutation({
    mutationFn: () => api.post("/api/launch/stop"),
    onSuccess: () => {
      qc.invalidateQueries();
      toast({ title: "Stopped", detail: "Nothing queued or drafted was lost." });
    },
    onError: (e) => reportError(e, "Could not stop"),
  });

  const login = useMutation({
    mutationFn: () => api.post("/api/launch/login"),
    onSuccess: (d: any) => {
      toast({
        title: "Sign in to X in the window that just opened",
        detail: `A browser is opening on this machine as @${d?.handle ?? "your account"}. ` +
          "Quill never sees your password. It waits up to five minutes.",
      });
    },
    onError: (e) => reportError(e, "Could not open the login window"),
  });

  const releaseKill = useMutation({
    mutationFn: () => api.post("/api/governor/kill", { on: false }),
    onSuccess: () => { qc.invalidateQueries(); toast({ tone: "success", title: "Kill switch released" }); },
    onError: (e) => reportError(e, "Could not release the kill switch"),
  });

  // Declared before any early return so hook order stays stable.
  const [showAll, setShowAll] = useState(false);

  async function onGoLive() {
    const s = q.data;
    const unresolved = (s?.checks ?? []).filter((c) => c.state === "blocked" && c.id !== "engine");
    const ok = await confirm({
      title: "Let Quill act on your X account?",
      confirmLabel: "Go live",
      body: (
        <>
          It will read the accounts you watch and draft replies in your voice.
          Anything on <b>auto</b> is published without asking you first, under the
          daily caps. Everything else waits in the queue for your approval.
          {unresolved.length > 0 && (
            <span className="block mt-2">
              Starting anyway with {unresolved.length} item
              {unresolved.length === 1 ? "" : "s"} outstanding — the panel will keep showing what is missing.
            </span>
          )}
        </>
      ),
    });
    if (ok) start.mutate();
  }

  async function onStop() {
    const ok = await confirm({
      title: "Stop Quill?",
      confirmLabel: "Stop",
      body: "The watcher and the sender shut down. Queued drafts, the shadow log and your settings are kept.",
    });
    if (ok) stop.mutate();
  }

  function runAction(a?: string) {
    if (a === "login") login.mutate();
    else if (a === "watchlist") go("Watchlist");
    else if (a === "release_kill") releaseKill.mutate();
    else if (a === "start") onGoLive();
  }

  if (q.isPending) {
    return <Card className="space-y-3"><Skeleton className="h-11 w-48" /><Skeleton className="h-24" /></Card>;
  }

  const s = q.data!;
  const blockers = s.checks.filter((c) => c.state === "blocked");
  const warns = s.checks.filter((c) => c.state === "warn");
  // Only what is wrong is worth screen space; everything else hides behind Details.
  const problems = [...blockers, ...warns];
  const visibleChecks = showAll ? s.checks : problems;
  const busy = start.isPending || stop.isPending;

  return (
    <Card
      pad={false}
      className={cx(
        "overflow-hidden",
        s.live && blockers.length === 0 && "border-[color:var(--go)]",
        s.live && blockers.length > 0 && "border-[color:var(--warn)]"
      )}
    >
      <div className="p-4 sm:p-5 flex flex-wrap items-center gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={cx(
              "h-2 w-2 rounded-full shrink-0",
              s.live
                ? blockers.length
                  ? "bg-[color:var(--warn)]"
                  : "bg-[color:var(--go)]"
                : "bg-[color:var(--muted)]"
            )} />
            <h2 className="text-[17px] font-semibold tracking-tight">
              {s.live
                ? blockers.length ? "Live, but held up" : "Quill is running"
                : "Quill is not running"}
            </h2>
            {s.live && s.started_at && (
              <Badge tone="neutral">up {uptime(s.started_at)}</Badge>
            )}
            {!s.live && s.engine !== "playwright" && (
              <Badge tone="neutral">offline fixtures</Badge>
            )}
          </div>
          <p className="text-[13px] text-muted mt-1 max-w-prose">
            {s.live
              ? blockers.length
                ? "The processes are up but it cannot reach your account yet. Clear the items below."
                : `Watching your accounts and drafting replies. ${s.queued_drafts} waiting for you.`
              : "Nothing is being read, drafted or sent. One button starts the watcher, the drafter and the sender."}
          </p>
        </div>

        {s.live ? (
          <Button size="lg" variant="default" loading={stop.isPending} onClick={onStop}
            icon={<IconX size={16} />}>
            Stop Quill
          </Button>
        ) : (
          <Button size="lg" variant="primary" loading={busy} onClick={onGoLive}
            icon={<IconSpark size={17} />} className="px-7 text-[15px]">
            Start Quill
          </Button>
        )}
      </div>

      {(blockers.length > 0 || warns.length > 0 || s.live) && (
        <div className="border-t border-rule bg-surface-2/60 px-4 sm:px-5 py-3">
          {/* When everything is fine, one line says so. The full checklist is a
              click away — a permanent wall of green ticks teaches nothing. */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[13px] font-medium">
              {problems.length ? (
                <span className="text-ink">
                  {problems.length} thing{problems.length === 1 ? "" : "s"} need
                  {problems.length === 1 ? "s" : ""} your attention
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-go">
                  <IconCheck size={15} /> All systems go
                </span>
              )}
            </span>
            <button
              onClick={() => setShowAll((v) => !v)}
              className="ml-auto text-[12.5px] text-muted hover:text-ink transition-colors"
            >
              {showAll ? "Hide details" : `Details (${s.checks.length})`}
            </button>
          </div>
          <ul className={cx("space-y-1.5", visibleChecks.length === 0 && "hidden")}>
            {visibleChecks.map((c) => (
              <li key={c.id} className="flex items-start gap-2.5">
                <span className="mt-0.5 shrink-0">
                  {c.state === "ok" ? <IconCheck size={15} className="text-go" />
                    : c.state === "warn" ? <IconInfo size={15} className="text-warn" />
                      : <IconAlert size={15} className="text-risk" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className={cx("text-[13px] font-medium",
                    c.state === "blocked" ? "text-ink" : "text-ink-2")}>
                    {c.label}
                  </span>
                  <span className="block text-[12.5px] text-muted">{c.detail}</span>
                </span>
                {c.action && c.state !== "ok" && (
                  <Button
                    size="sm"
                    variant={c.state === "blocked" ? "primary" : "default"}
                    className="shrink-0"
                    loading={c.action === "login" ? login.isPending
                      : c.action === "release_kill" ? releaseKill.isPending : false}
                    icon={c.action === "login" ? <IconExternal size={13} />
                      : c.action === "release_kill" ? <IconKill size={13} /> : undefined}
                    onClick={() => runAction(c.action)}
                  >
                    {ACTION_LABEL[c.action] ?? "Fix"}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

const ACTION_LABEL: Record<string, string> = {
  login: "Sign in to X",
  watchlist: "Add accounts",
  release_kill: "Release",
  start: "Start",
};

/** Compact live/offline state for the status rail. */
export function LivePill({ onClick }: { onClick: () => void }) {
  const q = useLaunchStatus();
  const s = q.data;
  const live = !!s?.live;
  const held = live && (s?.blocking.length ?? 0) > 0;
  return (
    <button
      onClick={onClick}
      title={live ? "Quill is running - open the Overview" : "Quill is not running - click to set it up"}
      className={cx(
        "inline-flex items-center gap-1.5 h-9 px-2.5 rounded-sm border text-[12.5px] font-medium transition-colors whitespace-nowrap shrink-0",
        live && !held && "border-[color:var(--go)] text-go bg-[color:var(--go-soft)]",
        held && "border-[color:var(--warn)] text-warn bg-[color:var(--warn-soft)]",
        !live && "border-rule-strong text-muted hover:text-ink hover:border-muted"
      )}
    >
      <span className={cx("h-1.5 w-1.5 rounded-full",
        live && !held ? "bg-[color:var(--go)]" : held ? "bg-[color:var(--warn)]" : "bg-[color:var(--muted)]")} />
      <span className="hidden sm:inline">{live ? (held ? "Held up" : "Live") : "Not running"}</span>
    </button>
  );
}
