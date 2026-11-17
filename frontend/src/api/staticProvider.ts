// Live data: JSON files published by the pipeline (GitHub Actions) next to the app: /data/*.json.
import type { DataProvider, EventQuery } from "./provider";
import type {
  AppNotification,
  Bookmaker,
  DashboardSummary,
  Freshness,
  HistoryEntry,
  PerformanceSummary,
  ProviderHealth,
  SportEvent,
  UserSettings,
} from "../types/domain";
import { computePerformance } from "../lib/performance";
import { registerBookmakers } from "../lib/bookmakers";
import { loadSettings, saveSettings } from "./settingsStore";

export interface LiveMeta {
  origin: "live";
  generatedAt: string;
  runKind: string;
  bookmakers: Record<string, string>;
  providers: ProviderHealth[];
  notifications: AppNotification[];
  backtestAvailable: boolean;
}

const READ_KEY = "przewaga.notifications.read";
const CACHE_PREFIX = "przewaga.cache.";

interface Cached<T> {
  savedAt: string;
  body: T;
}

/** Fetch JSON; on success keep a copy on the device, on failure (offline) return the last copy. */
async function getJson<T>(url: string, cacheKey: string): Promise<{ body: T; fromCache: string | null }> {
  try {
    const res = await fetch(`${url}${url.includes("?") ? "&" : "?"}t=${Math.floor(Date.now() / 300_000)}`, { cache: "no-cache" });
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
    const body = (await res.json()) as T;
    try {
      localStorage.setItem(CACHE_PREFIX + cacheKey, JSON.stringify({ savedAt: new Date().toISOString(), body } satisfies Cached<T>));
    } catch {
      /* storage full or unavailable: still fine online */
    }
    return { body, fromCache: null };
  } catch (err) {
    try {
      const raw = localStorage.getItem(CACHE_PREFIX + cacheKey);
      if (raw) {
        const c = JSON.parse(raw) as Cached<T>;
        return { body: c.body, fromCache: c.savedAt };
      }
    } catch {
      /* ignore */
    }
    throw err;
  }
}

export interface LiveDetection {
  meta: LiveMeta;
  /** ISO time of the cached copy when the network was unavailable, otherwise null. */
  offlineSince: string | null;
}

/** Returns live metadata when the pipeline has published data (or a cached copy exists), otherwise null. */
export async function detectLiveData(base: string): Promise<LiveDetection | null> {
  try {
    const { body, fromCache } = await getJson<LiveMeta>(`${base}/meta.json`, "meta");
    return body?.origin === "live" ? { meta: body, offlineSince: fromCache } : null;
  } catch {
    return null;
  }
}

export function datasetFreshness(generatedAt: string, now = Date.now()): Freshness {
  const h = (now - Date.parse(generatedAt)) / 3_600_000;
  if (h <= 13) return "fresh";
  if (h <= 30) return "aging";
  return "stale";
}

export class StaticDataProvider implements DataProvider {
  readonly mode = "live" as const;
  private events: Promise<SportEvent[]>;
  private history: Promise<HistoryEntry[]>;
  private settings: UserSettings = loadSettings();
  private read: Set<string>;

  constructor(
    private meta: LiveMeta,
    base: string,
    readonly offlineSince: string | null = null,
  ) {
    registerBookmakers(meta.bookmakers);
    this.events = getJson<SportEvent[]>(`${base}/events.json`, "events").then((r) => r.body);
    this.history = getJson<HistoryEntry[]>(`${base}/history.json`, "history").then((r) => r.body);
    try {
      this.read = new Set(JSON.parse(localStorage.getItem(READ_KEY) ?? "[]") as string[]);
    } catch {
      this.read = new Set();
    }
  }

  async getDashboard(): Promise<DashboardSummary> {
    const events = await this.events;
    const recs = events.flatMap((e) => e.recommendations.filter((r) => r.status === "active"));
    return {
      origin: "live",
      generatedAt: this.meta.generatedAt,
      dataFreshness: datasetFreshness(this.meta.generatedAt),
      offline: this.offlineSince !== null,
      analyzedEvents: events.length,
      valueBets: recs.length,
      avgEv: recs.length ? recs.reduce((s, r) => s + r.ev, 0) / recs.length : null,
      withdrawnToday: events.flatMap((e) => e.recommendations).filter((r) => r.status === "withdrawn").length,
      staleSources: events.filter((e) => e.sources.some((s) => s.kind === "odds" && s.freshness === "stale")).length,
    };
  }

  async getEvents(q: EventQuery = {}): Promise<SportEvent[]> {
    const now = Date.now();
    return (await this.events).filter((e) => {
      if (q.sport && q.sport !== "all" && e.sport !== q.sport) return false;
      const days = (Date.parse(e.kickoff) - now) / 86_400_000;
      if (days < -0.15) return false; // started more than ~3.5 h ago
      if (q.toDays !== undefined && days > q.toDays) return false;
      return true;
    });
  }

  async getEvent(id: string) {
    return (await this.events).find((e) => e.id === id) ?? null;
  }

  async getHistory(scope: "live" | "backtest") {
    return scope === "live" ? this.history : [];
  }

  async getPerformance(scope: "live" | "backtest"): Promise<PerformanceSummary> {
    return computePerformance(scope === "live" ? await this.history : [], scope);
  }

  async getNotifications() {
    return this.meta.notifications.map((n) => ({ ...n, read: n.read || this.read.has(n.id) }));
  }

  async markNotificationsRead() {
    this.meta.notifications.forEach((n) => this.read.add(n.id));
    try {
      localStorage.setItem(READ_KEY, JSON.stringify([...this.read].slice(-200)));
    } catch {
      /* ignore */
    }
  }

  async getSettings() {
    return this.settings;
  }

  async saveSettings(s: UserSettings) {
    this.settings = s;
    saveSettings(s);
    return s;
  }

  async getProviderHealth() {
    return this.meta.providers;
  }

  async getBookmakers(): Promise<Bookmaker[]> {
    return Object.entries(this.meta.bookmakers)
      .map(([id, name]) => ({ id, name, integrationVerified: true }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  hasBacktest() {
    return this.meta.backtestAvailable;
  }
}
