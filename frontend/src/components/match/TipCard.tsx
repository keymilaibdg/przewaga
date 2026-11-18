import { useState } from "react";
import { LuArrowRight, LuChevronDown, LuCircleCheck, LuCircleAlert, LuClock } from "react-icons/lu";
import type { Recommendation, SportEvent } from "../../types/domain";
import { cn } from "../../lib/cn";
import { fmtAgo, fmtDec, fmtKickoff, fmtPct, fmtPrice, qualityTier } from "../../lib/format";
import { navigate } from "../../router";
import { bookmakerName } from "../../lib/bookmakers";
import { DemoBadge, KeyValue } from "../ui/primitives";
import { EvPill, ProbBar, ProbLegend, RiskBadge, ScoreRing } from "../ui/indicators";
import { TeamCrest } from "./TeamCrest";
import { PlPriceHint } from "./PlPrice";
import { SportIcon } from "./SportIcon";
import { MarketBadge } from "./MarketBadge";

export function TipCard({ event, rec, rank, defaultOpen = false, className }: { event: SportEvent; rec: Recommendation; rank?: number; defaultOpen?: boolean; className?: string }) {
  const [open, setOpen] = useState(defaultOpen);
  const tier = qualityTier(rec.quality);
  return (
    <article className={cn("card overflow-hidden", className)}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="block w-full p-4 text-left">
        <div className="flex items-center gap-2 text-[11px] text-fg-faint">
          {rank !== undefined && <span className="tnum grid size-5 place-items-center rounded-md bg-ink-700 text-[10px] font-bold text-fg-muted">{rank}</span>}
          <SportIcon sport={event.sport} className="size-3.5" />
          <span className="truncate font-medium text-fg-muted">{event.league.name}</span>
          {event.origin === "demo" && <DemoBadge />}
          <span className="tnum ml-auto shrink-0">{fmtKickoff(event.kickoff)}</span>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <TeamCrest team={event.home} size={22} />
          <span className="truncate text-sm font-medium text-fg-muted">
            {event.home.name} <span className="text-fg-faint">–</span> {event.away.name}
          </span>
          <TeamCrest team={event.away} size={22} />
        </div>

        <div className="mt-3 flex items-center gap-3">
          <div className="min-w-0 flex-1">
            <div className="text-[17px] leading-snug font-semibold text-fg">{rec.label}</div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <EvPill ev={rec.ev} />
              <RiskBadge risk={rec.risk} compact />
              {rec.kind === "market" && <MarketBadge />}
            </div>
          </div>
          <div className="shrink-0 text-right">
            <div className="tnum text-2xl leading-none font-bold tracking-tight">{fmtPrice(rec.price)}</div>
            <div className="mt-1.5 text-[11px] text-fg-faint">{bookmakerName(rec.bookmaker)}</div>
          </div>
        </div>

        <div className="mt-4">
          <ProbBar model={rec.modelProb} low={rec.probLow} high={rec.probHigh} implied={rec.impliedProb} />
          <ProbLegend model={rec.modelProb} low={rec.probLow} high={rec.probHigh} implied={rec.impliedProb} />
        </div>

        <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
          <div className="flex items-center gap-2.5">
            <ScoreRing value={rec.quality} size={34} stroke={3} />
            <div className="leading-tight">
              <div className="text-xs font-semibold text-fg">{tier.label}</div>
              <div className="text-[10px] text-fg-faint">Ocena analizy (nie szansa wygranej)</div>
            </div>
          </div>
          <span className="flex items-center gap-1 text-xs font-medium text-accent">
            {open ? "Zwiń" : "Uzasadnienie"}
            <LuChevronDown className={cn("size-4 transition-transform duration-300", open && "rotate-180")} />
          </span>
        </div>
      </button>

      <div className={cn("grid transition-[grid-template-rows] duration-300 ease-out", open ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
        <div className="overflow-hidden" inert={!open}>
          <div className="space-y-4 border-t border-line bg-ink-900/40 px-4 pt-4 pb-4">
            <div className="grid grid-cols-3 gap-3">
              <KeyValue label="Kurs godziwy" value={fmtPrice(1 / rec.modelProb)} />
              <KeyValue label="P. bez marży" value={fmtPct(rec.fairProb)} />
              <KeyValue label="Przewaga" value={`+${fmtDec((rec.modelProb - rec.fairProb) * 100)} p.p.`} />
            </div>
            <PlPriceHint prob={rec.modelProb} />
            <ReasonList title="Za tym typem" items={rec.reasonsFor} tone="pos" />
            <ReasonList title="Przeciw / ryzyka" items={rec.reasonsAgainst} tone="warn" />
            <div className="flex items-center justify-between gap-2 pt-1">
              <span className="flex items-center gap-1.5 text-[11px] text-fg-faint">
                <LuClock className="size-3.5" /> Aktualizacja {fmtAgo(rec.updatedAt)}
              </span>
              <button
                type="button"
                onClick={() => navigate(`/mecz/${encodeURIComponent(event.id)}`)}
                className="flex h-9 items-center gap-1.5 rounded-full bg-accent/12 px-3.5 text-xs font-semibold text-accent ring-1 ring-inset ring-accent/25 hover:bg-accent/20"
              >
                Pełna analiza <LuArrowRight className="size-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}

export function ReasonList({ title, items, tone }: { title: string; items: string[]; tone: "pos" | "warn" }) {
  const Icon = tone === "pos" ? LuCircleCheck : LuCircleAlert;
  return (
    <div>
      <div className="mb-2 text-[11px] font-semibold tracking-wide text-fg-faint uppercase">{title}</div>
      <ul className="space-y-2">
        {items.map((t) => (
          <li key={t} className="flex gap-2 text-[13px] leading-snug text-fg-muted">
            <Icon className={cn("mt-0.5 size-4 shrink-0", tone === "pos" ? "text-pos" : "text-warn")} />
            <span>{t}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
