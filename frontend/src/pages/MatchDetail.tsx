import { useMemo, useState } from "react";
import { LuCircleSlash, LuClock, LuDatabase, LuTriangleAlert, LuCircleMinus, LuUserX, LuChevronDown, LuPlus, LuCheck } from "react-icons/lu";
import { useCoupon } from "../api/CouponContext";
import { PriceInsightCard } from "../components/match/PriceInsight";
import { MARKET_NOTE, MarketBadge } from "../components/match/MarketBadge";
import { useData, useQuery } from "../api/DataContext";
import { PageHeader, ResponsibleNote } from "../components/layout/AppShell";
import { Badge, Card, DemoBadge, EmptyState, KeyValue, Skeleton } from "../components/ui/primitives";
import { EvPill, FreshnessLabel, ProbBar, ProbLegend, RiskBadge, ScoreRing } from "../components/ui/indicators";
import { OddsChart, OutcomeBars, StatCompare } from "../components/charts/charts";
import { TeamCrest } from "../components/match/TeamCrest";
import { FormPills } from "../components/match/FormPills";
import { ReasonList } from "../components/match/TipCard";
import { PlPriceHint } from "../components/match/PlPrice";
import { SportIcon, sportLabel } from "../components/match/SportIcon";
import { bookmakerName, bookmakerShort } from "../lib/bookmakers";
import { NO_BET_MESSAGE } from "../demo/generate";
import { bestQuote, expectedValue, impliedProbability } from "../lib/odds";
import { visibleRecs } from "../lib/selectors";
import { fmtAgo, fmtCountdown, fmtDay, fmtDec, fmtKickoff, fmtPct, fmtPrice, fmtSignedPct, fmtTime, qualityTier } from "../lib/format";
import { cn } from "../lib/cn";
import type { MarketAnalysis, Recommendation, SelectionAnalysis, SportEvent, StatLine } from "../types/domain";

type Tab = "analysis" | "markets" | "odds" | "stats" | "lineups";
const TABS: { key: Tab; label: string }[] = [
  { key: "analysis", label: "Analiza" },
  { key: "markets", label: "Rynki" },
  { key: "odds", label: "Kursy" },
  { key: "stats", label: "Forma i statystyki" },
  { key: "lineups", label: "Składy" },
];

const SOURCE_LABEL: Record<string, string> = {
  fixtures: "Terminarz",
  odds: "Kursy",
  stats: "Statystyki",
  injuries: "Kontuzje",
  lineups: "Składy",
  xg: "xG",
};

export function MatchDetailPage({ id }: { id: string }) {
  const { settings } = useData();
  const q = useQuery((p) => p.getEvent(id), [id]);
  const [tab, setTab] = useState<Tab>("analysis");

  if (q.loading)
    return (
      <div className="space-y-3 pt-5">
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-40 w-full rounded-[1.25rem]" />
        <Skeleton className="h-64 w-full rounded-[1.25rem]" />
      </div>
    );
  if (!q.data)
    return (
      <>
        <PageHeader title="Mecz" back />
        <Card>
          <EmptyState icon={<LuCircleSlash className="size-5" />} title="Nie znaleziono wydarzenia" body="Mogło zostać usunięte z terminarza lub przełożone." />
        </Card>
      </>
    );

  const e = q.data;
  const recs = visibleRecs(e, settings);
  const withdrawn = e.recommendations.filter((r) => r.status === "withdrawn");

  return (
    <div className="animate-fade-up">
      <PageHeader
        back
        title={`${e.home.shortName} – ${e.away.shortName}`}
        subtitle={
          <span className="flex items-center gap-1.5">
            <SportIcon sport={e.sport} className="size-3.5" /> {sportLabel[e.sport]} · {e.league.name}
          </span>
        }
        actions={e.origin === "demo" ? <DemoBadge /> : undefined}
      />

      <Card className="relative overflow-hidden p-5">
        <div className="pointer-events-none absolute inset-0 opacity-60" style={{ background: `radial-gradient(60% 80% at 0% 0%, ${e.home.colors[0]}22, transparent 70%), radial-gradient(60% 80% at 100% 0%, ${e.away.colors[0]}22, transparent 70%)` }} />
        <div className="relative flex items-start justify-between gap-2">
          <TeamBlock team={e.home} form={e.formHome} label="Gospodarze" />
          <div className="shrink-0 pt-2 text-center">
            <div className="tnum text-2xl font-bold tracking-tight">{fmtTime(e.kickoff)}</div>
            <div className="mt-0.5 text-[11px] text-fg-muted first-letter:uppercase">{fmtDay(e.kickoff)}</div>
            <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-white/[0.05] px-2 py-0.5 text-[10px] text-fg-muted">
              <LuClock className="size-3" /> {fmtCountdown(e.kickoff)}
            </div>
          </div>
          <TeamBlock team={e.away} form={e.formAway} label="Goście" />
        </div>
        <div className="relative mt-4 flex items-center justify-between border-t border-line pt-3 text-[11px] text-fg-faint">
          <span className="flex items-center gap-1.5">
            <LuDatabase className="size-3.5" /> Ostatnia aktualizacja: {fmtAgo(e.lastUpdated)} ({fmtTime(e.lastUpdated)})
          </span>
        </div>
      </Card>

      <div className="no-scrollbar sticky top-[calc(1.75rem+env(safe-area-inset-top))] z-30 -mx-4 mt-4 flex gap-1 overflow-x-auto bg-ink-950/80 px-4 py-2 backdrop-blur-lg" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={cn("h-9 shrink-0 rounded-full px-3.5 text-[13px] font-medium transition-colors", tab === t.key ? "bg-fg text-ink-950" : "text-fg-muted hover:text-fg")}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div key={tab} className="animate-fade-up mt-3 space-y-4">
        {tab === "analysis" && <AnalysisTab e={e} recs={recs} withdrawn={withdrawn} />}
        {tab === "markets" && <MarketsTab e={e} />}
        {tab === "odds" && <OddsTab e={e} recs={recs} />}
        {tab === "stats" && <StatsTab e={e} />}
        {tab === "lineups" && <LineupsTab e={e} />}
      </div>
      <ResponsibleNote className="mt-8" />
    </div>
  );
}

function TeamBlock({ team, form, label }: { team: SportEvent["home"]; form: SportEvent["formHome"]; label: string }) {
  return (
    <div className="flex min-w-0 flex-1 flex-col items-center gap-2 text-center">
      <TeamCrest team={team} size={52} />
      <div className="w-full">
        <div className="line-clamp-2 text-sm leading-tight font-semibold">{team.name}</div>
        <div className="mt-0.5 text-[10px] text-fg-faint">{label}</div>
      </div>
      <FormPills form={form} count={5} />
    </div>
  );
}

// ---------------- Analysis ----------------

function AnalysisTab({ e, recs, withdrawn }: { e: SportEvent; recs: Recommendation[]; withdrawn: Recommendation[] }) {
  const best = recs[0];
  const main = e.markets.find((m) => m.market === "1X2" || m.market === "MONEYLINE");
  return (
    <>
      {best ? <BestBet rec={best} /> : <NoBetCard e={e} />}

      {e.priceInsight && <PriceInsightCard e={e} insight={e.priceInsight} />}

      {recs.slice(1).map((r) => (
        <Card key={r.id} className="p-4">
          <div className="text-[11px] font-semibold tracking-wide text-fg-faint uppercase">Alternatywny typ</div>
          <div className="mt-2 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate font-semibold">{r.label}</div>
              <div className="mt-1 flex gap-1.5">
                <EvPill ev={r.ev} />
                <RiskBadge risk={r.risk} compact />
              </div>
            </div>
            <div className="text-right">
              <div className="tnum text-xl font-bold">{fmtPrice(r.price)}</div>
              <div className="text-[10px] text-fg-faint">{bookmakerName(r.bookmaker)}</div>
            </div>
            <ScoreRing value={r.quality} size={40} />
          </div>
        </Card>
      ))}

      {withdrawn.map((r) => (
        <div key={r.id} className="flex gap-3 rounded-2xl bg-neg/[0.07] p-4 ring-1 ring-inset ring-neg/20">
          <LuCircleMinus className="mt-0.5 size-5 shrink-0 text-neg" />
          <div className="min-w-0">
            <div className="text-sm font-semibold text-fg">Wycofano: {r.label}</div>
            <p className="mt-1 text-xs leading-relaxed text-fg-muted">{r.withdrawReason}</p>
            <p className="mt-1 text-[11px] text-fg-faint">Typ pozostaje w historii jako wycofany przed startem (nie jest rozliczany).</p>
          </div>
        </div>
      ))}

      {main && main.available && (
        <Card className="p-4">
          <h3 className="mb-3 text-sm font-semibold">Prawdopodobieństwa wyniku</h3>
          <OutcomeBars rows={main.selections.map((s, i) => ({ label: i === 1 && main.selections.length === 3 ? "Remis" : s.label.replace("Wygrana ", ""), model: s.modelProb, market: s.fairProb }))} />
        </Card>
      )}

      {e.flags.length > 0 && (
        <Card className="p-4">
          <h3 className="mb-2.5 text-sm font-semibold">Czynniki ryzyka i uwagi</h3>
          <ul className="space-y-2">
            {e.flags.map((f) => (
              <li key={f} className="flex gap-2 text-[13px] text-fg-muted">
                <LuTriangleAlert className="mt-0.5 size-4 shrink-0 text-warn" /> {f}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="p-4">
        <h3 className="mb-1 text-sm font-semibold">Status danych</h3>
        <p className="mb-3 text-xs text-fg-faint">Każda informacja ma źródło i czas pobrania. Brak danych obniża ocenę — nigdy jej nie podnosi.</p>
        <ul className="divide-y divide-line">
          {e.sources.map((s) => (
            <li key={s.kind} className="flex items-center justify-between py-2.5 text-[13px]">
              <span className="text-fg-muted">{SOURCE_LABEL[s.kind]}</span>
              <span className="flex items-center gap-3">
                <span className="text-[11px] text-fg-faint">{s.updatedAt ? `${s.provider} · ${fmtAgo(s.updatedAt)}` : "brak w źródle"}</span>
                <FreshnessLabel freshness={s.freshness} />
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}

function BestBet({ rec }: { rec: Recommendation }) {
  const tier = qualityTier(rec.quality);
  return (
    <Card className="overflow-hidden p-0 ring-1 ring-accent/20">
      <div className="bg-[linear-gradient(135deg,rgb(47_214_234/0.1),transparent_60%)] p-4">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold tracking-wide text-accent uppercase">{rec.kind === "market" ? "Okazja rynkowa" : "Najlepszy typ"}</span>
          <span className="text-[11px] text-fg-faint">Wygenerowano {fmtAgo(rec.generatedAt)}</span>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <div className="min-w-0 flex-1">
            <div className="text-xl leading-tight font-bold">{rec.label}</div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              <EvPill ev={rec.ev} />
              <RiskBadge risk={rec.risk} />
              {rec.kind === "market" && <MarketBadge />}
            </div>
          </div>
          <div className="text-right">
            <div className="tnum text-3xl leading-none font-bold">{fmtPrice(rec.price)}</div>
            <div className="mt-1.5 text-[11px] text-fg-faint">najlepszy kurs · {bookmakerName(rec.bookmaker)}</div>
          </div>
        </div>
        {rec.kind === "market" && <p className="mt-3 text-[11px] leading-relaxed text-fg-muted">{MARKET_NOTE}</p>}
        <div className="mt-5">
          <ProbBar model={rec.modelProb} low={rec.probLow} high={rec.probHigh} implied={rec.impliedProb} />
          <ProbLegend model={rec.modelProb} low={rec.probLow} high={rec.probHigh} implied={rec.impliedProb} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4 border-t border-line p-4 sm:grid-cols-4">
        <KeyValue label="Prawdop. modelu" value={fmtPct(rec.modelProb)} hint={`${fmtPct(rec.probLow, 0)}–${fmtPct(rec.probHigh, 0)}`} />
        <KeyValue label="Implikowane" value={fmtPct(rec.impliedProb)} hint={`bez marży ${fmtPct(rec.fairProb)}`} />
        <KeyValue label="Expected Value" value={<span className="text-pos">{fmtSignedPct(rec.ev)}</span>} hint="na 1 jednostkę stawki" />
        <KeyValue label="Kurs godziwy" value={fmtPrice(1 / rec.modelProb)} hint="przy którym EV = 0" />
      </div>
      <div className="flex items-center gap-3 border-t border-line p-4">
        <ScoreRing value={rec.quality} size={44} />
        <div>
          <div className="text-sm font-semibold">
            Ocena analizy {rec.quality}/100 · {tier.label}
          </div>
          <div className="text-[11px] text-fg-faint">Jakość sygnału, nie gwarancja wyniku.</div>
        </div>
      </div>
      <div className="space-y-4 border-t border-line p-4">
        <PlPriceHint prob={rec.modelProb} />
        <ReasonList title="Argumenty za" items={rec.reasonsFor} tone="pos" />
        <ReasonList title="Argumenty przeciw i ryzyka" items={rec.reasonsAgainst} tone="warn" />
      </div>
    </Card>
  );
}

function NoBetCard({ e }: { e: SportEvent }) {
  const stale = e.flags.find((f) => f.startsWith("Kursy nieaktualne"));
  return (
    <Card className="p-5 text-center">
      <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-ink-800 ring-1 ring-inset ring-line">
        {stale ? <LuTriangleAlert className="size-5 text-warn" /> : <LuCircleSlash className="size-5 text-fg-muted" />}
      </div>
      <p className="mx-auto mt-4 max-w-sm text-[15px] leading-snug font-semibold">{NO_BET_MESSAGE}</p>
      <p className="mx-auto mt-2 max-w-sm text-xs leading-relaxed text-fg-faint">
        {stale ? "Kursy są starsze niż dopuszczalny próg — analiza zostanie wznowiona po odświeżeniu danych." : "Żaden rynek nie przekroczył progów EV i oceny jakości. Szczegóły w zakładce Rynki."}
      </p>
    </Card>
  );
}

// ---------------- Markets ----------------

function MarketsTab({ e }: { e: SportEvent }) {
  return (
    <>
      <p className="px-1 text-xs leading-relaxed text-fg-faint">
        Model wycenia każdą selekcję. Kurs ma wartość, gdy prawdopodobieństwo modelu przewyższa prawdopodobieństwo implikowane z najlepszego kursu. Marża podana dla bukmachera referencyjnego.
      </p>
      {e.markets.map((m) => (
        <MarketCard key={`${m.market}-${m.name}`} e={e} m={m} recIds={e.recommendations.filter((r) => r.status === "active").map((r) => r.selectionId)} />
      ))}
    </>
  );
}

function MarketCard({ e, m, recIds }: { e: SportEvent; m: MarketAnalysis; recIds: string[] }) {
  const coupon = useCoupon();
  const [note, setNote] = useState<string | null>(null);
  const started = Date.parse(e.kickoff) <= Date.now();
  if (!m.available) {
    return (
      <Card className="p-4 opacity-80">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">{m.name}</h3>
          <Badge>Niedostępny</Badge>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-fg-faint">{m.verdict}</p>
      </Card>
    );
  }
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{m.name}</h3>
        {m.margin !== null && <span className="tnum text-[11px] text-fg-faint">Marża {fmtPct(m.margin)}</span>}
      </div>
      <div className="mt-3 space-y-2">
        {m.selections.map((s) => {
          const best = bestQuote(s.quotes)!;
          const ev = expectedValue(s.modelProb, best.price);
          const isRec = recIds.includes(s.id);
          return (
            <div key={s.id} className={cn("rounded-xl p-3 ring-1 ring-inset", isRec ? "bg-pos/[0.06] ring-pos/25" : "bg-ink-800/60 ring-line")}>
              <div className="flex items-center justify-between gap-3">
                <span className="min-w-0 truncate text-[13px] font-medium">{s.label}</span>
                <span className="flex shrink-0 items-center gap-2">
                  <span className="tnum text-[15px] font-bold">{fmtPrice(best.price)}</span>
                  {!started && (
                    <button
                      type="button"
                      onClick={() => setNote(coupon.toggle(e, s))}
                      className={cn("grid size-7 place-items-center rounded-full ring-1 ring-inset", coupon.has(s.id) ? "bg-accent text-ink-950 ring-accent" : "text-fg-muted ring-line-strong hover:bg-white/5")}
                      aria-label={coupon.has(s.id) ? `Usuń z kuponu: ${s.label}` : `Dodaj do kuponu: ${s.label}`}
                      aria-pressed={coupon.has(s.id)}
                    >
                      {coupon.has(s.id) ? <LuCheck className="size-4" /> : <LuPlus className="size-4" />}
                    </button>
                  )}
                </span>
              </div>
              <div className="tnum mt-1.5 flex items-center gap-2 text-[11px] text-fg-faint">
                <span>
                  Model <b className="text-fg-muted">{fmtPct(s.modelProb)}</b>
                  {s.rawModelProb !== undefined && Math.abs(s.rawModelProb - s.modelProb) >= 0.005 && <> (sam model {fmtPct(s.rawModelProb)})</>}
                </span>
                <span>Impl. {fmtPct(impliedProbability(best.price))}</span>
                <span className={cn("ml-auto font-semibold", ev > 0 ? "text-pos" : "text-neg")}>EV {fmtSignedPct(ev)}</span>
              </div>
            </div>
          );
        })}
      </div>
      {note && <p className="mt-3 rounded-lg bg-warn/10 px-3 py-2 text-[11px] leading-relaxed text-warn">{note}</p>}
      <p className={cn("mt-3 text-xs leading-relaxed", m.selections.some((s) => recIds.includes(s.id)) ? "text-pos" : "text-fg-faint")}>{m.verdict}</p>
    </Card>
  );
}

// ---------------- Odds ----------------

function OddsTab({ e, recs }: { e: SportEvent; recs: Recommendation[] }) {
  const all = useMemo(() => e.markets.flatMap((m) => m.selections), [e]);
  const [selId, setSelId] = useState<string>(recs[0]?.selectionId ?? all[0]?.id ?? "");
  const sel: SelectionAnalysis | undefined = all.find((s) => s.id === selId);
  if (!sel) return <EmptyState icon={<LuCircleSlash className="size-5" />} title="Brak kursów dla tego wydarzenia" />;
  const best = bestQuote(sel.quotes)!;
  const first = sel.priceHistory[0].price;
  const move = best.price / first - 1;

  return (
    <>
      <label className="relative block">
        <span className="mb-1.5 block px-1 text-[11px] font-medium text-fg-faint">Rynek / selekcja</span>
        <select
          value={selId}
          onChange={(ev) => setSelId(ev.target.value)}
          className="h-12 w-full appearance-none rounded-xl bg-ink-850 pr-10 pl-4 text-sm text-fg ring-1 ring-line outline-none focus:ring-accent/50"
        >
          {e.markets
            .filter((m) => m.available)
            .map((m) => (
              <optgroup key={m.name} label={m.name}>
                {m.selections.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </optgroup>
            ))}
        </select>
        <LuChevronDown className="pointer-events-none absolute right-3.5 bottom-4 size-4 text-fg-faint" />
      </label>

      <Card className="p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Porównanie bukmacherów</h3>
          <span className="text-[11px] text-fg-faint">kurs godziwy modelu {fmtPrice(1 / sel.modelProb)}</span>
        </div>
        <ul className="mt-3 divide-y divide-line">
          {sel.quotes.map((q) => {
            const ev = expectedValue(sel.modelProb, q.price);
            const isBest = q.price === best.price;
            return (
              <li key={q.bookmaker} className="flex items-center gap-3 py-2.5">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-ink-700 text-[10px] font-bold text-fg-muted">{bookmakerShort(q.bookmaker)}</span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium">{bookmakerName(q.bookmaker)}</span>
                  <span className="block text-[10px] text-fg-faint">{fmtAgo(q.updatedAt)}</span>
                </span>
                <span className={cn("tnum text-[11px] font-semibold", ev > 0 ? "text-pos" : "text-fg-faint")}>EV {fmtSignedPct(ev)}</span>
                <span className={cn("tnum w-16 rounded-lg py-1.5 text-center text-[15px] font-bold", isBest ? "bg-accent/15 text-accent ring-1 ring-inset ring-accent/30" : "text-fg")}>{fmtPrice(q.price)}</span>
              </li>
            );
          })}
        </ul>
        <p className="mt-2 text-[11px] leading-relaxed text-fg-faint">
          {e.origin === "demo" ? "Integracje STS, Fortuna, Superbet i Betclic nie są jeszcze zweryfikowane — w trybie DEMO kursy są fikcyjne." : "Kursy z The Odds API (bukmacherzy europejscy). Kursy STS, Fortuny czy Superbetu mogą się różnić — przed zakładem sprawdź, czy u Twojego bukmachera EV nadal jest dodatnie (kurs ≥ kurs godziwy)."}
        </p>
      </Card>

      <Card className="p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Ruch kursu</h3>
          <span className={cn("tnum text-xs font-semibold", move >= 0 ? "text-pos" : "text-neg")}>
            {fmtPrice(first)} → {fmtPrice(best.price)} ({fmtSignedPct(move)})
          </span>
        </div>
        <div className="mt-3">
          <OddsChart points={sel.priceHistory} />
        </div>
        <p className="mt-2 text-[11px] leading-relaxed text-fg-faint">Spadek kursu często oznacza, że rynek już uwzględnił nową informację. Rekomendacje są przeliczane przy każdej zmianie.</p>
      </Card>
    </>
  );
}

// ---------------- Stats ----------------

function fmtStat(line: StatLine) {
  return (v: number) => {
    switch (line.format) {
      case "pct":
        return fmtPct(v, 0);
      case "int":
        return String(Math.round(v));
      case "dec2":
        return fmtDec(v, 2);
      default:
        return fmtDec(v, 1);
    }
  };
}

function StatsTab({ e }: { e: SportEvent }) {
  return (
    <>
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-semibold">Forma · ostatnie 8 spotkań</h3>
        <div className="space-y-4">
          {[
            { team: e.home, form: e.formHome },
            { team: e.away, form: e.formAway },
          ].map(({ team, form }) => (
            <div key={team.id}>
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2">
                  <TeamCrest team={team} size={20} />
                  <span className="truncate text-[13px] font-medium">{team.name}</span>
                </span>
                <FormPills form={form} count={8} />
              </div>
              <div className="flex h-10 items-end gap-1">
                {form
                  .slice(0, 8)
                  .reverse()
                  .map((f, i) => {
                    const diff = f.scored - f.conceded;
                    const maxAbs = e.sport === "football" ? 4 : 30;
                    return (
                      <div key={i} className="flex flex-1 flex-col items-center justify-end" title={`${f.home ? "D" : "W"} ${f.opponent} ${f.scored}:${f.conceded}`}>
                        <div className={cn("w-full rounded-sm", diff > 0 ? "bg-pos/70" : diff < 0 ? "bg-neg/70" : "bg-fg-faint/50")} style={{ height: `${Math.max(8, (Math.min(Math.abs(diff), maxAbs) / maxAbs) * 100)}%` }} />
                      </div>
                    );
                  })}
              </div>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-fg-faint">Słupki: różnica {e.sport === "football" ? "bramek" : "punktów"} (od najstarszego do najnowszego).</p>
      </Card>

      <Card className="p-4">
        <div className="mb-1 flex items-center justify-between text-[11px] font-semibold text-fg-faint">
          <span className="truncate">{e.home.shortName}</span>
          <span>Porównanie statystyk</span>
          <span className="truncate">{e.away.shortName}</span>
        </div>
        <div className="divide-y divide-line">
          {e.stats.map((s) => (
            <StatCompare key={s.key} label={s.label} home={s.home} away={s.away} higherIsBetter={s.higherIsBetter} format={fmtStat(s)} />
          ))}
        </div>
      </Card>

      <Card className="p-4">
        <h3 className="mb-2 text-sm font-semibold">Mecze bezpośrednie</h3>
        <ul className="divide-y divide-line">
          {e.h2h.map((h, i) => (
            <li key={i} className="flex items-center gap-3 py-2.5 text-[13px]">
              <span className="tnum w-16 shrink-0 text-[11px] text-fg-faint">{new Date(h.date).toLocaleDateString("pl-PL", { month: "short", year: "numeric" })}</span>
              <span className="min-w-0 flex-1 truncate text-right text-fg-muted">{h.homeTeam}</span>
              <span className="tnum shrink-0 rounded-md bg-ink-700 px-2 py-0.5 font-semibold">
                {h.homeScore}:{h.awayScore}
              </span>
              <span className="min-w-0 flex-1 truncate text-fg-muted">{h.awayTeam}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] text-fg-faint">H2H ma niską wagę w modelu — składy i forma zmieniają się szybciej niż historia spotkań.</p>
      </Card>
    </>
  );
}

// ---------------- Lineups ----------------

const REASON = { injury: "Kontuzja", suspension: "Zawieszenie", doubtful: "Niepewny", rest: "Odpoczynek" };
const IMPORTANCE = { key: "kluczowy", regular: "podstawowy", squad: "rezerwowy" };

function LineupsTab({ e }: { e: SportEvent }) {
  const status = { confirmed: ["Potwierdzone", "pos"], predicted: ["Przewidywane", "warn"], unavailable: ["Niedostępne", "neutral"] } as const;
  const [label, tone] = status[e.lineups.status];
  return (
    <>
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-semibold">Absencje</h3>
        {e.absences === null ? (
          <div className="flex gap-2.5 rounded-xl bg-warn/[0.07] p-3 text-xs text-fg-muted ring-1 ring-inset ring-warn/20">
            <LuTriangleAlert className="size-4 shrink-0 text-warn" /> Źródło nie dostarcza danych o kontuzjach i zawieszeniach dla tej ligi. Ocena analizy została obniżona.
          </div>
        ) : e.absences.length === 0 ? (
          <p className="text-[13px] text-fg-muted">Brak zgłoszonych absencji.</p>
        ) : (
          <ul className="divide-y divide-line">
            {e.absences.map((a, i) => (
              <li key={i} className="flex items-center gap-3 py-2.5">
                <LuUserX className={cn("size-4 shrink-0", a.importance === "key" ? "text-neg" : "text-fg-faint")} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium">{a.player}</span>
                  <span className="text-[11px] text-fg-faint">
                    {a.team === "home" ? e.home.name : e.away.name} · zawodnik {IMPORTANCE[a.importance]}
                  </span>
                </span>
                <Badge tone={a.reason === "doubtful" ? "warn" : "neg"}>{REASON[a.reason]}</Badge>
              </li>
            ))}
          </ul>
        )}
        {e.origin === "demo" && <p className="mt-3 text-[11px] text-fg-faint">DEMO: zawodnicy opisani pozycją i numerem — bez prawdziwych nazwisk.</p>}
      </Card>

      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Składy</h3>
          <Badge tone={tone}>{label}</Badge>
        </div>
        {e.lineups.status === "unavailable" ? (
          <p className="text-xs leading-relaxed text-fg-faint">
            {e.origin === "demo"
              ? "Składy pojawią się zwykle 24 h przed meczem (przewidywane) i ok. 60 min przed startem (potwierdzone). Rekomendacje zostaną wtedy przeliczone."
              : "Składy nie są pobierane: aktualizacja 1–2 razy dziennie nie trafia w okno publikacji składów (ok. 60 min przed meczem). Sprawdź składy przed zawarciem zakładu."}
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              {[
                { team: e.home, list: e.lineups.home },
                { team: e.away, list: e.lineups.away },
              ].map(({ team, list }) => (
                <div key={team.id}>
                  <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold text-fg-muted">
                    <TeamCrest team={team} size={16} /> {team.shortName}
                  </div>
                  <ul className="space-y-1">
                    {list.map((p) => (
                      <li key={p} className="tnum rounded-lg bg-ink-800/70 px-2.5 py-1.5 text-xs text-fg-muted">
                        {p}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            {e.lineups.updatedAt && <p className="mt-3 text-[11px] text-fg-faint">Aktualizacja {fmtAgo(e.lineups.updatedAt)} · {fmtKickoff(e.kickoff)}</p>}
          </>
        )}
      </Card>
    </>
  );
}
