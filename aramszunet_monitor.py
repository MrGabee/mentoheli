"""
⚡ E.ON Áramszünet Monitor – Csepel (XXI. kerület)
Adatforrás: E.ON JSON API
  - poweroutage.json    → tervezett áramszünetek
  - unexpectedoutage.json → élő üzemzavarok
"""

import os
import json
import hashlib
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT"]

API_TERVEZETT = "https://www.eon.hu/content/dam/eon/eon-hungary/external-app-data/outages/poweroutage.json"
API_UZEMZAVAR = "https://www.eon.hu/content/dam/eon/eon-hungary/external-app-data/outages/unexpectedoutage.json"

# Csepel bounding box (WGS84)
CSEPEL_LAT_MIN = 47.38
CSEPEL_LAT_MAX = 47.47
CSEPEL_LON_MIN = 19.00
CSEPEL_LON_MAX = 19.12

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
#  📍  CSEPEL SZŰRŐ – koordináta alapú
# ════════════════════════════════════════════
def koordinata_csepel_e(lat, lon):
    try:
        return (CSEPEL_LAT_MIN <= float(lat) <= CSEPEL_LAT_MAX and
                CSEPEL_LON_MIN <= float(lon) <= CSEPEL_LON_MAX)
    except Exception:
        return False

def csepel_e(eset):
    # Egyetlen koordináta pont
    coords = eset.get("coordinates") or {}
    if isinstance(coords, dict):
        lat = coords.get("lat") or coords.get("latitude")
        lon = coords.get("lng") or coords.get("lon") or coords.get("longitude")
        if lat and lon and koordinata_csepel_e(lat, lon):
            return True

    # Transformer középpont (üzemzavarnál)
    tc = eset.get("transformerAreaCenterCoordinates") or {}
    if isinstance(tc, dict):
        lat = tc.get("lat") or tc.get("latitude")
        lon = tc.get("lng") or tc.get("lon") or tc.get("longitude")
        if lat and lon and koordinata_csepel_e(lat, lon):
            return True

    # addressRanges lista (tervezett esetén)
    for ar in eset.get("addressRanges", []):
        if isinstance(ar, dict):
            c = ar.get("coordinates") or {}
            lat = c.get("lat") or c.get("latitude")
            lon = c.get("lng") or c.get("lon") or c.get("longitude")
            if lat and lon and koordinata_csepel_e(lat, lon):
                return True
            # Szöveges city/district ellenőrzés
            city = str(ar.get("city", "") or ar.get("district", "") or "").lower()
            if "csepel" in city or "xxi" in city:
                return True

    # city mező (üzemzavarnál)
    city = str(eset.get("city", "") or "").lower()
    if "csepel" in city or "xxi" in city:
        return True

    return False


# ════════════════════════════════════════════
#  🕐  IDŐPONT FORMÁZÁS
# ════════════════════════════════════════════
def ido_format(mezo):
    if not mezo:
        return "—"
    if isinstance(mezo, dict):
        datum = mezo.get("date") or mezo.get("datum") or ""
        ido   = mezo.get("time") or mezo.get("ido") or ""
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
    a    = eset["adat"]
    tipus = eset["tipus"]

    # ── Időpontok ──────────────────────────
    if tipus == "TERVEZETT":
        # intervals: [{"from": {...}, "to": {...}}, ...]
        intervals = a.get("intervals", [])
        if intervals and isinstance(intervals, list):
            elso = intervals[0] if isinstance(intervals[0], dict) else {}
            kezdes_raw = elso.get("from") or elso.get("start")
            veg_raw    = elso.get("to")   or elso.get("end")
        else:
            kezdes_raw = a.get("from") or a.get("startTime") or a.get("start")
            veg_raw    = a.get("to")   or a.get("endTime")   or a.get("end")
    else:
        # üzemzavar: "from" mező
        kezdes_raw = a.get("from") or a.get("startTime") or a.get("start")
        veg_raw    = a.get("to")   or a.get("endTime")   or a.get("end")

    # ── Koordináták ────────────────────────
    coords = a.get("coordinates") or a.get("transformerAreaCenterCoordinates") or {}
    lat = coords.get("lat") if isinstance(coords, dict) else None
    lon = coords.get("lng") or coords.get("lon") if isinstance(coords, dict) else None

    # ── Érintett utcák ─────────────────────
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
    utcak = ", ".join(utcak_lista[:6]) if utcak_lista else (a.get("city") or "—")

    # ── Fogyasztók ─────────────────────────
    consumers = a.get("consumers", {})
    if isinstance(consumers, dict):
        fogyaszto = consumers.get("total") or consumers.get("count") or "—"
    else:
        fogyaszto = str(consumers) if consumers else "—"

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
#  📧  E-MAIL
# ════════════════════════════════════════════
def email_kuldes(uj_esetek):
    ido   = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)
    targy = f"⚡ Csepel áramszünet – {db} új esemény | {ido}"

    sorok_html = ""
    sorok_txt  = ""

    for i, e in enumerate(uj_esetek, 1):
        f     = kinyert_adatok(e)
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

        sorok_txt += (
            f"\n{'─'*45}\n{i}. {badge}\n"
            f"Azonosító: {f['azonosito']}\n"
            f"Kezdés:    {f['kezdes']}\n"
            f"Vége:      {f['veg']}\n"
            f"Helyszín:  {f['utcak']}\n"
            f"Érintett:  {f['fogyaszto']} fogyasztó\n"
            + (f"Maps: {f['gmaps']}\n" if f['gmaps'] else "")
        )

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
  .btn{{display:inline-block;padding:9px 16px;margin:4px;border-radius:6px;
        text-decoration:none;font-weight:bold;color:#fff;font-size:12px}}
  .foot{{background:#ecf0f1;padding:12px 28px;font-size:11px;color:#95a5a6;text-align:center}}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>⚡ Csepel – Áramszünet értesítő</h1>
    <small>{ido} | {db} új esemény (XXI. kerület)</small>
  </div>
  <div class="body">
    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>
    <div style="text-align:center;margin-top:16px">
      <a href="https://www.eon.hu/hu/lakossagi/aram/aramszunet-informaciok.html"
         class="btn" style="background:#c0392b">⚡ E.ON térkép</a>
    </div>
  </div>
  <div class="foot">Automatikus értesítő – GitHub Actions | E.ON adatai alapján</div>
</div></body></html>"""

    szoveges = f"⚡ Csepel Áramszünet\nIdőpont: {ido}\n{sorok_txt}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"⚡ Áramszünet Monitor <{EMAIL_KULDO}>"
    msg["To"]      = EMAIL_CIMZETT
    msg.attach(MIMEText(szoveges, "plain", "utf-8"))
    msg.attach(MIMEText(html,     "html",  "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
        smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
    print(f"📧 E-mail elküldve: {targy}")


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"⚡ Csepel Áramszünet Monitor – {datetime.now().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi   = betolt_allapot()
    uj     = []

    for e in lekerdez_json(API_TERVEZETT, "TERVEZETT"):
        rid = hash_id(json.dumps(e["adat"], sort_keys=True))
        if rid not in regi.get("tervezett", {}):
            uj.append(e)
            regi.setdefault("tervezett", {})[rid] = datetime.now().isoformat()

    for e in lekerdez_json(API_UZEMZAVAR, "UZEMZAVAR"):
        rid = hash_id(json.dumps(e["adat"], sort_keys=True))
        if rid not in regi.get("uzemzavar", {}):
            uj.append(e)
            regi.setdefault("uzemzavar", {})[rid] = datetime.now().isoformat()

    print(f"\n⚡ Új események: {len(uj)}")
    if uj:
        email_kuldes(uj)
    else:
        print("✅ Nincs új esemény.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
