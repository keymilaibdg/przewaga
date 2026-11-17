// DEMO data generator. Produces internally consistent, clearly-labelled fake data so that
// every screen can be designed and tested before real providers are connected (stage 4).
// The simplified pricing here is NOT the production engine (stage 5, backend).
import type {
  Absence,
  AppNotification,
  BookmakerId,
  FormEntry,
  Freshness,
  H2HEntry,
  HistoryEntry,
  LineupInfo,
  MarketAnalysis,
  MarketType,
  OddsPoint,
  OddsQuote,
  Recommendation,
  RiskLevel,
  SelectionAnalysis,
  SourceStatus,
  SportEvent,
  StatLine,
  Team,
} from "../types/domain";
import { bestQuote, expectedValue, fairProbabilities, impliedProbability, overround } from "../lib/odds";
import { fmtDec, fmtPct, fmtPrice } from "../lib/format";
import { bookmakerName, LEAGUES, type DemoLeague, type DemoTeam } from "./catalog";
import {
  clamp,
  hashString,
  mulberry32,
  normal,
  normalCdf,
  pick,
  poissonPmf,
  poissonSample,
  randInt,
  round2,
  shuffle,
  uniform,
  type Rng,
} from "./random";

export const NO_BET_MESSAGE =
  "Brak zakładów spełniających obecnie kryteria jakości. Nie rekomendujemy obstawiania tego wydarzenia.";

const MIN_EV = 0.02;
const MIN_QUALITY = 60;
/** Very long prices amplify model error; never recommended. */
const MAX_PRICE = 5;

const BOOK_MARGINS: Record<BookmakerId, number> = {
  pinnacle: 0.028,
  bet365: 0.05,
  betclic: 0.07,
  sts: 0.075,
  fortuna: 0.078,
  superbet: 0.072,
};
const BOOKS = Object.keys(BOOK_MARGINS) as BookmakerId[];

// ---------- time helpers (Europe/Warsaw) ----------

function warsawOffsetHours(at: Date): number {
  const part = new Intl.DateTimeFormat("en-US", { timeZone: "Europe/Warsaw", timeZoneName: "shortOffset" })
    .formatToParts(at)
    .find((p) => p.type === "timeZoneName")?.value;
  const m = part?.match(/GMT([+-]\d+)/);
  return m ? Number(m[1]) : 1;
}

function warsawDate(now: Date, dayOffset: number, hh: number, mm: number): Date {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Warsaw", year: "numeric", month: "2-digit", day: "2-digit" })
    .format(now)
    .split("-")
    .map(Number);
  const utc = Date.UTC(parts[0], parts[1] - 1, parts[2] + dayOffset, hh, mm);
  return new Date(utc - warsawOffsetHours(new Date(utc)) * 3_600_000);
}

const minutesAgo = (now: Date, m: number) => new Date(now.getTime() - m * 60_000).toISOString();

// ---------- shared pricing ----------

interface RawSelection {
  key: string;
  label: string;
  line: number | null;
  p: number;
}

interface PricedMarket {
  analysis: MarketAnalysis;
  candidates: { sel: SelectionAnalysis; best: OddsQuote; ev: number; hw: number }[];
}

function roundPrice(price: number): number {
  if (price < 1.02) return 1.02;
  if (price < 3) return Math.round(price * 100) / 100;
  if (price < 10) return Math.round(price * 20) / 20;
  return Math.round(price * 2) / 2;
}

function priceMarket(
  rng: Rng,
  now: Date,
  eventId: string,
  market: MarketType,
  name: string,
  raw: RawSelection[],
  marketNoise: number,
  completeness: number,
  oddsAgeMin: number,
  /** Sum of true probabilities: 1 for exclusive outcomes, >1 for overlapping ones (double chance). */
  total = 1,
): PricedMarket {
  // Market's own view: model probabilities perturbed (models and markets disagree).
  const marketView = raw.map((r) => r.p * Math.exp(normal(rng, 0, marketNoise)));
  const mvSum = marketView.reduce((a, b) => a + b, 0);
  const marketFair = marketView.map((v) => (v / mvSum) * total);

  const quotesBySel: OddsQuote[][] = raw.map(() => []);
  const books = shuffle(rng, BOOKS).slice(0, randInt(rng, 4, 6));
  for (const b of books) {
    const margin = BOOK_MARGINS[b] * uniform(rng, 0.85, 1.15);
    raw.forEach((_, i) => {
      const noisy = marketFair[i] * Math.exp(normal(rng, 0, 0.012));
      quotesBySel[i].push({
        bookmaker: b,
        price: roundPrice(1 / (noisy * (1 + margin))),
        updatedAt: minutesAgo(now, oddsAgeMin + randInt(rng, 0, 6)),
      });
    });
  }

  const ref = books.includes("pinnacle") ? "pinnacle" : books[0];
  const refPrices = quotesBySel.map((qs) => qs.find((q) => q.bookmaker === ref)!.price);
  const fair = fairProbabilities(refPrices).map((f) => f * total);
  const margin = total === 1 ? overround(refPrices) : refPrices.reduce((s, p) => s + 1 / p, 0) / total - 1;

  const candidates: PricedMarket["candidates"] = [];
  const selections: SelectionAnalysis[] = raw.map((r, i) => {
    const quotes = [...quotesBySel[i]].sort((a, b) => b.price - a.price);
    const best = bestQuote(quotes)!;
    const spread = Math.sqrt(r.p * (1 - r.p)) / 0.5;
    const hw = (0.03 + 0.045 * (1 - completeness) + uniform(rng, 0, 0.02)) * spread;
    const sel: SelectionAnalysis = {
      id: `${eventId}:${market}:${r.key}`,
      market,
      label: r.label,
      line: r.line,
      quotes,
      modelProb: r.p,
      probLow: clamp(r.p - hw, 0.01, 0.99),
      probHigh: clamp(r.p + hw, 0.01, 0.99),
      fairProb: fair[i],
      priceHistory: priceHistory(rng, now, best.price),
    };
    candidates.push({ sel, best, ev: expectedValue(r.p, best.price), hw });
    return sel;
  });

  const top = [...candidates].sort((a, b) => b.ev - a.ev)[0];
  const verdict =
    top.ev <= 0
      ? `Najlepsza selekcja (${top.sel.label}) ma ujemne EV ${fmtPct(top.ev)} — kurs poniżej wartości godziwej modelu.`
      : top.ev < MIN_EV
        ? `Przewaga ${fmtPct(top.ev)} na „${top.sel.label}” jest mniejsza niż próg ${fmtPct(MIN_EV, 0)} i mieści się w niepewności modelu.`
        : `Dodatnie EV ${fmtPct(top.ev)} na „${top.sel.label}”.`;

  return { analysis: { market, name, margin, selections, available: true, verdict }, candidates };
}

function unavailableMarket(market: MarketType, name: string, reason: string): MarketAnalysis {
  return { market, name, margin: null, selections: [], available: false, verdict: reason };
}

function priceHistory(rng: Rng, now: Date, current: number): OddsPoint[] {
  const points: OddsPoint[] = [];
  const drift = normal(rng, 0, 0.045);
  let price = current * (1 + drift);
  for (let i = 12; i >= 1; i--) {
    points.push({ at: minutesAgo(now, i * 240), price: round2(Math.max(1.01, price)) });
    price += (current - price) / i + normal(rng, 0, 0.012) * current;
  }
  points.push({ at: now.toISOString(), price: current });
  return points;
}

// ---------- quality, risk, reasons ----------

function scoreQuality(edgeSnr: number, completeness: number, ev: number, freshness: Freshness, lineupsConfirmed: boolean, price: number): number {
  let q = 47 + 13 * clamp(edgeSnr, -1, 2.2) + 13 * completeness + clamp(ev, 0, 0.1) * 80;
  if (freshness === "aging") q -= 5;
  if (freshness === "stale") q -= 18;
  if (!lineupsConfirmed) q -= 2;
  if (price > 3) q -= 4;
  return Math.round(clamp(q, 0, 97));
}

function scoreRisk(hw: number, price: number, completeness: number): RiskLevel {
  const s = hw * 2 + (price - 1) * 0.06 + (1 - completeness) * 0.2;
  if (s < 0.22) return "low";
  if (s > 0.33) return "high";
  return "medium";
}

function oddsFreshness(ageMin: number, hoursToKickoff: number): Freshness {
  const limit = hoursToKickoff < 2 ? 10 : hoursToKickoff < 24 ? 30 : 120;
  if (ageMin <= limit) return "fresh";
  if (ageMin <= limit * 3) return "aging";
  return "stale";
}

// ---------- football ----------

const FB_POSITIONS = ["Bramkarz", "Środkowy obrońca", "Boczny obrońca", "Defensywny pomocnik", "Środkowy pomocnik", "Skrzydłowy", "Napastnik"];
const FB_LINEUP = ["BR #1", "PO #2", "ŚO #4", "ŚO #5", "LO #3", "DP #6", "ŚP #8", "OP #10", "PS #7", "LS #11", "N #9"];
const BB_POSITIONS = ["Rozgrywający", "Rzucający obrońca", "Niski skrzydłowy", "Silny skrzydłowy", "Środkowy"];
const BB_LINEUP = ["PG #3", "SG #11", "SF #7", "PF #23", "C #12"];

function toTeam(t: DemoTeam): Team {
  return { id: t.id, name: t.name, shortName: t.shortName, logoUrl: null, colors: t.colors };
}

function footballForm(rng: Rng, league: DemoLeague, team: DemoTeam, now: Date): FormEntry[] {
  const out: FormEntry[] = [];
  for (let i = 0; i < 8; i++) {
    const opp = pick(rng, league.teams.filter((x) => x.id !== team.id));
    const home = rng() > 0.5;
    const lf = league.baseline * team.att * opp.def * (home ? league.homeAdv : 1);
    const la = league.baseline * opp.att * team.def * (home ? 1 : league.homeAdv);
    const scored = poissonSample(rng, lf);
    const conceded = poissonSample(rng, la);
    out.push({
      date: new Date(now.getTime() - (i + 1) * 7 * 86_400_000 + randInt(rng, -2, 2) * 86_400_000).toISOString(),
      opponent: opp.name,
      home,
      scored,
      conceded,
      result: scored > conceded ? "W" : scored === conceded ? "D" : "L",
    });
  }
  return out;
}

function basketballForm(rng: Rng, league: DemoLeague, team: DemoTeam, now: Date): FormEntry[] {
  const out: FormEntry[] = [];
  for (let i = 0; i < 8; i++) {
    const opp = pick(rng, league.teams.filter((x) => x.id !== team.id));
    const home = rng() > 0.5;
    const margin = normal(rng, team.att - opp.att + (home ? league.homeAdv : -league.homeAdv), league.id === "nba" ? 12 : 10);
    const total = normal(rng, league.baseline * 2, 12);
    let scored = Math.round((total + margin) / 2);
    let conceded = Math.round((total - margin) / 2);
    if (scored === conceded) scored += 1;
    out.push({
      date: new Date(now.getTime() - (i + 1) * 2.5 * 86_400_000).toISOString(),
      opponent: opp.name,
      home,
      scored,
      conceded,
      result: scored > conceded ? "W" : "L",
    });
  }
  return out;
}

function avg(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / Math.max(1, xs.length);
}

function absencesFor(rng: Rng, positions: string[]): Absence[] {
  const n = randInt(rng, 0, 3);
  const reasons: Absence["reason"][] = ["injury", "injury", "suspension", "doubtful"];
  const imp: Absence["importance"][] = ["key", "regular", "regular", "squad"];
  return Array.from({ length: n }, () => ({
    player: `${pick(rng, positions)} #${randInt(rng, 2, 40)}`,
    team: rng() > 0.5 ? "home" : "away",
    reason: pick(rng, reasons),
    importance: pick(rng, imp),
  }));
}

function sources(now: Date, oddsAgeMin: number, hoursTo: number, opts: { xg?: boolean; injuries: boolean }): SourceStatus[] {
  return [
    { kind: "fixtures", provider: "DEMO", updatedAt: minutesAgo(now, 42), freshness: "fresh" },
    { kind: "odds", provider: "DEMO", updatedAt: minutesAgo(now, oddsAgeMin), freshness: oddsFreshness(oddsAgeMin, hoursTo) },
    { kind: "stats", provider: "DEMO", updatedAt: minutesAgo(now, 180), freshness: "fresh" },
    {
      kind: "injuries",
      provider: "DEMO",
      updatedAt: opts.injuries ? minutesAgo(now, 75) : null,
      freshness: opts.injuries ? "fresh" : "missing",
    },
    { kind: "lineups", provider: "DEMO", updatedAt: hoursTo < 1 ? minutesAgo(now, 8) : null, freshness: hoursTo < 1 ? "fresh" : "missing" },
    ...(opts.xg !== undefined
      ? [{ kind: "xg" as const, provider: "DEMO", updatedAt: opts.xg ? minutesAgo(now, 300) : null, freshness: (opts.xg ? "fresh" : "missing") as Freshness }]
      : []),
  ];
}

interface BuildCtx {
  rng: Rng;
  now: Date;
  league: DemoLeague;
  home: DemoTeam;
  away: DemoTeam;
  kickoff: Date;
  index: number;
}

function footballEvent(ctx: BuildCtx): SportEvent {
  const { rng, now, league, home, away, kickoff } = ctx;
  const id = `demo-fb-${ctx.index}-${home.id}-${away.id}`;
  const hoursTo = (kickoff.getTime() - now.getTime()) / 3_600_000;
  const hasXg = league.id !== "ekstraklasa";
  const hasInjuries = rng() > 0.12;
  const oddsAgeMin = ctx.index % 11 === 7 ? 260 : randInt(rng, 2, 18);
  const odds = oddsFreshness(oddsAgeMin, hoursTo);
  const completeness = clamp((hasXg ? 0.55 : 0.4) + (hasInjuries ? 0.25 : 0) + (hoursTo < 1 ? 0.15 : 0.08) + uniform(rng, -0.05, 0.05), 0.3, 1);

  const injuriesList = hasInjuries ? absencesFor(rng, FB_POSITIONS) : null;
  const keyOut = (side: "home" | "away") => (injuriesList ?? []).filter((a) => a.team === side && a.importance === "key" && a.reason !== "doubtful").length;
  const lamH = league.baseline * home.att * away.def * league.homeAdv * (1 - 0.06 * keyOut("home")) * (1 + 0.04 * keyOut("away"));
  const lamA = league.baseline * away.att * home.def * (1 - 0.06 * keyOut("away")) * (1 + 0.04 * keyOut("home"));

  // Score matrix with Dixon–Coles low-score correction (rho fixed for DEMO).
  const N = 10;
  const rho = -0.06;
  const m: number[][] = [];
  let total = 0;
  for (let i = 0; i <= N; i++) {
    m[i] = [];
    for (let j = 0; j <= N; j++) {
      let tau = 1;
      if (i === 0 && j === 0) tau = 1 - lamH * lamA * rho;
      else if (i === 0 && j === 1) tau = 1 + lamH * rho;
      else if (i === 1 && j === 0) tau = 1 + lamA * rho;
      else if (i === 1 && j === 1) tau = 1 - rho;
      m[i][j] = poissonPmf(i, lamH) * poissonPmf(j, lamA) * tau;
      total += m[i][j];
    }
  }
  const P = (f: (h: number, a: number) => boolean) => {
    let s = 0;
    for (let i = 0; i <= N; i++) for (let j = 0; j <= N; j++) if (f(i, j)) s += m[i][j];
    return s / total;
  };
  const pH = P((h, a) => h > a);
  const pD = P((h, a) => h === a);
  const pA = 1 - pH - pD;

  const priced: PricedMarket[] = [];
  const noise = 0.045;
  const add = (market: MarketType, name: string, raw: RawSelection[], total = 1) =>
    priced.push(priceMarket(rng, now, id, market, name, raw, noise, completeness, oddsAgeMin, total));

  add("1X2", "1X2", [
    { key: "1", label: `Wygrana ${home.name}`, line: null, p: pH },
    { key: "X", label: "Remis", line: null, p: pD },
    { key: "2", label: `Wygrana ${away.name}`, line: null, p: pA },
  ]);
  add("DOUBLE_CHANCE", "Podwójna szansa", [
    { key: "1X", label: `${home.shortName} lub remis (1X)`, line: null, p: pH + pD },
    { key: "X2", label: `${away.shortName} lub remis (X2)`, line: null, p: pA + pD },
  ], 1 + pD);
  add("DRAW_NO_BET", "Draw No Bet", [
    { key: "1", label: `${home.name} (DNB)`, line: null, p: pH / (pH + pA) },
    { key: "2", label: `${away.name} (DNB)`, line: null, p: pA / (pH + pA) },
  ]);
  for (const line of [1.5, 2.5, 3.5]) {
    const over = P((h, a) => h + a > line);
    add("TOTAL_GOALS", `Gole: powyżej/poniżej ${fmtDec(line)}`, [
      { key: `o${line}`, label: `Powyżej ${fmtDec(line)} gola`, line, p: over },
      { key: `u${line}`, label: `Poniżej ${fmtDec(line)} gola`, line, p: 1 - over },
    ]);
  }
  const btts = P((h, a) => h > 0 && a > 0);
  add("BTTS", "Obie drużyny strzelą", [
    { key: "yes", label: "Obie strzelą — TAK", line: null, p: btts },
    { key: "no", label: "Obie strzelą — NIE", line: null, p: 1 - btts },
  ]);
  const ahLine = pH > pA ? -1.5 : 1.5;
  const pHomeAh = ahLine < 0 ? P((h, a) => h - a >= 2) : P((h, a) => a - h <= 1);
  const signed = (x: number) => `${x > 0 ? "+" : "−"}${fmtDec(Math.abs(x))}`;
  add("ASIAN_HANDICAP", `Handicap azjatycki ${signed(ahLine)}`, [
    { key: `h${ahLine}`, label: `${home.name} ${signed(ahLine)}`, line: ahLine, p: pHomeAh },
    { key: `a${-ahLine}`, label: `${away.name} ${signed(-ahLine)}`, line: -ahLine, p: 1 - pHomeAh },
  ]);
  const homeO15 = P((h) => h >= 2);
  add("TEAM_TOTAL", `Gole ${home.shortName}: powyżej/poniżej 1,5`, [
    { key: "ho1.5", label: `${home.name} powyżej 1,5 gola`, line: 1.5, p: homeO15 },
    { key: "hu1.5", label: `${home.name} poniżej 1,5 gola`, line: 1.5, p: 1 - homeO15 },
  ]);

  const markets: MarketAnalysis[] = [
    ...priced.map((p) => p.analysis),
    unavailableMarket("CORNERS", "Rzuty rożne", "Niedostępny: źródło DEMO nie dostarcza wiarygodnych danych o rzutach rożnych. Rynek nie jest wyceniany."),
    unavailableMarket("CARDS", "Kartki", "Niedostępny: brak wiarygodnych danych o kartkach i sędziach. Rynek nie jest wyceniany."),
  ];

  const formHome = footballForm(rng, league, home, now);
  const formAway = footballForm(rng, league, away, now);
  const gf = (f: FormEntry[], side?: boolean) => avg(f.filter((x) => side === undefined || x.home === side).map((x) => x.scored));
  const ga = (f: FormEntry[], side?: boolean) => avg(f.filter((x) => side === undefined || x.home === side).map((x) => x.conceded));
  const xg = (lam: number) => (hasXg ? round2(lam * uniform(rng, 0.9, 1.1)) : null);
  const stats: StatLine[] = [
    { key: "gf", label: "Gole strzelone / mecz", home: gf(formHome), away: gf(formAway), higherIsBetter: true, format: "dec2", source: "DEMO" },
    { key: "ga", label: "Gole stracone / mecz", home: ga(formHome), away: ga(formAway), higherIsBetter: false, format: "dec2", source: "DEMO" },
    { key: "gf_split", label: "Gole u siebie / na wyjeździe", home: gf(formHome, true), away: gf(formAway, false), higherIsBetter: true, format: "dec2", source: "DEMO" },
    { key: "xg", label: "xG / mecz", home: xg(lamH), away: xg(lamA), higherIsBetter: true, format: "dec2", source: hasXg ? "DEMO" : null },
    { key: "xga", label: "xGA / mecz", home: xg(lamA * 0.95), away: xg(lamH * 1.05), higherIsBetter: false, format: "dec2", source: hasXg ? "DEMO" : null },
    { key: "sot", label: "Strzały celne / mecz", home: round2(lamH * 3.1 + uniform(rng, -0.4, 0.4)), away: round2(lamA * 3.1 + uniform(rng, -0.4, 0.4)), higherIsBetter: true, format: "dec1", source: "DEMO" },
    { key: "o25", label: "Mecze powyżej 2,5 gola", home: formHome.filter((f) => f.scored + f.conceded > 2.5).length / 8, away: formAway.filter((f) => f.scored + f.conceded > 2.5).length / 8, higherIsBetter: true, format: "pct", source: "DEMO" },
    { key: "btts", label: "Mecze BTTS", home: formHome.filter((f) => f.scored > 0 && f.conceded > 0).length / 8, away: formAway.filter((f) => f.scored > 0 && f.conceded > 0).length / 8, higherIsBetter: true, format: "pct", source: "DEMO" },
  ];

  const lineups: LineupInfo =
    hoursTo < 1
      ? { status: "confirmed", home: FB_LINEUP, away: FB_LINEUP, updatedAt: minutesAgo(now, 8) }
      : hoursTo < 30
        ? { status: "predicted", home: FB_LINEUP, away: FB_LINEUP, updatedAt: minutesAgo(now, 95) }
        : { status: "unavailable", home: [], away: [], updatedAt: null };

  const h2h: H2HEntry[] = Array.from({ length: 5 }, (_, i) => {
    const flip = rng() > 0.5;
    const hT = flip ? away : home;
    const aT = flip ? home : away;
    return {
      date: new Date(now.getTime() - (i + 1) * 170 * 86_400_000).toISOString(),
      homeTeam: hT.name,
      awayTeam: aT.name,
      homeScore: poissonSample(rng, league.baseline * hT.att * aT.def * league.homeAdv),
      awayScore: poissonSample(rng, league.baseline * aT.att * hT.def),
      competition: league.name,
    };
  });

  const flags: string[] = [];
  if (rng() < 0.25) flags.push("Mecz po rozgrywkach europejskich — możliwa rotacja");
  if (!hasXg) flags.push("Brak xG w źródle — model oparty na bramkach");
  if (!hasInjuries) flags.push("Brak danych o kontuzjach");
  if (odds !== "fresh") flags.push(odds === "stale" ? "Kursy nieaktualne — rekomendacje wstrzymane" : "Kursy starzeją się");

  const evt: SportEvent = {
    id,
    origin: "demo",
    sport: "football",
    league: { id: league.id, name: league.name, country: league.country, sport: "football" },
    home: toTeam(home),
    away: toTeam(away),
    kickoff: kickoff.toISOString(),
    status: "scheduled",
    venue: null,
    markets,
    recommendations: [],
    noBetReason: null,
    formHome,
    formAway,
    stats,
    absences: injuriesList,
    lineups,
    h2h,
    sources: sources(now, oddsAgeMin, hoursTo, { xg: hasXg, injuries: hasInjuries }),
    lastUpdated: minutesAgo(now, Math.min(oddsAgeMin, 20)),
    flags,
  };

  attachRecommendations(rng, now, evt, priced, completeness, odds, {
    reasonFor: (sel) => footballReasons(sel, evt, lamH, lamA),
  });
  return evt;
}

function footballReasons(sel: SelectionAnalysis, evt: SportEvent, lamH: number, lamA: number): string[] {
  const s = (k: string) => evt.stats.find((x) => x.key === k);
  const out = [`Model Dixon–Coles: oczekiwane bramki ${fmtDec(lamH, 2)} – ${fmtDec(lamA, 2)} (suma ${fmtDec(lamH + lamA, 2)})`];
  const xg = s("xg");
  if (sel.market === "TOTAL_GOALS" || sel.market === "BTTS" || sel.market === "TEAM_TOTAL") {
    const gf = s("gf");
    if (gf?.home != null && gf.away != null) out.push(`Średnio strzelone: ${evt.home.shortName} ${fmtDec(gf.home, 2)}, ${evt.away.shortName} ${fmtDec(gf.away, 2)} gola/mecz (ostatnie 8)`);
    const o = s(sel.market === "BTTS" ? "btts" : "o25");
    if (o?.home != null && o.away != null) out.push(`${o.label}: ${fmtPct(o.home, 0)} i ${fmtPct(o.away, 0)} spotkań w ostatnich 8`);
  } else if (xg?.home != null && xg.away != null) {
    out.push(`xG na mecz: ${evt.home.shortName} ${fmtDec(xg.home, 2)} vs ${evt.away.shortName} ${fmtDec(xg.away, 2)}`);
  }
  const keyAway = (evt.absences ?? []).filter((a) => a.importance === "key" && a.reason !== "doubtful");
  if (keyAway.length) out.push(`Uwzględnione absencje kluczowych zawodników: ${keyAway.map((a) => `${a.player} (${a.team === "home" ? evt.home.shortName : evt.away.shortName})`).join(", ")}`);
  return out;
}

// ---------- basketball ----------

function basketballEvent(ctx: BuildCtx): SportEvent {
  const { rng, now, league, home, away, kickoff } = ctx;
  const id = `demo-bb-${ctx.index}-${home.id}-${away.id}`;
  const hoursTo = (kickoff.getTime() - now.getTime()) / 3_600_000;
  const isNba = league.id === "nba";
  const hasInjuries = league.id === "nba" || league.id === "euroleague";
  const oddsAgeMin = randInt(rng, 2, 16);
  const odds = oddsFreshness(oddsAgeMin, hoursTo);
  const completeness = clamp((isNba ? 0.72 : 0.6) + (hasInjuries ? 0.15 : 0) + uniform(rng, -0.05, 0.05), 0.3, 1);
  const awayB2B = isNba && rng() < 0.3;
  const restHome = isNba ? randInt(rng, 1, 3) : randInt(rng, 2, 6);
  const restAway = awayB2B ? 0 : isNba ? randInt(rng, 1, 3) : randInt(rng, 2, 6);

  const injuriesList = hasInjuries ? absencesFor(rng, BB_POSITIONS) : null;
  const keyPenalty = (side: "home" | "away") =>
    (injuriesList ?? []).filter((a) => a.team === side && a.reason !== "doubtful").reduce((s, a) => s + (a.importance === "key" ? 3.2 : a.importance === "regular" ? 1.1 : 0.3), 0);

  const sdMargin = isNba ? 12.5 : 10.5;
  const sdTotal = isNba ? 17 : 13.5;
  const mu = home.att - away.att + league.homeAdv - keyPenalty("home") + keyPenalty("away") + (awayB2B ? 1.8 : 0);
  const paceHome = (isNba ? 99 : 72) + uniform(rng, -3, 3);
  const paceAway = (isNba ? 99 : 72) + uniform(rng, -3, 3);
  const T = league.baseline * 2 * ((paceHome + paceAway) / 2 / (isNba ? 99 : 72)) + uniform(rng, -3, 3);

  const muMkt = mu + normal(rng, 0, 1.3);
  const TMkt = T + normal(rng, 0, 2.2);

  const priced: PricedMarket[] = [];
  const add = (market: MarketType, name: string, raw: RawSelection[], noise = 0.03) =>
    priced.push(priceMarket(rng, now, id, market, name, raw, noise, completeness, oddsAgeMin));

  const pHome = 1 - normalCdf((0 - mu) / sdMargin);
  add("MONEYLINE", "Moneyline", [
    { key: "1", label: `Wygrana ${home.name}`, line: null, p: pHome },
    { key: "2", label: `Wygrana ${away.name}`, line: null, p: 1 - pHome },
  ]);
  const spread = Math.floor(muMkt) + 0.5; // home must win by more than `spread`
  const pCover = 1 - normalCdf((spread - mu) / sdMargin);
  add(
    "SPREAD",
    `Handicap ${spread > 0 ? "−" : "+"}${fmtDec(Math.abs(spread))}`,
    [
      { key: "h", label: `${home.name} ${spread > 0 ? "−" : "+"}${fmtDec(Math.abs(spread))}`, line: -spread, p: pCover },
      { key: "a", label: `${away.name} ${spread > 0 ? "+" : "−"}${fmtDec(Math.abs(spread))}`, line: spread, p: 1 - pCover },
    ],
    0.015,
  );
  const totalLine = Math.floor(TMkt) + 0.5;
  const pOver = 1 - normalCdf((totalLine - T) / sdTotal);
  add(
    "TOTAL_POINTS",
    `Punkty: powyżej/poniżej ${fmtDec(totalLine)}`,
    [
      { key: "o", label: `Powyżej ${fmtDec(totalLine)} pkt`, line: totalLine, p: pOver },
      { key: "u", label: `Poniżej ${fmtDec(totalLine)} pkt`, line: totalLine, p: 1 - pOver },
    ],
    0.015,
  );
  const homeLine = Math.floor((TMkt + muMkt) / 2) + 0.5;
  const pHomeOver = 1 - normalCdf((homeLine - (T + mu) / 2) / (sdTotal * 0.62));
  add(
    "TEAM_POINTS",
    `Punkty ${home.shortName}: powyżej/poniżej ${fmtDec(homeLine)}`,
    [
      { key: "ho", label: `${home.name} powyżej ${fmtDec(homeLine)} pkt`, line: homeLine, p: pHomeOver },
      { key: "hu", label: `${home.name} poniżej ${fmtDec(homeLine)} pkt`, line: homeLine, p: 1 - pHomeOver },
    ],
    0.015,
  );

  const markets: MarketAnalysis[] = [
    ...priced.map((p) => p.analysis),
    unavailableMarket("PLAYER_PROPS", "Statystyki zawodników", "Niedostępny: w trybie DEMO brak wiarygodnych danych o minutach i rolach zawodników."),
  ];

  const formHome = basketballForm(rng, league, home, now);
  const formAway = basketballForm(rng, league, away, now);
  const ortg = (t: DemoTeam) => round2((isNba ? 114 : 112) + t.att / 2 + uniform(rng, -1.5, 1.5));
  const drtg = (t: DemoTeam) => round2((isNba ? 114 : 112) - t.att / 2 + uniform(rng, -1.5, 1.5));
  const stats: StatLine[] = [
    { key: "ppg", label: "Punkty zdobyte / mecz", home: avg(formHome.map((f) => f.scored)), away: avg(formAway.map((f) => f.scored)), higherIsBetter: true, format: "dec1", source: "DEMO" },
    { key: "opp", label: "Punkty stracone / mecz", home: avg(formHome.map((f) => f.conceded)), away: avg(formAway.map((f) => f.conceded)), higherIsBetter: false, format: "dec1", source: "DEMO" },
    { key: "ortg", label: "Offensive Rating", home: ortg(home), away: ortg(away), higherIsBetter: true, format: "dec1", source: "DEMO" },
    { key: "drtg", label: "Defensive Rating", home: drtg(home), away: drtg(away), higherIsBetter: false, format: "dec1", source: "DEMO" },
    { key: "pace", label: "Pace", home: round2(paceHome), away: round2(paceAway), higherIsBetter: true, format: "dec1", source: "DEMO" },
    { key: "efg", label: "eFG%", home: uniform(rng, 0.5, 0.58), away: uniform(rng, 0.5, 0.58), higherIsBetter: true, format: "pct", source: "DEMO" },
    { key: "3p", label: "Skuteczność za 3", home: uniform(rng, 0.33, 0.39), away: uniform(rng, 0.33, 0.39), higherIsBetter: true, format: "pct", source: "DEMO" },
    { key: "rest", label: "Dni odpoczynku", home: restHome, away: restAway, higherIsBetter: true, format: "int", source: "DEMO" },
  ];

  const lineups: LineupInfo =
    hoursTo < 1
      ? { status: "confirmed", home: BB_LINEUP, away: BB_LINEUP, updatedAt: minutesAgo(now, 10) }
      : hoursTo < 30
        ? { status: "predicted", home: BB_LINEUP, away: BB_LINEUP, updatedAt: minutesAgo(now, 120) }
        : { status: "unavailable", home: [], away: [], updatedAt: null };

  const h2h: H2HEntry[] = Array.from({ length: 5 }, (_, i) => {
    const flip = rng() > 0.5;
    const hT = flip ? away : home;
    const aT = flip ? home : away;
    const margin = normal(rng, hT.att - aT.att + league.homeAdv, sdMargin);
    const tot = normal(rng, league.baseline * 2, 12);
    let hs = Math.round((tot + margin) / 2);
    const as = Math.round((tot - margin) / 2);
    if (hs === as) hs += 2;
    return { date: new Date(now.getTime() - (i + 1) * 95 * 86_400_000).toISOString(), homeTeam: hT.name, awayTeam: aT.name, homeScore: hs, awayScore: as, competition: league.name };
  });

  const flags: string[] = [];
  if (awayB2B) flags.push(`${away.shortName}: drugi mecz w dwa dni (back-to-back)`);
  if (!hasInjuries) flags.push("Brak danych o kontuzjach w źródle");

  const evt: SportEvent = {
    id,
    origin: "demo",
    sport: "basketball",
    league: { id: league.id, name: league.name, country: league.country, sport: "basketball" },
    home: toTeam(home),
    away: toTeam(away),
    kickoff: kickoff.toISOString(),
    status: "scheduled",
    venue: null,
    markets,
    recommendations: [],
    noBetReason: null,
    formHome,
    formAway,
    stats,
    absences: injuriesList,
    lineups,
    h2h,
    sources: sources(now, oddsAgeMin, hoursTo, { injuries: hasInjuries }),
    lastUpdated: minutesAgo(now, Math.min(oddsAgeMin, 20)),
    flags,
  };

  attachRecommendations(rng, now, evt, priced, completeness, odds, {
    reasonFor: (sel) => {
      const out = [
        `Model ratingowy: oczekiwana różnica ${mu >= 0 ? "+" : "−"}${fmtDec(Math.abs(mu))} pkt dla ${home.shortName}, suma ${fmtDec(T)} pkt`,
      ];
      const o = stats.find((s) => s.key === "ortg")!;
      const d = stats.find((s) => s.key === "drtg")!;
      out.push(`Net rating: ${home.shortName} ${fmtDec(o.home! - d.home!)} vs ${away.shortName} ${fmtDec(o.away! - d.away!)}`);
      if (sel.market === "TOTAL_POINTS" || sel.market === "TEAM_POINTS") out.push(`Tempo gry: ${fmtDec(paceHome)} i ${fmtDec(paceAway)} posiadań na mecz`);
      if (awayB2B) out.push(`${away.shortName} gra back-to-back (0 dni odpoczynku) — uwzględnione w modelu`);
      return out;
    },
  });
  return evt;
}

// ---------- recommendation gate ----------

function attachRecommendations(
  rng: Rng,
  now: Date,
  evt: SportEvent,
  priced: PricedMarket[],
  completeness: number,
  odds: Freshness,
  text: { reasonFor: (sel: SelectionAnalysis) => string[] },
) {
  const lineupsConfirmed = evt.lineups.status === "confirmed";
  const recs: Recommendation[] = [];
  for (const pm of priced) {
    for (const c of pm.candidates) {
      if (c.ev < MIN_EV || c.best.price > MAX_PRICE) continue;
      const edgeSnr = (c.sel.modelProb - c.sel.fairProb) / c.hw;
      const quality = scoreQuality(edgeSnr, completeness, c.ev, odds, lineupsConfirmed, c.best.price);
      if (quality < MIN_QUALITY) continue;
      const implied = impliedProbability(c.best.price);
      const against: string[] = [];
      if (c.sel.probLow < implied) against.push(`Przedział niepewności ${fmtPct(c.sel.probLow, 0)}–${fmtPct(c.sel.probHigh, 0)} obejmuje p. implikowane ${fmtPct(implied)}`);
      if (evt.lineups.status !== "confirmed") against.push("Składy niepotwierdzone — ponowne przeliczenie ok. 60 min przed startem");
      const hist = c.sel.priceHistory;
      const move = hist[hist.length - 1].price / hist[0].price - 1;
      if (move < -0.03) against.push(`Kurs spadł o ${fmtPct(-move)} w 48 h — rynek mógł już uwzględnić część informacji`);
      evt.flags.filter((f) => f.includes("rotacja") || f.includes("Brak")).forEach((f) => against.push(f));
      if (c.best.price > 2.6) against.push("Wysoki kurs = duża wariancja wyniku pojedynczego zakładu");
      if (against.length < 2)
        against.push(evt.sport === "football" ? "Pojedyncza bramka lub czerwona kartka może odwrócić wynik zakładu" : "Końcówki meczów (faule taktyczne) zwiększają wariancję wyniku");
      const reasonsFor = [
        ...text.reasonFor(c.sel),
        `Kurs ${fmtPrice(c.best.price)} (${bookmakerName(c.best.bookmaker)}) vs kurs godziwy modelu ${fmtPrice(1 / c.sel.modelProb)}`,
      ];
      if (c.sel.probLow > implied) reasonsFor.push(`Cały przedział modelu (${fmtPct(c.sel.probLow, 0)}–${fmtPct(c.sel.probHigh, 0)}) leży powyżej p. implikowanego`);
      recs.push({
        id: `rec:${c.sel.id}`,
        eventId: evt.id,
        selectionId: c.sel.id,
        market: c.sel.market,
        label: c.sel.label,
        bookmaker: c.best.bookmaker,
        price: c.best.price,
        modelProb: c.sel.modelProb,
        probLow: c.sel.probLow,
        probHigh: c.sel.probHigh,
        impliedProb: implied,
        fairProb: c.sel.fairProb,
        ev: c.ev,
        quality,
        risk: scoreRisk(c.hw, c.best.price, completeness),
        reasonsFor,
        reasonsAgainst: against,
        generatedAt: minutesAgo(now, randInt(rng, 30, 400)),
        updatedAt: evt.lastUpdated,
        status: "active",
      });
    }
  }
  recs.sort((a, b) => b.quality - a.quality || b.ev - a.ev);
  evt.recommendations = recs.slice(0, 2);
  if (evt.recommendations.length === 0) evt.noBetReason = NO_BET_MESSAGE;
}

// ---------- public API ----------

export interface DemoWorld {
  generatedAt: string;
  events: SportEvent[];
  history: HistoryEntry[];
  backtest: HistoryEntry[];
  notifications: AppNotification[];
}

const FB_SLOTS: [number, number][] = [
  [18, 0],
  [18, 30],
  [20, 45],
  [21, 0],
  [15, 30],
  [17, 30],
  [13, 30],
];
const NBA_SLOTS: [number, number][] = [
  [1, 0],
  [1, 30],
  [2, 0],
  [3, 30],
  [4, 0],
];
const EU_BB_SLOTS: [number, number][] = [
  [18, 0],
  [19, 0],
  [20, 0],
  [20, 30],
];

export function generateDemoWorld(now = new Date()): DemoWorld {
  const dayKey = now.toISOString().slice(0, 10);
  const rng = mulberry32(hashString(`przewaga-demo-${dayKey}`));
  const events: SportEvent[] = [];
  let index = 0;

  for (let day = 0; day <= 7; day++) {
    const perDay = day <= 1 ? 9 : 6;
    const used = new Set<string>();
    for (let k = 0; k < perDay; k++) {
      const weighted = LEAGUES.flatMap((l) => Array.from({ length: l.weight }, () => l));
      const league = pick(rng, weighted);
      const pool = league.teams.filter((t) => !used.has(`${league.id}:${t.id}`));
      if (pool.length < 2) continue;
      const [home, away] = shuffle(rng, pool).slice(0, 2);
      used.add(`${league.id}:${home.id}`);
      used.add(`${league.id}:${away.id}`);
      const slot = league.id === "nba" ? pick(rng, NBA_SLOTS) : league.sport === "basketball" ? pick(rng, EU_BB_SLOTS) : pick(rng, FB_SLOTS);
      const kickoff = warsawDate(now, league.id === "nba" ? day + 1 : day, slot[0], slot[1]);
      if (kickoff.getTime() < now.getTime() + 20 * 60_000) continue;
      if (kickoff.getTime() > now.getTime() + 7.5 * 86_400_000) continue;
      const ctx: BuildCtx = { rng, now, league, home, away, kickoff, index: index++ };
      events.push(league.sport === "football" ? footballEvent(ctx) : basketballEvent(ctx));
    }
  }

  // One withdrawn recommendation to demonstrate the lifecycle.
  const withActive = events.filter((e) => e.recommendations.length > 0);
  const victim = withActive[3];
  if (victim) {
    const r = victim.recommendations[victim.recommendations.length - 1];
    const before = round2(r.price * 1.14);
    r.status = "withdrawn";
    r.withdrawReason = `Kurs spadł z ${fmtPrice(before)} do ${fmtPrice(r.price)} po informacji o składzie — przewaga poniżej progu.`;
    r.quality = Math.min(r.quality, 58);
  }

  events.sort((a, b) => Date.parse(a.kickoff) - Date.parse(b.kickoff));
  const history = generateHistory(mulberry32(hashString(`hist-${dayKey}`)), now, 160, 80, "demo", 0.03);
  const backtest = generateHistory(mulberry32(hashString("backtest-v1")), now, 1800, 700, "demo", 0.022);
  return { generatedAt: now.toISOString(), events, history, backtest, notifications: buildNotifications(now, events) };
}

const HIST_MARKETS: { market: MarketType; label: (h: string, a: string) => string; sport: "football" | "basketball" }[] = [
  { market: "TOTAL_GOALS", label: () => "Powyżej 2,5 gola", sport: "football" },
  { market: "TOTAL_GOALS", label: () => "Poniżej 2,5 gola", sport: "football" },
  { market: "BTTS", label: () => "Obie strzelą — TAK", sport: "football" },
  { market: "1X2", label: (h) => `Wygrana ${h}`, sport: "football" },
  { market: "DOUBLE_CHANCE", label: (_, a) => `${a} lub remis (X2)`, sport: "football" },
  { market: "ASIAN_HANDICAP", label: (h) => `${h} −1,5`, sport: "football" },
  { market: "DRAW_NO_BET", label: (h) => `${h} (DNB)`, sport: "football" },
  { market: "MONEYLINE", label: (h) => `Wygrana ${h}`, sport: "basketball" },
  { market: "SPREAD", label: (_, a) => `${a} +5,5`, sport: "basketball" },
  { market: "TOTAL_POINTS", label: () => "Poniżej 224,5 pkt", sport: "basketball" },
];

function generateHistory(rng: Rng, now: Date, count: number, spanDays: number, origin: "demo", overconfidence = 0.015): HistoryEntry[] {
  const out: HistoryEntry[] = [];
  for (let i = 0; i < count; i++) {
    const spec = pick(rng, HIST_MARKETS);
    const league = pick(rng, LEAGUES.filter((l) => l.sport === spec.sport));
    const [h, a] = shuffle(rng, league.teams).slice(0, 2);
    const price = round2(uniform(rng, 1.4, 3.1));
    const ev = uniform(rng, 0.02, 0.11);
    const modelProb = Math.min(0.95, (1 + ev) / price);
    const trueP = Math.max(0.02, modelProb - overconfidence + normal(rng, 0, 0.02));
    const ageDays = (i / count) * spanDays;
    const kickoff = new Date(now.getTime() - ageDays * 86_400_000 + (i < 6 ? 6 * 3_600_000 : 0));
    const pending = kickoff.getTime() > now.getTime();
    const voidable = spec.market === "DRAW_NO_BET" && rng() < 0.22;
    const won = rng() < trueP;
    const result: HistoryEntry["result"] = pending ? "pending" : voidable ? "void" : won ? "won" : "lost";
    const profit = result === "won" ? price - 1 : result === "lost" ? -1 : 0;
    const quality = Math.round(clamp(60 + ev * 280 + normal(rng, 0, 5), 60, 96));
    out.push({
      id: `${origin}-h-${i}-${overconfidence}`,
      origin,
      sport: spec.sport,
      eventLabel: `${h.name} – ${a.name}`,
      league: league.name,
      kickoff: kickoff.toISOString(),
      market: spec.market,
      label: spec.label(h.shortName, a.shortName),
      bookmaker: pick(rng, BOOKS),
      openingPrice: price,
      closingPrice: pending ? null : round2(price * (1 - normal(rng, 0.012, 0.035))),
      modelProb,
      ev,
      quality,
      risk: price < 1.8 ? "low" : price < 2.5 ? "medium" : "high",
      generatedAt: new Date(kickoff.getTime() - uniform(rng, 2, 30) * 3_600_000).toISOString(),
      result,
      finalScore: pending ? null : spec.sport === "football" ? `${randInt(rng, 0, 3)}:${randInt(rng, 0, 3)}` : `${randInt(rng, 95, 125)}:${randInt(rng, 95, 125)}`,
      profit,
    });
  }
  return out.sort((x, y) => Date.parse(y.kickoff) - Date.parse(x.kickoff));
}

function buildNotifications(now: Date, events: SportEvent[]): AppNotification[] {
  const out: AppNotification[] = [];
  const active = events.flatMap((e) => e.recommendations.filter((r) => r.status === "active").map((r) => ({ e, r })));
  active
    .sort((a, b) => b.r.quality - a.r.quality)
    .slice(0, 2)
    .forEach(({ e, r }, i) =>
      out.push({
        id: `n-v-${i}`,
        at: minutesAgo(now, 12 + i * 37),
        kind: "new_value",
        title: "Nowa okazja z dodatnim EV",
        body: `${e.home.shortName} – ${e.away.shortName}: ${r.label} @ ${fmtPrice(r.price)} (EV ${fmtPct(r.ev)})`,
        eventId: e.id,
        read: false,
      }),
    );
  const withdrawn = events.flatMap((e) => e.recommendations.filter((r) => r.status === "withdrawn").map((r) => ({ e, r })));
  withdrawn.forEach(({ e, r }, i) =>
    out.push({
      id: `n-w-${i}`,
      at: minutesAgo(now, 55),
      kind: "withdrawn",
      title: "Rekomendacja wycofana",
      body: `${e.home.shortName} – ${e.away.shortName}: ${r.withdrawReason ?? ""}`,
      eventId: e.id,
      read: false,
    }),
  );
  const stale = events.find((e) => e.flags.some((f) => f.startsWith("Kursy nieaktualne")));
  if (stale)
    out.push({
      id: "n-s",
      at: minutesAgo(now, 90),
      kind: "system",
      title: "Nieaktualne kursy",
      body: `${stale.home.shortName} – ${stale.away.shortName}: kursy starsze niż dopuszczalny próg. Rekomendacje wstrzymane do odświeżenia.`,
      eventId: stale.id,
      read: true,
    });
  out.push({ id: "n-set", at: minutesAgo(now, 600), kind: "settled", title: "Rozliczono typy", body: "Rozliczono 4 typy z wczoraj (DEMO).", read: true });
  return out.sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
}
