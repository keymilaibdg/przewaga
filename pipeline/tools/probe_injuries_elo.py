"""Probe: latest official NBA injury report PDF (text layout) and ClubElo CSV endpoints."""
import io, sys, urllib.request, urllib.error
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
found = None
for i in range(40):
    stamp = t.strftime("%Y-%m-%d_%I_%M%p")
    url = f"https://ak-static.cms.nba.com/referee/injury/Injury-Report_{stamp}.pdf"
    st, body = get(url)
    print(stamp, st, len(body))
    if st == 200 and body[:4] == b"%PDF":
        found = body
        break
    t -= timedelta(minutes=15)
if found:
    import pypdf
    r = pypdf.PdfReader(io.BytesIO(found))
    print("pages", len(r.pages))
    for mode in ("layout", "plain"):
        txt = r.pages[0].extract_text(extraction_mode=mode)
        print(f"===== page 1 mode={mode}")
        for line in txt.splitlines()[:70]:
            print("|" + line)
for url in ("http://api.clubelo.com/" + datetime.now(timezone.utc).strftime("%Y-%m-%d"), "http://api.clubelo.com/Fixtures"):
    st, body = get(url)
    print("=====", url, st, len(body))
    lines = body.decode("utf-8", "replace").splitlines()
    for line in lines[:8]:
        print("|" + line[:400])
    print("... total lines", len(lines))
