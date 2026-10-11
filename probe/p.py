import requests, re, collections
u="https://calendar.google.com/calendar/ical/c904424062b8fed477daf383a5170f42b614517abf53b244308f5ed56618e0a5%40group.calendar.google.com/public/basic.ics"
r=requests.get(u,timeout=30); print("HTTP",r.status_code,len(r.text),r.headers.get("content-type"))
s=r.text.replace("\r\n ","").replace("\r\n","\n")
ev=s.split("BEGIN:VEVENT")[1:]
print("events",len(ev))
c=collections.Counter(re.search(r"^DTSTART[^:]*:(\d{6})",e,re.M).group(1) for e in ev if re.search(r"^DTSTART[^:]*:(\d{6})",e,re.M))
print(sorted(c.items())[-15:])
print("rrule",sum("RRULE" in e for e in ev))
fut=[e for e in ev if re.search(r"^DTSTART[^:]*:2026(1[0-2])",e,re.M) or "RRULE" in e]
for e in fut[:12]: print("-----"); print("\n".join(l[:300] for l in e.splitlines() if l.split(":")[0].split(";")[0] in ("DTSTART","DTEND","SUMMARY","LOCATION","DESCRIPTION","RRULE","STATUS")))
