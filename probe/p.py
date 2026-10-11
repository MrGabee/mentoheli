import re, requests, json
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"hu"}
def g(u,**k):
    r=requests.get(u,headers=H,timeout=30,**k); print("=====",r.url[:140],"HTTP",r.status_code,len(r.text)); return r.text
s=g("https://mupa.hu/programok/naptar")
ls=list(dict.fromkeys(re.findall(r'href="(https://mupa.hu/program/[^"]+)"',s))); print(len(ls),ls[:5])
if ls:
    i=s.find(ls[3]); print("RAW",re.sub(r"\s+"," ",s[max(0,i-2500):i+2500]))
s=g("https://www.jegy.hu/venue_list/")
print(sorted(set(re.findall(r'https://www.jegy.hu/venues/([^/"]*soroks[^/"]*)/',s))))
print(sorted(set(re.findall(r'https://www.jegy.hu/venues/([^/"]*(?:csepel|erzsebet|miklos|szigetszent)[^/"]*)/',s))))
s=g("https://soroksar.hu/wp-json/tribe/events/v1/events",params={"per_page":5})
print(s[:1500])
s=g("https://soroksar.hu/esemenyek/")
print(" ".join(re.sub(r"<[^>]+>"," ",re.sub(r"<(script|style)[^>]*>.*?</\1>"," ",s,flags=re.S)).split())[:2000])
print(re.findall(r'href="(https://soroksar.hu/esemenyek/[^"]+)"',s)[:20])
