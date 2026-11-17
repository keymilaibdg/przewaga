import { LuShieldAlert, LuShieldCheck, LuShield } from "react-icons/lu";
import type { Freshness, RiskLevel } from "../../types/domain";
import { cn } from "../../lib/cn";
import { fmtPct, fmtSignedPct, freshnessLabel, qualityTier, riskLabel } from "../../lib/format";
import { Badge } from "./primitives";

const tierColor = {
  strong: "var(--color-pos)",
  good: "var(--color-accent)",
  ok: "var(--color-accent-blue)",
  weak: "var(--color-warn)",
  none: "var(--color-fg-faint)",
} as const;

/** Signal-quality ring (0–100). Explicitly not a win probability. */
export function ScoreRing({ value, size = 48, stroke = 4, showLabel = true }: { value: number; size?: number; stroke?: number; showLabel?: boolean }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const tier = qualityTier(value);
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} title={`Ocena analizy: ${value}/100 — ${tier.label}`} aria-label={`Ocena analizy ${value} na 100`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-ink-700)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={tierColor[tier.tone]}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${(c * value) / 100} ${c}`}
          style={{ transition: "stroke-dasharray .8s cubic-bezier(.22,1,.36,1)" }}
        />
      </svg>
      {showLabel && (
        <span className="tnum absolute inset-0 grid place-items-center font-bold text-fg" style={{ fontSize: size * 0.3 }}>
          {value}
        </span>
      )}
    </div>
  );
}

export function EvPill({ ev, className }: { ev: number; className?: string }) {
  const tone = ev > 0 ? "pos" : ev < 0 ? "neg" : "neutral";
  return (
    <Badge tone={tone} className={cn("tnum", className)}>
      EV {fmtSignedPct(ev)}
    </Badge>
  );
}

export function RiskBadge({ risk, compact }: { risk: RiskLevel; compact?: boolean }) {
  const tone = risk === "low" ? "pos" : risk === "medium" ? "warn" : "neg";
  const Icon = risk === "low" ? LuShieldCheck : risk === "medium" ? LuShield : LuShieldAlert;
  return (
    <Badge tone={tone} icon={<Icon className="size-3" />}>
      {compact ? riskLabel[risk] : `Ryzyko: ${riskLabel[risk].toLowerCase()}`}
    </Badge>
  );
}

const freshColor: Record<Freshness, string> = {
  fresh: "bg-pos text-pos",
  aging: "bg-warn text-warn",
  stale: "bg-neg text-neg",
  missing: "bg-fg-faint text-fg-faint",
};

export function FreshnessDot({ freshness, pulse }: { freshness: Freshness; pulse?: boolean }) {
  return <span className={cn("inline-block size-1.5 shrink-0 rounded-full", freshColor[freshness], pulse && freshness === "fresh" && "animate-pulse-dot")} />;
}

export function FreshnessLabel({ freshness, text }: { freshness: Freshness; text?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-fg-muted">
      <FreshnessDot freshness={freshness} />
      {text ?? freshnessLabel[freshness]}
    </span>
  );
}

/**
 * Model probability (with uncertainty band) against the bookmaker-implied probability.
 * Green fill when the model sits above implied, amber when the interval straddles it.
 */
export function ProbBar({ model, low, high, implied, className }: { model: number; low: number; high: number; implied: number; className?: string }) {
  const above = low > implied;
  return (
    <div className={cn("w-full", className)}>
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-ink-700">
        <div className="absolute inset-y-0 rounded-full bg-white/[0.08]" style={{ left: `${low * 100}%`, width: `${(high - low) * 100}%` }} />
        <div className={cn("absolute inset-y-0 left-0 rounded-full", above ? "bg-pos" : "bg-accent")} style={{ width: `${model * 100}%`, transition: "width .8s cubic-bezier(.22,1,.36,1)" }} />
      </div>
      <div className="relative h-0">
        <span className="absolute -top-3 h-4 w-0.5 -translate-x-1/2 rounded-full bg-fg" style={{ left: `${implied * 100}%` }} title={`Prawdopodobieństwo implikowane ${fmtPct(implied)}`} />
      </div>
    </div>
  );
}

export function ProbLegend({ model, implied, low, high }: { model: number; implied: number; low: number; high: number }) {
  return (
    <div className="tnum mt-2 flex items-center justify-between text-[11px] text-fg-faint">
      <span>
        Model <b className="font-semibold text-fg">{fmtPct(model)}</b>
        <span className="ml-1">({fmtPct(low, 0)}–{fmtPct(high, 0)})</span>
      </span>
      <span className="flex items-center gap-1">
        <span className="inline-block h-2.5 w-0.5 rounded-full bg-fg" /> Implikowane <b className="font-semibold text-fg-muted">{fmtPct(implied)}</b>
      </span>
    </div>
  );
}
