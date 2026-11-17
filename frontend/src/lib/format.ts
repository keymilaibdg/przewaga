import type { BetResult, Freshness, RiskLevel } from "../types/domain";

const TZ = "Europe/Warsaw";

const timeFmt = new Intl.DateTimeFormat("pl-PL", { hour: "2-digit", minute: "2-digit", timeZone: TZ });
const dayFmt = new Intl.DateTimeFormat("pl-PL", { weekday: "short", day: "numeric", month: "short", timeZone: TZ });
const longDayFmt = new Intl.DateTimeFormat("pl-PL", { weekday: "long", day: "numeric", month: "long", timeZone: TZ });
const dateKeyFmt = new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", timeZone: TZ });

export const fmtTime = (iso: string) => timeFmt.format(new Date(iso));
export const fmtDay = (iso: string) => dayFmt.format(new Date(iso));
export const fmtLongDay = (iso: string | Date) => longDayFmt.format(typeof iso === "string" ? new Date(iso) : iso);

/** YYYY-MM-DD in Warsaw time. */
export const dateKey = (d: string | Date) => dateKeyFmt.format(typeof d === "string" ? new Date(d) : d);

export function relativeDay(iso: string, now = new Date()): string {
  const diff = Math.round((Date.parse(dateKey(iso)) - Date.parse(dateKey(now))) / 86_400_000);
  if (diff === 0) return "Dziś";
  if (diff === 1) return "Jutro";
  if (diff === -1) return "Wczoraj";
  return fmtDay(iso);
}

export function fmtKickoff(iso: string, now = new Date()): string {
  return `${relativeDay(iso, now)}, ${fmtTime(iso)}`;
}

export function fmtAgo(iso: string | null, now = new Date()): string {
  if (!iso) return "brak danych";
  const mins = Math.round((now.getTime() - Date.parse(iso)) / 60_000);
  if (mins < 1) return "przed chwilą";
  if (mins < 60) return `${mins} min temu`;
  const h = Math.floor(mins / 60);
  if (h < 24) return `${h} godz. temu`;
  return `${Math.floor(h / 24)} dn. temu`;
}

export function fmtCountdown(iso: string, now = new Date()): string {
  const mins = Math.round((Date.parse(iso) - now.getTime()) / 60_000);
  if (mins <= 0) return "trwa / zakończony";
  if (mins < 60) return `za ${mins} min`;
  const h = Math.floor(mins / 60);
  if (h < 24) return `za ${h} godz. ${mins % 60} min`;
  return `za ${Math.floor(h / 24)} dn.`;
}

export const fmtPrice = (p: number) => p.toFixed(2);
export const fmtPct = (p: number, digits = 1) => `${(p * 100).toFixed(digits).replace(".", ",")}%`;
export const fmtSignedPct = (p: number, digits = 1) => `${p > 0 ? "+" : p < 0 ? "−" : ""}${Math.abs(p * 100).toFixed(digits).replace(".", ",")}%`;
export const fmtUnits = (u: number) => `${u > 0 ? "+" : u < 0 ? "−" : ""}${Math.abs(u).toFixed(2).replace(".", ",")} j.`;
export const fmtDec = (n: number, digits = 1) => n.toFixed(digits).replace(".", ",");

export const riskLabel: Record<RiskLevel, string> = { low: "Niskie", medium: "Średnie", high: "Wysokie" };

export const freshnessLabel: Record<Freshness, string> = {
  fresh: "Aktualne",
  aging: "Starzejące się",
  stale: "Nieaktualne",
  missing: "Brak danych",
};

export const resultLabel: Record<BetResult, string> = {
  won: "Wygrany",
  lost: "Przegrany",
  void: "Zwrot",
  half_won: "Połowa wygr.",
  half_lost: "Połowa przegr.",
  pending: "Oczekuje",
  withdrawn: "Wycofany",
};

export function qualityTier(q: number): { label: string; tone: "strong" | "good" | "ok" | "weak" | "none" } {
  if (q >= 90) return { label: "Bardzo mocny sygnał", tone: "strong" };
  if (q >= 80) return { label: "Mocny sygnał", tone: "good" };
  if (q >= 70) return { label: "Interesujący typ", tone: "ok" };
  if (q >= 60) return { label: "Podwyższone ryzyko", tone: "weak" };
  return { label: "Brak rekomendacji", tone: "none" };
}

export function plural(n: number, one: string, few: string, many: string): string {
  if (n === 1) return one;
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 >= 2 && mod10 <= 4 && !(mod100 >= 12 && mod100 <= 14)) return few;
  return many;
}
