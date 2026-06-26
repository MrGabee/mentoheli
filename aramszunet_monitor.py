"""
⚡ ELMŰ / E.ON Áramszünet Monitor – Csepel (XXI. kerület)
Figyeli:
  1. Tervezett áramszünetek (poweroutage.json)
  2. Élő/váratlan üzemzavarok (unexpectedoutage.json)
Futtatás: GitHub Actions (percenként, self-loop)
"""

import os
import json
import hashlib
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ─────────────────────────────────────────────
#  ⚙️  KONFIGURÁCIÓ (GitHub Secrets-ből jön)
# ─────────────────────────────────────────────
EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT"]

# ─────────────────────────────────────────────
#  📡  E.ON JSON API VÉGPONTOK
# ─────────────────────────────────────────────
API_TERVEZETT  = "https://www.eon.hu/content/dam/eon/eon-hungary/external-app-data/outages/poweroutage.json"
API_UZEMZAVAR  = "https://www.eon.hu/content/dam/eon/eon-hungary/external-app-data/outages/unexpectedoutage.json"

# ─────────────────────────────────────────────
#  📍  CSEPEL BOUNDING BOX (WGS84)
# ─────────────────────────────────────────────
CSEPEL_LAT_MIN = 47.38
CSEPEL_LAT_MAX = 47.47
CSEPEL_LON_MIN = 19.00
CSEPEL_LON_MAX = 19.12

# Csepel szöveges kulcsszavak (fallback)
CSEPEL_KULCSSZAVAK = ["csepel", "xxi", "21. ker", "budapest xxi", "bp. xxi", "csepeli"]

ALLAPOT_FAJL = "aramszunet_allapot.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.eon.hu/",
}

# ════════════════════════════════════════════
#  💾  ÁLLAPOT KEZELÉS
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
#  📍  CSEPEL SZŰRŐ
# ════════════════════════════════════════════
def koordinata_csepel_e(lat, lon):
    try:
        return (CSEPEL_LAT_MIN <= float(lat) <= CSEPEL_LAT_MAX and
                CSEPEL_LON_MIN <= float(lon) <= CSEPEL_LON_MAX)
    except Exception:
        return False

def szoveg_csepel_e(szoveg):
    s = szoveg.lower()
    return any(k in s for k in CSEPEL_KULCSSZAVAK)

def csepel_e(eset):
    """Megvizsgálja hogy az áramszünet érinti-e Csepelt."""
    # Koordináta alapú szűrés
    coords = eset.get("coordinates") or eset.get("coordinate") or {}
    if isinstance(coords, dict):
        lat = coords.get("lat") or coords.get("latitude")
        lon = coords.get("lng") or coords.get("lon") or coords.get("longitude")
        if lat and lon and koordinata_csepel_e(lat, lon):
            return True

    # Koordináta lista esetén
    coord_list = eset.get("affectedCoordinates") or eset.get("coordinates", [])
    if isinstance(coord_list, list):
        for c in coord_list:
            if isinstance(c, dict):
                lat = c.get("lat") or c.get("latitude")
                lon = c.get("lng") or c.get("lon") or c.get("longitude")
                if lat and lon and koordinata_csepel_e(lat, lon):
                    return True

    # Szöveges szűrés (cím, leírás, stb.)
    eset_str = json.dumps(eset, ensure_ascii=False).lower()
    if szoveg_csepel_e(eset_str):
        return True

    # Kerület szám alapján
    kerulet = str(eset.get("district", "") or eset.get("kerület", "") or "")
    if "21" in kerulet or "xxi" in kerulet.lower():
        return True

    return False


# ════════════════════════════════════════════
#  📋  API LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez_json(url, tipus):
    try:
        print(f"📡 Lekérdezés ({tipus}): {url}")
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ HTTP {r.status_code}")
            return []

        data = r.json()

        # Az outages tömb megkeresése
        esetek = []
        if isinstance(data, list):
            esetek = data
        elif isinstance(data, dict):
            esetek = (data.get("outages") or data.get("data") or
                     data.get("items") or data.get("results") or [])

        print(f"  📊 Összes eset: {len(esetek)}")

        # Csepel szűrés
        csepel_esetek = []
        for e in esetek:
            if csepel_e(e):
                csepel_esetek.append({
                    "tipus": tipus,
                    "adat": e,
                    "url": url
                })

        print(f"  🎯 Csepeles eset: {len(csepel_esetek)}")
        return csepel_esetek

    except Exception as ex:
        print(f"  ❌ Hiba: {ex}")
        return []


# ════════════════════════════════════════════
#  📧  E-MAIL KÜLDÉS
# ════════════════════════════════════════════
def formatalt_eset(eset):
    """Áramszünet adatait olvasható formátumba hozza."""
    a = eset["adat"]
    tipus = eset["tipus"]

    # Időpontok
    kezdes = a.get("startTime") or a.get("start") or a.get("plannedStart") or a.get("from") or "—"
    veg    = a.get("endTime")   or a.get("end")   or a.get("plannedEnd")   or a.get("to")   or "—"

    # Koordináták
    coords = a.get("coordinates") or a.get("coordinate") or {}
    lat = coords.get("lat") or coords.get("latitude")  if isinstance(coords, dict) else None
    lon = coords.get("lng") or coords.get("lon")        if isinstance(coords, dict) else None

    # Érintett utcák
    utcak = a.get("affectedStreets") or a.get("streets") or a.get("address") or ""
    if isinstance(utcak, list):
        utcak = ", ".join(str(u) for u in utcak[:5])

    # Érintett háztartások
    hztart = a.get("affectedCustomers") or a.get("customers") or a.get("numberOfAffected") or "—"

    # Leírás
    leiras = a.get("description") or a.get("reason") or a.get("cause") or ""

    gmaps = f"https://www.google.com/maps?q={lat},{lon}&z=14" if lat and lon else None

    return {
        "kezdes": kezdes,
        "veg": veg,
        "lat": lat,
        "lon": lon,
        "utcak": utcak,
        "hztart": hztart,
        "leiras": leiras,
        "gmaps": gmaps,
        "tipus": tipus,
        "raw": json.dumps(a, ensure_ascii=False, indent=2)[:800]
    }

def email_kuldes(uj_esetek):
    if not uj_esetek:
        return

    ido = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    db  = len(uj_esetek)
    targy = f"⚡ Csepel áramszünet – {db} új esemény | {ido}"

    sorok_html = ""
    sorok_txt  = ""

    for i, e in enumerate(uj_esetek, 1):
        f = formatalt_eset(e)
        tipus    = f["tipus"]
        szin     = "#c0392b" if tipus == "UZEMZAVAR" else "#e67e22"
        badge    = "🔴 ÉLŐ ÜZEMZAVAR" if tipus == "UZEMZAVAR" else "📋 TERVEZETT ÁRAMSZÜNET"

        sorok_html += f"""
        <tr style="border-bottom:1px solid #eee">
          <td style="padding:14px;vertical-align:top;width:20px;color:#999">{i}.</td>
          <td style="padding:14px">
            <div style="margin-bottom:8px">
              <span style="background:{szin};color:#fff;padding:4px 10px;
                           border-radius:4px;font-size:12px;font-weight:bold">
                {badge}
              </span>
            </div>
            <table style="font-size:13px;width:100%">
              <tr><td style="color:#888;width:140px">⏰ Kezdés:</td><td>{f['kezdes']}</td></tr>
              <tr><td style="color:#888">⏰ Vége:</td><td>{f['veg']}</td></tr>
              {"<tr><td style='color:#888'>🏘️ Utcák:</td><td>" + f['utcak'] + "</td></tr>" if f['utcak'] else ""}
              {"<tr><td style='color:#888'>👥 Érintett:</td><td>" + str(f['hztart']) + " fogyasztó</td></tr>" if f['hztart'] != "—" else ""}
              {"<tr><td style='color:#888'>📝 Leírás:</td><td>" + f['leiras'] + "</td></tr>" if f['leiras'] else ""}
            </table>
            {"<div style='margin-top:8px'><a href='" + f['gmaps'] + "' style='background:#4285f4;color:#fff;padding:6px 12px;border-radius:4px;text-decoration:none;font-size:12px'>📍 Google Maps</a></div>" if f['gmaps'] else ""}
          </td>
        </tr>"""

        sorok_txt += (
            f"\n{'─'*45}\n"
            f"{i}. {badge}\n"
            f"Kezdés: {f['kezdes']}\n"
            f"Vége:   {f['veg']}\n"
            f"Utcák:  {f['utcak']}\n"
            f"Érintett: {f['hztart']}\n"
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
    <div style="text-align:center;margin-top:16px">
      <a href="https://www.eon.hu/hu/lakossagi/aram/aramszunet-informaciok.html"
         class="btn" style="background:#c0392b">⚡ E.ON áramszünet térkép</a>
      <a href="https://www.eon.hu/content/dam/eon/eon-hungary/external-app-data/outages/poweroutage.json"
         class="btn" style="background:#e67e22">📋 Tervezett JSON</a>
      <a href="https://www.eon.hu/content/dam/eon/eon-hungary/external-app-data/outages/unexpectedoutage.json"
         class="btn" style="background:#2980b9">🔴 Élő JSON</a>
    </div>
  </div>
  <div class="foot">
    Automatikus értesítő – GitHub Actions | E.ON adatai alapján
  </div>
</div></body></html>"""

    szoveges = (
        f"⚡ Csepel Áramszünet Értesítő\n"
        f"Időpont: {ido} | Új események: {db}\n"
        f"{sorok_txt}\n"
        f"E.ON térkép: https://www.eon.hu/hu/lakossagi/aram/aramszunet-informaciok.html\n"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"⚡ Áramszünet Monitor <{EMAIL_KULDO}>"
    msg["To"]      = EMAIL_CIMZETT
    msg.attach(MIMEText(szoveges, "plain", "utf-8"))
    msg.attach(MIMEText(html,     "html",  "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
            smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
        print(f"📧 E-mail elküldve: {targy}")
    except Exception as ex:
        print(f"❌ E-mail hiba: {ex}")
        raise


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"⚡ Csepel Áramszünet Monitor – {datetime.now().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi_allapot = betolt_allapot()
    uj_esetek    = []

    # ── Tervezett áramszünetek ────────────────
    tervezett = lekerdez_json(API_TERVEZETT, "TERVEZETT")
    for e in tervezett:
        rid = hash_id(json.dumps(e["adat"], sort_keys=True))
        if rid not in regi_allapot.get("tervezett", {}):
            uj_esetek.append(e)
            regi_allapot.setdefault("tervezett", {})[rid] = {
                "talalt": datetime.now().isoformat()
            }

    # ── Élő üzemzavarok ──────────────────────
    uzemzavar = lekerdez_json(API_UZEMZAVAR, "UZEMZAVAR")
    for e in uzemzavar:
        rid = hash_id(json.dumps(e["adat"], sort_keys=True))
        if rid not in regi_allapot.get("uzemzavar", {}):
            uj_esetek.append(e)
            regi_allapot.setdefault("uzemzavar", {})[rid] = {
                "talalt": datetime.now().isoformat()
            }

    print(f"\n⚡ Új (még nem értesített) események: {len(uj_esetek)}")

    if uj_esetek:
        email_kuldes(uj_esetek)
    else:
        print("✅ Nincs új Csepelt érintő áramszünet.")

    ment_allapot(regi_allapot)
    print("💾 Állapot elmentve.")
    print("✅ Kész.\n")


if __name__ == "__main__":
    main()
