// True-to-X preview.
//
// Every tool in this category has one, and it is the only way to judge a draft
// the way it will actually be read: line breaks, where the 280 cut lands, how a
// thread reads as a chain. Tweet Hunter hides its high-fidelity preview behind
// a button at the bottom of the composer; here it is always on screen, beside
// the editor, updating as you type. That is the whole point of having it.
//
// This deliberately does NOT reproduce X's branding - no logo, no verified
// badge, no real avatars. It is a layout rehearsal, not an imitation, and
// nothing here is presented as a genuine post.
import { useMemo } from "react";
import { cx } from "./ui";

const LIMIT = 280;

/** X counts a URL as a fixed 23 characters however long it really is. */
const URL_WEIGHT = 23;
const URL_RE = /https?:\/\/[^\s]+/g;

export function tweetLength(text: string) {
  const urls = text.match(URL_RE) ?? [];
  const urlChars = urls.reduce((n, u) => n + u.length, 0);
  return [...text].length - urlChars + urls.length * URL_WEIGHT;
}

/** Split on a line of --- or on a blank-line gap, the way the category does. */
export function splitThread(text: string): string[] {
  const parts = text.split(/^\s*---\s*$/m);
  return parts.map((p) => p.replace(/^\n+|\n+$/g, "")).filter((p) => p.trim().length > 0);
}

/** Highlight the entities X makes blue. Everything else stays plain text. */
function renderBody(text: string) {
  const pattern = /(https?:\/\/[^\s]+|[@#][\w]+)/g;
  const out: React.ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = pattern.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(
      <span key={`${m.index}-${m[0]}`} className="text-accent">
        {m[0]}
      </span>
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function Avatar({ handle, size = 40 }: { handle: string; size?: number }) {
  const ch = handle.replace(/^@/, "").slice(0, 1).toUpperCase() || "?";
  return (
    <span
      className="grid place-items-center rounded-full bg-surface-3 text-muted font-semibold shrink-0 select-none"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
      aria-hidden="true"
    >
      {ch}
    </span>
  );
}

function ActionRow() {
  // Inert, muted, evenly spread - present for rhythm, not for interaction.
  const icons = [
    "M7.5 17.5H6a2.5 2.5 0 0 1-2.5-2.5V7A2.5 2.5 0 0 1 6 4.5h12A2.5 2.5 0 0 1 20.5 7v8a2.5 2.5 0 0 1-2.5 2.5h-4.6L9 21v-3.5Z",
    "M6 8.5h9.5A3.5 3.5 0 0 1 19 12M18 15.5H8.5A3.5 3.5 0 0 1 5 12M8.5 5.5 6 8.5l2.5 3M15.5 12.5l2.5 3-2.5 3",
    "M12 20s-7.2-4.4-7.2-9.2A4.3 4.3 0 0 1 12 8.2a4.3 4.3 0 0 1 7.2 2.6C19.2 15.6 12 20 12 20Z",
    "M4 20V10M9.3 20V4M14.7 20v-7M20 20h-16",
  ];
  return (
    <div className="flex items-center gap-10 mt-2.5 text-faint" aria-hidden="true">
      {icons.map((d, i) => (
        <svg key={i} width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d={d} />
        </svg>
      ))}
    </div>
  );
}

export function TweetCard({
  handle, text, name, time = "now", replyingTo, connector = false, index,
  count, className = "",
}: {
  handle: string;
  text: string;
  name?: string;
  time?: string;
  replyingTo?: string;
  /** Draw the thread spine below the avatar. */
  connector?: boolean;
  index?: number;
  count?: number;
  className?: string;
}) {
  const len = tweetLength(text);
  const over = len > LIMIT;
  const display = name || handle.replace(/^@/, "");

  return (
    <article className={cx("flex gap-3 px-3.5 pt-3 pb-1 relative", className)}>
      <div className="flex flex-col items-center shrink-0">
        <Avatar handle={handle} />
        {connector && <span className="w-0.5 flex-1 mt-1 rounded-full bg-rule" />}
      </div>

      <div className="min-w-0 flex-1 pb-2">
        <div className="flex items-baseline gap-1.5 flex-wrap">
          <span className="font-semibold text-[14.5px] truncate">{display}</span>
          <span className="text-[13.5px] text-muted truncate">@{handle.replace(/^@/, "")}</span>
          <span className="text-[13.5px] text-faint">- {time}</span>
          {index != null && count != null && count > 1 && (
            <span className="num ml-auto text-[11.5px] text-faint shrink-0">
              {index + 1}/{count}
            </span>
          )}
        </div>

        {replyingTo && (
          <div className="text-[13px] text-muted mt-0.5">
            Replying to <span className="text-accent">@{replyingTo.replace(/^@/, "")}</span>
          </div>
        )}

        {/* The reason this component exists: real wrapping, real line breaks. */}
        <div className="tweet mt-1 whitespace-pre-wrap break-words">
          {text.trim() ? renderBody(text) : <span className="text-faint">Nothing written yet.</span>}
        </div>

        {over && (
          <div className="mt-1.5 text-[12px] text-risk font-medium">
            {len - LIMIT} character{len - LIMIT === 1 ? "" : "s"} over - X will not accept this.
          </div>
        )}

        <ActionRow />
      </div>
    </article>
  );
}

/** A whole post or thread, rendered as it will appear. */
export function TweetPreview({
  handle, text, replyingTo, className = "",
}: { handle: string; text: string; replyingTo?: string; className?: string }) {
  const parts = useMemo(() => {
    const p = splitThread(text);
    return p.length ? p : [""];
  }, [text]);

  return (
    <div className={cx("bg-surface border border-rule rounded-md shadow-1 overflow-hidden", className)}>
      {parts.map((p, i) => (
        <div key={i} className={cx(i > 0 && "border-t border-transparent")}>
          <TweetCard
            handle={handle}
            text={p}
            time={i === 0 ? "now" : "now"}
            replyingTo={i === 0 ? replyingTo : undefined}
            connector={i < parts.length - 1}
            index={i}
            count={parts.length}
          />
        </div>
      ))}
    </div>
  );
}

/** Per-tweet counts for a thread, so the limit is legible before you post. */
export function ThreadMeter({ text }: { text: string }) {
  const parts = splitThread(text);
  if (parts.length < 2) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {parts.map((p, i) => {
        const len = tweetLength(p);
        const over = len > LIMIT;
        return (
          <span
            key={i}
            title={`Tweet ${i + 1}: ${len}/${LIMIT}`}
            className={cx(
              "num inline-flex items-center gap-1 h-[20px] px-1.5 rounded-full border text-[11px] font-medium",
              over
                ? "border-[color:var(--risk)] text-risk bg-[color:var(--risk-soft)]"
                : "border-rule text-muted bg-surface-2"
            )}
          >
            <span className="text-faint">{i + 1}</span>
            {len}
          </span>
        );
      })}
    </div>
  );
}
