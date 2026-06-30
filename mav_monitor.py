"""
🚁 Magyar Mentőhelikopter Monitor
Adatforrás: adsb.fi (ingyenes, kulcs nélkül)
Szűrés: MEDIC callsign (kizárólag magyar mentőhelikopterek)
Futtatás: GitHub Actions (percenként, self-loop)
"""

import os
import json
import time
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

# ─────────────────────────────────────────────
#  🕐  MAGYAR IDŐZÓNA (UTC+2, GitHub Actions UTC-t használ)
# ─────────────────────────────────────────────
MAGYAR_TZ = timezone(timedelta(hours=2))

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


# ─────────────────────────────────────────────
#  ⚙️  KONFIGURÁCIÓ (GitHub Secrets-ből jön)
# ─────────────────────────────────────────────
EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT"]

# ─────────────────────────────────────────────
#  📡  API FORRÁSOK
# ─────────────────────────────────────────────
# Ismert ICAO24 kódok – minden gépet közvetlenül lekérdezünk
MENTO_ICAO_MAP = {
    "47129c": "HA-HBG",  # Marcali (MEDIC3)
    "47129d": "HA-HBH",  # Miskolc (MEDIC6)
    "4712a0": "HA-HBK",  # ?
    "4712a1": "HA-HBL",  # Nyíregyháza
    "4712a2": "HA-HBM",  # Budaörs (tartalék)
    "4712a3": "HA-HBN",  # Budaörs
    "4712a4": "HA-HBO",  # Debrecen (MEDIC7)
}

# Ha ismerjük az összes ICAO-t, direkt lekérdezés
API_URLAK_ICAO = [
    "https://api.airplanes.live/v2/icao/{icao}",      # airplanes.live
    "https://opendata.adsb.fi/api/v2/icao/{icao}",    # adsb.fi
    "https://api.adsb.one/v2/icao/{icao}",            # adsb.one
    "https://api.adsb.lol/v2/icao/{icao}",            # adsb.lol
]

# OpenSky külön – más formátum, külön dolgozzuk fel
OPENSKY_URL = "https://opensky-network.org/api/states/all?icao24={icao}"

# Ország + callsign alapú lekérdezés
API_URLAK = [
    # Ország lista
    "https://opendata.adsb.fi/api/v2/country/HU",
    "https://api.adsb.one/v2/country/HU",
    "https://api.airplanes.live/v2/country/HU",
    "https://api.adsb.lol/v2/country/HU",
    # Callsign alapú direkt lekérdezés
    "https://api.airplanes.live/v2/callsign/MEDIC1",
    "https://api.airplanes.live/v2/callsign/MEDIC2",
    "https://api.airplanes.live/v2/callsign/MEDIC3",
    "https://api.airplanes.live/v2/callsign/MEDIC4",
    "https://api.airplanes.live/v2/callsign/MEDIC5",
    "https://api.airplanes.live/v2/callsign/MEDIC6",
    "https://api.airplanes.live/v2/callsign/MEDIC7",
    "https://api.airplanes.live/v2/callsign/MEDIKOPTER5",
    "https://api.adsb.lol/v2/callsign/MEDIC1",
    "https://api.adsb.lol/v2/callsign/MEDIC2",
    "https://api.adsb.lol/v2/callsign/MEDIC3",
    "https://api.adsb.lol/v2/callsign/MEDIC4",
    "https://api.adsb.lol/v2/callsign/MEDIC5",
    "https://api.adsb.lol/v2/callsign/MEDIC6",
    "https://api.adsb.lol/v2/callsign/MEDIC7",
    "https://api.adsb.lol/v2/callsign/MEDIKOPTER5",
    # Lajstromjel alapú lekérdezés
    "https://api.airplanes.live/v2/reg/HA-HBG",
    "https://api.airplanes.live/v2/reg/HA-HBH",
    "https://api.airplanes.live/v2/reg/HA-HBK",
    "https://api.airplanes.live/v2/reg/HA-HBL",
    "https://api.airplanes.live/v2/reg/HA-HBM",
    "https://api.airplanes.live/v2/reg/HA-HBN",
    "https://api.airplanes.live/v2/reg/HA-HBO",
]

# ─────────────────────────────────────────────
#  🚁  SZŰRÉS – csak MEDIC callsign
#  (kizárólag magyar mentőhelikopterek)
# ─────────────────────────────────────────────
ALLAPOT_FAJL  = "allapot.json"
FOLD_KUSZOB_M = 50  # méter – ennél alacsonyabb = földön

HEADERS = {
    "User-Agent": "MentoHelikopterMonitor/2.0 (github-actions)"
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
    return {}

def ment_allapot(allapot):
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=2)


# ════════════════════════════════════════════
#  🔍  SZŰRŐ – mentőhelikopter-e?
# ════════════════════════════════════════════
def mento_e(a):
    callsign = (a.get("flight") or "").strip().upper()
    reg      = (a.get("r") or "").strip().upper()

    # Magyar mentőhelikopter callsign-ok (7 bázis):
    # MEDIC1  – Budaörs
    # MEDIC2  – Balatonfüred
    # MEDIC3  – Marcali
    # MEDIC4  – Szekszárd
    # MEDIC5  – (tartalék)
    # MEDIC6  – Miskolc
    # MEDIC7  – Debrecen
    # MEDIKOPTER5 – Szentes
    MENTO_CALLSIGN = {
        "MEDIC1", "MEDIC2", "MEDIC3", "MEDIC4",
        "MEDIC5", "MEDIC6", "MEDIC7",
        "MEDIKOPTER5",
    }

    # Ismert lajstromjelek
    MENTO_LAJSTROM = {
        "HA-HBG", "HA-HBH", "HA-HBK",
        "HA-HBL", "HA-HBM", "HA-HBN", "HA-HBO"
    }

    return (
        callsign in MENTO_CALLSIGN or
        callsign.startswith("MEDIC") or
        callsign.startswith("MEDIKOPTER") or
        reg in MENTO_LAJSTROM
    )


# ════════════════════════════════════════════
#  📡  API LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez():
    gepek = {}  # icao → gép adat (duplikátum szűrés)

    # 1. ICAO alapú direkt lekérdezés – minden ismert gép
    for icao, reg in MENTO_ICAO_MAP.items():
        for url_tmpl in API_URLAK_ICAO:
            if "{icao}" not in url_tmpl:
                continue
            url = url_tmpl.format(icao=icao)
            try:
                r = requests.get(url, timeout=10, headers=HEADERS)
                if r.status_code == 200:
                    data = r.json()
                    ac = data.get("ac", [])
                    if ac:
                        for g in ac:
                            key = g.get("hex", icao).lower()
                            gepek[key] = g
                        print(f"✅ ICAO {icao} ({reg}): megtalálva")
                        break
            except Exception as e:
                pass

    # 2. Ország + callsign alapú lekérdezés
    for url in API_URLAK:
        try:
            r = requests.get(url, timeout=15, headers=HEADERS)
            if r.status_code == 200:
                data = r.json()
                ac_lista = data.get("ac", [])
                for g in ac_lista:
                    key = g.get("hex", "").lower()
                    if key and key not in gepek:
                        gepek[key] = g
                if "country" in url:
                    print(f"✅ Ország lista: {len(ac_lista)} gép")
                elif "callsign" in url and ac_lista:
                    cs = url.split("callsign/")[-1]
                    print(f"✅ Callsign {cs}: megtalálva")
        except Exception as e:
            pass

    # 3. OpenSky Network – más formátum, külön feldolgozás
    # Válasz formátum: {"states": [[icao24, callsign, country, ..., lat, lon, ...]]}
    # Oszlopok: 0=icao24, 1=callsign, 2=origin_country, 5=lon, 6=lat, 7=baro_alt,
    #           8=on_ground, 9=velocity, 10=heading, 11=vert_rate
    for icao, reg in MENTO_ICAO_MAP.items():
        if icao in gepek:
            continue  # már megvan más forrásból
        try:
            url = OPENSKY_URL.format(icao=icao)
            r = requests.get(url, timeout=10, headers=HEADERS)
            if r.status_code == 200:
                data = r.json()
                states = data.get("states") or []
                for s in states:
                    if not s or len(s) < 9:
                        continue
                    # OpenSky → standard formátumra alakítás
                    g = {
                        "hex":        (s[0] or "").lower(),
                        "flight":     (s[1] or "").strip(),
                        "r":          reg,
                        "lat":        s[6],
                        "lon":        s[5],
                        "alt_baro":   int(s[7] / 0.3048) if s[7] else "ground",
                        "on_ground":  s[8],
                        "gs":         int(s[9] * 1.944) if s[9] else 0,  # m/s → kt
                        "track":      s[10],
                    }
                    key = g["hex"]
                    if key and key not in gepek:
                        gepek[key] = g
                        print(f"✅ OpenSky {icao} ({reg}): megtalálva")
        except Exception:
            pass

    eredmeny = list(gepek.values())
    print(f"📊 Összesített egyedi gépek: {len(eredmeny)}")
    return eredmeny if eredmeny else None


# ════════════════════════════════════════════
#  📊  ADATOK FELDOLGOZÁSA
# ════════════════════════════════════════════
def feldolgoz(a):
    icao24   = (a.get("hex", "") or "").lower().strip()
    callsign = (a.get("flight", "") or "").strip()
    reg      = (a.get("r", "") or ISMERT_LAJSTROM.get(icao24, "")).strip()
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

    alt_m = geo_alt_m if geo_alt_m is not None else baro_alt_m
    if alt_m is not None and alt_m <= FOLD_KUSZOB_M:
        on_ground = True

    # Sebesség kt → km/h
    gs = a.get("gs")
    velocity_kmh = round(gs * 1.852) if gs is not None else None

    heading  = a.get("track")
    baro_rate = a.get("baro_rate")
    vert_rate_ms = round(baro_rate * 0.00508, 1) if baro_rate is not None else None

    squawk   = a.get("squawk")
    category = a.get("category", "")

    return {
        "icao24":       icao24,
        "callsign":     callsign,
        "reg":          reg,
        "tipus":        tipus,
        "lat":          lat,
        "lon":          lon,
        "baro_alt_m":   baro_alt_m,
        "geo_alt_m":    geo_alt_m,
        "on_ground":    on_ground,
        "velocity_kmh": velocity_kmh,
        "heading":      heading,
        "vert_rate_ms": vert_rate_ms,
        "squawk":       squawk,
        "category":     category,
        "timestamp":    time.time(),
    }

# Ismert lajstromjelek ICAO24 alapján
ISMERT_LAJSTROM = {
    "47129c": "HA-HBG",  # Marcali
    "47129d": "HA-HBH",  # Miskolc
    "4712a0": "HA-HBK",
    "4712a1": "HA-HBL",  # Nyíregyháza
    "4712a2": "HA-HBM",  # Budaörs tartalék
    "4712a3": "HA-HBN",  # Budaörs
    "4712a4": "HA-HBO",  # Debrecen
}


# ════════════════════════════════════════════
#  🔁  ÁLLAPOT ÖSSZEHASONLÍTÁS
# ════════════════════════════════════════════
def osszehasonlit(regi, uj):
    esemenyek = []

    for icao, uj_gep in uj.items():
        regi_gep = regi.get(icao)

        if regi_gep is None:
            if not uj_gep["on_ground"]:
                esemenyek.append({"tipus": "FELSZALLAS", "gep": uj_gep})
        else:
            if regi_gep["on_ground"] and not uj_gep["on_ground"]:
                esemenyek.append({"tipus": "FELSZALLAS", "gep": uj_gep})
            elif not regi_gep["on_ground"] and uj_gep["on_ground"]:
                esemenyek.append({"tipus": "LESZALLAS",  "gep": uj_gep})

    # Eltűnt gépek
    for icao, regi_gep in regi.items():
        if icao not in uj and not regi_gep["on_ground"]:
            elapsed = time.time() - regi_gep.get("timestamp", 0)
            if elapsed > 120:
                esemenyek.append({"tipus": "LESZALLAS", "gep": regi_gep})

    return esemenyek


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

    ido      = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    emoji    = "🚁⬆️" if tipus == "FELSZALLAS" else "🚁⬇️"
    tipus_hu = "FELSZÁLLÁS" if tipus == "FELSZALLAS" else "LESZÁLLÁS"
    szin     = "#e74c3c" if tipus == "FELSZALLAS" else "#2980b9"

    lat_str = f"{lat:.6f}" if lat is not None else "ismeretlen"
    lon_str = f"{lon:.6f}" if lon is not None else "ismeretlen"
    alt_str = f"{alt_m} m ({round(alt_m * 3.28084)} ft)" if alt_m is not None else "ismeretlen"
    vel_str = f"{vel} km/h" if vel is not None else "ismeretlen"
    hdg_str = f"{round(hdg)}°" if hdg is not None else "ismeretlen"
    vr_str  = (f"+{vr}" if vr and vr > 0 else str(vr)) + " m/s" if vr is not None else "ismeretlen"

    # Követési linkek
    fr24_live     = f"https://www.flightradar24.com/{cs.strip()}"
    fr24_acdata   = f"https://www.flightradar24.com/data/aircraft/{reg.replace('-','').lower()}"
    adsbexch      = f"https://globe.adsbexchange.com/?icao={icao24}"
    flightaware   = f"https://www.flightaware.com/live/modes/{icao24.upper()}/ident/0/zoom/9"
    airnav        = f"https://www.airnavradar.com/data/aircraft/{icao24.upper()}"
    planespotters = f"https://www.planespotters.net/hex/{icao24.upper()}"
    opensky       = f"https://opensky-network.org/aircraft-profile?icao24={icao24}"
    adsbfi        = f"https://adsb.fi/#icao={icao24.upper()}"
    gmaps = f"https://www.google.com/maps?q={lat},{lon}&z=13" if lat and lon else None
    osm   = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=13/{lat}/{lon}" if lat and lon else None

    gmaps_link_html = f' &nbsp;<a href="{gmaps}" style="color:#4285f4;text-decoration:none;font-weight:bold">📍 Maps</a>' if gmaps else ''

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
  .badge .big {{ font-size:24px; font-weight:bold; color:#2c3e50; }}
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
  .btn {{ display:inline-block; padding:8px 14px; margin:4px;
          border-radius:6px; text-decoration:none; font-size:12px;
          font-weight:bold; color:#fff; }}
  .gmaps  {{ background:#4285f4; }} .osm    {{ background:#7cb342; }}
  .fr24   {{ background:#ff6600; }} .fr24ac {{ background:#cc4400; }}
  .adsbex {{ background:#1a1a2e; }} .fa     {{ background:#003087; }}
  .airnav {{ background:#0077cc; }} .ps     {{ background:#5b5ea6; }}
  .osky   {{ background:#2c7a4b; }} .adsbfi {{ background:#e67e22; }}
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
        <div class="lbl">Hívójel</div>
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

    <table>
      <tr><td>⏰ Időpont</td><td>{ido}</td></tr>
      <tr><td>🚁 Esemény</td>
          <td><strong style="color:{szin}">{tipus_hu}</strong></td></tr>
      <tr><td>🌍 Szélesség</td><td>{lat_str}{gmaps_link_html}</td></tr>
      <tr><td>🌍 Hosszúság</td><td>{lon_str}{gmaps_link_html}</td></tr>
      <tr><td>⬆️ Magasság</td><td>{alt_str}</td></tr>
      <tr><td>💨 Sebesség</td><td>{vel_str}</td></tr>
      <tr><td>🧭 Irányszög</td><td>{hdg_str}</td></tr>
      <tr><td>↕️ Függőleges sebesség</td><td>{vr_str}</td></tr>
      <tr><td>📻 Squawk</td><td>{squawk}</td></tr>
      <tr><td>✈️ Típus</td><td>{gep["tipus"] or "—"}</td></tr>
    </table>

    <div class="live-box">
      <h3>🔴 ÉLŐ KÖVETÉS</h3>
      <div class="note">Kattints a nyomon követéshez</div>
      <a href="{fr24_live}"    class="btn fr24"  >✈️ Flightradar24</a>
      <a href="{adsbexch}"    class="btn adsbex">📡 ADS-B Exchange</a>
      <a href="{adsbfi}"      class="btn adsbfi">🟠 adsb.fi</a>
      <a href="{flightaware}" class="btn fa"    >🔵 FlightAware</a>
      <a href="{airnav}"      class="btn airnav">🟦 AirNav RadarBox</a>
      <br style="margin:4px 0">
      <a href="{fr24_acdata}" class="btn fr24ac">📋 FR24 adatlap</a>
      <a href="{planespotters}"class="btn ps"   >📷 Planespotters</a>
      <a href="{opensky}"     class="btn osky"  >🌐 OpenSky</a>
    </div>

    {"" if not gmaps else f'''
    <div class="map-box">
      <h3>🗺️ Pozíció a térképen</h3>
      <div style="font-family:monospace;font-size:14px;font-weight:bold;
                  background:#ecf0f1;padding:7px 12px;border-radius:6px;
                  display:inline-block;margin:6px 0">
        {lat_str}° É, {lon_str}° K
      </div><br>
      <a href="{gmaps}" class="btn gmaps">📍 Google Maps</a>
      <a href="{osm}"   class="btn osm"  >🗺️ OpenStreetMap</a>
    </div>
    '''}

  </div>
  <div class="foot">
    Automatikus értesítés – GitHub Actions | adsb.fi adatai alapján
  </div>
</div></body></html>"""

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
        f"Flightradar24: {fr24_live}\n"
        f"ADS-B Exchange: {adsbexch}\n"
        f"adsb.fi: {adsbfi}\n"
        + (f"Google Maps: {gmaps}\n" if gmaps else "")
    )

    targy = f"{emoji} Mentőhelikopter {tipus_hu} – {cs} | {ido}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"🚁 Mentőhelikopter Monitor <{EMAIL_KULDO}>"
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
    print(f"\n{'='*50}")
    print(f"🚁 Mentőhelikopter Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*50}")

    gepek_raw = lekerdez()
    if gepek_raw is None:
        print("❌ API nem elérhető.")
        return

    # Szűrés – csak MEDIC callsign
    uj_allapot = {}
    for a in gepek_raw:
        if mento_e(a):
            gep = feldolgoz(a)
            uj_allapot[gep["icao24"]] = gep

    print(f"🚁 MEDIC hívójelű gépek: {len(uj_allapot)}")
    for g in uj_allapot.values():
        print(f"  → {g['callsign']} | {g['icao24'].upper()} | {g['reg']} | {'FÖLDÖN' if g['on_ground'] else 'LEVEGŐBEN'}")

    regi_allapot = betolt_allapot()
    esemenyek    = osszehasonlit(regi_allapot, uj_allapot)

    print(f"⚡ Változások: {len(esemenyek)}")
    for e in esemenyek:
        print(f"  → {e['tipus']}: {e['gep']['callsign'] or e['gep']['icao24']}")
        email_kuldes(e)

    ment_allapot(uj_allapot)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
