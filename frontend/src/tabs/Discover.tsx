// Discover. Four small feeds. The inbox is the one that leads anywhere, so it
// gets the wide column; searches, mentions and people sit in the rail.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useToast } from "../components/Toast";
import {
  Badge, Button, Card, EmptyState, ErrorState, Input, SectionTitle, Skeleton,
} from "../components/ui";
import { IconArrowRight, IconDiscover, IconPlus, IconX } from "../components/Icons";

export function Discover() {
  return (
    <div className="grid gap-4 lg:grid-cols-3 items-start">
      <div className="lg:col-span-2"><Inbox /></div>
      <div className="space-y-4">
        <SavedSearches />
        <Mentions />
        <People />
      </div>
    </div>
  );
}

function Inbox() {
  const qc = useQueryClient();
  const { toast, reportError } = useToast();
  const disc = useQuery({ queryKey: ["discover"], queryFn: () => api.get("/api/discover") });

  const promote = useMutation({
    mutationFn: (id: number) => api.post(`/api/discover/${id}/promote`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["discover"] });
      qc.invalidateQueries({ queryKey: ["queue"] });
      toast({ tone: "success", title: "Promoted", detail: "It's in the Autopilot queue with drafted replies." });
    },
    onError: (e) => reportError(e, "Could not promote that"),
  });

  if (disc.isError) return <ErrorState error={disc.error} onRetry={disc.refetch} />;
  if (disc.isPending) return <div className="space-y-2">{[0, 1, 2].map((i) => <Card key={i}><Skeleton className="h-12" /></Card>)}</div>;

  const items: any[] = disc.data ?? [];

  return (
    <section>
      <SectionTitle hint="found outside the watchlist">Discovery inbox</SectionTitle>
      {items.length === 0 ? (
        <EmptyState
          icon={<IconDiscover size={24} />}
          title="Nothing surfaced"
          note="Saved searches feed this list. Add one on the right and Quill will bring back posts worth a reply."
        />
      ) : (
        <div className="space-y-2">
          {items.map((d) => (
            <Card key={d.id} className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-semibold">@{d.author}</span>
                <Badge tone={d.relevance >= 78 ? "accent" : "neutral"} className="ml-auto">
                  rel {Math.round(d.relevance)}
                </Badge>
              </div>
              <div className="tweet">{d.text}</div>
              <Button size="sm" variant="ghost" className="-ml-2" icon={<IconArrowRight size={14} />}
                loading={promote.isPending} onClick={() => promote.mutate(d.id)}>
                Promote to queue
              </Button>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}

function SavedSearches() {
  const qc = useQueryClient();
  const { reportError } = useToast();
  const searches = useQuery({ queryKey: ["searches"], queryFn: () => api.get("/api/searches") });
  const [q, setQ] = useState("");

  const add = useMutation({
    mutationFn: () => api.post("/api/searches", { query: q }),
    onSuccess: () => { setQ(""); qc.invalidateQueries({ queryKey: ["searches"] }); },
    onError: (e) => reportError(e, "Could not save that search"),
  });
  const del = useMutation({
    mutationFn: (id: number) => api.del(`/api/searches/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["searches"] }),
    onError: (e) => reportError(e, "Could not delete that search"),
  });

  const list: any[] = searches.data ?? [];

  return (
    <Card className="space-y-3">
      <SectionTitle>Saved searches</SectionTitle>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim()) add.mutate(); }}>
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="query" aria-label="Search query" />
        <Button type="submit" variant="default" icon={<IconPlus size={14} />}
          loading={add.isPending} disabled={!q.trim()} aria-label="Save search" />
      </form>
      {searches.isPending ? (
        <Skeleton className="h-8" />
      ) : list.length === 0 ? (
        <p className="text-[12.5px] text-muted">None saved.</p>
      ) : (
        <ul className="divide-y divide-[color:var(--rule)] -my-1">
          {list.map((s: any) => (
            <li key={s.id} className="py-1.5 flex items-center gap-2 group">
              <span className="mono text-ink-2 flex-1 truncate">{s.query}</span>
              <button onClick={() => del.mutate(s.id)} aria-label={`Delete search ${s.query}`}
                className="shrink-0 h-6 w-6 grid place-items-center rounded-sm text-faint
                  hover:text-risk opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity">
                <IconX size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Mentions() {
  const notifs = useQuery({ queryKey: ["notifications"], queryFn: () => api.get("/api/notifications") });
  const list: any[] = notifs.data ?? [];
  return (
    <Card className="space-y-2">
      <SectionTitle hint="read-only">Mentions</SectionTitle>
      {notifs.isPending ? (
        <Skeleton className="h-10" />
      ) : list.length === 0 ? (
        <p className="text-[12.5px] text-muted">Nothing new.</p>
      ) : (
        <ul className="divide-y divide-[color:var(--rule)] -my-1">
          {list.slice(0, 8).map((n: any) => (
            <li key={n.id} className="py-2">
              <div className="flex items-baseline gap-2">
                <span className="text-[12.5px] font-semibold">@{n.author_handle}</span>
                {n.kind && <Badge tone="neutral">{n.kind}</Badge>}
              </div>
              <div className="text-[13px] text-ink-2 mt-0.5 truncate-2">{n.text}</div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function People() {
  const people = useQuery({ queryKey: ["people"], queryFn: () => api.get("/api/people") });
  const list: any[] = people.data ?? [];
  return (
    <Card className="space-y-2">
      <SectionTitle hint="who you engage with most">People</SectionTitle>
      {people.isPending ? (
        <Skeleton className="h-10" />
      ) : list.length === 0 ? (
        <p className="text-[12.5px] text-muted">No engagement history yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {list.slice(0, 10).map((p: any) => (
            <li key={p.handle} className="flex items-center gap-2 text-[13px]">
              <span className="truncate">@{p.handle}</span>
              <span className="ml-auto num text-[12px] text-muted shrink-0">{p.engagements}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
