"""
ARGOS ATLAS kamerák (argosatlas.com) – magyarországi kamerák, amelyek
képe nálunk még nincs meg.

Az Argos egy világméretű kameragyűjtő. A teljes listája egy nyilvános
JSON (/api/cameras_index.json), kameránként pedig a /api/cam/{id}/stream
végpont elárulja az eredeti forrást (pl. "dyn:worldcam_europe2:836").
Ebből szűrjük ki azokat, amelyek képe a saját forrásainkban (Windy,
Útinform, Közút Figyelő) már megvan.

Az oldal Cloudflare mögött van, ezért – mint az Útinformnál – valódi
headless Chrome-ból, az oldal kontextusából kérdezünk le.
A kameránkénti forrást egy gyorsítótárban (windy/data/argos_forras.json)
tartjuk, így csak az új kamerákat kell egyenként lekérdezni.
"""
import base64
import json
import unicodedata
from math import asin, cos, radians, sin, sqrt
import os
import re
import sys
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

OUTPUT_FILE = 'windy/data/webcams_argos.json'
CACHE_FILE = 'windy/data/argos_forras.json'
BASE = 'https://www.argosatlas.com'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')
NYILVANTARTAS = 'windy/data/kamera_nyilvantartas.json'
MAX_UJ_LEKERES = int(os.environ.get('ARGOS_MAX_UJ', '1200'))
# Ennyi méteren belül egy saját közúti kamera = ugyanaz az Útinform-kép
# (az Argos közúti kamerái az Útinform képei, a Windy ugyanezeket adja).
KOZUTI_EGYEZES_M = 50

# Magyarország durva határpoligonja (lon, lat)
HU = [(16.11,46.87),(16.37,46.64),(16.6,46.47),(16.88,46.33),(17.25,46.11),(17.66,45.86),(18.2,45.78),(18.56,45.8),(18.83,45.91),(19.42,46.05),(20.05,46.14),(20.26,46.11),(20.72,46.17),(21.2,46.4),(21.29,46.62),(21.5,46.9),(21.67,47.0),(22.0,47.37),(22.18,47.6),(22.6,47.76),(22.9,48.0),(22.7,48.12),(22.2,48.42),(21.72,48.35),(21.45,48.58),(20.8,48.58),(20.47,48.47),(19.97,48.17),(19.5,48.2),(19.0,48.07),(18.82,47.83),(18.6,47.76),(17.86,47.75),(17.48,47.88),(17.17,48.02),(17.05,47.7),(16.68,47.6),(16.5,47.42),(16.45,47.15),(16.11,46.87)]


def magyar(la, lo):
    if not (45.73 <= la <= 48.59 and 16.1 <= lo <= 22.9):
        return False
    x, y, c = lo, la, False
    for (x1, y1), (x2, y2) in zip(HU, HU[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def normal(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def tav_m(a, b):
    la1, lo1, la2, lo2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * asin(sqrt(h))


def sajat_kamerak():
    """A saját forrásaink (Windy, Útinform, Közút Figyelő) nevei és helyei
    a kamera-nyilvántartásból."""
    try:
        ny = json.load(open(NYILVANTARTAS, encoding='utf-8')).get('kamerak', {})
    except (FileNotFoundError, json.JSONDecodeError):
        return set(), []
    nevek = {normal(v.get('nev')) for k, v in ny.items() if not k.startswith('argos:')}
    helyek = [(v['lat'], v['lon']) for k, v in ny.items()
              if not k.startswith('argos:') and v.get('lat') is not None]
    return nevek, helyek


def megvan_nalunk(e, kulcs, nevek, helyek):
    """Igaz, ha ennek az Argos-kamerának a képe a saját forrásainkban is megvan."""
    if kulcs and re.search(r'windy|utinform|kozut|ikszr', kulcs, re.I):
        return True
    if kulcs:  # ismert, más eredeti forrás (worldcam, YouTube, ...)
        return False
    if normal(e.get('name')) in nevek:
        return True
    if e.get('category') == 'trafico' and helyek:
        return min(tav_m((e['lat'], e['lon']), h) for h in helyek) <= KOZUTI_EGYEZES_M
    return False


def forraskulcs(stream):
    """A stream-címből az eredeti forrás azonosítója (pl. dyn:worldcam_europe2:836)."""
    if not stream:
        return None
    m = re.search(r'/api/sp/[^/]+/([A-Za-z0-9_\-=]+)', stream)
    if m:
        s = m.group(1)
        try:
            return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)).decode('utf-8', 'replace')
        except Exception:
            return s
    m = re.search(r'youtube(?:-nocookie)?\.com/embed/([\w-]+)', stream)
    if m:
        return 'youtube:' + m.group(1)
    return stream[:200]


def main():
    try:
        cache = json.load(open(CACHE_FILE, encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_context(user_agent=UA).new_page()
        page.goto(BASE + '/map/', wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(3000)
        lista = page.evaluate("async () => (await fetch('/api/cameras_index.json')).json()")
        hu = [e for e in lista if isinstance(e.get('lat'), (int, float))
              and isinstance(e.get('lon'), (int, float)) and magyar(e['lat'], e['lon'])]
        print(f'Argos: {len(lista)} kamera összesen, ebből {len(hu)} Magyarországon')

        hianyzik = [e['id'] for e in hu if e['id'] not in cache][:MAX_UJ_LEKERES]
        print(f'Forrás lekérdezése {len(hianyzik)} új kamerához...')
        if hianyzik:
            uj = page.evaluate("""async (ids) => {
                const out = {};
                const varj = ms => new Promise(r => setTimeout(r, ms));
                for (const id of ids) {
                    for (let k = 0; k < 4; k++) {
                        try {
                            const r = await fetch('/api/cam/' + encodeURIComponent(id) + '/stream');
                            if (r.status === 429) { await varj(8000 * (k + 1)); continue; }
                            out[id] = r.ok ? await r.json() : {hiba: r.status};
                        } catch (e) { out[id] = {hiba: String(e)}; }
                        break;
                    }
                    await varj(600);
                }
                return out;
            }""", hianyzik)
            for i, v in uj.items():
                if 'hiba' in v:
                    continue  # következő futáskor újra próbáljuk
                cache[i] = {'kulcs': forraskulcs(v.get('stream')), 'kind': v.get('kind'),
                            'stream': v.get('stream') if v.get('kind') == 'youtube' else None}

        # Képellenőrzés: van-e állókép (ha nincs és YouTube sem, nem mutatjuk).
        nevek, helyek = sajat_kamerak()
        jeloltek = [e for e in hu if not megvan_nalunk(e, cache.get(e['id'], {}).get('kulcs'), nevek, helyek)]
        ellenorizendo = [e['id'] for e in jeloltek if e['id'] in cache and not cache[e['id']].get('kep_ok')]
        print(f'{len(jeloltek)} kamera képe nincs meg nálunk; képellenőrzés: {len(ellenorizendo)}')
        if ellenorizendo:
            kep = page.evaluate("""async (ids) => {
                const out = {}; const varj = ms => new Promise(r => setTimeout(r, ms));
                for (const id of ids) {
                    try { const r = await fetch('/api/cam/' + id + '/image', {method: 'GET'});
                          out[id] = r.ok && (r.headers.get('content-type') || '').startsWith('image'); }
                    catch (e) { out[id] = false; }
                    await varj(500);
                }
                return out;
            }""", ellenorizendo)
            for i, ok in kep.items():
                cache[i]['kep_ok'] = bool(ok)
        b.close()

    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=0, sort_keys=True)

    import collections
    print('Forrástípusok:', collections.Counter(
        (cache.get(e['id'], {}).get('kulcs') or 'ismeretlen').rsplit(':', 1)[0] for e in hu).most_common(40))

    kamerak = []
    for e in jeloltek:
        c = cache.get(e['id'], {})
        if not c.get('kep_ok') and c.get('kind') != 'youtube':
            continue
        kamerak.append({
            'id': e['id'],
            'source': 'argos',
            'title': e.get('name') or 'Argos kamera',
            'city': None,
            'category': e.get('category'),
            'media_type': e.get('media_type'),
            'eredeti': c.get('kulcs'),
            'latitude': e['lat'],
            'longitude': e['lon'],
            'image_preview': f"{BASE}/api/cam/{e['id']}/image" if c.get('kep_ok') else None,
            'image_thumbnail': f"{BASE}/api/cam/{e['id']}/image" if c.get('kep_ok') else None,
            'player_embed': c.get('stream'),
        })
    # Csak akkor frissül az időbélyeg (és lesz commit), ha a lista változott.
    try:
        regi = json.load(open(OUTPUT_FILE, encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        regi = {}
    idopont = regi.get('updated_at') if regi.get('webcams') == kamerak else None
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'updated_at': idopont or datetime.now(timezone.utc).isoformat(), 'count': len(kamerak),
                   'webcams': kamerak}, f, ensure_ascii=False, indent=1)
    print(f'Elmentve: {OUTPUT_FILE} ({len(kamerak)} kamera)')


if __name__ == '__main__':
    sys.exit(main())
