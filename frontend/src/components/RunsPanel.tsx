import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Badge, Card, EmptyState, SectionTitle, Table, Td, Tr, cx } from "./ui";

/** Every sweep, and for each one every post it looked at with the reason it
 *  ended where it did. This is the answer to "why did that tweet not get a
 *  reply" without reading a log file. */
export function RunsPanel() {
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.get("/api/runs?limit=60"),
    refetchInterval: 30000,
  });
  const [open, setOpen] = useState<number | null>(null);
  const detail = useQuery({
    queryKey: ["run", open],
    queryFn: () => api.get(`/api/runs/${open}`),
    enabled: open != null,
  });

  const rows: any[] = runs.data?.runs ?? [];

  return (
    <Card className="space-y-3">
      <SectionTitle hint="each sweep, and what came of every post in it">Runs</SectionTitle>
      {rows.length === 0 ? (
        <EmptyState title="No runs yet" note="Runs appear as soon as Quill reads a feed." />
      ) : (
        <Table head={["When", "Kind", "Source", "Seen", "Scored", "Drafted", "Sent", "Skipped because"]}>
          {rows.map((r) => (
            <Tr key={r.id}>
              <Td>
                <button
                  className={cx("text-accent hover:underline", open === r.id && "font-semibold")}
                  onClick={() => setOpen(open === r.id ? null : r.id)}
                >
                  {new Date(r.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </button>
              </Td>
              <Td><Badge tone={r.kind === "foryou" ? "accent" : "neutral"}>{r.kind}</Badge></Td>
              <Td className="text-muted">{r.source}</Td>
              <Td>{r.seen}</Td>
              <Td>{r.picked}</Td>
              <Td>{r.drafted}</Td>
              <Td className={r.sent > 0 ? "text-go font-semibold" : ""}>{r.sent}</Td>
              <Td className="text-muted text-[12px]">
                {Object.entries(r.summary?.why_skipped ?? {})
                  .filter(([, v]) => (v as number) > 0)
                  .map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`)
                  .join(" · ")}
              </Td>
            </Tr>
          ))}
        </Table>
      )}

      {open != null && detail.data && (
        <div className="space-y-2">
          <div className="text-[12.5px] text-muted">
            Run {open}: {detail.data.posts.length} posts. Click a row for its journey.
          </div>
          <Table head={["Author", "Age", "Likes", "Replies", "Relevance", "Outcome", "Why"]}>
            {detail.data.posts.map((p: any) => (
              <PostRow key={p.id} p={p} />
            ))}
          </Table>
        </div>
      )}
    </Card>
  );
}

function ageOf(iso: string | null): string {
  if (!iso) return "";
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  return m < 60 ? `${m}m` : m < 1440 ? `${Math.round(m / 60)}h` : `${Math.round(m / 1440)}d`;
}

const TONE: Record<string, "go" | "warn" | "risk" | "neutral" | "info"> = {
  sent: "go", scheduled: "info", discarded: "neutral", skipped: "neutral",
  dismissed: "neutral", failed: "risk", needs_review: "warn", queued: "warn", silent: "neutral",
};

function PostRow({ p }: { p: any }) {
  const [show, setShow] = useState(false);
  const outcome = p.outcome || p.stage;
  return (
    <>
      <Tr>
        <Td>
          <button className="text-accent hover:underline" onClick={() => setShow(!show)}>
            @{p.author || "?"}
          </button>
        </Td>
        <Td className="text-muted">{ageOf(p.post_created_at)}</Td>
        <Td>{p.likes}</Td>
        <Td>{p.replies}</Td>
        <Td>{p.relevance != null ? Number(p.relevance).toFixed(0) : ""}</Td>
        <Td><Badge tone={TONE[outcome] ?? "neutral"}>{outcome}</Badge></Td>
        <Td className="text-muted text-[12px]">
          <span className="block max-w-[360px] truncate" title={p.reason}>{p.reason}</span>
        </Td>
      </Tr>
      {show && (
        <tr>
          <td colSpan={7} className="px-3 pb-3">
            <ol className="text-[12px] text-muted space-y-0.5 border-l-2 border-rule pl-3">
              {p.events.map((e: any, i: number) => (
                <li key={i}>
                  <span className="text-faint">{e.at.slice(11, 19)}</span>{" "}
                  <span className="text-ink">{e.stage}</span>
                  {e.detail && <span> · {e.detail}</span>}
                </li>
              ))}
              {p.sent_x_post_id && (
                <li>
                  <a className="text-accent hover:underline" target="_blank" rel="noreferrer"
                     href={`https://x.com/i/status/${p.sent_x_post_id}`}>open the reply</a>
                </li>
              )}
            </ol>
          </td>
        </tr>
      )}
    </>
  );
}
