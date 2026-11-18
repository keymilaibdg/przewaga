"""ETAP 5 probe: what do the free historical sources really contain? Prints a short report (no secrets)."""
import csv, io, json, os, sys, urllib.request, urllib.error

def get(url, headers=None, n=None):
    req = urllib.request.Request(url, headers={"User-Agent": "przewaga/0.5", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read() if n is None else r.read(n)
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300]
    except Exception as e:  # noqa: BLE001
        return -1, str(e).encode()

def text(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")

out = []
for path in ["mmz4281/1920/E0.csv", "mmz4281/2425/E0.csv", "mmz4281/2526/E0.csv", "mmz4281/2627/E0.csv", "mmz4281/2526/SP1.csv", "mmz4281/2627/D1.csv", "new/POL.csv", "mmz4281/2526/I1.csv", "mmz4281/2526/P1.csv", "mmz4281/2526/N1.csv", "new/AUT.csv"]:
    st, raw = get("https://www.football-data.co.uk/" + path)
    if st != 200:
        out.append(f"{path}: HTTP {st}")
        continue
    rows = list(csv.DictReader(io.StringIO(text(raw))))
    cols = list(rows[0].keys()) if rows else []
    filled = {c: sum(1 for r in rows if (r.get(c) or "").strip()) for c in cols if any(k in c for k in ("PS", "Max", "BFE", "Avg", "P>", "P<", "PC>", "B365H", "Season"))}
    out.append(f"{path}: {len(rows)} rows; cols={len(cols)}; filled={filled}")
    if rows:
        out.append(f"   first={ {k: rows[0][k] for k in cols[:8]} } last_date={rows[-1].get('Date')}")

ak = os.environ.get("APISPORTS_KEY")
if ak:
    for lid, season in [(2, 2024), (3, 2023), (848, 2022)]:
        st, raw = get(f"https://v3.football.api-sports.io/fixtures?league={lid}&season={season}", {"x-apisports-key": ak})
        try:
            b = json.loads(raw)
            resp = b.get("response", [])
            rounds = sorted({r["league"]["round"].split(" - ")[0] for r in resp})[:12]
            out.append(f"api-football league={lid} season={season}: HTTP {st} n={len(resp)} errors={b.get('errors')} rounds={rounds}")
            if resp:
                out.append(f"   sample={resp[0]['teams']['home']['name']} - {resp[0]['teams']['away']['name']} {resp[0]['score']}")
        except Exception as e:  # noqa: BLE001
            out.append(f"api-football {lid}/{season}: {st} {e}")
else:
    out.append("APISPORTS_KEY: missing")

bk = os.environ.get("BALLDONTLIE_KEY")
if bk:
    for s in (2018, 2022):
        st, raw = get(f"https://api.balldontlie.io/v1/games?seasons[]={s}&per_page=100", {"Authorization": bk})
        try:
            b = json.loads(raw)
            out.append(f"balldontlie season={s}: HTTP {st} n={len(b.get('data', []))} meta={b.get('meta')}")
        except Exception as e:  # noqa: BLE001
            out.append(f"balldontlie {s}: {st} {raw[:200]!r}")

for url in [
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba/nba%20odds%202021-22.xlsx",
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba-odds-2021-22/",
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba-odds-2022-23/",
    "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba-odds-2023-24/",
    "https://raw.githubusercontent.com/openfootball/champions-league/master/2024-25/cl.txt",
    "https://raw.githubusercontent.com/openfootball/football.json/master/2024-25/uefa.cl.json",
]:
    st, raw = get(url, n=600)
    out.append(f"{url}: HTTP {st} head={text(raw)[:250]!r}")

print("\n".join(out))
