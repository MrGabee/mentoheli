"""
💶 Euró és dollár árfolyam a reggeli és az esti poszthoz
Adatforrás: Frankfurter API (az Európai Központi Bank napi referencia-
árfolyamai), ingyenes, kulcs nélkül. Hétköznap kb. 16:00-kor frissül,
ezért a reggeli poszt az előző munkanapi, az esti a napi árfolyamot mutatja.
Ha a forrás nem elérhető, üres listát ad, és a poszt árfolyam nélkül megy ki.
"""

from datetime import date, timedelta

import requests

URL = "https://api.frankfurter.app/{tol}..{ig}"
DEVIZAK = [("EUR", "💶", "Euró"), ("USD", "💵", "Dollár")]
HONAPOK = ["jan.", "febr.", "márc.", "ápr.", "máj.", "jún.", "júl.", "aug.", "szept.", "okt.", "nov.", "dec."]


def _szam(x):
    return f"{x:.2f}".replace(".", ",")


def _ket_utolso(deviza, nap):
    """Az utolsó két munkanap árfolyama forintban: [(dátum, érték), ...]."""
    r = requests.get(URL.format(tol=(nap - timedelta(days=10)).isoformat(), ig=nap.isoformat()),
                     params={"from": deviza, "to": "HUF"}, timeout=20)
    r.raise_for_status()
    sorok = sorted((d, v["HUF"]) for d, v in r.json()["rates"].items())
    return sorok[-2:]


def sorok(nap=None):
    nap = nap or date.today()
    try:
        adatok = [(jel, nev, _ket_utolso(deviza, nap)) for deviza, jel, nev in DEVIZAK]
    except Exception as ex:
        print(f"  ⚠️ Árfolyam nem elérhető: {type(ex).__name__}")
        return []
    ki = []
    for jel, nev, ertekek in adatok:
        if not ertekek:
            return []
        most = ertekek[-1][1]
        sor = f"{jel} {nev}: {_szam(most)} Ft"
        if len(ertekek) == 2:
            valt = most - ertekek[0][1]
            if abs(valt) >= 0.005:
                sor += f" ({'▲' if valt > 0 else '▼'} {_szam(abs(valt))} Ft)"
            else:
                sor += " (nem változott)"
        ki.append(sor)
    d = date.fromisoformat(adatok[0][2][-1][0])
    ki.append(f"ℹ️ Az EKB {HONAPOK[d.month - 1]} {d.day}-i referencia-árfolyama, a bankok ettől eltérő áron váltanak.")
    return ki
