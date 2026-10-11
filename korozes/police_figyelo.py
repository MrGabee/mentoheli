#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POLICE.HU FIGYELŐ
==================================================================
Figyeli a police.hu körözési rendszerét és hírfolyamát, és értesít
minden ÚJ bejegyzésről, ami a XX./XXI. kerülethez vagy Szigetszentmiklóshoz
kapcsolódik.

- Körözések (koral): az "Elrendelő szerv" / "Eljáró szerv" mezőben
  keresi a megadott szervezeteket.
- Hírek: a címben/összefoglalóban keresi a "XX. kerület"/"XXI. kerület"/
  "XX. KER"/"XXI. KER" mintát (pontos illesztés, "XXI. század"-szerű
  hamis találatok nélkül), valamint a "Szigetszentmiklós" szót.

MINDEN KATEGÓRIÁNÁL külön beállítható a 'facebook_post' jelző - ha
True, az adott kategória új találatai a Facebook Oldalra is
automatikusan kikerülnek email mellett, egy Make.com webhookon keresztül
(lásd MAKE_WEBHOOK_AKTIV kapcsoló lent).

Adatvédelem: "Elfogatóparancs alapján körözött személy" találatnál a
Facebook-posztból (nem az emailből!) kihagyjuk a nevet és a fényképet is,
mivel ott egy még el nem ítélt, valódi ember személyes adatairól van szó.
"""

import os
import sys
import re
import json
import time
import requests
from urllib.parse import quote
from datetime import datetime, timedelta, timezone, time as dtime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

# A közös poszt-stílusok (poszt_valtozatos.py) a repó gyökerében vannak
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from poszt_valtozatos import Stilus  # noqa: E402

# =====================================================================
# BEÁLLÍTÁS
# =====================================================================

BASE_URL = "https://www.police.hu"
DATA_FAJL = "korozes/data/police_figyelo.json"
MAX_UJ_RESZLET_LEKERDEZES = 40  # egy futásban max ennyi ÚJ elem részletét kérdezzük le
HIREK_RIASZTAS_UTANI_FUTAS = 8  # ennyi egymás utáni "mind a 10 hír-kategória üres" futás után figyelmeztető email (~2 óra a 15 perces ütemnél)

# ⬇️⬇️⬇️ ITT KAPCSOLOD KI/BE A MAKE.COM-ON KERESZTÜLI FACEBOOK-POSZTOLÁST (FŐKAPCSOLÓ) ⬇️⬇️⬇️
# True  = a lent, kategóriánként "facebook_post": True-ra állított
#         kategóriák új találatai automatikusan kikerülnek a Facebook
#         Oldalra is, egy Make.com automatizáción (webhook) keresztül -
#         ehhez egy érvényes MAKE_WEBHOOK_URL GitHub Secret kell.
# False = ez a Make.com-kapcsoló - akkor is letiltja a Facebook-posztolást,
#         ha egy-egy kategóriánál "facebook_post": True van beállítva.
#         Az email-küldést ez NEM érinti.
MAKE_WEBHOOK_AKTIV = True  # = "Make.com kapcsoló"

# True  = a rendőrségi posztok a MAKE_WEBHOOK_URL_RENDORSEG forgatókönyvön mennek
#         (illusztrációs kép, lezáráskor a poszt átírása, utolsó poszt lekérdezése).
# False = a fő MAKE_WEBHOOK_URL-en, szövegként; a "link" mező az átirányító
#         oldalra mutat (ebből lesz az illusztrációs előnézet). Javítás és
#         lekérdezés ilyenkor nincs.
#         (A Make-szervezetben az új Facebook-modulok el sem indulnak, ezért ez az alap.)
MAKE_KEPES_FORGATOKONYV = False

# A körözési rendszerben ezekre a szervekre szűrünk (Elrendelő VAGY Eljáró szerv mezőben)
KOROZES_SZERV_SZURO = [
    "BUDAPESTI XXI. KER. RK",
    "BUDAPESTI XX-XXIII. KER. RK",
    "BUDAPESTI XX. KER. RK",
    "BUDAPESTI XXIII. KER. RK",
    "Budapesti XX., XXI. és XXIII. Kerületi Bíróság",
    # Szigetszentmiklós saját rendőrkapitányságához tartozik (Pest Vármegyei
    # Rendőr-főkapitányság alá) - egyszerű "SZIGETSZENTMIKLÓS" részszöveges
    # szűrés, hogy a hivatalos elnevezés bármelyik formájára (teljes néven
    # "Szigetszentmiklósi Rendőrkapitányság" vagy rövidítve "SZIGETSZENTMIKLÓSI
    # RK") illeszkedjen.
    "SZIGETSZENTMIKLÓS",
]

# A hírekben erre a mintára szűrünk (kerület-jelölés, "XXI. század"-szerű hamis
# találatok elkerülésével - csak akkor egyezik, ha utána KER/kerület áll -,
# valamint Szigetszentmiklós néven, ékezettel és ékezet nélkül is)
HIREK_MINTA = re.compile(
    r"\bXXI?\.?\s*(KER|kerület)|\bXXIII\.?\s*(KER|kerület)|csepel|pesterzsébet|"
    r"soroksár(?!i\s+út)|szigetszentmikl[oó]s",   # a Soroksári út a IX. kerületben van
    re.IGNORECASE,
)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PoliceHuFigyelo/1.0)"}

# A kiposztolt körözéseket ennyi egymás utáni futáson át "Az oldal nem található"
# (404) állapotban kell látni, mielőtt lezártnak vesszük és javítjuk a posztot
LEZARAS_404_SZAM = 2
# Ennyi nap után már nem figyeljük, hogy egy kiposztolt körözés lekerült-e
KOVETES_NAP = 180

# Ezzel a szöveggel íródik át a poszt, ha az adatlap lekerült a police.hu-ról.
# Név és fénykép nélkül, hogy a lezárt ügy szereplője ne maradjon az oldalon.
LEZARVA_SZOVEG = {
    "eltunt_szemelyek": "A rendőrség lezárta a keresést, a felhívás lekerült a police.hu-ról. "
                        "Köszönöm mindenkinek, aki megosztotta és figyelt! 🙏",
    "korozott_szemelyek": "A rendőrség visszavonta ezt a körözést. Köszönöm a figyelmet!",
}
LEZARVA_JARMU = "A rendőrség visszavonta a jármű körözését. Köszönöm mindenkinek a megosztást! 🙏"

# A rendőrségi posztok képes posztként mennek ki ezzel az illusztrációval, így
# a szövegben lévő police.hu-linkekhez nem jelenik meg előnézet (a fotó sem).
KEP_ALAP = "https://raw.githubusercontent.com/MrGabee/mentoheli/main/kepek/"
KEP_KOROZES = KEP_ALAP + "rendorseg_korozes.png"
KEP_HIR = KEP_ALAP + "rendorseg_hir.png"

# Szöveges módban a poszt "link" mezője ezekre az átirányító oldalakra mutat: a
# Facebook-előnézet az illusztrációt mutatja, kattintásra a police.hu-ra visz.
ATIRANYITO_ALAP = "https://kozles.github.io/posztol/"
ATIRANYITO_KOROZES = ATIRANYITO_ALAP
ATIRANYITO_HIR = ATIRANYITO_ALAP + "hir.html"


def elonezet_link(atiranyito, police_url):
    return f"{atiranyito}?u={quote(police_url, safe='')}"

# Lecsengés: a rendőrségi poszt várólistára kerül, és csak akkor megy ki, ha
#  - az oldal legutóbbi posztja legalább LECSENGES_PERC perce ment ki,
#  - a következő időzített poszt legalább IDOZITETT_TAVOLSAG_PERC perc múlva jön,
#  - nincs éjszaka (EJSZAKA_TOL és EJSZAKA_IG között vár reggelig).
LECSENGES_PERC = 60
IDOZITETT_TAVOLSAG_PERC = 45
EJSZAKA_TOL = (22, 0)
EJSZAKA_IG = (6, 45)
VAROLISTA_MAX_ORA = 48   # ennél régebben váró posztot már nem teszünk ki

# ---------------------------------------------------------------------
# KÖRÖZÉSI KATEGÓRIÁK
# 'facebook_post': True esetén ennek a kategóriának az új találatai
# a Facebook Oldalra is automatikusan kikerülnek email mellett.
# ---------------------------------------------------------------------
KOROZES_KATEGORIAK = {
    "eltunt_szemelyek": {
        "label": "Eltűnt, ismeretlen helyen lévő személy",
        "list_path": "/hu/koral/eltunt-szemelyek",
        "facebook_post": True,
    },
    "korozott_szemelyek": {
        "label": "Elfogatóparancs alapján körözött személy",
        "list_path": "/hu/koral/elfogatoparancs-alapjan-korozott-szemelyek",
        "facebook_post": True,
    },
    "holttest_korozes": {
        "label": "Ismeretlen holttest/holttestrész körözés",
        "list_path": "/hu/koral/holttest-holttestresz-korozesek",
        "facebook_post": False,
    },
    "jarmu_korozes": {
        "label": "Közúti jármű körözés",
        "list_path": "/hu/koral/kozutijarmu-korozesek",
        "facebook_post": True,
    },
    "legijarmu_korozes": {
        "label": "Légi jármű körözés",
        "list_path": "/hu/koral/legijarmu-korozesek",
        "facebook_post": True,
    },
    "vizijarmu_korozes": {
        "label": "Vízi jármű körözés",
        "list_path": "/hu/koral/vizijarmu-korozesek",
        "facebook_post": True,
    },
}

# ---------------------------------------------------------------------
# HÍR KATEGÓRIÁK
# ---------------------------------------------------------------------
HIREK_KATEGORIAK = {
    "legfrissebb": {
        "label": "Legfrissebb híreink",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink",
        "facebook_post": True,
    },
    "szervezeti_hirek": {
        "label": "Szervezeti hírek",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/szervezeti-hirek",
        "facebook_post": True,
    },
    "helyi_hirek": {
        "label": "Helyi hírek",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/helyi-hirek",
        "facebook_post": True,
    },
    "bunugyek": {
        "label": "Bűnügyek",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/bunugyek",
        "facebook_post": True,
    },
    "felhivasok": {
        "label": "Felhívások",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/felhivasok",
        "facebook_post": True,
    },
    "dijkituzesek": {
        "label": "Díjkitűzések",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/dijkituzesek",
        "facebook_post": True,
    },
    "kozrendvedelem": {
        "label": "Közrendvédelem",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/kozrendvedelem",
        "facebook_post": True,
    },
    "kozlekedesrendeszet": {
        "label": "Közlekedésrendészet",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/kozlekedesrendeszet",
        "facebook_post": True,
    },
    "igazgatasrendeszet": {
        "label": "Igazgatásrendészet",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/igazgatasrendeszet",
        "facebook_post": True,
    },
    "hatarrendeszet": {
        "label": "Határrendészet",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/hatarrendeszet",
        "facebook_post": True,
    },
}

# =====================================================================
# KÖRÖZÉSI RENDSZER FELDOLGOZÁSA
# =====================================================================

def korozes_lista_lekerdezese(list_path):
    url = BASE_URL + list_path
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    talalatok = []
    seen_ids = set()
    for a in soup.select(f'a[href*="{list_path}/"]'):
        href = a.get("href", "")
        match = re.search(re.escape(list_path) + r"/(\d+)$", href)
        if not match:
            continue
        item_id = match.group(1)
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        cim = a.get_text(" ", strip=True)
        teljes_url = href if href.startswith("http") else BASE_URL + href
        talalatok.append({"id": item_id, "cim": cim, "url": teljes_url})

    return talalatok


def korozes_reszlet_lekerdezese(detail_url):
    resp = requests.get(detail_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    mezok = {}
    for dt, dd in zip(soup.find_all("dt"), soup.find_all("dd")):
        kulcs = dt.get_text(" ", strip=True)
        ertek = dd.get_text(" ", strip=True)
        if kulcs:
            mezok[kulcs] = ertek

    # Az adatlap szövege ma így néz ki: "Körözést elrendelő szerv" / ": SZERENCSI RK".
    # Az üres ":" után több soros érték jöhet (Cím:, Tel:, E-mail:), ezt a
    # következő címkéig összegyűjtjük.
    for t in soup(["script", "style"]):
        t.decompose()
    sorok = [x.strip() for x in soup.get_text("\n").split("\n") if x.strip()]
    for i in range(len(sorok) - 1):
        if sorok[i].startswith(":") or not sorok[i + 1].startswith(":"):
            continue
        ertek = sorok[i + 1][1:].strip()
        if not ertek:
            tobb, j = [], i + 2
            while j < len(sorok) and len(tobb) < 6 and not (j + 1 < len(sorok) and sorok[j + 1].startswith(":")):
                tobb.append(sorok[j])
                j += 1
            ertek = " ".join(tobb)
        mezok.setdefault(sorok[i], ertek)

    kep_meta = soup.find("meta", attrs={"property": "og:image"})
    kep_url = kep_meta["content"] if kep_meta and kep_meta.get("content") else ""

    h1 = soup.find("h1")
    cim = mezok.get("Név") or (h1.get_text(" ", strip=True) if h1 else "")
    if mezok.get("Jármű fajta") or mezok.get("Gyártmány"):   # jármű: "Motorkerékpár: EGYÉB GYÁRTMÁNY MX01"
        tipus = " ".join(v for v in (mezok.get("Gyártmány"), mezok.get("Típusa")) if v)
        fajta = mezok.get("Jármű fajta", "Jármű").capitalize()
        cim = f"{fajta}: {tipus}" if tipus else fajta

    return {"cim": cim, "kep": kep_url, "mezok": mezok}


def korozes_szerv_egyezik(mezok):
    ellenorzendo_mezok = [
        v for k, v in mezok.items()
        if "szerv" in k.lower() and "értesítési" not in k.lower() and "határozat" not in k.lower()
    ]
    szoveg = " ".join(ellenorzendo_mezok).upper()
    for szerv in KOROZES_SZERV_SZURO:
        if szerv.upper() in szoveg:
            return szerv
    return None


# =====================================================================
# HÍRFOLYAM FELDOLGOZÁSA
# =====================================================================

def _hirek_foszelektor(soup):
    """A hírlista cikkei: <article> elemek, a címben linkkel, a bevezető a
    .lead-text-ben. (Régi oldalszerkezet esetén h2/h3-as linkek.)"""
    cikkek = []
    seen_urls = set()
    for art in soup.find_all("article"):
        a = art.select_one('h1 a[href*="/hirek-es-informaciok/"], h2 a[href*="/hirek-es-informaciok/"], h3 a[href*="/hirek-es-informaciok/"]')
        if not a:
            continue
        href = a.get("href", "")
        if "?page=" in href or href in seen_urls:
            continue
        seen_urls.add(href)
        lead = art.select_one(".lead-text")
        teljes_url = href if href.startswith("http") else BASE_URL + href
        cikkek.append({"url": teljes_url, "cim": a.get_text(" ", strip=True),
                       "osszefoglalo": lead.get_text(" ", strip=True) if lead else ""})
    if cikkek:
        return cikkek
    for a in soup.select('h2 a[href*="/hirek-es-informaciok/"], h3 a[href*="/hirek-es-informaciok/"]'):
        href = a.get("href", "")
        if "?page=" in href or href in seen_urls:
            continue
        seen_urls.add(href)
        cim = a.get_text(" ", strip=True)

        szulo = a.find_parent(["h2", "h3"])
        osszefoglalo = ""
        if szulo:
            kovetkezo_p = szulo.find_next("p")
            if kovetkezo_p:
                osszefoglalo = kovetkezo_p.get_text(" ", strip=True)

        teljes_url = href if href.startswith("http") else BASE_URL + href
        cikkek.append({"url": teljes_url, "cim": cim, "osszefoglalo": osszefoglalo})
    return cikkek


def _hirek_tartalek(soup):
    """TARTALÉK kinyerés, ha a police.hu átalakította az oldal szerkezetét
    (a h2/h3 szelektor ezért 0 találatot ad - pontosan ez történt: mind a 10
    hír-kategória gyorsítótára a kezdetektől ÜRES volt). Itt már nem a
    HTML-elem típusa számít, hanem csak az, hogy a link egy KONKRÉT cikkre
    mutat (a hír-szekció alatt, a kategória-oldalak maguk nem számítanak),
    és a link szövege elég hosszú ahhoz, hogy valódi cím legyen."""
    kategoria_utak = {k["list_path"].rstrip("/") for k in HIREK_KATEGORIAK.values()}
    cikkek = []
    seen_urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0]
        if "/hirek-es-informaciok/legfrissebb-hireink/" not in href:
            continue
        if "?page=" in href or "?" in href:
            continue
        teljes_url = href if href.startswith("http") else BASE_URL + href
        ut = teljes_url.replace(BASE_URL, "").rstrip("/")
        if ut in kategoria_utak or teljes_url in seen_urls:
            continue
        cim = a.get_text(" ", strip=True)
        if len(cim) < 15:
            continue
        seen_urls.add(teljes_url)

        osszefoglalo = ""
        kovetkezo_p = a.find_next("p")
        if kovetkezo_p:
            osszefoglalo = kovetkezo_p.get_text(" ", strip=True)
        cikkek.append({"url": teljes_url, "cim": cim, "osszefoglalo": osszefoglalo})
    return cikkek


def hirek_lista_lekerdezese(list_path):
    url = BASE_URL + list_path
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cikkek = _hirek_foszelektor(soup)
    if not cikkek:
        cikkek = _hirek_tartalek(soup)
        if cikkek:
            print(f"   ℹ️  A fő szelektor 0 találatot adott, a tartalék-kinyerés {len(cikkek)} cikket talált.")
    if not cikkek:
        # DIAGNOSZTIKA - hogy a következő futás naplójából kiderüljön, MIÉRT
        # nincs találat (letiltás / JavaScript-es oldal / új szerkezet).
        osszes_hirlink = [a["href"] for a in soup.find_all("a", href=True) if "/hirek-es-informaciok/" in a["href"]]
        print(f"   🔎 DIAGNOSZTIKA: HTTP {resp.status_code}, {len(resp.text)} karakter, "
              f"{len(soup.find_all('a'))} link összesen, ebből {len(osszes_hirlink)} hír-szekciós; "
              f"h2/h3 elemek: {len(soup.find_all(['h2', 'h3']))}")
        oldal_eleje = re.sub(r"\s+", " ", resp.text[:300])
        print(f"   🔎 Oldal eleje: {oldal_eleje}")
    return cikkek


def hirek_egyezik(cikk):
    szoveg = cikk["cim"] + " " + cikk["osszefoglalo"]
    return bool(HIREK_MINTA.search(szoveg))


# =====================================================================
# FACEBOOK POSZTOLÁS (Make.com webhookon keresztül)
# =====================================================================

def _make_hivas(adat, timeout=60):
    nev = "MAKE_WEBHOOK_URL_RENDORSEG" if MAKE_KEPES_FORGATOKONYV else "MAKE_WEBHOOK_URL"
    url = os.environ.get(nev, "")
    if not url:
        print(f"      ⚠️  Nincs beállítva {nev}, Facebook-posztolás kihagyva.")
        return None
    try:
        return requests.post(url, json=adat, timeout=timeout)
    except Exception as e:
        print(f"      ⚠️  Make.com hiba: {e}")
        return None


def facebook_post(uzenet, kep_url=None, post_id=None, link=None):
    """Poszt a Facebook Oldalra egy Make.com automatizáción (webhook) keresztül.
    - kep_url: képes posztként megy ki ezzel a képpel (a Make visszaadja az azonosítóját)
    - post_id: nem új poszt, hanem a meglévő szövegének átírása
    Visszaad: a poszt azonosítóját (str), True-t (ha nincs azonosító), vagy None-t hiba esetén."""
    adat = {"message": uzenet}
    if not MAKE_KEPES_FORGATOKONYV:
        if post_id:
            return None   # a fő forgatókönyv csak új posztot tud, átírni nem
        if link:
            # A Link mező az átirányító oldalra mutat: a Facebook abból készít
            # előnézetet (illusztráció), így a police.hu-s fotó nem jelenik meg.
            adat["link"] = link
    elif post_id:
        adat["post_id"] = post_id
    elif kep_url:
        adat["kep"] = kep_url
    resp = _make_hivas(adat)
    if resp is None:
        return None
    if resp.status_code != 200:
        print(f"      ⚠️  Facebook poszt sikertelen (HTTP {resp.status_code}): {resp.text[:300]}")
        return None
    print(f"      ✅ Facebook poszt {'javítva' if post_id else 'sikeres'} (Make.com-on keresztül).")
    try:
        return resp.json().get("id") or True
    except ValueError:
        return True


def _ido(szoveg):
    """Facebook/Make dátum ("2026-10-11T19:00:00+0000" vagy ...Z) -> aware datetime."""
    szoveg = (szoveg or "").strip().replace("Z", "+00:00")
    szoveg = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", szoveg)
    return datetime.fromisoformat(szoveg)


def utolso_poszt_ideje():
    """Az oldal legutóbbi posztjának ideje (bármelyik figyelőtől), a Make-en
    keresztül lekérdezve. None, ha nem sikerült."""
    if not MAKE_KEPES_FORGATOKONYV:
        return None   # a fő forgatókönyv a kérdést posztként küldené ki
    resp = _make_hivas({"kerdes": "utolso_poszt"}, timeout=30)
    try:
        return _ido(resp.json()["utolso"]) if resp is not None and resp.status_code == 200 else None
    except Exception:
        print(f"      ⚠️  Nem sikerült lekérdezni az utolsó poszt idejét: {resp.text[:200] if resp is not None else ''}")
        return None


def idozitett_posztok(nap):
    """Az adott nap időzített posztjai (reggeli összefoglaló + színes posztok), helyi időben."""
    tz = ZoneInfo("Europe/Budapest")
    idok = [dtime(6, 30)]
    try:
        import szines_posztok
        idok += [ido for _, ido, napok, _ in szines_posztok.MENETREND if napok is None or nap.weekday() in napok]
    except Exception as e:
        print(f"      ⚠️  A színes posztok menetrendje nem olvasható: {e}")
        idok += [dtime(8, 0), dtime(10, 30), dtime(13, 0), dtime(16, 0), dtime(18, 0), dtime(20, 30)]
    return [datetime.combine(nap, i, tz) for i in idok]


def szabad_ablak(most, cache):
    """(True, "") ha most kimehet egy rendőrségi poszt, különben (False, ok)."""
    helyi = most.astimezone(ZoneInfo("Europe/Budapest"))
    hm = (helyi.hour, helyi.minute)
    if hm >= EJSZAKA_TOL or hm < EJSZAKA_IG:
        return False, "éjszaka, reggelig vár"
    tav = timedelta(minutes=IDOZITETT_TAVOLSAG_PERC)
    for t in idozitett_posztok(helyi.date()):
        if timedelta(0) <= t - helyi < tav or timedelta(0) <= helyi - t < tav:
            return False, f"időzített poszt közel ({t.strftime('%H:%M')})"
    # Saját nyilvántartás: ha tudjuk, hogy még nem telt le a lecsengés, nem kérdezünk
    nem_elotte = cache.get("_lecsenges", {}).get("nem_elotte")
    if nem_elotte and most < datetime.fromisoformat(nem_elotte):
        return False, f"lecsengés, legkorábban {datetime.fromisoformat(nem_elotte).astimezone(ZoneInfo('Europe/Budapest')).strftime('%H:%M')}"
    utolso = utolso_poszt_ideje()
    if utolso is None:
        return True, ""   # a Make-lekérdezés nem működik: a fenti szabályok elegendők
    kovetkezo = utolso + timedelta(minutes=LECSENGES_PERC)
    cache.setdefault("_lecsenges", {})["nem_elotte"] = kovetkezo.isoformat()
    if most < kovetkezo:
        return False, f"az előző poszt még cseng ({utolso.astimezone(ZoneInfo('Europe/Budapest')).strftime('%H:%M')})"
    return True, ""


def varolista_kuldese(cache):
    """A várólista legrégebbi posztját küldi ki, ha most van rá szabad ablak."""
    lista = cache.setdefault("fb_varolista", [])
    most = datetime.now(timezone.utc)
    lista[:] = [t for t in lista if most - datetime.fromisoformat(t["felvetel"]) < timedelta(hours=VAROLISTA_MAX_ORA)]
    if not lista:
        return
    mehet, ok = szabad_ablak(most, cache)
    if not mehet:
        print(f"⏳ {len(lista)} rendőrségi poszt vár ({ok}).")
        return
    tetel = lista[0]
    if tetel.get("kovetes") and requests.get(tetel["kovetes"]["url"], headers=HEADERS, timeout=20).status_code == 404:
        print("   ℹ️  Várakozás közben lekerült a police.hu-ról, nem posztolom.")
        lista.pop(0)
        return
    post_id = facebook_post(tetel["fb_szoveg"], tetel["kep"], link=tetel.get("link"))
    if not post_id:
        return   # sikertelen: a következő futás újrapróbálja
    lista.pop(0)
    cache["_lecsenges"] = {"nem_elotte": (most + timedelta(minutes=LECSENGES_PERC)).isoformat()}
    if isinstance(post_id, str) and tetel.get("kovetes"):
        k = tetel["kovetes"]
        cache.setdefault("fb_posztok", {})[k["url"]] = {
            "post_id": post_id, "tipus": k["tipus"], "datum": most.isoformat(), "hiany": 0}


def _telefon(mezok):
    for k, v in mezok.items():
        if "értesítési" in k.lower():
            m = re.search(r"Tel:\s*([0-9()\-/ ]{6,})", v)
            if m:
                return m.group(1).strip(" ;")
    return ""


# A személyes posztok végére: miért illusztráció van a fénykép helyett
SZEMELYISEGI_JOG = ("🔒 A fényképet a személyiségi jogok védelme miatt nem teszem ki, "
                    "helyette illusztráció szerepel. A hivatalos adatlap a linken érhető el.")

JOGALAP = "Körözés jogalapja, bűncselekmény megnevezése, minősítése"


def rovid_nev(mezok):
    """"BARANYI FANNI" -> "B. Fanni" (családnév kezdőbetűje + utónév)."""
    nev = mezok.get("Név", "").split()
    uto = mezok.get("Viselt utónév 1", "").strip()
    if not nev:
        return ""
    if not uto or uto not in nev:
        uto = nev[-1]
    return f"{nev[0][0]}. {uto.title()}"


def korozes_poszt_szoveg(kulcs, kat, reszlet, szerv, url):
    """A körözés Facebook-szövege, E/1-ben."""
    st = Stilus("korozes")
    m = reszlet["mezok"]
    tel = _telefon(m)
    hivd = f"☎️ Ha bármit tudsz, hívd a 112-t vagy a kapitányságot: {tel}" if tel else "☎️ Ha bármit tudsz, hívd a 112-t!"
    if kulcs == "korozott_szemelyek":
        # Adatvédelem: csak rövidített név (B. Fanni), fénykép nélkül.
        sorok = [st.cim, st.bevezeto, "",
                 f"🚨 Elfogatóparancs a környéken: {rovid_nev(m)}" if rovid_nev(m) else "🚨 Új elfogatóparancs a környéken",
                 f"⚖️ {m[JOGALAP]}" if m.get(JOGALAP) else None,
                 f"🚔 {szerv}", hivd, "",
                 f"🔗 Hivatalos körözés: {url}", "", SZEMELYISEGI_JOG]
    elif kulcs == "eltunt_szemelyek":
        szul = m.get("Születési dátum", "")[:4]
        sorok = [st.cim, st.bevezeto, "",
                 f"👤 {reszlet['cim']}" + (f" (született {szul})" if szul else ""),
                 f"📅 Eltűnés napja: {m['Eltűnés dátuma']}" if m.get("Eltűnés dátuma") else None,
                 f"🚔 {szerv}", hivd, "",
                 f"📸 A fénykép és minden részlet: {url}", "", SZEMELYISEGI_JOG]
    elif "jarmu" in kulcs:
        sorok = [st.cim, st.bevezeto, "",
                 f"🚗 {reszlet['cim']}",
                 f"🎨 Szín: {m['Szín'].lower()}" if m.get("Szín") else None,
                 f"🔢 Rendszám: {m['Rendszám']}" if m.get("Rendszám") else None,
                 f"📅 Eltulajdonítás: {m['Eltűnés/eltulajdonítás dátuma']}" if m.get("Eltűnés/eltulajdonítás dátuma") else None,
                 f"🚔 {szerv}", hivd, "", f"🔗 Részletek: {url}"]
    else:
        sorok = [st.cim, st.bevezeto, "", reszlet["cim"], f"{kat['label']} · {szerv}", "", url]
    if st.zaro:
        sorok += ["", st.zaro]
    return "\n".join(sor for sor in sorok if sor is not None)


def lezart_poszt_szoveg(tipus):
    szoveg = LEZARVA_SZOVEG.get(tipus, LEZARVA_JARMU)
    return f"✅ FRISSÍTÉS – LEZÁRVA\n\n{szoveg}\n\n#Csepel #Pesterzsébet #Soroksár #Szigetszentmiklós"


def lezart_posztok_javitasa(cache):
    """A kiposztolt körözések adatlapját újra megnézi; ha a police.hu már
    "Az oldal nem található" (404) választ ad, a posztot átírja."""
    posztok = cache.setdefault("fb_posztok", {})
    most = datetime.now(timezone.utc)
    for url, info in list(posztok.items()):
        try:
            if most - datetime.fromisoformat(info["datum"]) > timedelta(days=KOVETES_NAP):
                del posztok[url]
                continue
            resp = requests.get(url, headers=HEADERS, timeout=20)
        except Exception as e:
            print(f"   ⚠️  Követés-hiba ({url}): {e}")
            continue
        if resp.status_code != 404:
            info["hiany"] = 0
            continue
        info["hiany"] = info.get("hiany", 0) + 1
        if info["hiany"] < LEZARAS_404_SZAM:
            continue
        print(f"   ✅ Lekerült a police.hu-ról, poszt javítása: {url}")
        if not (MAKE_WEBHOOK_AKTIV and MAKE_KEPES_FORGATOKONYV) or facebook_post(lezart_poszt_szoveg(info["tipus"]), post_id=info["post_id"]):
            del posztok[url]
        time.sleep(1)


# =====================================================================
# EMAIL KÜLDÉS
# =====================================================================

def smtp_email_kuldes(host, port, felhasznalo, jelszo, cimzett, tema, torzs_html):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart("alternative")
    msg["Subject"] = tema
    msg["From"] = felhasznalo
    msg["To"] = cimzett
    msg.attach(MIMEText(torzs_html, "html", "utf-8"))

    with smtplib.SMTP_SSL(host, port, timeout=20) as server:
        server.login(felhasznalo, jelszo)
        server.sendmail(felhasznalo, [cimzett], msg.as_string())


# =====================================================================
# GYORSÍTÓTÁR
# =====================================================================

def gyorsitotar_betoltese():
    if os.path.exists(DATA_FAJL):
        with open(DATA_FAJL, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"korozes": {}, "hirek": {}}


def gyorsitotar_mentese(adat):
    os.makedirs(os.path.dirname(DATA_FAJL), exist_ok=True)
    with open(DATA_FAJL, "w", encoding="utf-8") as f:
        json.dump(adat, f, ensure_ascii=False, indent=2)


# =====================================================================
# FŐ LOGIKA
# =====================================================================

def main():
    cache = gyorsitotar_betoltese()
    elso_futas = not os.path.exists(DATA_FAJL)
    uj_lekerdezes_szamlalo = 0

    talalt_ertesitesek = []

    for kulcs, kat in KOROZES_KATEGORIAK.items():
        print(f"🔍 Körözés: {kat['label']}...")
        cache["korozes"].setdefault(kulcs, [])
        latott_idk = set(cache["korozes"][kulcs])

        try:
            lista = korozes_lista_lekerdezese(kat["list_path"])
        except Exception as e:
            print(f"   ⚠️  Hiba a lista lekérdezésekor: {e}")
            continue

        for elem in lista:
            if elem["id"] in latott_idk:
                continue

            if elso_futas:
                cache["korozes"][kulcs].append(elem["id"])
                continue

            if uj_lekerdezes_szamlalo >= MAX_UJ_RESZLET_LEKERDEZES:
                # Elértük a lekérdezési limitet ebben a futásban - NEM jelöljük
                # látottnak, hogy a következő futás újra megpróbálja (ne vesszen el).
                print(f"   ⏳ Limit elérve, később újrapróbáljuk: {elem['id']}")
                continue

            try:
                reszlet = korozes_reszlet_lekerdezese(elem["url"])
                uj_lekerdezes_szamlalo += 1
                time.sleep(0.3)
            except Exception as e:
                print(f"   ⚠️  Részlet-hiba ({elem['url']}): {e}")
                # Hálózati/parszolási hiba esetén se jelöljük látottnak,
                # hogy legközelebb újra megpróbáljuk.
                continue

            # Csak most, sikeres részlet-lekérdezés után jelöljük látottnak,
            # hogy a limit vagy hiba miatt kihagyott elemek ne vesszenek el örökre.
            cache["korozes"][kulcs].append(elem["id"])

            egyezo_szerv = korozes_szerv_egyezik(reszlet["mezok"])
            if not egyezo_szerv:
                continue

            print(f"   🎯 Találat: {reszlet['cim']} ({egyezo_szerv})")

            mezok_html = "".join(
                f"<p><strong>{k}:</strong> {v}</p>" for k, v in reszlet["mezok"].items() if v
            )
            # Az emailben mindig minden adat (név, fénykép, mezők) szerepel -
            # ez a szűrésre feliratkozott, megbízható címzettnek szól.
            torzs = (
                f"<h2>{reszlet['cim']}</h2>"
                f"<p><em>Kategória: {kat['label']} · Egyező szerv: {egyezo_szerv}</em></p>"
                + (f'<img src="{reszlet["kep"]}" style="max-width:300px;"><br>' if reszlet["kep"] else "")
                + mezok_html
                + f'<p><a href="{elem["url"]}">Megnyitás a police.hu-n</a></p>'
            )

            # A Facebook-poszt (nyilvános felület!) más elbírálás alá esik:
            # "elfogatóparancs alapján körözött személy" esetén - mivel ez egy
            # élő, még el nem ítélt, valódi ember személyes adata - sem a nevét,
            # sem a fényképét NEM tesszük ki nyilvánosan, csak a szervet és a
            # police.hu-s hivatkozást (ott, bejelentkezés nélkül is, megnézhető
            # a teljes, hivatalos közlemény). Minden más kategóriánál (eltűnt
            # személy, jármű-/légi-/vízijármű-körözés, holttest) ez a
            # korlátozás nem indokolt, ott a korábbi, teljes tartalom marad.
            fb_szoveg = korozes_poszt_szoveg(kulcs, kat, reszlet, egyezo_szerv, elem["url"])
            fb_kep = KEP_KOROZES
            fb_link = elonezet_link(ATIRANYITO_KOROZES, elem["url"])

            talalt_ertesitesek.append({
                "tema": f"[Körözés] {reszlet['cim']}",
                "torzs": torzs,
                "kep": reszlet["kep"],
                "fb_szoveg": fb_szoveg,
                "fb_kep": fb_kep,
                "fb_link": fb_link,
                "facebook_post": kat["facebook_post"],
                "kovetes": {"url": elem["url"], "tipus": kulcs},
            })

    ertesitett_hir_urlk = set()    # ugyanaz a cikk több kategóriában is szerepelhet - csak egyszer értesítünk róla
    hirek_kategoria_hibak = 0      # hány hír-kategória lekérdezése dobott hibát
    hirek_kategoria_uresek = 0     # hány hír-kategória adott 0 cikket (hiba nélkül)
    for kulcs, kat in HIREK_KATEGORIAK.items():
        print(f"🔍 Hírek: {kat['label']}...")
        cache["hirek"].setdefault(kulcs, [])
        latott_urlk = set(cache["hirek"][kulcs])
        # KATEGÓRIA-SZINTŰ alapállapot: ha ehhez a kategóriához még SOHA nem
        # mentettünk egyetlen cikket sem (pl. mert a korábbi, hibás kinyerés
        # mindig 0-t adott - így maradt üres mind a 10), akkor az első
        # sikeres lekérdezés csendben alapállapotot ment, NEM küld emailt
        # a teljes aktuális oldalról. (A fájl-szintű "elso_futas" ezt nem
        # fedi le, mert a fájl már régóta létezik.)
        kategoria_elso_futas = elso_futas or not latott_urlk

        try:
            cikkek = hirek_lista_lekerdezese(kat["list_path"])
        except Exception as e:
            print(f"   ⚠️  Hiba a lista lekérdezésekor: {e}")
            hirek_kategoria_hibak += 1
            continue

        if not cikkek:
            hirek_kategoria_uresek += 1
        elif kategoria_elso_futas and not elso_futas:
            print(f"   🌱 Alapállapot ehhez a kategóriához: {len(cikkek)} cikk elmentve, email nem megy.")

        for cikk in cikkek:
            if cikk["url"] in latott_urlk:
                continue
            cache["hirek"][kulcs].append(cikk["url"])

            if kategoria_elso_futas:
                continue

            if not hirek_egyezik(cikk):
                continue
            if cikk["url"] in ertesitett_hir_urlk:
                continue
            ertesitett_hir_urlk.add(cikk["url"])

            print(f"   🎯 Találat: {cikk['cim']}")

            torzs = (
                f"<h2>{cikk['cim']}</h2>"
                f"<p><em>Kategória: {kat['label']}</em></p>"
                f"<p>{cikk['osszefoglalo']}</p>"
                f'<p><a href="{cikk["url"]}">Megnyitás a police.hu-n</a></p>'
            )
            talalt_ertesitesek.append({
                "tema": f"[Hír] {cikk['cim']}",
                "torzs": torzs,
                "kep": None,
                "fb_szoveg": f"{(st := Stilus('rendorseg')).cim}\n{st.bevezeto}\n\n{cikk['cim']}\n\n{cikk['osszefoglalo']}\n\n🔗 {cikk['url']}",
                "fb_kep": KEP_HIR,
                "fb_link": elonezet_link(ATIRANYITO_HIR, cikk["url"]),
                "facebook_post": kat["facebook_post"],
            })

    # ------------------------------------------------------------------
    # EGÉSZSÉG-ŐR ("néma hiba" ellen): eddig, ha a police.hu átalakította az
    # oldalát, a script zölden, hiba nélkül futott tovább, 0 találattal -
    # és soha egyetlen email sem jött. Most ha az ÖSSZES hír-kategória
    # egymás után HIRDEK_RIASZTAS_UTANI_FUTAS alkalommal 0 cikket (vagy hibát)
    # ad, figyelmeztető emailt küldünk (legfeljebb naponta egyet).
    # ------------------------------------------------------------------
    egeszseg = cache.setdefault("_egeszseg", {})
    mind_ures = (hirek_kategoria_hibak + hirek_kategoria_uresek) >= len(HIREK_KATEGORIAK)
    egeszseg["hirek_ures_egymas_utan"] = (egeszseg.get("hirek_ures_egymas_utan", 0) + 1) if mind_ures else 0
    riasztas_kell = False
    if egeszseg["hirek_ures_egymas_utan"] >= HIREK_RIASZTAS_UTANI_FUTAS:
        utolso = egeszseg.get("utolso_riasztas")
        try:
            utolso_dt = datetime.fromisoformat(utolso) if utolso else None
        except ValueError:
            utolso_dt = None
        if utolso_dt is None or (datetime.now(timezone.utc) - utolso_dt) > timedelta(hours=24):
            riasztas_kell = True
            egeszseg["utolso_riasztas"] = datetime.now(timezone.utc).isoformat()

    if cache.get("fb_posztok"):
        print("🔍 Kiposztolt körözések ellenőrzése...")
        lezart_posztok_javitasa(cache)

    gyorsitotar_mentese(cache)

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    email_kuldo = os.environ.get("EMAIL_KULDO", "")
    email_jelszo = os.environ.get("EMAIL_JELSZO", "")
    email_cimzett = os.environ.get("EMAIL_CIMZETT", "")
    smtp_kesz = bool(email_kuldo and email_jelszo and email_cimzett)

    if riasztas_kell:
        print(f"\n🚨 A hír-figyelés {egeszseg['hirek_ures_egymas_utan']} futás óta egyetlen cikket sem lát - figyelmeztetés küldése.")
        if smtp_kesz:
            try:
                smtp_email_kuldes(
                    smtp_host, smtp_port, email_kuldo, email_jelszo, email_cimzett,
                    "⚠️ Police.hu figyelő: a HÍREK-figyelés nem lát egyetlen cikket sem",
                    "<h2>A police.hu hírfigyelő nem működik megfelelően</h2>"
                    f"<p>Az utolsó <strong>{egeszseg['hirek_ures_egymas_utan']}</strong> futásban mind a "
                    f"{len(HIREK_KATEGORIAK)} hír-kategória 0 cikket adott vissza (vagy hibát dobott) - "
                    "valószínűleg a police.hu megváltoztatta az oldal szerkezetét, vagy letiltja a "
                    "GitHub-os lekérdezéseket. Amíg ez így van, hír-értesítő NEM érkezik. "
                    "A körözési rész ettől független.</p>"
                    "<p>Részletek: GitHub → Actions → 'Police.hu Figyelő' → legutóbbi futás naplója "
                    "('🔎 DIAGNOSZTIKA' sorok).</p>",
                )
            except Exception as e:
                print(f"   ⚠️  Figyelmeztető email küldési hiba: {e}")

    if elso_futas:
        print(f"\n✅ Első futás - alapállapot elmentve ({sum(len(v) for v in cache['korozes'].values())} körözés, "
              f"{sum(len(v) for v in cache['hirek'].values())} hír). Email nem ment.")
        return

    if not talalt_ertesitesek:
        print("\n✅ Nincs új, releváns találat ebben a körben.")
        if MAKE_WEBHOOK_AKTIV:
            varolista_kuldese(cache)
            gyorsitotar_mentese(cache)
        return

    print(f"\n📬 {len(talalt_ertesitesek)} új találat - értesítés küldése...")

    for ertesites in talalt_ertesitesek:
        if smtp_kesz:
            try:
                smtp_email_kuldes(smtp_host, smtp_port, email_kuldo, email_jelszo,
                                   email_cimzett, ertesites["tema"], ertesites["torzs"])
                print(f"   ✅ Email elküldve: {ertesites['tema']}")
            except Exception as e:
                print(f"   ⚠️  Email-küldési hiba: {e}")
        else:
            print("   ⚠️  Nincs beállítva SMTP - email kihagyva.")

        if MAKE_WEBHOOK_AKTIV and ertesites["facebook_post"]:
            cache.setdefault("fb_varolista", []).append({
                "fb_szoveg": ertesites["fb_szoveg"], "kep": ertesites["fb_kep"],
                "kovetes": ertesites.get("kovetes"), "link": ertesites.get("fb_link"),
                "felvetel": datetime.now(timezone.utc).isoformat()})

        time.sleep(1)

    if MAKE_WEBHOOK_AKTIV:
        varolista_kuldese(cache)
    gyorsitotar_mentese(cache)


if __name__ == "__main__":
    main()
