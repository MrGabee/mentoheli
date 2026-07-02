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
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

MAGYAR_TZ = timezone(timedelta(hours=2))

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


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

BALESET_KULCSSZAVAK = [
    "baleset", "gazolas", "gázolás", "gazolt", "gázolt",
    "utkozés", "ütközés", "utkozest", "karambol",
]

BALESET_KIZARO = [
    "baleset-megelőzés", "balesetmegelőzés", "balesetmentes",
    "baleset-megelőzési", "baleset nélkül", "balesetmentesen",
    "kerékpáros biztonság", "közlekedésbiztonsági", "meghibásodott", "műszaki ok",
]

# meghibásodott NINCS itt – csak baleset/forgalmi ok miatti pótlóbusz kell
VOLAN_KULCSSZAVAK = [
    "autóbusz menetrendi változás", "helyközi autóbusz",
    "járat törölve", "járatkimaradás", "pótlóbusz",
    "autóbuszjárat", "buszjárat", "menetrendi változás",
    "forgalmi változás", "útlezárás",
]

JOVO_KIZARO = [
    "hétfőtől", "kedtől", "szerdától", "csütörtöktől", "péntektől",
    "szombattól", "vasárnaptól", "holnaptól", "jövő héttől",
    "várhatóan", "tervezett", "előre jelzett",
    "hajnalban", "reggeltől", "éjszakától",
    " hétfőn", " kedden", " szerdán", " csütörtökön", " pénteken",
    " szombaton", " vasárnap", "holnap ",
    "rendezvény", "rendezvény miatt", "esemény miatt",
    "lezárják", "lezárásra kerül",
    "ideiglenes forgalmi változás", "ideiglenes menetrendi",
    "-ától", "-étől", "-jától",
]

OSSZES_KULCSSZO = BALESET_KULCSSZAVAK + VOLAN_KULCSSZAVAK
MAX_ORA = 3


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


def esemeny_tipus(url, cim, reszlet=""):
    szoveg        = (url + " " + cim).lower()
    teljes_szoveg = (url + " " + cim + " " + reszlet).lower()

    if any(k in szoveg for k in BALESET_KIZARO):
        van_baleset_szo = False
    else:
        van_baleset_szo = any(k in szoveg for k in BALESET_KULCSSZAVAK)

    if van_baleset_szo:
        return "BALESET"

    if any(k in szoveg for k in VOLAN_KULCSSZAVAK):
        if any(k in teljes_szoveg for k in JOVO_KIZARO):
            return None
        return "VOLAN"

    return None

def baleset_e(url, cim, reszlet=""):
    return esemeny_tipus(url, cim, reszlet) is not None

def friss_e(datum_str):
    if not datum_str:
        return True
    try:
        datum_str = datum_str.strip()
        for fmt in ["%Y.%m.%d. %H:%M", "%Y.%m.%d. %H:%M:%S", "%Y.%m.%d %H:%M"]:
            try:
                datum = datetime.strptime(datum_str, fmt)
                datum = datum.replace(tzinfo=MAGYAR_TZ)
                return magyar_ido() - datum <= timedelta(hours=MAX_ORA)
            except ValueError:
                continue
        return True
    except Exception:
        return True


def lekerdez_cikk_datuma(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None, ""
        soup = BeautifulSoup(r.text, "html.parser")

        datum = None
        teljes_szoveg = soup.get_text(separator=" ", strip=True)

        import re
        pattern = r'(\d{4}\.\d{2}\.\d{2}\.?\s+\d{2}:\d{2}(?::\d{2})?)'

        cimke_pattern = r'(?:Utolsó módosítás|Közzétéve|Frissítve|Megjelenés)[:\s]*' + pattern
        cimke_match = re.search(cimke_pattern, teljes_szoveg, re.IGNORECASE)
        if cimke_match:
            datum = cimke_match.group(1).strip()
            print(f"    📅 Dátum (címke alapján): {datum}")
        else:
            matches = re.findall(pattern, teljes_szoveg)
            if matches:
                datum = matches[-1].strip()
                print(f"    📅 Dátum (utolsó találat, fallback): {datum}")

        for zavaro in soup.find_all(["script", "style", "nav", "footer", "header"]):
            zavaro.decompose()
        for zavaro in soup.find_all(class_=re.compile(r"cookie|suti|gdpr|consent", re.I)):
            zavaro.decompose()

        tartalom_div = (
            soup.find("div", class_="field-type-text-with-summary") or
            soup.find("div", class_="field-name-body") or
            soup.find("article")
        )
        if tartalom_div:
            reszlet = tartalom_div.get_text(separator=" ", strip=True)[:1500]
        else:
            paragrafusok = soup.find_all("p")
            KIZARANDO_SZAVAK = ["süti", "cookie", "gdpr", "google analytics",
                                 "facebook pixel", "hírlevelünk", "fel- és leiratkozás",
                                 "marketing sütiket", "webanalitikai"]
            jo_bekezdesek = []
            for p in paragrafusok:
                szoveg = p.get_text(strip=True)
                if len(szoveg) > 50 and not any(k in szoveg.lower() for k in KIZARANDO_SZAVAK):
                    jo_bekezdesek.append(szoveg)
            reszlet = " ".join(jo_bekezdesek)[:1500]

        return datum, reszlet

    except Exception as ex:
        print(f"    ⚠️ Cikk hiba: {ex}")
        return None, ""

def lekerdez_lista():
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
                    esemenyek.append({"id": esemeny_id, "cim": cim, "url": full_url})
        except Exception as ex:
            print(f"  ❌ Lista hiba: {ex}")
    print(f"  📊 Összes MÁVINFORM link: {len(esemenyek)}")
    return esemenyek


def email_kuldes(uj_esetek):
    ido   = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)
    targy = f"🚂 MÁV/Volán esemény – {db} új | {ido}"

    sorok_html = ""
    sorok_txt  = ""

    for i, e in enumerate(uj_esetek, 1):
        cim     = e.get("cim", "—")
        reszlet = e.get("reszlet", "")[:800]
        url     = e.get("url", "")
        datum   = e.get("datum", "—")
        tipus   = e.get("tipus", "BALESET")

        if tipus == "VOLAN":
            badge = "🚌 VOLÁNBUSZ – FORGALMI/MENETREND"
            szin  = "#e67e22"
        else:
            badge = "🚂 BALESET / GÁZOLÁS"
            szin  = "#8B0000"

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:{szin};color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">
              {badge}
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


def hiba_email_kuldes(hiba_szoveg):
    try:
        ido = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
        targy = f"⚠️ MÁV/Volán Monitor HIBA | {ido}"
        szoveg = (
            f"A MÁV/Volán Monitor script hibára futott.\n"
            f"{'─'*40}\n"
            f"Időpont: {ido}\n\n"
            f"Hiba részletei:\n{hiba_szoveg}\n"
        )
        msg = MIMEMultipart("alternative")
        msg["Subject"] = targy
        msg["From"]    = f"⚠️ MÁV/Volán Monitor <{EMAIL_KULDO}>"
        msg["To"]      = EMAIL_CIMZETT
        msg.attach(MIMEText(szoveg, "plain", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
            smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
        print(f"📧 Hibaértesítő e-mail elküldve.")
    except Exception as ex:
        print(f"❌ A hibaértesítő e-mail küldése is sikertelen: {ex}")


def main():
    print(f"\n{'='*55}")
    print(f"🚂 MÁV Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    uj   = []

    esemenyek = lekerdez_lista()

    for e in esemenyek:
        rid = hash_id(e["id"])

        if rid in regi:
            continue

        tipus = esemeny_tipus(e["url"], e["cim"], e.get("reszlet", ""))
        if tipus is None:
            regi[rid] = {"cim": e["cim"][:100], "talalt": magyar_ido().isoformat()}
            continue

        e["tipus"] = tipus
        print(f"  🔍 {tipus} cikk: {e['cim'][:70]}")

        datum, reszlet = lekerdez_cikk_datuma(e["url"])

        if not friss_e(datum):
            print(f"    ⏩ Régi cikk ({datum}), kihagyva.")
            regi[rid] = {"cim": e["cim"][:100], "talalt": magyar_ido().isoformat()}
            continue

        print(f"    ✅ Friss {tipus} esemény!")
        e["datum"]   = datum or "—"
        e["reszlet"] = reszlet
        uj.append(e)
        regi[rid] = {"cim": e["cim"][:100], "talalt": magyar_ido().isoformat()}

    print(f"\n🚂 Új esemény: {len(uj)}")
    if uj:
        email_kuldes(uj)
    else:
        print("✅ Nincs új baleseti esemény.")

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
