import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../lib/api";

export function Discover() {
  const qc = useQueryClient();
  const disc = useQuery({ queryKey: ["discover"], queryFn: () => api.get("/api/discover") });
  const searches = useQuery({ queryKey: ["searches"], queryFn: () => api.get("/api/searches") });
  const people = useQuery({ queryKey: ["people"], queryFn: () => api.get("/api/people") });
  const notifs = useQuery({ queryKey: ["notifications"], queryFn: () => api.get("/api/notifications") });
  const [q, setQ] = useState("");
  const addSearch = useMutation({ mutationFn: () => api.post("/api/searches", { query: q }),
    onSuccess: () => { setQ(""); qc.invalidateQueries({ queryKey: ["searches"] }); } });
  const promote = useMutation({ mutationFn: (id: number) => api.post(`/api/discover/${id}/promote`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["discover", "queue"] }) });
  return (
    <div className="max-w-3xl grid sm:grid-cols-2 gap-4">
      <section>
        <div className="text-sm text-muted mb-2">Saved searches</div>
        <div className="flex gap-2 mb-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="query"
            className="flex-1 px-2 py-1.5 border border-rule bg-transparent text-sm" />
          <button onClick={() => addSearch.mutate()} className="px-3 border border-rule text-sm">save</button>
        </div>
        <ul className="text-sm space-y-1">
          {(searches.data ?? []).map((s: any) => <li key={s.id} className="text-muted">· {s.query}</li>)}
        </ul>
      </section>
      <section>
        <div className="text-sm text-muted mb-2">Discovery inbox</div>
        <ul className="space-y-2">
          {(disc.data ?? []).map((d: any) => (
            <li key={d.id} className="border border-rule bg-[var(--surface)] p-2 text-sm">
              <div className="text-xs text-muted">@{d.author} · rel {d.relevance}</div>
              <div className="tweet">{d.text}</div>
              <button onClick={() => promote.mutate(d.id)} className="text-accent text-xs mt-1">promote →</button>
            </li>
          ))}
          {(disc.data ?? []).length === 0 && <li className="text-muted text-sm">empty</li>}
        </ul>
      </section>
      <section>
        <div className="text-sm text-muted mb-2">Notifications</div>
        <ul className="text-sm space-y-1">
          {(notifs.data ?? []).map((n: any) => (
            <li key={n.id} className="text-muted">@{n.author_handle}: <span className="text-ink">{n.text}</span></li>
          ))}
        </ul>
      </section>
      <section>
        <div className="text-sm text-muted mb-2">People</div>
        <ul className="text-sm space-y-1">
          {(people.data ?? []).map((p: any) => (
            <li key={p.handle} className="text-muted">@{p.handle} · {p.engagements} engagements</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
