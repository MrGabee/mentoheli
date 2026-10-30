"""
🚧 CSEPELI ÉS ERZSÉBETI KÖZÚTI ESEMÉNYEK – BKK Info "Közút" fül
Forrás: https://bkk.hu/bkk-info/#!t=kozut (minden kategória)

A balesetekről szóló e-mail továbbra is a bkk_kozut_playwright_monitor.py
dolga, balesetről itt NEM megy poszt. Ez a szkript ugyanazt az oldalt
olvassa, minden más kategóriával (lezárás, sávlezárás, útfelújítás...), és csak a XXI. és XX.
kerületet, illetve a környék fő útjait érintő ÚJ eseményeket posztolja ki
a Facebook-oldalra (Make.com webhookon keresztül).

Első futáskor (üres állapotnál) csak megjegyzi a már futó eseményeket,
nem posztol, hogy ne zúduljon ki egyszerre egy halom régi lezárás.
"""

import os
import re
import json
import random
import hashlib
import requests
from datetime import datetime

import poszt_valtozatos
import poszt_utem
from ejszakai_sor import ejszaka
from bkk_kozut_playwright_monitor import (
    sync_playwright, cookie_sav_elfogadasa, esemenyek_kinyerese, most,
    MAX_PROBALKOZAS, UJRAPROBALKOZAS_ALAP_VARAKOZAS_MP,
)
import time

BKK_KOZUT_OSSZES_URL = "https://bkk.hu/bkk-info/#!t=kozut&d=today"
# A baleseteket Gábor külön kezeli (bkk_kozut_playwright_monitor.py), ezért
# a baleset-szűrt listát is lekérjük, és ami abban szerepel, azt kihagyjuk.
BKK_KOZUT_BALESET_URL = "https://bkk.hu/bkk-info/#!t=kozut&e=3&d=today"
BALESET_SZAVAK = ["baleset", "ütközés", "karambol"]
ALLAPOT_FAJL = "bkk_kozut_csepel_allapot.json"
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")
TESZT_MOD = os.environ.get("TESZT_MOD", "0") == "1"
# Az egy futásban talált új események egyetlen, összevont posztban mennek ki.
# Ugyanazzal a címmel ennyi napon belül nem posztolunk újra (a naponta
# ismétlődő éjszakai korlátozások minden nap új azonosítót kapnak).
CIM_ISMETLES_NAP = 14
# Éjszaka nem posztolunk: az új események a jó reggelt posztig várnak (ejszakai_sor).

# A cím elején álló kerületjelzés ("XXI., Szent István úton") a legbiztosabb.
KERULET_MINTA = re.compile(r"(?<![IVX])(XXI|XX)\.\s*,")
# Kerületjelzés nélküli címekhez: csepeli, erzsébeti és a környéket érintő utak.
KULCSSZAVAK = [
    "csepel", "pesterzsébet", "weiss manfréd", "ráckevei", "rákóczi ferenc út",
    "szent istván út", "corvin csomópont", "gerincút", "gubacsi", "határ út",
    "nagykőrösi út", "soroksári út", "kvassay", "deák ferenc híd",
    "kis-duna", "szabadkikötő", "hollandi út", "szentlőrinci út", "helsinki út",
]

CIMEK = [
    "🚧 FORGALMI VÁLTOZÁS A KÖRNYÉKEN 🚧",
    "🚦 ÚJ KORLÁTOZÁS: ERRE FIGYELJETEK! 🚦",
    "🛣️ LEZÁRÁS, SÁVSZŰKÍTÉS – CSEPEL ÉS KÖRNYÉKE 🛣️",
    "⚠️ AUTÓSOK, FIGYELEM! ⚠️",
    "🚧 VÁLTOZIK A FORGALOM 🚧",
]
BEVEZETOK = [
    "A BKK közúti oldalán új bejegyzést láttam, ami minket is érint:",
    "Szólok előre, mert a környékünkön változik a forgalmi rend:",
    "Ha erre jártok, számoljatok vele:",
    "Friss infó a BKK-tól, ami a mi utainkat érinti:",
    "Ezt érdemes tudni, mielőtt elindultok:",
]
ZAROK = [
    "Indulás előtt érdemes ránézni a térképre, és kicsit több időt számolni.",
    "Aki teheti, kerülje el ezt a szakaszt, a többiek legyenek türelmesek.",
    "Vigyázzatok magatokra és egymásra!",
    "Ha arra jártok, és látjátok, milyen a helyzet, írjátok meg kommentben.",
    "Lassítsatok, és figyeljetek a kihelyezett táblákra!",
]


def kornyekbeli(cim):
    if any(b in cim.lower() for b in BALESET_SZAVAK):
        return False
    if KERULET_MINTA.search(cim):
        return True
    kis = cim.lower()
    # Az M0-ból csak a déli szakasz érint minket (Deák Ferenc híd, Csepel-sziget).
    if "m0" in kis and "déli" in kis:
        return True
    return any(k in kis for k in KULCSSZAVAK)


def oldal_esemenyei():
    utolso_hiba = None
    for probalkozas in range(1, MAX_PROBALKOZAS + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    viewport={"width": 1400, "height": 1000},
                )
                page = context.new_page()
                print(f"🌐 Betöltés ({probalkozas}/{MAX_PROBALKOZAS}): {BKK_KOZUT_OSSZES_URL}")
                page.goto(BKK_KOZUT_OSSZES_URL, wait_until="load", timeout=30000)
                page.wait_for_timeout(5000)
                cookie_sav_elfogadasa(page)
                szoveg = page.inner_text("body")
                esemenyek = esemenyek_kinyerese(szoveg)

                page.goto(BKK_KOZUT_BALESET_URL, wait_until="load", timeout=30000)
                page.reload(wait_until="load", timeout=30000)
                page.wait_for_timeout(5000)
                baleset_szoveg = page.inner_text("body")
                baleset_idk = {e["id"] for e in esemenyek_kinyerese(baleset_szoveg)}
                browser.close()
                if "Közúti közlekedési változások" not in baleset_szoveg:
                    raise RuntimeError("A baleset-lista nem töltődött be")
                return szoveg, [e for e in esemenyek if e["id"] not in baleset_idk]
        except Exception as ex:
            utolso_hiba = ex
            print(f"  ⚠️ Sikertelen próbálkozás ({probalkozas}/{MAX_PROBALKOZAS}): {ex}")
            if probalkozas < MAX_PROBALKOZAS:
                time.sleep(UJRAPROBALKOZAS_ALAP_VARAKOZAS_MP * (2 ** (probalkozas - 1)))
    raise RuntimeError(f"Az oldal betöltése sikertelen: {utolso_hiba}")


TOBB_BEVEZETO = [
    "A BKK közúti oldalán több új bejegyzést is láttam, ami minket érint:",
    "Egyszerre több helyen is változik a forgalom a környéken:",
    "Összeszedtem a friss korlátozásokat, amik a mi utainkat érintik:",
    "Több dologra is figyeljetek, ha mostanában erre jártok:",
]


def _esemeny_sorok(e):
    sorok = [f"📍 {e['cim']}"]
    if e["befejezes"]:
        sorok.append(f"🕐 {e['kezdes']} – {e['befejezes']}")
    else:
        sorok.append(f"🕐 Kezdete: {e['kezdes']}")
    return sorok


def poszt_szoveg(esemenyek):
    """Egy vagy több új esemény egyetlen posztban."""
    r = random.Random("|".join(e["id"] for e in esemenyek))
    bev = r.choice(BEVEZETOK if len(esemenyek) == 1 else TOBB_BEVEZETO)
    sorok = [r.choice(CIMEK), "", bev]
    for e in esemenyek:
        sorok += [""] + _esemeny_sorok(e)
    sorok += ["", r.choice(ZAROK), "", "Forrás: BKK Info (Közút)",
              "#Csepel #Pesterzsébet #közlekedés #lezárás"]
    return "\n".join(sorok)


def nemreg_latott_cim(allapot, cim, t):
    for v in allapot.values():
        if v.get("cim") != cim:
            continue
        try:
            if (t - datetime.fromisoformat(v["eloszor_latva"])).days < CIM_ISMETLES_NAP:
                return True
        except Exception:
            return True
    return False


def facebook_poszt(szoveg):
    if not MAKE_WEBHOOK_URL:
        print("  ⚠️  Nincs beállítva MAKE_WEBHOOK_URL - posztolás kihagyva.")
        return False
    try:
        resp = requests.post(MAKE_WEBHOOK_URL, json={"message": poszt_valtozatos.atrendez(szoveg)}, timeout=20)
        if resp.status_code == 200:
            print("  ✅ Facebook poszt elküldve.")
            return True
        print(f"  ⚠️  Facebook poszt sikertelen (HTTP {resp.status_code})")
    except Exception as ex:
        print(f"  ⚠️  Facebook poszt hiba: {type(ex).__name__}")
    return False


def main():
    szoveg, esemenyek = oldal_esemenyei()
    helyi = [e for e in esemenyek if kornyekbeli(e["cim"])]
    print(f"📊 Nem baleseti események: {len(esemenyek)}, ebből környékbeli: {len(helyi)}")

    if TESZT_MOD:
        print("═" * 60)
        print(szoveg[:6000])
        print("═" * 60)
        for e in esemenyek:
            print(("✅ " if kornyekbeli(e["cim"]) else "   ") + f"{e['cim']} | {e['kezdes']} - {e['befejezes']}")
        return

    elso_futas = not os.path.exists(ALLAPOT_FAJL)
    allapot = {}
    if not elso_futas:
        with open(ALLAPOT_FAJL, encoding="utf-8") as f:
            allapot = json.load(f)

    t = most()
    ujak = []
    for e in helyi:
        if e["id"] in allapot or any(u["id"] == e["id"] for u in ujak):
            continue
        if elso_futas:
            allapot[e["id"]] = {"cim": e["cim"], "eloszor_latva": t.isoformat(), "posztolva": False}
            continue
        if nemreg_latott_cim(allapot, e["cim"], t) or any(u["cim"] == e["cim"] for u in ujak):
            print(f"🔁 Már posztolt/ismert cím, kihagyva: {e['cim']}")
            allapot[e["id"]] = {"cim": e["cim"], "eloszor_latva": t.isoformat(), "posztolva": False}
            continue
        ujak.append(e)

    if ujak and ejszaka(t):
        print(f"🌙 Éjszaka van, {len(ujak)} új esemény reggelig vár.")
    elif ujak:
        for e in ujak:
            print(f"🆕 {e['cim']}")
        # Sürgős poszt, de két poszt között így is eltelik legalább 10 perc;
        # ha most nem mehet, az események nem kerülnek be, a következő futás küldi.
        if poszt_utem.mehet(surgos=True) and facebook_poszt(poszt_szoveg(ujak)):
            poszt_utem.jegyez()
            for e in ujak:
                allapot[e["id"]] = {"cim": e["cim"], "eloszor_latva": t.isoformat(), "posztolva": True}

    if elso_futas:
        print(f"ℹ️ Első futás: {len(allapot)} futó esemény megjegyezve, posztolás nélkül.")

    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
