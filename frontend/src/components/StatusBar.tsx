// The status rail. Present on every tab (U-05): autonomy mode, today's caps,
// session and canary health, next send slot, and the two stop controls.
// Kill and Panic stay reachable at every width — they are the safety exits.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { TABS, TabId } from "../lib/nav";
import { useTheme } from "../lib/theme";
import { useToast } from "./Toast";
import { Badge, Button, IconButton, StatusDot, cx } from "./ui";
import { LivePill, useLaunchStatus } from "./LaunchPanel";
import { IconKill, IconMenu, IconMonitor, IconMoon, IconPanic, IconSearch, IconSun } from "./Icons";

export function StatusBar({
  tab, onOpenMenu, onOpenPalette, onGo,
}: {
  tab: TabId; onOpenMenu: () => void; onOpenPalette: () => void;
  onGo: (t: TabId) => void;
}) {
  const qc = useQueryClient();
  const { toast, reportError, confirm } = useToast();
  const { theme, cycle } = useTheme();

  const gov = useQuery({
    queryKey: ["governor"],
    queryFn: () => api.get("/api/governor"),
    refetchInterval: 15000,
  });
  const g = gov.data;
  const u = g?.usage;
  // Health is only current while something is running to sample it.
  const launch = useLaunchStatus();
  const stopped = launch.data ? !launch.data.live : false;

  const kill = useMutation({
    mutationFn: (on: boolean) => api.post("/api/governor/kill", { on }),
    onSuccess: (_d, on) => {
      qc.invalidateQueries({ queryKey: ["governor"] });
      toast({
        tone: on ? "error" : "success",
        title: on ? "Kill switch engaged" : "Kill switch released",
        detail: on ? "Every write is refused until you release it." : "Writes may resume under the usual caps.",
      });
    },
    onError: (e) => reportError(e, "Kill switch failed"),
  });

  const panic = useMutation({
    mutationFn: () => api.post("/api/governor/panic"),
    onSuccess: () => {
      qc.invalidateQueries();
      toast({ tone: "error", title: "Panic executed", detail: "Kill switch on; recent auto replies deleted." });
    },
    onError: (e) => reportError(e, "Panic failed"),
  });

  async function doPanic() {
    const ok = await confirm({
      title: "Run panic?",
      danger: true,
      confirmLabel: "Run panic",
      body: (
        <>
          This engages the kill switch <b>and deletes recent automatic replies from X</b>.
          Deleted posts cannot be restored. Drafts and the audit log are kept.
        </>
      ),
    });
    if (ok) panic.mutate();
  }

  const current = TABS.find((t) => t.id === tab);
  const themeIcon =
    theme === "system" ? <IconMonitor size={16} /> : theme === "dark" ? <IconMoon size={16} /> : <IconSun size={16} />;

  return (
    <header
      className="sticky top-0 z-30 bg-surface/85 border-b border-rule"
      style={{ backdropFilter: "blur(8px)", paddingTop: "env(safe-area-inset-top)" }}
    >
      <div className="h-14 px-3 sm:px-5 flex items-center gap-2 sm:gap-3">
        <IconButton className="md:hidden" onClick={onOpenMenu} aria-label="Open menu">
          <IconMenu size={18} />
        </IconButton>

        <div className="min-w-0">
          <h1 className="text-[15px] font-semibold tracking-tight truncate">{current?.label ?? tab}</h1>
          <p className="hidden sm:block text-[11.5px] text-faint truncate leading-tight">{current?.blurb}</p>
        </div>

        {/* Live state. Collapses progressively rather than wrapping. */}
        <div className="hidden xl:flex items-center gap-3 ml-4">
          <Badge tone={g?.mode === "auto" ? "accent" : g?.mode === "assisted" ? "warn" : "neutral"}>
            {g?.mode ?? "—"}
          </Badge>
          {u && (
            <span className="num text-[12.5px] text-muted">
              <b className="text-ink-2 font-semibold">{u.replies_auto.used}</b>/{u.replies_auto.cap} auto
              <span className="text-faint"> · </span>
              <b className="text-ink-2 font-semibold">{u.replies_assisted.used}</b>/{u.replies_assisted.cap} assisted
            </span>
          )}
        </div>

        <div className="hidden lg:flex items-center gap-3 ml-auto mr-1">
          <StatusDot ok={g?.session_ok} unknown={!g || stopped}
            label={`session ${!g ? "…" : stopped ? "not checked" : g.session_ok ? "ok" : "down"}`} />
          <StatusDot ok={g?.canary_ok} unknown={!g || stopped}
            label={`canary ${!g ? "…" : stopped ? "not checked" : g.canary_ok ? "ok" : "fail"}`} />
          <span className="text-[12.5px] text-muted num">
            next {g?.next_slot
              ? new Date(g.next_slot).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
              : "—"}
          </span>
        </div>

        <div className="flex items-center gap-1.5 ml-auto lg:ml-0">
          <LivePill onClick={() => onGo("Home")} />

          <button
            onClick={onOpenPalette}
            className={cx(
              "hidden sm:flex items-center gap-2 h-9 pl-2.5 pr-2 rounded-sm border border-rule-strong",
              "bg-surface-2 text-muted hover:text-ink hover:border-muted transition-colors text-[13px]"
            )}
          >
            <IconSearch size={15} />
            <span className="hidden md:inline">Search</span>
            <span className="kbd ml-1 hidden md:inline-flex">⌘K</span>
          </button>
          <IconButton className="sm:hidden" onClick={onOpenPalette} aria-label="Search and commands">
            <IconSearch size={17} />
          </IconButton>

          <IconButton onClick={cycle} aria-label={`Theme: ${theme}. Click to change.`} title={`Theme: ${theme}`}>
            {themeIcon}
          </IconButton>

          <Button
            size="md"
            variant={g?.kill_switch ? "danger" : "default"}
            icon={<IconKill size={15} />}
            loading={kill.isPending}
            onClick={() => kill.mutate(!g?.kill_switch)}
            title={g?.kill_switch ? "Release the kill switch" : "Refuse all writes"}
          >
            <span className="hidden sm:inline">{g?.kill_switch ? "Killed" : "Kill"}</span>
          </Button>

          <Button
            size="md"
            variant="danger"
            icon={<IconPanic size={15} />}
            loading={panic.isPending}
            onClick={doPanic}
            title="Kill switch + delete recent auto replies"
          >
            <span className="hidden sm:inline">Panic</span>
          </Button>
        </div>
      </div>

      {/* Everything the wide bar shows, folded into one line on small screens. */}
      <div className="lg:hidden px-3 sm:px-5 pb-2 flex items-center gap-3 overflow-x-auto">
        <Badge tone={g?.mode === "auto" ? "accent" : g?.mode === "assisted" ? "warn" : "neutral"}>
          {g?.mode ?? "—"}
        </Badge>
        {u && (
          <span className="num text-[12px] text-muted whitespace-nowrap">
            {u.replies_auto.used}/{u.replies_auto.cap} auto · {u.replies_assisted.used}/{u.replies_assisted.cap} assisted
          </span>
        )}
        <StatusDot ok={g?.session_ok} unknown={!g || stopped} label="session" />
        <StatusDot ok={g?.canary_ok} unknown={!g || stopped} label="canary" />
        {g?.quiet_now && <span className="text-[12px] text-faint whitespace-nowrap">quiet hours</span>}
      </div>
    </header>
  );
}
