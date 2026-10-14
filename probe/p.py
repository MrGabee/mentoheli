import requests, re, html
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
T=[("Óvodatitkár","https://kozszolgallas.ksz.gov.hu/JobAd/Info/170088"),
("Esetmenedzser","https://kozszolgallas.ksz.gov.hu/JobAd/Info/166729"),
("Karbantartó","https://kozszolgallas.ksz.gov.hu/JobAd/Info/166734"),
("Szállító","https://www.profession.hu/allas/szallito-ferro-kontroll-kft-budapest-2991620"),
("Rakodó","https://www.profession.hu/allas/rakodo-csomagolo-munkas-metalfin-atta-cso-kft-budapest-2983487"),
("Frissáru","https://www.profession.hu/allas/frissaru-pultos-teljes-munkaido-tesco-global-zrt-budapest-3010057"),
("Ágazatvezető","https://drive.google.com/file/d/1OFU2ZYXeOeWKN8eKp-EWV0YxaSyObU6R/view?usp=drive_link"),
("Raktáros","https://drive.google.com/file/d/19KD7XIXi0rx749PnimoKseZlFS_lDzJF/view?usp=sharing"),
("Kőműves","https://varosgazda.eu/2026/09/17/allaslehetosegek/")]
for cim,u in T:
    try:
        r=requests.get(u,headers=H,timeout=20,allow_redirects=True)
        t=r.text; ti=re.search(r"<title[^>]*>(.*?)</title>",t,re.S)
        body=html.unescape(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",re.sub(r"(?s)<(script|style).*?</\1>","",t))))
        print("==",cim,r.status_code,r.url[:100],"|",(ti.group(1).strip()[:100] if ti else ""),"| cim benne:",cim.lower() in body.lower())
        for kw in ["nem található","lejárt","megszűnt","nem elérhető","not found","nem létezik","inaktív","lezárult","Hiba"]:
            if kw.lower() in body.lower(): print("   kw:",kw, "...", body[max(0,body.lower().find(kw.lower())-80):body.lower().find(kw.lower())+80])
        print("   body:",body[:300])
    except Exception as e: print("==",cim,"HIBA",e)
