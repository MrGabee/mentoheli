import re
s=open('/tmp/o',encoding='utf-8',errors='replace').read()
print('feeds:', re.findall(r'<link[^>]*(?:rss|atom)[^>]*>', s, re.I)[:5])
for m in re.findall(r'<script[^>]*ld\+json[^>]*>(.*?)</script>', s, re.S)[:6]:
    print(m.strip()[:1500]); print('#####')
i=s.find('Kapcsolódó információk')
print('---- context at', i)
print(re.sub(r'\s+',' ',s[i:i+9000]))
