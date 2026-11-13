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
hu = []
for e in L:
    la, lo = koord(e)
    try: la, lo = float(la), float(lo)
    except Exception: continue
    if 45.73 <= la <= 48.59 and 16.1 <= lo <= 22.9:
        hu.append((la, lo, e))
print('Magyarország-dobozban:', len(hu))
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
ujak = [(la, lo, e) for la, lo, e in hu if min(d((la, lo), k) for k in ismert) > 150]
print('nálunk 150 m-en belül nincs párja:', len(ujak))
print('új források:', collections.Counter(str(forras(e)) for _, _, e in ujak).most_common(30))
for la, lo, e in ujak[:80]:
    print('  ', round(la, 4), round(lo, 4), json.dumps(e, ensure_ascii=False)[:260])
