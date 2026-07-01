"""
🚁 Magyar Mentőhelikopter Monitor
Adatforrás: adsb.fi (ingyenes, kulcs nélkül)
Szűrés: MEDIC callsign (kizárólag magyar mentőhelikopterek)
Futtatás: GitHub Actions (percenként, self-loop)
DIAGNOSZTIKAI VERZIÓ – részletes hibakiírással ha 0 gépet találunk
"""

import os
import json
import time
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

MAGYAR_TZ = timezone(timedelta(hours=2))

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT"]

MENTO_ICAO_MAP = {
    "47129c": "HA-HBG",
    "47129d": "HA-HBH",
    "4712a0": "HA-HBK",
    "4712a1": "HA-HBL",
    "4712a2": "HA-HBM",
    "4712a3": "HA-HBN",
    "4712a4": "HA-HBO",
}

API_URLAK_ICAO = [
    "https://api.airplanes.live/v2/icao/{icao}",
    "https://opendata.adsb.fi/api/v2/icao/{icao}",
    "https://api.adsb.one/v2/icao/{icao}",
    "https://api.adsb.lol/v2/icao/{icao}",
]

OPENSKY_URL = "https://opensky-network.org/api/states/all?icao24={icao}"

API_URLAK = [
    "https://opendata.adsb.fi/api/v2/country/HU",
    "https://api.adsb.one/v2/country/HU",
    "https://api.airplanes.live/v2/country/HU",
    "https://api.adsb.lol/v2/country/HU",
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
    "https://api.airplanes.live/v2/reg/HA-HBG",
    "https://api.airplanes.live/v2/reg/HA-HBH",
    "https://api.airplanes.live/v2/reg/HA-HBK",
    "https://api.airplanes.live/v2/reg/HA-HBL",
    "https://api.airplanes.live/v2/reg/HA-HBM",
    "https://api.airplanes.live/v2/reg/HA-HBN",
    "https://api.airplanes.live/v2/reg/HA-HBO",
]

ALLAPOT_FAJL  = "allapot.json"
FOLD_KUSZOB_M = 50

HEADERS = {
    "User-Agent": "MentoHelikopterMonitor/2.0 (github-actions)"
}


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


def mento_e(a):
    callsign = (a.get("flight") or "").strip().upper()
    reg      = (a.get("r") or "").strip().upper()

    MENTO_CALLSIGN = {
        "MEDIC1", "MEDIC2", "MEDIC3", "MEDIC4",
        "MEDIC5", "MEDIC6", "MEDIC7",
        "MEDIKOPTER5",
    }
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


def lekerdez():
    gepek = {}
    diag_sorok = []

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
                        print(f"OK ICAO {icao} ({reg}): megtalalva")
                        break
                else:
                    diag_sorok.append(f"  ICAO {url} -> HTTP {r.status_code} | body: {r.text[:150]!r}")
            except Exception as e:
                diag_sorok.append(f"  ICAO {url} -> KIVETEL: {type(e).__name__}: {e}")

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
                    print(f"OK Orszag lista: {len(ac_lista)} gep")
                elif "callsign" in url and ac_lista:
                    cs = url.split("callsign/")[-1]
                    print(f"OK Callsign {cs}: megtalalva")
            else:
                diag_sorok.append(f"  {url} -> HTTP {r.status_code} | body: {r.text[:150]!r}")
        except Exception as e:
            diag_sorok.append(f"  {url} -> KIVETEL: {type(e).__name__}: {e}")

    for icao, reg in MENTO_ICAO_MAP.items():
        if icao in gepek:
            continue
        try:
            url = OPENSKY_URL.format(icao=icao)
            r = requests.get(url, timeout=10, headers=HEADERS)
            if r.status_code == 200:
                data = r.json()
                states = data.get("states") or []
                for s in states:
                    if not s or len(s) < 9:
                        continue
                    lat_val = s[6]
                    lon_val = s[5]
                    if lat_val is None or lon_val is None:
                        continue
                    g = {
                        "hex":        (s[0] or "").lower(),
                        "flight":     (s[1] or "").strip(),
                        "r":          reg,
                        "lat":        lat_val,
                        "lon":        lon_val,
                        "alt_baro":   int(s[7] / 0.3048) if s[7] else "ground",
                        "on_ground":  s[8],
                        "gs":         int(s[9] * 1.944) if s[9] else 0,
                        "track":      s[10],
                    }
                    key = g["hex"]
                    if key and key not in gepek:
                        gepek[key] = g
                        print(f"OK OpenSky {icao} ({reg}): megtalalva")
            else:
                diag_sorok.append(f"  OpenSky {icao} -> HTTP {r.status_code} | body: {r.text[:150]!r}")
        except Exception as e:
            diag_sorok.append(f"  OpenSky {icao} -> KIVETEL: {type(e).__name__}: {e}")

    eredmeny = list(gepek.values())
    print(f"Osszesitett egyedi gepek: {len(eredmeny)}")

    if len(eredmeny) == 0:
        print(f"\nDIAGNOSZTIKA - {len(diag_sorok)} forras valaszolt hibasan/uresen:")
        for sor in diag_sorok[:15]:
            print(sor)
        if len(diag_sorok) > 15:
            print(f"  ... es meg {len(diag_sorok) - 15} tovabbi hasonlo hiba.")

    return eredmeny if eredmeny else None


def feldolgoz(a):
    icao24   = (a.get("hex", "") or "").lower().strip()
    callsign = (a.get("flight", "") or "").strip()
    reg      = (a.get("r", "") or ISMERT_LAJSTROM.get(icao24, "")).strip()
    tipus    = (a.get("t", "") or "").strip()
    lat      = a.get("lat")
    lon      = a.get("lon")

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

ISMERT_LAJSTROM = {
    "47129c": "HA-HBG",
    "47129d": "HA-HBH",
    "4712a0": "HA-HBK",
    "4712a1": "HA-HBL",
    "4712a2": "HA-HBM",
    "4712a3": "HA-HBN",
    "4712a4": "HA-HBO",
}


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

    for icao, regi_gep in regi.items():
        if icao not in uj and not regi_gep["on_ground"]:
            elapsed = time.time() - regi_gep.get("timestamp", 0)
            if elapsed > 120:
                esemenyek.append({"tipus": "LESZALLAS", "gep": regi_gep})

    return esemenyek


def email_kuldes(esemeny):
    tipus   = esemeny["tipus"]
    gep     = esemeny["gep"]
    icao24  = gep["icao24"]
    cs      = gep["callsign"] or gep["reg"] or icao24.upper()
    reg     = gep["reg"] or ""
    lat     = gep["lat"]
    lon     = gep["lon"]
    alt_m   = gep["geo_alt_m"] or gep["baro_alt_m"]
    vel     = gep["velocity_kmh"]

    ido      = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    emoji    = "🚁⬆️" if tipus == "FELSZALLAS" else "🚁⬇️"
    tipus_hu = "FELSZÁLLÁS" if tipus == "FELSZALLAS" else "LESZÁLLÁS"
    szin     = "#c0392b" if tipus == "FELSZALLAS" else "#2980b9"

    # Weboldal URL paraméterekkel
    import urllib.parse
    params = {
        "tipus": tipus,
        "cs":    cs,
        "reg":   reg,
        "icao":  icao24.upper(),
        "ido":   ido,
    }
    if lat is not None: params["lat"] = f"{lat:.6f}"
    if lon is not None: params["lon"] = f"{lon:.6f}"
    if alt_m is not None: params["alt"] = str(alt_m)
    if vel is not None: params["vel"] = str(vel)

    weboldal_url = f"https://mrgabee.github.io/mentoheli/?{urllib.parse.urlencode(params)}"

    targy = f"{emoji} Mentőhelikopter {tipus_hu} – {cs} | {ido}"

    html = f"""<!DOCTYPE html>
<html lang="hu"><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px">
  <div style="max-width:500px;margin:0 auto;background:#fff;border-radius:12px;
              overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.15)">

    <div style="background:{szin};color:#fff;padding:24px;text-align:center">
      <div style="font-size:48px;margin-bottom:8px">{emoji}</div>
      <div style="font-size:24px;font-weight:bold">Mentőhelikopter {tipus_hu}</div>
      <div style="font-size:14px;opacity:.85;margin-top:6px">{ido}</div>
    </div>

    <div style="padding:24px;text-align:center">
      <div style="font-size:32px;font-weight:bold;color:#2c3e50;margin-bottom:4px">{cs}</div>
      <div style="font-size:16px;color:#888;margin-bottom:24px">{reg} &nbsp;|&nbsp; {icao24.upper()}</div>

      <a href="{weboldal_url}"
         style="display:block;background:{szin};color:#fff;padding:16px;
                border-radius:10px;text-decoration:none;font-size:18px;
                font-weight:bold;margin-bottom:12px">
        🚁 Megnyitás – térkép &amp; követés
      </a>

      <a href="https://www.flightradar24.com/{cs}"
         style="display:block;background:#ff6600;color:#fff;padding:14px;
                border-radius:10px;text-decoration:none;font-size:15px;
                font-weight:bold">
        ✈️ Flightradar24 – élő követés
      </a>
    </div>

    <div style="background:#ecf0f1;padding:12px;text-align:center;
                font-size:11px;color:#95a5a6">
      Automatikus értesítő – Baleset-info.hu
    </div>
  </div>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"🚁 Mentőhelikopter Monitor <{EMAIL_KULDO}>"
    msg["To"]      = EMAIL_CIMZETT
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
        smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
    print(f"📧 E-mail elküldve: {targy}")


def main():
    print(f"\n{'='*50}")
    print(f"🚁 Mentőhelikopter Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*50}")

    gepek_raw = lekerdez()
    if gepek_raw is None:
        print("❌ API nem elérhető.")
        return

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
