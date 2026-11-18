import { LuScale } from "react-icons/lu";
import { Badge } from "../ui/primitives";

/** Marks a market-mode tip: the edge comes from comparing bookmakers, not from the model. */
export function MarketBadge() {
  return (
    <Badge tone="blue" icon={<LuScale className="size-3" />}>
      Okazja rynkowa
    </Badge>
  );
}

export const MARKET_NOTE =
  "Okazja rynkowa: ten bukmacher płaci więcej, niż wynosi uczciwy kurs rynku (kurs bukmachera z najniższą marżą po jej odjęciu). To nie jest prognoza modelu — przewaga znika, gdy kurs się wyrówna. W Polsce graj tylko u legalnych bukmacherów.";
