// Bookmaker display names. Live data provides key -> title from the odds provider (meta.json).
const names = new Map<string, string>([
  ["sts", "STS"],
  ["fortuna", "Fortuna"],
  ["superbet", "Superbet"],
  ["betclic", "Betclic"],
  ["betclic_fr", "Betclic"],
  ["pinnacle", "Pinnacle"],
  ["bet365", "bet365"],
]);

export function registerBookmakers(map: Record<string, string>) {
  for (const [k, v] of Object.entries(map)) names.set(k, v);
}

export const bookmakerName = (id: string) => names.get(id) ?? id;

export function bookmakerShort(id: string): string {
  return bookmakerName(id).replace(/[^A-Za-z0-9]/g, "").slice(0, 3).toUpperCase();
}
