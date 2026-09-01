// ⌘K / Ctrl-K palette: jump to any tab and run the handful of global actions
// without leaving the keyboard. Everything it can do is reachable by mouse too;
// this is a shortcut, never the only path.
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { TABS, TabId } from "../lib/nav";
import { Theme, useTheme } from "../lib/theme";
import { useToast } from "./Toast";
import { Modal, cx } from "./ui";
import { IconKill, IconMonitor, IconMoon, IconPanic, IconSearch, IconSun } from "./Icons";

type Cmd = {
  id: string;
  label: string;
  hint?: string;
  section: string;
  icon?: JSX.Element;
  keys?: string;
  run: () => void;
};

/**
 * Score a command against the query. Subsequence matching alone is not enough:
 * "ops" is a subsequence of "Autopilot … shadow log", so without ranking the
 * wrong row wins. Higher is better; 0 means no match.
 */
function score(needle: string, label: string, hint: string) {
  if (!needle) return 1;
  const n = needle.toLowerCase();
  const l = label.toLowerCase();
  const h = hint.toLowerCase();

  if (l === n) return 100;
  if (l.startsWith(n)) return 90;
  // A match at a word boundary beats one buried mid-word.
  if (new RegExp(`\\b${n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`).test(l)) return 80;
  if (l.includes(n)) return 70;
  if (h.includes(n)) return 40;

  // Loosest tier: initials, then any subsequence of the label.
  const initials = l.split(/\s+/).map((w) => w[0]).join("");
  if (initials.startsWith(n)) return 60;

  let i = 0;
  for (const ch of l) { if (ch === n[i]) i++; if (i === n.length) return 20; }
  return 0;
}

export function CommandPalette({
  open, onClose, onGo, killOn,
}: { open: boolean; onClose: () => void; onGo: (t: TabId) => void; killOn: boolean }) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();
  const { toast, reportError, confirm } = useToast();
  const { setTheme } = useTheme();

  const kill = useMutation({
    mutationFn: (on: boolean) => api.post("/api/governor/kill", { on }),
    onSuccess: (_d, on) => {
      qc.invalidateQueries({ queryKey: ["governor"] });
      toast({ tone: on ? "error" : "success", title: on ? "Kill switch engaged" : "Kill switch released" });
    },
    onError: (e) => reportError(e, "Kill switch failed"),
  });
  const panic = useMutation({
    mutationFn: () => api.post("/api/governor/panic"),
    onSuccess: () => { qc.invalidateQueries(); toast({ tone: "error", title: "Panic executed" }); },
    onError: (e) => reportError(e, "Panic failed"),
  });

  const cmds: Cmd[] = useMemo(() => {
    const nav: Cmd[] = TABS.map((t) => ({
      id: `go:${t.id}`,
      label: t.label,
      hint: t.blurb,
      section: "Go to",
      icon: <t.icon size={16} />,
      keys: `g ${t.key}`,
      run: () => { onGo(t.id); onClose(); },
    }));

    const themes: [Theme, string, JSX.Element][] = [
      ["light", "Light theme", <IconSun size={16} key="l" />],
      ["dark", "Dark theme", <IconMoon size={16} key="d" />],
      ["system", "Match system theme", <IconMonitor size={16} key="s" />],
    ];

    const actions: Cmd[] = [
      {
        id: "kill",
        label: killOn ? "Release the kill switch" : "Engage the kill switch",
        hint: killOn ? "Allow writes again, under the usual caps" : "Refuse every write until released",
        section: "Actions",
        icon: <IconKill size={16} />,
        run: () => { kill.mutate(!killOn); onClose(); },
      },
      {
        id: "panic",
        label: "Panic — kill and delete recent auto replies",
        hint: "Irreversible: deleted posts cannot be restored",
        section: "Actions",
        icon: <IconPanic size={16} />,
        run: async () => {
          onClose();
          const ok = await confirm({
            title: "Run panic?",
            danger: true,
            confirmLabel: "Run panic",
            body: <>This engages the kill switch <b>and deletes recent automatic replies from X</b>. Deleted posts cannot be restored.</>,
          });
          if (ok) panic.mutate();
        },
      },
      {
        id: "refresh",
        label: "Refresh all data",
        section: "Actions",
        icon: <IconSearch size={16} />,
        run: () => { qc.invalidateQueries(); toast({ title: "Refreshed" }); onClose(); },
      },
      ...themes.map(([t, label, icon]) => ({
        id: `theme:${t}`,
        label,
        section: "Appearance",
        icon,
        run: () => { setTheme(t); onClose(); },
      })),
    ];

    return [...nav, ...actions];
  }, [killOn, onGo, onClose, kill, panic, qc, setTheme, toast, confirm]);

  const hits = useMemo(() => {
    const scored = cmds
      .map((c, i) => ({ c, i, s: score(q, c.label, `${c.hint ?? ""} ${c.section}`) }))
      .filter((x) => x.s > 0);
    // Best first; ties keep the declared order so an empty query reads as the menu.
    scored.sort((a, b) => b.s - a.s || a.i - b.i);
    return scored.map((x) => x.c);
  }, [cmds, q]);

  useEffect(() => { if (open) { setQ(""); setSel(0); } }, [open]);
  useEffect(() => { setSel(0); }, [q]);
  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  // Keep the highlighted row in view while arrowing through a long list.
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-idx="${sel}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [sel]);

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, hits.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); hits[sel]?.run(); }
  }

  // Section headers only make sense while the list is in its declared order;
  // once results are ranked, groups interleave and a header would repeat.
  const grouped = q.trim() === "";
  let lastSection = "";

  return (
    <Modal open={open} onClose={onClose}>
      <div className="flex items-center gap-2.5 px-4 h-12 border-b border-rule">
        <IconSearch size={17} className="text-faint shrink-0" />
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onKey}
          placeholder="Jump to a tab, or run a command…"
          aria-label="Command palette"
          className="flex-1 bg-transparent border-0 outline-none text-[14.5px] placeholder:text-faint"
        />
        <span className="kbd">esc</span>
      </div>

      <div ref={listRef} className="max-h-[52vh] overflow-y-auto py-1.5">
        {hits.length === 0 && (
          <div className="px-4 py-8 text-center text-[13px] text-muted">
            Nothing matches “{q}”.
          </div>
        )}
        {hits.map((c, i) => {
          const header = grouped && c.section !== lastSection
            ? ((lastSection = c.section), c.section)
            : null;
          const on = i === sel;
          return (
            <div key={c.id}>
              {header && (
                <div className="px-4 pt-2.5 pb-1 text-[10.5px] font-semibold uppercase tracking-wider text-faint">
                  {header}
                </div>
              )}
              <button
                data-idx={i}
                onMouseMove={() => setSel(i)}
                onClick={c.run}
                className={cx(
                  "w-full flex items-center gap-3 px-4 py-2 text-left transition-colors duration-75",
                  on ? "bg-[color:var(--accent-soft)]" : "hover:bg-surface-2"
                )}
              >
                <span className={cx("shrink-0", on ? "text-accent" : "text-muted")}>{c.icon}</span>
                <span className="min-w-0 flex-1">
                  <span className={cx("block text-[13.5px] font-medium truncate", on ? "text-accent" : "text-ink")}>
                    {c.label}
                  </span>
                  {c.hint && <span className="block text-[12px] text-muted truncate">{c.hint}</span>}
                </span>
                {c.keys && <span className="kbd shrink-0">{c.keys}</span>}
              </button>
            </div>
          );
        })}
      </div>
    </Modal>
  );
}
