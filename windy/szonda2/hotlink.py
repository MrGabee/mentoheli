"""Ideiglenes: betölthető-e az Argos kép idegen oldalról <img>-gel?"""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()
    page.goto('https://mrgabee.github.io/balesetinfo/', wait_until='load')
    print('oldal betöltve')
    for i in ['84c35988b535734fc6', 'fa0833734ca541ee2d', '6e4196574452431ab0']:
        w = page.evaluate("""u => new Promise(r => { const im = new Image(); im.referrerPolicy='no-referrer';
            im.onload = () => r(im.naturalWidth + 'x' + im.naturalHeight); im.onerror = () => r('HIBA'); im.src = u; })""",
            f'https://www.argosatlas.com/api/cam/{i}/image?t=1')
        w2 = page.evaluate("""u => new Promise(r => { const im = new Image();
            im.onload = () => r(im.naturalWidth + 'x' + im.naturalHeight); im.onerror = () => r('HIBA'); im.src = u; })""",
            f'https://www.argosatlas.com/api/cam/{i}/image?t=2')
        print('HOTLINK', i, 'no-referrer:', w, 'referrerrel:', w2)
    b.close()
import json
json.dump({'kesz': True}, open('windy/szonda2/hotlink.json', 'w'))
