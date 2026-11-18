"""Probe 2: NBA injury report -> words with positions (test fixture); ClubElo endpoints with retries."""
import io, json, time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 przewaga/0.6"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:  # noqa: BLE001
        return -1, str(e).encode()

et = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))
t = et.replace(minute=et.minute - et.minute % 15, second=0, microsecond=0)
for i in range(40):
    stamp = t.strftime("%Y-%m-%d_%I_%M%p")
    st, body = get(f"https://ak-static.cms.nba.com/referee/injury/Injury-Report_{stamp}.pdf")
    if st == 200 and body[:4] == b"%PDF":
        print("found", stamp)
        import pdfplumber
        pages = []
        with pdfplumber.open(io.BytesIO(body)) as pdf:
            for p in pdf.pages[:3]:
                pages.append({"width": p.width, "words": [{"text": w["text"], "x0": round(w["x0"], 1), "x1": round(w["x1"], 1), "top": round(w["top"], 1)} for w in p.extract_words(keep_blank_chars=False)]})
        import os; os.makedirs("pipeline/tests/data", exist_ok=True)
        json.dump({"stamp": stamp, "pages": pages}, open("pipeline/tests/data/nba_injury_words.json", "w"), indent=0)
        break
    t -= timedelta(minutes=15)

d0 = datetime.now(timezone.utc)
for url in [f"http://api.clubelo.com/{(d0 - timedelta(days=k)).strftime('%Y-%m-%d')}" for k in (0, 1, 3)] + ["http://api.clubelo.com/ManCity", "https://api.clubelo.com/ManCity", "http://clubelo.com/API"]:
    for attempt in range(3):
        st, body = get(url)
        if st == 200:
            break
        time.sleep(5)
    lines = body.decode("utf-8", "replace").splitlines()
    print("=====", url, st, len(body), "lines", len(lines))
    for line in lines[:5]:
        print("|" + line[:300])
