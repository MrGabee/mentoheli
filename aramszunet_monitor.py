"""
⚡ E.ON Áramszünet Monitor – Csepel (XXI.) + Pesterzsébet (XX.)
   + Szigetszentmiklós
Szűrés: city mező (kerület-azonosító vagy településnév) + polygon
"""

import os
import json
import hashlib
import smtplib
import requests

import poszt_valtozatos
import ejszakai_sor
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from poszt_valtozatos import Stilus
import email_arculat as ea

from zoneinfo import ZoneInfo
MAGYAR_TZ = ZoneInfo("Europe/Budapest")

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT_ARAM"]
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")

# ⬇️ E-MAIL KAPCSOLÓ: Gábor kérésére (2026.10.21.) az oldalra szánt értesítések
# nem mennek e-mailben (a kollégája kapta őket). A Facebook-posztolás marad.
# 2026.10.28.: Gábor kérésére újra megy, a kollégának (EMAIL_CIMZETT_ARAM).
EMAIL_AKTIV = True

# ⬇️⬇️⬇️ ITT KAPCSOLOD KI/BE AZ AUTOMATA FACEBOOK-POSZTOLÁST ⬇️⬇️⬇️
# True  = automatikusan posztol a Facebook Oldalra is, egy Make.com
#         automatizáción keresztül (webhook -> Facebook Pages modul) -
#         ehhez csak egy érvényes MAKE_WEBHOOK_URL GitHub Secret kell,
#         Meta fejlesztői app / token NEM szükséges hozzá.
# False = csak emailt küld, a Facebook-szöveg ott lesz kimásolható
FACEBOOK_POSZTOLAS_AKTIV = True

API_TERVEZETT = "https://www.eon.hu/content/dam/eon/eon-hungary/external-app-data/outages/poweroutage.json"
API_UZEMZAVAR = "https://www.eon.hu/content/dam/eon/eon-hungary/external-app-data/outages/unexpectedoutage.json"

ALLAPOT_FAJL = "aramszunet_allapot.json"

# Ide írd be a saját rajzolt képed URL-jét, ha van - a Facebook-posztba
# automatikusan bekerül a másolható szöveg alá. Ha nincs kép, hagyd üresen.
KEP_URL = "https://mrgabee.hu/aramszunet.png"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.eon.hu/",
}

NOMINATIM_HEADERS = {
    "User-Agent": "BalesetinfoAramszunetMonitor/1.0 (baleset-info.hu)"
}


# ════════════════════════════════════════════
#  💾  ÁLLAPOT
# ════════════════════════════════════════════
def betolt_allapot():
    if os.path.exists(ALLAPOT_FAJL):
        try:
            with open(ALLAPOT_FAJL) as f:
                return json.load(f)
        except Exception:
            pass
    return {"tervezett": {}, "uzemzavar": {}}

def ment_allapot(allapot):
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=2)

def hash_id(szoveg):
    return hashlib.md5(szoveg.encode("utf-8")).hexdigest()[:12]


# ════════════════════════════════════════════
#  🗺️  NOMINATIM REVERSE GEOCODING
# ════════════════════════════════════════════
def reverse_geocode(lat, lon):
    """Koordinátából utca nevet kér le Nominatim-tól (ingyenes, OSM alapú)."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&zoom=17"
        r = requests.get(url, headers=NOMINATIM_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            addr = data.get("address", {})
            road     = addr.get("road") or addr.get("pedestrian") or addr.get("path") or ""
            suburb   = addr.get("suburb") or addr.get("neighbourhood") or ""
            if road:
                return road
            elif suburb:
                return f"({suburb} körzetben)"
    except Exception as ex:
        print(f"  ⚠️ Nominatim hiba: {ex}")
    return None


# ════════════════════════════════════════════
#  📍  SZŰRŐ – Csepel (XXI.) + Pesterzsébet (XX.)
#      + Szigetszentmiklós (önálló település, nincs kerület-száma)
# ════════════════════════════════════════════

TERULETEK = [
    # (regex-minta a "city" mezőre vagy None, ha nincs kerület-szám; kulcsszó; megjelenítendő címke)
    # Szigetszentmiklós előrébb van, mert "Csepel-sziget" földrajzi kifejezés
    # tartalmazhatja a "csepel" szót, és azt nem szeretnénk tévesen XXI.-nek venni.
    (None,        "szigetszentmiklós", "Szigetszentmiklós"),
    (r'\bXXI\b',  "csepel",           "XXI. kerület (Csepel)"),
    (r'\bXX\b',   "pesterzsébet",     "XX. kerület (Pesterzsébet)"),
]


def kerulet_cimke(city):
    """Visszaadja a megjelenítendő terület-címkét, ha a city mező egyezik
    valamelyik figyelt kerülettel/településsel, egyébként None-t."""
    c = str(city or "").strip()
    c_lower = c.lower()
    import re
    for minta, kulcsszo, cimke in TERULETEK:
        if (minta and re.search(minta, c)) or kulcsszo in c_lower:
            return cimke
    return None


def erintett_kerulet(eset):
    """Megkeresi az esethez tartozó kerület-címkét (addressRanges-ből vagy
    a fő city mezőből), vagy None-t ad, ha egyik figyelt kerülettel sem egyezik."""
    for ar in eset.get("addressRanges", []):
        if isinstance(ar, dict):
            cimke = kerulet_cimke(ar.get("city", ""))
            if cimke:
                return cimke

    cimke = kerulet_cimke(eset.get("city", ""))
    if cimke:
        return cimke

    return None


def csepel_e(eset):
    """Megtartva kompatibilitásból: True, ha bármelyik figyelt kerülettel egyezik."""
    return erintett_kerulet(eset) is not None


# ════════════════════════════════════════════
#  🕐  IDŐPONT FORMÁZÁS
# ════════════════════════════════════════════
def ido_format(mezo):
    if not mezo:
        return "—"
    if isinstance(mezo, dict):
        datum = mezo.get("date") or ""
        ido   = mezo.get("time") or ""
        if datum and ido:
            return f"{datum} {ido}"
        return datum or ido or str(mezo)
    if isinstance(mezo, (int, float)):
        try:
            dt = datetime.fromtimestamp(mezo / 1000 if mezo > 1e10 else mezo, tz=timezone.utc)
            dt = dt.astimezone(MAGYAR_TZ)
            return dt.strftime("%Y.%m.%d %H:%M")
        except Exception:
            return str(mezo)
    # String formátum – pl. "2026-07-04 15:41:21" vagy "2026-07-04T15:41:21Z"
    s = str(mezo).replace("T", " ").replace("Z", "").strip()[:19]
    try:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc).astimezone(MAGYAR_TZ)
        return dt.strftime("%Y.%m.%d %H:%M")
    except Exception:
        try:
            dt = datetime.strptime(s, "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=timezone.utc).astimezone(MAGYAR_TZ)
            return dt.strftime("%Y.%m.%d %H:%M")
        except Exception:
            return s


def parse_datetime_raw(mezo):
    """Ugyanazt a bemenetet dolgozza fel, mint az ido_format(), de VALÓDI
    datetime objektumot ad vissza (magyar időzónában), nem szöveget - ez
    kell az 'X nappal a kezdés előtt' összehasonlításhoz. Ha nem
    értelmezhető, None-t ad."""
    if not mezo:
        return None
    if isinstance(mezo, dict):
        datum = mezo.get("date") or ""
        ido   = mezo.get("time") or ""
        mezo  = f"{datum} {ido}".strip() if (datum or ido) else None
        if not mezo:
            return None
    if isinstance(mezo, (int, float)):
        try:
            dt = datetime.fromtimestamp(mezo / 1000 if mezo > 1e10 else mezo, tz=timezone.utc)
            return dt.astimezone(MAGYAR_TZ)
        except Exception:
            return None
    s = str(mezo).replace("T", " ").replace("Z", "").strip()[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc).astimezone(MAGYAR_TZ)
        except Exception:
            continue
    return None


# ════════════════════════════════════════════
#  📡  LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez_json(url, tipus):
    try:
        print(f"📡 {tipus}: {url}")
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ HTTP {r.status_code}")
            return []
        data = r.json()
        esetek = data.get("outages", []) if isinstance(data, dict) else data
        print(f"  📊 Összes: {len(esetek)}")
        csepel = [{"tipus": tipus, "adat": e, "url": url} for e in esetek if csepel_e(e)]
        print(f"  🎯 Csepel: {len(csepel)}")
        return csepel
    except Exception as ex:
        print(f"  ❌ {ex}")
        return []


# ════════════════════════════════════════════
#  📋  ADATOK KINYERÉSE
# ════════════════════════════════════════════
def kinyert_adatok(eset):
    a     = eset["adat"]
    tipus = eset["tipus"]
    kerulet = erintett_kerulet(a) or "ismeretlen kerület"

    if tipus == "TERVEZETT":
        intervals  = a.get("intervals", [])
        elso       = intervals[0] if intervals and isinstance(intervals[0], dict) else {}
        kezdes_raw = elso.get("from") or elso.get("start")
        veg_raw    = elso.get("to")   or elso.get("end")
    else:
        kezdes_raw = a.get("from") or a.get("startTime")
        veg_raw    = a.get("to")   or a.get("endTime")

    # Koordináta
    coords = a.get("coordinates") or a.get("transformerAreaCenterCoordinates") or {}
    lat = coords.get("lat") if isinstance(coords, dict) else None
    lon = coords.get("lng") or coords.get("lon") if isinstance(coords, dict) else None
    if lat == 0.0: lat = None
    if lon == 0.0: lon = None

    # Ha nincs koordináta a fő mezőben, transformer koordinátát próbáljuk
    if not lat or not lon:
        tc = a.get("transformerAreaCenterCoordinates") or {}
        if isinstance(tc, dict):
            lat = tc.get("lat") or lat
            lon = tc.get("lng") or tc.get("lon") or lon
            if lat == 0.0: lat = None
            if lon == 0.0: lon = None

    # Utca lista az addressRanges-ből - MINDEN sor külön marad, úgy ahogy
    # az E.ON kiadta, nincs összevonás, nincs limit (akár 30 sor is lehet).
    def tiszta_hazszam(nyers):
        if not nyers:
            return ""
        return str(nyers).split("HRSZ")[0].strip()

    utcak_lista = []
    for ar in a.get("addressRanges", []):
        if isinstance(ar, dict):
            city   = ar.get("city", "")
            street = ar.get("street", "") or ar.get("streetName", "")
            # A valódi E.ON mezőnevek: startNum / endNum (élőben ellenőrizve).
            # A startNum gyakran "13  HRSZ:214146" formában jön - a HRSZ
            # (helyrajzi szám) részt levágjuk, csak a tiszta házszám kell.
            from_n = tiszta_hazszam(ar.get("startNum", "") or ar.get("fromNumber", "") or ar.get("houseNumberFrom", ""))
            to_n   = tiszta_hazszam(ar.get("endNum", "")   or ar.get("toNumber", "")   or ar.get("houseNumberTo", ""))
            if street:
                sor = f"{city} {street}".strip()
                if from_n and to_n and from_n != to_n:
                    sor += f" {from_n}-{to_n}"
                elif from_n:
                    sor += f" {from_n}"
                utcak_lista.append(sor)

    # "utcak" - minden cím saját sorában (nem összevonva, nem levágva)
    utcak = "\n".join(utcak_lista) if utcak_lista else (a.get("city") or "—")

    # Ha nincs utca (üzemzavar esetén tipikus), Nominatim-tól kérjük le
    nominatim_utca = None
    if (not utcak_lista) and lat and lon:
        nominatim_utca = reverse_geocode(lat, lon)
        if nominatim_utca:
            utcak = f"Budapest {kerulet} - {nominatim_utca} (közelében)"
            print(f"  🗺️ Nominatim: {utcak}")

    consumers = a.get("consumers", {})
    fogyaszto = consumers.get("total") if isinstance(consumers, dict) else str(consumers) if consumers else "—"

    azonosito = a.get("id") or a.get("internalId") or "—"
    gmaps = f"https://www.google.com/maps?q={lat},{lon}&z=15" if lat and lon else None

    return {
        "azonosito":      str(azonosito),
        "kezdes":         ido_format(kezdes_raw),
        "kezdes_dt":      parse_datetime_raw(kezdes_raw),
        "veg":            ido_format(veg_raw),
        "utcak":          utcak,
        "utcak_lista":    utcak_lista,
        "nominatim_utca": nominatim_utca,
        "fogyaszto":      str(fogyaszto),
        "gmaps":          gmaps,
        "tipus":          tipus,
        "lat":            lat,
        "lon":            lon,
        "kerulet":        kerulet,
    }


# ════════════════════════════════════════════
#  📘  FACEBOOK POSZT SZÖVEG
# ════════════════════════════════════════════
def facebook_szoveg(uj_adatok, osszes_aktiv_adatok, ido):
    db_uj = len(uj_adatok)

    erintett_keruletek = sorted(set(f["kerulet"] for f in uj_adatok))
    tobb_kerulet = len(erintett_keruletek) > 1
    st = Stilus("aramszunet")

    sorok = [
        st.cim,
        f"🕒 {ido}   •   {db_uj} új esemény",
        st.vonal(),
        "",
        st.bevezeto,
        "",
    ]

    # A kért bevezető mondat - jelezve, hogy nem csak Csepelről olvasnak minket
    sorok.append(
        "👋 Mivel nemcsak Csepelről, hanem a környező kerületekből és "
        "városokból (Pesterzsébet, Szigetszentmiklós) is sokan "
        "olvastok, mostantól ezekről a területekről is beszámolok, "
        "hogy senki ne maradjon le a fontos hírekről! 💙"
    )
    sorok.append("")

    def esemeny_blokk(f, tervezett):
        sor = []
        fejlec = "🔌 TERVEZETT" if tervezett else "🔴 ÉLŐ ÜZEMZAVAR"
        sor.append(f"{fejlec}  |  📌 {f['kerulet']}")
        if tervezett:
            sor.append(f"   📅 {f['kezdes'][:10] if f['kezdes'] != '—' else '—'}")
            kezdes_ido = f['kezdes'][11:] if len(f['kezdes']) > 10 else f['kezdes']
            veg_ido    = f['veg'][11:]    if len(f['veg'])    > 10 else f['veg']
            sor.append(f"   🕐 {kezdes_ido} → {veg_ido}")
        else:
            sor.append(f"   🕐 Kezdete: {f['kezdes']}")
        # Minden cím saját sorában, ahogy az E.ON kiadta - nincs összevonás
        if f["utcak_lista"]:
            for cim in f["utcak_lista"]:
                sor.append(f"   📍 {cim}")
        else:
            sor.append(f"   📍 {f['utcak']}")
        sor.append(f"   👥 Érintett: {f['fogyaszto']} fogyasztó")
        return "\n".join(sor)

    # Csoportosítás kerület szerint, hogy átlátható legyen, hol mi történik
    for kerulet in erintett_keruletek:
        keruleti_uj = [f for f in uj_adatok if f["kerulet"] == kerulet]
        sorok.append(st.terulet(kerulet.upper()))
        sorok.append(st.vekony())
        for f in keruleti_uj:
            sorok.append(esemeny_blokk(f, f["tipus"] == "TERVEZETT"))
            sorok.append("")

    # Összesítő - az összes jelenleg aktív üzemzavar tömören, kerület szerint
    aktiv_uzemzavar = [e for e in osszes_aktiv_adatok if e["tipus"] == "UZEMZAVAR"]
    if aktiv_uzemzavar:
        sorok.append(st.vonal())
        sorok.append(f"📋 ÖSSZES AKTÍV ÜZEMZAVAR  ({len(aktiv_uzemzavar)} db)")
        sorok.append(st.vekony())
        for f in aktiv_uzemzavar:
            utca = f["utcak"] or f["kerulet"]
            sorok.append(f"• [{f['kerulet']}] {utca}  |  {f['kezdes']}  |  {f['fogyaszto']} fogyasztó")
        sorok.append("")

    sorok.append(st.vekony())
    sorok.append("ℹ️ Forrás: E.ON nyilvános tájékoztatás")
    sorok.append("🤖 Automatikus értesítő – Baleset-info.hu")
    sorok.append("📍 Figyelt terület: Csepel, Pesterzsébet, Szigetszentmiklós")
    if st.zaro:
        sorok += ["", st.zaro]

    if KEP_URL:
        sorok.append("")
        sorok.append(KEP_URL)

    return "\n".join(sorok)


def facebook_szoveg_emlekezteto(emlekezteto_adatok, ido):
    """Az emlékeztető-posztokhoz tartozó FB-szöveg - explicit jelzi, hogy ez
    egy korábban már bejelentett áramszünetről szóló EMLÉKEZTETŐ, nem új
    esemény, hogy a követők ne értsék félre kétszeri bejelentésnek."""
    db = len(emlekezteto_adatok)
    erintett_keruletek = sorted(set(f["kerulet"] for f in emlekezteto_adatok))
    st = Stilus("aramszunet_emlekezteto")

    sorok = [
        st.cim,
        f"🕒 {ido}   •   {db} esemény",
        st.vonal(),
        "",
        st.bevezeto,
        "",
        "ℹ️ Ez egy emlékeztető korábban már bejelentett, tervezett "
        "áramszünet(ek)ről, amik hamarosan esedékesek:",
        "",
    ]

    def esemeny_blokk(f):
        nap = f.get("emlekezteto_nap")
        nap_cimke = f"{nap} nap múlva esedékes" if nap else "hamarosan esedékes"
        sor = [f"🔌 TERVEZETT  |  📌 {f['kerulet']}  |  ⏰ {nap_cimke.upper()}"]
        sor.append(f"   📅 {f['kezdes'][:10] if f['kezdes'] != '—' else '—'}")
        kezdes_ido = f['kezdes'][11:] if len(f['kezdes']) > 10 else f['kezdes']
        veg_ido    = f['veg'][11:]    if len(f['veg'])    > 10 else f['veg']
        sor.append(f"   🕐 {kezdes_ido} → {veg_ido}")
        if f["utcak_lista"]:
            for cim in f["utcak_lista"]:
                sor.append(f"   📍 {cim}")
        else:
            sor.append(f"   📍 {f['utcak']}")
        sor.append(f"   👥 Érintett: {f['fogyaszto']} fogyasztó")
        return "\n".join(sor)

    for kerulet in erintett_keruletek:
        keruleti = [f for f in emlekezteto_adatok if f["kerulet"] == kerulet]
        sorok.append(st.terulet(kerulet.upper()))
        sorok.append(st.vekony())
        for f in keruleti:
            sorok.append(esemeny_blokk(f))
            sorok.append("")

    sorok.append(st.vekony())
    sorok.append("ℹ️ Forrás: E.ON nyilvános tájékoztatás")
    sorok.append("🤖 Automatikus értesítő – Baleset-info.hu")
    sorok.append("📍 Figyelt terület: Csepel, Pesterzsébet, Szigetszentmiklós")
    if st.zaro:
        sorok += ["", st.zaro]

    if KEP_URL:
        sorok.append("")
        sorok.append(KEP_URL)

    return "\n".join(sorok)


# ════════════════════════════════════════════
#  📘  FACEBOOK AUTOMATA POSZTOLÁS (Make.com webhookon keresztül)
# ════════════════════════════════════════════
def facebook_poszt_kuldese(szoveg):
    """Szöveges posztot küld a Facebook Oldalra - nem közvetlenül a Meta
    Graph API-n keresztül, hanem egy Make.com automatizáción (Scenario)
    keresztül: ide küldünk egy egyszerű webhook-hívást a szöveggel, a
    Make.com pedig ezt posztolja ki a Facebook Oldalra. Ez elkerüli a
    Meta fejlesztői app / Business Portfolio beállítását."""
    if not MAKE_WEBHOOK_URL:
        print("  ⚠️  Nincs beállítva MAKE_WEBHOOK_URL - Facebook-posztolás kihagyva.")
        return False

    try:
        resp = requests.post(MAKE_WEBHOOK_URL, json={"message": poszt_valtozatos.atrendez(szoveg)}, timeout=20)

        if resp.status_code == 200:
            print("  ✅ Facebook poszt elküldve (Make.com-on keresztül).")
            return True
        else:
            print(f"  ⚠️  Facebook poszt sikertelen (HTTP {resp.status_code}): {resp.text[:300]}")
            return False
    except Exception as e:
        print(f"  ⚠️  Facebook poszt hiba: {e}")
        return False


# ════════════════════════════════════════════
#  📧  E-MAIL
# ════════════════════════════════════════════
ARAM_JELVENY = ('<span style="display:inline-block;font-weight:bold;font-size:13px;line-height:1;'
                'padding:6px 9px;border-radius:4px;background:#f2b705;color:#1b232c;'
                'font-family:Arial,sans-serif;letter-spacing:.5px">⚡ ÁRAM</span>')
EON_TERKEP = "https://www.eon.hu/hu/lakossagi/aram/aramszunet-informaciok.html"


def _helyszin(f):
    """Az érintett címek: első utca a kártya címének, a teljes lista a törzsbe."""
    lista = f["utcak_lista"] or [f["utcak"]]
    elso = lista[0]
    cim = f"{f['kerulet']} · {elso}" + (f" és még {len(lista) - 1} cím" if len(lista) > 1 else "")
    sorok = "".join(f'<div style="padding:2px 0">• {ea.esc(u)}</div>' for u in lista)
    return cim, f'<div style="margin:8px 0 4px;font-size:14px">{sorok}</div>'


def _aram_kartya(f, szin, cimke, cimke_szin=None):
    cim, cimek_html = _helyszin(f)
    test = (cimek_html
            + ea.adat_tabla([("Kezdés", f["kezdes"]), ("Várható vége", f["veg"]),
                             ("Érintett", f"{f['fogyaszto']} fogyasztó" if f["fogyaszto"] not in ("", "—", "None") else ""),
                             ("Azonosító", f["azonosito"] if f["azonosito"] != "—" else "")])
            + ea.gomb("📍 Térkép", f["gmaps"])
            + ea.gomb("E.ON áramszünet-térkép", EON_TERKEP, masodlagos=True))
    return ea.kartya(szin, cimke, cim, test, jelvenyek=ARAM_JELVENY, cimke_szin=cimke_szin)


def _fb_kartya(szoveg, felirat):
    test = ('<div style="white-space:pre-wrap;font-size:13px;line-height:1.55;background:#f6f8fa;'
            f'border:1px solid #e4e6eb;border-radius:6px;padding:12px">{ea.esc(szoveg)}</div>')
    return ea.kartya("#1877f2", "Facebook", felirat, test)


def _kuld(targy, felado, szoveges, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"{felado} <{EMAIL_KULDO}>"
    msg["To"]      = EMAIL_CIMZETT
    msg.attach(MIMEText(szoveges, "plain", "utf-8"))
    msg.attach(MIMEText(html,     "html",  "utf-8"))
    if EMAIL_AKTIV:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
            smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
        print(f"📧 E-mail elküldve: {targy}")
    else:
        print(f"ℹ️ E-mail kikapcsolva (EMAIL_AKTIV = False), nem ment ki: {targy}")


def email_kuldes(uj_esetek, osszes_aktiv_esetek):
    ido   = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)

    uj_adatok      = [kinyert_adatok(e) for e in uj_esetek]
    aktiv_adatok   = [kinyert_adatok(e) for e in osszes_aktiv_esetek]
    fb_szoveg_txt  = facebook_szoveg(uj_adatok, aktiv_adatok, ido)

    # Az élő üzemzavarok elöl
    uj_adatok.sort(key=lambda f: f["tipus"] != "UZEMZAVAR")
    elso = uj_adatok[0]
    fajta = "Üzemzavar" if elso["tipus"] == "UZEMZAVAR" else "Áramszünet"
    hely = _helyszin(elso)[0]
    targy = (f"⚡ {fajta} · {hely}" if db == 1
             else f"⚡ E.ON: {db} új áramszünet · {elso['kerulet']} és környéke")

    kartyak = "".join(
        _aram_kartya(f, ea.SZIN["piros"], "Élő üzemzavar") if f["tipus"] == "UZEMZAVAR"
        else _aram_kartya(f, ea.SZIN["sarga"], "Tervezett áramszünet", ea.SZIN["sarga_szoveg"])
        for f in uj_adatok)
    if FACEBOOK_POSZTOLAS_AKTIV:
        kartyak += _fb_kartya(fb_szoveg_txt, "Ez a poszt megy ki az oldalra")
    html = ea.keret(kartyak, "Áramszünet Figyelő · Csepel, Pesterzsébet, Szigetszentmiklós · E.ON adatai alapján")

    szoveges = "Áramszünet Figyelő – új események\n"
    for f in uj_adatok:
        szoveges += (f"\n{'Élő üzemzavar' if f['tipus'] == 'UZEMZAVAR' else 'Tervezett áramszünet'}: {f['kerulet']}\n"
                     f"  {f['kezdes']} – {f['veg']}\n  {f['utcak']}\n")
    szoveges += f"\nE.ON áramszünet-térkép: {EON_TERKEP}\n"

    _kuld(targy, "Áramszünet Figyelő", szoveges, html)
    return fb_szoveg_txt


# ════════════════════════════════════════════
#  ⏰  EMLÉKEZTETŐ (2 nappal a tervezett esemény előtt)
# ════════════════════════════════════════════
EMLEKEZTETO_NAPOK_ELOTTE = [7, 1]  # több érték is megadható - mindegyikhez külön emlékeztető megy, ahogy közeledik az esemény


def emlekezteto_kuldes(emlekezteto_adatok):
    db    = len(emlekezteto_adatok)
    elso  = emlekezteto_adatok[0]
    targy = (f"⏰ Emlékeztető · áramszünet {elso['kezdes']} · {_helyszin(elso)[0]}" if db == 1
             else f"⏰ Emlékeztető: {db} közelgő áramszünet")

    kartyak = ""
    szoveges = "Emlékeztető – közelgő áramszünet\n"
    for f in emlekezteto_adatok:
        nap = f.get("emlekezteto_nap")
        cimke = "Holnap esedékes" if nap == 1 else (f"{nap} napon belül esedékes" if nap else "Közelgő áramszünet")
        kartyak += _aram_kartya(f, ea.SZIN["sarga"], cimke, ea.SZIN["sarga_szoveg"])
        szoveges += f"\n{cimke}: {f['kerulet']}\n  {f['kezdes']} – {f['veg']}\n  {f['utcak']}\n"
    html = ea.keret(kartyak, "Áramszünet Figyelő · emlékeztető a korábban bejelentett tervezett áramszünetekről")

    _kuld(targy, "Áramszünet Figyelő", szoveges, html)


AKTIV_JSON_FAJL = "aramszunet_aktiv.json"


def ment_aktiv_json(osszes_aktiv_adatok):
    """Kiírja a jelenleg aktív (tervezett + üzemzavar) eseményeket egy
    külön JSON-fájlba, amit a weboldal (aramszunet.html) tölt be és
    jelenít meg élőben."""
    export = []
    for f in osszes_aktiv_adatok:
        export.append({
            "azonosito": f["azonosito"],
            "tipus": f["tipus"],
            "kerulet": f["kerulet"],
            "utcak_lista": f["utcak_lista"],
            "utcak": f["utcak"],
            "kezdes": f["kezdes"],
            "veg": f["veg"],
            "fogyaszto": f["fogyaszto"],
            "lat": f["lat"],
            "lon": f["lon"],
            "gmaps": f["gmaps"],
        })

    with open(AKTIV_JSON_FAJL, "w", encoding="utf-8") as fjson:
        json.dump({
            "frissitve": magyar_ido().isoformat(),
            "esemenyek": export,
        }, fjson, ensure_ascii=False, indent=2)
    print(f"🌐 Weboldal-adat mentve: {AKTIV_JSON_FAJL} ({len(export)} esemény)")


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"⚡ Csepel Áramszünet Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    if FACEBOOK_POSZTOLAS_AKTIV:
        ejszakai_sor.sor_kiurites(regi, facebook_poszt_kuldese)
    uj   = []
    osszes_aktiv = []  # minden jelenleg is aktív csepeli esemény

    for e in lekerdez_json(API_TERVEZETT, "TERVEZETT"):
        azonosito = str(e["adat"].get("id") or e["adat"].get("internalId") or json.dumps(e["adat"], sort_keys=True))
        rid = hash_id(azonosito)
        osszes_aktiv.append(e)
        if rid not in regi.get("tervezett", {}):
            uj.append(e)
            regi.setdefault("tervezett", {})[rid] = magyar_ido().isoformat()

    for e in lekerdez_json(API_UZEMZAVAR, "UZEMZAVAR"):
        azonosito = str(e["adat"].get("id") or e["adat"].get("internalId") or json.dumps(e["adat"], sort_keys=True))
        rid = hash_id(azonosito)
        osszes_aktiv.append(e)
        if rid not in regi.get("uzemzavar", {}):
            uj.append(e)
            regi.setdefault("uzemzavar", {})[rid] = magyar_ido().isoformat()

    print(f"\n⚡ Új események: {len(uj)} | Összes aktív: {len(osszes_aktiv)}")
    if uj:
        # Élő üzemzavar: azonnal posztolok, és levél is megy. Előre bejelentett
        # áramszünet: a poszt a következő szabad sávba kerül, levél nem jön róla.
        surgos = [e for e in uj if e["tipus"] == "UZEMZAVAR"]
        raeros = [e for e in uj if e["tipus"] != "UZEMZAVAR"]
        ido = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
        aktiv_adatok = [kinyert_adatok(e) for e in osszes_aktiv]
        if surgos:
            fb_szoveg_txt = email_kuldes(surgos, osszes_aktiv)
            if FACEBOOK_POSZTOLAS_AKTIV:
                print("\n📘 Facebook poszt küldése (üzemzavar)...")
                ejszakai_sor.kuld_vagy_sorba(regi, fb_szoveg_txt, facebook_poszt_kuldese, surgos=True)
        if raeros and FACEBOOK_POSZTOLAS_AKTIV:
            print("\n🗓️ Tervezett áramszünet: a poszt sorba kerül...")
            ejszakai_sor.kuld_vagy_sorba(
                regi, facebook_szoveg([kinyert_adatok(e) for e in raeros], aktiv_adatok, ido),
                facebook_poszt_kuldese, surgos=False)
    else:
        print("✅ Nincs új esemény.")

    # ---- Emlékeztetők: EMLEKEZTETO_NAPOK_ELOTTE-ben megadott napokkal a
    #      tervezett kezdés előtt (soronként egyedileg nyomon követve, hogy
    #      egy esemény minden küszöbnél kaphasson emlékeztetőt, de egy
    #      körben csak egyet, a legsürgetőbbet) ----
    most = magyar_ido()
    emlekezteto_kuldendo = []
    regi.setdefault("emlekezteto", {})
    kuszobok = sorted(set(EMLEKEZTETO_NAPOK_ELOTTE), reverse=True)  # pl. [7, 2, 1]

    for e in osszes_aktiv:
        if e["tipus"] != "TERVEZETT":
            continue  # az üzemzavarok azonnaliak, azoknál nincs "közelgő" emlékeztető

        azonosito = str(e["adat"].get("id") or e["adat"].get("internalId") or json.dumps(e["adat"], sort_keys=True))
        rid = hash_id(azonosito)

        adatok = kinyert_adatok(e)
        kezdes_dt = adatok["kezdes_dt"]
        if not kezdes_dt:
            continue  # nem sikerült értelmezni a dátumot, kihagyjuk

        hatralevo = kezdes_dt - most
        if hatralevo <= timedelta(0):
            continue  # már elkezdődött/elmúlt, nincs értelme emlékeztetőnek

        for nap in kuszobok:
            kulcs = f"{rid}::{nap}"
            if kulcs in regi["emlekezteto"]:
                continue  # ezt a küszöböt ennél az eseménynél már elküldtük

            if hatralevo <= timedelta(days=nap):
                adatok["emlekezteto_nap"] = nap
                emlekezteto_kuldendo.append(adatok)
                regi["emlekezteto"][kulcs] = most.isoformat()

                # A nagyobb (korábbi) küszöböket is elküldöttnek jelöljük,
                # nehogy utólag, "elkésve" külön emlékeztetőt kapjon rájuk.
                for korabbi_nap in kuszobok:
                    if korabbi_nap > nap:
                        regi["emlekezteto"][f"{rid}::{korabbi_nap}"] = most.isoformat()
                break  # eseményenként csak egy emlékeztető megy ki egy körben

    if emlekezteto_kuldendo:
        # Közelgő eseményről levél nem megy (Gábor kérése), csak a poszt, szabad sávban
        print(f"\n⏰ Emlékeztető {len(emlekezteto_kuldendo)} közelgő eseményről...")

        if FACEBOOK_POSZTOLAS_AKTIV:
            print("\n📘 Emlékeztető Facebook poszt küldése...")
            fb_emlekezteto_szoveg = facebook_szoveg_emlekezteto(
                emlekezteto_kuldendo, most.strftime("%Y.%m.%d %H:%M:%S")
            )
            ejszakai_sor.kuld_vagy_sorba(regi, fb_emlekezteto_szoveg, facebook_poszt_kuldese, surgos=False)
    else:
        print("⏰ Nincs a beállított küszöbök egyikén belül sem esedékes, még nem jelzett tervezett esemény.")

    # ---- Weboldal-adat mentése (minden futáskor, új esemény nélkül is) ----
    aktiv_adatok_export = [kinyert_adatok(e) for e in osszes_aktiv]
    ment_aktiv_json(aktiv_adatok_export)

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
