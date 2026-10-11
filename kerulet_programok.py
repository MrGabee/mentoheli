"""
🎉 Kerületi programajánló
  - reggeli_szoveg: minden reggel a mai és a következő napok programjai
  - hetvegi_szoveg: pénteken a hétvégi programok (a Csili műsorával együtt)
"""

from datetime import timedelta

import kerulet_forrasok as forrasok
from poszt_valtozatos import Stilus

NAPOK = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]

# A reggeli poszt ennyi napot néz előre (a mai nappal együtt)
REGGELI_NAPOK = 7
# Egy posztban legfeljebb ennyi program, hogy ne legyen túl hosszú
MAX_PROGRAM = 10

HELY_JEL = {"Csepeli Munkásotthon": "🏛️", "Barba Negra": "🎸", "Csili": "🎭", "Müpa": "🎻", "Fedák": "🎭"}


def _jel(p):
    for nev, jel in HELY_JEL.items():
        if p["hely"].startswith(nev):
            return jel
    return "📍"


def _sor(p, napnevvel=True):
    nap = f"{p['nap'].strftime('%m.%d.')} {NAPOK[p['nap'].weekday()]}" if napnevvel else ""
    ido = f", {p['ido']}" if p["ido"] else ""
    return [f"{_jel(p)} {nap}{ido} – {p['cim']}".replace("  ", " ").replace(" , ", " "),
            f"   📍 {p['hely']}  🔗 {p['link']}"]


def reggeli_szoveg(ma, lista=None):
    """None = minden forrás hibás (később újrapróbálja), "" = nincs program."""
    if lista is None:
        lista, hibas = forrasok.programok(ma, ma + timedelta(days=REGGELI_NAPOK - 1))
        if len(hibas) == len(forrasok.FORRASOK):
            return None
    if not [p for p in lista if p["nap"] == ma or p.get("keruleti", True)]:
        return ""

    st = Stilus("programok", ma.isoformat())
    sorok = [st.cim, f"📅 {ma.strftime('%Y.%m.%d.')}, {NAPOK[ma.weekday()]}", st.vonal(), "", st.bevezeto, ""]
    mai = [p for p in lista if p["nap"] == ma]
    # A következő napokból csak a kerületi helyszínek (a Müpa csak aznap)
    kesobbi = [p for p in lista if p["nap"] != ma and p.get("keruleti", True)][:max(0, MAX_PROGRAM - len(mai))]
    if mai:
        sorok.append("⭐ MA")
        for p in mai:
            sorok += [s.replace(f"{p['nap'].strftime('%m.%d.')} {NAPOK[p['nap'].weekday()]}, ", "") for s in _sor(p)]
        sorok.append("")
    if kesobbi:
        sorok.append("🗓️ A KÖVETKEZŐ NAPOKBAN" if mai else "🗓️ A HÉTEN")
        for p in kesobbi:
            sorok += _sor(p)
        sorok.append("")
    sorok.append("🎟️ Jegyek és részletek a linkeken. Jó szórakozást!")
    if st.zaro:
        sorok.append(st.zaro)
    sorok.append("#Csepel #Soroksár #programajánló #BarbaNegra #Munkásotthon #Müpa")
    return "\n".join(sorok)


def _csili(pentek):
    """A Csili hétvégi műsora ugyanabban a formában. Hiba esetén üres."""
    try:
        import csili
        esemenyek = csili.esemenyek(pentek, pentek + timedelta(days=2)) or []
    except Exception as ex:
        print(f"  ❌ Csili: {ex}")
        return []
    return [{"cim": e["cim"], "nap": e["kezdes"].date(), "ido": e["kezdes"].strftime("%H:%M"),
             "hely": "Csili Művelődési Központ", "link": e["link"]} for e in esemenyek]


def hetvegi_szoveg(pentek, lista=None):
    if lista is None:
        lista, hibas = forrasok.programok(pentek, pentek + timedelta(days=2))
        lista = sorted(lista + _csili(pentek), key=lambda p: (p["nap"], p["ido"]))
    if not lista:
        return ""

    st = Stilus("hetvege", pentek.isoformat())
    vasarnap = pentek + timedelta(days=2)
    sorok = [st.cim, f"📅 {pentek.strftime('%m.%d.')} – {vasarnap.strftime('%m.%d.')}", st.vonal(), "",
             st.bevezeto, ""]
    for i in range(3):
        nap = pentek + timedelta(days=i)
        napi = [p for p in lista if p["nap"] == nap][:6]
        if not napi:
            continue
        sorok.append(f"▶️ {NAPOK[nap.weekday()].upper()} ({nap.strftime('%m.%d.')})")
        for p in napi:
            ido = f"{p['ido']} – " if p["ido"] else ""
            sorok.append(f"{_jel(p)} {ido}{p['cim']}")
            sorok.append(f"   📍 {p['hely']}  🔗 {p['link']}")
        sorok.append("")
    sorok.append("Ha elmentek valahova, írjátok meg, milyen volt! 😊")
    if st.zaro:
        sorok.append(st.zaro)
    sorok.append("#hétvége #programajánló #Csepel #Pesterzsébet")
    return "\n".join(sorok)
