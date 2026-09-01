// Shared primitives. Every surface in Quill is built from these so spacing,
// radius, focus and colour stay identical across the nine tabs.
import React from "react";
import { Spinner } from "./Icons";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

/* ── Card ─────────────────────────────────────────────────── */
export function Card({
  children, className = "", pad = true, ...rest
}: React.HTMLAttributes<HTMLDivElement> & { pad?: boolean }) {
  return (
    <div
      {...rest}
      className={cx(
        "bg-surface border border-rule rounded-md shadow-1",
        pad && "p-4",
        className
      )}
    >
      {children}
    </div>
  );
}

export function SectionTitle({
  children, hint, action,
}: { children: React.ReactNode; hint?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-2 mb-3">
      <h2 className="text-[14.5px] font-semibold text-ink tracking-[-0.01em]">
        {children}
      </h2>
      {hint && <span className="text-[12.5px] text-muted">{hint}</span>}
      {action && <div className="ml-auto">{action}</div>}
    </div>
  );
}

/* ── Button ───────────────────────────────────────────────── */
type BtnVariant = "primary" | "default" | "ghost" | "danger" | "success";
type BtnSize = "sm" | "md" | "lg";

const BTN_BASE =
  "inline-flex items-center justify-center gap-1.5 font-medium rounded-sm border " +
  "transition-[background-color,border-color,color,box-shadow,transform] duration-100 " +
  "select-none whitespace-nowrap active:translate-y-px " +
  "disabled:opacity-50 disabled:cursor-not-allowed disabled:active:translate-y-0";

const BTN_VARIANT: Record<BtnVariant, string> = {
  primary:
    "bg-accent border-accent text-[color:var(--accent-ink)] hover:bg-accent-hover hover:border-accent-hover shadow-1",
  default:
    "bg-surface border-rule-strong text-ink hover:bg-surface-2 hover:border-muted",
  ghost:
    "bg-transparent border-transparent text-muted hover:bg-surface-2 hover:text-ink",
  danger:
    "bg-transparent border-[color:var(--risk)] text-risk hover:bg-[color:var(--risk-soft)]",
  success:
    "bg-transparent border-[color:var(--go)] text-go hover:bg-[color:var(--go-soft)]",
};

const BTN_SIZE: Record<BtnSize, string> = {
  sm: "h-7 px-2.5 text-[12.5px]",
  md: "h-9 px-3.5 text-[13.5px]",
  lg: "h-11 px-5 text-[15px]",
};

export function Button({
  variant = "default", size = "md", loading = false, icon, className = "",
  children, disabled, ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: BtnVariant; size?: BtnSize; loading?: boolean; icon?: React.ReactNode;
}) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cx(BTN_BASE, BTN_VARIANT[variant], BTN_SIZE[size], className)}
    >
      {loading ? <Spinner size={14} /> : icon}
      {children}
    </button>
  );
}

/** Square icon-only button; needs an aria-label from the caller. */
export function IconButton({
  variant = "ghost", size = "md", className = "", children, ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; size?: BtnSize }) {
  const box = size === "sm" ? "h-7 w-7" : size === "lg" ? "h-11 w-11" : "h-9 w-9";
  return (
    <button {...rest} className={cx(BTN_BASE, BTN_VARIANT[variant], box, "p-0", className)}>
      {children}
    </button>
  );
}

/* ── Badge / status ───────────────────────────────────────── */
type Tone = "neutral" | "accent" | "go" | "risk" | "warn";

const TONE_BG: Record<Tone, string> = {
  neutral: "bg-surface-2 text-muted border-rule",
  accent: "bg-[color:var(--accent-soft)] text-accent border-transparent",
  go: "bg-[color:var(--go-soft)] text-go border-transparent",
  risk: "bg-[color:var(--risk-soft)] text-risk border-transparent",
  warn: "bg-[color:var(--warn-soft)] text-warn border-transparent",
};

export function Badge({
  tone = "neutral", className = "", children,
}: { tone?: Tone; className?: string; children: React.ReactNode }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 h-[20px] px-2 rounded-full border",
        "text-[11px] font-semibold tracking-wide uppercase",
        TONE_BG[tone], className
      )}
    >
      {children}
    </span>
  );
}

const DOT_TONE: Record<Tone, string> = {
  neutral: "bg-[color:var(--muted)]",
  accent: "bg-[color:var(--accent)]",
  go: "bg-[color:var(--go)]",
  risk: "bg-[color:var(--risk)]",
  warn: "bg-[color:var(--warn)]",
};

/** Status dot + label. The dot carries no meaning alone — the label always says it. */
export function StatusDot({
  ok, label, unknown = false,
}: { ok?: boolean; label: string; unknown?: boolean }) {
  const tone: Tone = unknown ? "neutral" : ok ? "go" : "risk";
  return (
    <span className="inline-flex items-center gap-1.5 text-[12.5px] text-muted whitespace-nowrap shrink-0">
      <span className={cx("h-1.5 w-1.5 rounded-full shrink-0", DOT_TONE[tone])} />
      {label}
    </span>
  );
}

/* ── Meter ────────────────────────────────────────────────── */
export function Meter({
  label, used, cap, hint,
}: { label: string; used: number; cap: number; hint?: string }) {
  const pct = cap > 0 ? Math.min(100, (used / cap) * 100) : 0;
  // Caps are a safety device: the bar warns before it is hit, not after.
  const tone = pct >= 100 ? "risk" : pct >= 75 ? "warn" : "accent";
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[12.5px] text-muted truncate">{label}</span>
        <span className="text-[12.5px] num tabular-nums text-ink-2 font-medium">
          {used}<span className="text-faint">/{cap}</span>
        </span>
      </div>
      <div className="h-1.5 mt-1.5 rounded-full bg-surface-3 overflow-hidden">
        <div
          className={cx("h-full rounded-full transition-[width] duration-300 ease-out", DOT_TONE[tone])}
          style={{ width: `${pct}%` }}
        />
      </div>
      {hint && <div className="text-[11px] text-faint mt-1">{hint}</div>}
    </div>
  );
}

/* ── Loading / empty / error ──────────────────────────────── */
/* ── StatCard ─────────────────────────────────────────────────
   The at-a-glance number. One per thing that matters; big enough to read
   from across the desk, with a plain-English label under it. */
export function StatCard({
  label, value, sub, tone = "neutral", onClick, icon, loading,
}: {
  label: string; value: React.ReactNode; sub?: React.ReactNode;
  tone?: "neutral" | "accent" | "go" | "warn" | "risk";
  onClick?: () => void; icon?: React.ReactNode; loading?: boolean;
}) {
  const toneCls: Record<string, string> = {
    neutral: "text-ink",
    accent: "text-accent",
    go: "text-go",
    warn: "text-warn",
    risk: "text-risk",
  };
  const Wrap: any = onClick ? "button" : "div";
  return (
    <Wrap
      onClick={onClick}
      className={cx(
        "bg-surface border border-rule rounded-md shadow-1 p-4 text-left w-full",
        onClick && "hover:border-muted transition-colors cursor-pointer"
      )}
    >
      <div className="flex items-center gap-1.5 text-[12.5px] text-muted">
        {icon}<span>{label}</span>
      </div>
      {loading ? (
        <div className="skeleton h-8 w-16 mt-1.5" />
      ) : (
        <div className={cx("num text-[28px] leading-tight font-semibold mt-0.5", toneCls[tone])}>
          {value}
        </div>
      )}
      {sub && <div className="text-[12px] text-faint mt-0.5">{sub}</div>}
    </Wrap>
  );
}

/* ── Help ─────────────────────────────────────────────────────
   Quill is full of words a newcomer has no reason to know (canary, shadow,
   governor). Every one of them gets a plain-English hover. */
export function Help({ text }: { text: string }) {
  return (
    <span
      title={text}
      aria-label={text}
      className="inline-grid place-items-center h-[14px] w-[14px] rounded-full border border-rule
        text-[9px] text-muted cursor-help align-middle ml-1 select-none"
    >
      ?
    </span>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={cx("skeleton", className)} />;
}

export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <Card className="space-y-2.5">
      <Skeleton className="h-3 w-32" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={cx("h-3.5", i === rows - 1 ? "w-2/3" : "w-full")} />
      ))}
    </Card>
  );
}

export function EmptyState({
  title, note, icon, action,
}: { title: string; note?: string; icon?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-rule-strong bg-surface/40 px-6 py-10 text-center anim-fade">
      {icon && <div className="mx-auto mb-3 text-faint w-fit">{icon}</div>}
      <div className="font-semibold text-ink">{title}</div>
      {note && <div className="text-[13px] text-muted mt-1 max-w-sm mx-auto">{note}</div>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : String(error ?? "unknown error");
  return (
    <div className="rounded-md border border-[color:var(--risk)] bg-[color:var(--risk-soft)] px-4 py-3 anim-fade">
      <div className="text-[13px] font-semibold text-risk">Couldn't load this</div>
      <div className="text-[12.5px] text-ink-2 mt-0.5 break-words">{msg}</div>
      {onRetry && (
        <Button size="sm" variant="default" className="mt-2.5" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

/** Standard query wrapper: skeleton → error → empty → content. */
export function QueryPane<T>({
  query, empty, children, skeleton,
}: {
  query: { isPending: boolean; isError: boolean; error: unknown; data?: T; refetch: () => void };
  empty?: React.ReactNode;
  skeleton?: React.ReactNode;
  children: (data: T) => React.ReactNode;
}) {
  if (query.isPending) return <>{skeleton ?? <SkeletonCard />}</>;
  if (query.isError) return <ErrorState error={query.error} onRetry={query.refetch} />;
  const d = query.data as T;
  if (empty && Array.isArray(d) && d.length === 0) return <>{empty}</>;
  return <>{children(d)}</>;
}

/* ── Form bits ────────────────────────────────────────────── */
export function Field({
  label, hint, children, className = "",
}: { label?: string; hint?: string; children: React.ReactNode; className?: string }) {
  return (
    <label className={cx("block", className)}>
      {label && (
        <span className="block text-[12.5px] font-medium text-muted mb-1">{label}</span>
      )}
      {children}
      {hint && <span className="block text-[11.5px] text-faint mt-1">{hint}</span>}
    </label>
  );
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className = "", ...rest }, ref) {
    return <input ref={ref} {...rest} className={cx("field h-9", className)} />;
  }
);

export const Textarea = React.forwardRef<
  HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className = "", ...rest }, ref) {
  return <textarea ref={ref} {...rest} className={cx("field resize-none", className)} />;
});

export const Select = React.forwardRef<
  HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className = "", ...rest }, ref) {
  return <select ref={ref} {...rest} className={cx("field h-9", className)} />;
});

/* ── Segmented control ────────────────────────────────────── */
export function Segmented<T extends string>({
  value, onChange, options, size = "md",
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string; count?: number }[];
  size?: "sm" | "md";
}) {
  const h = size === "sm" ? "h-7 text-[12.5px]" : "h-8 text-[13px]";
  return (
    <div role="tablist" className="inline-flex p-0.5 gap-0.5 bg-surface-2 border border-rule rounded-sm">
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={on}
            onClick={() => onChange(o.value)}
            className={cx(
              "px-3 rounded-[4px] font-medium transition-colors duration-100 inline-flex items-center gap-1.5",
              h,
              on ? "bg-surface text-ink shadow-1" : "text-muted hover:text-ink"
            )}
          >
            {o.label}
            {o.count != null && (
              <span className={cx("num text-[11px]", on ? "text-accent" : "text-faint")}>
                {o.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ── Table ────────────────────────────────────────────────── */
export function Table({ head, children }: { head: React.ReactNode[]; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-md border border-rule bg-surface shadow-1">
      <table className="w-full text-[13px] border-collapse">
        <thead>
          <tr className="border-b border-rule bg-surface-2">
            {head.map((h, i) => (
              <th key={i}
                className="text-left font-semibold text-[11.5px] uppercase tracking-wide text-muted px-3 py-2 whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Tr({ children }: { children: React.ReactNode }) {
  return (
    <tr className="border-b border-rule last:border-0 hover:bg-surface-2 transition-colors duration-75">
      {children}
    </tr>
  );
}

export function Td({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <td className={cx("px-3 py-2 align-middle", className)}>{children}</td>;
}

/* ── Modal shell ──────────────────────────────────────────── */
export function Modal({
  open, onClose, children, labelledBy,
}: { open: boolean; onClose: () => void; children: React.ReactNode; labelledBy?: string }) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[10vh] anim-fade"
      style={{ background: "rgba(6,10,15,.55)", backdropFilter: "blur(2px)" }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div role="dialog" aria-modal="true" aria-labelledby={labelledBy}
        className="w-full max-w-lg bg-surface border border-rule-strong rounded-lg shadow-pop anim-rise overflow-hidden">
        {children}
      </div>
    </div>
  );
}
