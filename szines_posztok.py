"""
🌈 Színes posztok – egész napra elosztva, az áramszünetes és egyéb
értesítések mellé, hogy az oldal változatosabb legyen.

Napi menetrend (helyi idő, nyári/téli időszámítással): a MENETREND lista.
A posztok nem kerek órákra, hanem a szomszédaik közé, nagyjából félútra
esnek; a tényleges kiküldés a következő futáskor (:10 vagy :40) történik.

A workflow félóránként fut. Minden poszt a saját időpontja után, legfeljebb
KESES_ORA órán belül megy ki, naponta egyszer (szines_allapot.json), és
futásonként legfeljebb egy, hogy ne egyszerre jöjjenek.
"""

import os
import json
import requests
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import idojaras_riasztas_monitor as kuldo
import kerulet_programok
import reggeli_osszefoglalo
import ezen_a_napon
import csepeli_emlekezes
import csepeli_erdekesseg
import kerdes_nektek
import esti_idojaras
import veradas
import allasok
import hivatali_hirek
import otlet_keres
import kerulet_problema
import olvasoi_level
import csepeli_sport
import vallalkozasok
import egyszeri_posztok
import poszt_valtozatos

MAGYAR_TZ = ZoneInfo("Europe/Budapest")

# ⬇️⬇️⬇️ ITT KAPCSOLOD KI/BE AZ AUTOMATA FACEBOOK-POSZTOLÁST ⬇️⬇️⬇️
FACEBOOK_POSZTOLAS_AKTIV = True

ALLAPOT_FAJL = "szines_allapot.json"

# Ha külön Make-webhook van a színes posztokhoz (MAKE_WEBHOOK_URL_SZINES),
# azon mennek ki, különben a megszokott MAKE_WEBHOOK_URL-en.
SZINES_WEBHOOK = os.environ.get("MAKE_WEBHOOK_URL_SZINES", "")
if SZINES_WEBHOOK:
    kuldo.MAKE_WEBHOOK_URL = SZINES_WEBHOOK

# Minden poszt végére: gyors kapcsolatfelvétel (ahol nincs már benne),
# posztonként más megfogalmazással
def kapcsolat_sor(nap, kulcs):
    return poszt_valtozatos.rovid_kapcsolat(nap, kulcs, allasok.OLVASOI_EMAIL,
                                            "+36 70 754 0254", allasok.KAPCSOLAT_URL)
KAPCSOLAT_NELKUL = {"rovat_vallalkozas", "vallalkozas", "vallalkozas_20261022", "olvasoi_level_20261022", "kaszkador_20261023", "heimpal_20261023", "oraallitas_20261025", "csepeli_emlekezes", "allasok", "otlet_keres", "olvasoi_level", "kerulet_problema"}

# Ezekhez a posztokhoz kép is megy (a Make letölti és fotós posztként teszi ki)
KEP_ALAP = "https://raw.githubusercontent.com/MrGabee/mentoheli/main/kepek/"
KEPEK = {"otlet_keres": KEP_ALAP + "otlet_keres.png"}


def kepes_poszt_kuldese(szoveg, kep_url):
    """Képes poszt a színes posztok Make-forgatókönyvén ("kep" mező)."""
    if not kuldo.MAKE_WEBHOOK_URL:
        print("  ⚠️  Nincs beállítva a Make webhook - Facebook-posztolás kihagyva.")
        return False
    try:
        resp = requests.post(kuldo.MAKE_WEBHOOK_URL, json={"message": poszt_valtozatos.atrendez(szoveg), "kep": kep_url}, timeout=60)
    except Exception as e:
        print(f"  ⚠️  Facebook poszt hiba: {e}")
        return False
    if resp.status_code != 200:
        print(f"  ⚠️  Facebook poszt sikertelen (HTTP {resp.status_code}): {resp.text[:300]}")
        return False
    print("  ✅ Képes Facebook poszt elküldve (Make.com-on keresztül).")
    return True


# Ha a GitHub késve indítja a futást, ennyi órán belül még kimegy a poszt
KESES_ORA = 2

HETFO = 0
KEDD = 1
SZERDA = 2
CSUTORTOK = 3
SZOMBAT = 5
PENTEK = 4
VASARNAP = 6

# (kulcs, időpont, csak ezeken a napokon [0=hétfő] vagy None, szöveg(nap, allapot))
# Holnapi véradás: 2026.10.16-án kivételesen 20:00-kor, egyébként 19:35-kor
VERADAS_IDO = time(20, 0) if datetime.now(MAGYAR_TZ).strftime("%Y-%m-%d") == "2026-10-16" else time(19, 35)

MENETREND = [
    ("reggeli",       time(5, 50),  None,     lambda nap, a: reggeli_osszefoglalo.szoveg(nap)),
    ("otlet_keres",   time(7, 15),  None,     lambda nap, a: otlet_keres.szoveg(nap)),
    ("programok",     time(8, 5),   None,     lambda nap, a: kerulet_programok.reggeli_szoveg(nap)),
    ("ezen_a_napon",  time(10, 20), None,     lambda nap, a: ezen_a_napon.szoveg(nap)),
    ("csepeli_emlekezes", time(9, 50), None,  lambda nap, a: csepeli_emlekezes.szoveg(nap)),
    ("olvasoi_level", time(14, 30),  None,     lambda nap, a: "" if nap.isoformat() == "2026-10-22" else olvasoi_level.szoveg(nap, a)),
    ("olvasoi_level_20261022", time(17, 35), {CSUTORTOK}, lambda nap, a: olvasoi_level.szoveg(nap, a) if nap.isoformat() == "2026-10-22" else ""),
    ("erdekesseg",    time(12, 50),  None,     lambda nap, a: csepeli_erdekesseg.szoveg(nap, a.setdefault("erdekesseg_volt", []))),
    ("hivatali",      time(11, 35), None,     lambda nap, a: hivatali_hirek.szoveg(nap, a)),
    ("sport_eredmeny", time(9, 15),  {HETFO},  lambda nap, a: csepeli_sport.eredmeny_szoveg(nap)),
    ("sport_elozetes", time(15, 35), {PENTEK}, lambda nap, a: csepeli_sport.elozetes_szoveg(nap)),
    ("veradas",       time(15, 35),  {HETFO},  lambda nap, a: veradas.heti_szoveg(nap)),
    ("allasok",       time(15, 35),  {KEDD, CSUTORTOK, SZOMBAT}, lambda nap, a: allasok.heti_szoveg(nap, a)),
    ("sport_hetkoz",  time(16, 5),   None,     lambda nap, a: csepeli_sport.hetkoznapi_szoveg(nap)),
    ("hetvege",       time(16, 35),  {PENTEK}, lambda nap, a: kerulet_programok.hetvegi_szoveg(nap)),
    ("kerulet_problema", time(17, 35), None, lambda nap, a: kerulet_problema.szoveg(nap)),
    ("kerdes",        time(18, 35),  None,     lambda nap, a: kerdes_nektek.szoveg(nap)),
    ("vallalkozas",   time(13, 25),  {SZERDA}, lambda nap, a: vallalkozasok.bemutato_szoveg(nap, a)),
    ("rovat_vallalkozas", time(13, 40), {HETFO}, lambda nap, a: vallalkozasok.bejelento_szoveg(nap)),
    ("bkk_soroksar", time(15, 5), {HETFO}, lambda nap, a: egyszeri_posztok.szoveg("bkk_soroksar", nap)),
    # Csak kézi indításra (üres napkészlet: ütemezve sosem megy ki)
    ("bombariado", time(0, 0), set(), lambda nap, a: egyszeri_posztok.szoveg("bombariado", nap)),
    ("ecofamily", time(15, 5), {SZERDA}, lambda nap, a: egyszeri_posztok.szoveg("ecofamily", nap)),
    ("vallalkozas_20261022", time(13, 25), {CSUTORTOK}, lambda nap, a: vallalkozasok.bemutato_szoveg(nap, a) if nap.isoformat() == "2026-10-22" else ""),
    ("heimpal_20261023", time(0, 0), set(), lambda nap, a: egyszeri_posztok.szoveg("heimpal_20261023", nap)),
    ("oraallitas_20261025", time(7, 25), {VASARNAP}, lambda nap, a: egyszeri_posztok.szoveg("oraallitas_20261025", nap)),
    ("kaszkador_20261023", time(13, 25), {PENTEK}, lambda nap, a: egyszeri_posztok.szoveg("kaszkador_20261023", nap)),
    ("hev_ajto_20261022", time(0, 0), set(), lambda nap, a: egyszeri_posztok.szoveg("hev_ajto_20261022", nap)),
    ("bankkartya_20261022", time(0, 0), set(), lambda nap, a: egyszeri_posztok.szoveg("bankkartya_20261022", nap)),
    ("busz159_20261022", time(0, 0), set(), lambda nap, a: egyszeri_posztok.szoveg("busz159_20261022", nap)),
    ("dugo_20261021", time(0, 0), set(), lambda nap, a: egyszeri_posztok.szoveg("dugo_20261021", nap)),
    ("dugo_20261027", time(0, 0), set(), lambda nap, a: egyszeri_posztok.szoveg("dugo_20261027", nap)),
    ("vallalkozas_velemeny", time(11, 5), {VASARNAP}, lambda nap, a: vallalkozasok.velemeny_szoveg(nap)),
    ("veradas_holnap", VERADAS_IDO, None,     lambda nap, a: veradas.emlekezteto_szoveg(nap)),
    ("esti_idojaras", time(20, 30), None,     lambda nap, a: esti_idojaras.szoveg(nap)),
]


def betolt_allapot():
    try:
        with open(ALLAPOT_FAJL, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def ment_allapot(allapot):
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=2)


# Csendes időszakok (helyi idő): ilyenkor nem megy ki színes poszt, mert Gábor
# kézzel tesz ki valamit; az esedékes poszt utána, a KESES_ORA-n belül megy ki.
CSENDES_IDOSZAKOK = [
    ("2026-10-17 20:10", "2026-10-17 20:55"),  # megosztott bejegyzés 20:30-kor
]


# Dinamikus csendes ablak: a Facebook-oldal figyelő állítja be egy fontos
# megosztás után, hogy legyen ideje lecsengeni (fb_oldal_figyelo.py).
CSENDES_FAJL = "csendes_ablak.json"


def csendes(most):
    t = most.strftime("%Y-%m-%d %H:%M")
    if any(tol <= t < ig for tol, ig in CSENDES_IDOSZAKOK):
        return True
    try:
        with open(CSENDES_FAJL, encoding="utf-8") as f:
            return t < json.load(f).get("ig", "")
    except Exception:
        return False


def esedekes(most, allapot):
    """A most kimenő posztok kulcsai, időrendben."""
    ma = most.date().isoformat()
    if csendes(most):
        return []
    lista = []
    for kulcs, ido, napok, _ in MENETREND:
        if napok is not None and most.weekday() not in napok:
            continue
        kezd = datetime.combine(most.date(), ido, MAGYAR_TZ)
        if kezd <= most < kezd + timedelta(hours=KESES_ORA) and allapot.get("kiment", {}).get(kulcs) != ma:
            lista.append(kulcs)
    return lista


def main():
    most = datetime.now(MAGYAR_TZ)
    if os.environ.get("KENYSZERITETT"):          # kézi indítás: egy adott poszt azonnal
        most_kulcsok = [os.environ["KENYSZERITETT"]]
    else:
        most_kulcsok = None
    print(f"🌈 Színes posztok – {most.strftime('%Y.%m.%d %H:%M:%S')}")

    allapot = betolt_allapot()
    kulcsok = most_kulcsok or esedekes(most, allapot)
    if not kulcsok:
        print("⏭️ Most nincs esedékes poszt.")
        return

    kulcs = kulcsok[0]
    keszito = next(m[3] for m in MENETREND if m[0] == kulcs)
    szoveg = keszito(most.date(), allapot)
    if szoveg is None:
        print(f"⚠️ {kulcs}: a forrás most nem elérhető, a következő futás újrapróbálja.")
        return

    if szoveg == "":
        print(f"ℹ️ {kulcs}: ma nincs miről írni, kihagyva.")
    else:
        if kulcs not in KAPCSOLAT_NELKUL:
            szoveg += "\n\n" + kapcsolat_sor(most.date(), kulcs)
        print("\n" + szoveg + "\n")
        if not FACEBOOK_POSZTOLAS_AKTIV:
            print("ℹ️ Facebook-posztolás kikapcsolva.")
        elif not (kepes_poszt_kuldese(szoveg, KEPEK[kulcs]) if kulcs in KEPEK
                  else kuldo.facebook_poszt_kuldese(szoveg)):
            return  # sikertelen küldés: a következő futás újrapróbálja

    if not most_kulcsok:
        allapot.setdefault("kiment", {})[kulcs] = most.date().isoformat()
    ment_allapot(allapot)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
