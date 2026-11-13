"""Ideiglenes: Vigilyst, All Traffic Cams, LiveTraffic, ASFINAG felderítése."""
import json, re, collections
from playwright.sync_api import sync_playwright
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
START = {
    'vigilyst': ['https://vigilyst.com/verkehrskameras', 'https://vigilyst.com/'],
    'alltrafficcams': ['https://alltrafficcams.com/live/webcams/hungary/border-crossings/', 'https://www.alltrafficcams.com/'],
    'livetraffic': ['https://www.livetraffic.eu/', 'https://www.livetraffic.eu/hungary'],
    'asfinag': ['https://www.asfinag.at/verkehr-sicherheit/webcams/', 'https://www.asfinag.at/'],
}
HUMINTA = re.compile(r'hungar|ungarn|magyar|/hu/|budapest|hegyeshalom|nickelsdorf|sopron|klingenbach|heiligenkreuz|r[äa]bafüzes', re.I)
ki = {}

def vizsgal(page, url):
    halo = []
    def on(r):
        ct = r.headers.get('content-type', '')
        if 'json' in ct or 'xml' in ct or '/api' in r.url:
            try:
                t = r.text()
            except Exception:
                t = ''
            halo.append({'url': r.url[:300], 'status': r.status, 'ct': ct[:40], 'meret': len(t),
                         'hu': len(re.findall(r'Hungar|Ungarn|Magyar|Budapest', t)), 'eleje': t[:400]})
    page.on('response', on)
    try:
        resp = page.goto(url, wait_until='domcontentloaded', timeout=45000)
        page.wait_for_timeout(8000)
        for _ in range(4):
            page.mouse.wheel(0, 3000); page.wait_for_timeout(600)
        st = resp.status if resp else None
    except Exception as e:
        page.remove_listener('response', on)
        return {'hiba': str(e)[:300]}
    page.remove_listener('response', on)
    linkek = sorted(set(page.eval_on_selector_all('a[href]', 'e => e.map(x => x.href)')))
    kepek = page.eval_on_selector_all('img', 'e => e.map(x => x.currentSrc || x.src)')
    return {
        'status': st, 'cim': page.title(),
        'szoveg': re.sub(r'\s+', ' ', page.inner_text('body'))[:2500],
        'hu_linkek': [l for l in linkek if HUMINTA.search(l)][:80],
        'linkek_db': len(linkek),
        'kephostok': collections.Counter(re.sub(r'https?://([^/]+).*', r'\1', k) for k in kepek if k).most_common(12),
        'kep_minta': [k for k in kepek if k][:25],
        'iframe': page.eval_on_selector_all('iframe', 'e => e.map(x => x.src)')[:20],
        'halo': halo[:60],
    }

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(user_agent=UA, locale='hu-HU', viewport={'width': 1400, 'height': 1000})
    page = ctx.new_page()
    for nev, urlek in START.items():
        ki[nev] = {}
        for u in urlek:
            ki[nev][u] = vizsgal(page, u)
        hu = []
        for v in ki[nev].values():
            hu += v.get('hu_linkek', []) if isinstance(v, dict) else []
        for u in list(dict.fromkeys(hu))[:4]:
            if u not in ki[nev]:
                ki[nev][u] = vizsgal(page, u)
        json.dump(ki, open('windy/szonda2/negy_oldal.json', 'w'), ensure_ascii=False, indent=1)
    b.close()
print('kész')
