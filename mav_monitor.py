"""
🚂 MÁV/Volán Rendkívüli Esemény Monitor
Adatforrás: MÁVINFORM (mavcsoport.hu/mavinform)
Szűrés: CSAK baleset, gázolás, rendkívüli időjárás
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
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT"]

MAV_URL      = "https://www.mavcsoport.hu/mavinform"
MAV_BASE_URL = "https://www.mavcsoport.hu"
ALLAPOT_FAJL = "mav_allapot.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
}

# ─────────────────────────────────────────────
#  🔍  SZŰRŐ KULCSSZAVAK
#  Csak ezeket akarjuk – URL vagy cím alapján
# ─────────────────────────────────────────────
IGEN_KULCSSZAVAK = [
    # Baleset és gázolás – CSAK ezek kellenek
    "baleset", "gazolas", "gázolás", "gazolt", "gázolt",
    "utkozés", "ütközés", "utkozest", "karambol",
]


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
#  🔍  SZŰRŐ
# ════════════════════════════════════════════
def erdekes_e(url, cim):
    """Csak baleset/gázolás/rendkívüli időjárás esetén igaz."""
    szoveg = (url + " " + cim).lower()
    return any(k in szoveg for k in IGEN_KULCSSZAVAK)


# ════════════════════════════════════════════
#  📡  LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez_lista():
    """MÁVINFORM lista – összes /mavinform/ link összegyűjtése."""
    esemenyek = []

    for oldal in range(0, 2):
        url = f"{MAV_URL}?page={oldal}" if oldal > 0 else MAV_URL
        try:
            print(f"🌐 Lekérdezés: {url}")
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                print(f"  ⚠️ HTTP {r.status_code}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if "/mavinform/" not in href:
                    continue
                cim = link.get_text(strip=True)
                if not cim or len(cim) < 5:
                    continue
                full_url = MAV_BASE_URL + href if href.startswith("/") else href
                esemeny_id = href.split("/mavinform/")[-1].strip("/").split("?")[0]
                if not esemeny_id:
                    continue
                if not any(e["id"] == esemeny_id for e in esemenyek):
                    esemenyek.append({
                        "id": esemeny_id,
                        "cim": cim,
                        "url": full_url,
                    })

        except Exception as ex:
            print(f"  ❌ Hiba: {ex}")

    print(f"  📊 Összes MÁVINFORM link: {len(esemenyek)}")
    return esemenyek

def lekerdez_reszlet(url):
    """Cikk részletének letöltése."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        tartalom = (
            soup.find("div", class_="field-type-text-with-summary") or
            soup.find("div", class_="field-name-body") or
            soup.find("article") or
            soup.find("main")
        )
        if tartalom:
            return tartalom.get_text(separator=" ", strip=True)[:2000]
        body = soup.find("body")
        return body.get_text(separator=" ", strip=True)[:2000] if body else ""
    except Exception:
        return ""


# ════════════════════════════════════════════
#  📧  E-MAIL
# ════════════════════════════════════════════
def email_kuldes(uj_esetek):
    ido   = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)
    targy = f"🚂 MÁV/Volán rendkívüli esemény – {db} új | {ido}"

    sorok_html = ""
    sorok_txt  = ""

    for i, e in enumerate(uj_esetek, 1):
        cim     = e.get("cim", "—")
        reszlet = e.get("reszlet", "")[:800]
        url     = e.get("url", "")

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:#8B0000;color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">
              🚂 RENDKÍVÜLI ESEMÉNY
            </span>
            <div style="font-size:15px;font-weight:bold;margin:10px 0;color:#2c3e50">
              {cim}
            </div>
            {"<div style='font-size:13px;color:#555;margin-bottom:10px;line-height:1.6'>" + reszlet + "</div>" if reszlet else ""}
            <a href="{url}" style="background:#2980b9;color:#fff;padding:7px 14px;
                                    border-radius:4px;text-decoration:none;
                                    font-size:12px;font-weight:bold">
              🔗 MÁVINFORM – Teljes cikk
            </a>
          </td>
        </tr>"""

        sorok_txt += (
            f"\n{'─'*45}\n"
            f"{i}. 🚂 {cim}\n"
            f"Link: {url}\n"
            + (f"{reszlet[:300]}\n" if reszlet else "")
        )

    html = f"""<!DOCTYPE html>
<html lang="hu"><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}}
  .wrap{{max-width:650px;margin:20px auto;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.15)}}
  .hdr{{background:#8B0000;color:#fff;padding:22px 28px}}
  .hdr h1{{margin:0;font-size:20px}}
  .hdr small{{opacity:.85;font-size:13px}}
  .body{{padding:20px 28px}}
  .foot{{background:#ecf0f1;padding:12px 28px;font-size:11px;
         color:#95a5a6;text-align:center}}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>🚂 MÁV/Volán – Rendkívüli esemény</h1>
    <small>{ido} | {db} új esemény | Baleset / Gázolás / Rendkívüli időjárás</small>
  </div>
  <div class="body">
    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>
    <div style="text-align:center;margin-top:16px">
      <a href="https://www.mavcsoport.hu/mavinform"
         style="background:#8B0000;color:#fff;padding:9px 16px;border-radius:6px;
                text-decoration:none;font-weight:bold;font-size:12px">
        🚂 MÁVINFORM oldal
      </a>
    </div>
  </div>
  <div class="foot">Automatikus értesítő – GitHub Actions | MÁVINFORM adatai alapján</div>
</div></body></html>"""

    szoveges = f"🚂 MÁV/Volán Rendkívüli Esemény\nIdőpont: {ido}\n{sorok_txt}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"🚂 MÁV Monitor <{EMAIL_KULDO}>"
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
    print(f"🚂 MÁV Monitor – {datetime.now().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    uj   = []

    esemenyek = lekerdez_lista()

    for e in esemenyek:
        rid = hash_id(e["id"])

        # Ha már ismerjük → kihagyjuk
        if rid in regi:
            continue

        # URL/cím alapú szűrés – csak baleset/gázolás/rendkívüli időjárás
        if erdekes_e(e["url"], e["cim"]):
            print(f"  🚨 Találat: {e['cim'][:70]}")
            reszlet = lekerdez_reszlet(e["url"])
            e["reszlet"] = reszlet
            uj.append(e)

        # Minden esetben mentjük az ID-t hogy ne kérdezzük le újra
        regi[rid] = {
            "cim": e["cim"][:100],
            "talalt": datetime.now().isoformat()
        }

    print(f"\n🚂 Új rendkívüli esemény: {len(uj)}")
    if uj:
        email_kuldes(uj)
    else:
        print("✅ Nincs új rendkívüli esemény.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
