"""
🎸 Kerületi programforrások a színes posztokhoz
  - Barba Negra (Csepel, Szállító u. 3.) – a barbanegra.hu/programok oldal
  - Csepeli Munkásotthon (Árpád u. 1.) – a jegy.hu helyszínoldala (a saját
    Google-naptáruk nem nyilvános, ezért csak a jegyes programok látszanak)
  - Fedák Sári Színház (Soroksár) – a fedakszinhaz.hu játékterv-oldala
  - Müpa – a jegy.hu helyszínoldala (nem kerületi, ezért naponta csak
    néhány programja kerül be, és csak a mai/hétvégi ajánlóba)
Minden forrás egységes listát ad: {"cim", "nap" (date), "ido", "hely", "link"}.
Hiba esetén None, hogy a hívó el tudja dönteni, kihagyja-e a forrást.
"""

import re
import html
import requests
from datetime import date

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "hu",
}

BARBA_URL = "https://www.barbanegra.hu/programok"
BARBA_ALAP = "https://www.barbanegra.hu"


def _szoveg(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def barba_negra_feldolgoz(oldal):
    """Az eseménykártyák (<article class="event-card">) kiolvasása.
    A dátum a program linkjének végén van: /program/kalapacs_20261016"""
    lista, latott = [], set()
    for kartya in re.split(r"<article\b", oldal)[1:]:
        kartya = kartya.split("</article>", 1)[0]
        link = re.search(r'href="(/program/[^"]*?_(\d{8})[^"]*)"', kartya)
        if not link or link.group(1) in latott:
            continue
        latott.add(link.group(1))
        d = link.group(2)
        try:
            nap = date(int(d[:4]), int(d[4:6]), int(d[6:]))
        except ValueError:
            continue
        cim = re.search(r'data-title="([^"]*)"', kartya)
        cim = _szoveg(cim.group(1)) if cim else ""
        if not cim:
            h3 = re.search(r"<h3[^>]*>(.*?)</h3>", kartya, re.S)
            cim = _szoveg(h3.group(1)) if h3 else ""
        szinpad = re.search(r'class="badge[^"]*"[^>]*>(.*?)</span>\s*</div>', kartya, re.S)
        szinpad = _szoveg(szinpad.group(1)) if szinpad else ""
        ido = re.search(r"Kapunyitás:\s*(\d{1,2}:\d{2})", kartya)
        lista.append({
            "cim":  cim,
            "nap":  nap,
            "ido":  f"{ido.group(1)} kapunyitás" if ido else "",
            "hely": f"Barba Negra {szinpad}".strip(),
            "link": BARBA_ALAP + link.group(1),
        })
    lista.sort(key=lambda x: x["nap"])
    return lista


def barba_negra():
    try:
        r = requests.get(BARBA_URL, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            print(f"  ⚠️ Barba Negra HTTP {r.status_code}")
            return None
        lista = barba_negra_feldolgoz(r.text)
        print(f"  🎸 Barba Negra: {len(lista)} program")
        return lista
    except Exception as ex:
        print(f"  ❌ Barba Negra: {ex}")
        return None


JEGY_ALAP = "https://www.jegy.hu/venue/"


def jegy_hu_feldolgoz(oldal, hely):
    """A jegy.hu helyszínoldal programdobozai (<div class="programBox">)."""
    lista, latott = [], set()
    for doboz in re.split(r'<div class="programBox">', oldal)[1:]:
        kezd = re.search(r'itemprop="startDate" content="(\d{4})-(\d{2})-(\d{2})[T ](\d{2}:\d{2})', doboz)
        link = re.search(r'href="(https://www\.jegy\.hu/program/[^"/]+)"', doboz)
        cim = re.search(r"<h2>(.*?)</h2>", doboz, re.S)
        if not (kezd and link and cim):
            continue
        kulcs = (link.group(1), kezd.group(0))
        if kulcs in latott:
            continue
        latott.add(kulcs)
        lista.append({
            "cim":  _szoveg(cim.group(1)),
            "nap":  date(int(kezd.group(1)), int(kezd.group(2)), int(kezd.group(3))),
            "ido":  kezd.group(4),
            "hely": hely,
            "link": link.group(1),
        })
    lista.sort(key=lambda x: (x["nap"], x["ido"]))
    return lista


def jegy_hu(helyszin, hely):
    try:
        r = requests.get(JEGY_ALAP + helyszin, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            print(f"  ⚠️ jegy.hu ({helyszin}) HTTP {r.status_code}")
            return None
        lista = jegy_hu_feldolgoz(r.text, hely)
        print(f"  🎭 {hely}: {len(lista)} program")
        return lista
    except Exception as ex:
        print(f"  ❌ jegy.hu ({helyszin}): {ex}")
        return None


def munkasotthon():
    a = jegy_hu("csepeli-munkasotthon", "Csepeli Munkásotthon")
    b = jegy_hu("csepeli-munkasotthon-szinhazterem", "Csepeli Munkásotthon, színházterem")
    if a is None and b is None:
        return None
    return (a or []) + (b or [])


def mupa():
    return jegy_hu("mupa", "Müpa")


FEDAK_URL = "https://www.fedakszinhaz.hu/jatekterv/"
FEDAK_ALAP = "https://www.fedakszinhaz.hu/"

HONAP_SZAM = {"JANUÁR": 1, "FEBRUÁR": 2, "MÁRCIUS": 3, "ÁPRILIS": 4, "MÁJUS": 5, "JÚNIUS": 6,
              "JÚLIUS": 7, "AUGUSZTUS": 8, "SZEPTEMBER": 9, "OKTÓBER": 10, "NOVEMBER": 11, "DECEMBER": 12}


def fedak_feldolgoz(oldal):
    """A Webnode-os oldal szövegblokkjai: <h4>szerző</h4><h3>CÍM</h3><h4>műfaj</h4>
    <h4>2026. OKTÓBER 11. /vasárnap/<br>15:00 ÓRA</h4><h4>terem</h4>"""
    lista, latott = [], set()
    for blokk in re.split(r'<div class="b b-text', oldal)[1:]:
        cim = re.search(r"<h3[^>]*>(.*?)</h3>", blokk, re.S)
        datum = re.search(r"(\d{4})\.\s*([A-ZÁÉÍÓÖŐÚÜŰ]+)\s*(\d{1,2})\.(.*?)(\d{1,2}[:.]\d{2})\s*ÓRA", _szoveg(blokk))
        if not (cim and datum) or datum.group(2) not in HONAP_SZAM:
            continue
        h4 = [_szoveg(x) for x in re.findall(r"<h4[^>]*>(.*?)</h4>", blokk, re.S)]
        szerzo = h4[0] if h4 and not re.search(r"\d{4}\.", h4[0]) else ""
        cim = _szoveg(cim.group(1))
        cim = f"{szerzo}: {cim}" if szerzo else cim
        try:
            nap = date(int(datum.group(1)), HONAP_SZAM[datum.group(2)], int(datum.group(3)))
        except ValueError:
            continue
        if (nap, cim) in latott:
            continue
        latott.add((nap, cim))
        lista.append({
            "cim":  cim,
            "nap":  nap,
            "ido":  datum.group(5).replace(".", ":"),
            "hely": "Fedák Sári Színház (Soroksár)",
            "link": FEDAK_URL,
        })
    lista.sort(key=lambda x: (x["nap"], x["ido"]))
    return lista


def fedak():
    try:
        r = requests.get(FEDAK_URL, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            print(f"  ⚠️ Fedák Sári Színház HTTP {r.status_code}")
            return None
        lista = fedak_feldolgoz(r.text)
        print(f"  🎭 Fedák Sári Színház: {len(lista)} előadás")
        return lista
    except Exception as ex:
        print(f"  ❌ Fedák Sári Színház: {ex}")
        return None


# (név, lekérdező, kerületi-e, naponta legfeljebb ennyi program)
FORRASOK = [
    ("Csepeli Munkásotthon", munkasotthon, True,  None),
    ("Barba Negra",          barba_negra,  True,  None),
    ("Fedák Sári Színház",   fedak,        True,  None),
    ("Müpa",                 mupa,         False, 3),
]


def programok(tol, ig):
    """Az összes forrás programjai a [tol, ig] napok között, időrendben.
    Visszaad: (lista, hibas_forrasok)."""
    osszes, hibas = [], []
    for nev, fv, keruleti, napi_max in FORRASOK:
        eredmeny = fv()
        if eredmeny is None:
            hibas.append(nev)
            continue
        naponta, latott = {}, set()
        for p in eredmeny:
            if not tol <= p["nap"] <= ig or (p["nap"], p["cim"]) in latott:
                continue   # ugyanaz a program aznap többször (pl. délelőtt és délben)
            latott.add((p["nap"], p["cim"]))
            if napi_max and naponta.get(p["nap"], 0) >= napi_max:
                continue
            naponta[p["nap"]] = naponta.get(p["nap"], 0) + 1
            osszes.append(dict(p, keruleti=keruleti))
    osszes.sort(key=lambda x: (x["nap"], x["ido"]))
    return osszes, hibas


KULTIK_URL = "https://port.hu/helyszin/mozi/kultik-csepel/place-7912"
PORT_ALAP = "https://port.hu"


def kultik_feldolgoz(oldal):
    """A port.hu mozioldala: a filmcímek táblázata (<a class="event-title">) és
    mellette a napi idősáv-táblázat (<div class="scroll-table" data-day="ÉÉÉÉHHNN">),
    amelynek soraiban (<tr class="event-row">) az adott film vetítési időpontjai vannak.
    Visszaad: [{"cim", "nap", "idok": [...], "link"}]."""
    lista = []
    for m in re.finditer(r'<div class="scroll-table" data-day="(\d{8})"', oldal):
        d = m.group(1)
        try:
            nap = date(int(d[:4]), int(d[4:6]), int(d[6:]))
        except ValueError:
            continue
        elotte = oldal[:m.start()]
        cimtabla = elotte[elotte.rfind("<table"):]
        filmek = re.findall(r'<a href="([^"]+)" title="[^"]*" class="event-title">(.*?)</a>', cimtabla, re.S)
        idotabla = oldal[m.end():].split("</table>", 1)[0]
        sorok = idotabla.split('<tr class="event-row">')[1:]
        for (link, cim), sor in zip(filmek, sorok):
            idok = sorted(re.findall(r'event-time">\s*(\d{1,2}:\d{2})', sor))
            if idok:
                lista.append({"cim": _szoveg(cim), "nap": nap, "idok": idok, "link": PORT_ALAP + link})
    return lista


def kultik():
    """A Kultik Csepel mozi műsora a port.hu-ról, vagy None hiba esetén."""
    try:
        r = requests.get(KULTIK_URL, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            print(f"  ⚠️ Kultik (port.hu) HTTP {r.status_code}")
            return None
        lista = kultik_feldolgoz(r.text)
        print(f"  🎬 Kultik Csepel: {len(lista)} film")
        return lista
    except Exception as ex:
        print(f"  ❌ Kultik (port.hu): {ex}")
        return None
