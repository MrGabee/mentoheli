"""
☀️ Reggeli összefoglaló – Csepel (XXI.) + Pesterzsébet (XX.) + Szigetszentmiklós
Minden reggel egy Facebook poszt arról, ami aznap érinti a környéket:
  ⚡ aznapi áramszünetek  (aramszunet_aktiv.json, az áramszünet-figyelő írja)
  💧 vízhiányok           (vizmuvek.hu munkatérkép, élő lekérdezés)
  ⚠️ időjárási riasztások (MeteoAlarm / HungaroMet)
  🎂 a napi névnap
Minden nap posztol; ha nincs zavar, azt is megírja.
"""

import os
import json
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

# A vízműves modul betöltéskor e-mail beállításokat vár - itt nem
# küldünk e-mailt, ezért üres alapértéket kap, ha nincs megadva.
for _valtozo in ("EMAIL_KULDO", "EMAIL_JELSZO", "EMAIL_CIMZETT_ARAM"):
    os.environ.setdefault(_valtozo, "")

import idojaras_riasztas_monitor as riasztas
import vizmuvek_monitor as vizmuvek
from poszt_valtozatos import Stilus
from nevnap import nevnap

# Valódi budapesti időzóna, nyári/téli időszámítással
MAGYAR_TZ = ZoneInfo("Europe/Budapest")

# A poszt helyi idő szerint ekkor megy ki, egész évben
KULDES_IDEJE = time(6, 30)

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


# ⬇️⬇️⬇️ ITT KAPCSOLOD KI/BE AZ AUTOMATA FACEBOOK-POSZTOLÁST ⬇️⬇️⬇️
FACEBOOK_POSZTOLAS_AKTIV = True

ARAMSZUNET_FAJL = "aramszunet_aktiv.json"

TERULET_SORREND = ["XXI. kerület (Csepel)", "XX. kerület (Pesterzsébet)", "Szigetszentmiklós"]


# ════════════════════════════════════════════
#  ⚡  ÁRAMSZÜNETEK MA
# ════════════════════════════════════════════
def mai_aramszunetek(ma):
    try:
        with open(ARAMSZUNET_FAJL, encoding="utf-8") as f:
            esemenyek = json.load(f).get("esemenyek", [])
    except Exception as ex:
        print(f"  ⚠️ Áramszünet-fájl nem olvasható: {ex}")
        return []
    return [e for e in esemenyek if (e.get("kezdes") or "").startswith(ma)]

def utca_nevek(esemeny, max_db=4):
    """'Budapest XXI. Rakéta utca 10' → 'Rakéta utca', ismétlések nélkül."""
    nevek = []
    for cim in esemeny.get("utcak_lista") or []:
        szavak = cim.split()
        # Település és kerület levágása, házszám elhagyása
        while szavak and (szavak[0] in ("Budapest", "Szigetszentmiklós") or szavak[0].endswith(".")):
            szavak = szavak[1:]
        while szavak and (any(ch.isdigit() for ch in szavak[-1]) or szavak[-1].startswith("/")):
            szavak = szavak[:-1]
        nev = " ".join(szavak)
        if nev and nev not in nevek:
            nevek.append(nev)
    if len(nevek) > max_db:
        return ", ".join(nevek[:max_db]) + f" és még {len(nevek) - max_db}"
    return ", ".join(nevek)


# ════════════════════════════════════════════
#  💧  VÍZHIÁNYOK
# ════════════════════════════════════════════
def vizhianyok():
    esetek = vizmuvek.lekerdez()
    return [e for e in esetek if e["tipus"] in ("geo_0", "geo_1")]


# ════════════════════════════════════════════
#  ⚠️  RIASZTÁSOK MA
# ════════════════════════════════════════════
def mai_riasztasok(ma):
    """Ami legkésőbb ma kezdődik és még érvényes (a lejártakat a lekérdezés kiszűri)."""
    mai = []
    for r in riasztas.lekerdez() or []:
        kezdet = riasztas._ido(r["kezdet"])
        if kezdet and kezdet.astimezone(MAGYAR_TZ).strftime("%Y-%m-%d") <= ma:
            mai.append(r)
    return mai


# ════════════════════════════════════════════
#  📘  POSZT SZÖVEG
# ════════════════════════════════════════════
def facebook_szoveg(aram, viz, idojaras):
    st = Stilus("reggeli")
    sorok = [
        st.cim,
        f"📅 Mai helyzet – {magyar_ido().strftime('%Y.%m.%d.')}",
        st.vonal(),
        "",
        st.bevezeto,
        "",
    ]

    nevek = nevnap(magyar_ido().date())
    if nevek:
        sorok += [f"🎂 Ma {nevek} napja van, boldog névnapot kívánok! 🌷", ""]

    if idojaras:
        sorok.append("⚠️ IDŐJÁRÁSI RIASZTÁS")
        for r in sorted(idojaras, key=lambda x: -x["szint"]):
            sjel, snev = riasztas.SZINT_NEV.get(r["szint"], ("⚠️", ""))
            tjel, tnev = riasztas.TIPUS_NEV.get(r["tipus"], ("⚠️", r["esemeny"]))
            sorok.append(f"{sjel} {r['terulet']}: {tjel} {tnev}, {riasztas.ido_szoveg(r['kezdet'])} – {riasztas.ido_szoveg(r['lejar'])}")
        sorok.append("")

    if aram:
        sorok.append(f"⚡ ÁRAMSZÜNET MA ({len(aram)} db)")
        for terulet in TERULET_SORREND:
            for e in (x for x in aram if x.get("kerulet") == terulet):
                tol = (e.get("kezdes") or "")[11:16]
                ig  = (e.get("veg") or "")[11:16]
                sorok.append(f"📍 {terulet}: {utca_nevek(e)} ({tol}–{ig})")
        sorok.append("")

    if viz:
        sorok.append(f"💧 VÍZHIÁNY ({len(viz)} helyszín)")
        for terulet in TERULET_SORREND:
            helyek = [e for e in viz if e["terulet"] == terulet]
            if not helyek:
                continue
            cimek = ", ".join(e["cim"] for e in helyek[:4])
            if len(helyek) > 4:
                cimek += f" és még {len(helyek) - 4}"
            sorok.append(f"📍 {terulet}: {cimek}")
        sorok.append("")

    if not (idojaras or aram or viz):
        sorok += ["✅ Ma nem tudok áramszünetről, vízhiányról vagy időjárási riasztásról a környéken. Nyugis napot! 😊", ""]

    sorok += [
        "ℹ️ Részletek a korábbi posztjaimban. Források: E.ON, Fővárosi Vízművek, HungaroMet",
    ]
    if st.zaro:
        sorok.append(st.zaro)
    sorok.append("#Csepel #Pesterzsébet #Szigetszentmiklós #reggeli")
    return "\n".join(sorok)


# ════════════════════════════════════════════
#  ▶️  FŐPROGRAM
# ════════════════════════════════════════════
def most_kell_futni(utemezes):
    """A workflow két UTC-időpontban indul (04:30 és 05:30), mert a GitHub
    nem ismeri az óraátállítást. Ez kiválasztja, melyik felel meg aznap
    a helyi 6:30-nak: nyáron a 04:30 UTC, télen az 05:30 UTC.
    Kézi indításnál (nincs ütemezés) mindig fut."""
    if not utemezes:
        return True
    perc, ora = utemezes.split()[:2]
    cel = datetime.combine(magyar_ido().date(), KULDES_IDEJE, MAGYAR_TZ).astimezone(timezone.utc)
    return int(ora) == cel.hour and int(perc) == cel.minute


def szoveg(nap):
    """A színes posztok menetrendjéből (6:30) hívva: a nap összefoglalója."""
    ma = nap.strftime("%Y-%m-%d")
    return facebook_szoveg(mai_aramszunetek(ma), vizhianyok(), mai_riasztasok(ma))


def main():
    print(f"\n{'='*55}")
    print(f"☀️ Reggeli összefoglaló – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    if not most_kell_futni(os.environ.get("UTEMEZES", "")):
        print("⏭️ Ez az időpont most nem 6:30 helyi idő szerint (óraátállítás) - kihagyva.")
        return

    ma = magyar_ido().strftime("%Y-%m-%d")
    aram     = mai_aramszunetek(ma)
    viz      = vizhianyok()
    idojaras = mai_riasztasok(ma)
    print(f"⚡ {len(aram)}  💧 {len(viz)}  ⚠️ {len(idojaras)}")

    szoveg = facebook_szoveg(aram, viz, idojaras)
    print("\n" + szoveg + "\n")

    if not FACEBOOK_POSZTOLAS_AKTIV:
        print("ℹ️ Facebook-posztolás kikapcsolva.")
        return
    riasztas.facebook_poszt_kuldese(szoveg)
    print("✅ Kész.\n")


if __name__ == "__main__":
    main()
