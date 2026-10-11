"""
📘 Facebook posztolási kvóta – közös napi és havi korlát minden posztolónak
Minden posztoló forrásnak saját napi maximuma van, és van egy közös
napi és havi felső határ is, hogy a Make.com műveleti kerete ne fogyjon
ki (és ne legyen spam a követőknek).

A számláló egy GitHub repó-változóban (Settings → Secrets and variables →
Actions → Variables → FB_KVOTA) van, nem fájlban, így a párhuzamosan futó
workflow-k nem írják felül egymás commitjait. Ehhez a workflow-nak
FB_KVOTA_TOKEN néven át kell adni a PAT_TOKEN-t.
Ha a token nincs megadva (pl. helyi futtatásnál), az fb_kvota.json fájlt
használja. Ha a GitHub API nem elérhető, a posztolást NEM tiltja le.
"""

import json
import os
from datetime import datetime, timedelta, timezone

import requests

MAGYAR_TZ = timezone(timedelta(hours=2))

KVOTA_FAJL    = "fb_kvota.json"
VALTOZO_NEV   = "FB_KVOTA"
GITHUB_TOKEN  = os.environ.get("FB_KVOTA_TOKEN", "")
GITHUB_REPO   = os.environ.get("GITHUB_REPOSITORY", "")

# ⬇️⬇️⬇️ ITT ÁLLÍTHATÓK A KORLÁTOK ⬇️⬇️⬇️
# Forrásonkénti napi maximum (ami nincs a listában, az 1 posztot kaphat).
FORRAS_NAPI_MAX = {
    "vizmuvek":             6,
    "aramszunet":           6,
    "police":               6,
    "idojaras_riasztas":    3,
    "reggeli_osszefoglalo": 1,
}
# Az összes posztoló együttes napi és havi maximuma.
# Make.com ingyenes csomag: havi 1000 művelet, egy poszt kb. 2 műveletet
# használ (webhook + Facebook modul) → havonta legfeljebb ~500 poszt fér bele.
OSSZES_NAPI_MAX = 20
OSSZES_HAVI_MAX = 400


def _most():
    return datetime.now(MAGYAR_TZ)


# ─────────────────────────────────────────────
#  Tárolás: GitHub repó-változó, vagy helyi fájl
# ─────────────────────────────────────────────
def _api_url(nev=""):
    return f"https://api.github.com/repos/{GITHUB_REPO}/actions/variables{('/' + nev) if nev else ''}"

def _fejlec():
    return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

def _github_mod():
    return bool(GITHUB_TOKEN and GITHUB_REPO)

def _betolt():
    """None = nem sikerült beolvasni (ilyenkor nem tiltunk)."""
    if _github_mod():
        try:
            r = requests.get(_api_url(VALTOZO_NEV), headers=_fejlec(), timeout=15)
            if r.status_code == 404:
                return {}
            if r.status_code == 200:
                return json.loads(r.json().get("value") or "{}")
            print(f"  ⚠️ Kvóta beolvasás sikertelen (HTTP {r.status_code}).")
        except Exception as e:
            print(f"  ⚠️ Kvóta beolvasás hiba: {e}")
        return None
    if os.path.exists(KVOTA_FAJL):
        try:
            with open(KVOTA_FAJL, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _ment(adat):
    if _github_mod():
        ertek = json.dumps(adat, ensure_ascii=False, separators=(",", ":"))
        try:
            r = requests.patch(_api_url(VALTOZO_NEV), headers=_fejlec(),
                               json={"name": VALTOZO_NEV, "value": ertek}, timeout=15)
            if r.status_code == 404:
                r = requests.post(_api_url(), headers=_fejlec(),
                                  json={"name": VALTOZO_NEV, "value": ertek}, timeout=15)
            if r.status_code not in (201, 204):
                print(f"  ⚠️ Kvóta mentés sikertelen (HTTP {r.status_code}): {r.text[:200]}")
        except Exception as e:
            print(f"  ⚠️ Kvóta mentés hiba: {e}")
        return
    with open(KVOTA_FAJL, "w", encoding="utf-8") as f:
        json.dump(adat, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
#  Nyilvános függvények
# ─────────────────────────────────────────────
def maradt(forras):
    """Hány posztot küldhet még ez a forrás (0 = elérte valamelyik korlátot)."""
    adat = _betolt()
    if adat is None:
        return 1
    most = _most()
    nap  = adat.get("napok", {}).get(most.strftime("%Y-%m-%d"), {})
    honap_db = adat.get("honapok", {}).get(most.strftime("%Y-%m"), 0)
    return max(0, min(
        FORRAS_NAPI_MAX.get(forras, 1) - nap.get(forras, 0),
        OSSZES_NAPI_MAX - sum(nap.values()),
        OSSZES_HAVI_MAX - honap_db,
    ))

def elhasznal(forras):
    """Egy elküldött poszt elkönyvelése."""
    adat = _betolt()
    if adat is None:
        return
    most = _most()
    napok = adat.setdefault("napok", {})
    nap = napok.setdefault(most.strftime("%Y-%m-%d"), {})
    nap[forras] = nap.get(forras, 0) + 1
    honapok = adat.setdefault("honapok", {})
    honapok[most.strftime("%Y-%m")] = honapok.get(most.strftime("%Y-%m"), 0) + 1
    # Csak az utolsó 7 nap és 3 hónap marad meg, hogy kicsi maradjon.
    adat["napok"]   = {k: napok[k] for k in sorted(napok)[-7:]}
    adat["honapok"] = {k: honapok[k] for k in sorted(honapok)[-3:]}
    _ment(adat)

def posztolhat(forras):
    """Rövid ellenőrzés naplózással a meglévő posztolóknak."""
    if maradt(forras) > 0:
        return True
    print(f"  ⛔ [{forras}] Elérte a napi/havi Facebook posztkorlátot - a poszt most kimarad.")
    return False
