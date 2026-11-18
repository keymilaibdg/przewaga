import type { UserSettings } from "../types/domain";

const KEY = "przewaga.settings.v2";

export const DEFAULT_SETTINGS: UserSettings = {
  sports: ["football", "basketball"],
  minQuality: 60,
  minEv: 0.02,
  maxRisk: "high",
  excludedBookmakers: [],
  notifications: { newValue: true, oddsMove: true, withdrawn: true, lineups: false, settled: true, couponReminders: true },
  unitStake: 10,
  stakeTax: 0.12,
  dailyLimitUnits: 5,
  marketMode: true,
};

export function loadSettings(): UserSettings {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw) as Partial<UserSettings>;
    return { ...DEFAULT_SETTINGS, ...parsed, notifications: { ...DEFAULT_SETTINGS.notifications, ...(parsed.notifications ?? {}) } };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(s: UserSettings): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* storage unavailable (private mode, sandboxed preview) — keep in memory only */
  }
}
