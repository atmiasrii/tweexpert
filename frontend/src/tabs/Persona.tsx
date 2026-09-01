// Persona. The voice card is structured data the operator edits by hand, so the
// editor validates as you type and refuses to submit something the backend would
// reject. The playground sits beside it: change the card, see what changes.
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getCsrf } from "../lib/api";
import { useToast } from "../components/Toast";
import {
  Badge, Button, Card, ErrorState, SectionTitle, Skeleton, Textarea, cx,
} from "../components/ui";
import { IconSpark, IconUpload } from "../components/Icons";

const AXES = [
  ["sounds_like_operator", "voice"],
  ["adds_something", "adds"],
  ["reads_human", "human"],
  ["low_embarrassment_risk", "safe"],
] as const;

export function Persona() {
  const qc = useQueryClient();
  const { toast, reportError } = useToast();
  const p = useQuery({ queryKey: ["persona"], queryFn: () => api.get("/api/persona") });

  const [card, setCard] = useState("");
  const [dirty, setDirty] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Load the server copy once, and again whenever it changes underneath us —
  // but never over unsaved edits.
  useEffect(() => {
    if (!p.data || dirty) return;
    setCard(JSON.stringify(p.data.voice_card ?? {}, null, 2));
  }, [p.data, dirty]);

  const parseError = useMemo(() => {
    if (!card.trim()) return "The voice card cannot be empty.";
    try {
      const v = JSON.parse(card);
      if (v === null || typeof v !== "object" || Array.isArray(v)) return "The voice card must be a JSON object.";
      return null;
    } catch (e: any) {
      return String(e?.message ?? "Invalid JSON");
    }
  }, [card]);

  const save = useMutation({
    mutationFn: () => api.put("/api/persona", { voice_card: JSON.parse(card) }),
    onSuccess: () => {
      setDirty(false);
      qc.invalidateQueries({ queryKey: ["persona"] });
      toast({ tone: "success", title: "Voice card saved" });
    },
    onError: (e) => reportError(e, "Could not save the voice card"),
  });

  const importArchive = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch("/api/persona/import", {
        method: "POST",
        body: fd,
        headers: { "X-CSRF-Token": getCsrf() },
        credentials: "same-origin",
      });
      if (!r.ok) throw new Error((await r.text()) || r.statusText);
      return r.json();
    },
    onSuccess: (d: any) => {
      qc.invalidateQueries({ queryKey: ["persona"] });
      toast({
        tone: "success",
        title: "Archive imported",
        detail: d?.imported != null ? `${d.imported} posts added to the corpus.` : undefined,
      });
    },
    onError: (e) => reportError(e, "Could not import that archive"),
  });

  if (p.isError) return <ErrorState error={p.error} onRetry={p.refetch} />;
  const data = p.data;

  return (
    <div className="grid gap-4 lg:grid-cols-2 items-start">
      <Card className="space-y-3">
        <SectionTitle
          hint={data ? `corpus ${data.corpus_size ?? 0} samples` : undefined}
          action={dirty ? <Badge tone="warn">unsaved</Badge> : undefined}
        >
          Voice card
        </SectionTitle>

        {p.isPending ? (
          <Skeleton className="h-64" />
        ) : (
          <>
            <Textarea
              value={card}
              onChange={(e) => { setCard(e.target.value); setDirty(true); }}
              rows={18}
              spellCheck={false}
              aria-label="Voice card JSON"
              className={cx("mono !text-[12px] leading-relaxed",
                parseError && dirty && "border-[color:var(--risk)]")}
            />
            {parseError && dirty && (
              <div className="text-[12px] text-risk">{parseError}</div>
            )}

            <div className="flex flex-wrap gap-2">
              <Button variant="primary" loading={save.isPending}
                disabled={!!parseError || !dirty} onClick={() => save.mutate()}>
                Save voice card
              </Button>
              {dirty && (
                <Button variant="ghost" onClick={() => {
                  setDirty(false);
                  setCard(JSON.stringify(p.data?.voice_card ?? {}, null, 2));
                }}>
                  Revert
                </Button>
              )}
              <Button variant="default" icon={<IconUpload size={14} />}
                loading={importArchive.isPending}
                onClick={() => fileRef.current?.click()}>
                Import archive
              </Button>
              <input
                ref={fileRef} type="file" className="hidden" accept=".json,.zip,.js"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) importArchive.mutate(f);
                  e.target.value = "";
                }}
              />
            </div>
          </>
        )}

        {data?.learning && (
          <div className="pt-3 mt-1 border-t border-rule">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[12.5px] text-muted">fine-tune data</span>
              <Badge tone="neutral">{data.learning.dpo_pairs} DPO pairs</Badge>
              <Badge tone="neutral">{data.learning.sft_examples} SFT</Badge>
              <Badge tone={data.learning.enough_to_train ? "go" : "neutral"}>
                {data.learning.enough_to_train ? "enough to train" : "keep collecting"}
              </Badge>
            </div>
            <p className="text-[12px] text-faint mt-1.5">
              Every approval, edit and dismissal is a training signal. Export from Ops when there's enough.
            </p>
          </div>
        )}
      </Card>

      <Playground />
    </div>
  );
}

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
      <Textarea
        value={tweet}
        onChange={(e) => setTweet(e.target.value)}
        rows={3}
        placeholder="Paste any tweet and see how Quill would answer it…"
        className="tweet"
        aria-label="Tweet to reply to"
      />
      <Button variant="default" icon={<IconSpark size={14} />}
        loading={preview.isPending} disabled={!tweet.trim()} onClick={() => preview.mutate()}>
        Generate three
      </Button>

      {preview.isPending && (
        <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>
      )}

      {cands.length > 0 && (
        <div className="space-y-2">
          {cands.map((c, i) => (
            <div key={i} className="rounded-sm border border-rule p-3 space-y-2">
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge tone="neutral">{c.angle}</Badge>
                {c.prefilter_ok === false && <Badge tone="risk">{c.prefilter_reason}</Badge>}
              </div>
              <div className="tweet">{c.text}</div>
              {c.critic && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {AXES.map(([key, label]) => {
                    const v = c.critic[key];
                    const tone = v == null ? "neutral" : v >= 4 ? "go" : v >= 3 ? "warn" : "risk";
                    return <Badge key={key} tone={tone as any}>{label} {v ?? "—"}</Badge>;
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {!preview.isPending && cands.length === 0 && (
        <p className="text-[12.5px] text-muted">
          Use this after editing the voice card — it is the fastest way to tell whether a change helped.
        </p>
      )}
    </Card>
  );
}
