"""
⚡ E.ON Áramszünet Monitor – Csepel (XXI. kerület)
Szűrés: city mező (Budapest XXI.) + polygon
"""

import os
import json
import hashlib
import smtplib
import requests
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from shapely.geometry import Point, Polygon

# ─────────────────────────────────────────────
#  🕐  MAGYAR IDŐZÓNA (UTC+2, GitHub Actions UTC-t használ)
# ─────────────────────────────────────────────
MAGYAR_TZ = timezone(timedelta(hours=2))

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT_ARAM"]

API_TERVEZETT = "https://www.eon.hu/content/dam/eon/eon-hungary/external-app-data/outages/poweroutage.json"
API_UZEMZAVAR = "https://www.eon.hu/content/dam/eon/eon-hungary/external-app-data/outages/unexpectedoutage.json"

# XXI. kerület (Csepel) pontos határpontjai – OSM alapján
# Shapely Polygon – (lon, lat) sorrendben!
CSEPEL_POLYGON = Polygon([
    (19.0178, 47.4025), (19.0188, 47.4090), (19.0200, 47.4150),
    (19.0215, 47.4215), (19.0235, 47.4275), (19.0265, 47.4325),
    (19.0290, 47.4365), (19.0310, 47.4388), (19.0375, 47.4418),
    (19.0450, 47.4432), (19.0530, 47.4440), (19.0610, 47.4440),
    (19.0690, 47.4435), (19.0760, 47.4418), (19.0825, 47.4385),
    (19.0875, 47.4345), (19.0910, 47.4295), (19.0935, 47.4240),
    (19.0948, 47.4180), (19.0950, 47.4115), (19.0940, 47.4040),
    (19.0925, 47.3975), (19.0900, 47.3915), (19.0860, 47.3860),
    (19.0810, 47.3810), (19.0740, 47.3765), (19.0660, 47.3735),
    (19.0570, 47.3715), (19.0480, 47.3710), (19.0390, 47.3718),
    (19.0315, 47.3735), (19.0255, 47.3760), (19.0215, 47.3795),
    (19.0190, 47.3840), (19.0175, 47.3895), (19.0172, 47.3960),
    (19.0178, 47.4025),
])

ALLAPOT_FAJL = "aramszunet_allapot.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.eon.hu/",
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
#  📍  SZŰRŐ – city mező VAGY polygon
# ════════════════════════════════════════════
def pont_polygon_ban(lat, lon, polygon):
    n = len(polygon)
    belul = False
    j = n - 1
    for i in range(n):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]
        if ((lon_i > lon) != (lon_j > lon)) and \
           (lat < (lat_j - lat_i) * (lon - lon_i) / (lon_j - lon_i) + lat_i):
            belul = not belul
        j = i
    return belul

def csepel_e(eset):
    """Csepeli-e az esemény?
    1. Ha bármely addressRange city mezője 'Budapest XXI.' → igen
    2. Ha a koordináta a Csepel polygonon belül van → igen
    """
    # 1. City mező ellenőrzés az addressRanges-ben
    for ar in eset.get("addressRanges", []):
        if isinstance(ar, dict):
            city = str(ar.get("city", "") or "").strip()
            if "XXI" in city or "Csepel" in city.lower():
                return True

    # 2. City mező az üzemzavar szintjén
    city = str(eset.get("city", "") or "").strip()
    if "XXI" in city or "Csepel" in city.lower():
        return True

    # 3. Koordináta alapú ellenőrzés (polygon)
    coords = eset.get("coordinates") or {}
    if isinstance(coords, dict):
        lat = coords.get("lat")
        lon = coords.get("lng") or coords.get("lon")
        if lat and lon and float(lat) != 0.0 and float(lon) != 0.0:
            if pont_polygon_ban(float(lat), float(lon), CSEPEL_POLYGON):
                return True

    # 4. Transformer koordináta
    tc = eset.get("transformerAreaCenterCoordinates") or {}
    if isinstance(tc, dict):
        lat = tc.get("lat")
        lon = tc.get("lng") or tc.get("lon")
        if lat and lon and float(lat) != 0.0 and float(lon) != 0.0:
            if pont_polygon_ban(float(lat), float(lon), CSEPEL_POLYGON):
                return True

    # 5. addressRanges koordinátái
    for ar in eset.get("addressRanges", []):
        if isinstance(ar, dict):
            c = ar.get("coordinates") or {}
            lat = c.get("lat")
            lon = c.get("lng") or c.get("lon")
            if lat and lon and float(lat) != 0.0 and float(lon) != 0.0:
                if pont_polygon_ban(float(lat), float(lon), CSEPEL_POLYGON):
                    return True

    return False


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
            return datetime.fromtimestamp(mezo / 1000 if mezo > 1e10 else mezo).strftime("%Y.%m.%d %H:%M")
        except Exception:
            return str(mezo)
    return str(mezo).replace("T", " ").replace("Z", "")[:19]


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

    if tipus == "TERVEZETT":
        intervals  = a.get("intervals", [])
        elso       = intervals[0] if intervals and isinstance(intervals[0], dict) else {}
        kezdes_raw = elso.get("from") or elso.get("start")
        veg_raw    = elso.get("to")   or elso.get("end")
    else:
        kezdes_raw = a.get("from") or a.get("startTime")
        veg_raw    = a.get("to")   or a.get("endTime")

    coords = a.get("coordinates") or a.get("transformerAreaCenterCoordinates") or {}
    lat = coords.get("lat") if isinstance(coords, dict) else None
    lon = coords.get("lng") or coords.get("lon") if isinstance(coords, dict) else None
    if lat == 0.0: lat = None
    if lon == 0.0: lon = None

    utcak_lista = []
    for ar in a.get("addressRanges", []):
        if isinstance(ar, dict):
            city   = ar.get("city", "")
            street = ar.get("street", "") or ar.get("streetName", "")
            from_n = ar.get("fromNumber", "") or ar.get("houseNumberFrom", "")
            to_n   = ar.get("toNumber", "")   or ar.get("houseNumberTo", "")
            if street:
                sor = f"{city} {street}".strip()
                if from_n and to_n:
                    sor += f" {from_n}-{to_n}"
                elif from_n:
                    sor += f" {from_n}"
                utcak_lista.append(sor)

    # Duplikátumok eltávolítása
    utcak_lista = list(dict.fromkeys(utcak_lista))
    utcak = ", ".join(utcak_lista[:4]) if utcak_lista else (a.get("city") or "—")

    consumers = a.get("consumers", {})
    fogyaszto = consumers.get("total") if isinstance(consumers, dict) else str(consumers) if consumers else "—"

    azonosito = a.get("id") or a.get("internalId") or "—"
    gmaps = f"https://www.google.com/maps?q={lat},{lon}&z=14" if lat and lon else None

    return {
        "azonosito": str(azonosito),
        "kezdes":    ido_format(kezdes_raw),
        "veg":       ido_format(veg_raw),
        "utcak":     utcak,
        "fogyaszto": str(fogyaszto),
        "gmaps":     gmaps,
        "tipus":     tipus,
    }


# ════════════════════════════════════════════
#  📘  FACEBOOK POSZT SZÖVEG
# ════════════════════════════════════════════
def facebook_szoveg(esetek, ido):
    db = len(esetek)
    sorok = [
        f"⚡ Csepel – Áramszünet értesítő",
        f"🕒 {ido} | {db} esemény",
        "",
    ]

    tervezett = [e for e in esetek if e["tipus"] == "TERVEZETT"]
    uzemzavar = [e for e in esetek if e["tipus"] == "UZEMZAVAR"]

    if tervezett:
        sorok.append("🔌 TERVEZETT ÁRAMSZÜNETEK")
        sorok.append("─────────────────────")
        for f in tervezett:
            utcak = f['utcak'] or '—'
            sorok.append(f"📅 {f['kezdes'][:10] if f['kezdes'] != '—' else '—'}")
            sorok.append(f"🕐 {f['kezdes'][11:] if len(f['kezdes']) > 10 else f['kezdes']} → {f['veg'][11:] if len(f['veg']) > 10 else f['veg']}")
            sorok.append(f"📍 {utcak}")
            sorok.append(f"👥 Érintett: {f['fogyaszto']} fogyasztó")
            sorok.append("")

    if uzemzavar:
        sorok.append("🔴 ÉLŐ ÜZEMZAVAR")
        sorok.append("─────────────────────")
        for f in uzemzavar:
            sorok.append(f"📍 {f['utcak'] or '—'}")
            sorok.append(f"🕐 Kezdete: {f['kezdes']}")
            sorok.append(f"👥 Érintett: {f['fogyaszto']} fogyasztó")
            sorok.append("")

    sorok.append("ℹ️ Forrás: E.ON nyilvános tájékoztatás")
    sorok.append("🤖 Automatikus értesítő")

    return "\n".join(sorok)


# ════════════════════════════════════════════
#  📧  E-MAIL
# ════════════════════════════════════════════
def email_kuldes(uj_esetek):
    ido   = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)
    targy = f"⚡ Csepel áramszünet – {db} új esemény | {ido}"

    adatok = [kinyert_adatok(e) for e in uj_esetek]
    fb_szoveg = facebook_szoveg(adatok, ido)

    sorok_html = ""
    for i, f in enumerate(adatok, 1):
        szin  = "#c0392b" if f["tipus"] == "UZEMZAVAR" else "#e67e22"
        badge = "🔴 ÉLŐ ÜZEMZAVAR" if f["tipus"] == "UZEMZAVAR" else "📋 TERVEZETT ÁRAMSZÜNET"

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:{szin};color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">{badge}</span>
            <table style="font-size:13px;width:100%;margin-top:10px">
              <tr><td style="color:#888;width:140px">🔢 Azonosító:</td><td>{f['azonosito']}</td></tr>
              <tr><td style="color:#888">⏰ Kezdés:</td><td><strong>{f['kezdes']}</strong></td></tr>
              <tr><td style="color:#888">⏰ Vége:</td><td><strong>{f['veg']}</strong></td></tr>
              <tr><td style="color:#888">🏘️ Helyszín:</td><td>{f['utcak']}</td></tr>
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
  .fb-box{{background:#f0f2f5;border:2px dashed #1877f2;border-radius:8px;
           padding:16px;margin:20px 0}}
  .fb-box h3{{margin:0 0 10px;color:#1877f2;font-size:14px}}
  .fb-box pre{{margin:0;font-family:Arial,sans-serif;font-size:13px;
              white-space:pre-wrap;word-break:break-word;
              color:#1c1e21;line-height:1.6}}
  .foot{{background:#ecf0f1;padding:12px 28px;font-size:11px;
         color:#95a5a6;text-align:center}}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>⚡ Csepel – Áramszünet értesítő</h1>
    <small>{ido} | {db} új esemény (XXI. kerület)</small>
  </div>
  <div class="body">
    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>

    <div class="fb-box">
      <h3>📘 Facebook poszt – kattints bele, Ctrl+A, Ctrl+C:</h3>
      <pre>{fb_szoveg}</pre>
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


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"⚡ Csepel Áramszünet Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    uj   = []

    for e in lekerdez_json(API_TERVEZETT, "TERVEZETT"):
        rid = hash_id(json.dumps(e["adat"], sort_keys=True))
        if rid not in regi.get("tervezett", {}):
            uj.append(e)
            regi.setdefault("tervezett", {})[rid] = magyar_ido().isoformat()

    for e in lekerdez_json(API_UZEMZAVAR, "UZEMZAVAR"):
        rid = hash_id(json.dumps(e["adat"], sort_keys=True))
        if rid not in regi.get("uzemzavar", {}):
            uj.append(e)
            regi.setdefault("uzemzavar", {})[rid] = magyar_ido().isoformat()

    print(f"\n⚡ Új események: {len(uj)}")
    if uj:
        email_kuldes(uj)
    else:
        print("✅ Nincs új esemény.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
