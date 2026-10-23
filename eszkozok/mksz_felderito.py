"""Ideiglenes felderítő: az mksz.hu publikus API-ját vizsgálja
(a Csepel DSE kézilabda-meccseihez). Csak kiír, nem posztol."""
import re
import os
import sys
import json
import requests

H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/129.0 Safari/537.36",
     "Accept": "application/json", "Origin": "https://www.mksz.hu", "Referer": "https://www.mksz.hu/"}
API = "https://public.mksz.hu/public/api/v1/"

html = requests.get("https://www.mksz.hu/", headers=H, timeout=30).text
app = next((s for s in re.findall(r'src="(/js/app\.[^"]+)"', html)), None)
js = requests.get("https://www.mksz.hu" + app, headers=H, timeout=30).text if app else ""
print("app.js", app, len(js))
utak = set()
for m in re.finditer(r'["`]((?:[a-z0-9\-]+/)*(?:[a-z0-9\-]+|\$\{[^}`]{1,40}\})(?:/(?:[a-z0-9\-]+|\$\{[^}`]{1,40}\}))+/?(?:\?[^"`]{0,80})?)["`]', js):
    u = m.group(1)
    if not u.startswith(("http", "img", "css", "js/", "fonts")) and len(u) < 140:
        utak.add(u)
for u in sorted(utak):
    print("  UT", u)

def get(ut, **p):
    try:
        r = requests.get(API + ut, headers=H, params=p, timeout=30)
        szoveg = r.text
        print(f"\n### GET {ut} {p} -> {r.status_code} {len(szoveg)}")
        try:
            adat = r.json()
        except ValueError:
            adat = None
        if isinstance(adat, dict) and isinstance(adat.get("content"), list):
            adat = adat["content"]
        if isinstance(adat, list) and adat and "merkozesId" in adat[0]:
            print(f"{len(adat)} meccs; mezők: {sorted(adat[0].keys())}")
            for m in adat[:60]:
                print(f"  {m.get('merkozesDatum')} | {m.get('evadEv')} | {m.get('foversenyRovidNev')} / {m.get('alversenyNev')} | "
                      f"{m.get('hazaiCsapatNev')} ({m.get('hazaiSportszervezetId')}) – {m.get('vendegCsapatNev')} ({m.get('vendegSportszervezetId')}) "
                      f"| {m.get('hazaiCsapatGol')}:{m.get('vendegCsapatGol')} | {m.get('letesitmenyNev')} | {m.get('merkozesStatusz')}")
        else:
            print(szoveg[:1500])
    except Exception as ex:
        print("hiba", ut, ex)

for ut in (sys.argv[1:] or os.environ.get("UTAK", "").split()):
    get(ut)
