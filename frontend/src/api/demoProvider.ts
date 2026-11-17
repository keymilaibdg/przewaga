import type { DataProvider, EventQuery } from "./provider";
import type { AppNotification, Bookmaker, DashboardSummary, ProviderHealth, UserSettings } from "../types/domain";
import { generateDemoWorld, type DemoWorld } from "../demo/generate";
import { computePerformance } from "../lib/performance";
import { BOOKMAKERS } from "../demo/catalog";
import { loadSettings, saveSettings } from "./settingsStore";

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export class DemoProvider implements DataProvider {
  readonly mode = "demo" as const;
  private world: DemoWorld;
  private settings: UserSettings;
  private notifications: AppNotification[];

  constructor(now = new Date()) {
    this.world = generateDemoWorld(now);
    this.notifications = this.world.notifications;
    this.settings = loadSettings();
  }

  async getDashboard(): Promise<DashboardSummary> {
    await delay(120);
    const recs = this.world.events.flatMap((e) => e.recommendations.filter((r) => r.status === "active"));
    return {
      origin: "demo",
      generatedAt: this.world.generatedAt,
      dataFreshness: "fresh",
      analyzedEvents: this.world.events.length,
      valueBets: recs.length,
      avgEv: recs.length ? recs.reduce((s, r) => s + r.ev, 0) / recs.length : null,
      withdrawnToday: this.world.events.flatMap((e) => e.recommendations).filter((r) => r.status === "withdrawn").length,
      staleSources: this.world.events.filter((e) => e.sources.some((s) => s.kind === "odds" && s.freshness === "stale")).length,
    };
  }

  async getEvents(q: EventQuery = {}) {
    await delay(140);
    const now = Date.now();
    return this.world.events.filter((e) => {
      if (q.sport && q.sport !== "all" && e.sport !== q.sport) return false;
      const days = (Date.parse(e.kickoff) - now) / 86_400_000;
      if (q.toDays !== undefined && days > q.toDays) return false;
      return true;
    });
  }

  async getEvent(id: string) {
    await delay(100);
    return this.world.events.find((e) => e.id === id) ?? null;
  }

  async getHistory(scope: "live" | "backtest") {
    await delay(120);
    return scope === "live" ? this.world.history : this.world.backtest;
  }

  async getPerformance(scope: "live" | "backtest") {
    await delay(160);
    return computePerformance(scope === "live" ? this.world.history : this.world.backtest, scope);
  }

  async getNotifications() {
    await delay(60);
    return this.notifications;
  }

  async markNotificationsRead() {
    this.notifications = this.notifications.map((n) => ({ ...n, read: true }));
  }

  async getSettings() {
    return this.settings;
  }

  async saveSettings(s: UserSettings) {
    this.settings = s;
    saveSettings(s);
    return s;
  }

  hasBacktest() {
    return true;
  }

  async getBookmakers(): Promise<Bookmaker[]> {
    return BOOKMAKERS;
  }

  async getProviderHealth(): Promise<ProviderHealth[]> {
    return [
      { id: "api-football", name: "API-Football", purpose: "Terminarze, wyniki, składy, kontuzje, statystyki", status: "not_configured", lastSync: null, quota: null },
      { id: "the-odds-api", name: "The Odds API", purpose: "Kursy wielu bukmacherów", status: "not_configured", lastSync: null, quota: null },
      { id: "sportmonks", name: "Sportmonks", purpose: "xG i statystyki zaawansowane", status: "not_configured", lastSync: null, quota: null },
      { id: "nba", name: "Statystyki NBA", purpose: "Ratingi, pace, dostępność zawodników", status: "not_configured", lastSync: null, quota: null },
      { id: "euroleague", name: "Euroliga / EuroCup", purpose: "Terminarze i statystyki", status: "not_configured", lastSync: null, quota: null },
      { id: "pl-books", name: "STS · Fortuna · Superbet · Betclic", purpose: "Kursy polskich bukmacherów", status: "unverified", lastSync: null, quota: null },
    ];
  }
}
