"""
🤾 A foci mellett a többi sportág csepeli csapatainak meccsei.
A csepeli_sport.osszes_meccs() ugyanabban a formában kapja meg őket,
mint az MLSZ-meccseket, csak a "sport" mezőben más áll.

  - kézilabda: az MKSZ nyilvános API-ja (public.mksz.hu), sportszervezet szerint

Kézi próba (nem posztol): python mas_sportagak.py [YYYY-MM-DD]
"""

import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

MKSZ_API = "https://public.mksz.hu/public/api/v1/"
MKSZ_FEJLEC = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/129.0 Safari/537.36",
               "Accept": "application/json", "Origin": "https://www.mksz.hu",
               "Referer": "https://www.mksz.hu/"}
# Csepeli kézilabda-egyesületek az MKSZ nyilvántartásában (azonosító: név)
MKSZ_KLUBOK = {328: "Csepel DSE", 899: "Csepel SZSE", 336: "Csepeli KSE"}

# Sportáganként az emoji és a forrás neve a posztban
EMOJI = {"foci": "⚽", "kezilabda": "🤾"}
FORRAS = {"foci": "MLSZ adatbank", "kezilabda": "MKSZ"}
HASHTAG = {"foci": "#foci", "kezilabda": "#kézilabda"}


def _json(url):
    req = urllib.request.Request(url, headers=MKSZ_FEJLEC)
    with urllib.request.urlopen(req, timeout=25) as f:
        return json.loads(f.read().decode("utf-8", "replace"))


def mksz_meccs(m, klub):
    """Egy MKSZ-meccs a csepeli_sport formájában."""
    ido = datetime.fromisoformat(m["merkozesDatum"][:19])
    lezart = m.get("merkozesStatusz") == "JEGYZOK_LEZARVA"
    h, v = m.get("hazaiCsapatGol"), m.get("vendegCsapatGol")
    helyszin = (m.get("letesitmenyNev") or "").strip()
    bajnoksag = (m.get("alversenyNev") or m.get("foversenyRovidNev") or "").strip()
    korosztaly = (m.get("korosztalyNev") or "").strip()
    if korosztaly and korosztaly.lower() not in bajnoksag.lower():
        bajnoksag = f"{korosztaly} {bajnoksag}".strip()
    return {
        "id": f"mksz-{m['merkozesId']}",
        "sport": "kezilabda",
        "csapat": klub,
        "bajnoksag": bajnoksag or "kézilabda",
        "hazai": (m.get("hazaiCsapatNev") or "").strip(),
        "vendeg": (m.get("vendegCsapatNev") or "").strip(),
        "nap": ido.date(),
        "ido": "" if (ido.hour, ido.minute) == (0, 0) else f"{ido.hour}:{ido.minute:02d}",
        "golok": (int(h), int(v)) if lezart and h is not None and v is not None else None,
        "helyszin": "" if helyszin in ("", "Nincs megadva") else helyszin,
    }


def kezilabda(tol, ig):
    """A csepeli kézilabdacsapatok meccsei tol..ig között. Hiba esetén üres lista."""
    meccsek = {}
    for azon, klub in MKSZ_KLUBOK.items():
        p = {"sportszervezetId.equals": azon,
             "merkozesDatum.greaterThanOrEqual": f"{tol}T00:00:00.000",
             "merkozesDatum.lessThanOrEqual": f"{ig}T23:59:59.000",
             "size": 200, "page": 0}
        try:
            adat = _json(MKSZ_API + "versenyek/program?" + urllib.parse.urlencode(p))
        except Exception as ex:
            print(f"  ❌ MKSZ {klub}: {ex}")
            continue
        if isinstance(adat, dict):
            adat = adat.get("content") or []
        for m in adat:
            try:
                meccsek.setdefault(f"mksz-{m['merkozesId']}", mksz_meccs(m, klub))
            except Exception as ex:
                print(f"  ⚠️ MKSZ meccs kimaradt: {ex}")
    print(f"  🤾 {len(meccsek)} kézilabdameccs")
    return list(meccsek.values())


def osszes(ma=None):
    """Minden nem foci meccs a mai nap körül (2 hét vissza, 2 hét előre)."""
    ma = ma or date.today()
    return kezilabda(ma - timedelta(days=14), ma + timedelta(days=14))


if __name__ == "__main__":
    nap = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    for m in sorted(osszes(nap), key=lambda m: (m["nap"], m["ido"] or "99")):
        print(f"   {m['nap']} {m['ido']:>5} | {m['bajnoksag']} | {m['hazai']} – {m['vendeg']} | {m['golok']} | {m['helyszin']}")
