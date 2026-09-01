// An X-style tweet, rendered in a box. Used in the Persona showcase, the
// TweetDeck columns and anywhere a real post needs to look like a real post.
import React from "react";
import { cx } from "./ui";

function VerifiedBadge() {
  return (
    <svg viewBox="0 0 22 22" width="16" height="16" aria-label="Verified"
      className="inline-block shrink-0" fill="var(--accent)">
      <path d="M20.396 11c-.018-.646-.215-1.275-.57-1.816-.354-.54-.852-.972-1.438-1.246.223-.607.27-1.264.14-1.897-.131-.634-.437-1.218-.882-1.687-.47-.445-1.053-.75-1.687-.882-.633-.13-1.29-.083-1.897.14-.273-.587-.704-1.086-1.245-1.44S11.647 1.62 11 1.604c-.646.017-1.273.213-1.813.568s-.969.854-1.24 1.44c-.608-.223-1.267-.272-1.902-.14-.635.13-1.22.436-1.69.882-.445.47-.749 1.055-.878 1.688-.13.633-.08 1.29.144 1.896-.587.274-1.087.705-1.443 1.245-.356.54-.555 1.17-.574 1.817.02.647.218 1.276.574 1.817.356.54.856.972 1.443 1.245-.224.606-.274 1.263-.144 1.896.13.634.433 1.218.877 1.688.47.443 1.054.747 1.688.878.633.132 1.29.084 1.897-.136.274.586.705 1.084 1.246 1.439.54.354 1.17.551 1.816.569.647-.016 1.276-.213 1.817-.567s.972-.854 1.245-1.44c.604.239 1.266.296 1.903.164.636-.132 1.22-.447 1.68-.907.46-.46.776-1.044.908-1.681s.075-1.299-.165-1.903c.586-.274 1.084-.705 1.439-1.246.354-.54.551-1.17.569-1.816zM9.662 14.85l-3.429-3.428 1.293-1.302 2.072 2.072 4.4-4.794 1.347 1.246z"/>
    </svg>
  );
}

export function TweetCard({
  handle, name, verified, text, when = "1h", replyTo,
  metrics, children, className, dense,
}: {
  handle: string; name?: string; verified?: boolean; text: string;
  when?: string; replyTo?: string;
  metrics?: { likes?: number; reposts?: number; replies?: number; views?: number };
  children?: React.ReactNode; className?: string; dense?: boolean;
}) {
  const initial = (name || handle || "?").trim().charAt(0).toUpperCase();
  return (
    <div className={cx("rounded-md border border-rule bg-surface", dense ? "p-3" : "p-3.5", className)}>
      <div className="flex gap-2.5">
        <div className="shrink-0 h-10 w-10 rounded-full grid place-items-center text-[15px] font-semibold
          text-[color:var(--accent-ink)] bg-[color:var(--accent)] select-none">
          {initial}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1 leading-tight flex-wrap">
            <span className="font-bold text-ink truncate max-w-[55%]">{name || handle}</span>
            {verified && <VerifiedBadge />}
            <span className="text-muted truncate">@{handle}</span>
            <span className="text-faint">·</span>
            <span className="text-muted">{when}</span>
          </div>
          {replyTo && (
            <div className="text-[13px] text-muted mt-0.5">
              Replying to <span className="text-accent">@{replyTo}</span>
            </div>
          )}
          <div className="tweet mt-1">{text}</div>
          <div className="flex items-center gap-6 mt-2.5 text-muted">
            <Action icon={<ReplyIcon />} n={metrics?.replies} />
            <Action icon={<RepostIcon />} n={metrics?.reposts} />
            <Action icon={<LikeIcon />} n={metrics?.likes} />
            <Action icon={<ViewsIcon />} n={metrics?.views} />
          </div>
          {children && <div className="mt-2">{children}</div>}
        </div>
      </div>
    </div>
  );
}

function Action({ icon, n }: { icon: React.ReactNode; n?: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[12.5px]">
      <span className="opacity-70">{icon}</span>
      {n != null && n > 0 && <span className="num">{fmt(n)}</span>}
    </span>
  );
}

function fmt(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
  return String(n);
}

const S = { width: 15, height: 15, fill: "none", stroke: "currentColor", strokeWidth: 1.8 } as const;
const ReplyIcon = () => (<svg viewBox="0 0 24 24" {...S}><path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.9-.9L3 21l1.9-5.6A8.38 8.38 0 0 1 4 11.5 8.5 8.5 0 0 1 12.5 3 8.38 8.38 0 0 1 21 11.5z"/></svg>);
const RepostIcon = () => (<svg viewBox="0 0 24 24" {...S}><path d="M17 1l4 4-4 4M3 11V9a4 4 0 0 1 4-4h14M7 23l-4-4 4-4m14 0v2a4 4 0 0 1-4 4H3"/></svg>);
const LikeIcon = () => (<svg viewBox="0 0 24 24" {...S}><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 1 0-7.8 7.8l1.1 1L12 21l7.7-7.6 1.1-1a5.5 5.5 0 0 0 0-7.8z"/></svg>);
const ViewsIcon = () => (<svg viewBox="0 0 24 24" {...S}><path d="M3 20V10M9 20V4M15 20v-8M21 20V8"/></svg>);
