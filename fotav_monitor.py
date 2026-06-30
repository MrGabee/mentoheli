"""
🔥 FŐTÁV Távhő Monitor – Csepel (XXI. kerület)
Adatforrás: gmp.fotav.hu/KMZ/munkatabl.html
Szűrés: Csepeli irányítószámok (1211-1221)
Futtatás: GitHub Actions (percenként, self-loop)
"""

import os
import json
import hashlib
import smtplib
import requests
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
#  🕐  MAGYAR IDŐZÓNA (UTC+2, GitHub Actions UTC-t használ)
# ─────────────────────────────────────────────
MAGYAR_TZ = timezone(timedelta(hours=2))

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT"]

FOTAV_URL    = "https://gmp.fotav.hu/KMZ/munkatabl.html"
ALLAPOT_FAJL = "fotav_allapot.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
    "Referer": "https://gmp.fotav.hu/mappublic.aspx",
}

# Csepel irányítószámok (csak XXI. kerület valódi csepeli részei)
CSEPEL_IRSZ = ["1211", "1212", "1213", "1214", "1215"]


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
#  📍  CSEPEL SZŰRŐ
# ════════════════════════════════════════════
def csepel_e(cim):
    """Ellenőrzi hogy a cím csepeli irányítószámot tartalmaz-e."""
    for irsz in CSEPEL_IRSZ:
        if irsz in cim:
            return True
    return False


# ════════════════════════════════════════════
#  📡  LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez():
    """FŐTÁV munkatabl.html scraping."""
    try:
        print(f"🌐 Lekérdezés: {FOTAV_URL}")
        r = requests.get(FOTAV_URL, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ HTTP {r.status_code}")
            return []

        soup = BeautifulSoup(r.content, "html.parser")
        esemenyek = []

        # GridView1 – Jelenlegi munkavégzések
        gv1 = soup.find("table", id="GridView1")
        if gv1:
            for sor in gv1.find_all("tr")[1:]:  # fejléc kihagyása
                cellak = sor.find_all("td")
                if len(cellak) >= 4:
                    cim     = cellak[0].get_text(strip=True)
                    kezdes  = cellak[1].get_text(strip=True)
                    veg     = cellak[2].get_text(strip=True)
                    info    = cellak[3].get_text(strip=True)
                    utfelb  = cellak[4].get_text(strip=True) if len(cellak) > 4 else "—"
                    if csepel_e(cim):
                        esemenyek.append({
                            "tipus": "JELENLEGI_MUNKA",
                            "cim": cim, "kezdes": kezdes,
                            "veg": veg, "info": info,
                            "utfelbontas": utfelb
                        })

        # GridView2 – Jelenlegi kiesett épületek
        gv2 = soup.find("table", id="GridView2")
        if gv2:
            for sor in gv2.find_all("tr")[1:]:
                cellak = sor.find_all("td")
                if len(cellak) >= 3:
                    cim    = cellak[0].get_text(strip=True)
                    kezdes = cellak[1].get_text(strip=True)
                    veg    = cellak[2].get_text(strip=True)
                    if csepel_e(cim) and "nincsenek" not in cim.lower():
                        esemenyek.append({
                            "tipus": "KIESETT_EPULET",
                            "cim": cim, "kezdes": kezdes,
                            "veg": veg, "info": "Kiesett épület",
                            "utfelbontas": "—"
                        })

        # GridView3 – Tervezett munkavégzések
        gv3 = soup.find("table", id="GridView3")
        if gv3:
            for sor in gv3.find_all("tr")[1:]:
                cellak = sor.find_all("td")
                if len(cellak) >= 4:
                    cim     = cellak[0].get_text(strip=True)
                    kezdes  = cellak[1].get_text(strip=True)
                    veg     = cellak[2].get_text(strip=True)
                    info    = cellak[3].get_text(strip=True)
                    utfelb  = cellak[4].get_text(strip=True) if len(cellak) > 4 else "—"
                    if csepel_e(cim):
                        esemenyek.append({
                            "tipus": "TERVEZETT_MUNKA",
                            "cim": cim, "kezdes": kezdes,
                            "veg": veg, "info": info,
                            "utfelbontas": utfelb
                        })

        # GridView4 – Tervezett kiesett épületek
        gv4 = soup.find("table", id="GridView4")
        if gv4:
            for sor in gv4.find_all("tr")[1:]:
                cellak = sor.find_all("td")
                if len(cellak) >= 3:
                    cim    = cellak[0].get_text(strip=True)
                    kezdes = cellak[1].get_text(strip=True)
                    veg    = cellak[2].get_text(strip=True)
                    if csepel_e(cim) and "nincsenek" not in cim.lower():
                        esemenyek.append({
                            "tipus": "TERVEZETT_KIESETT",
                            "cim": cim, "kezdes": kezdes,
                            "veg": veg, "info": "Tervezett kiesés",
                            "utfelbontas": "—"
                        })

        print(f"  📊 Csepeli találatok: {len(esemenyek)}")
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
    ido   = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)
    targy = f"🔥 FŐTÁV Csepel – {db} új esemény | {ido}"

    tipus_info = {
        "JELENLEGI_MUNKA":    ("🔴", "JELENLEGI MUNKAVÉGZÉS",    "#c0392b"),
        "KIESETT_EPULET":     ("🔴", "KIESETT ÉPÜLET",           "#8B0000"),
        "TERVEZETT_MUNKA":    ("🟠", "TERVEZETT MUNKAVÉGZÉS",    "#e67e22"),
        "TERVEZETT_KIESETT":  ("🟠", "TERVEZETT KIESÉS",         "#d35400"),
    }

    sorok_html = ""
    sorok_txt  = ""

    for i, e in enumerate(uj_esetek, 1):
        tipus  = e.get("tipus", "")
        emoji, label, szin = tipus_info.get(tipus, ("🔵", tipus, "#2980b9"))
        cim    = e.get("cim", "—")
        kezdes = e.get("kezdes", "—")
        veg    = e.get("veg", "—")
        info   = e.get("info", "—")
        utfelb = e.get("utfelbontas", "—")

        gmaps = f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(cim)}"

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:{szin};color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">
              {emoji} {label}
            </span>
            <div style="font-size:15px;font-weight:bold;margin:10px 0;color:#2c3e50">
              {cim}
            </div>
            <table style="font-size:13px;width:100%;margin-top:6px">
              <tr><td style="color:#888;width:140px">⏰ Kezdés:</td>
                  <td><strong>{kezdes}</strong></td></tr>
              <tr><td style="color:#888">⏰ Vége:</td>
                  <td><strong>{veg}</strong></td></tr>
              <tr><td style="color:#888">📋 Információ:</td>
                  <td>{info}</td></tr>
              <tr><td style="color:#888">🚧 Útfelbontás:</td>
                  <td>{utfelb}</td></tr>
            </table>
            <div style="margin-top:10px">
              <a href="{gmaps}" style="background:#4285f4;color:#fff;padding:7px 14px;
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
            f"Cím:     {cim}\n"
            f"Kezdés:  {kezdes}\n"
            f"Vége:    {veg}\n"
            f"Info:    {info}\n"
            f"Útfelb.: {utfelb}\n"
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
    <h1>🔥 FŐTÁV – Csepeli értesítő</h1>
    <small>{ido} | {db} új esemény (XXI. kerület)</small>
  </div>
  <div class="body">
    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>
    <div style="text-align:center;margin-top:16px">
      <a href="https://gmp.fotav.hu/mappublic.aspx"
         style="background:#c0392b;color:#fff;padding:9px 16px;border-radius:6px;
                text-decoration:none;font-weight:bold;font-size:12px">
        🔥 FŐTÁV térkép
      </a>
    </div>
  </div>
  <div class="foot">Automatikus értesítő – GitHub Actions | FŐTÁV adatai alapján</div>
</div></body></html>"""

    szoveges = f"🔥 FŐTÁV Csepel értesítő\nIdőpont: {ido}\n{sorok_txt}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"🔥 FŐTÁV Monitor <{EMAIL_KULDO}>"
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
    print(f"🔥 FŐTÁV Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    uj   = []

    esemenyek = lekerdez()

    for e in esemenyek:
        rid = hash_id(e["tipus"] + e["cim"] + e["kezdes"])
        if rid not in regi:
            uj.append(e)
            regi[rid] = {
                "cim": e["cim"][:100],
                "talalt": magyar_ido().isoformat()
            }

    print(f"\n🔥 Új csepeli FŐTÁV esemény: {len(uj)}")
    if uj:
        email_kuldes(uj)
    else:
        print("✅ Nincs új esemény.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
