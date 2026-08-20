#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POLICE.HU FIGYELŐ
==================================================================
Figyeli a police.hu körözési rendszerét és hírfolyamát, és értesít
minden ÚJ bejegyzésről, ami a XX./XXI. kerülethez kapcsolódik.

- Körözések (koral): az "Elrendelő szerv" / "Eljáró szerv" mezőben
  keresi a megadott szervezeteket.
- Hírek: a címben/összefoglalóban keresi a "XX. kerület"/"XXI. kerület"/
  "XX. KER"/"XXI. KER" mintát (pontos illesztés, "XXI. század"-szerű
  hamis találatok nélkül).

MINDEN KATEGÓRIÁNÁL külön beállítható a 'facebook_post' jelző - ha
True, az adott kategória új találatai a Facebook Oldalra is
automatikusan kikerülnek email mellett.
"""

import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup

# =====================================================================
# BEÁLLÍTÁS
# =====================================================================

BASE_URL = "https://www.police.hu"
DATA_FAJL = "korozes/data/police_figyelo.json"
MAX_UJ_RESZLET_LEKERDEZES = 40  # egy futásban max ennyi ÚJ elem részletét kérdezzük le

# A körözési rendszerben ezekre a szervekre szűrünk (Elrendelő VAGY Eljáró szerv mezőben)
KOROZES_SZERV_SZURO = [
    "BUDAPESTI XXI. KER. RK",
    "BUDAPESTI XX-XXIII. KER. RK",
    "Budapesti XX., XXI. és XXIII. Kerületi Bíróság",
]

# A hírekben erre a mintára szűrünk (kerület-jelölés, "XXI. század"-szerű hamis
# találatok elkerülésével - csak akkor egyezik, ha utána KER/kerület áll)
HIREK_MINTA = re.compile(r"XX\.?\s*(KER|kerület)|XXI\.?\s*(KER|kerület)", re.IGNORECASE)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PoliceHuFigyelo/1.0)"}

# ---------------------------------------------------------------------
# KÖRÖZÉSI KATEGÓRIÁK
# 'facebook_post': True esetén ennek a kategóriának az új találatai
# a Facebook Oldalra is automatikusan kikerülnek email mellett.
# ---------------------------------------------------------------------
KOROZES_KATEGORIAK = {
    "eltunt_szemelyek": {
        "label": "Eltűnt, ismeretlen helyen lévő személy",
        "list_path": "/hu/koral/eltunt-szemelyek",
        "facebook_post": False,
    },
    "korozott_szemelyek": {
        "label": "Elfogatóparancs alapján körözött személy",
        "list_path": "/hu/koral/elfogatoparancs-alapjan-korozott-szemelyek",
        "facebook_post": False,
    },
    "holttest_korozes": {
        "label": "Ismeretlen holttest/holttestrész körözés",
        "list_path": "/hu/koral/holttest-holttestresz-korozesek",
        "facebook_post": False,
    },
    "jarmu_korozes": {
        "label": "Közúti jármű körözés",
        "list_path": "/hu/koral/kozutijarmu-korozesek",
        "facebook_post": False,
    },
    "legijarmu_korozes": {
        "label": "Légi jármű körözés",
        "list_path": "/hu/koral/legijarmu-korozesek",
        "facebook_post": False,
    },
    "vizijarmu_korozes": {
        "label": "Vízi jármű körözés",
        "list_path": "/hu/koral/vizijarmu-korozesek",
        "facebook_post": False,
    },
}

# ---------------------------------------------------------------------
# HÍR KATEGÓRIÁK
# ---------------------------------------------------------------------
HIREK_KATEGORIAK = {
    "legfrissebb": {
        "label": "Legfrissebb híreink",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink",
        "facebook_post": False,
    },
    "szervezeti_hirek": {
        "label": "Szervezeti hírek",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/szervezeti-hirek",
        "facebook_post": False,
    },
    "helyi_hirek": {
        "label": "Helyi hírek",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/helyi-hirek",
        "facebook_post": False,
    },
    "bunugyek": {
        "label": "Bűnügyek",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/bunugyek",
        "facebook_post": False,
    },
    "felhivasok": {
        "label": "Felhívások",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/felhivasok",
        "facebook_post": False,
    },
    "dijkituzesek": {
        "label": "Díjkitűzések",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/dijkituzesek",
        "facebook_post": False,
    },
    "kozrendvedelem": {
        "label": "Közrendvédelem",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/kozrendvedelem",
        "facebook_post": False,
    },
    "kozlekedesrendeszet": {
        "label": "Közlekedésrendészet",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/kozlekedesrendeszet",
        "facebook_post": False,
    },
    "igazgatasrendeszet": {
        "label": "Igazgatásrendészet",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/igazgatasrendeszet",
        "facebook_post": False,
    },
    "hatarrendeszet": {
        "label": "Határrendészet",
        "list_path": "/hu/hirek-es-informaciok/legfrissebb-hireink/hatarrendeszet",
        "facebook_post": False,
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
        talalatok.append({"id": item_id, "cim": cim, "url": BASE_URL + href})

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

    kep_meta = soup.find("meta", attrs={"property": "og:image"})
    kep_url = kep_meta["content"] if kep_meta and kep_meta.get("content") else ""

    h1 = soup.find("h1")
    cim = h1.get_text(" ", strip=True) if h1 else ""

    return {"cim": cim, "kep": kep_url, "mezok": mezok}


def korozes_szerv_egyezik(mezok):
    ellenorzendo_mezok = [
        v for k, v in mezok.items()
        if "elrendelő szerv" in k.lower() or "eljáró szerv" in k.lower()
    ]
    szoveg = " ".join(ellenorzendo_mezok).upper()
    for szerv in KOROZES_SZERV_SZURO:
        if szerv.upper() in szoveg:
            return szerv
    return None


# =====================================================================
# HÍRFOLYAM FELDOLGOZÁSA
# =====================================================================

def hirek_lista_lekerdezese(list_path):
    url = BASE_URL + list_path
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cikkek = []
    seen_urls = set()
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


def hirek_egyezik(cikk):
    szoveg = cikk["cim"] + " " + cikk["osszefoglalo"]
    return bool(HIREK_MINTA.search(szoveg))


# =====================================================================
# FACEBOOK POSZTOLÁS (Graph API)
# =====================================================================

def facebook_post(uzenet, kep_url=None):
    """Szükséges env változók: FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN"""
    page_id = os.environ.get("FB_PAGE_ID", "")
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    if not page_id or not token:
        print("      ⚠️  Nincs beállítva FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN, Facebook-posztolás kihagyva.")
        return False

    try:
        if kep_url:
            url = f"https://graph.facebook.com/v21.0/{page_id}/photos"
            payload = {"url": kep_url, "caption": uzenet, "access_token": token}
        else:
            url = f"https://graph.facebook.com/v21.0/{page_id}/feed"
            payload = {"message": uzenet, "access_token": token}

        resp = requests.post(url, data=payload, timeout=20)
        if resp.status_code == 200:
            print("      ✅ Facebook poszt sikeres.")
            return True
        else:
            print(f"      ⚠️  Facebook poszt sikertelen (HTTP {resp.status_code}): {resp.text[:300]}")
            return False
    except Exception as e:
        print(f"      ⚠️  Facebook poszt hiba: {e}")
        return False


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
            cache["korozes"][kulcs].append(elem["id"])

            if elso_futas:
                continue

            if uj_lekerdezes_szamlalo >= MAX_UJ_RESZLET_LEKERDEZES:
                continue

            try:
                reszlet = korozes_reszlet_lekerdezese(elem["url"])
                uj_lekerdezes_szamlalo += 1
                time.sleep(0.3)
            except Exception as e:
                print(f"   ⚠️  Részlet-hiba ({elem['url']}): {e}")
                continue

            egyezo_szerv = korozes_szerv_egyezik(reszlet["mezok"])
            if not egyezo_szerv:
                continue

            print(f"   🎯 Találat: {reszlet['cim']} ({egyezo_szerv})")

            mezok_html = "".join(
                f"<p><strong>{k}:</strong> {v}</p>" for k, v in reszlet["mezok"].items() if v
            )
            torzs = (
                f"<h2>{reszlet['cim']}</h2>"
                f"<p><em>Kategória: {kat['label']} · Egyező szerv: {egyezo_szerv}</em></p>"
                + (f'<img src="{reszlet["kep"]}" style="max-width:300px;"><br>' if reszlet["kep"] else "")
                + mezok_html
                + f'<p><a href="{elem["url"]}">Megnyitás a police.hu-n</a></p>'
            )
            talalt_ertesitesek.append({
                "tema": f"[Körözés] {reszlet['cim']}",
                "torzs": torzs,
                "kep": reszlet["kep"],
                "fb_szoveg": f"{reszlet['cim']}\n\n{kat['label']} · {egyezo_szerv}\n\n{elem['url']}",
                "facebook_post": kat["facebook_post"],
            })

    for kulcs, kat in HIREK_KATEGORIAK.items():
        print(f"🔍 Hírek: {kat['label']}...")
        cache["hirek"].setdefault(kulcs, [])
        latott_urlk = set(cache["hirek"][kulcs])

        try:
            cikkek = hirek_lista_lekerdezese(kat["list_path"])
        except Exception as e:
            print(f"   ⚠️  Hiba a lista lekérdezésekor: {e}")
            continue

        for cikk in cikkek:
            if cikk["url"] in latott_urlk:
                continue
            cache["hirek"][kulcs].append(cikk["url"])

            if elso_futas:
                continue

            if not hirek_egyezik(cikk):
                continue

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
                "fb_szoveg": f"{cikk['cim']}\n\n{cikk['osszefoglalo']}\n\n{cikk['url']}",
                "facebook_post": kat["facebook_post"],
            })

    gyorsitotar_mentese(cache)

    if elso_futas:
        print(f"\n✅ Első futás - alapállapot elmentve ({sum(len(v) for v in cache['korozes'].values())} körözés, "
              f"{sum(len(v) for v in cache['hirek'].values())} hír). Email nem ment.")
        return

    if not talalt_ertesitesek:
        print("\n✅ Nincs új, releváns találat ebben a körben.")
        return

    print(f"\n📬 {len(talalt_ertesitesek)} új találat - értesítés küldése...")

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    email_kuldo = os.environ.get("EMAIL_KULDO", "")
    email_jelszo = os.environ.get("EMAIL_JELSZO", "")
    email_cimzett = os.environ.get("EMAIL_CIMZETT", "")

    for ertesites in talalt_ertesitesek:
        if email_kuldo and email_jelszo and email_cimzett:
            try:
                smtp_email_kuldes(smtp_host, smtp_port, email_kuldo, email_jelszo,
                                   email_cimzett, ertesites["tema"], ertesites["torzs"])
                print(f"   ✅ Email elküldve: {ertesites['tema']}")
            except Exception as e:
                print(f"   ⚠️  Email-küldési hiba: {e}")
        else:
            print("   ⚠️  Nincs beállítva SMTP - email kihagyva.")

        if ertesites["facebook_post"]:
            facebook_post(ertesites["fb_szoveg"], ertesites["kep"])

        time.sleep(1)


if __name__ == "__main__":
    main()
