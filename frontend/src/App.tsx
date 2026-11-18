import { useEffect, useState } from "react";
import { DataProviderRoot } from "./api/DataContext";
import { DemoProvider } from "./api/demoProvider";
import { StaticDataProvider, detectLiveData } from "./api/staticProvider";
import type { DataProvider } from "./api/provider";
import { LogoMark } from "./components/layout/Logo";
import { AppShell } from "./components/layout/AppShell";
import { CouponProvider } from "./api/CouponContext";
import { CouponButton } from "./components/coupon/Coupon";
import { useRoute } from "./router";
import { DashboardPage } from "./pages/Dashboard";
import { TipsPage } from "./pages/Tips";
import { MatchesPage } from "./pages/Matches";
import { MatchDetailPage } from "./pages/MatchDetail";
import { StatsPage } from "./pages/Stats";
import { ProfilePage } from "./pages/Profile";

export function App() {
  // Live data published by the pipeline wins; without it the app runs on clearly-labelled DEMO data.
  const [provider, setProvider] = useState<DataProvider | null>(null);
  const [noData, setNoData] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const route = useRoute();
  useEffect(() => {
    setNoData(false);
    detectLiveData(__DATA_URL__).then((live) => {
      if (live) setProvider(new StaticDataProvider(live.meta, __DATA_URL__, live.offlineSince));
      else if (__NATIVE__) setNoData(true); // the APK never silently switches to DEMO data
      else setProvider(new DemoProvider());
    });
  }, [attempt]);

  if (noData && !provider) {
    return <NoDataScreen onRetry={() => setAttempt((a) => a + 1)} onDemo={() => setProvider(new DemoProvider())} />;
  }
  const [first, second] = route.segments;

  let page;
  switch (first) {
    case undefined:
      page = <DashboardPage />;
      break;
    case "typy":
      page = <TipsPage />;
      break;
    case "mecze":
      page = <MatchesPage initialSport={route.query.get("sport")} initialView={route.query.get("widok")} />;
      break;
    case "mecz":
      page = <MatchDetailPage id={decodeURIComponent(second ?? "")} />;
      break;
    case "statystyki":
      page = <StatsPage initialTab={route.query.get("zakladka")} />;
      break;
    case "profil":
      page = <ProfilePage />;
      break;
    default:
      page = <DashboardPage />;
  }

  if (!provider) {
    return (
      <div className="app-backdrop grid min-h-dvh place-items-center">
        <div className="animate-fade-in flex flex-col items-center gap-3 text-fg-faint">
          <LogoMark size={56} />
          <span className="text-xs">Ładowanie danych…</span>
        </div>
      </div>
    );
  }

  return (
    <DataProviderRoot provider={provider}>
      <CouponProvider>
        <AppShell path={route.path} demo={provider.mode === "demo"}>
          <div key={`${route.path}?${route.query.toString()}`}>{page}</div>
        </AppShell>
        <CouponButton />
      </CouponProvider>
    </DataProviderRoot>
  );
}

function NoDataScreen({ onRetry, onDemo }: { onRetry: () => void; onDemo: () => void }) {
  return (
    <div className="app-backdrop pt-safe grid min-h-dvh place-items-center px-6">
      <div className="animate-fade-up flex max-w-sm flex-col items-center text-center">
        <LogoMark size={56} />
        <h1 className="mt-5 text-lg font-bold">Brak danych do wyświetlenia</h1>
        <p className="mt-2 text-sm leading-relaxed text-fg-muted">
          Nie udało się pobrać analiz. Sprawdź połączenie z internetem. Jeśli to pierwsze uruchomienie, pierwsza automatyczna aktualizacja mogła się jeszcze nie wykonać.
        </p>
        <button type="button" onClick={onRetry} className="mt-6 h-12 w-full rounded-xl bg-accent font-semibold text-ink-950 active:scale-[0.98]">
          Spróbuj ponownie
        </button>
        <button type="button" onClick={onDemo} className="mt-3 h-11 w-full rounded-xl bg-ink-850 text-sm font-medium text-fg-muted ring-1 ring-line">
          Pokaż wersję DEMO (dane fikcyjne)
        </button>
      </div>
    </div>
  );
}
