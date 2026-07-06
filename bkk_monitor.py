"""
🚌 BKK INFO Monitor – Baleset miatt terelések
Adatforrás: m.bkkinfo.hu (scraping)
Futtatás: GitHub Actions (percenként, self-loop)
"""

import os
import re
import time
import json
import hashlib
import smtplib
import requests
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

MAGYAR_TZ = timezone(timedelta(hours=2))

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


EMAIL_KULDO           = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO          = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT         = os.environ["EMAIL_CIMZETT_BKK"]
EMAIL_CIMZETT_KERULET = os.environ.get("EMAIL_CIMZETT_KERULET", "")

BKK_URL      = "https://m.bkkinfo.hu/"
BKK_BASE_URL = "https://m.bkkinfo.hu"
ALLAPOT_FAJL = "bkk_allapot.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
}

# Balesetes kulcsszavak
BALESET_KULCSSZAVAK = [
    "baleset", "gázolás", "gazolás", "ütközés", "utkozés",
    "karambol", "tűzoltó", "tuzolto", "mentő", "mento",
    "hatósági", "hatosagi", "helyszínel", "helyszynel",
    "életmentés", "eletmentes",
]

# Kizáró szavak
KIZARO_KULCSSZAVAK = [
    "utas rosszul", "rosszullét", "rosszul lett",
    "szabálytalan parkolás", "parkolási",
    "akadályozó jármű",
    "közműjavítás", "közmű",
    "karbantartás", "felújítás", "építkezés",
    "rendezvény", "járműhiba", 
]

# Figyelt csepeli vonalak
FIGYELT_VONALAK = [
    "35", "36", "38", "38A", "71", "138", "148", "151", "152", "159",
    "238", "278", "938", "948", "979", "979A", "H7",
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
#  🔍  SZŰRŐK
# ════════════════════════════════════════════
def baleset_e(szoveg):
    s = szoveg.lower()
    return any(k in s for k in BALESET_KULCSSZAVAK)

def kizaras_e(szoveg):
    s = szoveg.lower()
    return any(k in s for k in KIZARO_KULCSSZAVAK)

def figyelt_vonal_e(cim, reszlet=""):
    teljes = " " + (cim + " " + reszlet).upper() + " "
    for vonal in FIGYELT_VONALAK:
        pattern = r'(?<=[\s,.(/-])' + re.escape(vonal.upper()) + r'(?=[\s,.(/-])'
        if re.search(pattern, teljes):
            return True
    return False


# ════════════════════════════════════════════
#  📡  BKK INFO LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez_reszlet(url):
    """Lekéri az esemény részleteit az esemény oldaláról."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return "", ""
        soup = BeautifulSoup(r.text, "html.parser")

        # Badge típus
        badge = "🚨 FORGALMI ESEMÉNY"
        for tag in soup.find_all(["span", "div"]):
            txt = tag.get_text(strip=True)
            if "tűzoltó" in txt.lower() or "tuzolto" in txt.lower():
                badge = "🔥 TŰZOLTÓ"
                break
            elif "mentő" in txt.lower() or "mento" in txt.lower():
                badge = "🚑 MENTŐ"
                break
            elif "hatósági" in txt.lower() or "hatosagi" in txt.lower():
                badge = "👮 HATÓSÁGI ZÁRÁS"
                break

        # Részletes szöveg
        for zavaro in soup.find_all(["script", "style", "nav", "header", "footer"]):
            zavaro.decompose()

        reszlet = ""
        tartalom = soup.find("div", class_=re.compile(r"content|description|detail|szoveg", re.I))
        if tartalom:
            reszlet = tartalom.get_text(separator=" ", strip=True)[:800]
        else:
            bekezdesek = soup.find_all("p")
            jo = [p.get_text(strip=True) for p in bekezdesek if len(p.get_text(strip=True)) > 30]
            reszlet = " ".join(jo)[:800]

        return badge, reszlet
    except Exception as ex:
        print(f"  ⚠️ Részlet hiba: {ex}")
        return "🚨 FORGALMI ESEMÉNY", ""


def lekerdez_bkk():
    """Lekéri az m.bkkinfo.hu listát és visszaadja a balesetes eseményeket."""
    esemenyek = []
    try:
        print(f"🚌 BKK INFO lekérdezés: {BKK_URL}")
        r = requests.get(BKK_URL, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ HTTP {r.status_code}")
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        osszes = 0

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "/zavarok/" not in href:
                continue

            cim = link.get_text(strip=True)
            if not cim or len(cim) < 5:
                continue

            esemeny_id = href.split("/zavarok/")[-1].strip("/")
            if not esemeny_id:
                continue

            full_url = href if href.startswith("http") else BKK_BASE_URL + href
            osszes += 1

            # Csak balesetes eseményeket dolgozunk fel
            if baleset_e(cim) and not kizaras_e(cim):
                esemenyek.append({
                    "id":  esemeny_id,
                    "cim": cim,
                    "url": full_url,
                })

        print(f"  📊 Összes esemény: {osszes}")
        print(f"  🚨 Balesetes esemény: {len(esemenyek)}")
        return esemenyek

    except Exception as ex:
        print(f"  ❌ BKK hiba: {ex}")
        return []


# ════════════════════════════════════════════
#  📧  E-MAIL
# ════════════════════════════════════════════
def email_kuldes(uj_esetek, cimzett=None):
    cimzett = cimzett or EMAIL_CIMZETT
    ido  = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    db   = len(uj_esetek)
    targy = f"🚨 BKK forgalmi esemény – {db} új | {ido}"

    sorok_html = ""
    for i, e in enumerate(uj_esetek, 1):
        cim    = e.get("cim", "—")
        reszlet = e.get("reszlet", "")
        url    = e.get("url", BKK_URL)
        badge  = e.get("badge", "🚨 FORGALMI ESEMÉNY – TERELÉS")

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:#c0392b;color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">{badge}</span>
            <div style="font-size:15px;font-weight:bold;margin:10px 0;color:#2c3e50">{cim}</div>
            {"<div style='font-size:13px;color:#555;margin-bottom:10px;line-height:1.6'>" + reszlet + "</div>" if reszlet else ""}
            <a href="{url}" style="background:#2980b9;color:#fff;padding:7px 14px;
                                    border-radius:4px;text-decoration:none;font-size:12px;font-weight:bold">
              🔗 BKK INFO oldal
            </a>
          </td>
        </tr>"""

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
  .foot{{background:#ecf0f1;padding:12px 28px;font-size:11px;color:#95a5a6;text-align:center}}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>🚨 BKK – Baleset miatti terelés</h1>
    <small>{ido} | {db} új esemény</small>
  </div>
  <div class="body">
    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>
    <div style="text-align:center;margin-top:16px">
      <a href="{BKK_URL}" style="background:#c0392b;color:#fff;padding:9px 16px;
         border-radius:6px;text-decoration:none;font-weight:bold;font-size:12px">
        🚌 BKK INFO oldal
      </a>
    </div>
  </div>
  <div class="foot">Automatikus értesítő – GitHub Actions | BKK INFO adatai alapján</div>
</div></body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"🚨 BKK Monitor <{EMAIL_KULDO}>"
    msg["To"]      = cimzett
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
        smtp.sendmail(EMAIL_KULDO, cimzett, msg.as_string())
    print(f"📧 E-mail elküldve → {cimzett}: {targy}")


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"🚌 BKK Baleset Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    uj   = []

    esemenyek = lekerdez_bkk()

    for e in esemenyek:
        rid    = hash_id(e["id"])
        uj_cim = e["cim"]

        # Ha már ismerjük ÉS a cím nem változott → kihagyjuk
        if rid in regi and regi[rid].get("cim") == uj_cim:
            continue

        # Új esemény vagy cím változott → részletek lekérése
        badge, reszlet = lekerdez_reszlet(e["url"])

        # Kizárás ellenőrzése a részletes szöveg alapján is
        if kizaras_e(uj_cim + " " + reszlet):
            print(f"  ⏭️ Kizárva: {uj_cim[:60]}")
            regi[rid] = {"cim": uj_cim, "talalt": magyar_ido().isoformat()}
            continue

        e["badge"]   = badge
        e["reszlet"] = reszlet

        if rid in regi:
            print(f"  🔄 Cím változott: {regi[rid].get('cim','')[:40]} → {uj_cim[:40]}")
        else:
            print(f"  ✅ Új esemény: {uj_cim[:60]}")

        uj.append(e)
        regi[rid] = {"cim": uj_cim, "talalt": magyar_ido().isoformat()}

    print(f"\n🚨 Új/változott esemény: {len(uj)}")
    if uj:
        email_kuldes(uj)

        if EMAIL_CIMZETT_KERULET:
            kerulet = [e for e in uj if figyelt_vonal_e(e.get("cim",""), e.get("reszlet",""))]
            if kerulet:
                print(f"🚨 Kerületes e-mail: {len(kerulet)} esemény")
                email_kuldes(kerulet, cimzett=EMAIL_CIMZETT_KERULET)
    else:
        print("✅ Nincs új baleseti esemény.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
