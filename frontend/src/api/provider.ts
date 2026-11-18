// Data access contract. DemoProvider implements it now; HttpProvider (stage 3+) will call the FastAPI backend.
import type {
  AppNotification,
  Bookmaker,
  DashboardSummary,
  HistoryEntry,
  ModelStatus,
  PerformanceSummary,
  ProviderHealth,
  Sport,
  SportEvent,
  UserSettings,
} from "../types/domain";

export interface EventQuery {
  sport?: Sport | "all";
  fromDays?: number;
  toDays?: number;
}

export interface DataProvider {
  readonly mode: "demo" | "live";
  getDashboard(): Promise<DashboardSummary>;
  getEvents(q?: EventQuery): Promise<SportEvent[]>;
  getEvent(id: string): Promise<SportEvent | null>;
  getHistory(scope: "live" | "backtest"): Promise<HistoryEntry[]>;
  getPerformance(scope: "live" | "backtest"): Promise<PerformanceSummary>;
  getNotifications(): Promise<AppNotification[]>;
  markNotificationsRead(): Promise<void>;
  getSettings(): Promise<UserSettings>;
  saveSettings(s: UserSettings): Promise<UserSettings>;
  getProviderHealth(): Promise<ProviderHealth[]>;
  getBookmakers(): Promise<Bookmaker[]>;
  /** Whether a historical backtest dataset is available. */
  hasBacktest(): boolean;
  /** Which competitions the model may recommend in (backtest verdict). */
  getModelStatus(): Promise<ModelStatus[]>;
}
