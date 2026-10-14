import sys; sys.path.insert(0,"probe")
from datetime import date
import requests, allasok
pl = allasok.profession_feldolgoz(allasok._get(allasok.PROFESSION_URL)) or []
for a in pl[:3]:
    for ua in (allasok.HEADERS, {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36","Accept-Language":"hu-HU,hu;q=0.9","Accept":"text/html"}):
        r=requests.get(a["link"],headers=ua,timeout=25)
        print("PROF",a["link"],"->",r.status_code,r.url,[h.status_code for h in r.history],len(r.text))
a={}
t=allasok.heti_szoveg(date(2026,10,15),a)
print("=====POSZT=====");print(t);print("látott:",len(a["allas_latott"]))
