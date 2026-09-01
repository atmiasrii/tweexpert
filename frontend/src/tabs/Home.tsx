// Overview. Answers three questions in one screen: is it healthy, how much of
// today's budget is spent, and is anything waiting on me.
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { TabId } from "../lib/nav";
import {
  Badge, Button, Card, ErrorState, Meter, SectionTitle, Skeleton, StatusDot, cx,
} from "../components/ui";
import { IconArrowRight, IconCheck, IconExternal, IconSpark } from "../components/Icons";
import { LaunchPanel, useLaunchStatus } from "../components/LaunchPanel";
import { PipelineFlow } from "../components/PipelineFlow";

export function Home({ go }: { go: (t: TabId) => void }) {
  const gov = useQuery({ queryKey: ["governor"], queryFn: () => api.get("/api/governor") });
  const health = useQuery({ queryKey: ["health"], queryFn: () => api.get("/api/ops/health") });
  const queue = useQuery({ queryKey: ["queue"], queryFn: () => api.get("/api/queue") });
  const shadow = useQuery({ queryKey: ["shadow"], queryFn: () => api.get("/api/shadow") });
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api.get("/api/accounts") });
  const actions = useQuery({ queryKey: ["actions"], queryFn: () => api.get("/api/ops/actions?limit=8") });
  const launch = useLaunchStatus();

  const g = gov.data;
  const h = health.data;
  const u = g?.usage;
  const queueN = queue.data?.length ?? 0;
  const shadowN = shadow.data?.length ?? 0;

  const stopped = launch.data ? !launch.data.live : false;

  if (gov.isError) return <ErrorState error={gov.error} onRetry={gov.refetch} />;

  return (
    <div className="space-y-4">
      {/* The one control, above everything it governs. */}
      <LaunchPanel go={go} />

      {/* Live: what Quill is doing right now, step by step. */}
      <PipelineFlow />

      <div className="grid gap-4 lg:grid-cols-3 items-start">
      {/* What needs a human, first and largest. */}
      <div className="lg:col-span-2 space-y-4">
        <Card className="space-y-3">
          <SectionTitle hint="drafts held for your decision">Needs you</SectionTitle>
          <div className="grid sm:grid-cols-2 gap-3">
            <Attention
              n={queueN}
              label={queueN === 1 ? "reply waiting" : "replies waiting"}
              cta="Review queue"
              tone={queueN > 0 ? "accent" : "quiet"}
              onGo={() => go("Autopilot")}
              loading={queue.isPending}
            />
            <Attention
              n={shadowN}
              label={shadowN === 1 ? "shadow draft to grade" : "shadow drafts to grade"}
              cta="Open shadow log"
              tone={shadowN > 0 ? "warn" : "quiet"}
              onGo={() => go("Autopilot")}
              loading={shadow.isPending}
            />
          </div>
          {queueN === 0 && shadowN === 0 && !queue.isPending && (
            <div className="flex items-center gap-2 text-[13px] text-go pt-1">
              <IconCheck size={15} />
              Nothing waiting. The watcher runs on schedule — you don't need to sit here.
            </div>
          )}
        </Card>

        <Card>
          <SectionTitle hint="today, per the governor (S-07)">Budget</SectionTitle>
          {!u ? (
            <div className="grid sm:grid-cols-2 gap-4">
              {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-9" />)}
            </div>
          ) : (
            <div className="grid sm:grid-cols-2 gap-x-6 gap-y-4">
              <Meter label="Auto replies" used={u.replies_auto.used} cap={u.replies_auto.cap}
                hint="Auto disables itself on trouble" />
              <Meter label="Assisted replies" used={u.replies_assisted.used} cap={u.replies_assisted.cap} />
              <Meter label="Posts" used={u.posts.used} cap={u.posts.cap} />
              <Meter label="Threads" used={u.threads.used} cap={u.threads.cap} />
            </div>
          )}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 mt-4 pt-3 border-t border-rule text-[12.5px] text-muted">
            <span>mode <Badge tone={g?.mode === "auto" ? "accent" : g?.mode === "assisted" ? "warn" : "neutral"}>{g?.mode ?? "—"}</Badge></span>
            <span className="num">reads today <b className="text-ink-2">{u?.reads ?? 0}</b></span>
            {g?.quiet_now && <Badge tone="neutral">quiet hours</Badge>}
            {g?.kill_switch && <Badge tone="risk">kill switch on</Badge>}
          </div>
        </Card>

        <Card>
          <SectionTitle action={
            <Button size="sm" variant="ghost" onClick={() => go("Ops")} icon={<IconArrowRight size={14} />}>
              Full audit
            </Button>
          }>
            Recent actions
          </SectionTitle>
          {actions.isPending ? (
            <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-5" />)}</div>
          ) : (actions.data ?? []).length === 0 ? (
            <p className="text-[13px] text-muted">Nothing has run yet.</p>
          ) : (
            <ul className="divide-y divide-[color:var(--rule)] -my-1">
              {(actions.data ?? []).slice(0, 6).map((a: any) => (
                <li key={a.id} className="flex items-center gap-2.5 py-2 text-[13px]">
                  <span className={cx(
                    "h-1.5 w-1.5 rounded-full shrink-0",
                    a.outcome === "done" ? "bg-[color:var(--go)]"
                      : a.error ? "bg-[color:var(--risk)]" : "bg-[color:var(--muted)]"
                  )} />
                  <span className="font-medium">{a.kind}</span>
                  <span className="text-faint">by {a.issuer}</span>
                  <span className="ml-auto text-[12px] text-muted num shrink-0">
                    {a.created_at ? new Date(a.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Health rail. */}
      <div className="space-y-4">
        <Card className="space-y-2.5">
          <SectionTitle>Health</SectionTitle>
          <div className="space-y-2">
            <HealthRow label="X session" ok={h?.session_ok} loading={health.isPending}
              stale={stopped} okText="logged in" badText="signed out" />
            <HealthRow label="Selector canary" ok={h?.canary_ok} loading={health.isPending}
              stale={stopped} okText="matching" badText="drifted" />
            <HealthRow label="Worker" ok={stopped ? false : h?.worker_ok}
              loading={health.isPending} okText="running" badText="not running" />
          </div>
          {stopped && (
            <p className="text-[11.5px] text-faint">
              Readings are from the last time Quill ran. Start it for live values.
            </p>
          )}
          <div className="pt-2.5 mt-1 border-t border-rule flex items-center gap-2 text-[12.5px] text-muted">
            <span>engine</span>
            <Badge tone={h?.engine === "playwright" ? "accent" : "neutral"}>{h?.engine ?? "…"}</Badge>
            {h?.engine === "fixture" && <span className="text-faint">offline fixtures</span>}
          </div>
          {h?.stale_processes?.length > 0 && (
            <div className="text-[12.5px] text-risk">stale: {h.stale_processes.join(", ")}</div>
          )}
        </Card>

        <Card className="space-y-2.5">
          <SectionTitle>Watchlist</SectionTitle>
          {accounts.isPending ? (
            <Skeleton className="h-16" />
          ) : (accounts.data ?? []).length === 0 ? (
            <p className="text-[13px] text-muted">
              No accounts watched yet. Quill has nothing to read.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {(accounts.data ?? []).slice(0, 6).map((a: any) => (
                <li key={a.id} className="flex items-center gap-2 text-[13px]">
                  <span className="truncate">@{a.handle}</span>
                  <Badge className="ml-auto shrink-0"
                    tone={a.mode === "auto" ? "accent" : a.mode === "assisted" ? "warn" : "neutral"}>
                    {a.mode}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
          <Button size="sm" variant="default" className="w-full mt-1" onClick={() => go("Watchlist")}>
            Manage watchlist
          </Button>
        </Card>

        <Card className="space-y-2">
          <SectionTitle>Quick start</SectionTitle>
          <Quick icon={<IconSpark size={15} />} label="Write a post" onClick={() => go("Compose")} />
          <Quick icon={<IconExternal size={15} />} label="Tune the voice card" onClick={() => go("Persona")} />
          <Quick icon={<IconArrowRight size={15} />} label="Check discovery" onClick={() => go("Discover")} />
        </Card>
        </div>
      </div>
    </div>
  );
}

function Attention({
  n, label, cta, tone, onGo, loading,
}: {
  n: number; label: string; cta: string;
  tone: "accent" | "warn" | "quiet"; onGo: () => void; loading?: boolean;
}) {
  const live = tone !== "quiet";
  return (
    <button
      onClick={onGo}
      className={cx(
        "text-left rounded-md border p-3.5 transition-colors group",
        live
          ? tone === "accent"
            ? "border-[color:var(--accent)] bg-[color:var(--accent-soft)] hover:brightness-[.98]"
            : "border-[color:var(--warn)] bg-[color:var(--warn-soft)] hover:brightness-[.98]"
          : "border-rule bg-surface-2 hover:border-muted"
      )}
    >
      <div className="flex items-baseline gap-2">
        <span className={cx("num text-[28px] font-semibold leading-none",
          live ? (tone === "accent" ? "text-accent" : "text-warn") : "text-muted")}>
          {loading ? "—" : n}
        </span>
        <span className="text-[13px] text-muted">{label}</span>
      </div>
      <span className={cx(
        "inline-flex items-center gap-1 mt-2.5 text-[12.5px] font-medium",
        live ? (tone === "accent" ? "text-accent" : "text-warn") : "text-muted"
      )}>
        {cta}
        <IconArrowRight size={13} className="transition-transform group-hover:translate-x-0.5" />
      </span>
    </button>
  );
}

function HealthRow({
  label, ok, loading, stale, okText, badText,
}: {
  label: string; ok?: boolean; loading?: boolean; stale?: boolean;
  okText: string; badText: string;
}) {
  const unknown = loading || ok === undefined || stale;
  const text = loading ? "..." : stale ? "not checked" : ok ? okText : badText;
  return (
    <div className="flex items-center gap-2">
      <span className="text-[13px] text-ink-2">{label}</span>
      <span className="ml-auto">
        <StatusDot ok={ok} unknown={unknown} label={text} />
      </span>
    </div>
  );
}

function Quick({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className="w-full flex items-center gap-2.5 h-9 px-2.5 -mx-1 rounded-sm text-[13px] text-ink-2
        hover:bg-surface-2 hover:text-ink transition-colors text-left">
      <span className="text-muted">{icon}</span>
      {label}
    </button>
  );
}
