"""
🌙 Éjszakai várakoztatás: 22:00-tól a reggeli jó reggelt posztig
a nem sürgős értesítések (áramszünet, vízművek) nem mennek ki a Facebookra,
hanem a szkript saját állapotfájljában (az "fb_sor" kulcs alatt) várnak, és a
reggeli első futáskor mennek ki.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import json

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


def ejszaka(t=None):
    t = t or datetime.now(ZoneInfo("Europe/Budapest"))
    hm = (t.hour, t.minute)
    if hm >= EJSZAKA_TOL or hm < REGGELI_IDO:
        return True
    return hm < LEGKESOBB and not reggeli_kiment(t.date())


def kuld_vagy_sorba(allapot, szoveg, kuldo):
    if ejszaka():
        allapot.setdefault("fb_sor", []).append(szoveg)
        print("  🌙 Éjszaka van, a poszt reggelig vár.")
        return
    kuldo(szoveg)


def sor_kiurites(allapot, kuldo):
    """Reggel kiküldi az éjszaka félretett posztokat; ami nem ment ki, marad."""
    if ejszaka() or not allapot.get("fb_sor"):
        return
    maradt = []
    for szoveg in allapot["fb_sor"]:
        print("📘 Éjszaka félretett poszt küldése...")
        if kuldo(szoveg) is False:
            maradt.append(szoveg)
    allapot["fb_sor"] = maradt
