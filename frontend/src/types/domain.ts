// Canonical domain contract. Mirrors backend Pydantic schemas (stage 3+).
// All timestamps are ISO-8601 UTC strings.

export type Sport = "football" | "basketball";
export type RiskLevel = "low" | "medium" | "high";
export type Freshness = "fresh" | "aging" | "stale" | "missing";
export type EventStatus = "scheduled" | "live" | "finished" | "postponed";
export type DataOrigin = "demo" | "live";

/** Bookmaker key as delivered by the odds provider (e.g. "pinnacle", "betclic_fr"). */
export type BookmakerId = string;

export interface Bookmaker {
  id: BookmakerId;
  name: string;
  /** Whether a verified, ToS-compliant integration exists. */
  integrationVerified: boolean;
}

export interface Team {
  id: string;
  name: string;
  shortName: string;
  /** Crest/logo URL from the data provider; null => generated monogram crest. */
  logoUrl: string | null;
  colors: [string, string];
}

export interface League {
  id: string;
  name: string;
  country: string;
  sport: Sport;
}

export type FootballMarket =
  | "1X2"
  | "DOUBLE_CHANCE"
  | "DRAW_NO_BET"
  | "TOTAL_GOALS"
  | "BTTS"
  | "ASIAN_HANDICAP"
  | "TEAM_TOTAL"
  | "CORNERS"
  | "CARDS";

export type BasketballMarket = "MONEYLINE" | "SPREAD" | "TOTAL_POINTS" | "TEAM_POINTS" | "PLAYER_PROPS";

export type MarketType = FootballMarket | BasketballMarket;

export interface OddsQuote {
  bookmaker: BookmakerId;
  price: number;
  updatedAt: string;
}

export interface OddsPoint {
  at: string;
  price: number;
}

/** One selection inside a market, priced by the model and by bookmakers. */
export interface SelectionAnalysis {
  id: string;
  market: MarketType;
  /** Human label, e.g. "Powyżej 2.5 gola". */
  label: string;
  line: number | null;
  quotes: OddsQuote[];
  /** Final probability (model blended with the margin-free market, weight from the backtest) and its interval. */
  modelProb: number;
  /** The model alone, before blending with the market (pipeline >= ETAP 5). */
  rawModelProb?: number;
  probLow: number;
  probHigh: number;
  /** Margin-free market probability (de-vigged best-available book). */
  fairProb: number;
  /** Price history for the best line. */
  priceHistory: OddsPoint[];
}

export interface MarketAnalysis {
  market: MarketType;
  name: string;
  /** Bookmaker overround for the reference book, e.g. 0.054 = 5.4%. */
  margin: number | null;
  selections: SelectionAnalysis[];
  available: boolean;
  /** Why this market is not recommended / unavailable. */
  verdict: string;
}

export interface Recommendation {
  id: string;
  eventId: string;
  selectionId: string;
  market: MarketType;
  label: string;
  bookmaker: BookmakerId;
  price: number;
  modelProb: number;
  probLow: number;
  probHigh: number;
  impliedProb: number;
  fairProb: number;
  ev: number;
  /** Signal quality 0-100. Not a win probability. */
  quality: number;
  risk: RiskLevel;
  reasonsFor: string[];
  reasonsAgainst: string[];
  generatedAt: string;
  updatedAt: string;
  status: "active" | "withdrawn";
  withdrawReason?: string;
  /** "market": a bookmaker pays more than the margin-free price of the sharpest book (tryb rynkowy, no model). */
  kind?: "model" | "market";
}

export type FormResult = "W" | "D" | "L";

export interface FormEntry {
  date: string;
  opponent: string;
  home: boolean;
  scored: number;
  conceded: number;
  result: FormResult;
}

export interface StatLine {
  key: string;
  label: string;
  home: number | null;
  away: number | null;
  /** True when a higher value is better. */
  higherIsBetter: boolean;
  format?: "int" | "dec1" | "dec2" | "pct";
  source: string | null;
}

export interface Absence {
  player: string;
  team: "home" | "away";
  reason: "injury" | "suspension" | "doubtful" | "rest";
  importance: "key" | "regular" | "squad";
  note?: string;
}

export interface LineupInfo {
  status: "confirmed" | "predicted" | "unavailable";
  home: string[];
  away: string[];
  updatedAt: string | null;
}

export interface H2HEntry {
  date: string;
  homeTeam: string;
  awayTeam: string;
  homeScore: number;
  awayScore: number;
  competition: string;
}

export interface SourceStatus {
  kind: "fixtures" | "odds" | "stats" | "injuries" | "lineups" | "xg";
  provider: string;
  updatedAt: string | null;
  freshness: Freshness;
}

export interface SportEvent {
  id: string;
  origin: DataOrigin;
  sport: Sport;
  league: League;
  home: Team;
  away: Team;
  kickoff: string;
  status: EventStatus;
  venue: string | null;
  markets: MarketAnalysis[];
  recommendations: Recommendation[];
  /** Shown when no recommendation passes the quality gate. */
  noBetReason: string | null;
  formHome: FormEntry[];
  formAway: FormEntry[];
  stats: StatLine[];
  absences: Absence[] | null;
  lineups: LineupInfo;
  h2h: H2HEntry[];
  sources: SourceStatus[];
  lastUpdated: string;
  flags: string[];
  /** Where the 1X2 / moneyline prices come from, whether they are worth taking, risk (pipeline >= analiza-kursu). */
  priceInsight?: PriceInsight | null;
}

export interface InsightFactor {
  key: string;
  title: string;
  home: string;
  away: string;
  favours: "home" | "away" | "none";
  note: string;
}

export interface PriceBucketStats {
  from: number;
  to: number;
  n: number;
  wins: number;
  winRate: number;
  winRateLow: number;
  winRateHigh: number;
  avgPrice: number;
  implied: number;
  fair: number;
  roiAvg: number;
  roiBest: number;
  roiTaxed: number;
  league: string;
  matches: number | null;
  source: string | null;
}

export interface SelectionInsight {
  selectionId: string;
  label: string;
  key: string;
  price: number;
  bookmaker: string;
  worstPrice: number;
  medianPrice: number;
  books: number;
  implied: number;
  fairProb: number;
  finalProb: number;
  rawModelProb: number;
  marketMargin: number | null;
  marginInPrice: number;
  ev: number;
  evTaxed: number;
  breakEven: number;
  breakEvenTaxed: number;
  minPriceTaxed: number | null;
  loseProb: number;
  oneInN: number | null;
  per100: { expected: number; win: number; lose: number; sd: number };
  series: { n10AllWin: number; n10ExpectedLosses: number; n10InLoss: number; n50InLoss: number };
  acca: { legs: number; price: number; prob: number; evTaxed: number };
  movement: { first: number; last: number; changePct: number; since: string } | null;
  history: PriceBucketStats | null;
  canRecommend: boolean;
  verdict: { level: "value" | "neutral" | "avoid"; headline: string; points: string[] };
}

export interface PriceInsight {
  favouriteSelectionId: string;
  why: string;
  factors: InsightFactor[];
  selections: SelectionInsight[];
  modelNote: string;
}

/** "withdrawn" = recommendation withdrawn before kick-off: kept in history, excluded from performance. */
export type BetResult = "won" | "lost" | "void" | "half_won" | "half_lost" | "pending" | "withdrawn";

export interface HistoryEntry {
  id: string;
  origin: DataOrigin;
  sport: Sport;
  eventLabel: string;
  league: string;
  kickoff: string;
  market: MarketType;
  label: string;
  bookmaker: BookmakerId;
  openingPrice: number;
  closingPrice: number | null;
  clv?: number | null;
  modelProb: number;
  ev: number;
  quality: number;
  risk: RiskLevel;
  generatedAt: string;
  result: BetResult;
  finalScore: string | null;
  /** Profit in units for a 1-unit stake. */
  profit: number;
}

export interface PerformanceSlice {
  key: string;
  label: string;
  bets: number;
  won: number;
  roi: number;
  yieldPct: number;
}

export interface CalibrationBin {
  predicted: number;
  observed: number;
  count: number;
}

export interface PerformanceSummary {
  scope: "live" | "backtest";
  bets: number;
  settled: number;
  won: number;
  lost: number;
  voided: number;
  pending: number;
  staked: number;
  profit: number;
  roi: number;
  hitRate: number;
  avgPrice: number;
  avgClv: number | null;
  cumulative: { at: string; profit: number }[];
  bySport: PerformanceSlice[];
  byMarket: PerformanceSlice[];
  byRisk: PerformanceSlice[];
  calibration: CalibrationBin[];
  brier: number | null;
}

export interface AppNotification {
  id: string;
  at: string;
  kind: "new_value" | "odds_move" | "withdrawn" | "lineup" | "settled" | "system";
  title: string;
  body: string;
  eventId?: string;
  read: boolean;
}

export interface UserSettings {
  sports: Sport[];
  minQuality: number;
  minEv: number;
  maxRisk: RiskLevel;
  /** Bookmakers the user does not want recommendations from. */
  excludedBookmakers: BookmakerId[];
  notifications: {
    newValue: boolean;
    oddsMove: boolean;
    withdrawn: boolean;
    lineups: boolean;
    /** Settled recommendations (won / lost). */
    settled: boolean;
    /** Reminder one hour before a match from the coupon (APK). */
    couponReminders: boolean;
  };
  /** Show market-mode tips (price above the margin-free market; no model). */
  marketMode: boolean;
  unitStake: number;
  /** Tax deducted from the stake by the user's bookmaker (Poland: 0.12; tax-free promo: 0). */
  stakeTax: number;
  dailyLimitUnits: number;
}

/** Per competition: may the model recommend? Decided by the walk-forward backtest (ETAP 5). */
export interface ModelStatus {
  league: string;
  name: string;
  sport: Sport;
  status: "validated" | "validating" | "market_only";
  statusLabel: string;
  reason: string;
  minEv: number;
  calibratedAt: string | null;
  markets: { market: string; name: string; status: ModelStatus["status"]; statusLabel: string; modelWeight: number; reason: string }[];
}

export interface ProviderHealth {
  id: string;
  name: string;
  purpose: string;
  status: "connected" | "not_configured" | "error" | "unverified";
  lastSync: string | null;
  quota: string | null;
}

export interface DashboardSummary {
  origin: DataOrigin;
  generatedAt: string;
  /** Freshness of the whole dataset (time since the last pipeline run). */
  dataFreshness: Freshness;
  /** True when the device is offline and the app shows the last downloaded copy. */
  offline?: boolean;
  analyzedEvents: number;
  valueBets: number;
  avgEv: number | null;
  withdrawnToday: number;
  staleSources: number;
}
