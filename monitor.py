"""
🚁 Magyar Mentőhelikopter Monitor
Adatforrás: Flightradar24 HTML scraping (ha-hbm, ha-hbg, stb.)
Detektálás: ATD (felszállás) és Landed (leszállás) változás alapján
Futtatás: GitHub Actions (percenként, self-loop)
"""

import os
import json
import hashlib
import smtplib
import requests
import re
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

# Ismert mentőhelikopterek – lajstromjel → hívójel
MENTO_GEPEK = {
    "ha-hbg": "MEDIC3",
    "ha-hbh": "MEDIC6",
    "ha-hbi": "MEDIC6",
    "ha-hbk": "MEDIC",
    "ha-hbl": "MEDIC1",
    "ha-hbm": "MEDIC2",
    "ha-hbn": "MEDIC",
    "ha-hbo": "MEDIC7",
}

ALLAPOT_FAJL     = "allapot.json"
ESEMENY_NAPLO    = "esemeny_naplo.json"
EMAIL_COOLDOWN   = 180  # 3 perc

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


# ════════════════════════════════════════════
#  💾  ÁLLAPOT
# ════════════════════════════════════════════
def betolt(fajl, alapert={}):
    if os.path.exists(fajl):
        try:
            with open(fajl) as f:
                return json.load(f)
        except Exception:
            pass
    return dict(alapert)

def ment(fajl, adat):
    with open(fajl, "w", encoding="utf-8") as f:
        json.dump(adat, f, ensure_ascii=False, indent=2)


# ════════════════════════════════════════════
#  📡  FLIGHTRADAR24 SCRAPING
# ════════════════════════════════════════════
def lekerdez_fr24(reg):
    """
    Lekéri a Flightradar24 adatlapját és visszaadja az utolsó repülés adatait:
    {
      "atd":     "13:08",       # tényleges felszállás (helyi idő)
      "landed":  "13:51",       # leszállás (None ha még repül)
      "elo":     True/False,    # jelenleg a levegőben van-e
      "datum":   "01 Jul 2026",
      "callsign":"MEDIC2",
      "flight_id": "...",       # playback ID ha van
    }
    """
    url = f"https://www.flightradar24.com/data/aircraft/{reg}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ FR24 HTTP {r.status_code} – {reg}")
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        tabla = soup.find("table", id="tbl-datatable")
        if not tabla:
            print(f"  ⚠️ Táblázat nem található – {reg}")
            return None

        sorok = tabla.find("tbody").find_all("tr", class_="data-row")
        if not sorok:
            print(f"  ⚠️ Nincs sor a táblázatban – {reg}")
            return None

        # Első (legutóbbi) sor
        sor = sorok[0]
        cellak = sor.find_all("td", class_=lambda c: c and "hidden-xs" in c)

        datum    = ""
        callsign = ""
        atd      = ""
        landed   = None
        elo      = False
        flight_id = ""

        # Dátum
        datum_td = sor.find("td", attrs={"data-time-format": "DD MMM YYYY"})
        if datum_td:
            datum = datum_td.get_text(strip=True)

        # ATD
        atd_tds = sor.find_all("td", attrs={"data-timestamp": True})
        if len(atd_tds) >= 2:
            atd = atd_tds[1].get_text(strip=True)

        # Callsign
        for td in cellak:
            txt = td.get_text(strip=True)
            if "MEDIC" in txt or "MEDIKOPTER" in txt:
                callsign = txt.strip("()")
                break

        # Status (Landed / Scheduled / Unknown)
        status_td = sor.find("td", attrs={"data-prefix": True})
        if status_td:
            status_txt = status_td.get_text(strip=True)
            if "Landed" in status_txt:
                # "Landed 13:51" → kinyerjük az időt
                m = re.search(r"Landed\s+(\d{1,2}:\d{2})", status_txt)
                landed = m.group(1) if m else status_txt
                elo    = False
            elif "Scheduled" in status_txt or "Unknown" in status_txt:
                elo = True  # még nem landolt
            else:
                elo = True

        # Playback link
        play_btn = sor.find("a", class_="btn-playback")
        if play_btn:
            href = play_btn.get("href", "")
            m = re.search(r"#([0-9a-f]+)$", href)
            if m:
                flight_id = m.group(1)

        print(f"  ✅ FR24 {reg}: datum={datum} atd={atd} landed={landed} elo={elo} cs={callsign}")
        return {
            "atd":       atd,
            "landed":    landed,
            "elo":       elo,
            "datum":     datum,
            "callsign":  callsign or MENTO_GEPEK.get(reg, ""),
            "flight_id": flight_id,
        }

    except Exception as ex:
        print(f"  ❌ FR24 hiba ({reg}): {ex}")
        return None


# ════════════════════════════════════════════
#  🔁  ÁLLAPOT ÖSSZEHASONLÍTÁS
# ════════════════════════════════════════════
def osszehasonlit(regi_allapot, uj_adatok, esemeny_naplo):
    esemenyek = []
    most = datetime.now().timestamp()

    for reg, uj in uj_adatok.items():
        if uj is None:
            continue

        regi = regi_allapot.get(reg, {})
        regi_atd    = regi.get("atd", "")
        regi_landed = regi.get("landed")
        regi_datum  = regi.get("datum", "")

        uj_atd    = uj["atd"]
        uj_landed = uj["landed"]
        uj_datum  = uj["datum"]

        # Cooldown ellenőrzés
        def cooldown_ok(tipus):
            kulcs = f"{reg}:{tipus}"
            utolso = esemeny_naplo.get(kulcs, 0)
            if most - utolso < EMAIL_COOLDOWN:
                print(f"  ⏭️ Cooldown: {tipus} – {reg}")
                return False
            esemeny_naplo[kulcs] = most
            return True

        # FELSZÁLLÁS: új ATD jelent meg vagy megváltozott
        if uj_atd and (uj_atd != regi_atd or uj_datum != regi_datum):
            if regi_atd or regi_datum:  # ne az első betöltésnél
                if cooldown_ok("FELSZALLAS"):
                    print(f"  🚁⬆️ FELSZÁLLÁS: {reg} | {uj_datum} {uj_atd}")
                    esemenyek.append({"tipus": "FELSZALLAS", "reg": reg, "adat": uj})

        # LESZÁLLÁS: landed mező megjelent ahol még nem volt
        elif uj_landed and not regi_landed and regi_atd:
            if cooldown_ok("LESZALLAS"):
                print(f"  🚁⬇️ LESZÁLLÁS: {reg} | {uj_datum} Landed {uj_landed}")
                esemenyek.append({"tipus": "LESZALLAS", "reg": reg, "adat": uj})

    return esemenyek


# ════════════════════════════════════════════
#  📧  E-MAIL KÜLDÉS
# ════════════════════════════════════════════
def email_kuldes(esemeny):
    tipus    = esemeny["tipus"]
    reg      = esemeny["reg"]
    adat     = esemeny["adat"]
    callsign = adat["callsign"] or MENTO_GEPEK.get(reg, reg.upper())
    datum    = adat["datum"]
    atd      = adat["atd"]
    landed   = adat["landed"]
    elo      = adat["elo"]
    flight_id = adat["flight_id"]

    ido      = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    emoji    = "🚁⬆️" if tipus == "FELSZALLAS" else "🚁⬇️"
    tipus_hu = "FELSZÁLLÁS" if tipus == "FELSZALLAS" else "LESZÁLLÁS"
    szin     = "#c0392b" if tipus == "FELSZALLAS" else "#2980b9"

    reg_upper = reg.upper()
    fr24_url  = f"https://www.flightradar24.com/data/aircraft/{reg}"
    play_url  = f"https://www.flightradar24.com/data/aircraft/{reg}#{flight_id}" if flight_id else None

    # Info sor
    if tipus == "FELSZALLAS":
        info = f"Felszállás: {datum} {atd}"
    else:
        info = f"Felszállás: {datum} {atd} → Leszállás: {landed}"

    # Gombok
    gombok = ""
    if elo and tipus == "FELSZALLAS":
        gombok += f"""
      <a href="{fr24_url}"
         style="display:block;background:#ff6600;color:#fff;padding:15px;
                border-radius:10px;text-decoration:none;font-size:16px;
                font-weight:bold;margin-bottom:12px">
        🔴 Élő követés – Flightradar24
      </a>"""

    if play_url:
        gombok += f"""
      <a href="{play_url}"
         style="display:block;background:#cc4400;color:#fff;padding:14px;
                border-radius:10px;text-decoration:none;font-size:15px;
                font-weight:bold;margin-bottom:12px">
        ▶️ Visszajátszás – Flightradar24
      </a>"""

    gombok += f"""
      <a href="{fr24_url}"
         style="display:block;background:#888;color:#fff;padding:13px;
                border-radius:10px;text-decoration:none;font-size:14px;
                font-weight:bold">
        📋 Flightradar24 adatlap – {reg_upper}
      </a>"""

    targy = f"{emoji} Mentőhelikopter {tipus_hu} – {callsign} | {ido}"

    html = f"""<!DOCTYPE html>
<html lang="hu"><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px">
  <div style="max-width:480px;margin:0 auto">

    <div style="background:{szin};border-radius:12px 12px 0 0;padding:24px;
                text-align:center;color:#fff">
      <div style="font-size:44px;margin-bottom:8px">{emoji}</div>
      <div style="font-size:22px;font-weight:bold">Mentőhelikopter {tipus_hu}</div>
      <div style="font-size:13px;opacity:.75;margin-top:6px">{ido}</div>
    </div>

    <div style="background:#fff;padding:24px;text-align:center;
                border-left:1px solid #ddd;border-right:1px solid #ddd">
      <div style="font-size:36px;font-weight:bold;color:#2c3e50;
                  letter-spacing:1px">{callsign}</div>
      <div style="font-size:16px;color:#888;margin-top:4px;margin-bottom:8px">
        {reg_upper}
      </div>
      <div style="font-size:14px;color:#555;margin-bottom:24px;
                  background:#f8f8f8;padding:10px;border-radius:8px">
        {info}
      </div>
      {gombok}
    </div>

    <div style="background:#ecf0f1;border-radius:0 0 12px 12px;padding:12px;
                text-align:center;font-size:11px;color:#95a5a6">
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


# ════════════════════════════════════════════
#  ⚠️  HIBAJELENTŐ E-MAIL
# ════════════════════════════════════════════
def hiba_email(hiba_szoveg):
    try:
        ido   = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
        targy = f"⚠️ Mentőhelikopter Monitor HIBA | {ido}"
        szoveg = f"A Mentőhelikopter Monitor script hibára futott.\n\nIdőpont: {ido}\n\n{hiba_szoveg}"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = targy
        msg["From"]    = f"⚠️ Monitor <{EMAIL_KULDO}>"
        msg["To"]      = EMAIL_CIMZETT
        msg.attach(MIMEText(szoveg, "plain", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
            smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
    except Exception as ex:
        print(f"❌ Hibaértesítő küldése sikertelen: {ex}")


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*50}")
    print(f"🚁 Mentőhelikopter Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*50}")

    regi_allapot  = betolt(ALLAPOT_FAJL)
    esemeny_naplo = betolt(ESEMENY_NAPLO)
    uj_adatok     = {}

    for reg in MENTO_GEPEK:
        print(f"\n🔍 Lekérdezés: {reg}")
        uj_adatok[reg] = lekerdez_fr24(reg)

    esemenyek = osszehasonlit(regi_allapot, uj_adatok, esemeny_naplo)

    print(f"\n⚡ Változások: {len(esemenyek)}")
    for e in esemenyek:
        email_kuldes(e)

    # Állapot frissítése
    for reg, adat in uj_adatok.items():
        if adat is not None:
            regi_allapot[reg] = adat

    ment(ALLAPOT_FAJL, regi_allapot)
    ment(ESEMENY_NAPLO, esemeny_naplo)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        import traceback
        hiba_reszletek = traceback.format_exc()
        print(f"❌ VÁRATLAN HIBA:\n{hiba_reszletek}")
        hiba_email(hiba_reszletek)
        raise
