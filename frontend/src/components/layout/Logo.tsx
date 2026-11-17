import { useId } from "react";

export function LogoMark({ size = 32 }: { size?: number }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <defs>
        <linearGradient id={`lg${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#2fd6ea" />
          <stop offset="100%" stopColor="#4f8dff" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="#0e1525" />
      <rect x="0.75" y="0.75" width="62.5" height="62.5" rx="15.25" fill="none" stroke="white" strokeOpacity="0.08" strokeWidth="1.5" />
      <path d="M14 44 L26 32 L34 38 L50 20" fill="none" stroke={`url(#lg${id})`} strokeWidth="5.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="50" cy="20" r="5" fill="#2fd6ea" />
    </svg>
  );
}

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark size={34} />
      <div className="leading-none">
        <div className="text-[17px] font-bold tracking-tight">Przewaga</div>
        <div className="mt-1 text-[10px] font-medium tracking-[0.14em] text-fg-faint uppercase">Analityka zakładów</div>
      </div>
    </div>
  );
}
