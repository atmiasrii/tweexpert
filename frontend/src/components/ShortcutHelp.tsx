// The "?" sheet. Shortcuts only help if they are discoverable; this is the one
// place that lists them, and it reads from the same tab table the sidebar uses.
import { TABS } from "../lib/nav";
import { Modal } from "./ui";

const GLOBAL: [string, string][] = [
  ["⌘K / Ctrl K", "Command palette"],
  ["g then a key", "Jump to a tab"],
  ["?", "This sheet"],
  ["Esc", "Close anything open"],
];

const REVIEW: [string, string][] = [
  ["J / K", "Next / previous draft"],
  ["1 2 3", "Pick candidate one, two or three"],
  ["E", "Edit the draft inline"],
  ["Enter", "Approve — sends after a short undo window"],
  ["X", "Skip this draft"],
  ["U", "Undo the send in flight"],
];

function Row({ keys, what }: { keys: string; what: string }) {
  return (
    <div className="flex items-baseline gap-3 py-1.5 border-b border-rule last:border-0">
      <span className="w-28 shrink-0">
        {keys.split(" ").map((k, i) =>
          k === "/" || k === "then" ? (
            <span key={i} className="text-faint text-[11px] mx-0.5">{k}</span>
          ) : (
            <span key={i} className="kbd mr-1">{k}</span>
          )
        )}
      </span>
      <span className="text-[13px] text-muted">{what}</span>
    </div>
  );
}

export function ShortcutHelp({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Modal open={open} onClose={onClose} labelledBy="shortcut-title">
      <div className="px-5 py-4 border-b border-rule flex items-center">
        <h2 id="shortcut-title" className="text-[15px] font-semibold">Keyboard</h2>
        <span className="kbd ml-auto">esc</span>
      </div>
      <div className="px-5 py-4 max-h-[62vh] overflow-y-auto">
        <Section title="Anywhere">
          {GLOBAL.map(([k, w]) => <Row key={k} keys={k} what={w} />)}
        </Section>
        <Section title="Autopilot queue">
          {REVIEW.map(([k, w]) => <Row key={k} keys={k} what={w} />)}
        </Section>
        <Section title="Jump to">
          <div className="grid grid-cols-2 gap-x-6">
            {TABS.map((t) => (
              <div key={t.id} className="flex items-baseline gap-2 py-1.5">
                <span className="kbd">g</span>
                <span className="kbd">{t.key}</span>
                <span className="text-[13px] text-muted truncate">{t.label}</span>
              </div>
            ))}
          </div>
        </Section>
      </div>
    </Modal>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-5 last:mb-0">
      <h3 className="text-[10.5px] font-semibold uppercase tracking-wider text-faint mb-1.5">{title}</h3>
      {children}
    </section>
  );
}
