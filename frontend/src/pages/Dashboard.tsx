import { useMemo, useState } from "react";
import { LuBell, LuRefreshCw, LuSparkles, LuCircleSlash, LuArrowRight } from "react-icons/lu";
import { useData, useQuery } from "../api/DataContext";
import { Logo } from "../components/layout/Logo";
import { ResponsibleNote } from "../components/layout/AppShell";
import { Card, DemoBadge, EmptyState, SectionHeader, Skeleton } from "../components/ui/primitives";
import { FreshnessDot, ScoreRing } from "../components/ui/indicators";
import { Sheet } from "../components/ui/Sheet";
import { TipCard } from "../components/match/TipCard";
import { TeamCrest } from "../components/match/TeamCrest";
import { SportIcon } from "../components/match/SportIcon";
import { NotificationList } from "../components/layout/NotificationList";
import { topTips, visibleRecs } from "../lib/selectors";
import { fmtAgo, fmtKickoff, fmtLongDay, fmtPct, fmtPrice, fmtTime, plural } from "../lib/format";
import { navigate } from "../router";
import { bookmakerName } from "../lib/bookmakers";
import { cn } from "../lib/cn";
import { AppPicksCard } from "../components/match/AppPicks";
import { appPicks } from "../lib/picks";

export function DashboardPage() {
  const { settings, refresh } = useData();
  const summary = useQuery((p) => p.getDashboard());
  const events = useQuery((p) => p.getEvents({ toDays: 7 }));
  const notifications = useQuery((p) => p.getNotifications());
  const [notifOpen, setNotifOpen] = useState(false);
  const [seen, setSeen] = useState(false);
  const { provider } = useData();

  const tips = useMemo(() => (events.data ? topTips(events.data, settings, 10) : []), [events.data, settings]);
  const todayTips = useMemo(() => tips.filter((t) => Date.parse(t.event.kickoff) - Date.now() < 24 * 3_600_000), [tips]);
  const featured = todayTips[0] ?? null;
  const rest = tips.filter((t) => t !== featured).slice(0, 3);
  const upcoming = useMemo(() => (events.data ?? []).slice(0, 8), [events.data]);
  const picks = useMemo(() => (events.data ? appPicks(events.data, { sports: settings.sports, stakeTax: settings.stakeTax, limit: 5, withinHours: 36 }) : []), [events.data, settings]);
  const unread = seen ? 0 : (notifications.data ?? []).filter((n) => !n.read).length;
  const s = summary.data;

  return (
    <div className="animate-fade-up">
      <header className="flex items-center justify-between pt-5 pb-1">
        <Logo />
        <button
          type="button"
          onClick={() => {
            setNotifOpen(true);
            setSeen(true);
            provider.markNotificationsRead();
          }}
          className="relative grid size-11 place-items-center rounded-full bg-ink-850 text-fg-muted ring-1 ring-line transition-colors hover:text-fg"
          aria-label={`Powiadomienia${unread ? `, nieprzeczytane: ${unread}` : ""}`}
        >
          <LuBell className="size-5" />
          {unread > 0 && <span className="tnum absolute -top-0.5 -right-0.5 grid size-5 place-items-center rounded-full bg-accent text-[10px] font-bold text-ink-950">{unread}</span>}
        </button>
      </header>

      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-fg-muted">{capitalize(fmtLongDay(new Date()))}</p>
        <button type="button" onClick={refresh} className="flex h-8 items-center gap-1.5 rounded-full bg-ink-850 px-3 text-[11px] text-fg-muted ring-1 ring-line hover:text-fg" aria-label="Odśwież dane">
          <FreshnessDot freshness={s ? s.dataFreshness : "missing"} pulse />
          {s ? `${s.origin === "demo" ? "Dane DEMO" : s.offline ? "Offline" : s.dataFreshness === "stale" ? "Dane nieaktualne" : "Aktualizacja"} · ${s.origin === "demo" ? fmtTime(s.generatedAt) : fmtAgo(s.generatedAt)}` : "Ładowanie…"}
          <LuRefreshCw className={cn("size-3.5", (summary.loading || events.loading) && "animate-spin")} />
        </button>
      </div>

      {/* Summary */}
      <section className="mt-4">
        <div className="relative overflow-hidden rounded-[1.4rem] border border-line-strong bg-[linear-gradient(135deg,#112038_0%,#0e1525_55%,#0b1a24_100%)] p-5 shadow-card">
          <div className="pointer-events-none absolute -top-20 -right-16 size-56 rounded-full bg-accent/10 blur-3xl" />
          <div className="relative flex items-start justify-between">
            <div>
              <div className="text-xs font-medium text-fg-muted">Podsumowanie analiz · 7 dni</div>
              <div className="mt-1 flex items-baseline gap-2">
                {s ? <span className="tnum text-4xl font-bold tracking-tight">{s.valueBets}</span> : <Skeleton className="h-10 w-14" />}
                <span className="text-sm text-fg-muted">{s ? plural(s.valueBets, "okazja z dodatnim EV", "okazje z dodatnim EV", "okazji z dodatnim EV") : ""}</span>
              </div>
            </div>
            {s?.origin === "demo" && <DemoBadge />}
          </div>
          <div className="relative mt-5 grid grid-cols-3 gap-2">
            <Kpi label="Analizy" value={s ? String(s.analyzedEvents) : null} hint="wydarzeń" />
            <Kpi label="Śr. EV" value={s ? (s.avgEv === null ? "—" : `+${fmtPct(s.avgEv)}`) : null} hint="okazji" tone="pos" />
            <Kpi label="Wycofane" value={s ? String(s.withdrawnToday) : null} hint={s && s.staleSources ? `${s.staleSources} nieakt. kursy` : s ? plural(s.withdrawnToday, "typ", "typy", "typów") : ""} tone={s && s.withdrawnToday ? "warn" : undefined} />
          </div>
        </div>
      </section>

      {/* Best of the day */}
      <section className="mt-7">
        <SectionHeader title="Najlepsza okazja dnia" subtitle="Najwyższa ocena analizy w ciągu 24 h" />
        {events.loading ? (
          <Skeleton className="h-56 w-full rounded-[1.25rem]" />
        ) : featured ? (
          <FeaturedTip tip={featured} />
        ) : (
          <Card>
            <EmptyState icon={<LuCircleSlash className="size-5" />} title="Brak zakładów spełniających kryteria w ciągu 24 h" body="Nie rekomendujemy obstawiania na siłę. Sprawdź kolejne dni w zakładce Mecze." />
          </Card>
        )}
      </section>

      {/* App picks (one per match) for building a coupon */}
      {picks.length > 0 && (
        <section className="mt-7">
          <AppPicksCard picks={picks} title="Typy aplikacji na dziś i jutro" subtitle="Po jednym typie na mecz — szybko zbudujesz z nich kupon" />
        </section>
      )}

      {/* Top tips */}
      <section className="mt-7">
        <SectionHeader title="TOP rekomendacje" subtitle={`${tips.length} z maks. 10 spełnia Twoje kryteria`} action="Wszystkie" onAction={() => navigate("/typy")} />
        <div className="space-y-3">
          {events.loading
            ? [0, 1].map((i) => <Skeleton key={i} className="h-48 w-full rounded-[1.25rem]" />)
            : rest.map((t, i) => <TipCard key={t.rec.id} event={t.event} rec={t.rec} rank={i + 2} className="animate-fade-up" />)}
        </div>
      </section>

      {/* Upcoming */}
      <section className="mt-7">
        <SectionHeader title="Nadchodzące mecze" action="Kalendarz" onAction={() => navigate("/mecze")} />
        <div className="no-scrollbar -mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1">
          {events.loading
            ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-36 w-44 shrink-0 rounded-[1.25rem]" />)
            : upcoming.map((e) => {
                const rec = visibleRecs(e, settings)[0];
                return (
                  <button
                    key={e.id}
                    type="button"
                    onClick={() => navigate(`/mecz/${encodeURIComponent(e.id)}`)}
                    className="card w-44 shrink-0 snap-start p-3.5 text-left transition-transform active:scale-[0.97]"
                  >
                    <div className="flex items-center gap-1.5 text-[10px] text-fg-faint">
                      <SportIcon sport={e.sport} className="size-3" />
                      <span className="truncate">{e.league.name}</span>
                    </div>
                    <div className="mt-2.5 flex items-center -space-x-1.5">
                      <TeamCrest team={e.home} size={28} />
                      <TeamCrest team={e.away} size={28} />
                    </div>
                    <div className="mt-2 truncate text-[13px] font-semibold">{e.home.shortName} – {e.away.shortName}</div>
                    <div className="tnum mt-0.5 text-[11px] text-fg-faint">{fmtKickoff(e.kickoff)}</div>
                    <div className={cn("mt-2.5 truncate rounded-lg px-2 py-1 text-[11px] font-medium", rec ? "bg-pos/10 text-pos" : "bg-white/[0.04] text-fg-faint")}>
                      {rec ? `${rec.label} @ ${fmtPrice(rec.price)}` : "Brak typu"}
                    </div>
                  </button>
                );
              })}
        </div>
      </section>

      {/* Recent updates */}
      <section className="mt-7">
        <SectionHeader title="Ostatnie aktualizacje" action="Wszystkie" onAction={() => setNotifOpen(true)} />
        <Card className="px-4 py-1">{notifications.data ? <NotificationList items={notifications.data.slice(0, 3)} compact /> : <Skeleton className="my-3 h-24" />}</Card>
      </section>

      <ResponsibleNote className="mt-8" />

      <Sheet open={notifOpen} onClose={() => setNotifOpen(false)} title="Powiadomienia">
        <NotificationList items={notifications.data ?? []} onOpen={() => setNotifOpen(false)} />
      </Sheet>
    </div>
  );
}

const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function Kpi({ label, value, hint, tone }: { label: string; value: string | null; hint: string; tone?: "pos" | "warn" }) {
  return (
    <div className="rounded-xl bg-white/[0.035] px-3 py-2.5 ring-1 ring-inset ring-white/[0.05]">
      <div className="truncate text-[10px] font-medium tracking-wide text-fg-faint uppercase">{label}</div>
      {value === null ? (
        <Skeleton className="mt-1.5 h-5 w-10" />
      ) : (
        <div className={cn("tnum mt-1 text-lg font-bold", tone === "pos" && "text-pos", tone === "warn" && "text-warn")}>{value}</div>
      )}
      <div className="truncate text-[10px] text-fg-faint">{hint}</div>
    </div>
  );
}

function FeaturedTip({ tip }: { tip: ReturnType<typeof topTips>[number] }) {
  const { event, rec } = tip;
  return (
    <button
      type="button"
      onClick={() => navigate(`/mecz/${encodeURIComponent(event.id)}`)}
      className="relative block w-full overflow-hidden rounded-[1.25rem] p-px text-left shadow-glow transition-transform active:scale-[0.985]"
      style={{ background: "linear-gradient(135deg, rgb(47 214 234 / .55), rgb(79 141 255 / .25) 40%, rgb(255 255 255 / .06))" }}
    >
      <div className="relative rounded-[calc(1.25rem-1px)] bg-ink-850 p-4">
        <div className="pointer-events-none absolute inset-0 rounded-[inherit] bg-[radial-gradient(80%_60%_at_100%_0%,rgb(47_214_234/0.12),transparent)]" />
        <div className="relative flex items-center gap-2 text-[11px] text-fg-faint">
          <span className="flex items-center gap-1 rounded-full bg-accent/12 px-2 py-0.5 font-semibold text-accent">
            <LuSparkles className="size-3" /> Okazja dnia
          </span>
          {event.origin === "demo" && <DemoBadge />}
          <span className="tnum ml-auto">{fmtKickoff(event.kickoff)}</span>
        </div>
        <div className="relative mt-4 flex items-center justify-between gap-2">
          <div className="flex min-w-0 flex-1 flex-col items-center gap-1.5 text-center">
            <TeamCrest team={event.home} size={44} />
            <span className="line-clamp-2 w-full text-[13px] leading-tight font-semibold">{event.home.name}</span>
          </div>
          <div className="shrink-0 text-center">
            <div className="text-[10px] tracking-wider text-fg-faint uppercase">{event.league.name}</div>
            <div className="mt-1 text-xs font-medium text-fg-muted">vs</div>
          </div>
          <div className="flex min-w-0 flex-1 flex-col items-center gap-1.5 text-center">
            <TeamCrest team={event.away} size={44} />
            <span className="line-clamp-2 w-full text-[13px] leading-tight font-semibold">{event.away.name}</span>
          </div>
        </div>
        <div className="relative mt-4 rounded-2xl bg-ink-950/50 p-3.5 ring-1 ring-inset ring-line">
          <div className="text-[11px] text-fg-faint">Rekomendowany typ</div>
          <div className="mt-0.5 text-base leading-snug font-semibold">{rec.label}</div>
          <div className="mt-3 flex items-center gap-3">
            <ScoreRing value={rec.quality} size={44} />
            <div className="tnum min-w-0 flex-1 text-xs leading-relaxed text-fg-muted">
              <div>
                Model <b className="text-fg">{fmtPct(rec.modelProb)}</b>
              </div>
              <div>
                Impl. {fmtPct(rec.impliedProb)} · <span className="font-semibold text-pos">EV +{fmtPct(rec.ev)}</span>
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="tnum text-2xl leading-none font-bold">{fmtPrice(rec.price)}</div>
              <div className="mt-1 text-[10px] text-fg-faint">{bookmakerName(rec.bookmaker)}</div>
            </div>
          </div>
        </div>
        <div className="relative mt-3 flex items-center justify-between text-[11px] text-fg-faint">
          <span>Aktualizacja {fmtAgo(rec.updatedAt)}</span>
          <span className="flex items-center gap-1 font-semibold text-accent">
            Analiza <LuArrowRight className="size-3.5" />
          </span>
        </div>
      </div>
    </button>
  );
}
