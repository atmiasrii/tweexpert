import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../lib/api";

const DRAFT_KEY = "quill.compose.draft";

export function Compose() {
  // C-07 autosave: nothing typed is ever lost (persists across reloads).
  const [text, setText] = useState(() => {
    try { return localStorage.getItem(DRAFT_KEY) ?? ""; } catch { return ""; }
  });
  useEffect(() => {
    try { localStorage.setItem(DRAFT_KEY, text); } catch {}
  }, [text]);
  const [cands, setCands] = useState<any[]>([]);
  const gen = useMutation({
    mutationFn: () => api.post("/api/compose/generate", { idea: text }),
    onSuccess: (d) => setCands(d.candidates ?? []),
  });
  const restyle = useMutation({
    mutationFn: () => api.post("/api/compose/restyle", { text }),
    onSuccess: (d) => setText(d.text),
  });
  const queuePost = useMutation({
    mutationFn: () => api.post("/api/schedule", { text, category: "" }),
  });
  const count = text.length;
  const isThread = text.includes("---");
  return (
    <div className="max-w-2xl space-y-3">
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5}
        placeholder="write, or drop a rough idea… use --- to split a thread"
        className="w-full p-3 border border-rule bg-[var(--surface)] tweet resize-none" />
      <div className="flex flex-wrap gap-2 items-center text-sm">
        <span className={`font-mono ${count > 280 ? "text-risk" : "text-muted"}`}>{count}/280{isThread ? " · thread" : ""}</span>
        <button onClick={() => gen.mutate()} className="px-3 py-1.5 border border-rule">Draft this for me</button>
        <button onClick={() => restyle.mutate()} className="px-3 py-1.5 border border-rule">Sound more like me</button>
        <button onClick={() => queuePost.mutate()} className="px-3 py-1.5 bg-accent text-white">Queue post</button>
      </div>
      {cands.length > 0 && (
        <div className="space-y-2">
          {cands.map((c, i) => (
            <div key={i} className="border border-rule bg-[var(--surface)] p-3">
              <div className="text-xs text-muted mb-1">{c.angle}{c.critic?.min_axis ? ` · critic min ${c.critic.min_axis}` : ""}
                {!c.prefilter_ok && <span className="text-risk"> · filtered: {c.prefilter_reason}</span>}</div>
              <div className="tweet">{c.text}</div>
              <button onClick={() => setText(c.text)} className="mt-2 text-accent text-xs">use this</button>
            </div>
          ))}
        </div>
      )}
      <IdeaInbox />
    </div>
  );
}

import { useQuery, useQueryClient } from "@tanstack/react-query";
function IdeaInbox() {
  const qc = useQueryClient();
  const [t, setT] = useState("");
  const ideas = useQuery({ queryKey: ["ideas"], queryFn: () => api.get("/api/ideas") });
  const add = useMutation({ mutationFn: () => api.post("/api/ideas", { text: t }),
    onSuccess: () => { setT(""); qc.invalidateQueries({ queryKey: ["ideas"] }); } });
  return (
    <section className="border-t border-rule pt-3">
      <div className="text-sm text-muted mb-2">Idea inbox</div>
      <div className="flex gap-2">
        <input value={t} onChange={(e) => setT(e.target.value)} placeholder="half-formed thought…"
          className="flex-1 px-2 py-1.5 border border-rule bg-transparent text-sm" />
        <button onClick={() => add.mutate()} className="px-3 border border-rule text-sm">add</button>
      </div>
      <ul className="mt-2 space-y-1 text-sm">
        {(ideas.data ?? []).map((i: any) => <li key={i.id} className="text-muted">· {i.text}</li>)}
      </ul>
    </section>
  );
}
