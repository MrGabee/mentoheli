import requests, re
ID="c904424062b8fed477daf383a5170f42b614517abf53b244308f5ed56618e0a5@group.calendar.google.com"
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"hu"}
for u,p in [
 ("https://calendar.google.com/calendar/ical/%s/public/basic.ics"%ID,None),
 ("https://www.google.com/calendar/ical/%s/public/basic.ics"%ID,None),
 ("https://calendar.google.com/calendar/htmlembed",{"src":ID,"mode":"AGENDA","ctz":"Europe/Budapest"}),
 ("https://calendar.google.com/calendar/embed",{"src":ID,"mode":"AGENDA","ctz":"Europe/Budapest"}),
]:
    r=requests.get(u,params=p,headers=H,timeout=30); s=r.text
    print("=====",r.url[:150],"HTTP",r.status_code,len(s))
    if "BEGIN:VEVENT" in s: print(s[:3000]); continue
    txt=" ".join(re.sub(r"<[^>]+>"," ",re.sub(r"<(script|style)[^>]*>.*?</\1>"," ",s,flags=re.S)).split())
    print("TXT",txt[:2500])
    i=s.find("event"); print("RAW",s[i:i+1500] if "htmlembed" in u else "")
