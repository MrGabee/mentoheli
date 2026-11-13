"""Ideiglenes: onlinecamera.net felderítése."""
import json, re
from playwright.sync_api import sync_playwright
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
ki = {}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(user_agent=UA, locale='hu-HU').new_page()
    halo = []
    page.on('response', lambda r: halo.append([r.status, r.headers.get('content-type', ''), r.url]))
    page.goto('https://onlinecamera.net/elo-webkamerak', wait_until='networkidle', timeout=60000)
    page.wait_for_timeout(4000)
    for _ in range(10):
        page.mouse.wheel(0, 4000); page.wait_for_timeout(700)
    ki['cim'] = page.title()
    ki['szoveg'] = re.sub(r'\s+', ' ', page.inner_text('body'))[:6000]
    ki['linkek'] = sorted(set(page.eval_on_selector_all('a[href]', 'e => e.map(x => x.href)')))
    ki['kepek'] = page.eval_on_selector_all('img', 'e => e.map(x => x.currentSrc || x.src)')[:300]
    ki['halo'] = [h for h in halo if not h[1].startswith(('font', 'text/css'))][:400]
    kamera = [l for l in ki['linkek'] if 'onlinecamera.net' in l and l.count('/') >= 4][:6]
    ki['oldalak'] = {}
    for u in kamera:
        halo.clear()
        try:
            page.goto(u, wait_until='networkidle', timeout=45000); page.wait_for_timeout(3000)
        except Exception as e:
            ki['oldalak'][u] = str(e); continue
        ki['oldalak'][u] = {
            'cim': page.title(),
            'iframe': page.eval_on_selector_all('iframe', 'e => e.map(x => x.src)'),
            'video': page.eval_on_selector_all('video, source', 'e => e.map(x => x.src || x.currentSrc)'),
            'img': page.eval_on_selector_all('img', 'e => e.map(x => x.currentSrc || x.src)')[:40],
            'halo': [h for h in halo if any(k in h[1] for k in ('json', 'mpegurl', 'image', 'video'))][:80],
        }
    b.close()
json.dump(ki, open('windy/szonda2/onlinecamera.json', 'w'), ensure_ascii=False, indent=1)
