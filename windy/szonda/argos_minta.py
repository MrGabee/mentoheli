"""Ideiglenes: mintaoldalhoz kicsinyített képek azokról az Argos kamerákról,
amelyek eredeti forrása nem a mi forrásaink egyike."""
import json, re
from playwright.sync_api import sync_playwright
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
SAJAT = re.compile(r'windy|utinform|kozut|ikszr|budapestkozut', re.I)
kamerak = json.load(open('windy/data/webcams_argos.json'))['webcams']
jelolt = [k for k in kamerak if not SAJAT.search(k.get('eredeti') or '')]
print('összes', len(kamerak), 'nem saját forrású', len(jelolt))
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(user_agent=UA).new_page()
    page.goto('https://www.argosatlas.com/map/', wait_until='networkidle', timeout=60000)
    page.wait_for_timeout(3000)
    kepek = page.evaluate("""async (ids) => {
        const out = {}; const varj = ms => new Promise(r => setTimeout(r, ms));
        for (const id of ids) {
            for (let k = 0; k < 3; k++) {
                try {
                    const r = await fetch('/api/cam/' + id + '/image');
                    if (r.status === 429) { await varj(8000 * (k + 1)); continue; }
                    if (!r.ok) { out[id] = 'HIBA ' + r.status; break; }
                    const bm = await createImageBitmap(await r.blob());
                    const w = Math.min(360, bm.width), h = Math.round(bm.height * w / bm.width);
                    const c = document.createElement('canvas'); c.width = w; c.height = h;
                    c.getContext('2d').drawImage(bm, 0, 0, w, h);
                    out[id] = c.toDataURL('image/jpeg', 0.62);
                } catch (e) { out[id] = 'HIBA ' + e; }
                break;
            }
            await varj(500);
        }
        return out;
    }""", [k['id'] for k in jelolt])
    b.close()
json.dump({'kamerak': jelolt, 'kepek': kepek}, open('windy/szonda/argos_minta.json', 'w'), ensure_ascii=False)
print('kép ok:', sum(1 for v in kepek.values() if v.startswith('data:')), 'hiba:', sum(1 for v in kepek.values() if not v.startswith('data:')))
