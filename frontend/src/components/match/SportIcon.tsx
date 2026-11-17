import { TbBallBasketball, TbBallFootball } from "react-icons/tb";
import type { Sport } from "../../types/domain";

export function SportIcon({ sport, className }: { sport: Sport; className?: string }) {
  return sport === "football" ? <TbBallFootball className={className} aria-label="Piłka nożna" /> : <TbBallBasketball className={className} aria-label="Koszykówka" />;
}

export const sportLabel: Record<Sport, string> = { football: "Piłka nożna", basketball: "Koszykówka" };
