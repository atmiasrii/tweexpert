// Persona. The star is the skill mixer + a live showcase: move the dials, hit
// Apply, and watch Quill answer ten real-shaped posts in the new voice. The
// voice-card JSON and the free playground sit below for fine control.
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getCsrf } from "../lib/api";
import { useToast } from "../components/Toast";
import {
  Badge, Button, Card, ErrorState, SectionTitle, Skeleton, Textarea, cx,
} from "../components/ui";
import { IconSpark, IconUpload } from "../components/Icons";
import { TweetCard } from "../components/TweetCard";

const AXES = [
  ["sounds_like_operator", "voice"],
  ["adds_something", "adds"],
  ["reads_human", "human"],
  ["low_embarrassment_risk", "safe"],
] as const;

export function Persona() {
  const p = useQuery({ queryKey: ["persona"], queryFn: () => api.get("/api/persona") });
  if (p.isError) return <ErrorState error={p.error} onRetry={p.refetch} />;

  return (
    <div className="space-y-4 max-w-[1100px]">
      <SkillsShowcase persona={p.data} loading={p.isPending} />
      <div className="grid gap-4 lg:grid-cols-2 items-start">
        <VoiceCard persona={p.data} loading={p.isPending} refetch={p.refetch} />
        <Playground />
      </div>
    </div>
  );
}

/* ── skills + live showcase ─────────────────────────────────── */
function SkillsShowcase({ persona, loading }: { persona: any; loading: boolean }) {
  const qc = useQueryClient();
  const { toast, reportError } = useToast();
  const [skills, setSkills] = useState<Record<string, number>>({});
  const [dirty, setDirty] = useState(false);
  const [cards, setCards] = useState<any[]>([]);

  useEffect(() => {
    if (persona?.skills && !dirty) setSkills(persona.skills);
  }, [persona?.skills, dirty]);

  const labels: Record<string, string> = persona?.skill_labels ?? {};

  const applyAndGen = useMutation({
    mutationFn: async () => {
      await api.put("/api/persona/skills", { skills });
      return api.post("/api/persona/examples/generate");
    },
    onSuccess: (d) => {
      setCards(d.examples ?? []);
      setDirty(false);
      qc.invalidateQueries({ queryKey: ["persona"] });
      toast({ tone: "success", title: "Persona applied", detail: "Ten fresh replies below." });
    },
    onError: (e) => reportError(e, "Could not generate the showcase"),
  });

  const keys = Object.keys(labels).length ? Object.keys(labels) : Object.keys(skills);

  return (
    <Card className="space-y-4">
      <SectionTitle
        hint="tune the voice, then see it answer ten real posts"
        action={dirty ? <Badge tone="warn">unsaved</Badge> : undefined}
      >
        Persona mixer
      </SectionTitle>

      {loading ? (
        <Skeleton className="h-24" />
      ) : (
        <>
          <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
            {keys.map((k) => (
              <Slider
                key={k} label={labels[k] ?? k} value={skills[k] ?? 50}
                onChange={(v) => { setSkills((s) => ({ ...s, [k]: v })); setDirty(true); }}
              />
            ))}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="primary" icon={<IconSpark size={14} />}
              loading={applyAndGen.isPending} onClick={() => applyAndGen.mutate()}>
              Apply &amp; generate 10
            </Button>
            <span className="text-[12px] text-faint">
              Uses the local model — a few seconds per card.
            </span>
          </div>
        </>
      )}

      {applyAndGen.isPending && (
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-40" />)}
        </div>
      )}

      {cards.length > 0 && !applyAndGen.isPending && (
        <div className="grid gap-3 md:grid-cols-2">
          {cards.map((c, i) => (
            <div key={i} className="space-y-2">
              <TweetCard handle={c.handle} name={c.name} verified={c.verified}
                text={c.text} when="2h" dense />
              <div className="ml-6 pl-4 border-l-2 border-[color:var(--accent)]">
                <TweetCard handle={persona?.operator ?? "you"} name="You" text={c.reply}
                  when="now" replyTo={c.handle} dense
                  className="!border-[color:var(--accent-soft)] bg-[color:var(--accent-soft)]/40" />
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function Slider({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <label className="block">
      <div className="flex justify-between items-baseline mb-1">
        <span className="text-[13px] font-medium text-ink">{label}</span>
        <span className="num text-[12px] text-muted">{value}</span>
      </div>
      <input
        type="range" min={0} max={100} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[color:var(--accent)] cursor-pointer"
        aria-label={label}
      />
    </label>
  );
}

/* ── voice card ─────────────────────────────────────────────── */
function VoiceCard({ persona, loading, refetch }: { persona: any; loading: boolean; refetch: () => void }) {
  const qc = useQueryClient();
  const { toast, reportError } = useToast();
  const [card, setCard] = useState("");
  const [dirty, setDirty] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (persona?.voice_card && !dirty) setCard(JSON.stringify(persona.voice_card, null, 2));
  }, [persona?.voice_card, dirty]);

  const parseError = useMemo(() => {
    if (!card.trim()) return "The voice card cannot be empty.";
    try {
      const v = JSON.parse(card);
      if (v === null || typeof v !== "object" || Array.isArray(v)) return "Must be a JSON object.";
      return null;
    } catch (e: any) { return String(e?.message ?? "Invalid JSON"); }
  }, [card]);

  const save = useMutation({
    mutationFn: () => api.put("/api/persona", { voice_card: JSON.parse(card) }),
    onSuccess: () => { setDirty(false); qc.invalidateQueries({ queryKey: ["persona"] }); toast({ tone: "success", title: "Voice card saved" }); },
    onError: (e) => reportError(e, "Could not save the voice card"),
  });
  const importArchive = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData(); fd.append("file", file);
      const r = await fetch("/api/persona/import", { method: "POST", body: fd, headers: { "X-CSRF-Token": getCsrf() }, credentials: "same-origin" });
      if (!r.ok) throw new Error((await r.text()) || r.statusText);
      return r.json();
    },
    onSuccess: (d: any) => { qc.invalidateQueries({ queryKey: ["persona"] }); toast({ tone: "success", title: "Archive imported", detail: d?.imported != null ? `${d.imported} posts added.` : undefined }); },
    onError: (e) => reportError(e, "Could not import that archive"),
  });

  return (
    <Card className="space-y-3">
      <SectionTitle hint={persona ? `corpus ${persona.corpus_size ?? 0} samples` : undefined}
        action={dirty ? <Badge tone="warn">unsaved</Badge> : undefined}>
        Voice card
      </SectionTitle>
      {loading ? <Skeleton className="h-56" /> : (
        <>
          <Textarea value={card} onChange={(e) => { setCard(e.target.value); setDirty(true); }}
            rows={14} spellCheck={false} aria-label="Voice card JSON"
            className={cx("mono !text-[12px] leading-relaxed", parseError && dirty && "border-[color:var(--risk)]")} />
          {parseError && dirty && <div className="text-[12px] text-risk">{parseError}</div>}
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" loading={save.isPending} disabled={!!parseError || !dirty} onClick={() => save.mutate()}>Save voice card</Button>
            {dirty && <Button variant="ghost" onClick={() => { setDirty(false); setCard(JSON.stringify(persona?.voice_card ?? {}, null, 2)); }}>Revert</Button>}
            <Button variant="default" icon={<IconUpload size={14} />} loading={importArchive.isPending} onClick={() => fileRef.current?.click()}>Import archive</Button>
            <input ref={fileRef} type="file" className="hidden" accept=".json,.zip,.js"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) importArchive.mutate(f); e.target.value = ""; }} />
          </div>
        </>
      )}
      {persona?.learning && (
        <div className="pt-3 mt-1 border-t border-rule flex flex-wrap items-center gap-2">
          <span className="text-[12.5px] text-muted">fine-tune data</span>
          <Badge tone="neutral">{persona.learning.dpo_pairs} DPO</Badge>
          <Badge tone="neutral">{persona.learning.sft_examples} SFT</Badge>
          <Badge tone={persona.learning.enough_to_train ? "go" : "neutral"}>
            {persona.learning.enough_to_train ? "enough to train" : "keep collecting"}
          </Badge>
        </div>
      )}
    </Card>
  );
}

/* ── playground ─────────────────────────────────────────────── */
function Playground() {
  const { reportError } = useToast();
  const [tweet, setTweet] = useState("");
  const [cands, setCands] = useState<any[]>([]);
  const preview = useMutation({
    mutationFn: () => api.post("/api/persona/preview", { tweet }),
    onSuccess: (d) => setCands(d.candidates ?? []),
    onError: (e) => reportError(e, "Could not generate a preview"),
  });
  return (
    <Card className="space-y-3">
      <SectionTitle hint="nothing here is ever sent">Playground</SectionTitle>
      <Textarea value={tweet} onChange={(e) => setTweet(e.target.value)} rows={3}
        placeholder="Paste any tweet and see how Quill would answer it…" className="tweet" aria-label="Tweet to reply to" />
      <Button variant="default" icon={<IconSpark size={14} />} loading={preview.isPending}
        disabled={!tweet.trim()} onClick={() => preview.mutate()}>Generate three</Button>
      {preview.isPending && <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>}
      {cands.length > 0 && (
        <div className="space-y-2">
          {cands.map((c, i) => (
            <div key={i} className="rounded-sm border border-rule p-3 space-y-2">
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge tone="neutral">{c.angle}</Badge>
                {c.prefilter_ok === false && <Badge tone="risk">{c.prefilter_reason}</Badge>}
                {c.critic && AXES.map(([k, short]) => (
                  <Badge key={k} tone={(c.critic[k] ?? 0) >= 4 ? "go" : (c.critic[k] ?? 0) >= 3 ? "neutral" : "risk"}>
                    {short} {c.critic[k] ?? "—"}
                  </Badge>
                ))}
              </div>
              <div className="tweet">{c.text}</div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
