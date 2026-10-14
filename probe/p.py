import sys, re; sys.path.insert(0,"probe")
import requests, allasok
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36","Accept-Language":"hu-HU,hu;q=0.9"}
urls=["https://www.profession.hu/allas/kiszallito-csepel-lang-kft-budapest-3017634",
      "https://www.profession.hu/allas/szallito-ferro-kontroll-kft-budapest-2991620"]
for u in urls:
    r=requests.get(u,headers=allasok.HEADERS,timeout=25)
    sz=allasok._szoveg(re.sub(r"(?s)<(script|style).*?</\1>"," ",r.text)).lower()
    print("PROF",u,r.status_code,r.url==u)
    for h in allasok.HALOTT_SZOVEG:
        for m in re.finditer(re.escape(h),sz): print("  HIT",h,"::",sz[max(0,m.start()-80):m.end()+80])
    for k in ("lejárt","már nem","inaktív","nem elérhető","archiv"):
        for m in list(re.finditer(k,sz))[:2]: print("  KW",k,"::",sz[max(0,m.start()-60):m.end()+60])
    print("  og:title", re.findall(r'property="og:title" content="([^"]*)"',r.text)[:1])
u="https://kormanyhivatalok.hu/dokumentumtar?combine=XXI.&forras=300&field_dokumentum_cimke%5B%5D=99&kozzeteve=All"
r=requests.get(u,headers=H,timeout=40)
print("KH",r.status_code,r.url,len(r.text))
t=r.text
i=t.find("view-content"); print(t[i:i+6000] if i>=0 else t[:3000])
for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',t,re.S):
    x=re.sub("<[^>]+>","",m.group(2)).strip()
    if len(x)>20: print("A",m.group(1),"|",x[:150])
