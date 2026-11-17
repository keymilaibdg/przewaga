import { LuReceipt } from "react-icons/lu";
import { useData } from "../../api/DataContext";
import { minPriceWithTax } from "../../lib/odds";
import { fmtPct, fmtPrice } from "../../lib/format";
import { cn } from "../../lib/cn";

/** Minimum price at the user's (legal, Polish) bookmaker for the bet to keep positive EV after the stake tax. */
export function PlPriceHint({ prob, className }: { prob: number; className?: string }) {
  const { settings } = useData();
  const min = minPriceWithTax(prob, settings.stakeTax, 0);
  return (
    <div className={cn("flex items-start gap-2 rounded-xl bg-accent-blue/[0.07] px-3 py-2.5 text-xs leading-snug text-fg-muted ring-1 ring-inset ring-accent-blue/15", className)}>
      <LuReceipt className="mt-0.5 size-4 shrink-0 text-accent-blue" />
      <span>
        U swojego legalnego bukmachera graj tylko przy kursie <b className="tnum text-fg">≥ {fmtPrice(min)}</b>
        {settings.stakeTax > 0 ? ` (uwzględnia podatek ${fmtPct(settings.stakeTax, 0)} od stawki)` : " (zakład bez podatku)"}. Niższy kurs = ujemne EV.
      </span>
    </div>
  );
}
