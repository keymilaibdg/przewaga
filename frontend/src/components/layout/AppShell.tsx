import type { ReactNode } from "react";
import { LuArrowLeft, LuChartColumn, LuHouse, LuCalendarDays, LuTarget, LuUser } from "react-icons/lu";
import { cn } from "../../lib/cn";
import { goBack, navigate } from "../../router";

const NAV = [
  { to: "/", label: "Start", icon: LuHouse, match: (p: string) => p === "/" },
  { to: "/typy", label: "Typy", icon: LuTarget, match: (p: string) => p.startsWith("/typy") },
  { to: "/mecze", label: "Mecze", icon: LuCalendarDays, match: (p: string) => p.startsWith("/mecz") },
  { to: "/statystyki", label: "Statystyki", icon: LuChartColumn, match: (p: string) => p.startsWith("/statystyki") },
  { to: "/profil", label: "Profil", icon: LuUser, match: (p: string) => p.startsWith("/profil") },
];

export function AppShell({ path, demo, children }: { path: string; demo: boolean; children: ReactNode }) {
  return (
    <div className="app-backdrop min-h-dvh">
      {demo && (
        <div className="pt-safe sticky top-0 z-40 border-b border-warn/20 bg-[#1a1608]/90 backdrop-blur-md">
          <p className="mx-auto flex h-7 max-w-xl items-center justify-center truncate px-4 text-[11px] font-medium text-warn">
            TRYB DEMO · dane fikcyjne — to nie są rekomendacje
          </p>
        </div>
      )}
      <main className="mx-auto max-w-xl px-4 pb-[calc(6rem+env(safe-area-inset-bottom))]">{children}</main>
      <BottomNav path={path} />
    </div>
  );
}

function BottomNav({ path }: { path: string }) {
  return (
    <nav className="pb-safe fixed inset-x-0 bottom-0 z-40 border-t border-line bg-ink-950/85 backdrop-blur-xl" aria-label="Nawigacja główna">
      <ul className="mx-auto grid h-16 max-w-xl grid-cols-5">
        {NAV.map(({ to, label, icon: Icon, match }) => {
          const active = match(path);
          return (
            <li key={to}>
              <button
                type="button"
                onClick={() => navigate(to)}
                aria-current={active ? "page" : undefined}
                className={cn("relative flex h-full w-full flex-col items-center justify-center gap-1 text-[11px] font-medium transition-colors", active ? "text-fg" : "text-fg-faint hover:text-fg-muted")}
              >
                <span className={cn("absolute top-0 h-0.5 w-8 rounded-full bg-accent transition-opacity duration-300", active ? "opacity-100" : "opacity-0")} />
                <span className={cn("grid h-7 w-12 place-items-center rounded-full transition-colors duration-300", active && "bg-accent/12 text-accent")}>
                  <Icon className="size-[21px]" strokeWidth={active ? 2.2 : 1.8} />
                </span>
                {label}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function PageHeader({ title, subtitle, back, actions }: { title: string; subtitle?: ReactNode; back?: boolean; actions?: ReactNode }) {
  return (
    <header className="flex items-center gap-3 pt-5 pb-4">
      {back && (
        <button type="button" onClick={() => goBack("/mecze")} className="-ml-2 grid size-10 shrink-0 place-items-center rounded-full text-fg-muted hover:bg-white/5" aria-label="Wstecz">
          <LuArrowLeft className="size-5" />
        </button>
      )}
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[22px] font-bold tracking-tight">{title}</h1>
        {subtitle && <div className="mt-0.5 text-[13px] text-fg-faint">{subtitle}</div>}
      </div>
      {actions}
    </header>
  );
}

export function ResponsibleNote({ className }: { className?: string }) {
  return (
    <p className={cn("px-2 text-center text-[11px] leading-relaxed text-fg-faint", className)}>
      18+. Zakłady wiążą się z ryzykiem utraty pieniędzy. Prognozy są szacunkami statystycznymi, nie gwarancją wyniku. Graj tylko u legalnych bukmacherów i w ustalonych limitach.
    </p>
  );
}
