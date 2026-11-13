"""Ideiglenes: Argos magyar kameráinak részletei (képforrás) – kép szerinti összevetés."""
import json, re, collections
from playwright.sync_api import sync_playwright
src = open('windy/szonda/argos_elemzes.py').read()
HU = eval(re.search(r"HU = (\[.*?\])\n", src).group(1))
def bent(la, lo):
    x, y, c = lo, la, False
    for (x1, y1), (x2, y2) in zip(HU, HU[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(user_agent=UA).new_page()
    page.goto('https://www.argosatlas.com/map/', wait_until='networkidle', timeout=45000)
    page.wait_for_timeout(3000)
    eredmeny = page.evaluate("""async () => {
        const L = await (await fetch('/api/cameras_index.json')).json();
        return L;
    }""")
    hu = [e for e in eredmeny if isinstance(e.get('lat'), (int, float)) and 45.73 <= e['lat'] <= 48.59 and 16.1 <= e['lon'] <= 22.9 and bent(e['lat'], e['lon'])]
    print('magyar:', len(hu))
    ids = [e['id'] for e in hu]
    reszl = page.evaluate("""async (ids) => {
        const out = {}; let i = 0;
        async function munkas() {
            while (i < ids.length) {
                const id = ids[i++];
                try { const r = await fetch('/api/cam/' + encodeURIComponent(id));
                      out[id] = {s: r.status, t: (await r.text()).slice(0, 4000)}; }
                catch (e) { out[id] = {s: 0, t: String(e)}; }
            }
        }
        await Promise.all(Array.from({length: 6}, munkas));
        return out;
    }""", ids)
    b.close()
print('státuszok:', collections.Counter(v['s'] for v in reszl.values()))
for id_ in ids[:3]:
    print('MINTA', id_, reszl[id_]['t'][:1500])
print('#### LISTA')
for e in hu:
    r = reszl.get(e['id'], {})
    urls = sorted(set(re.findall(r'https?://[^"\\\s]+', r.get('t', '').replace('\\/', '/'))))
    print('K|' + '|'.join([e['id'], e['category'], e['media_type'], e['name'], f"{e['lat']:.5f},{e['lon']:.5f}", str(r.get('s'))] + urls[:4]))
