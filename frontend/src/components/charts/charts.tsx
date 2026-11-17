import { useId, useMemo, useState } from "react";
import { cn } from "../../lib/cn";
import { fmtDec, fmtPct, fmtPrice, fmtTime, fmtDay } from "../../lib/format";

type Pt = { x: number; y: number };

function scale(d0: number, d1: number, r0: number, r1: number) {
  const span = d1 - d0 || 1;
  return (v: number) => r0 + ((v - d0) / span) * (r1 - r0);
}

function path(points: Pt[]): string {
  return points.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join("");
}

/** Tiny trend line, e.g. odds movement on a card. */
export function Sparkline({ values, width = 72, height = 24, className }: { values: number[]; width?: number; height?: number; className?: string }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const sx = scale(0, values.length - 1, 1, width - 1);
  const sy = scale(min, max === min ? min + 1 : max, height - 2, 2);
  const pts = values.map((v, i) => ({ x: sx(i), y: sy(v) }));
  const up = values[values.length - 1] >= values[0];
  const color = up ? "var(--color-pos)" : "var(--color-neg)";
  return (
    <svg width={width} height={height} className={className} aria-hidden>
      <path d={path(pts)} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={pts[pts.length - 1].x} cy={pts[pts.length - 1].y} r={2} fill={color} />
    </svg>
  );
}

/** Area/line chart with zero baseline and touch/hover readout. */
export function AreaChart({
  data,
  height = 180,
  formatY = (v: number) => fmtDec(v, 1),
  formatX = (iso: string) => fmtDay(iso),
  zeroLine = true,
  color: fixedColor,
}: {
  data: { at: string; value: number }[];
  height?: number;
  formatY?: (v: number) => string;
  formatX?: (iso: string) => string;
  zeroLine?: boolean;
  /** Fixed stroke colour; default colours by sign of the last value. */
  color?: string;
}) {
  const gid = useId().replace(/:/g, "");
  const [hover, setHover] = useState<number | null>(null);
  const W = 340;
  const H = height;
  const pad = { l: 4, r: 4, t: 12, b: 20 };

  const geo = useMemo(() => {
    if (data.length < 2) return null;
    const ys = data.map((d) => d.value);
    let min = Math.min(...ys, zeroLine ? 0 : Infinity);
    let max = Math.max(...ys, zeroLine ? 0 : -Infinity);
    const padY = (max - min) * 0.12 || 1;
    min -= padY;
    max += padY;
    const sx = scale(0, data.length - 1, pad.l, W - pad.r);
    const sy = scale(min, max, H - pad.b, pad.t);
    const pts = data.map((d, i) => ({ x: sx(i), y: sy(d.value) }));
    return { pts, sy, sx };
  }, [data, H, zeroLine]);

  if (!geo) return <div className="grid h-40 place-items-center text-xs text-fg-faint">Za mało danych do wykresu</div>;
  const { pts, sy } = geo;
  const last = data[data.length - 1].value;
  const color = fixedColor ?? (last >= 0 ? "var(--color-pos)" : "var(--color-neg)");
  const y0 = sy(0);
  const area = `${path(pts)}L${pts[pts.length - 1].x},${H - pad.b}L${pts[0].x},${H - pad.b}Z`;
  const h = hover === null ? null : { p: pts[hover], d: data[hover] };

  const onMove = (clientX: number, el: SVGSVGElement) => {
    const r = el.getBoundingClientRect();
    const x = ((clientX - r.left) / r.width) * W;
    const i = Math.round(((x - pad.l) / (W - pad.l - pad.r)) * (data.length - 1));
    setHover(Math.max(0, Math.min(data.length - 1, i)));
  };

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full touch-pan-y select-none"
        onPointerMove={(e) => onMove(e.clientX, e.currentTarget)}
        onPointerDown={(e) => onMove(e.clientX, e.currentTarget)}
        onPointerLeave={() => setHover(null)}
        role="img"
        aria-label="Wykres"
      >
        <defs>
          <linearGradient id={`g${gid}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.28} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1={pad.l} x2={W - pad.r} y1={pad.t + (H - pad.t - pad.b) * f} y2={pad.t + (H - pad.t - pad.b) * f} stroke="var(--color-line)" />
        ))}
        {zeroLine && <line x1={pad.l} x2={W - pad.r} y1={y0} y2={y0} stroke="var(--color-fg-faint)" strokeDasharray="3 4" strokeOpacity={0.6} />}
        <path d={area} fill={`url(#g${gid})`} />
        <path d={path(pts)} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
        {h && (
          <>
            <line x1={h.p.x} x2={h.p.x} y1={pad.t} y2={H - pad.b} stroke="var(--color-fg-faint)" strokeOpacity={0.5} />
            <circle cx={h.p.x} cy={h.p.y} r={4} fill="var(--color-ink-950)" stroke={color} strokeWidth={2} />
          </>
        )}
        <text x={pad.l} y={H - 4} fontSize={10} fill="var(--color-fg-faint)">
          {formatX(data[0].at)}
        </text>
        <text x={W - pad.r} y={H - 4} fontSize={10} fill="var(--color-fg-faint)" textAnchor="end">
          {formatX(data[data.length - 1].at)}
        </text>
      </svg>
      {h && (
        <div className="tnum pointer-events-none absolute top-0 right-0 rounded-lg bg-ink-700/90 px-2 py-1 text-[11px] text-fg ring-1 ring-line-strong backdrop-blur">
          {formatX(h.d.at)} · <b>{formatY(h.d.value)}</b>
        </div>
      )}
    </div>
  );
}

/** Odds movement chart for one selection. */
export function OddsChart({ points }: { points: { at: string; price: number }[] }) {
  return <AreaChart data={points.map((p) => ({ at: p.at, value: p.price }))} height={140} zeroLine={false} color="var(--color-accent)" formatY={fmtPrice} formatX={(iso) => `${fmtDay(iso)} ${fmtTime(iso)}`} />;
}

/** Two-sided comparison bar for a single statistic. */
export function StatCompare({
  label,
  home,
  away,
  higherIsBetter,
  format,
}: {
  label: string;
  home: number | null;
  away: number | null;
  higherIsBetter: boolean;
  format: (v: number) => string;
}) {
  if (home === null || away === null) {
    return (
      <div className="py-2.5">
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-fg-faint">—</span>
          <span className="text-fg-muted">{label}</span>
          <span className="text-fg-faint">—</span>
        </div>
        <p className="mt-1 text-center text-[11px] text-warn">Źródło nie dostarcza tych danych</p>
      </div>
    );
  }
  const total = Math.abs(home) + Math.abs(away) || 1;
  const homeBetter = higherIsBetter ? home > away : home < away;
  const awayBetter = higherIsBetter ? away > home : away < home;
  return (
    <div className="py-2.5">
      <div className="tnum flex items-center justify-between text-[13px]">
        <span className={cn("font-semibold", homeBetter ? "text-fg" : "text-fg-muted")}>{format(home)}</span>
        <span className="text-fg-muted">{label}</span>
        <span className={cn("font-semibold", awayBetter ? "text-fg" : "text-fg-muted")}>{format(away)}</span>
      </div>
      <div className="mt-1.5 flex gap-1">
        <div className="flex h-1.5 flex-1 justify-end overflow-hidden rounded-full bg-ink-700">
          <div className={cn("h-full rounded-full", homeBetter ? "bg-accent" : "bg-fg-faint/60")} style={{ width: `${(Math.abs(home) / total) * 100}%` }} />
        </div>
        <div className="flex h-1.5 flex-1 overflow-hidden rounded-full bg-ink-700">
          <div className={cn("h-full rounded-full", awayBetter ? "bg-accent-blue" : "bg-fg-faint/60")} style={{ width: `${(Math.abs(away) / total) * 100}%` }} />
        </div>
      </div>
    </div>
  );
}

/** Stacked outcome bar: model vs margin-free market. */
export function OutcomeBars({ rows }: { rows: { label: string; model: number; market: number }[] }) {
  const colors = ["bg-accent", "bg-fg-faint", "bg-accent-blue"];
  const Bar = ({ k }: { k: "model" | "market" }) => (
    <div className="flex h-7 w-full overflow-hidden rounded-lg">
      {rows.map((r, i) => (
        <div key={r.label} className={cn("tnum grid place-items-center text-[11px] font-semibold text-ink-950", colors[i % 3], i > 0 && "border-l-2 border-ink-850")} style={{ width: `${r[k] * 100}%` }}>
          {r[k] > 0.12 ? fmtPct(r[k], 0) : ""}
        </div>
      ))}
    </div>
  );
  return (
    <div className="space-y-2.5">
      <div>
        <div className="mb-1 text-[11px] text-fg-faint">Model</div>
        <Bar k="model" />
      </div>
      <div>
        <div className="mb-1 text-[11px] text-fg-faint">Rynek (bez marży)</div>
        <Bar k="market" />
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-[11px] text-fg-muted">
        {rows.map((r, i) => (
          <span key={r.label} className="flex items-center gap-1.5">
            <span className={cn("size-2 rounded-sm", colors[i % 3])} />
            {r.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Reliability diagram: predicted vs observed hit rate. */
export function CalibrationChart({ bins }: { bins: { predicted: number; observed: number; count: number }[] }) {
  const S = 240;
  const pad = 28;
  const lo = 0.2;
  const hi = 0.9;
  const s = scale(lo, hi, pad, S - 8);
  const sy = scale(lo, hi, S - pad, 8);
  const maxN = Math.max(1, ...bins.map((b) => b.count));
  if (!bins.length) return <div className="grid h-40 place-items-center text-xs text-fg-faint">Za mało rozliczonych typów do kalibracji</div>;
  return (
    <svg viewBox={`0 0 ${S} ${S}`} className="mx-auto w-full max-w-[280px]" role="img" aria-label="Wykres kalibracji">
      {[0.3, 0.5, 0.7, 0.9].map((v) => (
        <g key={v}>
          <line x1={s(v)} x2={s(v)} y1={8} y2={S - pad} stroke="var(--color-line)" />
          <line x1={pad} x2={S - 8} y1={sy(v)} y2={sy(v)} stroke="var(--color-line)" />
          <text x={s(v)} y={S - pad + 14} fontSize={9} textAnchor="middle" fill="var(--color-fg-faint)">
            {Math.round(v * 100)}%
          </text>
          <text x={pad - 4} y={sy(v) + 3} fontSize={9} textAnchor="end" fill="var(--color-fg-faint)">
            {Math.round(v * 100)}%
          </text>
        </g>
      ))}
      <line x1={s(lo)} y1={sy(lo)} x2={s(hi)} y2={sy(hi)} stroke="var(--color-fg-faint)" strokeDasharray="4 4" />
      <path d={path(bins.map((b) => ({ x: s(b.predicted), y: sy(b.observed) })))} fill="none" stroke="var(--color-accent)" strokeWidth={1.5} />
      {bins.map((b) => (
        <circle key={b.predicted} cx={s(b.predicted)} cy={sy(b.observed)} r={3 + (b.count / maxN) * 4} fill="var(--color-accent)" fillOpacity={0.85} stroke="var(--color-ink-850)" strokeWidth={1.5} />
      ))}
      <text x={S / 2 + 10} y={S - 2} fontSize={9} textAnchor="middle" fill="var(--color-fg-muted)">
        Prognozowane
      </text>
    </svg>
  );
}

/** Horizontal bars for ROI by segment. */
export function RoiBars({ rows }: { rows: { label: string; value: number; sub: string }[] }) {
  const max = Math.max(0.05, ...rows.map((r) => Math.abs(r.value)));
  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <div key={r.label}>
          <div className="tnum mb-1 flex items-baseline justify-between gap-2 text-[13px]">
            <span className="truncate text-fg-muted">{r.label}</span>
            <span className={cn("shrink-0 font-semibold", r.value >= 0 ? "text-pos" : "text-neg")}>
              {r.value >= 0 ? "+" : "−"}
              {fmtDec(Math.abs(r.value * 100), 1)}% <span className="ml-1 text-[11px] font-normal text-fg-faint">{r.sub}</span>
            </span>
          </div>
          <div className="relative h-1.5 rounded-full bg-ink-700">
            <div className="absolute inset-y-0 left-1/2 w-px bg-fg-faint/40" />
            <div
              className={cn("absolute inset-y-0 rounded-full", r.value >= 0 ? "bg-pos" : "bg-neg")}
              style={r.value >= 0 ? { left: "50%", width: `${(r.value / max) * 50}%` } : { right: "50%", width: `${(-r.value / max) * 50}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
