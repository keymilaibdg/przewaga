// DEMO catalogue: league and team names for demonstration only.
// Ratings below are invented and DO NOT describe the real strength of any team.
import type { Bookmaker, League, Sport } from "../types/domain";

export interface DemoTeam {
  id: string;
  name: string;
  shortName: string;
  colors: [string, string];
  /** Invented rating: football = attack/defence multipliers, basketball = net rating. */
  att: number;
  def: number;
}

export interface DemoLeague extends League {
  teams: DemoTeam[];
  /** Football: average goals per team per match. Basketball: average points per team. */
  baseline: number;
  homeAdv: number;
  weight: number;
}

const t = (id: string, name: string, shortName: string, c1: string, c2: string, att: number, def: number): DemoTeam => ({
  id,
  name,
  shortName,
  colors: [c1, c2],
  att,
  def,
});

export const BOOKMAKERS: Bookmaker[] = [
  { id: "sts", name: "STS", integrationVerified: false },
  { id: "fortuna", name: "Fortuna", integrationVerified: false },
  { id: "superbet", name: "Superbet", integrationVerified: false },
  { id: "betclic", name: "Betclic", integrationVerified: false },
  { id: "pinnacle", name: "Pinnacle", integrationVerified: false },
  { id: "bet365", name: "bet365", integrationVerified: false },
];

export const bookmakerName = (id: string) => BOOKMAKERS.find((b) => b.id === id)?.name ?? id;

const football = (id: string, name: string, country: string, baseline: number, homeAdv: number, weight: number, teams: DemoTeam[]): DemoLeague => ({
  id,
  name,
  country,
  sport: "football" as Sport,
  teams,
  baseline,
  homeAdv,
  weight,
});

const basketball = (id: string, name: string, country: string, baseline: number, homeAdv: number, weight: number, teams: DemoTeam[]): DemoLeague => ({
  id,
  name,
  country,
  sport: "basketball" as Sport,
  teams,
  baseline,
  homeAdv,
  weight,
});

export const LEAGUES: DemoLeague[] = [
  football("epl", "Premier League", "Anglia", 1.42, 1.12, 3, [
    t("ars", "Arsenal", "ARS", "#DB0007", "#FFFFFF", 1.32, 0.72),
    t("che", "Chelsea", "CHE", "#034694", "#FFFFFF", 1.18, 0.9),
    t("liv", "Liverpool", "LIV", "#C8102E", "#F6EB61", 1.38, 0.82),
    t("mci", "Manchester City", "MCI", "#6CABDD", "#1C2C5B", 1.34, 0.8),
    t("mun", "Manchester United", "MUN", "#DA291C", "#FBE122", 1.0, 1.05),
    t("tot", "Tottenham", "TOT", "#132257", "#FFFFFF", 1.12, 1.08),
    t("new", "Newcastle", "NEW", "#241F20", "#FFFFFF", 1.1, 0.92),
    t("avl", "Aston Villa", "AVL", "#670E36", "#95BFE5", 1.08, 0.98),
  ]),
  football("laliga", "La Liga", "Hiszpania", 1.3, 1.15, 2, [
    t("rma", "Real Madryt", "RMA", "#FEBE10", "#00529F", 1.36, 0.78),
    t("fcb", "FC Barcelona", "FCB", "#A50044", "#004D98", 1.4, 0.86),
    t("atm", "Atlético Madryt", "ATM", "#CB3524", "#262E61", 1.08, 0.74),
    t("ath", "Athletic Bilbao", "ATH", "#EE2523", "#FFFFFF", 1.0, 0.9),
    t("rso", "Real Sociedad", "RSO", "#0067B1", "#FFFFFF", 0.95, 0.96),
    t("vil", "Villarreal", "VIL", "#FFE667", "#005187", 1.08, 1.02),
  ]),
  football("seriea", "Serie A", "Włochy", 1.3, 1.1, 2, [
    t("int", "Inter", "INT", "#0068A8", "#000000", 1.3, 0.76),
    t("mil", "AC Milan", "MIL", "#FB090B", "#000000", 1.12, 0.92),
    t("juv", "Juventus", "JUV", "#FFFFFF", "#000000", 1.04, 0.8),
    t("nap", "Napoli", "NAP", "#12A0D7", "#FFFFFF", 1.16, 0.84),
    t("rom", "AS Roma", "ROM", "#8E1F2F", "#F0BC42", 1.0, 0.9),
    t("ata", "Atalanta", "ATA", "#1E71B8", "#000000", 1.2, 0.96),
  ]),
  football("bundesliga", "Bundesliga", "Niemcy", 1.58, 1.1, 2, [
    t("fcb-de", "Bayern Monachium", "BAY", "#DC052D", "#FFFFFF", 1.48, 0.8),
    t("bvb", "Borussia Dortmund", "BVB", "#FDE100", "#000000", 1.2, 1.0),
    t("b04", "Bayer Leverkusen", "B04", "#E32221", "#000000", 1.22, 0.88),
    t("rbl", "RB Lipsk", "RBL", "#DD0741", "#FFFFFF", 1.12, 0.96),
    t("vfb", "VfB Stuttgart", "VFB", "#E32219", "#FFFFFF", 1.1, 1.04),
    t("sge", "Eintracht Frankfurt", "SGE", "#E1000F", "#000000", 1.08, 1.06),
  ]),
  football("ligue1", "Ligue 1", "Francja", 1.38, 1.12, 1, [
    t("psg", "Paris Saint-Germain", "PSG", "#004170", "#DA291C", 1.42, 0.78),
    t("om", "Olympique Marsylia", "OM", "#2FAEE0", "#FFFFFF", 1.12, 0.96),
    t("asm", "AS Monaco", "ASM", "#E7192F", "#FFFFFF", 1.12, 1.0),
    t("losc", "Lille", "LOSC", "#E01E13", "#24215E", 1.02, 0.9),
    t("ol", "Olympique Lyon", "OL", "#1B3F94", "#E30613", 1.06, 1.04),
    t("ogcn", "OGC Nice", "NICE", "#C8102E", "#000000", 0.96, 0.96),
  ]),
  football("ucl", "Liga Mistrzów", "Europa", 1.45, 1.1, 2, [
    t("rma", "Real Madryt", "RMA", "#FEBE10", "#00529F", 1.36, 0.78),
    t("mci", "Manchester City", "MCI", "#6CABDD", "#1C2C5B", 1.34, 0.8),
    t("fcb-de", "Bayern Monachium", "BAY", "#DC052D", "#FFFFFF", 1.48, 0.8),
    t("int", "Inter", "INT", "#0068A8", "#000000", 1.3, 0.76),
    t("psg", "Paris Saint-Germain", "PSG", "#004170", "#DA291C", 1.42, 0.78),
    t("ars", "Arsenal", "ARS", "#DB0007", "#FFFFFF", 1.32, 0.72),
  ]),
  football("ekstraklasa", "Ekstraklasa", "Polska", 1.36, 1.14, 2, [
    t("leg", "Legia Warszawa", "LEG", "#00843D", "#FFFFFF", 1.16, 0.92),
    t("lech", "Lech Poznań", "LPO", "#1F4E9B", "#FFFFFF", 1.2, 0.9),
    t("rak", "Raków Częstochowa", "RAK", "#D7151E", "#1E3D8F", 1.06, 0.82),
    t("jag", "Jagiellonia Białystok", "JAG", "#E2001A", "#FFD200", 1.14, 0.98),
    t("pog", "Pogoń Szczecin", "POG", "#00205B", "#B5121B", 1.08, 1.02),
    t("gor", "Górnik Zabrze", "GÓR", "#0F4FA8", "#E30613", 0.98, 1.0),
  ]),
  basketball("nba", "NBA", "USA", 114, 2.4, 3, [
    t("bos", "Boston Celtics", "BOS", "#007A33", "#BA9653", 8.5, 0),
    t("lal", "Los Angeles Lakers", "LAL", "#552583", "#FDB927", 2.0, 0),
    t("den", "Denver Nuggets", "DEN", "#0E2240", "#FEC524", 4.5, 0),
    t("mil", "Milwaukee Bucks", "MIL", "#00471B", "#EEE1C6", 1.5, 0),
    t("gsw", "Golden State Warriors", "GSW", "#1D428A", "#FFC72C", 1.0, 0),
    t("nyk", "New York Knicks", "NYK", "#006BB6", "#F58426", 4.0, 0),
    t("okc", "Oklahoma City Thunder", "OKC", "#007AC1", "#EF3B24", 9.0, 0),
    t("phi", "Philadelphia 76ers", "PHI", "#006BB6", "#ED174C", -1.0, 0),
    t("mia", "Miami Heat", "MIA", "#98002E", "#F9A01B", 0.5, 0),
    t("dal", "Dallas Mavericks", "DAL", "#00538C", "#B8C4CA", 1.5, 0),
  ]),
  basketball("euroleague", "Euroliga", "Europa", 81, 3.2, 2, [
    t("rmb", "Real Madryt", "RMB", "#FEBE10", "#00529F", 5.0, 0),
    t("pao", "Panathinaikos", "PAO", "#007A33", "#FFFFFF", 5.5, 0),
    t("oly", "Olympiacos", "OLY", "#E30613", "#FFFFFF", 5.0, 0),
    t("fen", "Fenerbahçe", "FEN", "#163962", "#FFED00", 4.5, 0),
    t("bar", "FC Barcelona", "FCB", "#A50044", "#004D98", 2.5, 0),
    t("asm-b", "AS Monaco", "ASM", "#E7192F", "#FFFFFF", 3.5, 0),
    t("par", "Partizan", "PAR", "#000000", "#FFFFFF", 0.5, 0),
    t("zal", "Žalgiris Kowno", "ZAL", "#006233", "#FFFFFF", 1.0, 0),
  ]),
  basketball("eurocup", "EuroCup", "Europa", 82, 3.0, 1, [
    t("hap", "Hapoel Jerozolima", "HJE", "#E30613", "#000000", 3.0, 0),
    t("bes", "Beşiktaş", "BJK", "#000000", "#FFFFFF", 1.5, 0),
    t("tre", "Umana Reyer Wenecja", "REY", "#8A1538", "#FFD200", 0.5, 0),
    t("cdn", "Cedevita Olimpija", "CEO", "#00843D", "#FFD200", 0.0, 0),
  ]),
  basketball("plk", "ORLEN Basket Liga", "Polska", 82, 3.4, 2, [
    t("tre-s", "Trefl Sopot", "TRE", "#FFD200", "#003F87", 3.0, 0),
    t("sla", "Śląsk Wrocław", "ŚLĄ", "#00843D", "#FFFFFF", 2.0, 0),
    t("kin", "King Szczecin", "KIN", "#000000", "#E2B53E", 2.5, 0),
    t("anw", "Anwil Włocławek", "ANW", "#003DA5", "#FFFFFF", 1.0, 0),
    t("leg-b", "Legia Warszawa", "LEG", "#00843D", "#FFFFFF", 1.5, 0),
    t("sto", "Stal Ostrów Wlkp.", "STO", "#1D428A", "#E30613", 0.5, 0),
  ]),
];
