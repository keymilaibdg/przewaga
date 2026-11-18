import { useMemo, useState } from "react";
import { LuCircleSlash, LuInfo } from "react-icons/lu";
import { useData, useQuery } from "../api/DataContext";
import { PageHeader, ResponsibleNote } from "../components/layout/AppShell";
import { Card, EmptyState, FilterChip, Skeleton } from "../components/ui/primitives";
import { TipCard } from "../components/match/TipCard";
import { NO_BET_MESSAGE } from "../demo/generate";
import { topTips } from "../lib/selectors";
import type { RiskLevel, Sport } from "../types/domain";
import { AppPicksCard } from "../components/match/AppPicks";
import { appPicks } from "../lib/picks";

type SortKey = "quality" | "ev" | "prob" | "ratio";

const SORTS: { key: SortKey; label: string }[] = [
  { key: "quality", label: "Ocena analizy" },
  { key: "ev", label: "Największe value" },
  { key: "prob", label: "Najwyższe prawdopodob." },
  { key: "ratio", label: "Kurs vs prawdopodob." },
];

export function TipsPage() {
  const { settings } = useData();
  const events = useQuery((p) => p.getEvents({ toDays: 7 }));
  const [sport, setSport] = useState<Sport | "all">("all");
  const [risks, setRisks] = useState<RiskLevel[]>([]);
  const [sort, setSort] = useState<SortKey>("quality");

  const list = useMemo(() => {
    if (!events.data) return [];
    let tips = topTips(events.data, settings, 50);
    if (sport !== "all") tips = tips.filter((t) => t.event.sport === sport);
    if (risks.length) tips = tips.filter((t) => risks.includes(t.rec.risk));
    const key = {
      quality: (r: (typeof tips)[number]) => r.rec.quality,
      ev: (r: (typeof tips)[number]) => r.rec.ev,
      prob: (r: (typeof tips)[number]) => r.rec.modelProb,
      ratio: (r: (typeof tips)[number]) => r.rec.modelProb / r.rec.impliedProb,
    }[sort];
    return [...tips].sort((a, b) => key(b) - key(a)).slice(0, 10);
  }, [events.data, settings, sport, risks, sort]);

  const picks = useMemo(
    () => (events.data ? appPicks(events.data, { sports: sport === "all" ? settings.sports : [sport], stakeTax: settings.stakeTax, limit: 15 }) : []),
    [events.data, settings, sport],
  );

  const toggleRisk = (r: RiskLevel) => setRisks((rs) => (rs.includes(r) ? rs.filter((x) => x !== r) : [...rs, r]));

  return (
    <div className="animate-fade-up">
      <PageHeader title="Typy" subtitle="Okazje z dodatnim EV i typy aplikacji do kuponu · najbliższe 7 dni" />

      <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 pb-2">
        <FilterChip active={sport === "all"} onClick={() => setSport("all")}>Wszystkie</FilterChip>
        <FilterChip active={sport === "football"} onClick={() => setSport("football")}>Piłka nożna</FilterChip>
        <FilterChip active={sport === "basketball"} onClick={() => setSport("basketball")}>Koszykówka</FilterChip>
        <span className="mx-1 w-px shrink-0 self-stretch bg-line" />
        <FilterChip active={risks.includes("low")} onClick={() => toggleRisk("low")}>Niskie ryzyko</FilterChip>
        <FilterChip active={risks.includes("medium")} onClick={() => toggleRisk("medium")}>Średnie</FilterChip>
        <FilterChip active={risks.includes("high")} onClick={() => toggleRisk("high")}>Wysokie</FilterChip>
      </div>

      <div className="mt-1 flex items-center gap-2">
        <span className="shrink-0 text-xs text-fg-faint">Sortuj:</span>
        <div className="no-scrollbar -mr-4 flex gap-1.5 overflow-x-auto pr-4">
          {SORTS.map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => setSort(s.key)}
              className={`h-8 shrink-0 rounded-lg px-2.5 text-xs font-medium transition-colors ${sort === s.key ? "bg-ink-700 text-fg" : "text-fg-faint hover:text-fg-muted"}`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 flex gap-2.5 rounded-xl bg-accent-blue/[0.07] p-3 text-xs leading-relaxed text-fg-muted ring-1 ring-inset ring-accent-blue/15">
        <LuInfo className="mt-0.5 size-4 shrink-0 text-accent-blue" />
        <span>
          <b className="text-fg">Ocena analizy</b> mierzy jakość sygnału (przewaga względem niepewności, kompletność i świeżość danych). To nie jest szansa wygranej — tę pokazuje pasek prawdopodobieństwa.
        </span>
      </div>

      <div className="mt-4 space-y-3">
        {events.loading ? (
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-52 w-full rounded-[1.25rem]" />)
        ) : list.length ? (
          list.map((t, i) => <TipCard key={t.rec.id} event={t.event} rec={t.rec} rank={i + 1} defaultOpen={i === 0} className="animate-fade-up" />)
        ) : (
          <Card>
            <EmptyState icon={<LuCircleSlash className="size-5" />} title={NO_BET_MESSAGE} body="Typy z przewagą (modelu lub okazje rynkowe) pojawiają się tylko, gdy są. Poniżej typy aplikacji do kuponu — bez przewagi, z uczciwą informacją o ryzyku." />
          </Card>
        )}
      </div>

      <div className="mt-6">
        <AppPicksCard picks={picks} title="Typy aplikacji (do kuponu)" subtitle="Po jednym typie na mecz z najbliższych 7 dni: okazje najpierw, potem najbardziej prawdopodobne wyniki" />
      </div>
      <ResponsibleNote className="mt-8" />
    </div>
  );
}
