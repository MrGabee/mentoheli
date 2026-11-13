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
    return {f"windy:{c['id']}": (c.get('title') or '', c.get('latitude'), c.get('longitude')) for c in adat.get('webcams', [])}


def utinform_kamerak():
    r = requests.get(UTINFORM_URL, headers=FEJLEC, timeout=30)
    r.raise_for_status()
    return {f"utinform:{c['id']}": (c.get('title') or '', c.get('latitude'), c.get('longitude')) for c in r.json().get('webcams', [])}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def tavolsag_m(a, b):
    from math import radians, sin, cos, asin, sqrt
    la1, lo1, la2, lo2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * asin(sqrt(h))


# Ennyi méteren belül egy másik forrás kamerája "ugyanaz a hely":
# az ilyen kamerát nem jelöljük újnak.
KOZELI_M = 150


def kozeli_regi(kulcs, hely, ny):
    """Egy másik forrás régebbi kamerája, ami ugyanott van (vagy None)."""
    if hely[0] is None or hely[1] is None:
        return None
    forras = kulcs.split(':', 1)[0]
    legjobb = None
    for k, v in ny['kamerak'].items():
        if k.split(':', 1)[0] == forras or v.get('lat') is None:
            continue
        if v.get('elso') != 'alap':
            continue  # csak a már korábban ismert kamerákhoz mérünk
        d = tavolsag_m(hely, (v['lat'], v['lon']))
        if d <= KOZELI_M and (legjobb is None or d < legjobb[1]):
            legjobb = (k, d)
    return legjobb


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
            kamerak[f"kozutfigyelo:kf-{doc['external_id']}"] = (doc.get('location_description') or '', _f(doc.get('latitude')), _f(doc.get('longitude')))
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
        for kulcs, (nev, lat, lon) in kamerak.items():
            regi = ny['kamerak'].get(kulcs)
            if regi is not None:
                # régi bejegyzés kiegészítése a hellyel (egyszeri pótlás)
                if regi.get('lat') is None and lat is not None:
                    regi['lat'], regi['lon'] = round(lat, 5), round(lon, 5)
                continue
            ny['kamerak'][kulcs] = {'elso': 'alap' if alap else most, 'nev': nev,
                                   'lat': round(lat, 5) if lat is not None else None,
                                   'lon': round(lon, 5) if lon is not None else None}
            if not alap:
                ujak.append(kulcs)
        ny['alap_kesz'][forras] = True
        print(f'[{forras}] {len(kamerak)} kamera' + (' – alapállapot rögzítve' if alap else ''))

    # Az "új" kamerák közül, amelyik egy másik forrásban már megvolt
    # ugyanott, azt nem tekintjük újnak. (A korábban újnak jelöltekre is
    # lefut, amíg nincsenek ellenőrizve.)
    for kulcs, v in ny['kamerak'].items():
        if v.get('elso') == 'alap' or v.get('ellenorizve'):
            continue
        talalt = kozeli_regi(kulcs, (v.get('lat'), v.get('lon')), ny)
        if v.get('lat') is None:
            continue
        v['ellenorizve'] = True
        if talalt:
            v['hasonlo'] = talalt[0]
            print(f"  = {kulcs} ({v.get('nev')}) már megvolt: {talalt[0]} "
                  f"({ny['kamerak'][talalt[0]].get('nev')}), {talalt[1]:.0f} m")
        else:
            print(f"  + valóban új: {kulcs} ({v.get('nev')})")
    ujak = [k for k in ujak if not ny['kamerak'][k].get('hasonlo')]

    if json.dumps(ny, sort_keys=True) == elotte:
        print('Nincs új kamera, a nyilvántartás változatlan.')
        return 0
    ny['frissitve'] = most
    os.makedirs(os.path.dirname(NYILVANTARTAS), exist_ok=True)
    with open(NYILVANTARTAS, 'w', encoding='utf-8') as f:
        json.dump(ny, f, ensure_ascii=False, indent=0, sort_keys=True)
    print(f'Új kamera most: {len(ujak)}')
    for u in ujak:
        print('  +', u, ny['kamerak'][u].get('nev'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
