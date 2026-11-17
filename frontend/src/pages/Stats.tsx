import { useMemo, useState } from "react";
import { LuFlaskConical, LuRadio, LuHistory } from "react-icons/lu";
import { useData, useQuery } from "../api/DataContext";
import { PageHeader, ResponsibleNote } from "../components/layout/AppShell";
import { Badge, Card, DemoBadge, EmptyState, FilterChip, KeyValue, Segmented, Skeleton } from "../components/ui/primitives";
import { AreaChart, CalibrationChart, RoiBars } from "../components/charts/charts";
import { SportIcon } from "../components/match/SportIcon";
import { bookmakerName } from "../lib/bookmakers";
import { dateKey, fmtDay, fmtDec, fmtPct, fmtPrice, fmtSignedPct, fmtUnits, plural, resultLabel } from "../lib/format";
import { cn } from "../lib/cn";
import type { BetResult, HistoryEntry, PerformanceSummary } from "../types/domain";

type Scope = "live" | "backtest";

export function StatsPage({ initialTab }: { initialTab?: string | null }) {
  const [tab, setTab] = useState<"perf" | "history">(initialTab === "historia" ? "history" : "perf");
  const [scope, setScope] = useState<Scope>("live");
  const { provider } = useData();

  return (
    <div className="animate-fade-up">
      <PageHeader title="Statystyki" subtitle="Skuteczność modelu i historia wszystkich typów" actions={provider.mode === "demo" ? <DemoBadge /> : undefined} />
      <Segmented
        value={tab}
        onChange={setTab}
        options={[
          { value: "perf", label: "Skuteczność" },
          { value: "history", label: "Historia typów" },
        ]}
      />
      <div className="mt-3 flex gap-2">
        <FilterChip active={scope === "live"} onClick={() => setScope("live")}>
          <LuRadio className="size-3.5" /> Rekomendacje
        </FilterChip>
        <FilterChip active={scope === "backtest"} onClick={() => setScope("backtest")}>
          <LuFlaskConical className="size-3.5" /> Backtest
        </FilterChip>
      </div>
      <p className="mt-2 px-1 text-[11px] leading-relaxed text-fg-faint">
        {scope === "live"
          ? "Typy faktycznie opublikowane przez aplikację, zapisane w chwili wygenerowania. Przegrane nie są usuwane."
          : "Symulacja historyczna walk-forward — dane wyłącznie sprzed meczu. Liczona osobno, nie miesza się z wynikami rekomendacji."}
      </p>
      <div key={`${tab}-${scope}`} className="animate-fade-up mt-4">
        {scope === "backtest" && !provider.hasBacktest() ? (
          <Card>
            <EmptyState icon={<LuFlaskConical className="size-5" />} title="Backtest nie jest jeszcze dostępny" body="Wyniki testów historycznych pojawią się po ETAPIE 5 (kalibracja i backtesting modeli). Nie mieszamy ich z wynikami rekomendacji." />
          </Card>
        ) : tab === "perf" ? (
          <Performance scope={scope} />
        ) : (
          <History scope={scope} />
        )}
      </div>
      <ResponsibleNote className="mt-8" />
    </div>
  );
}

function Performance({ scope }: { scope: Scope }) {
  const q = useQuery((p) => p.getPerformance(scope), [scope]);
  if (q.loading || !q.data) return <Skeleton className="h-96 w-full rounded-[1.25rem]" />;
  const s: PerformanceSummary = q.data;
  if (s.bets === 0)
    return (
      <Card>
        <EmptyState icon={<LuHistory className="size-5" />} title="Brak typów do oceny" body="Statystyki pojawią się po pierwszych rozliczonych rekomendacjach. Wszystkie typy, także przegrane i wycofane, są zapisywane." />
      </Card>
    );
  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-xs text-fg-muted">Zysk (stawka 1 j.)</div>
            <div className={cn("tnum mt-1 text-3xl font-bold tracking-tight", s.profit >= 0 ? "text-pos" : "text-neg")}>{fmtUnits(s.profit)}</div>
          </div>
          <div className="text-right">
            <div className="text-xs text-fg-muted">ROI / Yield</div>
            <div className={cn("tnum mt-1 text-xl font-bold", s.roi >= 0 ? "text-pos" : "text-neg")}>{fmtSignedPct(s.roi)}</div>
          </div>
        </div>
        <div className="mt-4">
          <AreaChart data={s.cumulative.map((c) => ({ at: c.at, value: c.profit }))} formatY={(v) => fmtUnits(v)} />
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3">
        <Card className="p-4">
          <KeyValue label="Wszystkie typy" value={s.bets} hint={`${s.pending} oczekuje · ${s.voided} ${plural(s.voided, "zwrot", "zwroty", "zwrotów")}`} />
        </Card>
        <Card className="p-4">
          <KeyValue label="Skuteczność" value={fmtPct(s.hitRate)} hint={`${s.won} trafionych / ${s.lost} nietrafionych`} />
        </Card>
        <Card className="p-4">
          <KeyValue label="Średni kurs" value={fmtPrice(s.avgPrice)} hint={`próg opłacalności ${fmtPct(1 / s.avgPrice)}`} />
        </Card>
        <Card className="p-4">
          <KeyValue
            label="CLV (śr.)"
            value={s.avgClv === null ? "—" : <span className={s.avgClv >= 0 ? "text-pos" : "text-neg"}>{fmtSignedPct(s.avgClv)}</span>}
            hint="kurs wzięty vs zamknięcia"
          />
        </Card>
      </div>

      <Card className="p-4">
        <h3 className="text-sm font-semibold">Kalibracja modelu</h3>
        <p className="mt-0.5 mb-3 text-xs text-fg-faint">Punkty na przekątnej = prognozowane prawdopodobieństwa zgadzają się z rzeczywistością. Brier: {s.brier === null ? "—" : fmtDec(s.brier, 3)}</p>
        <CalibrationChart bins={s.calibration} />
      </Card>

      <Card className="p-4">
        <h3 className="mb-3 text-sm font-semibold">Wyniki wg dyscypliny</h3>
        <RoiBars rows={s.bySport.map((r) => ({ label: r.label, value: r.roi, sub: `${r.bets} typów` }))} />
      </Card>
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-semibold">Wyniki wg rynku</h3>
        <RoiBars rows={s.byMarket.map((r) => ({ label: r.label, value: r.roi, sub: `${r.bets}` }))} />
      </Card>
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-semibold">Wyniki wg poziomu ryzyka</h3>
        <RoiBars rows={s.byRisk.map((r) => ({ label: r.label, value: r.roi, sub: `${r.bets}` }))} />
      </Card>
      {s.settled < 300 && (
        <p className="px-1 text-[11px] leading-relaxed text-warn">
          Uwaga: {s.settled} {plural(s.settled, "rozliczony typ", "rozliczone typy", "rozliczonych typów")} to za mała próba, by ocenić przewagę modelu — wynik w dużej mierze zależy od wariancji.
        </p>
      )}
    </div>
  );
}

const RESULT_TONE: Record<BetResult, "pos" | "neg" | "neutral" | "warn"> = {
  won: "pos",
  half_won: "pos",
  lost: "neg",
  half_lost: "neg",
  void: "neutral",
  pending: "warn",
  withdrawn: "neutral",
};

function History({ scope }: { scope: Scope }) {
  const q = useQuery((p) => p.getHistory(scope), [scope]);
  const [filter, setFilter] = useState<"all" | "won" | "lost" | "pending">("all");
  const [limit, setLimit] = useState(40);
  const items = useMemo(() => {
    const all = q.data ?? [];
    return filter === "all" ? all : all.filter((h) => (filter === "won" ? h.result === "won" || h.result === "half_won" : filter === "lost" ? h.result === "lost" || h.result === "half_lost" : h.result === "pending"));
  }, [q.data, filter]);
  const groups = useMemo(() => {
    const m = new Map<string, HistoryEntry[]>();
    for (const h of items.slice(0, limit)) m.set(dateKey(h.kickoff), [...(m.get(dateKey(h.kickoff)) ?? []), h]);
    return [...m.entries()];
  }, [items, limit]);

  if (q.loading) return <Skeleton className="h-96 w-full rounded-[1.25rem]" />;
  return (
    <>
      <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
        {(
          [
            ["all", "Wszystkie"],
            ["won", "Trafione"],
            ["lost", "Nietrafione"],
            ["pending", "Oczekujące"],
          ] as const
        ).map(([k, l]) => (
          <FilterChip key={k} active={filter === k} onClick={() => setFilter(k)}>
            {l}
          </FilterChip>
        ))}
      </div>
      {groups.length === 0 ? (
        <Card className="mt-4">
          <EmptyState icon={<LuHistory className="size-5" />} title="Brak typów w tej kategorii" />
        </Card>
      ) : (
        <div className="mt-4 space-y-5">
          {groups.map(([day, list]) => (
            <section key={day}>
              <h3 className="mb-2 px-1 text-xs font-semibold text-fg-faint first-letter:uppercase">{fmtDay(list[0].kickoff)}</h3>
              <Card className="divide-y divide-line px-4">
                {list.map((h) => (
                  <div key={h.id} className="py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-[13px] font-semibold">{h.label}</div>
                        <div className="mt-0.5 flex items-center gap-1.5 truncate text-[11px] text-fg-faint">
                          <SportIcon sport={h.sport} className="size-3 shrink-0" />
                          <span className="truncate">
                            {h.eventLabel} · {h.league}
                          </span>
                        </div>
                      </div>
                      <Badge tone={RESULT_TONE[h.result]}>{resultLabel[h.result]}</Badge>
                    </div>
                    <div className="tnum mt-2 flex items-center gap-3 text-[11px] text-fg-muted">
                      <span>
                        Kurs <b className="text-fg">{fmtPrice(h.openingPrice)}</b>
                        {h.closingPrice && <span className="text-fg-faint"> → {fmtPrice(h.closingPrice)}</span>}
                      </span>
                      <span>p {fmtPct(h.modelProb, 0)}</span>
                      <span>EV {fmtSignedPct(h.ev)}</span>
                      <span className="hidden sm:inline">{bookmakerName(h.bookmaker)}</span>
                      {h.finalScore && <span className="text-fg-faint">{h.finalScore}</span>}
                      <span className={cn("ml-auto font-semibold", h.profit > 0 ? "text-pos" : h.profit < 0 ? "text-neg" : "text-fg-faint")}>{h.result === "pending" ? "—" : fmtUnits(h.profit)}</span>
                    </div>
                  </div>
                ))}
              </Card>
            </section>
          ))}
          {items.length > limit && (
            <button type="button" onClick={() => setLimit((l) => l + 40)} className="h-11 w-full rounded-xl bg-ink-850 text-sm font-medium text-fg-muted ring-1 ring-line hover:text-fg">
              Pokaż więcej ({items.length - limit})
            </button>
          )}
        </div>
      )}
    </>
  );
}
