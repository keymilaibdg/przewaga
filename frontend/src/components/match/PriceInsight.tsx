import { useState, type ReactNode } from "react";
import { LuChevronDown, LuCircleCheck, LuInfo, LuTriangleAlert } from "react-icons/lu";
import { Badge, Card, Segmented } from "../ui/primitives";
import { bookmakerName } from "../../lib/bookmakers";
import { cn } from "../../lib/cn";
import { fmtDec, fmtPct, fmtPrice, fmtSignedPct } from "../../lib/format";
import type { PriceInsight, SelectionInsight, SportEvent } from "../../types/domain";

const LEVEL = {
  value: { tone: "pos", label: "Warto rozważyć", icon: LuCircleCheck },
  neutral: { tone: "warn", label: "Bez przewagi", icon: LuInfo },
  avoid: { tone: "neg", label: "Nieopłacalne", icon: LuTriangleAlert },
} as const;

const zl = (x: number) => `${x >= 0 ? "" : "−"}${Math.abs(x).toFixed(2).replace(".", ",")} zł`;

/** "Analiza kursu": where the price comes from, whether it is justified, profitability and risk. */
export function PriceInsightCard({ e, insight }: { e: SportEvent; insight: PriceInsight }) {
  const [sel, setSel] = useState(insight.favouriteSelectionId);
  const s = insight.selections.find((x) => x.selectionId === sel) ?? insight.selections[0];
  if (!s) return null;
  const lv = LEVEL[s.verdict.level];
  const short = (lbl: string) => lbl.replace("Wygrana ", "");
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold">Analiza kursu</h3>
      <p className="mt-0.5 mb-3 text-xs text-fg-faint">Skąd się wziął kurs, czy jest uzasadniony, czy się opłaca i jakie niesie ryzyko.</p>
      <Segmented
        size="sm"
        value={s.selectionId}
        onChange={setSel}
        options={insight.selections.map((x) => ({ value: x.selectionId, label: `${short(x.label)} ${fmtPrice(x.price)}` }))}
      />

      <div className={cn("mt-4 rounded-xl p-3 ring-1 ring-inset", s.verdict.level === "value" ? "bg-pos/[0.06] ring-pos/25" : s.verdict.level === "neutral" ? "bg-warn/[0.06] ring-warn/25" : "bg-neg/[0.06] ring-neg/25")}>
        <Badge tone={lv.tone} icon={<lv.icon className="size-3.5" />}>
          {lv.label}
        </Badge>
        <p className="mt-2 text-sm font-semibold leading-snug">{s.verdict.headline}</p>
        <ul className="mt-2 space-y-1.5">
          {s.verdict.points.map((p, i) => (
            <li key={i} className="text-xs leading-relaxed text-fg-muted">
              • {p}
            </li>
          ))}
        </ul>
      </div>

      {s.selectionId === insight.favouriteSelectionId && insight.why && (
        <Section title="Dlaczego taki kurs?" open>
          <p className="text-xs leading-relaxed text-fg-muted">{insight.why}</p>
        </Section>
      )}

      {insight.factors.length > 0 && (
      <Section title="Co przemawia za którą drużyną" open={s.selectionId === insight.favouriteSelectionId}>
        <div className="grid grid-cols-[1fr_auto_auto] gap-x-3 gap-y-0 text-xs">
          <span />
          <span className="pb-1 text-right font-semibold text-fg-muted">{e.home.shortName || e.home.name}</span>
          <span className="pb-1 text-right font-semibold text-fg-muted">{e.away.shortName || e.away.name}</span>
          {insight.factors.map((f) => (
            <Row key={f.key} title={f.title} note={f.note} home={f.home} away={f.away} favours={f.favours} />
          ))}
        </div>
      </Section>
      )}

      <Section title="Skąd się wziął kurs">
        <Kv label="Najlepszy kurs" value={`${fmtPrice(s.price)} (${bookmakerName(s.bookmaker)})`} />
        <Kv label="Najgorszy / mediana" value={`${fmtPrice(s.worstPrice)} / ${fmtPrice(s.medianPrice)} — ${s.books} bukmacherów`} />
        <Kv label="Szansa zapisana w kursie" value={fmtPct(s.implied)} hint="1 / kurs" />
        <Kv label="Szansa wg rynku bez marży" value={fmtPct(s.fairProb)} hint="kursy po odjęciu marży bukmachera" />
        {s.marketMargin !== null && <Kv label="Marża bukmachera (cały rynek)" value={fmtPct(s.marketMargin)} />}
        <Kv label="Sam model (bez rynku)" value={fmtPct(s.rawModelProb)} hint="oparty tylko na wynikach — backtest: słabszy od rynku" />
        {s.movement && (
          <Kv label="Ruch kursu" value={`${fmtPrice(s.movement.first)} → ${fmtPrice(s.movement.last)} (${fmtSignedPct(s.movement.changePct)})`} hint="od pierwszego odczytu" />
        )}
      </Section>

      {s.history && <History h={s.history} price={s.medianPrice} />}

      <Section title="Opłacalność (stawka 100 zł, podatek 12%)">
        <Kv label="Wygrana" value={zl(s.per100.win)} />
        <Kv label="Przegrana" value={zl(s.per100.lose)} />
        <Kv label="Wynik średnio na zakład" value={zl(s.per100.expected)} tone={s.per100.expected >= 0 ? "pos" : "neg"} hint="EV po podatku" />
        <Kv label="EV bez podatku" value={fmtSignedPct(s.ev)} />
        <Kv label="Próg opłacalności" value={`${fmtPct(s.breakEvenTaxed)} wygranych`} hint={`bez podatku ${fmtPct(s.breakEven)}`} />
        {s.minPriceTaxed && <Kv label="Minimalny kurs w Polsce" value={fmtPrice(s.minPriceTaxed)} hint="u polskiego bukmachera, po podatku" />}
      </Section>

      <Section title="Ryzyko">
        <Kv label="Szansa przegranej" value={`${fmtPct(s.loseProb)}${s.oneInN ? ` (1 na ${fmtDec(s.oneInN)})` : ""}`} />
        <Kv label="Wahania wyniku" value={`± ${zl(s.per100.sd)}`} hint="odchylenie standardowe jednego zakładu za 100 zł" />
        <Kv label="10 takich zakładów — wszystkie wygrane" value={fmtPct(s.series.n10AllWin)} hint={`średnio ${fmtDec(s.series.n10ExpectedLosses)} przegranych na 10`} />
        <Kv label="Na minusie po 10 / 50 zakładach" value={`${fmtPct(s.series.n10InLoss, 0)} / ${fmtPct(s.series.n50InLoss, 0)}`} />
        <Kv label="Kupon z 3 takich zdarzeń" value={`kurs ${fmtPrice(s.acca.price)}, szansa ${fmtPct(s.acca.prob, 0)}`} hint={`EV po podatku ${fmtSignedPct(s.acca.evTaxed)}`} />
      </Section>

      <p className="mt-3 text-[11px] leading-relaxed text-fg-faint">{insight.modelNote} Prawdopodobieństwa to szacunki; pojedynczy zakład zawsze może przegrać.</p>
    </Card>
  );
}

function History({ h, price }: { h: NonNullable<SelectionInsight["history"]>; price: number }) {
  const trap = h.winRateHigh < h.fair;
  const longer = h.winRateLow > h.fair;
  return (
    <Section title={`Historia kursów ${fmtPrice(h.from)}–${fmtPrice(h.to)} (${h.league})`} open={price < 1.6}>
      <p className="mb-2 text-[11px] leading-relaxed text-fg-faint">
        {h.n} selekcji z takim kursem{h.matches ? ` w ${h.matches} meczach` : ""} ({h.source ?? "archiwum"}).
      </p>
      <Kv label="Wygrały" value={`${fmtPct(h.winRate)} (95%: ${fmtPct(h.winRateLow, 0)}–${fmtPct(h.winRateHigh, 0)})`} />
      <Kv label="Kurs zakładał" value={fmtPct(h.implied)} hint={`rynek bez marży ${fmtPct(h.fair)}`} />
      <Kv label="Zwrot przy kursie średnim" value={fmtSignedPct(h.roiAvg)} tone={h.roiAvg >= 0 ? "pos" : "neg"} />
      <Kv label="Zwrot przy najlepszym kursie" value={fmtSignedPct(h.roiBest)} tone={h.roiBest >= 0 ? "pos" : "neg"} />
      <Kv label="Zwrot po podatku 12%" value={fmtSignedPct(h.roiTaxed)} tone={h.roiTaxed >= 0 ? "pos" : "neg"} />
      <p className={cn("mt-2 text-[11px] leading-relaxed", trap ? "text-neg" : "text-fg-muted")}>
        {trap
          ? "Takie kursy wygrywały rzadziej, niż wynika z kursu nawet po odjęciu marży — faworyci w tym przedziale byli przeceniani."
          : longer
            ? "Takie kursy wygrywały częściej, niż zakładał rynek — mimo to po podatku zwykle bez zysku."
            : "Takie kursy wygrywały mniej więcej tak często, jak zakładał rynek bez marży (różnica w granicach przypadku) — strata bierze się z marży i podatku, nie z „ustawionego” faworyta."}
      </p>
    </Section>
  );
}

function Section({ title, open = false, children }: { title: string; open?: boolean; children: ReactNode }) {
  const [o, setO] = useState(open);
  return (
    <div className="mt-3 border-t border-line pt-3">
      <button type="button" onClick={() => setO(!o)} className="flex w-full items-center justify-between text-left text-[13px] font-semibold" aria-expanded={o}>
        {title}
        <LuChevronDown className={cn("size-4 text-fg-faint transition-transform", o && "rotate-180")} />
      </button>
      {o && <div className="mt-2">{children}</div>}
    </div>
  );
}

function Kv({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "pos" | "neg" }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1 text-xs">
      <span className="text-fg-muted">
        {label}
        {hint && <span className="block text-[10px] text-fg-faint">{hint}</span>}
      </span>
      <span className={cn("tnum shrink-0 text-right font-semibold", tone === "pos" && "text-pos", tone === "neg" && "text-neg")}>{value}</span>
    </div>
  );
}

function Row({ title, note, home, away, favours }: { title: string; note: string; home: string; away: string; favours: "home" | "away" | "none" }) {
  return (
    <>
      <span className="border-t border-white/[0.04] py-1.5 text-fg-muted">
        {title}
        {note && <span className="block text-[10px] leading-snug text-fg-faint">{note}</span>}
      </span>
      <span className={cn("tnum border-t border-white/[0.04] py-1.5 text-right", favours === "home" ? "font-semibold text-pos" : "text-fg")}>{home}</span>
      <span className={cn("tnum border-t border-white/[0.04] py-1.5 text-right", favours === "away" ? "font-semibold text-pos" : "text-fg")}>{away}</span>
    </>
  );
}
