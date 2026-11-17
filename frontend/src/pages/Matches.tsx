import { useMemo, useState } from "react";
import { LuCalendarDays, LuList, LuSearch, LuX, LuCalendarX } from "react-icons/lu";
import { useData, useQuery } from "../api/DataContext";
import { PageHeader } from "../components/layout/AppShell";
import { Card, EmptyState, FilterChip, Segmented, Skeleton } from "../components/ui/primitives";
import { MatchCard } from "../components/match/MatchCard";
import { SportIcon } from "../components/match/SportIcon";
import { attractiveness, visibleRecs } from "../lib/selectors";
import { dateKey, fmtDay, plural } from "../lib/format";
import { cn } from "../lib/cn";
import type { Sport, SportEvent } from "../types/domain";

type Range = "today" | "tomorrow" | "3d" | "7d";
type View = "list" | "calendar";

export function MatchesPage({ initialSport, initialView }: { initialSport?: string | null; initialView?: string | null }) {
  const { settings } = useData();
  const events = useQuery((p) => p.getEvents({ toDays: 8 }));
  const [sport, setSport] = useState<Sport | "all">(initialSport === "football" || initialSport === "basketball" ? initialSport : "all");
  const [view, setView] = useState<View>(initialView === "kalendarz" ? "calendar" : "list");
  const [range, setRange] = useState<Range>("3d");
  const [order, setOrder] = useState<"value" | "time">("value");
  const [league, setLeague] = useState<string | null>(null);
  const [onlyValue, setOnlyValue] = useState(false);
  const [q, setQ] = useState("");

  const bySport = useMemo(() => (events.data ?? []).filter((e) => sport === "all" || e.sport === sport), [events.data, sport]);
  const leagues = useMemo(() => [...new Map(bySport.map((e) => [e.league.id, e.league.name])).entries()], [bySport]);

  const filtered = useMemo(() => {
    const today = dateKey(new Date());
    const tomorrow = dateKey(new Date(Date.now() + 86_400_000));
    const limitMs = { today: 0, tomorrow: 0, "3d": 3 * 86_400_000, "7d": 7 * 86_400_000 }[range];
    const needle = q.trim().toLowerCase();
    return bySport.filter((e) => {
      const k = dateKey(e.kickoff);
      if (range === "today" && k !== today) return false;
      if (range === "tomorrow" && k !== tomorrow) return false;
      if ((range === "3d" || range === "7d") && Date.parse(e.kickoff) - Date.now() > limitMs) return false;
      if (league && e.league.id !== league) return false;
      if (onlyValue && !visibleRecs(e, settings).length) return false;
      if (needle && !`${e.home.name} ${e.away.name} ${e.league.name}`.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [bySport, range, league, onlyValue, q, settings]);

  const sorted = useMemo(
    () => [...filtered].sort((a, b) => (order === "value" ? attractiveness(b, settings) - attractiveness(a, settings) : 0) || Date.parse(a.kickoff) - Date.parse(b.kickoff)),
    [filtered, order, settings],
  );

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Mecze"
        subtitle={events.data ? `${filtered.length} ${plural(filtered.length, "wydarzenie", "wydarzenia", "wydarzeń")}` : "Ładowanie…"}
        actions={
          <Segmented
            size="sm"
            className="w-24"
            value={view}
            onChange={setView}
            options={[
              { value: "list", label: <LuList className="size-4" aria-label="Lista" /> },
              { value: "calendar", label: <LuCalendarDays className="size-4" aria-label="Kalendarz" /> },
            ]}
          />
        }
      />

      <Segmented
        value={sport}
        onChange={(v) => {
          setSport(v);
          setLeague(null);
        }}
        options={[
          { value: "all", label: "Wszystkie" },
          { value: "football", label: <><SportIcon sport="football" className="size-4" /> Piłka</> },
          { value: "basketball", label: <><SportIcon sport="basketball" className="size-4" /> Kosz</> },
        ]}
      />

      {view === "list" ? (
        <>
          <div className="relative mt-3">
            <LuSearch className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-fg-faint" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Szukaj drużyny lub ligi"
              className="h-11 w-full rounded-xl bg-ink-850 pr-10 pl-10 text-sm text-fg ring-1 ring-line outline-none placeholder:text-fg-faint focus:ring-accent/50"
              aria-label="Szukaj wydarzeń"
            />
            {q && (
              <button type="button" onClick={() => setQ("")} className="absolute top-1/2 right-2 grid size-8 -translate-y-1/2 place-items-center rounded-full text-fg-faint" aria-label="Wyczyść">
                <LuX className="size-4" />
              </button>
            )}
          </div>

          <div className="mt-3 grid grid-cols-4 gap-1.5">
            {(
              [
                ["today", "Dziś"],
                ["tomorrow", "Jutro"],
                ["3d", "3 dni"],
                ["7d", "7 dni"],
              ] as const
            ).map(([k, l]) => (
              <button
                key={k}
                type="button"
                onClick={() => setRange(k)}
                className={cn("h-9 rounded-lg text-[13px] font-medium transition-colors", range === k ? "bg-accent/15 text-accent ring-1 ring-inset ring-accent/30" : "bg-ink-850 text-fg-muted ring-1 ring-inset ring-line")}
              >
                {l}
              </button>
            ))}
          </div>

          <div className="no-scrollbar -mx-4 mt-3 flex gap-2 overflow-x-auto px-4">
            <FilterChip active={onlyValue} onClick={() => setOnlyValue((v) => !v)}>Tylko z typem</FilterChip>
            <FilterChip active={order === "time"} onClick={() => setOrder((o) => (o === "time" ? "value" : "time"))}>
              {order === "time" ? "Wg godziny" : "Wg atrakcyjności"}
            </FilterChip>
            <span className="mx-1 w-px shrink-0 self-stretch bg-line" />
            {leagues.map(([id, name]) => (
              <FilterChip key={id} active={league === id} onClick={() => setLeague((l) => (l === id ? null : id))}>
                {name}
              </FilterChip>
            ))}
          </div>

          <div className="mt-4 space-y-3">
            {events.loading ? (
              [0, 1, 2].map((i) => <Skeleton key={i} className="h-44 w-full rounded-[1.25rem]" />)
            ) : sorted.length ? (
              sorted.map((e) => <MatchCard key={e.id} event={e} rec={visibleRecs(e, settings)[0]} className="animate-fade-up" />)
            ) : (
              <Card>
                <EmptyState icon={<LuCalendarX className="size-5" />} title="Brak wydarzeń dla wybranych filtrów" body="Zmień zakres dat, ligę lub wyczyść wyszukiwanie." />
              </Card>
            )}
          </div>
        </>
      ) : (
        <CalendarView events={bySport} loading={events.loading} />
      )}
    </div>
  );
}

function CalendarView({ events, loading }: { events: SportEvent[]; loading: boolean }) {
  const { settings } = useData();
  const days = useMemo(() => Array.from({ length: 8 }, (_, i) => new Date(Date.now() + i * 86_400_000)), []);
  const [selected, setSelected] = useState(dateKey(days[0]));
  const byDay = useMemo(() => {
    const m = new Map<string, SportEvent[]>();
    for (const e of events) m.set(dateKey(e.kickoff), [...(m.get(dateKey(e.kickoff)) ?? []), e]);
    return m;
  }, [events]);
  const dayEvents = (byDay.get(selected) ?? []).sort((a, b) => Date.parse(a.kickoff) - Date.parse(b.kickoff));
  const weekday = new Intl.DateTimeFormat("pl-PL", { weekday: "short", timeZone: "Europe/Warsaw" });
  const dayNum = new Intl.DateTimeFormat("pl-PL", { day: "numeric", timeZone: "Europe/Warsaw" });

  return (
    <>
      <div className="no-scrollbar -mx-4 mt-4 flex gap-2 overflow-x-auto px-4 pb-1">
        {days.map((d) => {
          const k = dateKey(d);
          const evs = byDay.get(k) ?? [];
          const values = evs.filter((e) => visibleRecs(e, settings).length).length;
          const active = k === selected;
          return (
            <button
              key={k}
              type="button"
              onClick={() => setSelected(k)}
              className={cn(
                "flex w-14 shrink-0 flex-col items-center rounded-2xl py-2.5 ring-1 ring-inset transition-colors",
                active ? "bg-accent text-ink-950 ring-accent" : "bg-ink-850 text-fg ring-line",
              )}
            >
              <span className={cn("text-[11px] font-medium first-letter:uppercase", active ? "text-ink-950/70" : "text-fg-faint")}>{weekday.format(d).replace(".", "")}</span>
              <span className="tnum mt-0.5 text-lg font-bold">{dayNum.format(d)}</span>
              <span className={cn("tnum mt-1 text-[10px]", active ? "text-ink-950/70" : "text-fg-faint")}>{evs.length} mecz.</span>
              <span className={cn("mt-1 size-1.5 rounded-full", values ? (active ? "bg-ink-950" : "bg-pos") : "bg-transparent")} />
            </button>
          );
        })}
      </div>
      <p className="mt-2 px-1 text-[11px] text-fg-faint">
        <span className="mr-1 inline-block size-1.5 rounded-full bg-pos align-middle" /> dzień z co najmniej jednym typem spełniającym kryteria
      </p>
      <h2 className="mt-5 mb-3 px-1 text-[15px] font-semibold first-letter:uppercase">{fmtDay(dayEvents[0]?.kickoff ?? new Date(selected).toISOString())}</h2>
      <div className="space-y-3">
        {loading ? (
          <Skeleton className="h-44 w-full rounded-[1.25rem]" />
        ) : dayEvents.length ? (
          dayEvents.map((e) => <MatchCard key={e.id} event={e} rec={visibleRecs(e, settings)[0]} className="animate-fade-up" />)
        ) : (
          <Card>
            <EmptyState icon={<LuCalendarX className="size-5" />} title="Brak wydarzeń tego dnia" />
          </Card>
        )}
      </div>
    </>
  );
}
