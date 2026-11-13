"""Ideiglenes: Argos JS – hogyan épül a kamera képének címe."""
import json, re
from playwright.sync_api import sync_playwright
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
ki = {}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(user_agent=UA).new_page()
    jsek = {}
    page.on('response', lambda r: jsek.__setitem__(r.url, r) if r.url.endswith('.js') and 'argosatlas' in r.url else None)
    page.goto('https://www.argosatlas.com/map/', wait_until='networkidle', timeout=45000)
    page.wait_for_timeout(3000)
    for u, r in jsek.items():
        try: t = r.text()
        except Exception: continue
        for minta in [r'/api/cam/', r'/api/crowd/cam/', r'cameras_index', r'media_type', r'snapshot', r'/img/', r'/proxy', r'thumb', r'/api/asset/']:
            for m in list(re.finditer(re.escape(minta) if not minta.startswith('/') else minta, t))[:6]:
                ki.setdefault(u.rsplit('/', 1)[-1] + ' ' + minta, []).append(t[max(0, m.start()-500):m.end()+500])
    # próbáljunk egy ismert magyar azonosítót többféleképp
    proba = {}
    for url in ['/api/cam/0bd742cf3788cf0cb2', '/api/crowd/cam/0bd742cf3788cf0cb2', '/api/cam/ab046e8c8b3d73495d']:
        proba[url] = page.evaluate("async u => { const r = await fetch(u); return [r.status, (await r.text()).slice(0, 3000)]; }", url)
    ki['PROBA'] = proba
    b.close()
json.dump(ki, open('windy/szonda/argos_js.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(proba, ensure_ascii=False)[:3000])
