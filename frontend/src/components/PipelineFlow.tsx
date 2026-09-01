// The live flow. Shows the pipeline as a row of stages and lights up the one
// Quill is on right now, with a ticker of what just happened — who was read,
// what got drafted, where a reply went. Polls the activity feed so it reflects
// the browser/worker processes, not just this tab.
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Card, SectionTitle, cx } from "./ui";

const STAGE_TONE: Record<string, string> = {
  watching: "read", scoring: "read", drafting: "work", reviewing: "work",
  queued: "wait", sending: "send", sent: "done",
  discarded: "muted", silent: "muted", idle: "muted",
};

export function PipelineFlow() {
  const q = useQuery({
    queryKey: ["live-activity"],
    queryFn: () => api.get("/api/live/activity"),
    refetchInterval: 1500,        // a live view earns a real poll
  });
  const stages: { id: string; label: string }[] = q.data?.stages ?? [];
  const current = q.data?.current ?? { stage: "idle" };
  const recent: any[] = q.data?.recent ?? [];

  const activeId = current.stage;
  // Map terminal stages back onto the visible pipeline for highlighting.
  const activeIndex = stages.findIndex((s) => s.id === activeId);
  const highlightIdx = activeIndex >= 0 ? activeIndex
    : activeId === "discarded" || activeId === "silent" ? 1
    : activeId === "sent" ? stages.length - 1 : -1;

  const busy = ["watching", "scoring", "drafting", "reviewing", "sending"].includes(activeId);

  return (
    <Card className="space-y-3">
      <SectionTitle hint="what Quill is doing, live"
        action={<span className={cx("inline-flex items-center gap-1.5 text-[12px]",
          busy ? "text-go" : "text-muted")}>
          <span className={cx("h-2 w-2 rounded-full", busy ? "bg-[color:var(--go)] animate-pulse" : "bg-[color:var(--faint)]")} />
          {busy ? "active" : "idle"}
        </span>}>
        Pipeline
      </SectionTitle>

      <div className="flex items-stretch gap-1 overflow-x-auto pb-1">
        {stages.map((s, i) => {
          const on = i === highlightIdx;
          const done = highlightIdx >= 0 && i < highlightIdx;
          return (
            <div key={s.id} className="flex items-center gap-1 shrink-0">
              <div className={cx(
                "px-2.5 py-1.5 rounded-sm border text-[12px] whitespace-nowrap transition-colors",
                on ? "border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-accent font-semibold"
                   : done ? "border-[color:var(--go)]/40 text-go"
                   : "border-rule text-muted"
              )}>
                {on && <span className="inline-block h-1.5 w-1.5 rounded-full bg-[color:var(--accent)] mr-1.5 animate-pulse" />}
                {s.label}
              </div>
              {i < stages.length - 1 && (
                <span className={cx("text-[11px]", done ? "text-go" : "text-faint")}>→</span>
              )}
            </div>
          );
        })}
      </div>

      <div className="rounded-sm border border-rule divide-y divide-[color:var(--rule)] max-h-44 overflow-y-auto">
        {recent.length === 0 ? (
          <div className="px-3 py-3 text-[12.5px] text-muted">Nothing yet. Start Quill to see it work.</div>
        ) : recent.map((r) => (
          <div key={r.id} className="px-3 py-1.5 flex items-center gap-2 text-[12.5px]">
            <StageDot stage={r.stage} />
            <span className="text-ink-2">{label(r)}</span>
            <span className="ml-auto num text-[11px] text-faint">{time(r.at)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function label(r: any): string {
  const t = r.target ? ` @${r.target.replace(/^@/, "")}` : "";
  switch (r.stage) {
    case "watching": return r.detail || `reading${t}`;
    case "drafting": return `drafting a reply to${t}`;
    case "queued": return `queued a reply to${t} — waiting for you`;
    case "sending": return `sending your reply to${t}`;
    case "sent": return `replied to${t} ✓`;
    case "discarded": return `skipped${t}: ${r.detail || "not worth a reply"}`;
    case "silent": return `no good angle for${t}`;
    default: return r.detail || r.stage;
  }
}

function StageDot({ stage }: { stage: string }) {
  const tone = STAGE_TONE[stage] ?? "muted";
  const color = tone === "done" ? "var(--go)" : tone === "send" ? "var(--accent)"
    : tone === "muted" ? "var(--faint)" : tone === "wait" ? "var(--warn)" : "var(--accent)";
  return <span className="h-1.5 w-1.5 rounded-full shrink-0" style={{ background: color }} />;
}

function time(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
