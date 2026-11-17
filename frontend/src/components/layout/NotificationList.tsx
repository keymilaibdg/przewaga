import { LuBadgeCheck, LuCircleMinus, LuSparkles, LuTrendingDown, LuTriangleAlert, LuUsers } from "react-icons/lu";
import type { AppNotification } from "../../types/domain";
import { cn } from "../../lib/cn";
import { fmtAgo } from "../../lib/format";
import { navigate } from "../../router";
import { EmptyState } from "../ui/primitives";

const ICONS: Record<AppNotification["kind"], { icon: typeof LuSparkles; cls: string }> = {
  new_value: { icon: LuSparkles, cls: "bg-pos/12 text-pos" },
  odds_move: { icon: LuTrendingDown, cls: "bg-accent-blue/12 text-accent-blue" },
  withdrawn: { icon: LuCircleMinus, cls: "bg-neg/12 text-neg" },
  lineup: { icon: LuUsers, cls: "bg-accent/12 text-accent" },
  settled: { icon: LuBadgeCheck, cls: "bg-white/[0.06] text-fg-muted" },
  system: { icon: LuTriangleAlert, cls: "bg-warn/12 text-warn" },
};

export function NotificationList({ items, compact, onOpen }: { items: AppNotification[]; compact?: boolean; onOpen?: () => void }) {
  if (!items.length) return <EmptyState icon={<LuSparkles className="size-5" />} title="Brak powiadomień" />;
  return (
    <ul className="divide-y divide-line">
      {items.map((n) => {
        const { icon: Icon, cls } = ICONS[n.kind];
        return (
          <li key={n.id}>
            <button
              type="button"
              disabled={!n.eventId}
              onClick={() => {
                if (!n.eventId) return;
                onOpen?.();
                navigate(`/mecz/${encodeURIComponent(n.eventId)}`);
              }}
              className="flex w-full gap-3 py-3 text-left disabled:cursor-default"
            >
              <span className={cn("grid size-9 shrink-0 place-items-center rounded-xl", cls)}>
                <Icon className="size-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate text-[13px] font-semibold text-fg">{n.title}</span>
                  <span className="shrink-0 text-[10px] text-fg-faint">{fmtAgo(n.at)}</span>
                </span>
                <span className={cn("mt-0.5 block text-xs leading-snug text-fg-muted", compact && "line-clamp-2")}>{n.body}</span>
              </span>
              {!n.read && <span className="mt-1.5 size-2 shrink-0 rounded-full bg-accent" aria-label="Nowe" />}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
