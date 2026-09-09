import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Card, SectionTitle } from "./ui";

/** Today's run: when it started, what it owes, and whether it is keeping up.
 *  The point of this card is that "Quill has stopped" should be visible here
 *  rather than discovered in a log hours later.
 *
 *  Deliberately not the shared <Meter>: that one reddens as it fills, which is
 *  right for a cap you must not exceed and backwards for a target you want to
 *  reach. Here a full bar is the good outcome. */
export function RunProgress() {
  const run = useQuery({
    queryKey: ["run"],
    queryFn: () => api.get("/api/run"),
    refetchInterval: 30000,
  });
  const r = run.data;
  if (!r) return null;

  const startedAt = new Date(r.started_at).toLocaleTimeString([], {
    hour: "2-digit", minute: "2-digit",
  });
  const pct = r.target > 0 ? Math.min(100, (r.sent / r.target) * 100) : 0;
  const behind = Number(r.behind_by || 0);

  // Three states worth telling apart: keeping up, behind but still doable, and
  // out of time. Only the last will not fix itself.
  const outOfTime = !r.reachable;
  const lagging = !outOfTime && behind >= 3;
  const bar = outOfTime ? "var(--warn)" : "var(--go)";
  const status = outOfTime
    ? `Out of time: room for about ${r.capacity_left} more before ${r.deadline}`
    : lagging
      ? `Behind by ${behind.toFixed(0)}, widening what it looks at`
      : "Keeping pace";

  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <SectionTitle hint={`running since ${startedAt}`}>Today's run</SectionTitle>
        <div className="flex items-center gap-2">
          {r.relax_level > 0 && <Badge tone="info">reach {r.relax_level}</Badge>}
          {r.restarts?.length > 0 && (
            <Badge tone="warn">
              {r.restarts.length} restart{r.restarts.length === 1 ? "" : "s"}
            </Badge>
          )}
          <Badge tone={outOfTime ? "warn" : lagging ? "info" : "go"}>
            {r.sent} of {r.target}
          </Badge>
        </div>
      </div>

      <div className="h-2 rounded-full bg-surface-2 overflow-hidden">
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{ width: `${pct}%`, background: bar }}
        />
      </div>

      <div className="flex items-center justify-between gap-3 text-[12.5px] text-muted">
        <span>{status}</span>
        <span className="shrink-0">
          {r.reachable
            ? `${Number(r.expected).toFixed(0)} expected by now`
            : `target ${r.target} by ${r.deadline}`}
        </span>
      </div>
    </Card>
  );
}
