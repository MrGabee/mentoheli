"""
💼 Heti állásajánló – új csepeli álláshirdetések
Források:
  - allas.csepel.hu (az önkormányzat állásportálja)
  - varosgazda.eu (a Csepeli Városgazda saját álláslistája)
  - profession.hu (Csepel kulcsszóra)
  - kozszolgallas.ksz.gov.hu (a közszolgálati állásportál; a teljes listát
    lekérjük, és a környékbeli munkáltatókra / településekre szűrünk)
A hu.indeed.com és az allas.jofogas.hu a GitHub szervereiről nem érhető el
(robotszűrő, HTTP 403), ezért azok kimaradnak.
Csak a még nem posztolt hirdetések kerülnek be (az állapotfájlban tárolva).
Kiküldés előtt minden linket megnyit: ami hibaoldalra, „nincs publikálva”
oldalra vagy általános listára visz, illetve nincs rajta az állás neve, kimarad.
"""

import re
import html
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from poszt_valtozatos import Stilus

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
}

CSEPEL_URL = "https://allas.csepel.hu/"
VAROSGAZDA_URL = "https://varosgazda.eu/karrier/"
PROFESSION_URL = "https://www.profession.hu/allasok/budapest/1,0,23,csepel"
KSZ_URL = "https://kozszolgallas.ksz.gov.hu"
# Közszolgállás: környékbeli település, vagy budapesti munkáltató, akinek a nevében ez szerepel
KSZ_TELEPULESEK = {"Szigetszentmiklós", "Halásztelek", "Tököl", "Szigethalom", "Dunaharaszti", "Gyál"}
KSZ_KORNYEK = re.compile(r"\bXXI\.|\bXX\.|\bXXIII\.|CSEPEL|PESTERZSÉBET|SOROKSÁR|DÉL-PESTI|KÜLSŐ-PESTI", re.I)

# Az előző állásposzt óta megjelent összes hirdetés kimegy; ez csak biztonsági felső korlát
MAX_ALLAS = 100
# Ennyi azonosítót jegyzünk meg (a régiek kiesnek)
MAX_LATOTT = 1500
# Ennél régebbi dátumú hirdetés nem kerül be (gyakran már lejárt)
MAX_KOR_NAP = 30

# A kozszolgallas.ksz.gov.hu tanúsítványláncából hiányzik a köztes tanúsítvány
# (a böngésző pótolja, a Python nem), ezért ott csak olvasunk, ellenőrzés nélkül.
NEM_ELLENORZOTT_TLS = ("kozszolgallas.ksz.gov.hu",)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
HALOTT_SZOVEG = ("nincs publikálva", "nem található", "lejárt a hirdetés", "már nem aktív",
                 "a hirdetés lejárt", "page not found")

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


def _szavak(cim):
    """Az állás nevének jellemző szótövei (az oldalon ezek közül legalább egynek szerepelnie kell)."""
    return [w[:5].lower() for w in re.findall(r"\w+", cim) if len(w) >= 4] or [cim.lower()[:5]]


def link_el(a):
    """True: a link él és az adott állást mutatja; False: biztosan nem; None: most nem eldönthető."""
    url = a["link"]
    try:
        r = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True,
                         verify=not any(h in url for h in NEM_ELLENORZOTT_TLS))
    except Exception as ex:
        print(f"  ⏳ Nem ellenőrizhető most: {url} ({ex.__class__.__name__})")
        return None
    if r.status_code in (404, 410):
        return False
    if r.status_code != 200:
        return None
    vegso = r.url
    if "/Errors/" in vegso or "/Error" in vegso:
        return False
    if "profession.hu" in url and "/allas/" not in vegso:
        return False   # lejárt: általános állásfelsorolásra irányít át
    if "drive.google.com" in url:
        return "ServiceLogin" not in vegso and "accounts.google.com" not in vegso
    szoveg = _szoveg(re.sub(r"(?s)<(script|style).*?</\1>", " ", r.text)).lower()
    if any(h in szoveg for h in HALOTT_SZOVEG):
        return False
    return any(w in szoveg for w in _szavak(a["cim"]))


def ellenoriz(lista):
    """(élő hirdetések, biztosan halott hirdetések) – párhuzamosan nézi meg a linkeket."""
    with ThreadPoolExecutor(max_workers=8) as ex:
        eredmeny = list(ex.map(link_el, lista))
    elo = [a for a, e in zip(lista, eredmeny) if e is True]
    halott = [a for a, e in zip(lista, eredmeny) if e is False]
    for a in halott:
        print(f"  🚫 Nem elérhető, kimarad: {a['cim']} – {a['link']}")
    print(f"  ✅ Ellenőrizve: {len(elo)} él, {len(halott)} nem elérhető, "
          f"{len(lista) - len(elo) - len(halott)} most nem ellenőrizhető.")
    return elo, halott


def kozszolgallas():
    """A közszolgálati állásportál összes aktív hirdetése (egy lekéréssel), a környékre szűrve."""
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        s.verify = False   # hiányos tanúsítványlánc, lásd NEM_ELLENORZOTT_TLS
        oldal = s.get(KSZ_URL + "/JobAd?isDetailSearch=true", timeout=30).text
        tok = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', oldal).group(1)
        r = s.post(KSZ_URL + "/JobAd/ListGridAsync", timeout=90,
                   data='{"page":1,"pagesize":5000,"sort":"Created DESC"}',
                   headers={"Content-Type": "application/json; charset=utf-8",
                            "X-Requested-With": "XMLHttpRequest", "RequestVerificationToken": tok})
        if r.status_code != 200:
            print(f"  ⚠️ közszolgállás HTTP {r.status_code}")
            return None
    except Exception as ex:
        print(f"  ❌ közszolgállás: {ex}")
        return None
    lista, osszes = [], 0
    for m in re.finditer(r'(?s)jobaditemelement" id="(\d+)".*?<h4>\s*<strong>(.*?)</strong>.*?<h5><strong>(.*?)</strong></h5>'
                         r'.*?<h5>(.*?)</h5>', r.text):
        osszes += 1
        azon, cim, ceg, hely = m.group(1), _szoveg(m.group(2)), _szoveg(m.group(3)), _szoveg(m.group(4))
        if not (hely in KSZ_TELEPULESEK or (hely == "Budapest" and KSZ_KORNYEK.search(ceg))):
            continue
        cim = re.sub(r"\s+-\s+[^-]*\d[^-]*$", "", cim)   # a végéről a hivatkozási szám le
        lista.append({"cim": cim, "ceg": ceg.title() if ceg.isupper() else ceg,
                      "link": f"{KSZ_URL}/JobAd/Info/{azon}", "datum": None})
    print(f"  🏛️ közszolgállás: {osszes} hirdetésből {len(lista)} a környéken")
    return lista if osszes else None


def _kulcs(a):
    """Ugyanaz az állás több forrásból is jöhet: a név és a cég alapján szűrünk."""
    return re.sub(r"\W+", "", f"{a['cim']}|{a['ceg']}".lower())


def osszes():
    """Az összes forrás hirdetései (ismétlődés nélkül), vagy None, ha mind hibás."""
    eredmenyek, hibas = [], 0
    for nev, fv in [("allas.csepel.hu", lambda: (lambda o: None if o is None else csepel_feldolgoz(o))(_get(CSEPEL_URL))),
                    ("Városgazda", varosgazda),
                    ("profession.hu", lambda: (lambda o: None if o is None else profession_feldolgoz(o))(_get(PROFESSION_URL))),
                    ("közszolgállás", kozszolgallas)]:
        lista = fv()
        if lista is None:
            hibas += 1
            continue
        print(f"  💼 {nev}: {len(lista)} hirdetés")
        eredmenyek += lista
    if hibas == 4:
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
    hatar = nap - timedelta(days=MAX_KOR_NAP)
    regi = [a for a in lista if _kulcs(a) not in volt and a["datum"] and a["datum"] < hatar]
    uj = [a for a in lista if _kulcs(a) not in volt and not (a["datum"] and a["datum"] < hatar)]
    volt.extend(_kulcs(a) for a in regi)
    if not uj:
        del volt[:-MAX_LATOTT]
        return ""
    # Csak az a link kerül ki, ami tényleg az adott állást nyitja meg
    uj, halott = ellenoriz(uj)
    volt.extend(_kulcs(a) for a in halott)
    if not uj:
        del volt[:-MAX_LATOTT]
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
