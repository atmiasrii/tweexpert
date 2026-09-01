// The nine tabs (§19), in one place: the sidebar, the command palette and the
// keyboard shortcuts all read this list so they can never drift apart.
import {
  IconAnalytics, IconAutopilot, IconCompose, IconDeck, IconDiscover, IconHome,
  IconOps, IconPersona, IconSchedule, IconWatchlist,
} from "../components/Icons";

export type TabId =
  | "Home" | "Autopilot" | "Deck" | "Compose" | "Schedule" | "Watchlist"
  | "Discover" | "Analytics" | "Persona" | "Ops";

export type TabDef = {
  id: TabId;
  /** Sidebar label. */
  label: string;
  /** What this tab is for — shown in the command palette. */
  blurb: string;
  icon: (p: { size?: number; className?: string }) => JSX.Element;
  /** g-prefixed jump key, e.g. g then a → Autopilot. */
  key: string;
  group: "review" | "write" | "grow" | "system";
};

export const TABS: TabDef[] = [
  { id: "Autopilot", label: "Autopilot", blurb: "Review the reply queue and the shadow log", icon: IconAutopilot, key: "a", group: "review" },
  { id: "Deck", label: "Deck", blurb: "TweetDeck view — pending, sent and For You in columns", icon: IconDeck, key: "t", group: "review" },
  { id: "Home", label: "Overview", blurb: "Safeguards, caps and what needs attention", icon: IconHome, key: "h", group: "review" },

  { id: "Compose", label: "Compose", blurb: "Write a post, draft from an idea, capture ideas", icon: IconCompose, key: "c", group: "write" },
  { id: "Schedule", label: "Schedule", blurb: "Weekly slots and the queued post list", icon: IconSchedule, key: "s", group: "write" },
  { id: "Persona", label: "Persona", blurb: "Voice card, archive import, playground", icon: IconPersona, key: "p", group: "write" },

  { id: "Watchlist", label: "Watchlist", blurb: "Watched accounts and their autonomy mode", icon: IconWatchlist, key: "w", group: "grow" },
  { id: "Discover", label: "Discover", blurb: "Saved searches, discovery inbox, notifications", icon: IconDiscover, key: "d", group: "grow" },
  { id: "Analytics", label: "Analytics", blurb: "Post performance, replies by angle, followers", icon: IconAnalytics, key: "n", group: "grow" },

  { id: "Ops", label: "Ops", blurb: "Health, audit log, live logs, model calls, backups", icon: IconOps, key: "o", group: "system" },
];

export const GROUP_LABEL: Record<TabDef["group"], string> = {
  review: "Review",
  write: "Write",
  grow: "Grow",
  system: "System",
};

export const GROUP_ORDER: TabDef["group"][] = ["review", "write", "grow", "system"];

export function tabsByGroup(g: TabDef["group"]) {
  return TABS.filter((t) => t.group === g);
}
