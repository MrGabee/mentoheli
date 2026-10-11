import re, collections, requests
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"hu"}
for u in ["https://www.fedakszinhaz.hu/","https://www.fedakszinhaz.hu/wp-json/tribe/events/v1/events?per_page=5","https://www.fedakszinhaz.hu/musor","https://www.fedakszinhaz.hu/eloadasok","https://www.fedakszinhaz.hu/wp-json/wp/v2/types"]:
    print("=====",u)
    try: r=requests.get(u,headers=H,timeout=25)
    except Exception as e: print("ERR",str(e)[:150]); continue
    s=r.text; print("HTTP",r.status_code,r.url,len(s),r.headers.get("content-type"))
    if "json" in (r.headers.get("content-type") or ""): print(s[:2000]); continue
    t=re.search(r"<title>(.*?)</title>",s,re.S); print("TITLE",t and t.group(1).strip()[:120])
    links=list(dict.fromkeys(re.findall(r'href="([^"]+)"',s)))
    c=collections.Counter(re.sub(r'/[^/]+/?$','/*',l) for l in links); print(c.most_common(20))
    print([l for l in links if re.search(r'musor|eloadas|esemeny|program|jegy|naptar|event',l,re.I)][:40])
    for m in re.findall(r'<script[^>]*ld\+json[^>]*>(.*?)</script>',s,re.S)[:2]: print("LD",m.strip()[:1000])
    txt=" ".join(re.sub(r"<[^>]+>"," ",re.sub(r"<(script|style)[^>]*>.*?</\1>"," ",s,flags=re.S)).split()); print("TXT",txt[:2500])
