import { LuChevronRight, LuCircleSlash, LuTriangleAlert } from "react-icons/lu";
import type { Recommendation, SportEvent } from "../../types/domain";
import { cn } from "../../lib/cn";
import { fmtKickoff, fmtPct, fmtPrice } from "../../lib/format";
import { oddsFreshness } from "../../lib/selectors";
import { navigate } from "../../router";
import { bookmakerName } from "../../lib/bookmakers";
import { DemoBadge } from "../ui/primitives";
import { EvPill, FreshnessDot, ScoreRing } from "../ui/indicators";
import { TeamCrest } from "./TeamCrest";
import { SportIcon } from "./SportIcon";

/** List card for an event: teams, kickoff, best visible recommendation or an explicit "no bet". */
export function MatchCard({ event, rec, className }: { event: SportEvent; rec: Recommendation | undefined; className?: string }) {
  const fresh = oddsFreshness(event);
  return (
    <button
      type="button"
      onClick={() => navigate(`/mecz/${encodeURIComponent(event.id)}`)}
      className={cn("card group block w-full p-4 text-left transition-transform duration-200 active:scale-[0.985]", className)}
    >
      <div className="flex items-center justify-between gap-2 text-[11px] text-fg-faint">
        <span className="flex min-w-0 items-center gap-1.5">
          <SportIcon sport={event.sport} className="size-3.5 shrink-0" />
          <span className="truncate font-medium text-fg-muted">{event.league.name}</span>
          {event.origin === "demo" && <DemoBadge />}
        </span>
        <span className="tnum flex shrink-0 items-center gap-1.5">
          <FreshnessDot freshness={fresh} />
          {fmtKickoff(event.kickoff)}
        </span>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <div className="min-w-0 flex-1 space-y-2">
          <TeamRow name={event.home.name} team={event.home} />
          <TeamRow name={event.away.name} team={event.away} />
        </div>
        {rec ? <ScoreRing value={rec.quality} size={46} /> : <LuChevronRight className="size-5 text-fg-faint transition-transform group-hover:translate-x-0.5" />}
      </div>

      {rec ? (
        <div className="mt-3.5 rounded-xl bg-ink-800/80 p-3 ring-1 ring-inset ring-line">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[11px] text-fg-faint">Rekomendowany typ</div>
              <div className="mt-0.5 truncate text-sm font-semibold text-fg">{rec.label}</div>
            </div>
            <div className="shrink-0 text-right">
              <div className="tnum text-lg leading-none font-bold text-fg">{fmtPrice(rec.price)}</div>
              <div className="mt-1 text-[10px] text-fg-faint">{bookmakerName(rec.bookmaker)}</div>
            </div>
          </div>
          <div className="tnum mt-2.5 flex items-center gap-2 text-[11px] text-fg-muted">
            <span>
              Model <b className="text-fg">{fmtPct(rec.modelProb)}</b>
            </span>
            <span className="text-fg-faint">·</span>
            <span>Impl. {fmtPct(rec.impliedProb)}</span>
            <EvPill ev={rec.ev} className="ml-auto" />
          </div>
        </div>
      ) : (
        <div className="mt-3.5 flex items-center gap-2 rounded-xl bg-ink-800/50 px-3 py-2.5 text-xs text-fg-faint ring-1 ring-inset ring-line">
          {fresh === "stale" ? <LuTriangleAlert className="size-4 shrink-0 text-warn" /> : <LuCircleSlash className="size-4 shrink-0" />}
          {fresh === "stale" ? "Kursy nieaktualne — analiza wstrzymana" : "Brak zakładu spełniającego kryteria — odpuść"}
        </div>
      )}
    </button>
  );
}

function TeamRow({ team, name }: { team: SportEvent["home"]; name: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <TeamCrest team={team} size={24} />
      <span className="truncate text-[15px] font-medium text-fg">{name}</span>
    </div>
  );
}
