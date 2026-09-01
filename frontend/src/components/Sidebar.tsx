// Left navigation. Full labels on wide screens, an icon rail in between, and a
// slide-over drawer on phones. The safeguard meters live in the footer so the
// caps are visible from every tab (U-05) without spending header width.
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { GROUP_LABEL, GROUP_ORDER, TabId, tabsByGroup } from "../lib/nav";
import { Badge, IconButton, Meter, cx } from "./ui";
import { IconX } from "./Icons";

export function Sidebar({
  tab, onPick, queueCount, mobileOpen, onCloseMobile,
}: {
  tab: TabId;
  onPick: (t: TabId) => void;
  queueCount: number;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}) {
  return (
    <>
      {/* Phone drawer scrim */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden anim-fade"
          style={{ background: "rgba(6,10,15,.5)" }}
          onClick={onCloseMobile} aria-hidden="true" />
      )}

      <aside
        className={cx(
          "z-50 shrink-0 bg-surface border-r border-rule flex flex-col",
          // Phone: off-canvas drawer.
          "fixed inset-y-0 left-0 w-[260px] transition-transform duration-200 ease-out lg:transition-none",
          mobileOpen ? "translate-x-0 shadow-pop" : "-translate-x-full",
          // Tablet: icon rail. Desktop: full sidebar.
          "md:sticky md:top-0 md:h-screen md:translate-x-0 md:w-[68px] md:shadow-none lg:w-[236px]"
        )}
        aria-label="Sections"
      >
        <div className="h-14 px-3 flex items-center gap-2 border-b border-rule shrink-0">
          <Brand />
          <IconButton size="sm" className="ml-auto md:hidden" onClick={onCloseMobile} aria-label="Close menu">
            <IconX size={15} />
          </IconButton>
        </div>

        <nav className="flex-1 overflow-y-auto py-3 px-2 md:px-2">
          {GROUP_ORDER.map((g) => (
            <div key={g} className="mb-3 last:mb-0">
              <div className="px-2 mb-1 text-[10.5px] font-semibold uppercase tracking-wider text-faint md:hidden lg:block">
                {GROUP_LABEL[g]}
              </div>
              {/* The rail keeps a divider where the group label would be. */}
              <div className="hidden md:block lg:hidden mx-2 mb-1.5 border-t border-rule" />

              <ul className="space-y-0.5">
                {tabsByGroup(g).map((t) => {
                  const on = t.id === tab;
                  const Icon = t.icon;
                  const badge = t.id === "Autopilot" && queueCount > 0 ? queueCount : null;
                  return (
                    <li key={t.id}>
                      <button
                        onClick={() => { onPick(t.id); onCloseMobile(); }}
                        aria-current={on ? "page" : undefined}
                        title={t.label}
                        className={cx(
                          "group relative w-full flex items-center gap-2.5 rounded-sm",
                          "h-9 px-2.5 text-[13.5px] font-medium transition-colors duration-100",
                          "md:justify-center md:px-0 lg:justify-start lg:px-2.5",
                          on
                            ? "bg-[color:var(--accent-soft)] text-accent"
                            : "text-muted hover:bg-surface-2 hover:text-ink"
                        )}
                      >
                        {/* Active marker, so the rail reads at icon size too. */}
                        <span className={cx(
                          "absolute left-0 top-1.5 bottom-1.5 w-[2.5px] rounded-full transition-opacity",
                          on ? "bg-[color:var(--accent)] opacity-100" : "opacity-0"
                        )} />
                        <Icon size={17} className="shrink-0" />
                        <span className="md:hidden lg:inline truncate">{t.label}</span>
                        {badge != null && (
                          <span className={cx(
                            "num text-[11px] font-semibold rounded-full px-1.5 h-[18px] inline-flex items-center",
                            "md:absolute md:top-1 md:right-1 lg:static",
                            on ? "bg-[color:var(--accent)] text-[color:var(--accent-ink)]" : "bg-surface-3 text-muted",
                            "ml-auto lg:ml-auto"
                          )}>
                            {badge}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <SafeguardFooter />
      </aside>
    </>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2 min-w-0">
      <span className="grid place-items-center h-7 w-7 rounded-sm bg-[color:var(--accent)] text-[color:var(--accent-ink)] shrink-0">
        {/* A nib. */}
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 20l3.2-8.5L15.5 3.2a2.2 2.2 0 0 1 3.2 3L10.3 14.7 4 20Z"
            stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
          <path d="M10.3 14.7 7.2 11.5M12 12l-2.6 6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
      </span>
      <span className="font-semibold tracking-tight text-[15px] md:hidden lg:inline">Quill</span>
    </div>
  );
}

/** Caps and autonomy mode, always on screen (S-07, U-05). */
function SafeguardFooter() {
  const gov = useQuery({
    queryKey: ["governor"],
    queryFn: () => api.get("/api/governor"),
    refetchInterval: 30000,
  });
  const g = gov.data;
  const u = g?.usage;
  if (!u) return <div className="h-px" />;

  return (
    <div className="border-t border-rule p-3 space-y-2.5 shrink-0 md:hidden lg:block">
      <div className="flex items-center gap-2">
        <Badge tone={g.mode === "auto" ? "accent" : g.mode === "assisted" ? "warn" : "neutral"}>
          {g.mode}
        </Badge>
        {g.quiet_now && <span className="text-[11px] text-faint">quiet hours</span>}
      </div>
      <Meter label="Auto replies" used={u.replies_auto.used} cap={u.replies_auto.cap} />
      <Meter label="Assisted" used={u.replies_assisted.used} cap={u.replies_assisted.cap} />
      <Meter label="Posts" used={u.posts.used} cap={u.posts.cap} />
    </div>
  );
}
