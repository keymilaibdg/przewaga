import { useEffect, useState, type ReactNode } from "react";
import { LuDownload, LuHeartHandshake, LuLock, LuPlug, LuSmartphone, LuUser } from "react-icons/lu";
import { useData, useQuery } from "../api/DataContext";
import { PageHeader } from "../components/layout/AppShell";
import { Badge, Card, Segmented, Toggle } from "../components/ui/primitives";
import { fmtPct } from "../lib/format";
import type { ProviderHealth, RiskLevel, UserSettings } from "../types/domain";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function ProfilePage() {
  const { settings, updateSettings, provider } = useData();
  const health = useQuery((p) => p.getProviderHealth());
  const books = useQuery((p) => p.getBookmakers());
  const live = provider.mode === "live";
  const set = <K extends keyof UserSettings>(k: K, v: UserSettings[K]) => updateSettings({ ...settings, [k]: v });

  return (
    <div className="animate-fade-up space-y-6">
      <PageHeader title="Profil" subtitle="Ustawienia, źródła danych i odpowiedzialna gra" />

      <Card className="flex items-center gap-4 p-4">
        <div className="grid size-12 place-items-center rounded-2xl bg-ink-700 text-fg-muted">
          <LuUser className="size-6" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-semibold">Użytkownik lokalny</div>
          <div className="text-xs text-fg-faint">Aplikacja jednego użytkownika — ustawienia zapisywane na tym urządzeniu</div>
        </div>
        <Badge tone={live ? "pos" : "warn"} icon={<LuLock className="size-3" />}>
          {live ? "Dane live" : "DEMO"}
        </Badge>
      </Card>

      <Group title="Kryteria rekomendacji" desc="Twoje progi działają dodatkowo do progów silnika (EV > 0, ocena ≥ 60). Można je tylko zaostrzyć.">
        <div className="py-2">
          <div className="text-sm">Dyscypliny</div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {(["football", "basketball"] as const).map((s) => {
              const on = settings.sports.includes(s);
              return (
                <button
                  key={s}
                  type="button"
                  aria-pressed={on}
                  onClick={() => set("sports", on ? settings.sports.filter((x) => x !== s) : [...settings.sports, s])}
                  className={`h-10 rounded-xl text-[13px] font-medium ring-1 ring-inset transition-colors ${on ? "bg-accent/15 text-accent ring-accent/30" : "bg-ink-800 text-fg-faint ring-line"}`}
                >
                  {s === "football" ? "Piłka nożna" : "Koszykówka"}
                </button>
              );
            })}
          </div>
        </div>
        <Slider label="Minimalna ocena analizy" value={settings.minQuality} min={60} max={90} step={5} display={`${settings.minQuality}/100`} onChange={(v) => set("minQuality", v)} />
        <Slider label="Minimalne EV" value={Math.round(settings.minEv * 100)} min={2} max={10} step={1} display={`+${fmtPct(settings.minEv, 0)}`} onChange={(v) => set("minEv", v / 100)} />
        <div className="py-2">
          <div className="mb-2 text-sm">Maksymalny poziom ryzyka</div>
          <Segmented<RiskLevel>
            value={settings.maxRisk}
            onChange={(v) => set("maxRisk", v)}
            options={[
              { value: "low", label: "Niskie" },
              { value: "medium", label: "Średnie" },
              { value: "high", label: "Wysokie" },
            ]}
          />
        </div>
      </Group>

      <Group
        title="Bukmacherzy"
        desc={live ? "Bukmacherzy dostępni w źródle kursów (region EU). Rekomendacja wskazuje najlepszy kurs spośród zaznaczonych." : "Rekomendacja wskazuje najlepszy kurs tylko spośród zaznaczonych."}
      >
        {(books.data ?? []).map((b) => (
          <Toggle
            key={b.id}
            label={b.name}
            description={live ? undefined : "Integracja niezweryfikowana"}
            checked={!settings.excludedBookmakers.includes(b.id)}
            onChange={(on) => set("excludedBookmakers", on ? settings.excludedBookmakers.filter((x) => x !== b.id) : [...settings.excludedBookmakers, b.id])}
          />
        ))}
        {books.data?.length === 0 && <p className="py-3 text-xs text-fg-faint">Brak danych o bukmacherach — pojawią się po pierwszym pobraniu kursów.</p>}
      </Group>

      <Group title="Powiadomienia" desc="Powiadomienia push działają po instalacji PWA i uruchomieniu backendu (ETAP 6).">
        <Toggle label="Nowe okazje z dodatnim EV" checked={settings.notifications.newValue} onChange={(v) => set("notifications", { ...settings.notifications, newValue: v })} />
        <Toggle label="Istotne zmiany kursów" checked={settings.notifications.oddsMove} onChange={(v) => set("notifications", { ...settings.notifications, oddsMove: v })} />
        <Toggle label="Wycofane rekomendacje" checked={settings.notifications.withdrawn} onChange={(v) => set("notifications", { ...settings.notifications, withdrawn: v })} />
        <Toggle label="Potwierdzone składy" checked={settings.notifications.lineups} onChange={(v) => set("notifications", { ...settings.notifications, lineups: v })} />
      </Group>

      <Group title="Źródła danych" desc={live ? "Stan ostatniego pobrania z każdego źródła. Aktualizacja 1–2 razy dziennie (limit darmowych planów)." : "Stan integracji API. W trybie DEMO żadne źródło nie jest podłączone."}>
        {(health.data ?? []).map((h) => (
          <ProviderRow key={h.id} h={h} />
        ))}
      </Group>

      <Group title="Podatek od stawki" desc="Legalni bukmacherzy w Polsce pobierają 12% od stawki. Aplikacja przelicza minimalny kurs, przy którym zakład nadal ma dodatnie EV.">
        <div className="py-3">
          <Segmented
            value={settings.stakeTax === 0 ? "0" : "12"}
            onChange={(v) => set("stakeTax", v === "0" ? 0 : 0.12)}
            options={[
              { value: "12", label: "12% (standard)" },
              { value: "0", label: "0% (zakład bez podatku)" },
            ]}
          />
          <p className="mt-2 text-[11px] leading-relaxed text-fg-faint">Kursy w aplikacji pochodzą od bukmacherów europejskich i służą jako punkt odniesienia. W Polsce obstawiaj wyłącznie u bukmacherów z zezwoleniem Ministra Finansów.</p>
        </div>
      </Group>

      <Group title="Odpowiedzialna gra" icon={<LuHeartHandshake className="size-4 text-pos" />}>
        <Slider label="Wielkość jednostki stawki" value={settings.unitStake} min={5} max={100} step={5} display={`${settings.unitStake} zł`} onChange={(v) => set("unitStake", v)} />
        <Slider label="Dzienny limit" value={settings.dailyLimitUnits} min={1} max={20} step={1} display={`${settings.dailyLimitUnits} j. (${settings.dailyLimitUnits * settings.unitStake} zł)`} onChange={(v) => set("dailyLimitUnits", v)} />
        <div className="space-y-2 py-3 text-xs leading-relaxed text-fg-muted">
          <p>Aplikacja jest narzędziem analitycznym. Nie obiecuje zysku — nawet zakłady z dodatnim EV przegrywają często, a seria strat jest normalnym zjawiskiem.</p>
          <p>Obstawiaj wyłącznie kwoty, których utrata nie wpłynie na Twoje życie. Jeśli granie przestaje być rozrywką lub gonisz straty — zrób przerwę i porozmawiaj ze specjalistą.</p>
        </div>
      </Group>

      {__NATIVE__ ? <UpdateCard /> : <InstallCard />}

      <p className="pb-2 text-center text-[11px] text-fg-faint">
        Przewaga v{__APP_VERSION__} · {__NATIVE__ ? "Android" : "web"} · tryb {live ? "live" : "DEMO"}
      </p>
    </div>
  );
}

function Group({ title, desc, icon, children }: { title: string; desc?: string; icon?: ReactNode; children: ReactNode }) {
  return (
    <section>
      <h2 className="flex items-center gap-2 px-1 text-[15px] font-semibold">
        {icon}
        {title}
      </h2>
      {desc && <p className="mt-0.5 px-1 text-xs leading-relaxed text-fg-faint">{desc}</p>}
      <Card className="mt-3 divide-y divide-line px-4 py-1">{children}</Card>
    </section>
  );
}

function Slider({ label, value, min, max, step, display, onChange }: { label: string; value: number; min: number; max: number; step: number; display: string; onChange: (v: number) => void }) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <label className="block py-3">
      <span className="flex items-center justify-between text-sm">
        <span>{label}</span>
        <span className="tnum font-semibold text-accent">{display}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-3 h-1.5 w-full cursor-pointer appearance-none rounded-full [&::-moz-range-thumb]:size-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-white [&::-webkit-slider-thumb]:size-5 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-[0_2px_8px_rgba(0,0,0,.5)]"
        style={{ background: `linear-gradient(90deg, var(--color-accent) ${pct}%, var(--color-ink-600) ${pct}%)` }}
      />
    </label>
  );
}

const STATUS: Record<ProviderHealth["status"], { label: string; tone: "pos" | "neutral" | "neg" | "warn" }> = {
  connected: { label: "Połączono", tone: "pos" },
  not_configured: { label: "Brak klucza", tone: "neutral" },
  error: { label: "Błąd", tone: "neg" },
  unverified: { label: "Niezweryfikowane", tone: "warn" },
};

function ProviderRow({ h }: { h: ProviderHealth }) {
  const st = STATUS[h.status];
  return (
    <div className="flex items-center gap-3 py-3">
      <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-ink-700 text-fg-muted">
        <LuPlug className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-medium">{h.name}</span>
        <span className="block truncate text-[11px] text-fg-faint">{h.purpose}</span>
      </span>
      <Badge tone={st.tone}>{st.label}</Badge>
    </div>
  );
}

function InstallCard() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState(() => {
    try {
      return window.matchMedia("(display-mode: standalone)").matches;
    } catch {
      return false;
    }
  });
  useEffect(() => {
    const on = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
    };
    const done = () => setInstalled(true);
    window.addEventListener("beforeinstallprompt", on);
    window.addEventListener("appinstalled", done);
    return () => {
      window.removeEventListener("beforeinstallprompt", on);
      window.removeEventListener("appinstalled", done);
    };
  }, []);

  return (
    <section>
      <h2 className="flex items-center gap-2 px-1 text-[15px] font-semibold">
        <LuSmartphone className="size-4 text-accent" /> Aplikacja na Androidzie
      </h2>
      <Card className="mt-3 p-4">
        {installed ? (
          <p className="text-sm text-pos">Aplikacja działa w trybie zainstalowanym.</p>
        ) : deferred ? (
          <button
            type="button"
            onClick={async () => {
              await deferred.prompt();
              setDeferred(null);
            }}
            className="flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-accent font-semibold text-ink-950 active:scale-[0.98]"
          >
            <LuDownload className="size-5" /> Zainstaluj aplikację
          </button>
        ) : (
          <ol className="list-decimal space-y-1.5 pl-5 text-[13px] text-fg-muted">
            <li>Otwórz aplikację w Chrome na Androidzie.</li>
            <li>Stuknij menu ⋮ w prawym górnym rogu.</li>
            <li>Wybierz „Dodaj do ekranu głównego” → „Zainstaluj”.</li>
          </ol>
        )}
      </Card>
    </section>
  );
}

function newerThan(a: string, b: string): boolean {
  const pa = a.replace(/^v/, "").split(".").map(Number);
  const pb = b.replace(/^v/, "").split(".").map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    if ((pa[i] ?? 0) !== (pb[i] ?? 0)) return (pa[i] ?? 0) > (pb[i] ?? 0);
  }
  return false;
}

/** APK: checks GitHub Releases of the public repository for a newer version. */
function UpdateCard() {
  const [state, setState] = useState<{ status: "checking" | "latest" | "update" | "error"; tag?: string; url?: string }>({ status: "checking" });
  useEffect(() => {
    if (!__REPO__) {
      setState({ status: "error" });
      return;
    }
    fetch(`https://api.github.com/repos/${__REPO__}/releases/latest`, { headers: { Accept: "application/vnd.github+json" } })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((rel: { tag_name: string; html_url: string }) =>
        setState(newerThan(rel.tag_name, __APP_VERSION__) ? { status: "update", tag: rel.tag_name, url: rel.html_url } : { status: "latest", tag: rel.tag_name }),
      )
      .catch(() => setState({ status: "error" }));
  }, []);
  return (
    <section>
      <h2 className="flex items-center gap-2 px-1 text-[15px] font-semibold">
        <LuSmartphone className="size-4 text-accent" /> Wersja aplikacji
      </h2>
      <Card className="mt-3 p-4 text-sm">
        {state.status === "checking" && <p className="text-fg-muted">Sprawdzam dostępność nowej wersji…</p>}
        {state.status === "latest" && <p className="text-pos">Masz najnowszą wersję ({__APP_VERSION__}).</p>}
        {state.status === "error" && <p className="text-fg-faint">Nie udało się sprawdzić aktualizacji (brak internetu).</p>}
        {state.status === "update" && (
          <>
            <p className="text-fg">
              Dostępna nowa wersja <b>{state.tag}</b> (masz {__APP_VERSION__}).
            </p>
            <a href={state.url} target="_blank" rel="noreferrer" className="mt-3 flex h-12 items-center justify-center gap-2 rounded-xl bg-accent font-semibold text-ink-950">
              <LuDownload className="size-5" /> Pobierz aktualizację
            </a>
            <p className="mt-2 text-[11px] text-fg-faint">Pobierz plik APK i zainstaluj go — ustawienia i historia zostaną zachowane.</p>
          </>
        )}
      </Card>
    </section>
  );
}
