// Compose. The editor is the page; generation is a side offer, never the
// default path. Nothing typed is ever lost (C-07) — the draft is autosaved.
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useToast } from "../components/Toast";
import {
  Badge, Button, Card, Input, SectionTitle, Skeleton, Textarea, cx,
} from "../components/ui";
import { IconArrowRight, IconPlus, IconSpark } from "../components/Icons";

const DRAFT_KEY = "quill.compose.draft";
const LIMIT = 280;

export function Compose() {
  const qc = useQueryClient();
  const { toast, reportError } = useToast();

  const [text, setText] = useState(() => {
    try { return localStorage.getItem(DRAFT_KEY) ?? ""; } catch { return ""; }
  });
  useEffect(() => {
    try { localStorage.setItem(DRAFT_KEY, text); } catch {}
  }, [text]);

  const [cands, setCands] = useState<any[]>([]);

  const gen = useMutation({
    mutationFn: () => api.post("/api/compose/generate", { idea: text }),
    onSuccess: (d) => {
      setCands(d.candidates ?? []);
      if (!d.candidates?.length) toast({ title: "No candidates came back", detail: "The safety gate may have refused every angle." });
    },
    onError: (e) => reportError(e, "Could not draft that"),
  });

  const restyle = useMutation({
    mutationFn: () => api.post("/api/compose/restyle", { text }),
    onSuccess: (d) => { setText(d.text); toast({ tone: "success", title: "Restyled in your voice" }); },
    onError: (e) => reportError(e, "Could not restyle that"),
  });

  const queuePost = useMutation({
    mutationFn: () => api.post("/api/schedule", { text, category: "" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedule"] });
      toast({ tone: "success", title: "Queued", detail: "It goes out at the next free slot." });
      setText("");
      setCands([]);
    },
    onError: (e) => reportError(e, "Could not queue that post"),
  });

  // "---" splits a thread; each part is counted separately against the limit.
  const parts = useMemo(
    () => text.split(/^\s*---\s*$/m).map((p) => p.trim()).filter(Boolean),
    [text]
  );
  const isThread = parts.length > 1;
  const longest = parts.reduce((m, p) => Math.max(m, p.length), 0);
  const over = isThread ? longest > LIMIT : text.length > LIMIT;
  const shown = isThread ? longest : text.length;
  const empty = text.trim().length === 0;

  return (
    <div className="grid gap-4 lg:grid-cols-3 items-start">
      <div className="lg:col-span-2 space-y-4">
        <Card pad={false} className="overflow-hidden">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={12}
            aria-label="Post text"
            placeholder="Write it. Or drop a rough idea and let Quill draft three angles.&#10;&#10;Use --- on its own line to split a thread."
            className="tweet border-0 rounded-none focus:shadow-none px-4 py-3.5 bg-transparent"
          />
          <div className="flex flex-wrap items-center gap-2 px-3 py-2.5 border-t border-rule bg-surface-2">
            <span className={cx("num text-[12.5px]", over ? "text-risk font-semibold" : "text-muted")}>
              {shown}/{LIMIT}
            </span>
            {isThread && <Badge tone="accent">thread · {parts.length}</Badge>}
            {over && <span className="text-[12px] text-risk">a part is over the limit</span>}

            <div className="flex flex-wrap gap-2 ml-auto">
              <Button size="sm" variant="default" icon={<IconSpark size={14} />}
                loading={gen.isPending} disabled={empty} onClick={() => gen.mutate()}>
                Draft three angles
              </Button>
              <Button size="sm" variant="default"
                loading={restyle.isPending} disabled={empty} onClick={() => restyle.mutate()}>
                Sound more like me
              </Button>
              <Button size="sm" variant="primary"
                loading={queuePost.isPending} disabled={empty || over} onClick={() => queuePost.mutate()}>
                Queue post
              </Button>
            </div>
          </div>
        </Card>

        {gen.isPending && (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <Card key={i} className="space-y-2"><Skeleton className="h-3 w-24" /><Skeleton className="h-4 w-full" /></Card>
            ))}
          </div>
        )}

        {cands.length > 0 && (
          <section>
            <SectionTitle hint="pick one to load it into the editor">Candidates</SectionTitle>
            <div className="space-y-2">
              {cands.map((c, i) => (
                <Card key={i} className="space-y-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge tone="neutral">{c.angle}</Badge>
                    {c.critic?.min_axis != null && (
                      <Badge tone={c.critic.min_axis >= 4 ? "go" : c.critic.min_axis >= 3 ? "warn" : "risk"}>
                        critic min {c.critic.min_axis}
                      </Badge>
                    )}
                    {c.prefilter_ok === false && <Badge tone="risk">filtered: {c.prefilter_reason}</Badge>}
                  </div>
                  <div className="tweet">{c.text}</div>
                  <Button size="sm" variant="ghost" className="-ml-2"
                    icon={<IconArrowRight size={14} />} onClick={() => setText(c.text)}>
                    Use this
                  </Button>
                </Card>
              ))}
            </div>
          </section>
        )}
      </div>

      <IdeaInbox />
    </div>
  );
}

/** Half-formed thoughts, kept out of the editor so they don't feel like drafts. */
function IdeaInbox() {
  const qc = useQueryClient();
  const { reportError } = useToast();
  const [t, setT] = useState("");
  const ideas = useQuery({ queryKey: ["ideas"], queryFn: () => api.get("/api/ideas") });

  const add = useMutation({
    mutationFn: () => api.post("/api/ideas", { text: t }),
    onSuccess: () => { setT(""); qc.invalidateQueries({ queryKey: ["ideas"] }); },
    onError: (e) => reportError(e, "Could not save that idea"),
  });
  const promote = useMutation({
    mutationFn: (id: number) => api.post(`/api/ideas/${id}/promote`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ideas"] }); qc.invalidateQueries({ queryKey: ["schedule"] }); },
    onError: (e) => reportError(e, "Could not promote that idea"),
  });

  const list: any[] = ideas.data ?? [];

  return (
    <Card className="space-y-3">
      <SectionTitle hint="nothing here is a commitment">Idea inbox</SectionTitle>
      <form
        className="flex gap-2"
        onSubmit={(e) => { e.preventDefault(); if (t.trim()) add.mutate(); }}
      >
        <Input value={t} onChange={(e) => setT(e.target.value)} placeholder="half-formed thought…" />
        <Button type="submit" variant="default" icon={<IconPlus size={14} />}
          loading={add.isPending} disabled={!t.trim()} aria-label="Add idea" />
      </form>

      {ideas.isPending ? (
        <div className="space-y-2">{[0, 1].map((i) => <Skeleton key={i} className="h-4" />)}</div>
      ) : list.length === 0 ? (
        <p className="text-[12.5px] text-muted">Empty. Drop things here as they occur to you.</p>
      ) : (
        <ul className="divide-y divide-[color:var(--rule)] -my-1">
          {list.map((i: any) => (
            <li key={i.id} className="py-2 group flex items-start gap-2">
              <span className="text-[13px] text-ink-2 flex-1">{i.text}</span>
              <button
                onClick={() => promote.mutate(i.id)}
                title="Promote to the post queue"
                className="shrink-0 text-[11.5px] text-accent opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
              >
                promote
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
