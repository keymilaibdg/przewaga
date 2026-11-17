import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { DataProvider } from "./provider";
import type { UserSettings } from "../types/domain";
import { DEFAULT_SETTINGS } from "./settingsStore";

interface DataContextValue {
  provider: DataProvider;
  settings: UserSettings;
  updateSettings: (s: UserSettings) => Promise<void>;
  /** Incremented on manual refresh; queries depend on it. */
  revision: number;
  refresh: () => void;
}

const Ctx = createContext<DataContextValue | null>(null);

export function DataProviderRoot({ provider, children }: { provider: DataProvider; children: ReactNode }) {
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    provider.getSettings().then(setSettings);
  }, [provider]);

  const updateSettings = useCallback(
    async (s: UserSettings) => {
      setSettings(await provider.saveSettings(s));
    },
    [provider],
  );

  const refresh = useCallback(() => setRevision((r) => r + 1), []);

  return <Ctx.Provider value={{ provider, settings, updateSettings, revision, refresh }}>{children}</Ctx.Provider>;
}

export function useData(): DataContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useData must be used inside DataProviderRoot");
  return v;
}

export interface QueryState<T> {
  data: T | undefined;
  loading: boolean;
  error: Error | null;
}

/** Minimal async query hook; re-runs when deps or global revision change. */
export function useQuery<T>(fn: (p: DataProvider) => Promise<T>, deps: unknown[] = []): QueryState<T> {
  const { provider, revision } = useData();
  const [state, setState] = useState<QueryState<T>>({ data: undefined, loading: true, error: null });

  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn(provider)
      .then((data) => alive && setState({ data, loading: false, error: null }))
      .catch((error: Error) => alive && setState({ data: undefined, loading: false, error }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider, revision, ...deps]);

  return state;
}
