import re, requests, urllib.parse
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"hu"}
def get(u):
    r=requests.get(u,headers=H,timeout=25); print("=====",u,"HTTP",r.status_code,len(r.text)); return r.text
s=get("https://www.csepelimunkasotthon.hu/programok-aktualit%C3%A1sok/programnapt%C3%A1r")
for m in set(re.findall(r'(?:src|href|data-url)="([^"]*(?:calendar|ical|\.ics|embed)[^"]*)"',s)): print("CAL",m[:400])
for m in set(re.findall(r'calendar[^"\'\s<>]{0,300}',s)): print("CALTXT",m[:300])
txt=" ".join(re.sub(r"<[^>]+>"," ",s).split()); i=txt.find("Programnapt"); print("TXT",txt[i:i+3000])
s=get("https://www.csepelimunkasotthon.hu/programok-aktualit%C3%A1sok")
txt=" ".join(re.sub(r"<[^>]+>"," ",s).split()); print("TXT2",txt[:3000])
s=get("https://www.jegy.hu/venue/csepeli-munkasotthon")
ls=list(dict.fromkeys(re.findall(r'href="(https://www.jegy.hu/program/[^"]+)"',s))); print(len(ls),ls[:20])
if ls:
    i=s.find(ls[0]); print("RAW",s[max(0,i-2000):i+2500])
s=get("https://csepel.hu/esemenynaptar.html")
ls=re.findall(r'href="([^"]+)"',s); print([l for l in ls if 'esemeny' in l or 'program' in l][:40])
txt=" ".join(re.sub(r"<[^>]+>"," ",s).split()); print("TXT3",txt[:2500])
