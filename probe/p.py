import requests, re, json, time
H={"User-Agent":"Mozilla/5.0"}
def get(u, **k):
    try:
        r=requests.get(u,headers=H,timeout=30,**k); print("=====",u[:140],r.status_code,r.headers.get("content-type"),len(r.text)); return r
    except Exception as e: print("=====",u[:140],"ERR",e)
r=get("https://air-quality-api.open-meteo.com/v1/air-quality?latitude=47.42&longitude=19.07&hourly=pm10,pm2_5,european_aqi,birch_pollen,grass_pollen,ragweed_pollen&timezone=Europe/Budapest&forecast_days=1")
if r: d=r.json(); print({k:(v[6:22:4]) for k,v in d.get("hourly",{}).items()})
now=int(time.time())
r=get(f"https://futar.bkk.hu/api/query/v1/ws/otp/api/where/alert-search.json?key=apaiary-test&version=3&appVersion=apiary-1.0&includeReferences=routes&query=Csepel")
if r:
    try:
        d=r.json(); e=d["data"]
        print(json.dumps(e.get("list",e.get("entry"))  ,ensure_ascii=False)[:2500])
        print("refs routes:", list((e.get("references",{}).get("routes") or {}).keys())[:30])
    except Exception as x: print(r.text[:800])
for u in ["https://www.hydroinfo.hu/","https://www.vizugy.hu/","https://mohubudapest.hu/lomtalanitas","https://mohubudapest.hu/","https://www.patikakereso.hu/","https://bkk.hu/apps/bkkinfo/json.php"]:
    r=get(u)
    if r is not None:
        t=r.text
        links=set(re.findall(r'href="([^"]+)"',t))
        hits=[l for l in links if re.search(r"(?i)budapest|vizall|lomtalan|ugyelet|json|rss|xml|csepel|XXI",l)]
        print(sorted(hits)[:40])
        if "json" in u: print(t[:1500])
