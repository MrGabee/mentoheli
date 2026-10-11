import re
s=open('/tmp/o',encoding='utf-8',errors='replace').read()
print('feeds:', re.findall(r'<link[^>]*(?:rss|atom)[^>]*>', s, re.I)[:5])
for m in re.findall(r'<script[^>]*ld\+json[^>]*>(.*?)</script>', s, re.S)[:4]:
    print(m.strip()[:2500]); print('#####')
# első dátumminta környezete nyers HTML-ben
for m in list(re.finditer(r'20\d\d\.\d\d\.\d\d\.', s))[:3]:
    print('---- raw at', m.start())
    print(s[max(0,m.start()-1500):m.start()+800])
