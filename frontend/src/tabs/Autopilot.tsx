// Autopilot — the heart of the product (§19). One-handed at 380px (T-14).
// Shortcuts (U-01): J/K navigate, 1/2/3 pick candidate, E edit, Enter approve, X skip.
import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";

type View = "queue" | "shadow" | "thresholds";

export function Autopilot() {
  const [view, setView] = useState<View>("queue");
  return (
    <div>
      <div className="flex gap-1 mb-3 text-sm">
        {(["queue", "shadow", "thresholds"] as View[]).map((v) => (
          <button key={v} onClick={() => setView(v)}
            className={`px-3 py-1.5 border ${view === v ? "border-accent text-accent" : "border-rule text-muted"}`}>
            {v === "queue" ? "Queue" : v === "shadow" ? "Shadow log" : "Thresholds"}
          </button>
        ))}
      </div>
      {view === "queue" && <Queue />}
      {view === "shadow" && <ShadowLog />}
      {view === "thresholds" && <Thresholds />}
    </div>
  );
}

function Queue() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["queue"], queryFn: () => api.get("/api/queue") });
  const items: any[] = q.data ?? [];
  const [idx, setIdx] = useState(0);
  const [pick, setPick] = useState(0);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [undo, setUndo] = useState<{ id: number; timer: number } | null>(null);
  const editRef = useRef<HTMLTextAreaElement>(null);

  const cur = items[Math.min(idx, items.length - 1)];
  useEffect(() => {
    if (cur) { setText(cur.final_text); setPick(cur.chosen_index ?? 0); setEditing(false); }
  }, [cur?.id]);

  const approve = useMutation({
    mutationFn: (body: { id: number; text: string }) =>
      api.post(`/api/drafts/${body.id}/approve`, { text: body.text }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["queue"] }); setIdx((i) => i); },
  });
  const dismiss = useMutation({
    mutationFn: (id: number) => api.post(`/api/drafts/${id}/dismiss`, { reason: "skip" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["queue"] }),
  });

  function doApprove() {
    if (!cur) return;
    const id = cur.id;
    // U-02: brief undo before it reaches the bus
    if (undo) window.clearTimeout(undo.timer);
    const timer = window.setTimeout(() => {
      approve.mutate({ id, text });
      setUndo(null);
    }, 4000);
    setUndo({ id, timer });
    setIdx((i) => Math.min(i + 1, Math.max(items.length - 1, 0)));
  }
  function cancelUndo() { if (undo) { window.clearTimeout(undo.timer); setUndo(null); } }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (editing) { if (e.key === "Escape") setEditing(false); return; }
      const k = e.key.toLowerCase();
      if (k === "j") setIdx((i) => Math.min(i + 1, items.length - 1));
      else if (k === "k") setIdx((i) => Math.max(i - 1, 0));
      else if (k === "1") pickCand(0);
      else if (k === "2") pickCand(1);
      else if (k === "3") pickCand(2);
      else if (k === "e") { setEditing(true); setTimeout(() => editRef.current?.focus(), 0); }
      else if (e.key === "Enter") doApprove();
      else if (k === "x" && cur) dismiss.mutate(cur.id);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function pickCand(i: number) {
    if (!cur || !cur.candidates?.[i]) return;
    setPick(i); setText(cur.candidates[i].text);
  }

  if (items.length === 0)
    return <Empty note="Nothing worth replying to yet. Next check runs on schedule." />;

  return (
    <div>
      <div className="text-xs text-muted mb-2 font-mono">
        {idx + 1}/{items.length} · <span className="kbd">J</span>/<span className="kbd">K</span> nav ·
        <span className="kbd">1</span><span className="kbd">2</span><span className="kbd">3</span> pick ·
        <span className="kbd">E</span> edit · <span className="kbd">Enter</span> approve · <span className="kbd">X</span> skip
      </div>
      {cur && (
        <div className="border border-rule bg-[var(--surface)] p-3 sm:p-4 max-w-2xl">
          <div className="text-[13px] text-muted mb-1 font-mono">
            @{cur.parent?.author ?? cur.account} · relevance {cur.relevance}
            {cur.critic?.[pick] && (
              <> · critic {["sounds_like_operator", "adds_something", "reads_human", "low_embarrassment_risk"]
                .map((a) => cur.critic[pick]?.[a]).join("/")}</>
            )}
          </div>
          <div className="tweet mb-3">{cur.parent?.text}</div>

          <div className="border border-rule p-2 mb-2">
            {editing ? (
              <textarea ref={editRef} value={text} onChange={(e) => setText(e.target.value)}
                className="w-full bg-transparent outline-none resize-none tweet" rows={3} />
            ) : (
              <div className="tweet">{text}</div>
            )}
          </div>

          <div className="flex flex-wrap gap-2 text-xs text-muted mb-3">
            {(cur.candidates ?? []).map((c: any, i: number) => (
              <button key={i} onClick={() => pickCand(i)}
                className={`px-2 py-1 border ${pick === i ? "border-accent text-accent" : "border-rule"}`}>
                {i + 1} · {c.angle}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <button onClick={doApprove} className="px-4 py-2 bg-accent text-white flex-1 sm:flex-none">Approve</button>
            <button onClick={() => { setEditing(true); setTimeout(() => editRef.current?.focus(), 0); }}
              className="px-4 py-2 border border-rule flex-1 sm:flex-none">Edit</button>
            <button onClick={() => cur && dismiss.mutate(cur.id)}
              className="px-4 py-2 border border-rule flex-1 sm:flex-none">Skip</button>
          </div>
        </div>
      )}
      {undo && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-ink text-white px-4 py-2 text-sm flex gap-3 items-center">
          <span>sending…</span>
          <button onClick={cancelUndo} className="underline">undo</button>
        </div>
      )}
    </div>
  );
}

function ShadowLog() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["shadow"], queryFn: () => api.get("/api/shadow") });
  const items: any[] = q.data ?? [];
  const judge = useMutation({
    mutationFn: (b: { id: number; approve: boolean }) => api.post(`/api/shadow/${b.id}/judge`, { approve: b.approve }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shadow"] }),
  });
  if (items.length === 0) return <Empty note="No shadow drafts yet." />;
  return (
    <div className="space-y-3 max-w-2xl">
      {items.map((d) => (
        <div key={d.id} className="border border-rule bg-[var(--surface)] p-3">
          <div className="text-xs text-muted font-mono mb-1">
            @{d.parent?.author} · rel {d.relevance} · would have sent {d.would_have_sent_at
              ? new Date(d.would_have_sent_at).toLocaleTimeString() : "—"}
          </div>
          <div className="tweet mb-2">{d.final_text}</div>
          <div className="flex gap-2 text-xs">
            <span className="text-muted self-center">Would you have approved?</span>
            <button onClick={() => judge.mutate({ id: d.id, approve: true })}
              className="px-2 py-1 border border-go text-go">Yes</button>
            <button onClick={() => judge.mutate({ id: d.id, approve: false })}
              className="px-2 py-1 border border-risk text-risk">No</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function Thresholds() {
  return (
    <div className="max-w-md text-sm text-muted">
      <p>Relevance and confidence thresholds are governed conservatively (§3).
        Defaults: relevance 60 (auto 78), critic ≥ 4 on every axis for auto.</p>
      <p className="mt-2">Per-account mode is set on the Watchlist tab.</p>
    </div>
  );
}

function Empty({ note }: { note: string }) {
  return (
    <div className="border border-dashed border-rule p-8 text-center text-muted max-w-md">
      <div className="text-go font-semibold mb-1">All clear</div>
      <div className="text-sm">{note}</div>
    </div>
  );
}
