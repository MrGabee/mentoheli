import re, collections, requests
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"hu"}
URLS=["https://www.mupa.hu/programok","https://www.mupa.hu/","https://www.mupa.hu/api/programs",
"https://soroksariszinhaz.hu/","https://www.soroksariszinhaz.hu/","https://www.jegy.hu/venue/soroksari-szinhaz",
"https://www.jegy.hu/search?q=soroks%C3%A1r","https://23.kerulet.ittlakunk.hu/civil/190530/tamogatokat-keres-soroksari-szinhaz",
"https://www.soroksar.hu/","https://concertbudapest.hu/helyszin/mupa/"]
for u in URLS:
    print("=====",u)
    try: r=requests.get(u,headers=H,timeout=25)
    except Exception as e: print("ERR",str(e)[:150]); continue
    s=r.text; print("HTTP",r.status_code,r.url,len(s),r.headers.get("content-type"))
    t=re.search(r"<title>(.*?)</title>",s,re.S); print("TITLE",t and t.group(1).strip()[:120])
    links=re.findall(r'href="([^"]+)"',s)
    c=collections.Counter(re.sub(r'/[^/]+/?$','/*',l) for l in links); print(c.most_common(12))
    ev=list(dict.fromkeys(l for l in links if re.search(r'program|esemeny|eloadas|szinhaz|venue|musor',l,re.I)))
    print(len(ev),ev[:30])
    for m in re.findall(r'<script[^>]*ld\+json[^>]*>(.*?)</script>',s,re.S)[:2]: print("LD",m.strip()[:800])
    if "ittlakunk" in u:
        txt=" ".join(re.sub(r"<[^>]+>"," ",re.sub(r"<(script|style)[^>]*>.*?</\1>"," ",s,flags=re.S)).split()); i=txt.find("Soroksári Színház"); print(txt[i:i+1500])
    if "mupa.hu/programok" in u and ev:
        i=s.find(ev[min(8,len(ev)-1)]); print("RAW",s[max(0,i-1500):i+1500])
