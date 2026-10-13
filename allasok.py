"""
💼 Heti állásajánló – új csepeli álláshirdetések
Források:
  - allas.csepel.hu (az önkormányzat állásportálja)
  - varosgazda.eu (a Csepeli Városgazda saját álláslistája)
  - profession.hu (Csepel kulcsszóra)
A hu.indeed.com és az allas.jofogas.hu a GitHub szervereiről nem érhető el
(robotszűrő, HTTP 403), ezért azok kimaradnak.
Csak a még nem posztolt hirdetések kerülnek be (az állapotfájlban tárolva).
"""

import re
import html
import requests
from datetime import date

from poszt_valtozatos import Stilus

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
}

CSEPEL_URL = "https://allas.csepel.hu/"
VAROSGAZDA_URL = "https://varosgazda.eu/karrier/"
PROFESSION_URL = "https://www.profession.hu/allasok/budapest/1,0,23,csepel"

# Az előző állásposzt óta megjelent összes hirdetés kimegy; ez csak biztonsági felső korlát
MAX_ALLAS = 100
# Ennyi azonosítót jegyzünk meg (a régiek kiesnek)
MAX_LATOTT = 1500

HONAPOK = {"január": 1, "február": 2, "március": 3, "április": 4, "május": 5, "június": 6, "július": 7,
           "augusztus": 8, "szeptember": 9, "október": 10, "november": 11, "december": 12}


def _szoveg(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def _get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            print(f"  ⚠️ {url} HTTP {r.status_code}")
            return None
        return r.text
    except Exception as ex:
        print(f"  ❌ {url}: {ex}")
        return None


def csepel_feldolgoz(oldal):
    """allas.csepel.hu: <div class="boxAllContainer"> blokkok (cím, cég, dátum, link)."""
    lista = []
    for blokk in re.split(r'<div class="boxAllContainer">', oldal)[1:]:
        link = re.search(r'<a href="([^"]+)"', blokk)
        cim = re.search(r'<h2 class="title">(.*?)</h2>', blokk, re.S)
        ceg = re.search(r'<div class="text-right">.*?<p>(.*?)</p>', blokk, re.S)
        datum = re.search(r'class="rightDate">(\d{4})\.(\d{2})\.(\d{2})', blokk)
        if not (link and cim):
            continue
        lista.append({
            "cim":   _szoveg(cim.group(1)),
            "ceg":   _szoveg(ceg.group(1)) if ceg else "",
            "link":  html.unescape(link.group(1)),
            "datum": date(int(datum.group(1)), int(datum.group(2)), int(datum.group(3))) if datum else None,
        })
    return lista


def varosgazda_feldolgoz(oldal, link):
    """varosgazda.eu: "– Kőműves és segédmunkás // 2026. Szeptember 17." sorok."""
    lista = []
    szoveg = html.unescape(re.sub(r"<[^>]+>", " ", oldal))
    for sor in re.findall(r"[–-]\s*([^–/\n]{3,80}?)\s*//\s*(\d{4})\.\s*([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]+)\s*(\d{1,2})\.", szoveg):
        nev, ev, honap, nap = sor
        try:
            datum = date(int(ev), HONAPOK[honap.lower()], int(nap))
        except (KeyError, ValueError):
            datum = None
        lista.append({"cim": " ".join(nev.split()).replace("M otoros", "Motoros"), "ceg": "Csepeli Városgazda Zrt.",
                      "link": link, "datum": datum})
    return lista


def varosgazda():
    """A karrieroldalról a legfrissebb "Álláslehetőségek" bejegyzés listája."""
    oldal = _get("https://varosgazda.eu/")
    if oldal is None:
        return None
    link = re.search(r'href="(https?://varosgazda\.eu/\d{4}/\d{2}/\d{2}/allaslehetosegek/?)"', oldal)
    link = link.group(1) if link else VAROSGAZDA_URL
    reszlet = _get(link)
    return None if reszlet is None else varosgazda_feldolgoz(reszlet, link)


def profession_feldolgoz(oldal):
    """profession.hu: <li class="advertisement-result-list-item" data-link=… data-item-name=… data-item-brand=…>"""
    lista = []
    for li in re.findall(r'<li class="advertisement-result-list-item"([^>]*)>', oldal):
        adat = dict(re.findall(r'data-([a-z0-9-]+)="([^"]*)"', li))
        if not adat.get("link") or not adat.get("item-name"):
            continue
        lista.append({
            "cim":   html.unescape(adat["item-name"]).strip(),
            "ceg":   html.unescape(adat.get("item-brand", "")).strip(),
            "link":  html.unescape(adat["link"]).split("?")[0],
            "datum": None,
        })
    return lista


def _kulcs(a):
    """Ugyanaz az állás több forrásból is jöhet: a név és a cég alapján szűrünk."""
    return re.sub(r"\W+", "", f"{a['cim']}|{a['ceg']}".lower())


def osszes():
    """Az összes forrás hirdetései (ismétlődés nélkül), vagy None, ha mind hibás."""
    eredmenyek, hibas = [], 0
    for nev, fv in [("allas.csepel.hu", lambda: (lambda o: None if o is None else csepel_feldolgoz(o))(_get(CSEPEL_URL))),
                    ("Városgazda", varosgazda),
                    ("profession.hu", lambda: (lambda o: None if o is None else profession_feldolgoz(o))(_get(PROFESSION_URL)))]:
        lista = fv()
        if lista is None:
            hibas += 1
            continue
        print(f"  💼 {nev}: {len(lista)} hirdetés")
        eredmenyek += lista
    if hibas == 3:
        return None
    latott, egyedi = set(), []
    for a in eredmenyek:
        if _kulcs(a) not in latott:
            latott.add(_kulcs(a))
            egyedi.append(a)
    return egyedi


def heti_szoveg(nap, allapot, lista=None):
    """Az új (még nem posztolt) állások. None = minden forrás hibás, "" = nincs új."""
    if lista is None:
        lista = osszes()
        if lista is None:
            return None
    volt = allapot.setdefault("allas_latott", [])
    uj = [a for a in lista if _kulcs(a) not in volt]
    if not uj:
        return ""
    # A dátummal rendelkezők a legfrissebbek elöl, a dátum nélküliek utánuk
    uj.sort(key=lambda a: a["datum"] or date.min, reverse=True)
    kimegy = uj[:MAX_ALLAS]
    # Mindet látottnak jelöljük, hogy a régi hirdetések ne gyűljenek fel
    volt.extend(_kulcs(a) for a in uj)
    del volt[:-MAX_LATOTT]

    st = Stilus("allasok", nap.isoformat())
    sorok = [st.cim, st.vonal(), "", st.bevezeto, ""]
    for a in kimegy:
        sorok.append(f"🔹 {a['cim']}" + (f" – {a['ceg']}" if a["ceg"] else ""))
        sorok.append(f"   🔗 {a['link']}")
    sorok.append("")
    if len(uj) > MAX_ALLAS:
        sorok.append(f"➕ És még {len(uj) - MAX_ALLAS} új hirdetés, ezeket az alábbi oldalon találod.")
    sorok.append(f"🔎 Még több csepeli állás: {CSEPEL_URL}")
    if st.zaro:
        sorok += ["", st.zaro]
    sorok.append("#állás #munka #Csepel #Pesterzsébet #Szigetszentmiklós")
    return "\n".join(sorok)
