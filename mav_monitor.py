"""
🚂 MÁV/Volán Rendkívüli Esemény Monitor
Adatforrás: MÁVINFORM (mavcsoport.hu/mavinform)
Szűrés: CSAK baleset/gázolás, ÉS csak friss (max 3 óra) cikkek
Futtatás: GitHub Actions (percenként, self-loop)
"""

import os
import json
import hashlib
import smtplib
import requests
from datetime import datetime, timedelta
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

# Csak baleset/gázolás kulcsszavak az URL-ben vagy címben
BALESET_KULCSSZAVAK = [
    "baleset", "gazolas", "gázolás", "gazolt", "gázolt",
    "utkozés", "ütközés", "utkozest", "karambol",
]

# Max ennyi óra régi cikket fogadunk el
MAX_ORA = 3


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
#  🔍  SZŰRŐK
# ════════════════════════════════════════════
def baleset_e(url, cim):
    szoveg = (url + " " + cim).lower()
    return any(k in szoveg for k in BALESET_KULCSSZAVAK)

def friss_e(datum_str):
    """
    Ellenőrzi hogy a cikk friss-e (max MAX_ORA órás).
    Formátum: '2026.06.27. 14:33' vagy '2026.06.27. 14:33:00'
    """
    if not datum_str:
        return True  # Ha nincs dátum, elfogadjuk
    try:
        datum_str = datum_str.strip()
        # Különböző formátumok kezelése
        for fmt in ["%Y.%m.%d. %H:%M", "%Y.%m.%d. %H:%M:%S", "%Y.%m.%d %H:%M"]:
            try:
                datum = datetime.strptime(datum_str, fmt)
                return datetime.now() - datum <= timedelta(hours=MAX_ORA)
            except ValueError:
                continue
        return True  # Ha nem sikerül parse-olni, elfogadjuk
    except Exception:
        return True


# ════════════════════════════════════════════
#  📡  LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez_cikk_datuma(url):
    """Egy MÁVINFORM cikk utolsó módosítási dátumát és tartalmát tölti le."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None, ""
        soup = BeautifulSoup(r.text, "html.parser")

        # Dátum keresése – "Utolsó módosítás: 2026.06.27. 14:33"
        datum = None
        teljes_szoveg = soup.get_text(separator=" ", strip=True)

        # Keresés a szövegben
        import re
        pattern = r'(\d{4}\.\d{2}\.\d{2}\.?\s+\d{2}:\d{2}(?::\d{2})?)'
        matches = re.findall(pattern, teljes_szoveg)
        if matches:
            # Az első (legfrissebb) dátumot vesszük
            datum = matches[0].strip()
            print(f"    📅 Dátum: {datum}")

        # Tartalom keresése
        tartalom_div = (
            soup.find("div", class_="field-type-text-with-summary") or
            soup.find("div", class_="field-name-body") or
            soup.find("article")
        )
        if tartalom_div:
            reszlet = tartalom_div.get_text(separator=" ", strip=True)[:1500]
        else:
            # Fallback: keresünk érdemi bekezdéseket
            paragrafusok = soup.find_all("p")
            reszlet = " ".join(p.get_text(strip=True) for p in paragrafusok
                              if len(p.get_text(strip=True)) > 50)[:1500]

        return datum, reszlet

    except Exception as ex:
        print(f"    ⚠️ Cikk hiba: {ex}")
        return None, ""

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
            print(f"  ❌ Lista hiba: {ex}")

    print(f"  📊 Összes MÁVINFORM link: {len(esemenyek)}")
    return esemenyek


# ════════════════════════════════════════════
#  📧  E-MAIL
# ════════════════════════════════════════════
def email_kuldes(uj_esetek):
    ido   = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)
    targy = f"🚂 MÁV/Volán baleset – {db} új esemény | {ido}"

    sorok_html = ""
    sorok_txt  = ""

    for i, e in enumerate(uj_esetek, 1):
        cim     = e.get("cim", "—")
        reszlet = e.get("reszlet", "")[:800]
        url     = e.get("url", "")
        datum   = e.get("datum", "—")

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:#8B0000;color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">
              🚂 BALESET / GÁZOLÁS
            </span>
            <div style="font-size:15px;font-weight:bold;margin:10px 0;color:#2c3e50">
              {cim}
            </div>
            <div style="font-size:12px;color:#888;margin-bottom:8px">
              ⏰ Utolsó módosítás: {datum}
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
            f"Dátum: {datum}\n"
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
    <h1>🚂 MÁV/Volán – Baleset értesítő</h1>
    <small>{ido} | {db} új esemény</small>
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

    szoveges = f"🚂 MÁV/Volán Baleset\nIdőpont: {ido}\n{sorok_txt}"

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

        # 1. URL/cím alapú szűrés – csak baleset/gázolás
        if not baleset_e(e["url"], e["cim"]):
            # Nem baleset – mentjük és kihagyjuk
            regi[rid] = {"cim": e["cim"][:100], "talalt": datetime.now().isoformat()}
            continue

        print(f"  🔍 Baleset cikk: {e['cim'][:70]}")

        # 2. Dátum + tartalom lekérése
        datum, reszlet = lekerdez_cikk_datuma(e["url"])

        # 3. Frissesség ellenőrzése – csak max 3 órás cikk kell
        if not friss_e(datum):
            print(f"    ⏩ Régi cikk ({datum}), kihagyva.")
            regi[rid] = {"cim": e["cim"][:100], "talalt": datetime.now().isoformat()}
            continue

        print(f"    ✅ Friss baleset esemény!")
        e["datum"]   = datum or "—"
        e["reszlet"] = reszlet
        uj.append(e)
        regi[rid] = {"cim": e["cim"][:100], "talalt": datetime.now().isoformat()}

    print(f"\n🚂 Új baleseti esemény: {len(uj)}")
    if uj:
        email_kuldes(uj)
    else:
        print("✅ Nincs új baleseti esemény.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
