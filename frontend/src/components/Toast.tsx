// Toasts and confirmations. Replaces window.alert / window.confirm: a tool that
// runs unattended must be able to show a failure without blocking its own event
// loop, and a destructive confirm needs to state the consequence in full (§22).
import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { Button, cx } from "./ui";
import { IconAlert, IconCheck, IconInfo, IconX } from "./Icons";

type ToastTone = "info" | "success" | "error";
type Toast = { id: number; tone: ToastTone; title: string; detail?: string };

type ConfirmSpec = {
  title: string;
  body?: React.ReactNode;
  confirmLabel?: string;
  danger?: boolean;
};

type Ctx = {
  toast: (t: { tone?: ToastTone; title: string; detail?: string }) => void;
  /** Reports a thrown error without swallowing the message. */
  reportError: (e: unknown, title?: string) => void;
  confirm: (spec: ConfirmSpec) => Promise<boolean>;
};

const ToastCtx = createContext<Ctx | null>(null);

export function useToast(): Ctx {
  const c = useContext(ToastCtx);
  if (!c) throw new Error("useToast outside ToastProvider");
  return c;
}

const TONE_STYLE: Record<ToastTone, { cls: string; icon: React.ReactNode }> = {
  info: { cls: "border-rule-strong", icon: <IconInfo size={16} className="text-accent" /> },
  success: { cls: "border-[color:var(--go)]", icon: <IconCheck size={16} className="text-go" /> },
  error: { cls: "border-[color:var(--risk)]", icon: <IconAlert size={16} className="text-risk" /> },
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const [ask, setAsk] = useState<(ConfirmSpec & { resolve: (v: boolean) => void }) | null>(null);
  const seq = useRef(1);

  const dismiss = useCallback((id: number) => {
    setItems((l) => l.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback<Ctx["toast"]>(({ tone = "info", title, detail }) => {
    const id = seq.current++;
    setItems((l) => [...l.slice(-3), { id, tone, title, detail }]);
    // Errors stay long enough to read and copy; the rest clear quickly.
    window.setTimeout(() => dismiss(id), tone === "error" ? 9000 : 4000);
  }, [dismiss]);

  const reportError = useCallback<Ctx["reportError"]>((e, title = "Something failed") => {
    const raw = e instanceof Error ? e.message : String(e ?? "");
    // Server errors arrive as text or JSON {"detail": "..."}; show the useful half.
    let detail = raw.trim();
    try {
      const parsed = JSON.parse(detail);
      if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
    } catch { /* plain text */ }
    if (detail.length > 400) detail = detail.slice(0, 400) + "…";
    toast({ tone: "error", title, detail: detail || undefined });
  }, [toast]);

  const confirm = useCallback<Ctx["confirm"]>((spec) => {
    return new Promise<boolean>((resolve) => setAsk({ ...spec, resolve }));
  }, []);

  const value = useMemo(() => ({ toast, reportError, confirm }), [toast, reportError, confirm]);

  const settle = (v: boolean) => { ask?.resolve(v); setAsk(null); };

  return (
    <ToastCtx.Provider value={value}>
      {children}

      {/* Toast stack — above content, below modals. */}
      <div className="fixed z-[60] bottom-4 right-4 left-4 sm:left-auto flex flex-col items-stretch sm:items-end gap-2 pointer-events-none"
        role="status" aria-live="polite">
        {items.map((t) => {
          const s = TONE_STYLE[t.tone];
          return (
            <div key={t.id}
              className={cx(
                "pointer-events-auto anim-toast w-full sm:w-[360px] flex gap-2.5 p-3",
                "bg-surface border rounded-md shadow-2", s.cls
              )}>
              <div className="mt-0.5 shrink-0">{s.icon}</div>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold text-ink">{t.title}</div>
                {t.detail && (
                  <div className="text-[12.5px] text-muted mt-0.5 break-words">{t.detail}</div>
                )}
              </div>
              <button onClick={() => dismiss(t.id)} aria-label="Dismiss"
                className="shrink-0 h-5 w-5 grid place-items-center rounded-sm text-faint hover:text-ink hover:bg-surface-2">
                <IconX size={13} />
              </button>
            </div>
          );
        })}
      </div>

      {/* Confirmation — never a bare "Are you sure?"; it names the consequence. */}
      {ask && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 anim-fade"
          style={{ background: "rgba(6,10,15,.55)", backdropFilter: "blur(2px)" }}
          onMouseDown={(e) => { if (e.target === e.currentTarget) settle(false); }}>
          <div role="alertdialog" aria-modal="true"
            className="w-full max-w-md bg-surface border border-rule-strong rounded-lg shadow-pop anim-rise p-5">
            <div className="text-[15px] font-semibold text-ink">{ask.title}</div>
            {ask.body && <div className="text-[13px] text-muted mt-2 leading-relaxed">{ask.body}</div>}
            <div className="flex justify-end gap-2 mt-5">
              <Button variant="default" onClick={() => settle(false)}>Cancel</Button>
              <Button
                autoFocus
                variant={ask.danger ? "danger" : "primary"}
                onClick={() => settle(true)}
              >
                {ask.confirmLabel ?? "Confirm"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </ToastCtx.Provider>
  );
}
