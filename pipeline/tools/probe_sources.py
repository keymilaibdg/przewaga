"""ETAP 5 probe #2: openfootball cup files and the SBR NBA odds table layout."""
import re, urllib.request, urllib.error

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 przewaga/0.5"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return -1, str(e)

for season in ("2021-22", "2022-23", "2023-24", "2024-25", "2025-26", "2026-27"):
    for comp in ("uefa.cl", "uefa.el", "uefa.conf", "uefa.cl.quali", "uefa.el.quali"):
        st, body = get(f"https://raw.githubusercontent.com/openfootball/football.json/master/{season}/{comp}.json")
        n = body.count('"team1"') if st == 200 else 0
        print(f"openfootball {season}/{comp}: HTTP {st} matches={n}")
        if st == 200 and comp == "uefa.el" and season == "2024-25":
            print(body[:900])

for s in ("2019-20", "2020-21", "2021-22", "2022-23"):
    st, body = get(f"https://www.sportsbookreviewsonline.com/scoresoddsarchives/nba-odds-{s}/")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S)
    print(f"SBR {s}: HTTP {st} len={len(body)} rows={len(rows)}")
    for r in rows[:5]:
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        print("   ", cells)
    if rows:
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", rows[-1], re.S)]
        print("   last", cells)
