"""
📘 Facebook posztolási kvóta – közös napi korlát az új posztolóknak
Minden posztoló forrásnak saját napi maximuma van, és van egy közös
napi felső határ is, hogy a Make.com műveleti keret és a Facebook
oldal se teljen be (és ne legyen spam a követőknek).
Az állapot az fb_kvota.json fájlban van, napra bontva.
"""

import json
import os
from datetime import datetime, timedelta, timezone

MAGYAR_TZ = timezone(timedelta(hours=2))

KVOTA_FAJL = "fb_kvota.json"

# ⬇️⬇️⬇️ ITT ÁLLÍTHATÓK A NAPI KORLÁTOK ⬇️⬇️⬇️
# Forrásonkénti napi maximum (ami nincs a listában, az 1 posztot kaphat).
FORRAS_NAPI_MAX = {
    "idojaras_riasztas": 3,
    "reggeli_osszefoglalo": 1,
}
# Az összes, ezt a kvótát használó posztoló együttes napi maximuma.
OSSZES_NAPI_MAX = 5


def _ma():
    return datetime.now(MAGYAR_TZ).strftime("%Y-%m-%d")


def _betolt():
    if os.path.exists(KVOTA_FAJL):
        try:
            with open(KVOTA_FAJL, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _ment(adat):
    # Csak az utolsó 14 nap marad meg, hogy ne nőjön a fájl.
    napok = sorted(adat)[-14:]
    adat = {nap: adat[nap] for nap in napok}
    with open(KVOTA_FAJL, "w", encoding="utf-8") as f:
        json.dump(adat, f, ensure_ascii=False, indent=2)


def maradt(forras):
    """Hány posztot küldhet még ma ez a forrás (0 = elérte a korlátot)."""
    nap = _betolt().get(_ma(), {})
    forras_maradt = FORRAS_NAPI_MAX.get(forras, 1) - nap.get(forras, 0)
    osszes_maradt = OSSZES_NAPI_MAX - sum(nap.values())
    return max(0, min(forras_maradt, osszes_maradt))


def elhasznal(forras):
    """Egy elküldött poszt elkönyvelése."""
    adat = _betolt()
    nap = adat.setdefault(_ma(), {})
    nap[forras] = nap.get(forras, 0) + 1
    _ment(adat)
