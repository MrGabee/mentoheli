"""
⚡ ELMŰ Áramszünet Monitor – Csepel (XXI. kerület)
Figyeli:
  1. Tervezett áramszünetek (elmuhalozat.hu táblázat)
  2. Élő üzemzavarok (elmuhalozat.hu térkép API)
Futtatás: GitHub Actions (percenként)
"""

import os
import json
import hashlib
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
#  ⚙️  KONFIGURÁCIÓ (GitHub Secrets-ből jön)
# ─────────────────────────────────────────────
EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT"]

# Csepelre vonatkozó keresőszavak (kis-nagybetű érzéketlen)
CSEPEL_KULCSSZAVAK = [
    "csepel", "xxi", "XXI", "21. ker", "csepeli",
    "Csepel", "Budapest XXI", "Bp. XXI",
]

ALLAPOT_FAJL = "aramszunet_allapot.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
    "Referer": "https://elmuhalozat.hu/",
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

def hash_rekord(szoveg):
    """Egyedi azonosító egy rekordhoz."""
    return hashlib.md5(szoveg.encode("utf-8")).hexdigest()[:12]


# ════════════════════════════════════════════
#  🔍  CSEPEL SZŰRŐ
# ════════════════════════════════════════════
def csepel_e(szoveg):
    szoveg_lower = szoveg.lower()
    return any(k.lower() in szoveg_lower for k in CSEPEL_KULCSSZAVAK)


# ════════════════════════════════════════════
#  📋  1. TERVEZETT ÁRAMSZÜNETEK SCRAPING
# ════════════════════════════════════════════
TERVEZETT_URLAK = [
    "https://elmuhalozat.hu/tudnivalok/energiakozeli-informaciok/tervezett-karbantartasok",
    "https://www.eon.hu/pestmegyeihalozat/tudnivalok/energiakozeli-informaciok/tervezett-aramszunetek-pest-megye-es-budapest-kornyeken.html",
]

def lekerdez_tervezett():
    """Scraping: tervezett áramszünetek táblázata."""
    eredmenyek = []

    for url in TERVEZETT_URLAK:
        try:
            print(f"📋 Tervezett lekérdezés: {url}")
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                print(f"  ⚠️ HTTP {r.status_code}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            # Táblázatsorok keresése
            sorok = soup.find_all("tr")
            for sor in sorok:
                cellak = sor.find_all(["td", "th"])
                if not cellak:
                    continue
                sor_szoveg = " | ".join(c.get_text(strip=True) for c in cellak)
                if csepel_e(sor_szoveg):
                    eredmenyek.append({
                        "tipus": "TERVEZETT",
                        "szoveg": sor_szoveg,
                        "url": url,
                        "cellak": [c.get_text(strip=True) for c in cellak],
                    })

            # Ha nincs táblázat, szöveges kereséssel próbálkozunk
            if not sorok:
                szoveg_blokkok = soup.find_all(
                    ["p", "div", "li", "span"],
                    string=lambda t: t and csepel_e(t)
                )
                for blokk in szoveg_blokkok:
                    eredmenyek.append({
                        "tipus": "TERVEZETT",
                        "szoveg": blokk.get_text(strip=True),
                        "url": url,
                        "cellak": [],
                    })

            print(f"  ✅ Csepeles találat: {len(eredmenyek)}")

        except Exception as e:
            print(f"  ❌ Hiba: {e}")

    return eredmenyek


# ════════════════════════════════════════════
#  ⚡  2. ÉLŐ ÜZEMZAVAROK – TÉRKÉP API
# ════════════════════════════════════════════
# Az ELMŰ térkép mögötti API endpoint-ok
# (Csepel koordinátái körüli terület)
UZEMZAVAR_URLAK = [
    # ELMŰ hálózat GeoJSON/API végpont (Csepel bbox)
    "https://elmuhalozat.hu/api/outages/current",
    "https://elmuhalozat.hu/api/v1/outages",
    # Backup: az E.ON pestmegyei hálózat API
    "https://www.eon.hu/pestmegyeihalozat/api/outages",
]

# Csepel koordinátái (bounding box)
CSEPEL_LAT_MIN = 47.38
CSEPEL_LAT_MAX = 47.47
CSEPEL_LON_MIN = 19.00
CSEPEL_LON_MAX = 19.12

def koordinata_csepel_e(lat, lon):
    """Koordináta Csepel területén belül van-e?"""
    try:
        return (CSEPEL_LAT_MIN <= float(lat) <= CSEPEL_LAT_MAX and
                CSEPEL_LON_MIN <= float(lon) <= CSEPEL_LON_MAX)
    except Exception:
        return False

def lekerdez_uzemzavar_api():
    """Közvetlen API hívás az élő üzemzavarokhoz."""
    eredmenyek = []

    for url in UZEMZAVAR_URLAK:
        try:
            print(f"⚡ Üzemzavar API: {url}")
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue

            data = r.json()
            esetek = data if isinstance(data, list) else data.get("outages", data.get("data", []))

            for eset in esetek:
                # Szöveges szűrés
                eset_str = json.dumps(eset, ensure_ascii=False)
                lat = eset.get("lat") or eset.get("latitude") or eset.get("y")
                lon = eset.get("lon") or eset.get("longitude") or eset.get("x")

                if csepel_e(eset_str) or (lat and lon and koordinata_csepel_e(lat, lon)):
                    eredmenyek.append({
                        "tipus": "UZEMZAVAR",
                        "szoveg": eset_str[:500],
                        "url": url,
                        "adat": eset,
                    })

        except Exception as e:
            print(f"  ⚠️ API nem elérhető ({url}): {e}")

    return eredmenyek

def lekerdez_uzemzavar_scraping():
    """Ha az API nem megy, az üzemzavar oldalt scrapeljük."""
    eredmenyek = []
    urlak = [
        "https://elmuhalozat.hu/tudnivalok/energiakozeli-informaciok/uzemzavarok",
        "https://elmuhalozat.hu/hibabejelentes",
    ]

    for url in urlak:
        try:
            print(f"⚡ Üzemzavar scraping: {url}")
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            szoveg_blokkok = soup.find_all(["tr", "div", "li", "p"])

            for blokk in szoveg_blokkok:
                szoveg = blokk.get_text(separator=" ", strip=True)
                if csepel_e(szoveg) and len(szoveg) > 10:
                    eredmenyek.append({
                        "tipus": "UZEMZAVAR",
                        "szoveg": szoveg[:500],
                        "url": url,
                        "adat": {},
                    })

        except Exception as e:
            print(f"  ⚠️ Scraping hiba ({url}): {e}")

    return eredmenyek


# ════════════════════════════════════════════
#  📧  E-MAIL KÜLDÉS
# ════════════════════════════════════════════
def email_kuldes(uj_esetek):
    if not uj_esetek:
        return

    ido = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    db = len(uj_esetek)

    targy = f"⚡ Csepel áramszünet értesítő – {db} új esemény | {ido}"

    # HTML táblázat az esetekhez
    sorok_html = ""
    sorok_txt  = ""
    for i, e in enumerate(uj_esetek, 1):
        tipus = e["tipus"]
        szin  = "#e74c3c" if tipus == "UZEMZAVAR" else "#e67e22"
        badge = "🔴 ÉLŐ ÜZEMZAVAR" if tipus == "UZEMZAVAR" else "📋 TERVEZETT"

        sorok_html += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #eee;width:30px">{i}.</td>
          <td style="padding:10px;border-bottom:1px solid #eee;">
            <span style="background:{szin};color:#fff;padding:3px 8px;
                         border-radius:4px;font-size:12px;font-weight:bold">
              {badge}
            </span><br><br>
            <span style="font-family:monospace;font-size:13px">{e['szoveg'][:400]}</span><br>
            <small style="color:#999">Forrás: <a href="{e['url']}">{e['url']}</a></small>
          </td>
        </tr>"""

        sorok_txt += f"\n{'─'*50}\n{i}. {badge}\n{e['szoveg'][:400]}\nForrás: {e['url']}\n"

    html = f"""<!DOCTYPE html>
<html lang="hu">
<head><meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; background:#f4f4f4; margin:0; padding:0; }}
  .wrap {{ max-width:650px; margin:20px auto; background:#fff;
           border-radius:10px; overflow:hidden;
           box-shadow:0 4px 12px rgba(0,0,0,.15); }}
  .hdr  {{ background:#c0392b; color:#fff; padding:22px 28px; }}
  .hdr h1 {{ margin:0; font-size:20px; }}
  .hdr small {{ opacity:.85; font-size:13px; }}
  .body {{ padding:22px 28px; }}
  table {{ width:100%; border-collapse:collapse; }}
  .foot {{ background:#ecf0f1; padding:12px 28px; font-size:11px;
           color:#95a5a6; text-align:center; }}
  .btn  {{ display:inline-block; padding:10px 20px; margin:8px 4px;
           border-radius:6px; text-decoration:none;
           font-weight:bold; color:#fff; font-size:13px; }}
</style>
</head>
<body><div class="wrap">
  <div class="hdr">
    <h1>⚡ Csepel – Áramszünet értesítő</h1>
    <small>{ido} | {db} új esemény</small>
  </div>
  <div class="body">
    <p style="color:#7f8c8d;font-size:13px">
      Az alábbi áramszünet-események kerültek rögzítésre Csepelen (XXI. kerület):
    </p>
    <table>{sorok_html}</table>
    <div style="text-align:center;margin-top:20px">
      <a href="https://elmuhalozat.hu/tudnivalok/energiakozeli-informaciok/tervezett-karbantartasok"
         class="btn" style="background:#e67e22">📋 Tervezett munkák</a>
      <a href="https://elmuhalozat.hu/tudnivalok/energiakozeli-informaciok/uzemzavarok"
         class="btn" style="background:#c0392b">⚡ Élő üzemzavarok</a>
      <a href="https://elmuhalozat.hu"
         class="btn" style="background:#2980b9">🌐 ELMŰ oldal</a>
    </div>
  </div>
  <div class="foot">
    Automatikus értesítő – GitHub Actions | ELMŰ Hálózati Kft. adatai alapján
  </div>
</div></body></html>"""

    szoveges = (
        f"⚡ Csepel Áramszünet Értesítő\n"
        f"Időpont: {ido}\n"
        f"Új események: {db}\n"
        f"{sorok_txt}\n"
        f"Tervezett munkák: https://elmuhalozat.hu/tudnivalok/energiakozeli-informaciok/tervezett-karbantartasok\n"
        f"Élő üzemzavarok: https://elmuhalozat.hu/tudnivalok/energiakozeli-informaciok/uzemzavarok\n"
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
    except Exception as e:
        print(f"❌ E-mail hiba: {e}")
        raise


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"⚡ Csepel Áramszünet Monitor – {datetime.now().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    # Előző állapot betöltése
    regi_allapot = betolt_allapot()

    uj_esetek = []

    # ── 1. Tervezett áramszünetek ──────────────────────────
    tervezett = lekerdez_tervezett()
    print(f"📋 Tervezett találatok (Csepel): {len(tervezett)}")
    for e in tervezett:
        rid = hash_rekord(e["szoveg"])
        if rid not in regi_allapot.get("tervezett", {}):
            uj_esetek.append(e)
            regi_allapot.setdefault("tervezett", {})[rid] = {
                "szoveg": e["szoveg"][:100],
                "talalt": datetime.now().isoformat()
            }

    # ── 2. Élő üzemzavarok ────────────────────────────────
    uzemzavar = lekerdez_uzemzavar_api()
    if not uzemzavar:
        uzemzavar = lekerdez_uzemzavar_scraping()
    print(f"⚡ Üzemzavar találatok (Csepel): {len(uzemzavar)}")
    for e in uzemzavar:
        rid = hash_rekord(e["szoveg"])
        if rid not in regi_allapot.get("uzemzavar", {}):
            uj_esetek.append(e)
            regi_allapot.setdefault("uzemzavar", {})[rid] = {
                "szoveg": e["szoveg"][:100],
                "talalt": datetime.now().isoformat()
            }

    print(f"⚡ Új (még nem értesített) események: {len(uj_esetek)}")

    # E-mail küldés ha van új esemény
    if uj_esetek:
        email_kuldes(uj_esetek)
    else:
        print("✅ Nincs új Csepelt érintő áramszünet.")

    # Állapot mentése
    ment_allapot(regi_allapot)
    print("💾 Állapot elmentve.")
    print("✅ Kész.\n")


if __name__ == "__main__":
    main()
