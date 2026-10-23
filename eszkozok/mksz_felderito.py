"""Ideiglenes felderítő: az mksz.hu JS-alkalmazásának API-végpontjait keresi
(a Csepel DSE kézilabda-meccseihez). Csak kiír, nem posztol."""
import re
import sys
import requests

H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/129.0 Safari/537.36"}
URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.mksz.hu/jegyzokonyv/32021361670"

r = requests.get(URL, headers=H, timeout=30)
print("HTML", r.status_code, len(r.text))
scriptek = re.findall(r'<script[^>]+src="([^"]+)"', r.text)
print("scriptek:", scriptek)
talalt = set()
for s in scriptek:
    u = s if s.startswith("http") else "https://www.mksz.hu" + ("" if s.startswith("/") else "/") + s
    try:
        js = requests.get(u, headers=H, timeout=30).text
    except Exception as ex:
        print("hiba", u, ex)
        continue
    print("JS", u, len(js))
    for m in re.findall(r'["\'`](https?://[^"\'`\s]*(?:api|data|backend|svc)[^"\'`\s]*)["\'`]', js, re.I):
        talalt.add(m)
    for m in re.findall(r'["\'`](/(?:api|v\d)[^"\'`\s]{2,120})["\'`]', js):
        talalt.add(m)
for t in sorted(talalt)[:300]:
    print("  ", t)
