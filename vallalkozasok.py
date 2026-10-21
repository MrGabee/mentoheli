"""
🏪 Helyi vállalkozások – heti bemutató és heti véleménykérés
- bemutato_szoveg: a vallalkozasok.json sorából a következő vállalkozás
  bemutatása (ha üres a sor, aznap nincs poszt). Új vállalkozást a fájl
  végére kell felvenni; Gábor vagy maga a vállalkozó küldheti be.
- velemeny_szoveg: hetente más szakmáról kérdezi az olvasókat, kit
  ajánlanak a kerületben. Konkrét céget nem nevez meg és nem minősít.
"""

import json
import os
from datetime import date

from poszt_valtozatos import Stilus

SOR_FAJL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vallalkozasok.json")

# (szakma a kérdésben, hashtag)
SZAKMAK = [
    ("pékséget", "pékség"),
    ("autószerelőt", "autószerelő"),
    ("fodrászt", "fodrász"),
    ("villanyszerelőt", "villanyszerelő"),
    ("vízvezeték-szerelőt", "vízszerelő"),
    ("cukrászdát", "cukrászda"),
    ("kozmetikust", "kozmetikus"),
    ("állatorvost", "állatorvos"),
    ("éttermet egy családi ebédhez", "étterem"),
    ("kávézót", "kávézó"),
    ("hentest, húsboltot", "hentes"),
    ("virágboltot", "virágbolt"),
    ("szobafestőt", "festő"),
    ("asztalost", "asztalos"),
    ("gumist", "gumiszerviz"),
    ("cipészt vagy kulcsmásolót", "cipész"),
    ("varrodát, ruhajavítót", "varroda"),
    ("kutyakozmetikust", "kutyakozmetika"),
    ("pizzériát", "pizza"),
    ("lakatost", "lakatos"),
    ("klímaszerelőt", "klíma"),
    ("könyvelőt", "könyvelő"),
    ("masszőrt", "masszázs"),
    ("műszerészt, telefonszervizt", "szerviz"),
    ("kertészt, kertgondozót", "kertész"),
    ("burkolót", "burkoló"),
    ("optikát", "optika"),
    ("zöldségest", "zöldséges"),
    ("edzőtermet", "edzőterem"),
    ("szabót vagy függönyvarrót", "szabó"),
]


def betolt():
    try:
        with open(SOR_FAJL, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def bemutato_szoveg(nap, allapot):
    """A következő, még be nem mutatott vállalkozás. "" = ma nincs kit bemutatni."""
    volt = allapot.setdefault("vallalkozas_volt", [])
    for v in betolt():
        if v["id"] in volt or date.fromisoformat(v.get("datum", "2000-01-01")) > nap:
            continue
        volt.append(v["id"])
        st = Stilus("vallalkozas", nap.isoformat())
        sorok = [st.cim, st.vonal(), "", st.bevezeto, "", f"🏷️ {v['nev']}"]
        if v.get("tevekenyseg"):
            sorok.append(f"🔧 {v['tevekenyseg']}")
        if v.get("cim"):
            sorok.append(f"📍 {v['cim']}")
        if v.get("nyitvatartas"):
            sorok.append(f"🕘 {v['nyitvatartas']}")
        if v.get("elerhetoseg"):
            sorok.append(f"📞 {v['elerhetoseg']}")
        if v.get("leiras"):
            sorok += ["", v["leiras"].strip()]
        sorok += [
            "",
            "💬 Jártatok már náluk? Írjátok meg kommentben a tapasztalatotokat!",
            "",
            "🤝 Csepeli vállalkozásod van? Várlak! Szívesen bemutatlak téged is, ingyen. Írj Messengeren, WhatsAppon (+36 70 754 0254), e-mailben (olvaso@mrgabee.hu), vagy jelentkezz az űrlapon: https://kozles.github.io/posztol/kapcsolat.html",
            "ℹ️ Ez nem fizetett hirdetés.",
        ]
        if st.zaro:
            sorok += ["", st.zaro]
        sorok.append(v.get("hashtagek") or "#Csepel #helyivállalkozás #vásároljhelyben")
        return "\n".join(sorok)
    return ""


def velemeny_szoveg(nap):
    """Heti kérdés: kit ajánlotok egy adott szakmában a kerületben?"""
    szakma, tag = SZAKMAK[(nap.toordinal() // 7) % len(SZAKMAK)]
    st = Stilus("vallalkozas_velemeny", nap.isoformat())
    sorok = [
        st.cim, st.vonal(), "", st.bevezeto, "",
        f"❓ Kit vagy melyik helyet ajánlanátok jó szívvel, ha valaki {szakma} keres Csepelen vagy a környéken?",
        "",
        "👇 Írjátok meg kommentben a nevét, és hogy miért ajánljátok! A legjobb ajánlásokból később bemutatót is készítek.",
        "",
        "🙏 Egy kérés: ajánljunk, ne szidjunk. Ha rossz tapasztalatotok volt, azt inkább magánüzenetben írjátok meg nekem.",
    ]
    if st.zaro:
        sorok += ["", st.zaro]
    sorok.append(f"#Csepel #helyivállalkozás #ajánló #{tag}")
    return "\n".join(sorok)


# Egyszeri rovatindító poszt (2026.10.19. hétfő 13:40)
BEJELENTO_NAP = date(2026, 10, 19)
BEJELENTO = """🏪 ÚJ ROVAT: CSEPELI VÁLLALKOZÁSOK 🏪

Új rovatot indítok, és ehhez a ti segítségetekre is szükségem van!

Szeretném, ha jobban megismernénk azokat, akik itt dolgoznak a környéken: a sarki péket, a megbízható szerelőt, a fodrászt, a kis családi boltot. Szerintem sokszor nem is tudjuk, milyen jó helyek vannak tőlünk pár utcányira.

🤝 Vállalkozó vagy Csepelen vagy a környéken? Jelentkezz, és szívesen bemutatlak, teljesen ingyen! Így érsz el:
💬 Messenger: írj az oldalnak üzenetet
📱 WhatsApp: +36 70 754 0254
✉️ E-mail: olvaso@mrgabee.hu
📝 Űrlap („Vállalkozás bemutatása” menüpont): https://kozles.github.io/posztol/kapcsolat.html

Ismersz egy jó helyi vállalkozást? Írd meg kommentben, és lehet, hogy hamarosan ők is bemutatkoznak!

#Csepel #helyivállalkozás #vásároljhelyben #újrovat"""


def bejelento_szoveg(nap):
    return BEJELENTO if nap == BEJELENTO_NAP else ""


if __name__ == "__main__":
    ma = date.today()
    print(velemeny_szoveg(ma))
    print("═" * 40)
    print(bemutato_szoveg(ma, {}) or "(üres a bemutató sor)")
