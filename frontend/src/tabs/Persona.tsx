import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../lib/api";

export function Persona() {
  const qc = useQueryClient();
  const p = useQuery({ queryKey: ["persona"], queryFn: () => api.get("/api/persona") });
  const [tweet, setTweet] = useState("");
  const [cands, setCands] = useState<any[]>([]);
  const [card, setCard] = useState("");
  const preview = useMutation({ mutationFn: () => api.post("/api/persona/preview", { tweet }),
    onSuccess: (d) => setCands(d.candidates ?? []) });
  const save = useMutation({ mutationFn: () => api.put("/api/persona", { voice_card: JSON.parse(card) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["persona"] }) });
  const importArchive = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData(); fd.append("file", file);
      return fetch("/api/persona/import", { method: "POST", body: fd,
        headers: { "X-CSRF-Token": (window as any).__csrf ?? "" }, credentials: "same-origin" }).then((r) => r.json());
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["persona"] }),
  });
  const data = p.data;
  if (data && !card) setCard(JSON.stringify(data.voice_card, null, 2));
  return (
    <div className="max-w-3xl grid sm:grid-cols-2 gap-4">
      <section>
        <div className="text-sm text-muted mb-2">Voice card · corpus {data?.corpus_size ?? 0} samples</div>
        <textarea value={card} onChange={(e) => setCard(e.target.value)} rows={16}
          className="w-full font-mono text-xs p-2 border border-rule bg-[var(--surface)]" />
        <div className="flex gap-2 mt-2">
          <button onClick={() => save.mutate()} className="px-3 py-1.5 bg-accent text-white text-sm">save voice card</button>
          <label className="px-3 py-1.5 border border-rule text-sm cursor-pointer">
            import archive
            <input type="file" className="hidden" onChange={(e) => e.target.files?.[0] && importArchive.mutate(e.target.files[0])} />
          </label>
        </div>
        {data?.learning && (
          <div className="mt-3 text-xs text-muted">
            fine-tune data: {data.learning.dpo_pairs} DPO pairs · {data.learning.sft_examples} SFT ·
            {data.learning.enough_to_train ? " enough to bother" : " keep collecting"}
          </div>
        )}
      </section>
      <section>
        <div className="text-sm text-muted mb-2">Playground (P-08)</div>
        <textarea value={tweet} onChange={(e) => setTweet(e.target.value)} rows={3}
          placeholder="paste any tweet…" className="w-full p-2 border border-rule bg-[var(--surface)] tweet" />
        <button onClick={() => preview.mutate()} className="mt-2 px-3 py-1.5 border border-rule text-sm">generate 3</button>
        <div className="mt-2 space-y-2">
          {cands.map((c, i) => (
            <div key={i} className="border border-rule bg-[var(--surface)] p-2">
              <div className="text-xs text-muted">{c.angle}
                {c.critic?.min_axis != null && ` · critic ${["sounds_like_operator","adds_something","reads_human","low_embarrassment_risk"].map((a)=>c.critic[a]).join("/")}`}
                {!c.prefilter_ok && <span className="text-risk"> · {c.prefilter_reason}</span>}</div>
              <div className="tweet">{c.text}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
