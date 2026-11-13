"""Ideiglenes: Argos kamera-végpontok próbája néhány magyar kamerán."""
import json
from playwright.sync_api import sync_playwright
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
IDK = ['ab046e8c8b3d73495d', '84c35988b535734fc6', '8844a34c51fe0be9b3', 'fa0833734ca541ee2d', '6e4196574452431ab0', 'a8709bc993b71f6845']
ki = {}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(user_agent=UA).new_page()
    page.goto('https://www.argosatlas.com/map/', wait_until='networkidle', timeout=45000)
    page.wait_for_timeout(3000)
    for i in IDK:
        for veg in ['feature', 'stream', 'image', 'eta']:
            u = f'/api/cam/{i}/{veg}'
            ki[u] = page.evaluate("""async u => { const r = await fetch(u);
                const ct = r.headers.get('content-type') || '';
                if (ct.includes('image')) { const bl = await r.blob(); return [r.status, ct, 'KÉP ' + bl.size + ' B', r.url]; }
                return [r.status, ct, (await r.text()).slice(0, 2500), r.url]; }""", u)
            page.wait_for_timeout(1500)
    b.close()
json.dump(ki, open('windy/szonda/argos_proba.json', 'w'), ensure_ascii=False, indent=1)
