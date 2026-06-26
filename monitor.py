"""
🚁 Magyar Mentőhelikopter Monitor
Adatforrás: adsb.fi (ingyenes, kulcs nélkül)
Futtatás: GitHub Actions (percenként)
"""

import os
import json
import time
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

# ─────────────────────────────────────────────
#  ⚙️  KONFIGURÁCIÓ
#  Ezeket GitHub Secrets-ben kell beállítani!
#  (repo → Settings → Secrets → Actions)
# ─────────────────────────────────────────────
EMAIL_KULDO   = os.environ["EMAIL_KULDO"]    # pl. te@gmail.com
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]  # Gmail App Password
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT"] # ahová az értesítés megy

# ─────────────────────────────────────────────
#  📡  API FORRÁSOK (sorban próbálja)
# ─────────────────────────────────────────────
API_URLAK = [
    "https://opendata.adsb.fi/api/v2/country/HU",
    "https://api.adsb.one/v2/country/HU",
    "https://api.airplanes.live/v2/country/HU",
]

# ─────────────────────────────────────────────
#  🚁  ISMERT MENTŐHELIKOPTER ICAO24 KÓDOK
#  (Magyar Légimentő Nonprofit Kft. EC135 P2+ flotta)
# ─────────────────────────────────────────────
ISMERT_MENTO_ICAO = {
    "4b1806": "HA-ECO",
    "4b180b": "HA-ECP",
    "4b1810": "HA-ECQ",
    "4b1815": "HA-ECR",
    "4b181a": "HA-ECS",
    "4b181f": "HA-ECT",
    "4b1824": "HA-ECU",
    "4b1829": "HA-ECV",
    "4b182e": "HA-ECW",
}

# Magyar lajstromjel prefix és mentő callsign prefixek
MAGYAR_PREFIX       = "HA-"
MENTO_CALLSIGN_PREF = ["HEMS", "RESCUE", "MENTOR"]

# Talajközelség küszöb méterben
FOLD_KUSZOB_M = 50


# ════════════════════════════════════════════
#  📡  API LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez_helikopterek():
    for url in API_URLAK:
        try:
            print(f"🌐 Lekérdezés: {url}")
            r = requests.get(url, timeout=15, headers={
                "User-Agent": "MentoHelikopterMonitor/2.0 (github-actions)"
            })
            if r.status_code == 200:
                data = r.json()
                gepek = data.get("ac", [])
                print(f"✅ Forrás OK: {url} | Gépek: {len(gepek)}")
                return gepek
            else:
                print(f"⚠️ HTTP {r.status_code} – {url}")
        except Exception as e:
            print(f"❌ Hiba ({url}): {e}")
    print("❌ Minden forrás sikertelen.")
    return None


# ════════════════════════════════════════════
#  🔍  SZŰRÉS: MENTŐHELIKOPTER-E?
# ════════════════════════════════════════════
def mento_e(a):
    icao24   = (a.get("hex", "") or "").lower().strip()
    callsign = (a.get("flight", "") or "").strip().upper()
    reg      = (a.get("r", "") or "").strip().upper()

    if icao24 in ISMERT_MENTO_ICAO:
        return True
    if reg.startswith(MAGYAR_PREFIX):
        return True
    if callsign.startswith("HA"):
        return True
    if any(callsign.startswith(p) for p in MENTO_CALLSIGN_PREF):
        return True
    return False


# ════════════════════════════════════════════
#  📊  ÁLLAPOT FELDOLGOZÁS
# ════════════════════════════════════════════
def feldolgoz(a):
    """Nyers ADS-B rekordból tiszta Python dict."""
    icao24   = (a.get("hex", "") or "").lower().strip()
    callsign = (a.get("flight", "") or "").strip()
    reg      = (a.get("r", "") or "").strip()
    tipus    = (a.get("t", "") or "").strip()
    lat      = a.get("lat")
    lon      = a.get("lon")

    # Magasság ft → m
    alt_baro_raw = a.get("alt_baro")
    if alt_baro_raw == "ground" or alt_baro_raw == 0:
        baro_alt_m = 0
    elif alt_baro_raw is not None:
        baro_alt_m = round(alt_baro_raw * 0.3048)
    else:
        baro_alt_m = None

    geo_alt_raw = a.get("alt_geom")
    geo_alt_m = round(geo_alt_raw * 0.3048) if geo_alt_raw is not None else None

    on_ground = a.get("on_ground", False) or alt_baro_raw == "ground"

    # Talajközelség magasság alapján is
    alt_m = geo_alt_m if geo_alt_m is not None else baro_alt_m
    if alt_m is not None and alt_m <= FOLD_KUSZOB_M:
        on_ground = True

    # Sebesség kt → km/h
    gs = a.get("gs")
    velocity_kmh = round(gs * 1.852) if gs is not None else None

    heading = a.get("track")

    # Vertikális sebesség ft/min → m/s
    baro_rate = a.get("baro_rate")
    vert_rate_ms = round(baro_rate * 0.00508, 1) if baro_rate is not None else None

    squawk   = a.get("squawk")
    category = a.get("category", "")

    return {
        "icao24": icao24,
        "callsign": callsign,
        "reg": reg or ISMERT_MENTO_ICAO.get(icao24, ""),
        "tipus": tipus,
        "lat": lat,
        "lon": lon,
        "baro_alt_m": baro_alt_m,
        "geo_alt_m": geo_alt_m,
        "on_ground": on_ground,
        "velocity_kmh": velocity_kmh,
        "heading": heading,
        "vert_rate_ms": vert_rate_ms,
        "squawk": squawk,
        "category": category,
        "timestamp": time.time(),
    }


# ════════════════════════════════════════════
#  💾  ÁLLAPOT FÁJL (GitHub Actions artifact)
# ════════════════════════════════════════════
ALLAPOT_FAJL = "allapot.json"

def betolt_allapot():
    if os.path.exists(ALLAPOT_FAJL):
        try:
            with open(ALLAPOT_FAJL) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def ment_allapot(allapot):
    with open(ALLAPOT_FAJL, "w") as f:
        json.dump(allapot, f, indent=2)


# ════════════════════════════════════════════
#  📧  E-MAIL KÜLDÉS
# ════════════════════════════════════════════
def email_kuldes(esemeny):
    tipus   = esemeny["tipus"]
    gep     = esemeny["gep"]
    icao24  = gep["icao24"]
    cs      = gep["callsign"] or gep["reg"] or icao24.upper()
    reg     = gep["reg"] or "—"
    lat     = gep["lat"]
    lon     = gep["lon"]
    alt_m   = gep["geo_alt_m"] or gep["baro_alt_m"]
    vel     = gep["velocity_kmh"]
    hdg     = gep["heading"]
    vr      = gep["vert_rate_ms"]
    squawk  = gep["squawk"] or "—"
    cat     = gep["category"] or "—"

    ido = datetime.now().strftime("%Y.%m.%d %H:%M:%S")

    emoji    = "🚁⬆️" if tipus == "FELSZALLAS" else "🚁⬇️"
    tipus_hu = "FELSZÁLLÁS" if tipus == "FELSZALLAS" else "LESZÁLLÁS"
    szin     = "#e74c3c" if tipus == "FELSZALLAS" else "#2980b9"

    lat_str = f"{lat:.6f}" if lat is not None else "ismeretlen"
    lon_str = f"{lon:.6f}" if lon is not None else "ismeretlen"
    alt_str = f"{alt_m} m ({round(alt_m * 3.28084)} ft)" if alt_m is not None else "ismeretlen"
    vel_str = f"{vel} km/h" if vel is not None else "ismeretlen"
    hdg_str = f"{round(hdg)}°" if hdg is not None else "ismeretlen"
    vr_str  = (f"+{vr}" if vr and vr > 0 else str(vr)) + " m/s" if vr is not None else "ismeretlen"

    # ── Követési linkek ────────────────────────────────────────
    fr24_live    = f"https://www.flightradar24.com/{cs.strip()}"
    fr24_acdata  = f"https://www.flightradar24.com/data/aircraft/{icao24.upper()}"
    adsbexch     = f"https://globe.adsbexchange.com/?icao={icao24}"
    flightaware  = f"https://www.flightaware.com/live/modes/{icao24.upper()}/ident/0/zoom/9"
    airnav       = f"https://www.airnavradar.com/data/aircraft/{icao24.upper()}"
    planespotters= f"https://www.planespotters.net/hex/{icao24.upper()}"
    opensky      = f"https://opensky-network.org/aircraft-profile?icao24={icao24}"
    adsbfi       = f"https://adsb.fi/#icao={icao24.upper()}"

    gmaps = f"https://www.google.com/maps?q={lat},{lon}&z=13" if lat and lon else None
    osm   = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=13/{lat}/{lon}" if lat and lon else None

    # ── HTML e-mail ────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="hu">
<head><meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; background:#f4f4f4; margin:0; padding:0; }}
  .wrap {{ max-width:620px; margin:20px auto; background:#fff;
           border-radius:10px; overflow:hidden;
           box-shadow:0 4px 12px rgba(0,0,0,.15); }}
  .hdr {{ background:{szin}; color:#fff; padding:22px 28px; }}
  .hdr h1 {{ margin:0; font-size:21px; }}
  .hdr small {{ opacity:.85; font-size:13px; }}
  .body {{ padding:22px 28px; }}
  .badges {{ text-align:center; margin-bottom:14px; }}
  .badge {{ display:inline-block; background:#ecf0f1; border-radius:6px;
            padding:10px 16px; margin:6px; }}
  .badge .big {{ font-size:26px; font-weight:bold; color:#2c3e50; }}
  .badge .lbl {{ font-size:11px; color:#7f8c8d; text-transform:uppercase; }}
  table {{ width:100%; border-collapse:collapse; margin:14px 0; }}
  td {{ padding:7px 10px; border-bottom:1px solid #ecf0f1; font-size:13px; }}
  td:first-child {{ color:#7f8c8d; width:42%; font-weight:bold; }}
  .live-box {{ background:#fff8f0; border:2px solid #ff6600;
               border-radius:8px; padding:14px; margin:14px 0; text-align:center; }}
  .live-box h3 {{ margin:0 0 4px; color:#cc4400; font-size:14px; }}
  .live-box .note {{ font-size:11px; color:#888; margin-bottom:10px; }}
  .map-box {{ background:#f9f9f9; border-radius:8px;
              padding:14px; margin:14px 0; text-align:center; }}
  .btn {{ display:inline-block; padding:9px 16px; margin:4px;
          border-radius:6px; text-decoration:none; font-size:12px;
          font-weight:bold; color:#fff; }}
  .gmaps  {{ background:#4285f4; }} .osm    {{ background:#7cb342; }}
  .fr24   {{ background:#ff6600; }} .fr24ac {{ background:#cc4400; }}
  .adsbex {{ background:#1a1a2e; }} .fa     {{ background:#003087; }}
  .airnav {{ background:#0077cc; }} .ps     {{ background:#5b5ea6; }}
  .osky   {{ background:#2c7a4b; }} .adsbfi {{ background:#e67e22; }}
  .coords {{ font-family:monospace; font-size:15px; font-weight:bold;
             background:#ecf0f1; padding:7px 12px; border-radius:6px;
             display:inline-block; margin:6px 0; }}
  .foot {{ background:#ecf0f1; padding:12px 28px; font-size:11px;
           color:#95a5a6; text-align:center; }}
</style>
</head>
<body><div class="wrap">

<div class="hdr">
  <h1>{emoji} Magyar Mentőhelikopter {tipus_hu}</h1>
  <small>{ido} | Magyar Légimentő Nonprofit Kft.</small>
</div>

<div class="body">
  <div class="badges">
    <div class="badge">
      <div class="lbl">Hívójel / Callsign</div>
      <div class="big">{cs}</div>
    </div>
    <div class="badge">
      <div class="lbl">Lajstromjel</div>
      <div class="big">{reg}</div>
    </div>
    <div class="badge">
      <div class="lbl">ICAO24</div>
      <div class="big">{icao24.upper()}</div>
    </div>
  </div>

  <!-- ADATOK -->
  <table>
    <tr><td>⏰ Időpont</td><td>{ido}</td></tr>
    <tr><td>🚁 Esemény</td>
        <td><strong style="color:{szin}">{tipus_hu}</strong></td></tr>
    <tr><td>🌍 Szélesség</td><td>{lat_str}</td></tr>
    <tr><td>🌍 Hosszúság</td><td>{lon_str}</td></tr>
    <tr><td>⬆️ Magasság</td><td>{alt_str}</td></tr>
    <tr><td>💨 Sebesség</td><td>{vel_str}</td></tr>
    <tr><td>🧭 Irányszög</td><td>{hdg_str}</td></tr>
    <tr><td>↕️ Függőleges sebesség</td><td>{vr_str}</td></tr>
    <tr><td>📻 Squawk</td><td>{squawk}</td></tr>
    <tr><td>✈️ Kategória</td><td>{cat}</td></tr>
    <tr><td>🛩️ Típus</td><td>{gep["tipus"] or "—"}</td></tr>
  </table>

  <!-- ÉLŐ KÖVETÉS -->
  <div class="live-box">
    <h3>🔴 ÉLŐ KÖVETÉS – kattints a nyomon követéshez!</h3>
    <div class="note">Az alábbi linkek közvetlenül a gép pozíciójára nyílnak</div>
    <a href="{fr24_live}"   class="btn fr24"  >✈️ Flightradar24 – Élő</a>
    <a href="{adsbexch}"   class="btn adsbex">📡 ADS-B Exchange</a>
    <a href="{adsbfi}"     class="btn adsbfi">🟠 adsb.fi</a>
    <a href="{flightaware}"class="btn fa"    >🔵 FlightAware</a>
    <a href="{airnav}"     class="btn airnav">🟦 AirNav RadarBox</a>
    <br style="margin:4px 0">
    <a href="{fr24_acdata}"class="btn fr24ac">📋 FR24 Repülőgép adatlap</a>
    <a href="{planespotters}"class="btn ps"  >📷 Planespotters</a>
    <a href="{opensky}"    class="btn osky"  >🌐 OpenSky útvonal</a>
  </div>

  <!-- TÉRKÉP -->
  {"" if not gmaps else f'''
  <div class="map-box">
    <h3>🗺️ Pozíció a térképen</h3>
    <div class="coords">{lat_str}° É, {lon_str}° K</div><br>
    <a href="{gmaps}" class="btn gmaps">📍 Google Maps</a>
    <a href="{osm}"   class="btn osm"  >🗺️ OpenStreetMap</a>
  </div>
  '''}

</div>
<div class="foot">
  Automatikus értesítés – Magyar Mentőhelikopter Monitor (GitHub Actions)<br>
  Adatforrás: <a href="https://adsb.fi">adsb.fi</a> &amp;
  <a href="https://adsb.one">adsb.one</a>
</div>
</div></body></html>"""

    # Szöveges fallback
    szoveges = (
        f"Mentőhelikopter {tipus_hu}\n"
        f"{'─'*40}\n"
        f"Időpont:    {ido}\n"
        f"Hívójel:    {cs}\n"
        f"Lajstrom:   {reg}\n"
        f"ICAO24:     {icao24.upper()}\n"
        f"Szélesség:  {lat_str}\n"
        f"Hosszúság:  {lon_str}\n"
        f"Magasság:   {alt_str}\n"
        f"Sebesség:   {vel_str}\n"
        f"Irányszög:  {hdg_str}\n"
        f"Squawk:     {squawk}\n\n"
        f"── ÉLŐ KÖVETÉS ──\n"
        f"Flightradar24: {fr24_live}\n"
        f"ADS-B Exchange: {adsbexch}\n"
        f"adsb.fi: {adsbfi}\n"
        f"FlightAware: {flightaware}\n"
        f"AirNav: {airnav}\n"
        f"Planespotters: {planespotters}\n"
        + (f"\n── TÉRKÉP ──\nGoogle Maps: {gmaps}\nOpenStreetMap: {osm}\n" if gmaps else "")
    )

    targy = f"{emoji} Mentőhelikopter {tipus_hu} – {cs} | {ido}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"🚁 Mentőhelikopter Monitor <{EMAIL_KULDO}>"
    msg["To"]      = EMAIL_CIMZETT
    msg.attach(MIMEText(szoveges, "plain", "utf-8"))
    msg.attach(MIMEText(html,     "html",  "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
            smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
        print(f"📧 E-mail elküldve: {targy}")
    except Exception as e:
        print(f"❌ E-mail hiba: {e}")
        raise


# ════════════════════════════════════════════
#  🔁  ÁLLAPOT ÖSSZEHASONLÍTÁS
# ════════════════════════════════════════════
def osszehasonlit(regi, uj):
    esemenyek = []

    for icao, uj_gep in uj.items():
        regi_gep = regi.get(icao)

        if regi_gep is None:
            # Újonnan megjelent és levegőben van
            if not uj_gep["on_ground"]:
                esemenyek.append({"tipus": "FELSZALLAS", "gep": uj_gep})
        else:
            if regi_gep["on_ground"] and not uj_gep["on_ground"]:
                esemenyek.append({"tipus": "FELSZALLAS", "gep": uj_gep})
            elif not regi_gep["on_ground"] and uj_gep["on_ground"]:
                esemenyek.append({"tipus": "LESZALLAS",  "gep": uj_gep})

    # Eltűnt gépek: volt levegőben, most nem látható
    for icao, regi_gep in regi.items():
        if icao not in uj and not regi_gep["on_ground"]:
            elapsed = time.time() - regi_gep.get("timestamp", 0)
            if elapsed > 120:  # 2 percig nem látható → leszállt
                esemenyek.append({"tipus": "LESZALLAS", "gep": regi_gep})

    return esemenyek


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*50}")
    print(f"🚁 Mentőhelikopter Monitor – {datetime.now().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*50}")

    # Lekérdezés
    gepek_raw = lekerdez_helikopterek()
    if gepek_raw is None:
        print("❌ API nem elérhető, kilépés.")
        return

    # Szűrés és feldolgozás
    uj_allapot = {}
    for a in gepek_raw:
        if mento_e(a):
            gep = feldolgoz(a)
            uj_allapot[gep["icao24"]] = gep

    print(f"🚁 Szűrt mentőgépek: {len(uj_allapot)}")

    # Előző állapot betöltése
    regi_allapot = betolt_allapot()
    print(f"📂 Előző állapotból ismert gépek: {len(regi_allapot)}")

    # Összehasonlítás
    esemenyek = osszehasonlit(regi_allapot, uj_allapot)
    print(f"⚡ Változások száma: {len(esemenyek)}")

    # E-mail küldés minden eseményre
    for e in esemenyek:
        print(f"  → {e['tipus']}: {e['gep']['callsign'] or e['gep']['icao24']}")
        email_kuldes(e)

    # Állapot mentése
    ment_allapot(uj_allapot)
    print("💾 Állapot elmentve.")
    print("✅ Kész.\n")


if __name__ == "__main__":
    main()
