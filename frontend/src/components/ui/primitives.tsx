import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { LuChevronRight } from "react-icons/lu";
import { cn } from "../../lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card", className)} {...props} />;
}

type ChipTone = "neutral" | "accent" | "pos" | "warn" | "neg" | "blue";

const chipTones: Record<ChipTone, string> = {
  neutral: "bg-white/[0.05] text-fg-muted ring-white/[0.06]",
  accent: "bg-accent/10 text-accent ring-accent/20",
  blue: "bg-accent-blue/10 text-accent-blue ring-accent-blue/20",
  pos: "bg-pos/10 text-pos ring-pos/20",
  warn: "bg-warn/10 text-warn ring-warn/20",
  neg: "bg-neg/10 text-neg ring-neg/20",
};

export function Badge({ tone = "neutral", className, children, icon }: { tone?: ChipTone; className?: string; children: ReactNode; icon?: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset whitespace-nowrap", chipTones[tone], className)}>
      {icon}
      {children}
    </span>
  );
}

export function DemoBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn("inline-flex items-center rounded-md bg-warn/15 px-1.5 py-px text-[10px] font-bold tracking-wider text-warn ring-1 ring-inset ring-warn/30", className)}
      title="Dane demonstracyjne — nie są prognozą"
    >
      DEMO
    </span>
  );
}

export function FilterChip({ active, className, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        "inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full px-3.5 text-[13px] font-medium ring-1 ring-inset transition-colors duration-200",
        active ? "bg-accent/15 text-accent ring-accent/35" : "bg-ink-800 text-fg-muted ring-line hover:text-fg",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function SectionHeader({ title, subtitle, action, onAction }: { title: string; subtitle?: string; action?: string; onAction?: () => void }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3 px-1">
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold tracking-tight text-fg">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-fg-faint">{subtitle}</p>}
      </div>
      {action && (
        <button type="button" onClick={onAction} className="-mr-1 flex shrink-0 items-center gap-0.5 rounded-lg px-1.5 py-1 text-[13px] font-medium text-accent hover:text-accent-strong">
          {action}
          <LuChevronRight className="size-4" />
        </button>
      )}
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  className,
  size = "md",
}: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (v: T) => void;
  className?: string;
  size?: "sm" | "md";
}) {
  const idx = Math.max(0, options.findIndex((o) => o.value === value));
  return (
    <div role="tablist" className={cn("relative grid rounded-xl bg-ink-900 p-1 ring-1 ring-inset ring-line", className)} style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      <span
        aria-hidden
        className="absolute inset-y-1 left-1 rounded-[0.6rem] bg-ink-700 shadow-[0_1px_0_0_rgb(255_255_255/0.06)_inset] transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]"
        style={{ width: `calc((100% - 0.5rem) / ${options.length})`, transform: `translateX(${idx * 100}%)` }}
      />
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          type="button"
          aria-selected={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn(
            "relative z-10 flex items-center justify-center gap-1.5 rounded-[0.6rem] font-medium transition-colors",
            size === "sm" ? "h-8 text-xs" : "h-9 text-[13px]",
            o.value === value ? "text-fg" : "text-fg-faint hover:text-fg-muted",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Toggle({ checked, onChange, label, description }: { checked: boolean; onChange: (v: boolean) => void; label: string; description?: string }) {
  return (
    <label className="flex min-h-12 cursor-pointer items-center justify-between gap-4 py-2">
      <span className="min-w-0">
        <span className="block text-sm text-fg">{label}</span>
        {description && <span className="mt-0.5 block text-xs text-fg-faint">{description}</span>}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn("relative h-7 w-12 shrink-0 rounded-full transition-colors duration-200", checked ? "bg-accent" : "bg-ink-600")}
      >
        <span className={cn("absolute top-1 left-1 size-5 rounded-full bg-white shadow transition-transform duration-200", checked && "translate-x-5")} />
      </button>
    </label>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

export function EmptyState({ icon, title, body, className }: { icon: ReactNode; title: string; body?: string; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center px-6 py-10 text-center", className)}>
      <div className="mb-4 grid size-12 place-items-center rounded-2xl bg-ink-800 text-fg-muted ring-1 ring-inset ring-line">{icon}</div>
      <p className="max-w-xs text-sm font-semibold text-fg">{title}</p>
      {body && <p className="mt-1.5 max-w-xs text-[13px] leading-relaxed text-fg-faint">{body}</p>}
    </div>
  );
}

export function KeyValue({ label, value, hint, className }: { label: string; value: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <div className="text-[11px] font-medium tracking-wide text-fg-faint uppercase">{label}</div>
      <div className="tnum mt-1 text-[15px] font-semibold text-fg">{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-fg-faint">{hint}</div>}
    </div>
  );
}
