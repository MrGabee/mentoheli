import re, collections
s=open('/tmp/o',encoding='utf-8',errors='replace').read()
links=re.findall(r'href="([^"]+)"', s)
c=collections.Counter(re.sub(r'/[^/]+$','/*',l) for l in links)
print(c.most_common(25))
ev=[l for l in links if re.search(r'/program/|/event/|/esemeny', l)]
print(len(ev), ev[:10])
for l in ev[:2]:
    i=s.find(l); print('---- RAW around', l); print(s[max(0,i-2500):i+1500])
for m in re.findall(r'<script[^>]*ld\+json[^>]*>(.*?)</script>', s, re.S)[:3]:
    print('LD', m.strip()[:2000])
