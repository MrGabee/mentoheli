"""Ideiglenes szonda: kameraforrás-oldalak hálózati forgalmának felderítése."""
import json, re, sys
from playwright.sync_api import sync_playwright

OLDALAK = sys.argv[1:] or [
    'https://www.argosatlas.com/map/?lat=47.2&lng=19.4&zoom=7',
    'https://www.argosatlas.com/',
]
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    for url in OLDALAK:
        print('\n' + '=' * 30, url)
        ctx = b.new_context(user_agent=UA, viewport={'width': 1400, 'height': 1000})
        page = ctx.new_page()
        valaszok = []
        def on_resp(r):
            ct = r.headers.get('content-type', '')
            if any(x in ct for x in ('json', 'javascript', 'text/plain', 'xml', 'protobuf', 'octet')) or '/api' in r.url:
                valaszok.append(r)
        page.on('response', on_resp)
        try:
            page.goto(url, wait_until='networkidle', timeout=45000)
        except Exception as e:
            print('goto hiba:', e)
        page.wait_for_timeout(5000)
        print('cím:', page.title())
        print('szöveg:', re.sub(r'\s+', ' ', page.inner_text('body'))[:800])
        hrefs = page.eval_on_selector_all('a[href]', 'els => els.map(e => e.href)')
        hu = [h for h in hrefs if re.search(r'hungar|magyar|ungarn|/hu[/-]', h, re.I)]
        print('magyar linkek:', len(hu), hu[:30])
        for r in valaszok:
            ct = r.headers.get('content-type', '')
            if 'javascript' in ct:
                print('  JS', r.url[:160])
                continue
            try:
                t = r.text()
            except Exception:
                t = ''
            hu_db = len(re.findall(r'Hungary|Magyarorsz|"HU"|Budapest', t))
            print(f'  {r.status} {ct[:30]} {len(t)}B hu={hu_db} {r.url[:200]}')
            if len(t) < 100000 and ('json' in ct):
                print('     ', t[:400].replace('\n', ' '))
        ctx.close()
    b.close()
