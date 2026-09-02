// Every reply Quill has put out, and what happened to each one. This is the
// question the operator actually asks ("did that thing I approved go out, and
// did it land?"), so it belongs on the dashboard, not buried in Analytics.
//
// Left: the list, newest first, each row colour-coded by where it got to.
// Right: the one you clicked, with its timeline and its numbers over time.
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Card, EmptyState, ErrorState, Help, SectionTitle, Skeleton, cx } from "./ui";
import { IconArrowRight, IconCheck } from "./Icons";

/* One colour per stage, used identically in the list, the detail and the
   timeline, so the colour itself carries the meaning. */
type Tone = "neutral" | "accent" | "go" | "risk" | "warn" | "info";

export const STAGE: Record<string, { label: string; tone: Tone }> = {
  waiting:  { label: "waiting on you", tone: "warn" },
  practice: { label: "practice",       tone: "neutral" },
  sending:  { label: "sending",        tone: "info" },
  posted:   { label: "live on X",      tone: "info" },
  measured: { label: "no reply yet",   tone: "neutral" },
  answered: { label: "got a reply",    tone: "go" },
  failed:   { label: "failed",         tone: "risk" },
  skipped:  { label: "skipped",        tone: "neutral" },
};

export function SentReplies() {
  const q = useQuery({
    queryKey: ["sent-replies"],
    queryFn: () => api.get("/api/analytics/sent"),
    refetchInterval: 15000,
  });
  const rows: any[] = q.data ?? [];
  const [picked, setPicked] = useState<number | null>(null);

  // Default to the newest reply so the panel is never an empty box.
  useEffect(() => {
    if (picked == null && rows.length) setPicked(rows[0].draft_id);
  }, [rows, picked]);

  const answered = rows.filter((r) => r.stage === "answered").length;

  return (
    <Card>
      <SectionTitle
        hint="what happened to each one"
        action={
          rows.length > 0 ? (
            <span className="text-[12px] text-muted">
              <b className="num text-go">{answered}</b> of{" "}
              <b className="num text-ink">{rows.length}</b> got a reply back
              <Help text="Someone replying under your reply is the outcome worth having. X does not say who replied, so this counts any replier." />
            </span>
          ) : undefined
        }
      >
        Replies you have sent
      </SectionTitle>

      {q.isPending ? (
        <Skeleton className="h-56" />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={q.refetch} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="Nothing sent yet"
          note="Approve a reply on Autopilot and it will show up here with its progress."
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)] items-start">
          <ul className="rounded-sm border border-rule divide-y divide-[color:var(--rule)]
            max-h-[420px] overflow-y-auto">
            {rows.map((r) => {
              const s = STAGE[r.stage] ?? STAGE.measured;
              const on = r.draft_id === picked;
              return (
                <li key={r.draft_id}>
                  <button
                    onClick={() => setPicked(r.draft_id)}
                    aria-current={on}
                    className={cx(
                      "w-full text-left px-3 py-2.5 transition-colors",
                      on ? "bg-[color:var(--accent-soft)]" : "hover:bg-surface-2"
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <StageDot stage={r.stage} />
                      <span className="text-[12.5px] font-medium text-ink truncate">
                        {r.to ? `@${r.to}` : "unknown"}
                      </span>
                      {r.auto && <Badge tone="warn">auto</Badge>}
                      <span className="ml-auto text-[11px] text-faint num shrink-0">
                        {ago(r.sent_at || r.created_at)}
                      </span>
                    </div>
                    <div className="text-[12.5px] text-muted mt-0.5 line-clamp-2">
                      {r.text}
                    </div>
                    <div className="mt-1 text-[11px] text-faint">{s.label}</div>
                  </button>
                </li>
              );
            })}
          </ul>

          <Detail draftId={picked} />
        </div>
      )}
    </Card>
  );
}

function StageDot({ stage }: { stage: string }) {
  const tone = (STAGE[stage] ?? STAGE.measured).tone;
  const map: Record<Tone, string> = {
    neutral: "var(--muted)", accent: "var(--accent)", go: "var(--go)",
    risk: "var(--risk)", warn: "var(--warn)", info: "var(--info)",
  };
  return (
    <span className="h-2 w-2 rounded-full shrink-0" style={{ background: map[tone] }} />
  );
}

/* ── one reply, in full ─────────────────────────────────────── */
function Detail({ draftId }: { draftId: number | null }) {
  const q = useQuery({
    queryKey: ["sent-reply", draftId],
    queryFn: () => api.get(`/api/analytics/sent/${draftId}`),
    enabled: draftId != null,
    refetchInterval: 20000,
  });

  if (draftId == null) {
    return <div className="text-[13px] text-muted p-4">Pick a reply to see how it did.</div>;
  }
  if (q.isPending) return <Skeleton className="h-[420px]" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={q.refetch} />;

  const d: any = q.data;
  const s = STAGE[d.stage] ?? STAGE.measured;
  const last = d.series?.[d.series.length - 1];

  return (
    <div className="rounded-sm border border-rule bg-surface-2/40 p-3 space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge tone={s.tone}>{s.label}</Badge>
        {d.mode && <Badge tone="neutral">{d.mode}</Badge>}
        {d.url && (
          <a href={d.url} target="_blank" rel="noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-[12px] text-accent hover:underline">
            open on X <IconArrowRight size={12} />
          </a>
        )}
      </div>

      <p className="text-[12.5px] text-muted">{d.note}</p>

      {d.parent_text && (
        <div className="rounded-sm border border-rule bg-surface p-2.5">
          <div className="text-[11px] text-faint mb-0.5">
            {d.to ? `@${d.to} posted` : "in reply to"}
          </div>
          <div className="tweet !text-[13px] line-clamp-4">{d.parent_text}</div>
        </div>
      )}

      <div className="rounded-sm border border-[color:var(--accent-soft)]
        bg-[color:var(--accent-soft)]/40 p-2.5">
        <div className="text-[11px] text-muted mb-0.5">your reply</div>
        <div className="tweet !text-[13.5px]">{d.text}</div>
      </div>

      {d.error && (
        <div className="rounded-sm border border-[color:var(--risk)]
          bg-[color:var(--risk-soft)] px-2.5 py-2 text-[12.5px] text-risk">
          {d.error}
        </div>
      )}

      <Timeline steps={d.steps ?? []} />

      {last && (
        <div className="grid grid-cols-3 gap-2">
          <Metric label="replies" value={last.replies} tone={last.replies > 0 ? "go" : "neutral"}
            help="The one that counts. Worth about 150 likes to X's ranking." />
          <Metric label="likes" value={last.likes} tone="neutral"
            help="Nearly worthless to the algorithm. Nice, but not the goal." />
          <Metric label="views" value={last.views} tone="neutral" />
        </div>
      )}

      {d.series?.length > 1 && <Series series={d.series} />}
    </div>
  );
}

function Timeline({ steps }: { steps: any[] }) {
  return (
    <ol className="space-y-0">
      {steps.map((st, i) => {
        const lastOne = i === steps.length - 1;
        return (
          <li key={st.key} className="flex gap-2.5">
            <div className="flex flex-col items-center">
              <span className={cx(
                "h-4 w-4 rounded-full grid place-items-center shrink-0 mt-0.5",
                st.done ? "bg-[color:var(--go)] text-white"
                        : "border border-dashed border-rule-strong"
              )}>
                {st.done && <IconCheck size={10} />}
              </span>
              {!lastOne && (
                <span className={cx("w-px flex-1 my-0.5",
                  st.done ? "bg-[color:var(--go)]/40" : "bg-[color:var(--rule)]")} />
              )}
            </div>
            <div className={cx("pb-2.5", lastOne && "pb-0")}>
              <div className={cx("text-[12.5px]", st.done ? "text-ink font-medium" : "text-faint")}>
                {st.label}
              </div>
              {/* A time on a step that has not happened reads as if it had. */}
              {(() => {
                const at = st.done && st.at ? when(st.at) : "";
                const detail = st.detail ?? "";
                if (!at && !detail) return null;
                return (
                  <div className="text-[11.5px] text-faint">
                    {at}{at && detail ? " · " : ""}{detail}
                  </div>
                );
              })()}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function Metric({ label, value, tone, help }: {
  label: string; value: number; tone: "go" | "neutral"; help?: string;
}) {
  return (
    <div className="rounded-sm border border-rule bg-surface px-2.5 py-2">
      <div className={cx("num text-[20px] font-semibold leading-none",
        tone === "go" ? "text-go" : "text-ink")}>
        {value}
      </div>
      <div className="text-[11.5px] text-muted mt-1">
        {label}{help && <Help text={help} />}
      </div>
    </div>
  );
}

/** How the numbers moved across the measurement checkpoints. */
function Series({ series }: { series: any[] }) {
  const max = Math.max(1, ...series.map((p) => p.views || p.likes || 0));
  return (
    <div>
      <div className="text-[11.5px] text-muted mb-1.5">how it moved</div>
      <div className="flex items-end gap-1.5 h-16">
        {series.map((p, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-1" title={when(p.at)}>
            <div className="w-full rounded-t-[3px] bg-[color:var(--info)]"
              style={{ height: `${Math.max(3, ((p.views || p.likes || 0) / max) * 100)}%` }} />
            <span className="text-[10px] text-faint num">{p.likes}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ago(iso?: string): string {
  if (!iso) return "";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

function when(iso?: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString([], {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}
