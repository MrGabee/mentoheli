import re, collections, requests, json
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"hu"}
URLS=[
 "https://concertbudapest.hu/helyszin/barba-negra/",
 "https://concertbudapest.hu/?s=munk%C3%A1sotthon",
 "https://concertbudapest.hu/helyszin/csepeli-munkasotthon/",
 "https://csepelimunkasotthon.hu/",
 "https://www.csepelimunkasotthon.hu/",
 "https://munkasotthon.csepel.hu/",
 "https://www.csepel.hu/",
 "https://csepel.hu/programok/",
 "https://port.hu/helyszin/csepeli-munkasotthon",
 "https://www.jegy.hu/venue/csepeli-munkasotthon",
 "https://www.programturizmus.hu/partner-csepeli-munkasotthon-muvelodesi-haz.html",
 "https://hu.wikipedia.org/w/api.php?action=parse&page=Okt%C3%B3ber_11.&prop=wikitext&format=json&formatversion=2",
 "https://hu.wikipedia.org/w/api.php?action=query&list=categorymembers&cmtitle=Kateg%C3%B3ria:Budapest_XXI._ker%C3%BClete&cmlimit=50&format=json",
 "https://api.open-meteo.com/v1/forecast?latitude=47.43&longitude=19.07&daily=temperature_2m_max,temperature_2m_min,weathercode&timezone=Europe/Budapest&forecast_days=2",
]
for u in URLS:
    print("=====",u)
    try:
        r=requests.get(u,headers=H,timeout=25,allow_redirects=True)
    except Exception as e:
        print("ERR",e); continue
    s=r.text
    print("HTTP",r.status_code,r.url,len(s),r.headers.get("content-type"))
    t=re.search(r"<title>(.*?)</title>",s,re.S); print("TITLE",t and t.group(1).strip()[:120])
    if "json" in (r.headers.get("content-type") or ""):
        print(s[:1500]); continue
    print("munkás:",len(re.findall("unk[aá]sotthon",s)))
    links=re.findall(r'href="([^"]+)"',s)
    c=collections.Counter(re.sub(r'/[^/]+/?$','/*',l) for l in links)
    print(c.most_common(15))
    ev=[l for l in links if re.search(r'esemeny|program|koncert|event|munkasotthon',l)]
    print(len(ev),list(dict.fromkeys(ev))[:25])
    for m in re.findall(r'<script[^>]*ld\+json[^>]*>(.*?)</script>',s,re.S)[:2]:
        print("LD",m.strip()[:1500])
    if "concertbudapest.hu/helyszin/barba" in u and ev:
        i=s.find(ev[5] if len(ev)>5 else ev[0]); print("RAW",s[max(0,i-1500):i+1500])
