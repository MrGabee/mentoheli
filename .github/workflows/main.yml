"""
⚡ E.ON Áramszünet Monitor – Csepel (XXI. kerület)
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
#  ⚙️  KONFIGURÁCIÓ
# ─────────────────────────────────────────────
EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT"]

API_TERVEZETT = "https://www.eon.hu/content/dam/eon/eon-hungary/external-app-data/outages/poweroutage.json"
API_UZEMZAVAR = "https://www.eon.hu/content/dam/eon/eon-hungary/external-app-data/outages/unexpectedoutage.json"

# Csepel bounding box
CSEPEL_LAT_MIN = 47.38
CSEPEL_LAT_MAX = 47.47
CSEPEL_LON_MIN = 19.00
CSEPEL_LON_MAX = 19.12

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
    # Koordináta alapú szűrés - egyetlen pont
    coords = eset.get("coordinates") or eset.get("coordinate") or {}
    if isinstance(coords, dict):
        lat = coords.get("lat") or coords.get("latitude")
        lon = coords.get("lng") or coords.get("lon") or coords.get("longitude")
        if lat and lon and koordinata_csepel_e(lat, lon):
            return True

    # Koordináta lista
    coord_list = eset.get("affectedCoordinates") or []
    if isinstance(coord_list, list):
        for c in coord_list:
            if isinstance(c, dict):
                lat = c.get("lat") or c.get("latitude")
                lon = c.get("lng") or c.get("lon") or c.get("longitude")
                if lat and lon and koordinata_csepel_e(lat, lon):
                    return True

    # Szöveges szűrés
    eset_str = json.dumps(eset, ensure_ascii=False).lower()
    if szoveg_csepel_e(eset_str):
        return True

    return False


# ════════════════════════════════════════════
#  🕐  IDŐPONT FORMÁZÁS
# ════════════════════════════════════════════
def ido_format(mezo):
    """Bármilyen formátumú időpontot olvasható stringgé alakít."""
    if not mezo:
        return "—"
    if isinstance(mezo, dict):
        datum = mezo.get("date") or mezo.get("datum") or ""
        ido   = mezo.get("time") or mezo.get("ido") or ""
        if datum and ido:
            return f"{datum} {ido}"
        elif datum:
            return datum
        elif ido:
            return ido
        # Ha más kulcsok vannak
        return str(mezo)
    if isinstance(mezo, (int, float)):
        # Unix timestamp
        try:
            return datetime.fromtimestamp(mezo).strftime("%Y.%m.%d %H:%M")
        except Exception:
            return str(mezo)
    return str(mezo).replace("T", " ").replace("Z", "")


# ════════════════════════════════════════════
#  📡  API LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez_json(url, tipus):
    try:
        print(f"📡 Lekérdezés ({tipus}): {url}")
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ HTTP {r.status_code}")
            return []

        data = r.json()

        # Nyers JSON kiírása debughoz
        print(f"  🔍 JSON kulcsok: {list(data.keys()) if isinstance(data, dict) else 'lista'}")

        esetek = []
        if isinstance(data, list):
            esetek = data
        elif isinstance(data, dict):
            for kulcs in ["outages", "data", "items", "results", "events", "powerOutages", "plannedOutages"]:
                if kulcs in data:
                    esetek = data[kulcs]
                    print(f"  📂 Kulcs: '{kulcs}', elemek: {len(esetek)}")
                    break

        if not esetek:
            print(f"  ⚠️ Nem találtam listát! Elérhető kulcsok: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
            # Ha az első elem struktúráját látni akarjuk
            if isinstance(data, dict) and data:
                elso_ertek = list(data.values())[0]
                if isinstance(elso_ertek, list) and elso_ertek:
                    print(f"  🔍 Első elem kulcsai: {list(elso_ertek[0].keys()) if isinstance(elso_ertek[0], dict) else 'N/A'}")
            return []

        print(f"  📊 Összes eset: {len(esetek)}")

        # Első elem struktúrájának kiírása
        if esetek and isinstance(esetek[0], dict):
            print(f"  🔍 Első elem kulcsai: {list(esetek[0].keys())}")

        csepel_esetek = []
        for e in esetek:
            if csepel_e(e):
                csepel_esetek.append({"tipus": tipus, "adat": e, "url": url})

        print(f"  🎯 Csepeles eset: {len(csepel_esetek)}")
        return csepel_esetek

    except Exception as ex:
        print(f"  ❌ Hiba: {ex}")
        import traceback
        traceback.print_exc()
        return []


# ════════════════════════════════════════════
#  📧  ADAT KINYERÉS ÉS E-MAIL
# ════════════════════════════════════════════
def kinyert_adatok(eset):
    """Az áramszünet adatait kinyeri a JSON-ból, minden lehetséges mezőnevet próbálva."""
    a = eset["adat"]

    # Kezdési időpont - minden lehetséges mezőnév
    kezdes_raw = (a.get("startTime") or a.get("start") or a.get("startDate") or
                  a.get("plannedStart") or a.get("plannedStartDate") or
                  a.get("from") or a.get("begin") or a.get("kezdes") or
                  a.get("kezdesIdopont") or None)

    # Befejezési időpont
    veg_raw = (a.get("endTime") or a.get("end") or a.get("endDate") or
               a.get("plannedEnd") or a.get("plannedEndDate") or
               a.get("to") or a.get("finish") or a.get("veg") or
               a.get("vegIdopont") or None)

    # Koordináták
    coords = a.get("coordinates") or a.get("coordinate") or {}
    lat = lon = None
    if isinstance(coords, dict):
        lat = coords.get("lat") or coords.get("latitude")
        lon = coords.get("lng") or coords.get("lon") or coords.get("longitude")

    # Érintett utcák/cím
    utcak = (a.get("affectedStreets") or a.get("streets") or
             a.get("address") or a.get("location") or
             a.get("cim") or a.get("utca") or "")
    if isinstance(utcak, list):
        utcak = ", ".join(str(u) for u in utcak[:8])

    # Érintett fogyasztók száma
    fogyaszto = (a.get("affectedCustomers") or a.get("customers") or
                 a.get("numberOfAffected") or a.get("affected") or "—")

    # Leírás/ok
    leiras = (a.get("description") or a.get("reason") or
              a.get("cause") or a.get("info") or a.get("leiras") or "")

    # Azonosító
    azonosito = a.get("id") or a.get("outageId") or a.get("internalId") or "—"

    gmaps = f"https://www.google.com/maps?q={lat},{lon}&z=14" if lat and lon else None

    return {
        "azonosito": str(azonosito),
        "kezdes": ido_format(kezdes_raw),
        "veg": ido_format(veg_raw),
        "lat": lat,
        "lon": lon,
        "utcak": str(utcak),
        "fogyaszto": str(fogyaszto),
        "leiras": str(leiras)[:300],
        "gmaps": gmaps,
        "tipus": eset["tipus"],
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
        f    = kinyert_adatok(e)
        szin  = "#c0392b" if f["tipus"] == "UZEMZAVAR" else "#e67e22"
        badge = "🔴 ÉLŐ ÜZEMZAVAR" if f["tipus"] == "UZEMZAVAR" else "📋 TERVEZETT ÁRAMSZÜNET"

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <div style="margin-bottom:10px">
              <span style="background:{szin};color:#fff;padding:5px 12px;
                           border-radius:4px;font-size:13px;font-weight:bold">
                {badge}
              </span>
            </div>
            <table style="font-size:13px;width:100%;border-collapse:collapse">
              <tr><td style="color:#888;padding:3px 8px 3px 0;width:150px">🔢 Azonosító:</td>
                  <td style="padding:3px 0">{f['azonosito']}</td></tr>
              <tr><td style="color:#888;padding:3px 8px 3px 0">⏰ Kezdés:</td>
                  <td style="padding:3px 0"><strong>{f['kezdes']}</strong></td></tr>
              <tr><td style="color:#888;padding:3px 8px 3px 0">⏰ Vége:</td>
                  <td style="padding:3px 0"><strong>{f['veg']}</strong></td></tr>
              {"<tr><td style='color:#888;padding:3px 8px 3px 0'>🏘️ Helyszín:</td><td style='padding:3px 0'>" + f['utcak'] + "</td></tr>" if f['utcak'] and f['utcak'] != 'None' else ""}
              {"<tr><td style='color:#888;padding:3px 8px 3px 0'>👥 Érintett:</td><td style='padding:3px 0'>" + f['fogyaszto'] + " fogyasztó</td></tr>" if f['fogyaszto'] not in ("—", "None", "") else ""}
              {"<tr><td style='color:#888;padding:3px 8px 3px 0'>📝 Leírás:</td><td style='padding:3px 0'>" + f['leiras'] + "</td></tr>" if f['leiras'] and f['leiras'] != 'None' else ""}
            </table>
            {"<div style='margin-top:10px'><a href='" + f['gmaps'] + "' style='background:#4285f4;color:#fff;padding:7px 14px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:bold'>📍 Google Maps</a></div>" if f['gmaps'] else ""}
          </td>
        </tr>"""

        sorok_txt += (
            f"\n{'─'*45}\n"
            f"{i}. {badge}\n"
            f"Azonosító: {f['azonosito']}\n"
            f"Kezdés:    {f['kezdes']}\n"
            f"Vége:      {f['veg']}\n"
            f"Helyszín:  {f['utcak']}\n"
            f"Érintett:  {f['fogyaszto']}\n"
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
         class="btn" style="background:#c0392b">⚡ E.ON térkép</a>
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

    # Tervezett áramszünetek
    tervezett = lekerdez_json(API_TERVEZETT, "TERVEZETT")
    for e in tervezett:
        rid = hash_id(json.dumps(e["adat"], sort_keys=True))
        if rid not in regi_allapot.get("tervezett", {}):
            uj_esetek.append(e)
            regi_allapot.setdefault("tervezett", {})[rid] = {
                "talalt": datetime.now().isoformat()
            }

    # Élő üzemzavarok
    uzemzavar = lekerdez_json(API_UZEMZAVAR, "UZEMZAVAR")
    for e in uzemzavar:
        rid = hash_id(json.dumps(e["adat"], sort_keys=True))
        if rid not in regi_allapot.get("uzemzavar", {}):
            uj_esetek.append(e)
            regi_allapot.setdefault("uzemzavar", {})[rid] = {
                "talalt": datetime.now().isoformat()
            }

    print(f"\n⚡ Új események: {len(uj_esetek)}")

    if uj_esetek:
        email_kuldes(uj_esetek)
    else:
        print("✅ Nincs új Csepelt érintő áramszünet.")

    ment_allapot(regi_allapot)
    print("💾 Állapot elmentve.")
    print("✅ Kész.\n")


if __name__ == "__main__":
    main()
