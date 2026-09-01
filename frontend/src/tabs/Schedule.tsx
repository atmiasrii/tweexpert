// Schedule. The week is the primary object: seven columns you can read at a
// glance, with the queue that drains into those slots underneath.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useToast } from "../components/Toast";
import {
  Badge, Button, Card, EmptyState, ErrorState, SectionTitle, Select, Skeleton, cx,
} from "../components/ui";
import { IconPlus, IconSchedule, IconX } from "../components/Icons";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

export function Schedule() {
  const qc = useQueryClient();
  const { toast, reportError, confirm } = useToast();
  const s = useQuery({ queryKey: ["schedule"], queryFn: () => api.get("/api/schedule") });

  const [wd, setWd] = useState(0);
  const [hour, setHour] = useState(9);
  const [minute, setMinute] = useState(0);

  // Tue/Wed/Thu, morning and lunch. The scheduler data behind this is for a
  // US tech audience, so it is a starting prior, not truth: re-check it against
  // your own Analytics after a few weeks.
  const RECOMMENDED = [1, 2, 3].flatMap((d) => [
    { weekday: d, hour: 9, minute: 0 },
    { weekday: d, hour: 13, minute: 0 },
  ]);

  const addRecommended = useMutation({
    mutationFn: async () => {
      for (const s of RECOMMENDED) await api.post("/api/schedule/slots", { ...s, category: "" });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedule"] });
      toast({ tone: "success", title: "Added 6 slots", detail: "Tue to Thu, 9am and 1pm." });
    },
    onError: (e) => reportError(e, "Could not add those slots"),
  });

  const addSlot = useMutation({
    mutationFn: () => api.post("/api/schedule/slots", { weekday: wd, hour, minute, category: "" }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["schedule"] }); toast({ tone: "success", title: "Slot added" }); },
    onError: (e) => reportError(e, "Could not add that slot"),
  });

  const removeQueued = useMutation({
    mutationFn: (id: number) => api.del(`/api/schedule/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["schedule"] }); toast({ title: "Removed from the queue" }); },
    onError: (e) => reportError(e, "Could not remove that post"),
  });

  if (s.isError) return <ErrorState error={s.error} onRetry={s.refetch} />;

  const slots: any[] = s.data?.slots ?? [];
  const queued: any[] = s.data?.queued ?? [];

  async function dropQueued(q: any) {
    const ok = await confirm({
      title: "Remove this from the queue?",
      danger: true,
      confirmLabel: "Remove",
      body: <span className="tweet block mt-1">{q.text}</span>,
    });
    if (ok) removeQueued.mutate(q.id);
  }

  return (
    <div className="space-y-5 max-w-[900px]">
      <Card>
        <SectionTitle hint="posting times, in your timezone">Weekly slots</SectionTitle>

        {s.isPending ? (
          <Skeleton className="h-32" />
        ) : (
          <div className="grid grid-cols-7 gap-1.5">
            {DAYS.map((d, i) => {
              const mine = slots
                .filter((sl) => sl.weekday === i)
                .sort((a, b) => a.hour * 60 + a.minute - (b.hour * 60 + b.minute));
              return (
                <div key={d}
                  className={cx(
                    "rounded-sm border p-1.5 min-h-[92px]",
                    mine.length ? "border-rule bg-surface" : "border-dashed border-rule bg-surface/40"
                  )}>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-faint mb-1.5 text-center">
                    {d}
                  </div>
                  <div className="space-y-1">
                    {mine.map((sl) => (
                      <div key={sl.id}
                        className="num text-[11.5px] font-medium text-center rounded-[4px] py-0.5
                          bg-[color:var(--accent-soft)] text-accent">
                        {String(sl.hour).padStart(2, "0")}:{String(sl.minute).padStart(2, "0")}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <form
          className="flex flex-wrap items-end gap-2 mt-3"
          onSubmit={(e) => { e.preventDefault(); addSlot.mutate(); }}
        >
          <Select value={wd} onChange={(e) => setWd(+e.target.value)} aria-label="Weekday" className="w-auto">
            {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
          </Select>
          <Select value={hour} onChange={(e) => setHour(+e.target.value)} aria-label="Hour" className="w-auto">
            {HOURS.map((h) => <option key={h} value={h}>{String(h).padStart(2, "0")}</option>)}
          </Select>
          <Select value={minute} onChange={(e) => setMinute(+e.target.value)} aria-label="Minute" className="w-auto">
            {[0, 15, 30, 45].map((m) => <option key={m} value={m}>{String(m).padStart(2, "0")}</option>)}
          </Select>
          <Button type="submit" variant="default" icon={<IconPlus size={14} />} loading={addSlot.isPending}>
            Add slot
          </Button>
          <span className="text-[12px] text-faint ml-1">
            Sends drift a few minutes off the slot on purpose.
          </span>
        </form>

        {slots.length === 0 && !s.isPending && (
          <div className="mt-3 pt-3 border-t border-rule flex flex-wrap items-center gap-2">
            <Button variant="primary" loading={addRecommended.isPending}
              onClick={() => addRecommended.mutate()}>
              Use recommended times
            </Button>
            <span className="text-[12px] text-faint">
              Tuesday to Thursday, 9am and 1pm. Best window for a tech audience.
              Check your own Analytics after a few weeks and adjust.
            </span>
          </div>
        )}
      </Card>

      <Card>
        <SectionTitle hint="evergreen posts are pulled in when the queue runs dry">
          Queued posts
        </SectionTitle>

        {s.isPending ? (
          <div className="space-y-2">{[0, 1].map((i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : queued.length === 0 ? (
          <EmptyState
            icon={<IconSchedule size={24} />}
            title="Nothing queued"
            note="Write something on Compose and queue it, or mark posts evergreen so the slots never go empty."
          />
        ) : (
          <ul className="space-y-2">
            {queued.map((q) => (
              <li key={q.id}>
                <div className="flex items-start gap-3 group rounded-sm border border-rule bg-surface-2/40 p-3">
                  <div className="tweet flex-1 min-w-0">{q.text}</div>
                  <div className="flex items-center gap-2 shrink-0">
                    {q.evergreen ? <Badge tone="go">evergreen</Badge>
                      : q.category ? <Badge tone="neutral">{q.category}</Badge> : null}
                    <button
                      onClick={() => dropQueued(q)}
                      aria-label="Remove from queue"
                      className="h-7 w-7 grid place-items-center rounded-sm text-faint
                        hover:text-risk hover:bg-[color:var(--risk-soft)] transition-colors
                        opacity-0 group-hover:opacity-100 focus:opacity-100"
                    >
                      <IconX size={14} />
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
