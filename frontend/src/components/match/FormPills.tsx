import type { FormEntry } from "../../types/domain";
import { cn } from "../../lib/cn";

const styles = {
  W: "bg-pos/15 text-pos ring-pos/25",
  D: "bg-white/[0.06] text-fg-muted ring-white/10",
  L: "bg-neg/15 text-neg ring-neg/25",
};
const letters = { W: "W", D: "R", L: "P" };

/** Most recent first. W = wygrana, R = remis, P = porażka. */
export function FormPills({ form, count = 5, size = "sm" }: { form: FormEntry[]; count?: number; size?: "sm" | "md" }) {
  return (
    <div className="flex gap-1" aria-label="Forma: ostatnie mecze">
      {form.slice(0, count).map((f, i) => (
        <span
          key={i}
          title={`${f.home ? "Dom" : "Wyjazd"} vs ${f.opponent}: ${f.scored}:${f.conceded}`}
          className={cn("grid place-items-center rounded-md font-bold ring-1 ring-inset", size === "sm" ? "size-5 text-[10px]" : "size-7 text-xs", styles[f.result])}
        >
          {letters[f.result]}
        </span>
      ))}
    </div>
  );
}
