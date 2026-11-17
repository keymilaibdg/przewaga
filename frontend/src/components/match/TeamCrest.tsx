import { useId, useState } from "react";
import type { Team } from "../../types/domain";
import { cn } from "../../lib/cn";

function luminance(hex: string): number {
  const v = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Provider logo when available, otherwise a generated monogram shield in team colours. */
export function TeamCrest({ team, size = 36, className }: { team: Team; size?: number; className?: string }) {
  const gid = useId().replace(/:/g, "");
  const [broken, setBroken] = useState(false);
  if (team.logoUrl && !broken) {
    return <img src={team.logoUrl} alt="" width={size} height={size} loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken(true)} className={cn("shrink-0 object-contain", className)} />;
  }
  const [c1, c2] = team.colors;
  const text = luminance(c1) > 0.6 ? "#0a0f1c" : "#ffffff";
  const label = team.shortName.slice(0, 3);
  return (
    <svg width={size} height={size} viewBox="0 0 40 44" className={cn("shrink-0 drop-shadow-[0_4px_10px_rgba(0,0,0,0.35)]", className)} aria-hidden>
      <defs>
        <linearGradient id={`c${gid}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={c1} />
          <stop offset="100%" stopColor={c1} stopOpacity={0.78} />
        </linearGradient>
      </defs>
      <path d="M20 1.5 37 6.5v14.2c0 10.6-7.2 18.3-17 21.8C10.2 39 3 31.3 3 20.7V6.5L20 1.5Z" fill={`url(#c${gid})`} stroke={c2} strokeOpacity={0.9} strokeWidth={1.6} />
      <path d="M20 1.5 37 6.5v14.2c0 10.6-7.2 18.3-17 21.8" fill="white" fillOpacity={0.06} />
      <text x="20" y="25.5" textAnchor="middle" fontSize={label.length > 2 ? 10.5 : 13} fontWeight={700} fill={text} fontFamily="Inter, sans-serif" letterSpacing="0.02em">
        {label}
      </text>
    </svg>
  );
}
