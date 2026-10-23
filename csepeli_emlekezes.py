"""
🕯️ Csepeli évfordulók – csepeli kötődésű emberek születés- és halálnapjai
Forrás: a magyar Wikipédia
  - a Kategória:Csepeliek (és alkategóriái) szócikkei
  - azok a szócikkek, amelyek bevezetőjében Csepel a születés vagy a halál helye
A bevezető zárójeléből olvassa ki a dátumokat:
  „Név (Csepel, 1931. május 5. – Budapest, 2001. október 23.) magyar …”
Ha egy nap senkinek nincs évfordulója, nincs poszt.
Kézzel is felvehetők emberek (KEZI), ha a Wikipédiában nincsenek fent.

Kézi próba (nem posztol): python csepeli_emlekezes.py [ÉÉÉÉ-HH-NN]
"""

import re
import sys
import random
import requests
from datetime import date, datetime
from zoneinfo import ZoneInfo

from ezen_a_napon import wiki_tiszta

MAGYAR_TZ = ZoneInfo("Europe/Budapest")
API = "https://hu.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "mentoheli/1.0 (https://github.com/MrGabee/mentoheli)"}

KATEGORIAK = ["Kategória:Csepeliek"]
KATEGORIA_MELYSEG = 2
KERESESEK = [r'insource:/\(Csepel, \[*[0-9]{4}/', r'insource:/– *\[*Csepel\]*, \[*[0-9]{4}/']
MAX_OLDAL = 1500
MAX_SZEMELY = 3
# Politikáról nem írok, így a politikusok kimaradnak
POLITIKA = re.compile(r"politikus|polgármester|képviselő|államtitkár|miniszter|pártfőtitkár|párttitkár", re.I)

HONAPOK = ["január", "február", "március", "április", "május", "június", "július",
           "augusztus", "szeptember", "október", "november", "december"]
DATUM = re.compile(r"(\d{3,4})\.\s*(" + "|".join(HONAPOK) + r")\s+(\d{1,2})\.")

# Kézzel felvett emberek: {"nev", "szuletett": date|None, "elhunyt": date|None,
#  "leiras": "magyar …", "kotodes": "Csepelen élt"}
KEZI = []


def _api(params):
    r = requests.get(API, headers=HEADERS, timeout=30, params=dict(params, format="json", formatversion=2))
    r.raise_for_status()
    return r.json()


def kategoria_oldalai(kategoria, melyseg, latott_kat):
    oldalak = set()
    folytat = {}
    while True:
        adat = _api(dict({"action": "query", "list": "categorymembers", "cmtitle": kategoria,
                          "cmtype": "page|subcat", "cmlimit": 500}, **folytat))
        for t in adat.get("query", {}).get("categorymembers", []):
            if t["ns"] == 0:
                oldalak.add(t["title"])
            elif t["ns"] == 14 and melyseg > 0 and t["title"] not in latott_kat:
                latott_kat.add(t["title"])
                oldalak |= kategoria_oldalai(t["title"], melyseg - 1, latott_kat)
        if "continue" not in adat:
            return oldalak
        folytat = adat["continue"]


def kereses_oldalai(kifejezes):
    oldalak, offset = set(), 0
    while offset is not None and offset < 1000:
        adat = _api({"action": "query", "list": "search", "srsearch": kifejezes,
                     "srnamespace": 0, "srlimit": 500, "sroffset": offset})
        oldalak |= {t["title"] for t in adat.get("query", {}).get("search", [])}
        offset = adat.get("continue", {}).get("sroffset")
    return oldalak


def jeloltek():
    oldalak, kat_oldalak = set(), set()
    for k in KATEGORIAK:
        try:
            kat_oldalak |= kategoria_oldalai(k, KATEGORIA_MELYSEG, {k})
        except Exception as ex:
            print(f"  ❌ {k}: {ex}")
    oldalak |= kat_oldalak
    for k in KERESESEK:
        try:
            oldalak |= kereses_oldalai(k)
        except Exception as ex:
            print(f"  ❌ keresés {k}: {ex}")
    print(f"  🔎 {len(kat_oldalak)} oldal a kategóriákból, összesen {len(oldalak)} jelölt")
    return sorted(oldalak)[:MAX_OLDAL], kat_oldalak


def bevezetok(cimek):
    """{cím: a szócikk bevezetője sima szövegként}"""
    eredmeny = {}
    for i in range(0, len(cimek), 50):
        adat = _api({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                     "titles": "|".join(cimek[i:i + 50]), "redirects": 1})
        for o in adat.get("query", {}).get("pages", []):
            rev = (o.get("revisions") or [{}])[0]
            tartalom = rev.get("slots", {}).get("main", {}).get("content", "")
            eleje = re.split(r"^==", tartalom, maxsplit=1, flags=re.M)[0]
            eleje = re.sub(r"^\s*\{\{.*?^\}\}", "", eleje, flags=re.S | re.M)   # infobox
            eredmeny[o["title"]] = wiki_tiszta(eleje)
    return eredmeny


def _datum(m):
    try:
        return date(int(m.group(1)), HONAPOK.index(m.group(2)) + 1, int(m.group(3)))
    except ValueError:
        return None


def feldolgoz(cim, bevezeto, kategoriabol=False):
    """Egy szócikk bevezetőjéből: {nev, szuletett, elhunyt, leiras, kotodes} vagy None."""
    nev = re.sub(r"\s*\(.*\)$", "", cim)
    z = re.search(r"\(([^()]*\d{3,4}\.[^()]*)\)", bevezeto[:600])
    if not z:
        return None
    zarojel = z.group(1)
    reszek = re.split(r"\s+[–-]\s+", zarojel, maxsplit=1)
    szul_m = DATUM.search(reszek[0])
    hal_m = DATUM.search(reszek[1]) if len(reszek) > 1 else None
    szuletett = _datum(szul_m) if szul_m else None
    elhunyt = _datum(hal_m) if hal_m else None
    if not (szuletett or elhunyt):
        return None
    csepelen_szul = "Csepel" in reszek[0]
    csepelen_hal = len(reszek) > 1 and "Csepel" in reszek[1]
    if not (kategoriabol or csepelen_szul or csepelen_hal):
        return None
    kotodes = ("Csepelen született" if csepelen_szul else
               "Csepelen hunyt el" if csepelen_hal else "csepeli kötődésű")
    utana = bevezeto[z.end():].strip(" ,")
    leiras = re.split(r"(?<=[a-zá-űé\)])\.\s", utana, maxsplit=1)[0].strip().rstrip(".")
    if POLITIKA.search(leiras):
        return None
    if len(leiras) > 220:
        leiras = leiras[:220].rsplit(" ", 1)[0] + "…"
    return {"nev": nev, "szuletett": szuletett, "elhunyt": elhunyt, "leiras": leiras,
            "kotodes": kotodes, "link": "https://hu.wikipedia.org/wiki/" + cim.replace(" ", "_")}


def szemelyek():
    cimek, kat = jeloltek()
    if not cimek:
        return None
    lista = []
    for cim, bev in bevezetok(cimek).items():
        sz = feldolgoz(cim, bev, cim in kat)
        if sz:
            lista.append(sz)
    print(f"  🕯️ {len(lista)} csepeli kötődésű ember dátummal")
    return lista + KEZI


def evfordulok(nap, lista):
    """[(ember, 'szuletes'|'halal', évek száma)] a mai napra."""
    talalat = []
    for sz in lista:
        for fajta, d in (("halal", sz.get("elhunyt")), ("szuletes", sz.get("szuletett"))):
            if d and (d.month, d.day) == (nap.month, nap.day) and d.year < nap.year:
                talalat.append((sz, fajta, nap.year - d.year))
    rnd = random.Random(f"csepeli_emlekezes|{nap}")
    rnd.shuffle(talalat)
    # A kerek évfordulók előre, aztán a halálozási évfordulók
    talalat.sort(key=lambda t: (t[2] % 10 != 0, t[2] % 5 != 0, t[1] != "halal"))
    latott, valogatott = set(), []
    for t in talalat:
        if t[0]["nev"] not in latott:
            latott.add(t[0]["nev"])
            valogatott.append(t)
    return valogatott[:MAX_SZEMELY]


def _bekezdes(sz, fajta, ev, nap):
    d = sz["elhunyt"] if fajta == "halal" else sz["szuletett"]
    datum = f"{d.year}. {HONAPOK[d.month - 1]} {d.day}."
    leiras = f", {sz['leiras']}" if sz["leiras"] else ""
    if fajta == "halal":
        elet = f" ({sz['szuletett'].year}–{d.year})" if sz.get("szuletett") else ""
        sor = f"🕯️ {ev} éve ({datum}) hunyt el {sz['nev']}{elet}{leiras}."
    elif sz.get("elhunyt"):
        sor = f"🌱 {ev} éve ({datum}) született {sz['nev']}{leiras}."
    else:
        sor = f"🎂 Ma {ev} éves {sz['nev']}{leiras}."
    return [sor, f"📍 {sz['kotodes'][0].upper() + sz['kotodes'][1:]}. Bővebben: {sz['link']}"]


def szoveg(nap, lista=None):
    lista = lista if lista is not None else szemelyek()
    if lista is None:
        return None
    valogatott = evfordulok(nap, lista)
    if not valogatott:
        return ""
    sorok = ["🕯️ CSEPELI ÉVFORDULÓ" if len(valogatott) == 1 else "🕯️ CSEPELI ÉVFORDULÓK",
             f"📅 {HONAPOK[nap.month - 1]} {nap.day}.", "",
             "Ma olyan emberekre emlékezem, akik kötődnek Csepelhez:" if len(valogatott) > 1
             else "Ma egy olyan emberre emlékezem, aki kötődik Csepelhez:", ""]
    for sz, fajta, ev in valogatott:
        sorok += _bekezdes(sz, fajta, ev, nap) + [""]
    kerdes = ("Ismertétek őt személyesen, vagy tudtok róla valamit?" if len(valogatott) == 1
              else "Ismertétek őket személyesen, vagy tudtok róluk valamit?")
    sorok += [f"💬 {kerdes} Írjátok meg kommentben!",
              "ℹ️ Forrás: Wikipédia", "", "#Csepel #emlékezés #évforduló #csepeliek"]
    return "\n".join(sorok)


if __name__ == "__main__":
    nap = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.now(MAGYAR_TZ).date()
    lista = szemelyek()
    if lista:
        for sz in sorted(lista, key=lambda s: s["nev"])[:40]:
            print(f"   {sz['nev']}: {sz['szuletett']} – {sz['elhunyt']} | {sz['kotodes']} | {sz['leiras'][:80]}")
    print("\n" + (szoveg(nap, lista) or "(ma nincs csepeli évforduló)"))
