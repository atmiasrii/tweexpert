// Theme: system | light | dark. Applied as data-theme on <html> so CSS tokens
// and Tailwind's dark: selector agree. Persisted per browser; storage can throw
// in a locked-down profile, so every access is guarded.
import { useEffect, useState } from "react";

export type Theme = "system" | "light" | "dark";
const KEY = "quill.theme";

export function readTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {}
  return "system";
}

function systemDark() {
  return typeof matchMedia === "function" &&
    matchMedia("(prefers-color-scheme: dark)").matches;
}

export function applyTheme(t: Theme) {
  const dark = t === "dark" || (t === "system" && systemDark());
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
}

/** Call once at boot, before first paint, to avoid a light flash. */
export function initTheme() {
  applyTheme(readTheme());
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readTheme);

  useEffect(() => {
    applyTheme(theme);
    try { localStorage.setItem(KEY, theme); } catch {}
  }, [theme]);

  // Track the OS preference while following it.
  useEffect(() => {
    if (theme !== "system" || typeof matchMedia !== "function") return;
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  const cycle = () =>
    setTheme((t) => (t === "system" ? "light" : t === "light" ? "dark" : "system"));

  return { theme, setTheme, cycle };
}
