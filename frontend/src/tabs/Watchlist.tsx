// Watchlist. The autonomy mode lives here, so this table has to make the shadow
// gate legible: an account cannot reach auto until the shadow period is served
// (Y-03), and the UI says why rather than just disabling the option.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useToast } from "../components/Toast";
import {
  Badge, Button, Card, EmptyState, ErrorState, Input, SectionTitle, Select,
  Skeleton, Table, Td, Tr, cx,
} from "../components/ui";
import { IconPlus, IconWatchlist, IconX } from "../components/Icons";

const MODES = ["shadow", "assisted", "auto"] as const;

export function Watchlist() {
  const qc = useQueryClient();
  const { toast, reportError, confirm } = useToast();
  const accts = useQuery({ queryKey: ["accounts"], queryFn: () => api.get("/api/accounts") });

  const [handle, setHandle] = useState("");
  const [tier, setTier] = useState("B");

  const add = useMutation({
    mutationFn: () => api.post("/api/accounts", { handle: handle.replace(/^@/, "").trim(), tier }),
    onSuccess: () => {
      setHandle("");
      qc.invalidateQueries({ queryKey: ["accounts"] });
      toast({ tone: "success", title: "Watching", detail: "It starts in shadow — Quill drafts but never sends." });
    },
    onError: (e) => reportError(e, "Could not watch that account"),
  });

  const setMode = useMutation({
    mutationFn: (b: { id: number; mode: string }) => api.post(`/api/accounts/${b.id}/mode`, { mode: b.mode }),
    onSuccess: (_d, b) => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      toast({ tone: b.mode === "auto" ? "error" : "success", title: `Mode set to ${b.mode}` });
    },
    // A refusal is the governor enforcing the shadow gate — show its reason.
    onError: (e) => reportError(e, "Mode change refused"),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/api/accounts/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["accounts"] }); toast({ title: "Stopped watching" }); },
    onError: (e) => reportError(e, "Could not remove that account"),
  });

  async function changeMode(a: any, mode: string) {
    if (mode === a.mode) return;
    if (mode === "auto") {
      const ok = await confirm({
        title: `Let @${a.handle} reply on its own?`,
        danger: true,
        confirmLabel: "Enable auto",
        body: (
          <>
            Quill will publish replies to this account with no human in the loop, capped at
            four a day and disabled automatically on trouble. You will see them after they
            are already public.
          </>
        ),
      });
      if (!ok) return;
    }
    setMode.mutate({ id: a.id, mode });
  }

  async function drop(a: any) {
    const ok = await confirm({
      title: `Stop watching @${a.handle}?`,
      danger: true,
      confirmLabel: "Stop watching",
      body: "Drafts already queued for this account stay in the queue.",
    });
    if (ok) remove.mutate(a.id);
  }

  if (accts.isError) return <ErrorState error={accts.error} onRetry={accts.refetch} />;
  const list: any[] = accts.data ?? [];

  return (
    <div className="space-y-4 max-w-[900px]">
      <Card>
        <SectionTitle hint="tier A is read most often">Watch an account</SectionTitle>
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => { e.preventDefault(); if (handle.trim()) add.mutate(); }}
        >
          <div className="relative flex-1 min-w-[180px]">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint text-[13px] pointer-events-none">@</span>
            <Input value={handle} onChange={(e) => setHandle(e.target.value)}
              placeholder="handle" className="pl-6" aria-label="Handle" />
          </div>
          <Select value={tier} onChange={(e) => setTier(e.target.value)} aria-label="Tier" className="w-auto">
            <option value="A">Tier A</option>
            <option value="B">Tier B</option>
            <option value="C">Tier C</option>
          </Select>
          <Button type="submit" variant="primary" icon={<IconPlus size={14} />}
            loading={add.isPending} disabled={!handle.trim()}>
            Watch
          </Button>
        </form>
      </Card>

      {accts.isPending ? (
        <Skeleton className="h-40" />
      ) : list.length === 0 ? (
        <EmptyState
          icon={<IconWatchlist size={24} />}
          title="Nothing watched yet"
          note="Quill reads only the accounts you list here. Add a few people whose posts you would actually reply to."
        />
      ) : (
        <Table head={["Account", "Tier", "Mode", "Shadow progress", "Drafts", ""]}>
          {list.map((a) => (
            <Tr key={a.id}>
              <Td><span className="font-medium">@{a.handle}</span>
                {a.display_name && <span className="block text-[12px] text-faint">{a.display_name}</span>}
              </Td>
              <Td><Badge tone={a.tier === "A" ? "accent" : "neutral"}>{a.tier}</Badge></Td>
              <Td>
                <Select
                  value={a.mode}
                  onChange={(e) => changeMode(a, e.target.value)}
                  aria-label={`Mode for @${a.handle}`}
                  className="h-8 w-[118px] text-[12.5px]"
                >
                  {MODES.map((m) => (
                    <option key={m} value={m} disabled={m === "auto" && !a.shadow_complete}>
                      {m}{m === "auto" && !a.shadow_complete ? " (locked)" : ""}
                    </option>
                  ))}
                </Select>
              </Td>
              <Td><ShadowProgress a={a} /></Td>
              <Td><span className="num text-muted">{a.draft_count ?? 0}</span></Td>
              <Td className="text-right">
                <button onClick={() => drop(a)} aria-label={`Stop watching @${a.handle}`}
                  className="h-7 w-7 grid place-items-center rounded-sm text-faint
                    hover:text-risk hover:bg-[color:var(--risk-soft)] transition-colors">
                  <IconX size={14} />
                </button>
              </Td>
            </Tr>
          ))}
        </Table>
      )}

      <p className="text-[12.5px] text-muted max-w-prose">
        Every account starts in <b className="text-ink-2">shadow</b>: Quill drafts, never sends, and you
        grade the drafts in the shadow log. Auto unlocks only once that period is served — the lock is
        enforced in the backend, not just here.
      </p>
    </div>
  );
}

function ShadowProgress({ a }: { a: any }) {
  if (a.shadow_complete) return <Badge tone="go">served</Badge>;

  const reviewed = a.shadow_reviewed_count ?? 0;
  const need = 20;
  const pct = Math.min(100, (reviewed / need) * 100);
  const started = a.shadow_started_at ? new Date(a.shadow_started_at) : null;
  const days = started ? Math.floor((Date.now() - started.getTime()) / 86_400_000) : 0;

  return (
    <div className="w-[140px]">
      <div className="flex justify-between text-[11.5px] text-muted num">
        <span>{reviewed}/{need} graded</span>
        <span>{days}/7 d</span>
      </div>
      <div className="h-1 mt-1 rounded-full bg-surface-3 overflow-hidden">
        <div className={cx("h-full rounded-full", pct >= 100 ? "bg-[color:var(--go)]" : "bg-[color:var(--accent)]")}
          style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
