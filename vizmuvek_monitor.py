"""
💧 Fővárosi Vízművek Monitor – Csepel (XXI. kerület)
Adatforrás: vizmuvek.hu/hu/kezdolap/informaciok/munkaterkep-hol-dolgozunk
Szűrés: Csepel polygon (ray casting)
Típusok: Vízhiány, Várható vízhiány, Forgalomkorlátozás
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
from bs4 import BeautifulSoup

EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT_ARAM"]

VIZMUVEK_URL = "https://www.vizmuvek.hu/hu/kezdolap/informaciok/munkaterkep-hol-dolgozunk"
ALLAPOT_FAJL = "vizmuvek_allapot.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

# ─────────────────────────────────────────────
#  📍  CSEPEL SZŰRŐ – XXI. kerület prefix
# ─────────────────────────────────────────────

TIPUS_MAP = {
    "geo_0": ("🔴", "VÍZHIÁNY",              "#c0392b"),
    "geo_1": ("🟠", "VÁRHATÓ VÍZHIÁNY",      "#e67e22"),
    "geo_2": ("🔵", "FORGALOMKORLÁTOZÁS",    "#2980b9"),
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


def csepel_e(cim):
    """Csepeli-e a cím? – XXI. kerület prefix alapján."""
    return cim.strip().startswith("XXI.")


# ════════════════════════════════════════════
#  📡  LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez():
    try:
        print(f"🌐 Lekérdezés: {VIZMUVEK_URL}")
        r = requests.get(VIZMUVEK_URL, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ HTTP {r.status_code}")
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        esemenyek = []

        # Összes geo div feldolgozása
        geo_divek = soup.find_all("div", class_=lambda c: c and "geo" in c.split())
        print(f"  📊 Összes geo elem: {len(geo_divek)}")

        for div in geo_divek:
            classes = div.get("class", [])
            # Típus meghatározása (geo_0, geo_1, geo_2)
            tipus = None
            for c in classes:
                if c in TIPUS_MAP:
                    tipus = c
                    break
            if not tipus:
                continue

            title = div.get("title", "")
            if not title:
                continue

            # Koordináták kinyerése
            lat_abbr = div.find("abbr", class_="latitude")
            lon_abbr = div.find("abbr", class_="longitude")
            if not lat_abbr or not lon_abbr:
                continue

            try:
                lat = float(lat_abbr.get("title", "0"))
                lon = float(lon_abbr.get("title", "0"))
            except (ValueError, TypeError):
                continue

            # Csepel szűrés – XXI. kerület prefix
            if not csepel_e(cim):
                continue

            # Adatok kinyerése a title-ből
            cim = ""
            munka = ""
            kezdes = ""
            veg = ""

            for sor in title.split("\n"):
                sor = sor.strip()
                if sor.startswith("Postacím:"):
                    cim = sor.replace("Postacím:", "").strip()
                elif sor.startswith("A munka megnevezése:"):
                    munka = sor.replace("A munka megnevezése:", "").strip()
                elif sor.startswith("Munka tervezett kezdete:"):
                    kezdes = sor.replace("Munka tervezett kezdete:", "").strip()
                elif sor.startswith("Munka tervezett vége:"):
                    veg = sor.replace("Munka tervezett vége:", "").strip()

            if not cim:
                continue

            gmaps = f"https://www.google.com/maps?q={lat},{lon}&z=15"

            esemenyek.append({
                "tipus":  tipus,
                "cim":    cim,
                "munka":  munka,
                "kezdes": kezdes,
                "veg":    veg,
                "lat":    lat,
                "lon":    lon,
                "gmaps":  gmaps,
            })
            print(f"  🎯 Csepel: [{tipus}] {cim}")

        print(f"  📊 Csepeli találat összesen: {len(esemenyek)}")
        return esemenyek

    except Exception as ex:
        print(f"  ❌ Hiba: {ex}")
        import traceback
        traceback.print_exc()
        return []


# ════════════════════════════════════════════
#  📧  E-MAIL
# ════════════════════════════════════════════
def email_kuldes(uj_esetek):
    ido   = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)
    targy = f"💧 Vízművek Csepel – {db} új esemény | {ido}"

    sorok_html = ""
    sorok_txt  = ""

    for i, e in enumerate(uj_esetek, 1):
        emoji, label, szin = TIPUS_MAP.get(e["tipus"], ("💧", e["tipus"], "#2980b9"))

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:{szin};color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">
              {emoji} {label}
            </span>
            <div style="font-size:15px;font-weight:bold;margin:10px 0;color:#2c3e50">
              {e['cim']}
            </div>
            <table style="font-size:13px;width:100%;margin-top:6px">
              <tr><td style="color:#888;width:160px">🔧 Munka típusa:</td>
                  <td>{e['munka'] or '—'}</td></tr>
              <tr><td style="color:#888">⏰ Kezdés:</td>
                  <td><strong>{e['kezdes'] or '—'}</strong></td></tr>
              <tr><td style="color:#888">⏰ Vége:</td>
                  <td><strong>{e['veg'] or '—'}</strong></td></tr>
            </table>
            <div style="margin-top:10px">
              <a href="{e['gmaps']}" style="background:#4285f4;color:#fff;padding:7px 14px;
                                            border-radius:4px;text-decoration:none;
                                            font-size:12px;font-weight:bold">
                📍 Google Maps
              </a>
            </div>
          </td>
        </tr>"""

        sorok_txt += (
            f"\n{'─'*45}\n"
            f"{i}. {emoji} {label}\n"
            f"Cím:    {e['cim']}\n"
            f"Munka:  {e['munka']}\n"
            f"Kezdés: {e['kezdes']}\n"
            f"Vége:   {e['veg']}\n"
            f"Maps:   {e['gmaps']}\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="hu"><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}}
  .wrap{{max-width:650px;margin:20px auto;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.15)}}
  .hdr{{background:#2980b9;color:#fff;padding:22px 28px}}
  .hdr h1{{margin:0;font-size:20px}}
  .hdr small{{opacity:.85;font-size:13px}}
  .body{{padding:20px 28px}}
  .foot{{background:#ecf0f1;padding:12px 28px;font-size:11px;
         color:#95a5a6;text-align:center}}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>💧 Fővárosi Vízművek – Csepeli értesítő</h1>
    <small>{ido} | {db} új esemény (XXI. kerület)</small>
  </div>
  <div class="body">
    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>
    <div style="text-align:center;margin-top:16px">
      <a href="https://www.vizmuvek.hu/hu/kezdolap/informaciok/munkaterkep-hol-dolgozunk"
         style="background:#2980b9;color:#fff;padding:9px 16px;border-radius:6px;
                text-decoration:none;font-weight:bold;font-size:12px">
        💧 Vízművek munkatérkép
      </a>
    </div>
  </div>
  <div class="foot">Automatikus értesítő – GitHub Actions | Fővárosi Vízművek adatai alapján</div>
</div></body></html>"""

    szoveges = f"💧 Fővárosi Vízművek Csepel\nIdőpont: {ido}\n{sorok_txt}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"💧 Vízművek Monitor <{EMAIL_KULDO}>"
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
    print(f"💧 Vízművek Monitor – {datetime.now().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    uj   = []

    esemenyek = lekerdez()

    for e in esemenyek:
        rid = hash_id(e["tipus"] + e["cim"] + e["kezdes"])
        if rid not in regi:
            uj.append(e)
            regi[rid] = {
                "cim":   e["cim"][:100],
                "talalt": datetime.now().isoformat()
            }

    print(f"\n💧 Új csepeli Vízművek esemény: {len(uj)}")
    if uj:
        email_kuldes(uj)
    else:
        print("✅ Nincs új esemény.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
