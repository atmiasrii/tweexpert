// Autopilot — the heart of the product (§19). One draft on screen at a time, so
// the decision is always "send this or not", never "scan a wall of drafts".
// Shortcuts (U-01): J/K navigate, 1/2/3 pick a candidate, E edit, Enter approve,
// X skip, U undo. Every action is reachable by touch too, one-handed at 380px
// (T-14): the action bar sticks to the bottom of the viewport on phones.
import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useToast } from "../components/Toast";
import { useLaunchStatus } from "../components/LaunchPanel";
import {
  Badge, Button, Card, EmptyState, ErrorState, Segmented, SkeletonCard, Textarea, cx,
} from "../components/ui";
import {
  IconCheck, IconPencil, IconSpark, IconX,
} from "../components/Icons";

type View = "queue" | "shadow" | "thresholds";

const AXES = [
  ["sounds_like_operator", "voice"],
  ["adds_something", "adds"],
  ["reads_human", "human"],
  ["low_embarrassment_risk", "safe"],
] as const;

/** Seconds the send is held so it can still be undone (U-02). */
const UNDO_SECONDS = 5;

export function Autopilot({ suspendKeys = false, go }: {
  suspendKeys?: boolean; go: (t: "Home") => void;
}) {
  const [view, setView] = useState<View>("queue");
  const queue = useQuery({ queryKey: ["queue"], queryFn: () => api.get("/api/queue") });
  const shadow = useQuery({ queryKey: ["shadow"], queryFn: () => api.get("/api/shadow") });

  return (
    <div className="space-y-4">
      <Segmented
        value={view}
        onChange={setView}
        options={[
          { value: "queue", label: "Queue", count: queue.data?.length ?? undefined },
          { value: "shadow", label: "Shadow log", count: shadow.data?.length ?? undefined },
          { value: "thresholds", label: "Thresholds" },
        ]}
      />
      {view === "queue" && <Queue suspendKeys={suspendKeys} onGoSetup={() => go("Home")} />}
      {view === "shadow" && <ShadowLog />}
      {view === "thresholds" && <Thresholds />}
    </div>
  );
}

/* ── queue ────────────────────────────────────────────────── */

function Queue({ suspendKeys, onGoSetup }: { suspendKeys: boolean; onGoSetup: () => void }) {
  const qc = useQueryClient();
  const launch = useLaunchStatus();
  const { toast, reportError } = useToast();
  const q = useQuery({ queryKey: ["queue"], queryFn: () => api.get("/api/queue") });
  const items: any[] = q.data ?? [];

  const [idx, setIdx] = useState(0);
  const [pick, setPick] = useState(0);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const editRef = useRef<HTMLTextAreaElement>(null);

  // The send in flight, if any: held locally for UNDO_SECONDS before the bus.
  const [pendingSend, setPendingSend] = useState<{ id: number; text: string; left: number } | null>(null);
  const timers = useRef<{ tick?: number; fire?: number }>({});

  const cur = items[Math.min(idx, Math.max(items.length - 1, 0))];

  useEffect(() => {
    if (!cur) return;
    setText(cur.final_text ?? "");
    setPick(cur.chosen_index ?? 0);
    setEditing(false);
  }, [cur?.id]);

  useEffect(() => {
    if (idx > items.length - 1) setIdx(Math.max(items.length - 1, 0));
  }, [items.length, idx]);

  const approve = useMutation({
    mutationFn: (b: { id: number; text: string }) =>
      api.post(`/api/drafts/${b.id}/approve`, { text: b.text }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["queue"] });
      qc.invalidateQueries({ queryKey: ["governor"] });
      toast({ tone: "success", title: "Reply sent" });
    },
    // A refusal here is the governor doing its job — say which gate stopped it.
    onError: (e) => reportError(e, "The reply was not sent"),
  });

  const dismiss = useMutation({
    mutationFn: (id: number) => api.post(`/api/drafts/${id}/dismiss`, { reason: "skip" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["queue"] }),
    onError: (e) => reportError(e, "Could not skip that draft"),
  });

  const clearTimers = useCallback(() => {
    if (timers.current.tick) window.clearInterval(timers.current.tick);
    if (timers.current.fire) window.clearTimeout(timers.current.fire);
    timers.current = {};
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const doApprove = useCallback(() => {
    if (!cur || pendingSend) return;
    const id = cur.id;
    const body = text;
    clearTimers();
    setPendingSend({ id, text: body, left: UNDO_SECONDS });
    timers.current.tick = window.setInterval(() => {
      setPendingSend((p) => (p ? { ...p, left: Math.max(0, p.left - 1) } : p));
    }, 1000);
    timers.current.fire = window.setTimeout(() => {
      clearTimers();
      setPendingSend(null);
      approve.mutate({ id, text: body });
    }, UNDO_SECONDS * 1000);
    // Move on immediately; the queue refetch will settle the true order.
    setIdx((i) => Math.min(i + 1, Math.max(items.length - 2, 0)));
  }, [cur, text, pendingSend, items.length, approve, clearTimers]);

  const cancelSend = useCallback(() => {
    clearTimers();
    setPendingSend(null);
    toast({ title: "Send cancelled", detail: "The draft is still in the queue." });
  }, [clearTimers, toast]);

  const pickCand = useCallback((i: number) => {
    const c = cur?.candidates?.[i];
    if (!c) return;
    setPick(i);
    setText(c.text);
  }, [cur]);

  const startEdit = useCallback(() => {
    setEditing(true);
    requestAnimationFrame(() => {
      const el = editRef.current;
      el?.focus();
      el?.setSelectionRange(el.value.length, el.value.length);
    });
  }, []);

  useEffect(() => {
    if (suspendKeys) return;
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement | null;
      const typing = !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
      if (typing) {
        if (e.key === "Escape") { e.preventDefault(); setEditing(false); (el as HTMLElement).blur(); }
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === "j") { e.preventDefault(); setIdx((i) => Math.min(i + 1, items.length - 1)); }
      else if (k === "k") { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)); }
      else if (k === "1" || k === "2" || k === "3") { e.preventDefault(); pickCand(Number(k) - 1); }
      else if (k === "e") { e.preventDefault(); startEdit(); }
      else if (e.key === "Enter") { e.preventDefault(); doApprove(); }
      else if (k === "x") { e.preventDefault(); if (cur) dismiss.mutate(cur.id); }
      else if (k === "u") { e.preventDefault(); if (pendingSend) cancelSend(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [suspendKeys, items.length, cur, pendingSend, pickCand, startEdit, doApprove, cancelSend, dismiss]);

  if (q.isPending) return <SkeletonCard rows={5} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={q.refetch} />;

  if (items.length === 0) {
    // An empty queue means two very different things. Say which one.
    return (
      <>
        {launch.data && !launch.data.live ? (
          <EmptyState
            icon={<IconSpark size={26} />}
            title="Quill is not running"
            note="Nothing is being read or drafted, so the queue cannot fill. Start it from the Overview."
            action={<Button variant="primary" onClick={onGoSetup}>Set up and start</Button>}
          />
        ) : (
          <EmptyState
            icon={<IconCheck size={26} />}
            title="Queue is clear"
            note="Nothing was worth replying to. The watcher checks again on schedule - you don't need to sit here."
          />
        )}
        {pendingSend && <UndoBar left={pendingSend.left} onUndo={cancelSend} />}
      </>
    );
  }

  const cand = cur?.candidates?.[pick];
  const critic = cand?.critic ?? cur?.critic?.[pick];
  const overLimit = text.length > 280;
  const edited = cand ? text.trim() !== String(cand.text ?? "").trim() : false;

  return (
    <div className="max-w-[720px]">
      {/* Position + keys. The legend is muted so it never competes with the tweet. */}
      <div className="flex items-center gap-3 mb-2.5">
        <span className="num text-[12.5px] text-muted shrink-0">
          <b className="text-ink font-semibold">{Math.min(idx + 1, items.length)}</b> of {items.length}
        </span>
        <div className="h-1 flex-1 rounded-full bg-surface-3 overflow-hidden max-w-[180px]">
          <div className="h-full bg-[color:var(--accent)] rounded-full transition-[width] duration-200"
            style={{ width: `${((idx + 1) / items.length) * 100}%` }} />
        </div>
        <div className="hidden sm:flex items-center gap-1.5 ml-auto text-[11.5px] text-faint">
          <span className="kbd">J</span><span className="kbd">K</span><span>move</span>
          <span className="kbd ml-1.5">E</span><span>edit</span>
          <span className="kbd ml-1.5">↵</span><span>approve</span>
          <span className="kbd ml-1.5">X</span><span>skip</span>
        </div>
      </div>

      {cur && (
        <Card pad={false} className="overflow-hidden">
          {/* Source post — untrusted text, rendered as data and nothing else (X-05). */}
          <div className="p-4 pb-3 border-b border-rule bg-surface-2/60">
            <div className="flex items-center gap-2 mb-2">
              <Avatar handle={cur.parent?.author ?? cur.account} />
              <span className="text-[13.5px] font-semibold truncate">@{cur.parent?.author ?? cur.account}</span>
              <Badge tone={cur.relevance >= 78 ? "accent" : "neutral"} className="ml-auto shrink-0">
                rel {Math.round(cur.relevance)}
              </Badge>
            </div>
            <div className="tweet text-ink-2">{cur.parent?.text}</div>
          </div>

          {/* The reply. Loudest element on the card. */}
          <div className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-faint">Your reply</span>
              {edited && <Badge tone="warn">edited</Badge>}
              <span className={cx("ml-auto num text-[12px]", overLimit ? "text-risk font-semibold" : "text-faint")}>
                {text.length}/280
              </span>
            </div>

            {editing ? (
              <Textarea
                ref={editRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onBlur={() => setEditing(false)}
                rows={4}
                className="tweet"
                aria-label="Edit reply"
              />
            ) : (
              <button
                onClick={startEdit}
                className={cx(
                  "w-full text-left rounded-sm border border-transparent px-2.5 py-2 -mx-2.5",
                  "hover:border-rule hover:bg-surface-2 transition-colors group"
                )}
                title="Click to edit (E)"
              >
                <span className="tweet">{text}</span>
                <IconPencil size={13} className="inline-block ml-1.5 mb-0.5 text-faint opacity-0 group-hover:opacity-100 transition-opacity" />
              </button>
            )}

            {/* Candidates: three angles, picked by number key or tap. */}
            {(cur.candidates?.length ?? 0) > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {cur.candidates.map((c: any, i: number) => {
                  const on = i === pick;
                  const blocked = c.prefilter_ok === false;
                  return (
                    <button
                      key={i}
                      onClick={() => pickCand(i)}
                      title={blocked ? `Filtered: ${c.prefilter_reason}` : c.angle}
                      className={cx(
                        "inline-flex items-center gap-1.5 h-7 pl-1.5 pr-2.5 rounded-full border text-[12.5px] transition-colors",
                        on
                          ? "bg-[color:var(--accent-soft)] border-[color:var(--accent)] text-accent font-medium"
                          : "bg-surface border-rule-strong text-muted hover:text-ink hover:border-muted"
                      )}
                    >
                      <span className={cx("kbd", on && "border-[color:var(--accent)] text-accent")}>{i + 1}</span>
                      {c.angle}
                      {blocked && <IconX size={12} className="text-risk" />}
                      {c.similarity_hit && <span className="text-warn text-[11px]">≈</span>}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Critic, one chip per axis — a single min score hides which axis failed. */}
            {critic && (
              <div className="flex flex-wrap items-center gap-1.5 mt-3 pt-3 border-t border-rule">
                <span className="text-[11px] uppercase tracking-wider text-faint mr-0.5">critic</span>
                {AXES.map(([key, label]) => {
                  const v = critic[key];
                  const tone = v == null ? "neutral" : v >= 4 ? "go" : v >= 3 ? "warn" : "risk";
                  return (
                    <Badge key={key} tone={tone as any}>
                      {label} {v ?? "—"}
                    </Badge>
                  );
                })}
                {critic.followed_injected_instructions && (
                  <Badge tone="risk">obeyed injected instructions</Badge>
                )}
                {cand?.prefilter_ok === false && (
                  <Badge tone="risk">filtered: {cand.prefilter_reason}</Badge>
                )}
              </div>
            )}
          </div>

          {/* Action bar. Sticky above the fold on phones so it is thumb-reachable. */}
          <div className={cx(
            "flex gap-2 p-3 border-t border-rule bg-surface",
            "sticky bottom-0 z-10"
          )}
            style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}>
            <Button
              variant="primary" size="lg"
              className="flex-1 sm:flex-none sm:px-8"
              icon={<IconCheck size={16} />}
              disabled={!!pendingSend || overLimit}
              onClick={doApprove}
            >
              Approve
            </Button>
            <Button variant="default" size="lg" icon={<IconPencil size={15} />} onClick={startEdit}
              className="sm:px-5">
              <span className="hidden sm:inline">Edit</span>
            </Button>
            <Button variant="default" size="lg" icon={<IconX size={15} />}
              loading={dismiss.isPending}
              onClick={() => cur && dismiss.mutate(cur.id)}
              className="sm:px-5">
              <span className="hidden sm:inline">Skip</span>
            </Button>
          </div>
        </Card>
      )}

      {pendingSend && <UndoBar left={pendingSend.left} onUndo={cancelSend} />}
    </div>
  );
}

/** The send-time undo (U-02): a real hold, not a cosmetic delay. */
function UndoBar({ left, onUndo }: { left: number; onUndo: () => void }) {
  const pct = (left / UNDO_SECONDS) * 100;
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 flex justify-center p-4 pointer-events-none"
      style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}>
      <div className="pointer-events-auto anim-toast flex items-center gap-3 pl-3.5 pr-2 h-11
        bg-[color:var(--ink)] text-[color:var(--ground)] rounded-full shadow-pop">
        <span className="relative grid place-items-center h-6 w-6 shrink-0">
          <svg width="24" height="24" viewBox="0 0 24 24" className="-rotate-90">
            <circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" strokeWidth="2" opacity=".25" />
            <circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" strokeDasharray={2 * Math.PI * 9.5}
              strokeDashoffset={(2 * Math.PI * 9.5) * (1 - pct / 100)}
              style={{ transition: "stroke-dashoffset 1s linear" }} />
          </svg>
          <span className="absolute num text-[10px] font-semibold">{left}</span>
        </span>
        <span className="text-[13px] whitespace-nowrap">Sending…</span>
        <button onClick={onUndo}
          className="h-8 px-3 rounded-full text-[13px] font-semibold bg-white/15 hover:bg-white/25 transition-colors">
          Undo <span className="kbd ml-1 bg-transparent border-white/30 text-inherit">U</span>
        </button>
      </div>
    </div>
  );
}

function Avatar({ handle }: { handle?: string }) {
  const ch = (handle ?? "?").replace(/^@/, "").slice(0, 1).toUpperCase();
  return (
    <span className="grid place-items-center h-7 w-7 rounded-full bg-surface-3 text-[12px] font-semibold text-muted shrink-0">
      {ch}
    </span>
  );
}

/* ── shadow log ───────────────────────────────────────────── */

function ShadowLog() {
  const qc = useQueryClient();
  const { reportError, toast } = useToast();
  const q = useQuery({ queryKey: ["shadow"], queryFn: () => api.get("/api/shadow") });
  const judge = useMutation({
    mutationFn: (b: { id: number; approve: boolean }) =>
      api.post(`/api/shadow/${b.id}/judge`, { approve: b.approve }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shadow"] });
      qc.invalidateQueries({ queryKey: ["accounts"] });
      toast({ title: "Judged", detail: "That counts toward the shadow review total." });
    },
    onError: (e) => reportError(e, "Could not record that judgement"),
  });

  if (q.isPending) return <div className="space-y-3 max-w-[720px]"><SkeletonCard /><SkeletonCard /></div>;
  if (q.isError) return <ErrorState error={q.error} onRetry={q.refetch} />;

  const items: any[] = q.data ?? [];
  if (items.length === 0) {
    return (
      <EmptyState
        icon={<IconSpark size={26} />}
        title="No shadow drafts yet"
        note="Watched accounts start in shadow: Quill drafts, never sends, and you grade the drafts here until it has earned the right to act."
      />
    );
  }

  return (
    <div className="space-y-3 max-w-[720px]">
      <p className="text-[12.5px] text-muted">
        These were never sent. Grading them is what ends the shadow period — it is the evidence, not a formality.
      </p>
      {items.map((d) => (
        <Card key={d.id} className="space-y-2.5">
          <div className="flex items-center gap-2">
            <Avatar handle={d.parent?.author} />
            <span className="text-[13px] font-semibold truncate">@{d.parent?.author}</span>
            <Badge tone="neutral" className="ml-auto shrink-0">rel {Math.round(d.relevance)}</Badge>
          </div>
          {d.parent?.text && <div className="text-[13px] text-muted truncate-2">{d.parent.text}</div>}
          <div className="tweet border-l-2 border-[color:var(--accent)] pl-3">{d.final_text}</div>
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-[12.5px] text-muted mr-auto">
              would have sent{" "}
              {d.would_have_sent_at
                ? new Date(d.would_have_sent_at).toLocaleString([], { hour: "2-digit", minute: "2-digit", month: "short", day: "numeric" })
                : "—"}
            </span>
            <Button size="sm" variant="success" icon={<IconCheck size={14} />}
              onClick={() => judge.mutate({ id: d.id, approve: true })}>
              I'd have sent it
            </Button>
            <Button size="sm" variant="danger" icon={<IconX size={14} />}
              onClick={() => judge.mutate({ id: d.id, approve: false })}>
              I wouldn't
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ── thresholds ───────────────────────────────────────────── */

function Thresholds() {
  const rows: [string, string, string][] = [
    ["Relevance to draft at all", "60", "Below this the post is discarded unread by the persona engine."],
    ["Relevance to send automatically", "78", "Assisted replies still queue at 60; auto needs a clearly on-topic post."],
    ["Critic minimum, every axis", "4 of 5", "One weak axis blocks an auto send. Voice, substance, humanness, embarrassment risk."],
    ["Shadow period", "7 days + 20 reviewed", "Both, not either. Enforced in code — the mode selector stays locked until it passes."],
    ["Auto replies per day", "4", "Its own cap, well under the assisted cap. Auto disables itself on trouble."],
  ];
  return (
    <div className="max-w-[720px] space-y-4">
      <Card className="space-y-3">
        <p className="text-[13px] text-muted leading-relaxed">
          These are deliberately conservative and are not exposed as sliders. The safeguards
          exist to keep an unattended account survivable, not compliant — raising them is the
          one change that reliably ends badly.
        </p>
        <div className="divide-y divide-[color:var(--rule)]">
          {rows.map(([label, value, note]) => (
            <div key={label} className="py-2.5 first:pt-0 last:pb-0">
              <div className="flex items-baseline gap-3">
                <span className="text-[13.5px] font-medium text-ink">{label}</span>
                <span className="ml-auto num text-[13px] font-semibold text-accent shrink-0">{value}</span>
              </div>
              <div className="text-[12.5px] text-muted mt-0.5">{note}</div>
            </div>
          ))}
        </div>
      </Card>
      <p className="text-[12.5px] text-muted">
        Per-account autonomy mode is set on <b className="text-ink-2">Watchlist</b>.
      </p>
    </div>
  );
}
