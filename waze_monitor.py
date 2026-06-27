"""
🚨 Waze Baleset Monitor – Budapest
Adatforrás: Waze Live Map API (georss)
Szűrés: ACCIDENT típusú bejelentések, Budapest bounding box
TESZT MÓD: minden alert típus jön
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

EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT"]
WAZE_COOKIE   = os.environ["WAZE_COOKIE"]

# Budapest bounding box
WAZE_URL = (
    "https://www.waze.com/live-map/api/georss"
    "?top=47.614&bottom=47.349&left=18.897&right=19.269"
    "&env=row&types=alerts,traffic"
)

ALLAPOT_FAJL = "waze_allapot.json"

# ─────────────────────────────────────────────
#  🔧  TESZT MÓD
#  True  = minden alert típus jön (teszteléshez)
#  False = csak ACCIDENT típus jön (éles mód)
# ─────────────────────────────────────────────
TESZT_MOD = True

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "hu-HU,hu;q=0.9,en;q=0.7",
    "Referer": "https://www.waze.com/hu/live-map/",
    "Cookie": WAZE_COOKIE,
}

# Alert típusok
TIPUS_MAP = {
    "ACCIDENT":   "🚨 Baleset",
    "JAM":        "🚗 Dugó",
    "ROAD_CLOSED": "🚧 Lezárás",
    "HAZARD":     "⚠️ Veszély",
    "POLICE":     "👮 Rendőr",
    "CONSTRUCTION": "🏗️ Építkezés",
}

# Baleset altípusok
BALESET_ALTIPUS = {
    0:  "🚨 Baleset",
    1:  "🚨 Kisebb baleset",
    2:  "🚨 Nagyobb baleset",
    3:  "🚗 Gépkocsi baleset",
    4:  "🚛 Teherautó baleset",
    5:  "🏍️ Motor baleset",
    6:  "🚲 Kerékpár baleset",
    7:  "🚶 Gyalogos baleset",
    8:  "🐕 Állat az úton",
    9:  "⚠️ Egyéb baleset",
    14: "🚨 Baleset – forgalom lassul",
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
    return {}

def ment_allapot(allapot):
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=2)

def hash_id(szoveg):
    return hashlib.md5(szoveg.encode("utf-8")).hexdigest()[:12]


# ════════════════════════════════════════════
#  📡  LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez():
    try:
        print(f"🌐 Waze lekérdezés... {'[TESZT MÓD]' if TESZT_MOD else '[ÉLES MÓD]'}")
        r = requests.get(WAZE_URL, headers=HEADERS, timeout=20)
        print(f"  HTTP: {r.status_code}")

        if r.status_code != 200:
            print(f"  ⚠️ Hiba: {r.text[:200]}")
            return []

        data = r.json()
        alerts = data.get("alerts", [])
        print(f"  📊 Összes alert: {len(alerts)}")

        eredmeny = []
        for a in alerts:
            tipus = a.get("type", "")

            # Teszt módban minden jön, éles módban csak baleset
            if not TESZT_MOD and tipus != "ACCIDENT":
                continue

            uuid       = a.get("uuid", "")
            altipus    = a.get("subtype", 0)
            lat        = a.get("location", {}).get("y")
            lon        = a.get("location", {}).get("x")
            utca       = a.get("street", "") or a.get("city", "") or "ismeretlen helyszín"
            varos      = a.get("city", "")
            magabizt   = a.get("reliability", 0)
            thumb_up   = a.get("nThumbsUp", 0)
            megjegyzes = a.get("reportDescription", "") or ""

            if lat and lon:
                gmaps     = f"https://www.google.com/maps?q={lat},{lon}&z=15"
                waze_link = f"https://www.waze.com/ul?ll={lat}%2C{lon}&navigate=yes&zoom=17"
            else:
                gmaps = waze_link = None

            # Típus meghatározása
            if tipus == "ACCIDENT":
                tipus_nev = BALESET_ALTIPUS.get(altipus, "🚨 Baleset")
            else:
                tipus_nev = TIPUS_MAP.get(tipus, f"📍 {tipus}")

            eredmeny.append({
                "uuid":       uuid,
                "tipus":      tipus,
                "tipus_nev":  tipus_nev,
                "altipus":    altipus,
                "lat":        lat,
                "lon":        lon,
                "utca":       utca,
                "varos":      varos,
                "magabizt":   magabizt,
                "thumb_up":   thumb_up,
                "megjegyzes": megjegyzes,
                "gmaps":      gmaps,
                "waze_link":  waze_link,
            })

        print(f"  🎯 Szűrt találat: {len(eredmeny)}")
        return eredmeny

    except Exception as ex:
        print(f"  ❌ {ex}")
        import traceback
        traceback.print_exc()
        return []


# ════════════════════════════════════════════
#  📧  E-MAIL
# ════════════════════════════════════════════
def email_kuldes(uj_esetek):
    ido   = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)
    mod   = " [TESZT]" if TESZT_MOD else ""
    targy = f"🚨 Waze{mod} – {db} új esemény | {ido}"

    sorok_html = ""
    sorok_txt  = ""

    for i, e in enumerate(uj_esetek, 1):
        szin = "#c0392b" if e["tipus"] == "ACCIDENT" else "#e67e22"

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:{szin};color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">
              {e['tipus_nev']}
            </span>
            <div style="font-size:15px;font-weight:bold;margin:10px 0;color:#2c3e50">
              📍 {e['utca']}{(' – ' + e['varos']) if e['varos'] and e['varos'] != e['utca'] else ''}
            </div>
            <table style="font-size:13px;width:100%;margin-top:6px">
              <tr><td style="color:#888;width:160px">⭐ Megbízhatóság:</td>
                  <td>{e['magabizt']}/10</td></tr>
              <tr><td style="color:#888">👍 Megerősítések:</td>
                  <td>{e['thumb_up']}</td></tr>
              {'<tr><td style="color:#888">💬 Megjegyzés:</td><td>' + e["megjegyzes"] + '</td></tr>' if e["megjegyzes"] else ''}
            </table>
            <div style="margin-top:10px">
              {'<a href="' + e["gmaps"] + '" style="background:#4285f4;color:#fff;padding:7px 14px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:bold;margin-right:8px">📍 Google Maps</a>' if e["gmaps"] else ''}
              {'<a href="' + e["waze_link"] + '" style="background:#00d4e0;color:#fff;padding:7px 14px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:bold">🚗 Waze</a>' if e["waze_link"] else ''}
            </div>
          </td>
        </tr>"""

        sorok_txt += (
            f"\n{'─'*45}\n"
            f"{i}. {e['tipus_nev']}\n"
            f"Helyszín: {e['utca']}\n"
            f"Megbízhatóság: {e['magabizt']}/10\n"
            + (f"Megjegyzés: {e['megjegyzes']}\n" if e["megjegyzes"] else "")
            + (f"Maps: {e['gmaps']}\n" if e["gmaps"] else "")
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
  .foot{{background:#ecf0f1;padding:12px 28px;font-size:11px;
         color:#95a5a6;text-align:center}}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>🚨 Waze – {'Teszt értesítő' if TESZT_MOD else 'Baleseti értesítő'}</h1>
    <small>{ido} | {db} esemény | Budapest</small>
  </div>
  <div class="body">
    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>
    <div style="text-align:center;margin-top:16px">
      <a href="https://www.waze.com/hu/live-map/"
         style="background:#00d4e0;color:#fff;padding:9px 16px;border-radius:6px;
                text-decoration:none;font-weight:bold;font-size:12px">
        🗺️ Waze Live Map
      </a>
    </div>
  </div>
  <div class="foot">Automatikus értesítő – GitHub Actions | Waze adatai alapján</div>
</div></body></html>"""

    szoveges = f"🚨 Waze Monitor\nIdőpont: {ido}\n{sorok_txt}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"🚨 Waze Monitor <{EMAIL_KULDO}>"
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
    print(f"🚨 Waze Monitor – {datetime.now().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    uj   = []

    esemenyek = lekerdez()

    for e in esemenyek:
        rid = hash_id(e["uuid"]) if e["uuid"] else hash_id(f"{e['lat']}{e['lon']}{e['tipus']}")

        if TESZT_MOD:
            # Teszt módban minden esemény jön
            uj.append(e)
        else:
            # Éles módban csak az újak
            if rid not in regi:
                uj.append(e)

        regi[rid] = {
            "utca":   e["utca"][:100],
            "talalt": datetime.now().isoformat()
        }

    print(f"\n🚨 Küldendő esemény: {len(uj)}")
    if uj:
        email_kuldes(uj)
    else:
        print("✅ Nincs esemény.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
