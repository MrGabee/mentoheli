"""
ÚJ KAMERÁK FIGYELÉSE
-------------------------------------------------------------------------
Minden futáskor lekéri az összes kameraforrás listáját (Windy, Útinform,
Közút Figyelő), és a windy/data/kamera_nyilvantartas.json fájlban
feljegyzi, melyik kamerát mikor láttuk először. A weboldal ebből jelöli
"ÚJ" címkével a friss kamerákat.

Egy forrás legelső sikeres lekérdezésekor minden kamera "alap" lesz
(vagyis nem új), különben az indulásnál minden kamera újnak látszana.
Ha egy forrás épp nem érhető el, a nyilvántartásban nem változik semmi.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

ITT = os.path.dirname(os.path.abspath(__file__))
NYILVANTARTAS = os.path.join(ITT, 'data', 'kamera_nyilvantartas.json')
WINDY_JSON = os.path.join(ITT, 'data', 'webcams_hu.json')
UTINFORM_URL = 'https://baleset-info.hu/tv2/utinform/serve_utinform_webcams.php'
KF_LIST_URL = 'https://kozutfigyelo-back.budapestkozut.hu/api/ikszr/list'
FEJLEC = {'User-Agent': 'Mozilla/5.0 (balesetinfo kamera-nyilvantarto)'}


def windy_kamerak():
    with open(WINDY_JSON, encoding='utf-8') as f:
        adat = json.load(f)
    return {f"windy:{c['id']}": c.get('title') or '' for c in adat.get('webcams', [])}


def utinform_kamerak():
    r = requests.get(UTINFORM_URL, headers=FEJLEC, timeout=30)
    r.raise_for_status()
    return {f"utinform:{c['id']}": c.get('title') or '' for c in r.json().get('webcams', [])}


def kozutfigyelo_kamerak():
    kamerak, oldal, oldalak = {}, 1, 1
    while oldal <= oldalak:
        r = requests.post(KF_LIST_URL, headers=FEJLEC, timeout=30,
                          json={'page': oldal, 'limit': 100, 'objectType': 'cameras', 'filter': ''})
        r.raise_for_status()
        d = r.json().get('data') or {}
        for doc in d.get('docs') or []:
            if doc.get('is_active') is False or doc.get('status') == 'inactive':
                continue
            kamerak[f"kozutfigyelo:kf-{doc['external_id']}"] = doc.get('location_description') or ''
        oldalak = d.get('pages') or 1
        oldal += 1
    return kamerak


FORRASOK = {
    'windy': windy_kamerak,
    'utinform': utinform_kamerak,
    'kozutfigyelo': kozutfigyelo_kamerak,
}


def main():
    most = datetime.now(timezone.utc).isoformat(timespec='seconds')
    try:
        with open(NYILVANTARTAS, encoding='utf-8') as f:
            ny = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        ny = {}
    ny.setdefault('kamerak', {})
    ny.setdefault('alap_kesz', {})

    ujak = []
    elotte = json.dumps(ny, sort_keys=True)
    for forras, lekeres in FORRASOK.items():
        try:
            kamerak = lekeres()
        except Exception as e:  # egy forrás hibája ne állítsa meg a többit
            print(f'[{forras}] nem érhető el: {e}')
            continue
        if not kamerak:
            print(f'[{forras}] üres lista, kihagyva')
            continue
        alap = not ny['alap_kesz'].get(forras)
        for kulcs, nev in kamerak.items():
            if kulcs in ny['kamerak']:
                continue
            ny['kamerak'][kulcs] = {'elso': 'alap' if alap else most, 'nev': nev}
            if not alap:
                ujak.append(f'{kulcs} ({nev})')
        ny['alap_kesz'][forras] = True
        print(f'[{forras}] {len(kamerak)} kamera' + (' – alapállapot rögzítve' if alap else ''))

    if json.dumps(ny, sort_keys=True) == elotte:
        print('Nincs új kamera, a nyilvántartás változatlan.')
        return 0
    ny['frissitve'] = most
    os.makedirs(os.path.dirname(NYILVANTARTAS), exist_ok=True)
    with open(NYILVANTARTAS, 'w', encoding='utf-8') as f:
        json.dump(ny, f, ensure_ascii=False, indent=0, sort_keys=True)
    print(f'Új kamera most: {len(ujak)}')
    for u in ujak:
        print('  +', u)
    return 0


if __name__ == '__main__':
    sys.exit(main())
