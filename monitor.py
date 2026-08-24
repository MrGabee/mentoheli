"""
🚁 Magyar Mentőhelikopter Monitor
Adatforrás: Flightradar24 HTML scraping
Detektálás: ATD (felszállás) és Landed (leszállás) változás alapján
Futtatás: GitHub Actions (percenként, self-loop)

KÉTFÉLE, EGYMÁSTÓL FÜGGETLEN FIGYELÉS:
  1. LAJSTROMJEL szerint (pl. ha-hbg) - a Flightradar24 "aircraft" oldaláról
  2. HÍVÓJEL szerint (pl. medic3) - a Flightradar24 "flights" (hívójel-előzmény)
     oldaláról

Ez azért fontos, mert ha egy géppark-váltás miatt megváltozna, melyik
lajstromjelű gép repül épp "MEDIC3" hívójellel (vagy fordítva, egy gép
hívójele változna), a MÁSIK módszer akkor is elkapja az eseményt.
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

# Ismert mentőhelikopterek – lajstromjel → hívójel (megjelenítéshez és a
# hívójel-alapú lekérdezés listájának összeállításához használjuk)
MENTO_GEPEK = {
    "ha-hbm": "MEDIC1",
    "ha-hbi": "MEDIC2",
    "ha-hbg": "MEDIC3",
    "ha-hbk": "MEDIC4",
    "ha-hbj": "MEDIC5",
    "ha-hbh": "MEDIC6",
    "ha-hbl": "MEDIC1",
    "ha-hbo": "MEDIC7",
    "ha-hbn": "MEDIC8",
}

# Az egyedi hívójelek listája (duplikátumok nélkül), amiket a lajstromjeltől
# FÜGGETLENÜL, KÜLÖN is lekérdezünk a Flightradar24 hívójel-előzményéből.
FIGYELT_HIVOJELEK = sorted(set(MENTO_GEPEK.values()))

ALLAPOT_FAJL    = "allapot.json"
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
            with open(fajl, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(alapert)

def ment(fajl, adat):
    with open(fajl, "w", encoding="utf-8") as f:
        json.dump(adat, f, ensure_ascii=False, indent=2)


# ════════════════════════════════════════════
#  📡  FLIGHTRADAR24 SCRAPING - KÖZÖS, ÚJRAFELHASZNÁLHATÓ FELDOLGOZÓ
# ════════════════════════════════════════════
def _tabla_feldolgozasa(html_szoveg, cimke):
    """A közös táblázat-feldolgozó logika - mind a lajstromjel-alapú, mind
    a hívójel-alapú FR24-oldal ugyanezt a táblaszerkezetet használja."""
    soup = BeautifulSoup(html_szoveg, "html.parser")
    tabla = soup.find("table", id="tbl-datatable")
    if not tabla:
        print(f"  ⚠️ Táblázat nem található – {cimke}")
        return None

    tbody = tabla.find("tbody")
    if not tbody:
        print(f"  ⚠️ Nincs tbody – {cimke}")
        return None

    sorok = tbody.find_all("tr", class_="data-row")
    if not sorok:
        print(f"  ⚠️ Nincs sor a táblázatban – {cimke}")
        return None

    # Első (legutóbbi) sor
    sor = sorok[0]
    cellak = sor.find_all("td", class_=lambda c: c and "hidden-xs" in c)

    datum     = ""
    callsign  = ""
    atd       = ""
    landed    = None
    elo       = False
    flight_id = ""

    datum_td = sor.find("td", attrs={"data-time-format": "DD MMM YYYY"})
    if datum_td:
        datum = datum_td.get_text(strip=True)

    atd_tds = sor.find_all("td", attrs={"data-timestamp": True})
    if len(atd_tds) >= 2:
        atd = atd_tds[1].get_text(strip=True)

    for td in cellak:
        txt = td.get_text(strip=True)
        if "MEDIC" in txt or "MEDIKOPTER" in txt:
            callsign = txt.strip("()")
            break

    status_td = sor.find("td", attrs={"data-prefix": True})
    if status_td:
        status_txt = status_td.get_text(strip=True)
        if "Landed" in status_txt:
            m = re.search(r"Landed\s+(\d{1,2}:\d{2})", status_txt)
            landed = m.group(1) if m else status_txt
            elo    = False
        else:
            elo = True

    play_btn = sor.find("a", class_="btn-playback")
    if play_btn:
        href = play_btn.get("href", "")
        m = re.search(r"#([0-9a-f]+)$", href)
        if m:
            flight_id = m.group(1)

    return {
        "atd":       atd,
        "landed":    landed,
        "elo":       elo,
        "datum":     datum,
        "callsign":  callsign,
        "flight_id": flight_id,
    }


def lekerdez_fr24_lajstromjel(reg):
    """Lekéri a Flightradar24 LAJSTROMJEL-alapú adatlapját (aircraft/{reg})."""
    url = f"https://www.flightradar24.com/data/aircraft/{reg}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ FR24 HTTP {r.status_code} – lajstrom {reg}")
            return None

        eredmeny = _tabla_feldolgozasa(r.text, f"lajstrom {reg}")
        if eredmeny is None:
            return None
        if not eredmeny["callsign"]:
            eredmeny["callsign"] = MENTO_GEPEK.get(reg, reg.upper())

        print(f"  ✅ FR24 [lajstrom {reg}]: datum={eredmeny['datum']} atd={eredmeny['atd']} "
              f"landed={eredmeny['landed']} elo={eredmeny['elo']} cs={eredmeny['callsign']}")
        return eredmeny
    except Exception as ex:
        print(f"  ❌ FR24 hiba (lajstrom {reg}): {ex}")
        return None


def lekerdez_fr24_hivojel(hivojel):
    """Lekéri a Flightradar24 HÍVÓJEL-alapú előzmény-oldalát
    (data/flights/{hívójel}) - ez FÜGGETLEN attól, éppen melyik lajstromjelű
    gép repül ezzel a hívójellel."""
    url = f"https://www.flightradar24.com/data/flights/{hivojel.lower()}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ FR24 HTTP {r.status_code} – hívójel {hivojel}")
            return None

        eredmeny = _tabla_feldolgozasa(r.text, f"hívójel {hivojel}")
        if eredmeny is None:
            return None
        if not eredmeny["callsign"]:
            eredmeny["callsign"] = hivojel.upper()

        # A hívójel-oldal táblázata jellemzően tartalmazza a lajstromjelet
        # is egy külön oszlopban - megpróbáljuk kinyerni, hogy a levélben
        # meg tudjuk mutatni, ÉPPEN melyik géppel repül ez a hívójel.
        soup = BeautifulSoup(r.text, "html.parser")
        tabla = soup.find("table", id="tbl-datatable")
        aktualis_reg = ""
        if tabla:
            tbody = tabla.find("tbody")
            if tbody:
                sorok = tbody.find_all("tr", class_="data-row")
                if sorok:
                    reg_link = sorok[0].find("a", href=re.compile(r"/data/aircraft/"))
                    if reg_link:
                        aktualis_reg = reg_link.get_text(strip=True)
        eredmeny["aktualis_reg"] = aktualis_reg

        print(f"  ✅ FR24 [hívójel {hivojel}]: datum={eredmeny['datum']} atd={eredmeny['atd']} "
              f"landed={eredmeny['landed']} elo={eredmeny['elo']} jelenlegi_gep={aktualis_reg}")
        return eredmeny
    except Exception as ex:
        print(f"  ❌ FR24 hiba (hívójel {hivojel}): {ex}")
        return None


# ════════════════════════════════════════════
#  🔁  ÁLLAPOT ÖSSZEHASONLÍTÁS
# ════════════════════════════════════════════
def osszehasonlit(regi_allapot, uj_adatok, esemeny_naplo):
    """A kulcsok formátuma: 'reg:ha-hbg' vagy 'cs:medic3' - így a két
    figyelési mód egymástól teljesen függetlenül, saját magában is
    felismeri a felszállás/leszállás eseményeket."""
    esemenyek = []
    most = datetime.now().timestamp()

    for kulcs, uj in uj_adatok.items():
        if uj is None:
            continue

        regi = regi_allapot.get(kulcs, {})

        regi_elo    = regi.get("elo", False)
        regi_atd    = regi.get("atd", "")
        regi_landed = regi.get("landed")
        regi_datum  = regi.get("datum", "")

        uj_elo    = uj["elo"]
        uj_atd    = uj["atd"]
        uj_landed = uj["landed"]
        uj_datum  = uj["datum"]

        def cooldown_ok(tipus):
            cd_kulcs = f"{kulcs}:{tipus}"
            utolso = esemeny_naplo.get(cd_kulcs, 0)
            if most - utolso < EMAIL_COOLDOWN:
                print(f"  ⏭️ Cooldown: {tipus} – {kulcs}")
                return False
            esemeny_naplo[cd_kulcs] = most
            return True

        # Ha legelső futás ennél a kulcsnál, csak elmentjük az állapotot
        if not regi:
            continue

        # 🚁⬆️ FELSZÁLLÁS DETEKTÁLÁSA
        felszallas_feltetel = (
            (uj_elo and not regi_elo) or
            (uj_datum != regi_datum and uj_datum != "") or
            (uj_atd and uj_atd != regi_atd)
        )

        if felszallas_feltetel:
            if cooldown_ok("FELSZALLAS"):
                print(f"  🚁⬆️ FELSZÁLLÁS: {kulcs} | {uj_datum} {uj_atd or 'Élő repülés'}")
                esemenyek.append({"tipus": "FELSZALLAS", "kulcs": kulcs, "adat": uj})

        # 🚁⬇️ LESZÁLLÁS DETEKTÁLÁSA
        elif uj_landed and not regi_landed:
            if cooldown_ok("LESZALLAS"):
                print(f"  🚁⬇️ LESZÁLLÁS: {kulcs} | {uj_datum} Landed {uj_landed}")
                esemenyek.append({"tipus": "LESZALLAS", "kulcs": kulcs, "adat": uj})

    return esemenyek


# ════════════════════════════════════════════
#  📧  E-MAIL KÜLDÉS
# ════════════════════════════════════════════
def email_kuldes(esemeny):
    tipus     = esemeny["tipus"]
    kulcs     = esemeny["kulcs"]
    adat      = esemeny["adat"]

    figyeles_tipusa = "Lajstromjel" if kulcs.startswith("reg:") else "Hívójel"
    azonosito = kulcs.split(":", 1)[1]

    callsign  = adat["callsign"] or MENTO_GEPEK.get(azonosito, azonosito.upper())
    datum     = adat["datum"]
    atd       = adat["atd"]
    landed    = adat["landed"]
    elo       = adat["elo"]
    flight_id = adat["flight_id"]
    aktualis_reg = adat.get("aktualis_reg", "")

    ido      = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    emoji    = "🚁⬆️" if tipus == "FELSZALLAS" else "🚁⬇️"
    tipus_hu = "FELSZÁLLÁS" if tipus == "FELSZALLAS" else "LESZÁLLÁS"
    szin     = "#c0392b" if tipus == "FELSZALLAS" else "#2980b9"

    if kulcs.startswith("reg:"):
        reg_upper = azonosito.upper()
        fr24_url  = f"https://www.flightradar24.com/data/aircraft/{azonosito}"
    else:
        reg_upper = aktualis_reg.upper() if aktualis_reg else "?"
        fr24_url  = f"https://www.flightradar24.com/data/flights/{azonosito.lower()}"

    fr24_map   = f"https://www.flightradar24.com/{callsign}"
    play_url   = f"{fr24_url}#{flight_id}" if flight_id else None

    def datum_magyar(d):
        honapok = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
                   "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
        try:
            resz = d.strip().split()
            return f"{resz[2]}.{honapok.get(resz[1], resz[1])}.{resz[0].zfill(2)}"
        except Exception:
            return d

    def ido_plusz2(ido_str):
        if not ido_str:
            return "Folyamatban..."
        try:
            h, m = map(int, ido_str.strip().split(":"))
            h = (h + 2) % 24
            return f"{h:02d}:{m:02d}"
        except Exception:
            return ido_str

    datum_hu = datum_magyar(datum) if datum else "Ma"
    atd_hu   = ido_plusz2(atd)
    landed_hu = ido_plusz2(landed) if landed else None

    if tipus == "FELSZALLAS":
        info = f"Felszállás: {datum_hu} {atd_hu}"
    else:
        info = f"Felszállás: {datum_hu} {atd_hu} → Leszállás: {landed_hu}"

    gombok = ""
    if elo and tipus == "FELSZALLAS":
        gombok += f"""
      <a href="{fr24_map}"
         style="display:block;background:#ff6600;color:#fff;padding:15px;
                border-radius:10px;text-decoration:none;font-size:16px;
                font-weight:bold;margin-bottom:12px">
        🔴 Élő követés – Flightradar24 térkép
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
        📋 Flightradar24 adatlap
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
      <div style="font-size:11px;opacity:.65;margin-top:4px">
        Észlelés módja: {figyeles_tipusa}-alapú figyelés
      </div>
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

    # ---- 1. LAJSTROMJEL szerinti lekérdezés (mint eddig) ----
    print("\n📋 Lajstromjel-alapú lekérdezések...")
    for reg in MENTO_GEPEK:
        print(f"\n🔍 Lekérdezés (lajstrom): {reg}")
        uj_adatok[f"reg:{reg}"] = lekerdez_fr24_lajstromjel(reg)

    # ---- 2. HÍVÓJEL szerinti lekérdezés (ÚJ, független) ----
    print("\n📻 Hívójel-alapú lekérdezések...")
    for hivojel in FIGYELT_HIVOJELEK:
        print(f"\n🔍 Lekérdezés (hívójel): {hivojel}")
        uj_adatok[f"cs:{hivojel.lower()}"] = lekerdez_fr24_hivojel(hivojel)

    esemenyek = osszehasonlit(regi_allapot, uj_adatok, esemeny_naplo)

    print(f"\n⚡ Változások: {len(esemenyek)}")
    for e in esemenyek:
        email_kuldes(e)

    # Állapot frissítése
    for kulcs, adat in uj_adatok.items():
        if adat is not None:
            regi_allapot[kulcs] = adat

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
