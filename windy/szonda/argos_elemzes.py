"""Ideiglenes: Argos Atlas kameralista – magyar kamerák összevetése a meglévőkkel."""
import json, re, collections
from math import radians, sin, cos, asin, sqrt
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(user_agent=UA).new_page()
    page.goto('https://www.argosatlas.com/map/', wait_until='networkidle', timeout=45000)
    page.wait_for_timeout(3000)
    res = page.evaluate("""async () => { const r = await fetch('/api/cameras_index.json');
        return {status: r.status, ct: r.headers.get('content-type'), text: await r.text()}; }""")
    b.close()
print('status', res['status'], res['ct'], len(res['text']), 'B')
t = res['text']
print('eleje:', t[:1500])
try:
    adat = json.loads(t)
except Exception as e:
    print('nem JSON:', e); raise SystemExit
def elemek(a):
    if isinstance(a, list): return a
    for k in ('cams', 'cameras', 'items', 'data', 'features', 'c'):
        if isinstance(a, dict) and k in a: return elemek(a[k])
    if isinstance(a, dict):
        print('kulcsok:', list(a)[:30])
        for v in a.values():
            if isinstance(v, list) and len(v) > 1000: return v
    return []
L = elemek(adat)
print('elemek száma:', len(L), 'minta:', json.dumps(L[:3], ensure_ascii=False)[:1500])
def koord(e):
    if isinstance(e, dict):
        if 'geometry' in e: c = e['geometry']['coordinates']; return c[1], c[0]
        la = e.get('lat') or e.get('latitude') or e.get('y'); lo = e.get('lon') or e.get('lng') or e.get('longitude') or e.get('x')
        return la, lo
    if isinstance(e, list):
        nums = [x for x in e if isinstance(x, (int, float))]
        for i in range(len(nums) - 1):
            a, b2 = nums[i], nums[i+1]
            if 40 < b2 < 60 and 10 < a < 30: return b2, a
            if 40 < a < 60 and 10 < b2 < 30: return a, b2
    return None, None
# Magyarország durva határpoligonja (lon, lat)
HU = [(16.11,46.87),(16.37,46.64),(16.6,46.47),(16.88,46.33),(17.25,46.11),(17.66,45.86),(18.2,45.78),(18.56,45.8),(18.83,45.91),(19.42,46.05),(20.05,46.14),(20.26,46.11),(20.72,46.17),(21.2,46.4),(21.29,46.62),(21.5,46.9),(21.67,47.0),(22.0,47.37),(22.18,47.6),(22.6,47.76),(22.9,48.0),(22.7,48.12),(22.2,48.42),(21.72,48.35),(21.45,48.58),(20.8,48.58),(20.47,48.47),(19.97,48.17),(19.5,48.2),(19.0,48.07),(18.82,47.83),(18.6,47.76),(17.86,47.75),(17.48,47.88),(17.17,48.02),(17.05,47.7),(16.68,47.6),(16.5,47.42),(16.45,47.15),(16.11,46.87)]
def bent(la, lo):
    x, y, c = lo, la, False
    for (x1, y1), (x2, y2) in zip(HU, HU[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c
hu = []
for e in L:
    la, lo = koord(e)
    try: la, lo = float(la), float(lo)
    except Exception: continue
    if 45.73 <= la <= 48.59 and 16.1 <= lo <= 22.9 and bent(la, lo):
        hu.append((la, lo, e))
print('Magyarországon belül:', len(hu))
print('kategóriák:', collections.Counter((e.get('category'), e.get('media_type')) for _, _, e in hu).most_common(20))
def forras(e):
    s = json.dumps(e, ensure_ascii=False)
    m = re.findall(r'https?://([^/"\\]+)', s)
    return m[0] if m else (e.get('src') or e.get('source') or e.get('p') or '?') if isinstance(e, dict) else '?'
print('források:', collections.Counter(str(forras(e)) for _, _, e in hu).most_common(30))
if hu and isinstance(hu[0][2], dict):
    print('mezők:', collections.Counter(k for _, _, e in hu for k in e).most_common(30))
    for k in ('src', 'source', 'p', 'prov', 'provider', 'f', 'o', 'org', 'fuente'):
        if k in hu[0][2]: print('forrásmező', k, collections.Counter(str(e.get(k)) for _, _, e in hu).most_common(30))
ny = json.load(open('windy/data/kamera_nyilvantartas.json'))['kamerak']
ismert = [(v['lat'], v['lon']) for v in ny.values() if v.get('lat') is not None]
def d(a, b2):
    la1, lo1, la2, lo2 = map(radians, (a[0], a[1], b2[0], b2[1]))
    h = sin((la2-la1)/2)**2 + cos(la1)*cos(la2)*sin((lo2-lo1)/2)**2
    return 2*6371000*asin(sqrt(h))
print('ismert kamera hellyel:', len(ismert))
ujak = [(la, lo, e) for la, lo, e in hu if min(d((la, lo), k) for k in ismert) > 150]
print('nálunk 150 m-en belül nincs párja:', len(ujak))
print('új kategóriák:', collections.Counter((e.get('category'), e.get('media_type')) for _, _, e in ujak).most_common(20))
import random; random.seed(1)
for la, lo, e in random.sample(ujak, min(60, len(ujak))):
    print('  ', round(la, 4), round(lo, 4), json.dumps(e, ensure_ascii=False)[:260])
