// Charts, drawn as plain SVG. No plotting library: these are two shapes, and a
// self-hosted tool should not pull 200KB to draw them.
//
// Colour comes from --chart-1, a token validated separately for light and dark
// (lightness band, chroma floor, contrast vs the chart surface). Every chart
// here is single-series, so identity is carried by the title and the axis, and
// no legend box is needed. Text always wears text tokens, never the mark colour.
import { useLayoutEffect, useRef, useState } from "react";
import { cx } from "./ui";

/** Width of the container, so the SVG can be drawn at real pixel size. */
function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const set = () => setW(el.clientWidth);
    set();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", set);
      return () => window.removeEventListener("resize", set);
    }
    const ro = new ResizeObserver(set);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

function niceTicks(min: number, max: number, count = 3) {
  if (min === max) return [min];
  const span = max - min;
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? mag * 10;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(Number(v.toFixed(6)));
  return out.length ? out : [min, max];
}

export type Point = { label: string; value: number };

/* ── line ─────────────────────────────────────────────────── */

export function LineChart({
  data, height = 168, format = (v: number) => String(v), valueLabel = "value",
}: {
  data: Point[];
  height?: number;
  format?: (v: number) => string;
  valueLabel?: string;
}) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const pad = { t: 10, r: 12, b: 22, l: 40 };
  const iw = Math.max(10, w - pad.l - pad.r);
  const ih = height - pad.t - pad.b;

  const values = data.map((d) => d.value);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  // A flat series should read as flat, not as noise blown up to full height.
  const pad0 = rawMax === rawMin ? Math.max(1, Math.abs(rawMax) * 0.05) : (rawMax - rawMin) * 0.12;
  const min = rawMin - pad0;
  const max = rawMax + pad0;

  const x = (i: number) => (data.length === 1 ? iw / 2 : (i / (data.length - 1)) * iw);
  const y = (v: number) => ih - ((v - min) / (max - min)) * ih;

  const ticks = niceTicks(min, max, 3);
  const path = data.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(d.value).toFixed(1)}`).join(" ");
  const area = data.length > 1 ? `${path} L${x(data.length - 1).toFixed(1)} ${ih} L${x(0).toFixed(1)} ${ih} Z` : "";

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    if (data.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left - pad.l;
    const i = data.length === 1 ? 0
      : Math.max(0, Math.min(data.length - 1, Math.round((px / iw) * (data.length - 1))));
    setHover(i);
  }

  const hv = hover != null ? data[hover] : null;

  return (
    <div ref={ref} className="relative w-full">
      {w > 0 && (
        <svg width={w} height={height} role="img"
          aria-label={`${valueLabel} over time, ${data.length} points`}
          onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          <g transform={`translate(${pad.l},${pad.t})`}>
            {/* Recessive grid, drawn behind everything. */}
            {ticks.map((t) => (
              <g key={t}>
                <line x1={0} x2={iw} y1={y(t)} y2={y(t)} stroke="var(--chart-grid)" strokeWidth={1} />
                <text x={-8} y={y(t)} dy="0.32em" textAnchor="end"
                  className="num" fontSize="10.5" fill="var(--chart-axis)">
                  {format(t)}
                </text>
              </g>
            ))}

            {data.length > 1 && (
              <>
                <defs>
                  <linearGradient id="q-area" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--chart-1)" stopOpacity="0.16" />
                    <stop offset="100%" stopColor="var(--chart-1)" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <path d={area} fill="url(#q-area)" />
                <path d={path} fill="none" stroke="var(--chart-1)" strokeWidth={2}
                  strokeLinejoin="round" strokeLinecap="round" />
              </>
            )}

            {/* A single reading is a point, not a line. */}
            {data.length === 1 && (
              <circle cx={x(0)} cy={y(data[0].value)} r={4.5} fill="var(--chart-1)"
                stroke="var(--surface)" strokeWidth={2} />
            )}

            {hv && (
              <>
                <line x1={x(hover!)} x2={x(hover!)} y1={0} y2={ih}
                  stroke="var(--chart-axis)" strokeWidth={1} strokeDasharray="3 3" />
                {/* 2px surface ring keeps the marker legible over the line. */}
                <circle cx={x(hover!)} cy={y(hv.value)} r={4.5} fill="var(--chart-1)"
                  stroke="var(--surface)" strokeWidth={2} />
              </>
            )}

            {/* First and last labels only — never a number on every point. */}
            {data.length > 1 && (
              <>
                <text x={0} y={ih + 15} fontSize="10.5" fill="var(--chart-axis)">{data[0].label}</text>
                <text x={iw} y={ih + 15} fontSize="10.5" textAnchor="end" fill="var(--chart-axis)">
                  {data[data.length - 1].label}
                </text>
              </>
            )}
            {data.length === 1 && (
              <text x={x(0)} y={ih + 15} fontSize="10.5" textAnchor="middle" fill="var(--chart-axis)">
                {data[0].label}
              </text>
            )}
          </g>
        </svg>
      )}

      {hv && (
        <div
          className="pointer-events-none absolute z-10 px-2 py-1.5 rounded-sm bg-surface border border-rule-strong shadow-2 text-[12px] whitespace-nowrap"
          style={{
            left: Math.min(Math.max(pad.l + x(hover!) - 40, 0), Math.max(0, w - 96)),
            top: 0,
          }}
        >
          <div className="text-faint">{hv.label}</div>
          <div className="num font-semibold text-ink">{format(hv.value)}</div>
        </div>
      )}
    </div>
  );
}

/* ── horizontal bars ──────────────────────────────────────── */

export function BarChart({
  data, format = (v: number) => String(v), max: fixedMax,
}: { data: Point[]; format?: (v: number) => string; max?: number }) {
  const max = fixedMax ?? Math.max(1, ...data.map((d) => d.value));
  return (
    <ul className="space-y-2">
      {data.map((d) => {
        const pct = (d.value / max) * 100;
        return (
          <li key={d.label} className="grid grid-cols-[minmax(0,7rem)_1fr_auto] items-center gap-3">
            <span className="text-[12.5px] text-muted truncate" title={d.label}>{d.label}</span>
            <span className="h-4 rounded-sm bg-surface-2 overflow-hidden">
              {/* 4px rounded data-end, anchored to the baseline. */}
              <span
                className={cx("block h-full rounded-r-[4px] transition-[width] duration-300")}
                style={{ width: `${Math.max(pct, d.value > 0 ? 3 : 0)}%`, background: "var(--chart-1)" }}
              />
            </span>
            <span className="num text-[12.5px] font-medium text-ink-2 tabular-nums">{format(d.value)}</span>
          </li>
        );
      })}
    </ul>
  );
}

/* ── hero number ──────────────────────────────────────────── */

export function Stat({
  label, value, delta, hint,
}: { label: string; value: string; delta?: number; hint?: string }) {
  return (
    <div>
      <div className="text-[11.5px] uppercase tracking-wider text-faint">{label}</div>
      <div className="flex items-baseline gap-2 mt-1">
        <span className="num text-[26px] font-semibold leading-none tracking-tight">{value}</span>
        {delta != null && delta !== 0 && (
          <span className={cx("num text-[12.5px] font-medium", delta > 0 ? "text-go" : "text-risk")}>
            {delta > 0 ? "+" : ""}{delta}
          </span>
        )}
      </div>
      {hint && <div className="text-[12px] text-muted mt-1">{hint}</div>}
    </div>
  );
}
