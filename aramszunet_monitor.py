"""
⚡ E.ON Áramszünet Monitor – Csepel (XXI.) + Pesterzsébet (XX.) + Kispest (XIX.)
   + Szigetszentmiklós
Szűrés: city mező (kerület-azonosító vagy településnév) + polygon
"""

import os
import json
import hashlib
import smtplib
import requests
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

MAGYAR_TZ = timezone(timedelta(hours=2))

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT_ARAM"]
FB_PAGE_ID    = os.environ.get("FB_PAGE_ID", "104411308403346")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")

# ⬇️⬇️⬇️ ITT KAPCSOLOD KI/BE AZ AUTOMATA FACEBOOK-POSZTOLÁST ⬇️⬇️⬇️
# True  = automatikusan posztol a Facebook Oldalra is (jelenleg nem publikus,
#         amíg nincs elvégezve a Meta Business Verification)
# False = csak emailt küld, a Facebook-szöveg ott lesz kimásolható
FACEBOOK_POSZTOLAS_AKTIV = False

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
#  📍  SZŰRŐ – Csepel (XXI.) + Pesterzsébet (XX.) + Kispest (XIX.)
#      + Szigetszentmiklós (önálló település, nincs kerület-száma)
# ════════════════════════════════════════════

TERULETEK = [
    # (regex-minta a "city" mezőre vagy None, ha nincs kerület-szám; kulcsszó; megjelenítendő címke)
    # Szigetszentmiklós előrébb van, mert "Csepel-sziget" földrajzi kifejezés
    # tartalmazhatja a "csepel" szót, és azt nem szeretnénk tévesen XXI.-nek venni.
    (None,        "szigetszentmiklós", "Szigetszentmiklós"),
    (r'\bXXI\b',  "csepel",           "XXI. kerület (Csepel)"),
    (r'\bXX\b',   "pesterzsébet",     "XX. kerület (Pesterzsébet)"),
    (r'\bXIX\b',  "kispest",          "XIX. kerület (Kispest)"),
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

    sorok = [
        "⚡ ÁRAMSZÜNET ÉRTESÍTŐ ⚡",
        f"🕒 {ido}   •   {db_uj} új esemény",
        "═" * 32,
        "",
    ]

    # A kért bevezető mondat - jelezve, hogy nem csak Csepelről olvasnak minket
    sorok.append(
        "👋 Mivel nemcsak Csepelről, hanem a környező kerületekből és "
        "városokból (Pesterzsébet, Kispest, Szigetszentmiklós) is sokan "
        "olvastok minket, mostantól ezekről a területekről is beszámolunk, "
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
        sorok.append(f"▸▸▸  {kerulet.upper()}  ◂◂◂")
        sorok.append("─" * 32)
        for f in keruleti_uj:
            sorok.append(esemeny_blokk(f, f["tipus"] == "TERVEZETT"))
            sorok.append("")

    # Összesítő - az összes jelenleg aktív üzemzavar tömören, kerület szerint
    aktiv_uzemzavar = [e for e in osszes_aktiv_adatok if e["tipus"] == "UZEMZAVAR"]
    if aktiv_uzemzavar:
        sorok.append("═" * 32)
        sorok.append(f"📋 ÖSSZES AKTÍV ÜZEMZAVAR  ({len(aktiv_uzemzavar)} db)")
        sorok.append("─" * 32)
        for f in aktiv_uzemzavar:
            utca = f["utcak"] or f["kerulet"]
            sorok.append(f"• [{f['kerulet']}] {utca}  |  {f['kezdes']}  |  {f['fogyaszto']} fogyasztó")
        sorok.append("")

    sorok.append("─" * 32)
    sorok.append("ℹ️ Forrás: E.ON nyilvános tájékoztatás")
    sorok.append("🤖 Automatikus értesítő – Baleset-info.hu")
    sorok.append("📍 Figyelt terület: Csepel, Pesterzsébet, Kispest, Szigetszentmiklós")

    if KEP_URL:
        sorok.append("")
        sorok.append(KEP_URL)

    return "\n".join(sorok)


# ════════════════════════════════════════════
#  📘  FACEBOOK AUTOMATA POSZTOLÁS (Graph API, szövegesen)
# ════════════════════════════════════════════
def facebook_poszt_kuldese(szoveg):
    """Szöveges posztot küld a Facebook Oldalra a Graph API-n keresztül.
    Nincs kép csatolva - tisztán szöveges bejegyzés (feed poszt)."""
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        print("  ⚠️  Nincs beállítva FB_PAGE_ID / FB_PAGE_TOKEN - Facebook-posztolás kihagyva.")
        return False

    try:
        url = f"https://graph.facebook.com/v21.0/{FB_PAGE_ID}/feed"
        payload = {"message": szoveg, "access_token": FB_PAGE_TOKEN}
        resp = requests.post(url, data=payload, timeout=20)

        if resp.status_code == 200:
            poszt_id = resp.json().get("id", "")
            print(f"  ✅ Facebook poszt elküldve. ID: {poszt_id}")
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
def email_kuldes(uj_esetek, osszes_aktiv_esetek):
    ido   = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)
    targy = f"⚡ Áramszünet (Csepel/Pesterzsébet/Kispest/Sziget.) – {db} új esemény | {ido}"

    uj_adatok      = [kinyert_adatok(e) for e in uj_esetek]
    aktiv_adatok   = [kinyert_adatok(e) for e in osszes_aktiv_esetek]
    fb_szoveg_txt  = facebook_szoveg(uj_adatok, aktiv_adatok, ido)

    sorok_html = ""
    for i, f in enumerate(uj_adatok, 1):
        szin  = "#c0392b" if f["tipus"] == "UZEMZAVAR" else "#e67e22"
        badge = "🔴 ÉLŐ ÜZEMZAVAR" if f["tipus"] == "UZEMZAVAR" else "📋 TERVEZETT ÁRAMSZÜNET"

        cimek_html = "".join(f"<div>• {c}</div>" for c in f["utcak_lista"]) if f["utcak_lista"] else f["utcak"]

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:{szin};color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">{badge}</span>
            <table style="font-size:13px;width:100%;margin-top:10px">
              <tr><td style="color:#888;width:140px">📌 Kerület:</td><td><strong>{f['kerulet']}</strong></td></tr>
              <tr><td style="color:#888">🔢 Azonosító:</td><td>{f['azonosito']}</td></tr>
              <tr><td style="color:#888">⏰ Kezdés:</td><td><strong>{f['kezdes']}</strong></td></tr>
              <tr><td style="color:#888">⏰ Vége:</td><td><strong>{f['veg']}</strong></td></tr>
              <tr><td style="color:#888;vertical-align:top">🏘️ Helyszín:</td><td>{cimek_html}</td></tr>
              <tr><td style="color:#888">👥 Érintett:</td><td>{f['fogyaszto']} fogyasztó</td></tr>
            </table>
            {"<div style='margin-top:10px'><a href='" + f['gmaps'] + "' style='background:#4285f4;color:#fff;padding:7px 14px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:bold'>📍 Google Maps</a></div>" if f['gmaps'] else ""}
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="hu"><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}}
  .wrap{{max-width:650px;margin:20px auto;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.15)}}
  .hdr{{background:#c0392b;color:#fff;padding:22px 28px}}
  .hdr h1{{margin:0;font-size:20px}}
  .hdr small{{opacity:.85;font-size:13px}}
  .body{{padding:20px 28px}}
  .fb-box{{background:linear-gradient(135deg,#f0f2f5,#e8edf3);
           border:1px solid #d0d7de;border-radius:12px;
           padding:18px 20px;margin:22px 0;
           box-shadow:0 1px 3px rgba(0,0,0,.06)}}
  .fb-box h3{{margin:0 0 12px;color:#1877f2;font-size:14px;
              display:flex;align-items:center;gap:6px}}
  .fb-box pre{{margin:0;font-family:Arial,sans-serif;font-size:13px;
              white-space:pre-wrap;word-break:break-word;
              color:#1c1e21;line-height:1.6;background:#fff;
              border-radius:8px;padding:14px;border:1px solid #e4e6eb}}
  .fb-kep-elonezet{{margin-top:12px;text-align:center}}
  .fb-kep-elonezet img{{max-width:100%;max-height:220px;border-radius:8px;
                        box-shadow:0 2px 6px rgba(0,0,0,.15)}}
  .foot{{background:#ecf0f1;padding:12px 28px;font-size:11px;
         color:#95a5a6;text-align:center}}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>⚡ Áramszünet értesítő – Csepel / Pesterzsébet / Kispest / Szigetszentmiklós</h1>
    <small>{ido} | {db} új esemény</small>
  </div>
  <div class="body">
    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>

    <div class="fb-box">
      <h3>📘 Facebook poszt szövege — jelöld ki és másold (Ctrl+A majd Ctrl+C)</h3>
      <pre>{fb_szoveg_txt}</pre>
      {f'<div class="fb-kep-elonezet"><img src="{KEP_URL}" alt="Facebook poszt kép"></div>' if KEP_URL else ''}
    </div>

    <div style="text-align:center;margin-top:16px">
      <a href="https://www.eon.hu/hu/lakossagi/aram/aramszunet-informaciok.html"
         style="background:#c0392b;color:#fff;padding:9px 16px;border-radius:6px;
                text-decoration:none;font-weight:bold;font-size:12px">
        ⚡ E.ON térkép
      </a>
      <a href="https://www.facebook.com/104411308403346"
         style="background:#1877f2;color:#fff;padding:9px 16px;border-radius:6px;
                text-decoration:none;font-weight:bold;font-size:12px;margin-left:8px">
        📘 Facebook oldal
      </a>
    </div>
  </div>
  <div class="foot">Automatikus értesítő – GitHub Actions | E.ON adatai alapján</div>
</div></body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"⚡ Áramszünet Monitor <{EMAIL_KULDO}>"
    msg["To"]      = EMAIL_CIMZETT
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
        smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
    print(f"📧 E-mail elküldve: {targy}")
    return fb_szoveg_txt


# ════════════════════════════════════════════
#  ⏰  EMLÉKEZTETŐ (2 nappal a tervezett esemény előtt)
# ════════════════════════════════════════════
EMLEKEZTETO_NAPOK_ELOTTE = [7, 2, 1]  # több érték is megadható - mindegyikhez külön emlékeztető megy, ahogy közeledik az esemény


def emlekezteto_kuldes(emlekezteto_adatok):
    ido   = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(emlekezteto_adatok)
    targy = f"⏰ Emlékeztető - közelgő áramszünet – {db} esemény | {ido}"

    sorok_html = ""
    sorok_txt  = ""
    for i, f in enumerate(emlekezteto_adatok, 1):
        szin = "#e67e22"
        cimek_html = "".join(f"<div>• {c}</div>" for c in f["utcak_lista"]) if f["utcak_lista"] else f["utcak"]
        nap = f.get("emlekezteto_nap")
        nap_cimke = f"{nap} napon belül esedékes" if nap else "közelgő"

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:{szin};color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">⏰ {nap_cimke.upper()}</span>
            <table style="font-size:13px;width:100%;margin-top:10px">
              <tr><td style="color:#888;width:110px">📌 Terület:</td><td><strong>{f['kerulet']}</strong></td></tr>
              <tr><td style="color:#888">📍 Érintett utcák:</td><td>{cimek_html}</td></tr>
              <tr><td style="color:#888">⏰ Kezdés:</td><td><strong>{f['kezdes']}</strong></td></tr>
              <tr><td style="color:#888">⏰ Várható vége:</td><td>{f['veg']}</td></tr>
              <tr><td style="color:#888">👥 Érintett fogyasztók:</td><td>{f['fogyaszto']}</td></tr>
            </table>
            {f'<div style="margin-top:8px"><a href="{f["gmaps"]}" style="background:#4285f4;color:#fff;padding:6px 12px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:bold">📍 Google Maps</a></div>' if f['gmaps'] else ''}
          </td>
        </tr>"""

        sorok_txt += (
            f"\n{'─'*45}\n{i}. ⏰ {nap_cimke.upper()}\n"
            f"Terület: {f['kerulet']}\nUtcák: {f['utcak']}\n"
            f"Kezdés: {f['kezdes']}\nVége: {f['veg']}\nFogyasztók: {f['fogyaszto']}\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="hu"><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}}
  .wrap{{max-width:650px;margin:20px auto;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.15)}}
  .hdr{{background:#e67e22;color:#fff;padding:22px 28px}}
  .hdr h1{{margin:0;font-size:20px}}
  .hdr small{{opacity:.85;font-size:13px}}
  .body{{padding:20px 28px}}
  .bevezeto{{background:#fef3e8;border-left:4px solid #e67e22;
             padding:12px 16px;margin-bottom:16px;
             font-size:14px;color:#2c3e50;line-height:1.6}}
  .foot{{background:#ecf0f1;padding:12px 28px;font-size:11px;color:#95a5a6;text-align:center}}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>⏰ Emlékeztető - közelgő áramszünet</h1>
    <small>{ido} | {db} esemény</small>
  </div>
  <div class="body">
    <div class="bevezeto">
      ℹ️ Ez egy emlékeztető korábban már bejelentett, tervezett áramszünet(ek)ről,
      amik hamarosan esedékesek (lásd az egyes tételeknél, mennyi nap van hátra).
    </div>
    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>
  </div>
  <div class="foot">Automatikus emlékeztető – GitHub Actions | E.ON adatok alapján</div>
</div></body></html>"""

    szoveges = f"⏰ Emlékeztető - közelgő áramszünet\nIdőpont: {ido}\n{sorok_txt}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"⏰ Áramszünet Emlékeztető <{EMAIL_KULDO}>"
    msg["To"]      = EMAIL_CIMZETT
    msg.attach(MIMEText(szoveges, "plain", "utf-8"))
    msg.attach(MIMEText(html,     "html",  "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
        smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
    print(f"⏰ Emlékeztető email elküldve: {targy}")


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
        fb_szoveg_txt = email_kuldes(uj, osszes_aktiv)

        if FACEBOOK_POSZTOLAS_AKTIV:
            print("\n📘 Facebook poszt küldése...")
            facebook_poszt_kuldese(fb_szoveg_txt)
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
        print(f"\n⏰ Emlékeztető küldése {len(emlekezteto_kuldendo)} közelgő eseményről...")
        emlekezteto_kuldes(emlekezteto_kuldendo)
    else:
        print("⏰ Nincs a beállított küszöbök egyikén belül sem esedékes, még nem jelzett tervezett esemény.")

    # ---- Weboldal-adat mentése (minden futáskor, új esemény nélkül is) ----
    aktiv_adatok_export = [kinyert_adatok(e) for e in osszes_aktiv]
    ment_aktiv_json(aktiv_adatok_export)

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
