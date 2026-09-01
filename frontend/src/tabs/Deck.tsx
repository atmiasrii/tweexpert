// TweetDeck view. Three live columns: replies waiting on you, replies already
// sent, and posts from your For You feed you can jump on. Built to answer fast —
// each pending card has approve/skip right there.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useToast } from "../components/Toast";
import { Badge, Button, EmptyState, SectionTitle, Skeleton, cx } from "../components/ui";
import { IconArrowRight, IconCheck, IconSpark, IconX } from "../components/Icons";
import { TweetCard } from "../components/TweetCard";

export function Deck() {
  return (
    <div className="grid gap-3 lg:grid-cols-3 items-start h-full">
      <Column title="Pending" hint="waiting on you"><Pending /></Column>
      <Column title="Sent" hint="already replied"><Sent /></Column>
      <Column title="For You" hint="jump on your feed"><ForYou /></Column>
    </div>
  );
}

function Column({ title, hint, children }: { title: string; hint: string; children: React.ReactNode }) {
  return (
    <section className="rounded-md border border-rule bg-surface-2/40 p-2.5 flex flex-col
      max-h-[calc(100vh-160px)]">
      <div className="px-1.5 pb-2"><SectionTitle hint={hint}>{title}</SectionTitle></div>
      <div className="space-y-2.5 overflow-y-auto pr-0.5">{children}</div>
    </section>
  );
}

/* ── pending ────────────────────────────────────────────────── */
function Pending() {
  const qc = useQueryClient();
  const { toast, reportError } = useToast();
  const q = useQuery({ queryKey: ["queue"], queryFn: () => api.get("/api/queue") });

  const approve = useMutation({
    mutationFn: (id: number) => api.post(`/api/drafts/${id}/approve`, {}),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["queue"] }); toast({ tone: "success", title: "Sent" }); },
    onError: (e) => reportError(e, "Could not send"),
  });
  const skip = useMutation({
    mutationFn: (id: number) => api.post(`/api/drafts/${id}/dismiss`, { reason: "skip" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["queue"] }),
    onError: (e) => reportError(e, "Could not skip"),
  });

  if (q.isPending) return <>{[0, 1].map((i) => <Skeleton key={i} className="h-40" />)}</>;
  const items: any[] = q.data ?? [];
  if (items.length === 0) return <EmptyState title="Queue clear" note="Nothing waiting. New drafts land here." />;

  return (
    <>
      {items.map((d) => (
        <div key={d.id} className="rounded-md border border-rule bg-surface p-2.5 space-y-2">
          {d.parent && (
            <TweetCard handle={d.parent.author} name={d.parent.author} text={d.parent.text} when="" dense
              className="!border-0 !p-0" />
          )}
          <div className="rounded-sm bg-[color:var(--accent-soft)]/40 border border-[color:var(--accent-soft)] p-2">
            <div className="text-[11px] text-muted mb-0.5">your reply · rel {Math.round(d.relevance)}</div>
            <div className="tweet !text-[14px]">{d.final_text}</div>
          </div>
          <div className="flex gap-1.5">
            <Button size="sm" variant="primary" icon={<IconCheck size={13} />}
              loading={approve.isPending} onClick={() => approve.mutate(d.id)}>Approve</Button>
            <Button size="sm" variant="ghost" icon={<IconX size={13} />}
              onClick={() => skip.mutate(d.id)}>Skip</Button>
          </div>
        </div>
      ))}
    </>
  );
}

/* ── sent ───────────────────────────────────────────────────── */
function Sent() {
  const q = useQuery({
    queryKey: ["deck-sent"],
    queryFn: () => api.get("/api/ops/actions?kind=reply&outcome=done&limit=40"),
    refetchInterval: 5000,
  });
  if (q.isPending) return <>{[0, 1].map((i) => <Skeleton key={i} className="h-16" />)}</>;
  const rows: any[] = (q.data ?? []).filter((a: any) => a.x_post_id);
  if (rows.length === 0) return <EmptyState title="Nothing sent yet" note="Approved and auto-sent replies show here." />;
  return (
    <>
      {rows.map((a) => (
        <div key={a.id} className="rounded-md border border-rule bg-surface p-2.5">
          <div className="flex items-center gap-1.5 text-[12px]">
            <Badge tone={a.issuer === "policy" ? "accent" : "go"}>{a.issuer === "policy" ? "auto" : "you"}</Badge>
            {a.target && <span className="text-muted">→ @{a.target}</span>}
            <span className="ml-auto num text-[11px] text-faint">{when(a.created_at)}</span>
          </div>
          <a className="mt-1 inline-flex items-center gap-1 text-[12px] text-accent hover:underline"
            href={`https://x.com/i/status/${a.x_post_id}`} target="_blank" rel="noreferrer">
            view on X <IconArrowRight size={12} />
          </a>
        </div>
      ))}
    </>
  );
}

/* ── for you ────────────────────────────────────────────────── */
function ForYouAuto() {
  const qc = useQueryClient();
  const { toast, reportError } = useToast();
  const cfg = useQuery({ queryKey: ["foryou-cfg"], queryFn: () => api.get("/api/live/foryou/config"), refetchInterval: 10000 });
  const save = useMutation({
    mutationFn: (patch: any) => api.put("/api/live/foryou/config", patch),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["foryou-cfg"] }); },
    onError: (e) => reportError(e, "Could not update"),
  });
  const c = cfg.data ?? {};
  const on = !!c.foryou_enabled;
  return (
    <div className="rounded-md border border-rule bg-surface p-2.5 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-semibold">Auto-reply to For You</span>
        <button
          onClick={() => save.mutate({ foryou_enabled: !on })}
          className={cx("relative h-5 w-9 rounded-full transition-colors",
            on ? "bg-[color:var(--accent)]" : "bg-[color:var(--rule-strong)]")}
          aria-pressed={on} aria-label="Toggle For You auto-reply">
          <span className={cx("absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all",
            on ? "left-[18px]" : "left-0.5")} />
        </button>
      </div>
      <div className="text-[12px] text-muted">
        every <b className="text-ink">{c.foryou_interval_min ?? 5} min</b>, scans up to{" "}
        <b className="text-ink">{c.foryou_per_run ?? 5}</b> posts ·{" "}
        <select value={c.foryou_mode ?? "auto"} onChange={(e) => save.mutate({ foryou_mode: e.target.value })}
          className="bg-transparent border border-rule rounded-sm px-1 py-0.5 text-[12px]">
          <option value="auto">auto-send</option>
          <option value="assisted">draft only</option>
        </select>
      </div>
      <div className="text-[11.5px] text-faint">
        sent today: <span className="num">{c.sent_today ?? 0}</span>/{c.cap ?? 40} ·
        replies still space out ~9 min apart to stay safe
      </div>
      {on && c.foryou_mode === "auto" && (
        <div className="text-[11px] text-warn">Sends to strangers on its own once Quill is live.</div>
      )}
    </div>
  );
}

function ForYou() {
  const qc = useQueryClient();
  const { toast, reportError } = useToast();
  const disc = useQuery({ queryKey: ["discover"], queryFn: () => api.get("/api/discover") });

  const scan = useMutation({
    mutationFn: () => api.post("/api/live/foryou"),
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ["discover", "queue"] }); toast({ tone: "success", title: "Scanned For You", detail: `picked ${d.picked ?? 0}, sent ${d.sent ?? 0}, queued ${d.queued ?? 0}.` }); },
    onError: (e) => reportError(e, "Could not scan For You"),
  });
  const promote = useMutation({
    mutationFn: (id: number) => api.post(`/api/discover/${id}/promote`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["discover", "queue"] }); toast({ tone: "success", title: "Drafted", detail: "It's in Pending." }); },
    onError: (e) => reportError(e, "Could not draft that"),
  });

  const items: any[] = disc.data ?? [];
  return (
    <>
      <ForYouAuto />
      <Button size="sm" variant="default" icon={<IconSpark size={13} />}
        loading={scan.isPending} onClick={() => scan.mutate()} className="w-full">
        Scan my For You feed now
      </Button>
      {disc.isPending ? <Skeleton className="h-24" /> :
        items.length === 0 ? <EmptyState title="Nothing surfaced" note="Scan your feed, or add saved searches in Discover." /> :
        items.map((d) => (
          <div key={d.id} className="rounded-md border border-rule bg-surface p-2.5 space-y-2">
            <TweetCard handle={d.author} name={d.author} text={d.text} when="" dense className="!border-0 !p-0" />
            <Button size="sm" variant="ghost" icon={<IconArrowRight size={13} />}
              loading={promote.isPending} onClick={() => promote.mutate(d.id)}>Draft a reply</Button>
          </div>
        ))}
    </>
  );
}

function when(iso?: string): string {
  if (!iso) return "";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return `${Math.floor(s / 3600)}h`;
}
