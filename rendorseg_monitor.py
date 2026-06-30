"""
🚔 Rendőrség Baleseti Hírek Monitor
Adatforrás: police.hu RSS feed – Baleseti hírek
Futtatás: GitHub Actions (self-loop)
"""

import os
import json
import hashlib
import smtplib
import requests
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ─────────────────────────────────────────────
#  🕐  MAGYAR IDŐZÓNA
# ─────────────────────────────────────────────
MAGYAR_TZ = timezone(timedelta(hours=2))

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


# ─────────────────────────────────────────────
#  ⚙️  KONFIGURÁCIÓ
# ─────────────────────────────────────────────
EMAIL_KULDO    = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO   = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT  = os.environ["EMAIL_CIMZETT_RENDORSEG"]

RSS_URL        = "https://www.police.hu/hu/rss/Baleseti%20h%C3%ADrek"
ALLAPOT_FAJL   = "rendorseg_allapot.json"
MAX_CIKK       = 30  # csak az utolsó 30 cikket nézzük

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BalesetinfoMonitor/1.0)"
}

def tisztit_html(szoveg):
    """HTML tagek eltávolítása a szövegből."""
    szoveg = re.sub(r'<[^>]+>', ' ', szoveg)
    szoveg = szoveg.replace('&nbsp;', ' ').replace('&amp;', '&')
    szoveg = szoveg.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    szoveg = re.sub(r'\s+', ' ', szoveg).strip()
    return szoveg


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

def hash_id(szoveg):
    return hashlib.md5(szoveg.encode("utf-8")).hexdigest()[:12]


# ════════════════════════════════════════════
#  📡  RSS LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez_rss():
    try:
        r = requests.get(RSS_URL, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"⚠️ HTTP {r.status_code}")
            return []

        root = ET.fromstring(r.content)
        channel = root.find("channel")
        if channel is None:
            print("⚠️ Nem található channel az RSS-ben")
            return []

        cikkek = []
        for item in channel.findall("item")[:MAX_CIKK]:
            cim     = (item.findtext("title") or "").strip()
            link    = (item.findtext("link") or "").strip()
            leiras  = tisztit_html((item.findtext("description") or "").strip())
            datum   = (item.findtext("pubDate") or "").strip()

            if not cim or not link:
                continue

            cikkek.append({
                "cim":    cim,
                "link":   link,
                "leiras": leiras,
                "datum":  datum,
            })

        print(f"📡 RSS: {len(cikkek)} cikk beolvasva")
        return cikkek

    except ET.ParseError as e:
        print(f"❌ XML parse hiba: {e}")
        return []
    except Exception as e:
        print(f"❌ RSS hiba: {e}")
        return []


# ════════════════════════════════════════════
#  🕐  DÁTUM FELDOLGOZÁS
# ════════════════════════════════════════════
def parse_datum(datum_str):
    """RSS pubDate formátum: 'Mon, 30 Jun 2026 10:30:00 +0200'"""
    if not datum_str:
        return None
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
    ]:
        try:
            return datetime.strptime(datum_str, fmt)
        except ValueError:
            continue
    return None

def datum_magyar(datum_str):
    """Megjelenítési formátum: 2026.06.30 10:30"""
    d = parse_datum(datum_str)
    if d:
        return d.astimezone(MAGYAR_TZ).strftime("%Y.%m.%d %H:%M")
    return datum_str or "—"


# ════════════════════════════════════════════
#  📧  E-MAIL KÜLDÉS
# ════════════════════════════════════════════
def email_kuldes(uj_cikkek):
    ido = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    db  = len(uj_cikkek)
    targy = f"🚔 Rendőrség – {db} új baleseti hír | {ido}"

    sorok_html = ""
    for i, c in enumerate(uj_cikkek, 1):
        datum_str = datum_magyar(c["datum"])
        leiras    = c["leiras"][:3000] if c["leiras"] else ""
        link      = c["link"]
        cim       = c["cim"]

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:#1a237e;color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">
              🚔 RENDŐRSÉG – BALESETI HÍR
            </span>
            <div style="font-size:15px;font-weight:bold;margin:10px 0;color:#2c3e50">
              {cim}
            </div>
            <div style="font-size:12px;color:#888;margin-bottom:8px">
              📅 {datum_str}
            </div>
            {"<div style='font-size:13px;color:#555;margin-bottom:10px;line-height:1.6'>" + leiras + "</div>" if leiras else ""}
            <a href="{link}" style="background:#1a237e;color:#fff;padding:7px 14px;
                                     border-radius:4px;text-decoration:none;
                                     font-size:12px;font-weight:bold">
              🔗 Teljes hír – police.hu
            </a>
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="hu"><head><meta charset="UTF-8">
<style>
  body {{ font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0; }}
  .wrap {{ max-width:650px;margin:20px auto;background:#fff;border-radius:10px;
           overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.15); }}
  .hdr {{ background:#1a237e;color:#fff;padding:22px 28px; }}
  .hdr h1 {{ margin:0;font-size:20px; }}
  .hdr small {{ opacity:.85;font-size:13px; }}
  .body {{ padding:20px 28px; }}
  table {{ width:100%;border-collapse:collapse; }}
  td {{ padding:7px 10px;font-size:13px; }}
  .foot {{ background:#ecf0f1;padding:12px 28px;font-size:11px;
           color:#95a5a6;text-align:center; }}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>🚔 Rendőrség – Baleseti hírek</h1>
    <small>{ido} | {db} új hír | police.hu RSS</small>
  </div>
  <div class="body">
    <table>{sorok_html}</table>
    <div style="text-align:center;margin-top:16px">
      <a href="https://www.police.hu/hu/hirek-es-informaciok/legfrissebb-hireink/baleseti-hirek"
         style="background:#1a237e;color:#fff;padding:9px 16px;border-radius:6px;
                text-decoration:none;font-weight:bold;font-size:12px">
        🚔 Összes baleseti hír – police.hu
      </a>
    </div>
  </div>
  <div class="foot">Automatikus értesítő – GitHub Actions | police.hu RSS alapján</div>
</div></body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"🚔 Rendőrség Monitor <{EMAIL_KULDO}>"
    msg["To"]      = EMAIL_CIMZETT
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
        smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
    print(f"📧 E-mail elküldve: {targy}")


# ════════════════════════════════════════════
#  ⚠️  HIBAJELENTŐ E-MAIL
# ════════════════════════════════════════════
def hiba_email_kuldes(hiba_szoveg):
    try:
        ido   = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
        targy = f"⚠️ Rendőrség Monitor HIBA | {ido}"
        szoveg = (
            f"A Rendőrség Monitor script hibára futott.\n"
            f"{'─'*40}\n"
            f"Időpont: {ido}\n\n"
            f"Hiba részletei:\n{hiba_szoveg}\n"
        )
        msg = MIMEMultipart("alternative")
        msg["Subject"] = targy
        msg["From"]    = f"⚠️ Rendőrség Monitor <{EMAIL_KULDO}>"
        msg["To"]      = EMAIL_CIMZETT
        msg.attach(MIMEText(szoveg, "plain", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
            smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
        print("📧 Hibaértesítő e-mail elküldve.")
    except Exception as ex:
        print(f"❌ Hibaértesítő küldése is sikertelen: {ex}")


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"🚔 Rendőrség Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi   = betolt_allapot()
    cikkek = lekerdez_rss()

    uj = []
    for c in cikkek:
        rid = hash_id(c["link"])
        if rid not in regi:
            uj.append(c)
            regi[rid] = {
                "cim":   c["cim"][:100],
                "datum": c["datum"],
                "talalt": magyar_ido().isoformat()
            }

    print(f"🚔 Új baleseti hírek: {len(uj)}")
    if uj:
        email_kuldes(uj)
    else:
        print("✅ Nincs új hír.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        import traceback
        hiba_reszletek = traceback.format_exc()
        print(f"❌ VÁRATLAN HIBA:\n{hiba_reszletek}")
        hiba_email_kuldes(hiba_reszletek)
        raise
