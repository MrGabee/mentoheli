"""
🌈 Színes posztok – egész napra elosztva, az áramszünetes és egyéb
értesítések mellé, hogy az oldal változatosabb legyen.

Napi menetrend (helyi idő, nyári/téli időszámítással):
  08:00  🎉 Kerületi programajánló (Munkásotthon, Barba Negra, …)
  10:30  📜 Ezen a napon történt
  13:00  🏛️ Környékbeli érdekesség (helytörténet)
  15:00  🩸 Heti véradás-ajánló – csak hétfőn
  16:00  🥳 Hétvégi programajánló – csak pénteken
  18:00  💬 Kérdés nektek
  19:00  ⏰ Véradás-emlékeztető – csak ha holnap kitelepült véradás van
  20:30  🌙 Holnapi időjárás

A workflow félóránként fut. Minden poszt a saját időpontja után, legfeljebb
KESES_ORA órán belül megy ki, naponta egyszer (szines_allapot.json), és
futásonként legfeljebb egy, hogy ne egyszerre jöjjenek.
"""

import os
import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import idojaras_riasztas_monitor as kuldo
import kerulet_programok
import reggeli_osszefoglalo
import ezen_a_napon
import csepeli_erdekesseg
import kerdes_nektek
import esti_idojaras
import veradas
import allasok
import hivatali_hirek

MAGYAR_TZ = ZoneInfo("Europe/Budapest")

# ⬇️⬇️⬇️ ITT KAPCSOLOD KI/BE AZ AUTOMATA FACEBOOK-POSZTOLÁST ⬇️⬇️⬇️
FACEBOOK_POSZTOLAS_AKTIV = True

ALLAPOT_FAJL = "szines_allapot.json"

# Ha külön Make-webhook van a színes posztokhoz (MAKE_WEBHOOK_URL_SZINES),
# azon mennek ki, különben a megszokott MAKE_WEBHOOK_URL-en.
SZINES_WEBHOOK = os.environ.get("MAKE_WEBHOOK_URL_SZINES", "")
if SZINES_WEBHOOK:
    kuldo.MAKE_WEBHOOK_URL = SZINES_WEBHOOK

# Ha a GitHub késve indítja a futást, ennyi órán belül még kimegy a poszt
KESES_ORA = 2

HETFO = 0
SZERDA = 2
PENTEK = 4

# (kulcs, időpont, csak ezeken a napokon [0=hétfő] vagy None, szöveg(nap, allapot))
MENETREND = [
    ("reggeli",       time(6, 30),  None,     lambda nap, a: reggeli_osszefoglalo.szoveg(nap)),
    ("programok",     time(8, 0),   None,     lambda nap, a: kerulet_programok.reggeli_szoveg(nap)),
    ("ezen_a_napon",  time(10, 30), None,     lambda nap, a: ezen_a_napon.szoveg(nap)),
    ("erdekesseg",    time(13, 0),  None,     lambda nap, a: csepeli_erdekesseg.szoveg(nap, a.setdefault("erdekesseg_volt", []))),
    ("hivatali",      time(11, 45), None,     lambda nap, a: hivatali_hirek.szoveg(nap, a)),
    ("veradas",       time(15, 0),  {HETFO},  lambda nap, a: veradas.heti_szoveg(nap)),
    ("allasok",       time(15, 0),  {SZERDA}, lambda nap, a: allasok.heti_szoveg(nap, a)),
    ("hetvege",       time(16, 0),  {PENTEK}, lambda nap, a: kerulet_programok.hetvegi_szoveg(nap)),
    ("kerdes",        time(18, 0),  None,     lambda nap, a: kerdes_nektek.szoveg(nap)),
    ("veradas_holnap", time(19, 0), None,     lambda nap, a: veradas.emlekezteto_szoveg(nap)),
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


def esedekes(most, allapot):
    """A most kimenő posztok kulcsai, időrendben."""
    ma = most.date().isoformat()
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
        print("\n" + szoveg + "\n")
        if not FACEBOOK_POSZTOLAS_AKTIV:
            print("ℹ️ Facebook-posztolás kikapcsolva.")
        elif not kuldo.facebook_poszt_kuldese(szoveg):
            return  # sikertelen küldés: a következő futás újrapróbálja

    if not most_kulcsok:
        allapot.setdefault("kiment", {})[kulcs] = most.date().isoformat()
    ment_allapot(allapot)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
