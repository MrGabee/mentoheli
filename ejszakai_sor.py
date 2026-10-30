"""
🌙 Éjszakai várakoztatás: az esti jó éjszakát posztól (legkésőbb 22:00-tól) a reggeli jó reggelt posztig
a nem sürgős értesítések (áramszünet, vízművek) nem mennek ki a Facebookra,
hanem a szkript saját állapotfájljában (az "fb_sor" kulcs alatt) várnak, és a
reggeli első futáskor mennek ki.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import json

import poszt_utem

# 22:00-tól a jó reggelt kimeneteléig várnak a posztok. Ha a jó reggelt
# valamiért késik, legkésőbb LEGKESOBB-kor akkor is kimennek.
EJSZAKA_TOL = (22, 0)
REGGELI_IDO = (5, 50)
LEGKESOBB = (8, 0)
SZINES_ALLAPOT = "szines_allapot.json"


def reggeli_kiment(nap):
    try:
        with open(SZINES_ALLAPOT, encoding="utf-8") as f:
            return json.load(f).get("kiment", {}).get("reggeli") == nap.isoformat()
    except Exception:
        return False


def esti_kiment(nap):
    try:
        with open(SZINES_ALLAPOT, encoding="utf-8") as f:
            return json.load(f).get("kiment", {}).get("esti_idojaras") == nap.isoformat()
    except Exception:
        return False


def ejszaka(t=None):
    t = t or datetime.now(ZoneInfo("Europe/Budapest"))
    hm = (t.hour, t.minute)
    if hm >= EJSZAKA_TOL or hm < REGGELI_IDO:
        return True
    if hm >= (12, 0) and esti_kiment(t.date()):
        return True  # a jó éjszakát poszt után már nem posztolok
    return hm < LEGKESOBB and not reggeli_kiment(t.date())


def kuld_vagy_sorba(allapot, szoveg, kuldo, surgos=True):
    """Sürgős poszt: azonnal kimegy, ha az előző óta eltelt a minimális idő,
    különben a sor elejére kerül. Ráérős poszt (előre bejelentett esemény):
    sorba kerül, és a következő szabad sávban megy ki (poszt_utem)."""
    sor = allapot.setdefault("fb_sor", [])
    if ejszaka():
        sor.append({"szoveg": szoveg, "surgos": surgos})
        print("  🌙 Éjszaka van, a poszt reggelig vár.")
        return
    if surgos and poszt_utem.mehet(surgos=True) and kuldo(szoveg) is not False:
        poszt_utem.jegyez()
        return
    if surgos:
        sor.insert(0, {"szoveg": szoveg, "surgos": True})
        print("  ⏳ A sürgős poszt a sor elejére került.")
    else:
        sor.append({"szoveg": szoveg, "surgos": False})
        print("  🗓️ Előre bejelentett esemény: a poszt a következő szabad sávban megy ki.")
        sor_kiurites(allapot, kuldo)


def sor_kiurites(allapot, kuldo):
    """A félretett posztokból egyet küld ki, ha van szabad sáv; a többi vár."""
    sor = allapot.get("fb_sor") or []
    if ejszaka() or not sor:
        return
    elem = sor[0] if isinstance(sor[0], dict) else {"szoveg": sor[0], "surgos": False}
    if not poszt_utem.mehet(surgos=elem["surgos"]):
        return
    print("📘 Félretett poszt küldése...")
    if kuldo(elem["szoveg"]) is not False:
        allapot["fb_sor"] = sor[1:]
        poszt_utem.jegyez()
