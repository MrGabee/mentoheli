import re, requests
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"hu"}
s=requests.get("https://www.fedakszinhaz.hu/",headers=H,timeout=25).text
links=list(dict.fromkeys(re.findall(r'href="(/[^"]*|https://www.fedakszinhaz.hu/[^"]*)"',s))); print(links)
for l in links:
    if re.search(r'jatekterv|aktualis',l,re.I):
        u=l if l.startswith("http") else "https://www.fedakszinhaz.hu"+l
        r=requests.get(u,headers=H,timeout=25); t=r.text; print("=====",u,r.status_code,len(t))
        txt=" ".join(re.sub(r"<[^>]+>"," ",re.sub(r"<(script|style)[^>]*>.*?</\1>"," ",t,flags=re.S)).split())
        i=txt.find("JÁTÉKTERV",200); print("TXT",txt[:5000])
        i=t.find("2026. OKT"); print("RAW",t[max(0,i-2500):i+1500])
