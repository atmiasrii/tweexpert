// Analytics. Four questions: is the account growing, which reply angles land,
// how often you approve what Quill writes, and which posts did anything.
// Every chart is single-series, so no legend is needed — the title names it —
// and the numbers behind each chart are always available as a table.
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { BarChart, LineChart, Point, Stat } from "../components/Charts";
import {
  Badge, Card, EmptyState, ErrorState, SectionTitle, Skeleton, Table, Td, Tr, cx,
} from "../components/ui";
import { IconAnalytics } from "../components/Icons";

export function Analytics() {
  const posts = useQuery({ queryKey: ["an-posts"], queryFn: () => api.get("/api/analytics/posts") });
  const replies = useQuery({ queryKey: ["an-replies"], queryFn: () => api.get("/api/analytics/replies") });
  const followers = useQuery({ queryKey: ["an-followers"], queryFn: () => api.get("/api/analytics/followers") });
  const rate = useQuery({ queryKey: ["an-rate"], queryFn: () => api.get("/api/analytics/approval-rate") });

  const fSeries: any[] = followers.data?.series ?? [];
  const rSeries: any[] = rate.data?.series ?? [];

  const followerPoints: Point[] = useMemo(
    () => fSeries.map((p) => ({
      label: new Date(p.date).toLocaleDateString([], { month: "short", day: "numeric" }),
      value: p.count,
    })),
    [fSeries]
  );

  const ratePoints: Point[] = useMemo(
    () => rSeries.map((p) => ({ label: p.week, value: Math.round((p.rate ?? 0) * 100) })),
    [rSeries]
  );

  const latest = fSeries.at(-1)?.count;
  const prev = fSeries.at(-2)?.count;
  const delta = latest != null && prev != null ? latest - prev : undefined;
  const latestRate = rSeries.at(-1);

  const angleData: Point[] = (replies.data ?? []).map((r: any) => ({
    label: r.angle ?? "?",
    value: r.count ?? 0,
  }));

  return (
    <div className="space-y-4 max-w-[980px]">
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <SectionTitle hint="daily sample">Followers</SectionTitle>
          {followers.isPending ? (
            <Skeleton className="h-[168px]" />
          ) : followers.isError ? (
            <ErrorState error={followers.error} onRetry={followers.refetch} />
          ) : followerPoints.length === 0 ? (
            <p className="text-[13px] text-muted py-8 text-center">No samples yet.</p>
          ) : (
            <>
              <Stat label="latest" value={String(latest ?? "—")} delta={delta}
                hint={delta != null ? "change since the previous sample" : undefined} />
              <div className="mt-3">
                <LineChart data={followerPoints} valueLabel="followers" />
              </div>
            </>
          )}
        </Card>

        <Card>
          <SectionTitle hint="drafts you approved, by week">Approval rate</SectionTitle>
          {rate.isPending ? (
            <Skeleton className="h-[168px]" />
          ) : ratePoints.length === 0 ? (
            <p className="text-[13px] text-muted py-8 text-center">
              Not enough decisions yet. Approve or dismiss a few drafts.
            </p>
          ) : (
            <>
              <Stat
                label="latest week"
                value={`${Math.round((latestRate?.rate ?? 0) * 100)}%`}
                hint={latestRate?.n != null ? `${latestRate.n} decision${latestRate.n === 1 ? "" : "s"}` : undefined}
              />
              <div className="mt-3">
                <LineChart data={ratePoints} valueLabel="approval rate" format={(v) => `${v}%`} />
              </div>
            </>
          )}
        </Card>
      </div>

      <Card>
        <SectionTitle hint="which angle you actually send">Replies by angle</SectionTitle>
        {replies.isPending ? (
          <Skeleton className="h-20" />
        ) : angleData.length === 0 ? (
          <p className="text-[13px] text-muted">No replies sent yet.</p>
        ) : (
          <BarChart data={angleData} />
        )}
      </Card>

      <PostTable q={posts} />
    </div>
  );
}

function PostTable({ q }: { q: any }) {
  const [sort, setSort] = useState<"likes" | "views" | "length">("likes");
  const rows: any[] = useMemo(() => {
    const r = [...(q.data ?? [])];
    r.sort((a, b) => (b[sort] ?? 0) - (a[sort] ?? 0));
    return r;
  }, [q.data, sort]);

  if (q.isPending) return <Card><Skeleton className="h-32" /></Card>;
  if (q.isError) return <ErrorState error={q.error} onRetry={q.refetch} />;

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={<IconAnalytics size={24} />}
        title="No posts measured yet"
        note="Quill samples its own posts a while after they go out, so numbers appear on a delay."
      />
    );
  }

  const SortBtn = ({ k, label }: { k: typeof sort; label: string }) => (
    <button
      onClick={() => setSort(k)}
      className={cx(
        "text-[11.5px] uppercase tracking-wide font-semibold transition-colors",
        sort === k ? "text-accent" : "text-muted hover:text-ink"
      )}
    >
      {label}{sort === k ? " ↓" : ""}
    </button>
  );

  return (
    <Card>
      <SectionTitle hint="sampled after publication">Post performance</SectionTitle>
      <Table head={["Post", "Kind", <SortBtn key="l" k="length" label="Len" />,
        <SortBtn key="h" k="likes" label="Likes" />, <SortBtn key="v" k="views" label="Views" />]}>
        {rows.map((p: any) => (
          <Tr key={p.x_post_id}>
            <Td className="max-w-[420px]">
              <span className="block truncate" title={p.text}>{p.text}</span>
              {p.category && <span className="text-[11.5px] text-faint">{p.category}</span>}
            </Td>
            <Td><Badge tone={p.kind === "reply" ? "neutral" : "accent"}>{p.kind}</Badge></Td>
            <Td><span className="num text-muted">{p.length}</span></Td>
            <Td><span className="num font-medium">{p.likes}</span></Td>
            <Td><span className="num text-muted">{p.views}</span></Td>
          </Tr>
        ))}
      </Table>
    </Card>
  );
}
