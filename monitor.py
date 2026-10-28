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
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from bs4 import BeautifulSoup

import email_arculat as ea
import heli_pozicio as hp

MAGYAR_TZ = ZoneInfo("Europe/Budapest")

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
def _gep_reg(kulcs, callsign, aktualis_reg, nyom):
    """Melyik géphez tartozik az esemény (a nyomvonalhoz kell)."""
    if kulcs.startswith("reg:"):
        return kulcs[4:]
    if aktualis_reg:
        return aktualis_reg.lower()
    jeloltek = [r for r, cs in MENTO_GEPEK.items() if cs.upper() == (callsign or "").upper()]
    jeloltek.sort(key=lambda r: -((nyom.get(r) or {}).get("pontok") or [[0]])[-1][0])
    return jeloltek[0] if jeloltek else ""


def _nagy(szoveg, url, szin):
    return (f'<a href="{ea.esc(url)}" style="display:block;text-align:center;background:{szin};color:#ffffff;'
            f'text-decoration:none;font-weight:bold;font-size:17px;padding:15px 12px;border-radius:8px;'
            f'margin:0 0 10px">{szoveg}</a>') if url else ""


def pozicio_blokk(tipus, pontok):
    """(adatsorok, gombok HTML, térkép PNG, szöveges sorok) a nyomvonalból."""
    if not pontok:
        return [], "", None, []
    felszallas = tipus == "FELSZALLAS"
    elso, utolso = pontok[0], pontok[-1]
    sorok, szoveg = [], []
    hely = hp.hely_neve(elso[1], elso[2])
    sorok.append(("Felszállás helye", f"{hely} ({elso[1]:.5f}, {elso[2]:.5f})" if hely else f"{elso[1]:.5f}, {elso[2]:.5f}"))
    szoveg.append(f"Felszállás helye: {hely} {elso[1]:.5f}, {elso[2]:.5f}")
    gombok = _nagy("📍 Felszállás helye – térkép", hp.gmaps(elso[1], elso[2]), "#16a34a" if felszallas else "#5b6b7b")
    if felszallas:
        if len(pontok) > 1:
            sorok.append(("Most", f"{utolso[3]} m magasan, {utolso[4]} km/h"))
    else:
        uhely = hp.hely_neve(utolso[1], utolso[2])
        korhaz = hp.korhaz_kozel(utolso[1], utolso[2])
        sorok.append(("Utolsó ismert pont", f"{uhely} ({utolso[1]:.5f}, {utolso[2]:.5f})" if uhely
                      else f"{utolso[1]:.5f}, {utolso[2]:.5f}"))
        if korhaz:
            sorok.append(("Közelben", f"🏥 {korhaz}"))
        sorok.append(("Csepeltől", f"{hp.tavolsag_km(hp.CSEPEL, utolso[1:3]):.1f} km"))
        st = hp.statisztika(pontok)
        if st:
            sorok.append(("Repült táv", f"{st['km']} km (legmagasabban {st['max_m']} m, max. {st['max_kmh']} km/h)"))
        szoveg.append(f"Utolsó ismert pont: {uhely} {utolso[1]:.5f}, {utolso[2]:.5f}" + (f" ({korhaz})" if korhaz else ""))
        gombok = _nagy("📍 Utolsó ismert pont – térkép", hp.gmaps(utolso[1], utolso[2]), "#dc2626") + gombok
    return sorok, gombok, hp.terkep_png(pontok), szoveg


def email_kuldes(esemeny, nyom=None):
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

    tipus_hu = "FELSZÁLLÁS" if tipus == "FELSZALLAS" else "LESZÁLLÁS"

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

    def helyi_ido(ido_str):
        """Az FR24 táblázata UTC-ben adja az időt; magyar idő (téli/nyári)."""
        if not ido_str:
            return ""
        try:
            h, m = map(int, ido_str.strip().split(":"))
            utc = datetime.now(timezone.utc).replace(hour=h, minute=m, second=0, microsecond=0)
            return utc.astimezone(MAGYAR_TZ).strftime("%H:%M")
        except Exception:
            return ido_str

    datum_hu  = datum_magyar(datum) if datum else "Ma"
    atd_hu    = helyi_ido(atd)
    if atd_hu == "—":
        atd_hu = ""
    landed_hu = helyi_ido(landed) if landed else ""
    felszallas = tipus == "FELSZALLAS"
    def repult_ido():
        try:
            if atd_hu and landed_hu:
                perc = (int(landed_hu[:2]) * 60 + int(landed_hu[3:])) - (int(atd_hu[:2]) * 60 + int(atd_hu[3:]))
                return f"{perc % 1440} perc"
        except ValueError:
            pass
        return ""
    repult = repult_ido()

    sorok = [
        ("Dátum", datum_hu),
        ("Felszállás", atd_hu or "folyamatban"),
        ("Leszállás", "" if felszallas else landed_hu),
        ("Repült idő", "" if felszallas else repult),
        ("Lajstromjel", "" if reg_upper == "?" else reg_upper),
        ("Észlelés", f"{figyeles_tipusa} alapján"),
    ]
    nyom = nyom if nyom is not None else {}
    reg = _gep_reg(kulcs, callsign, aktualis_reg, nyom)
    pontok = hp.aktualis_ut(nyom, reg) if reg else []
    if not felszallas:
        # leszállásnál az FR24 visszajátszás pontosabb (a földig tart), ha elérhető
        pontok = hp.fr24_nyomvonal(flight_id, HEADERS) or pontok
    if not atd_hu and pontok and not felszallas:
        atd_hu = datetime.fromtimestamp(pontok[0][0], MAGYAR_TZ).strftime("%H:%M")
        sorok[1] = ("Felszállás", atd_hu)
        sorok[3] = ("Repült idő", repult_ido())
    poz_sorok, poz_gombok, terkep, poz_szoveg = pozicio_blokk(tipus, pontok)
    sorok += poz_sorok
    nagy_gomb = _nagy
    # A legfontosabbak felül, nagy gombokkal
    gombok = ""
    if elo and felszallas:
        gombok += nagy_gomb("🔴 Élő követés – Flightradar24", fr24_map, "#dc2626")
    gombok += poz_gombok
    if play_url:
        gombok += nagy_gomb("▶️ Visszajátszás – Flightradar24", play_url, "#1f5fae" if not felszallas else "#b45309")
    test = (gombok + ea.adat_tabla(sorok)
            + ('<img src="cid:terkep" width="100%" alt="Térkép" style="display:block;width:100%;'
               'max-width:556px;border-radius:6px;margin:6px 0 4px">'
               '<div style="font-size:12px;color:#8a949e;margin-bottom:6px">'
               + ("🟢 felszállás · 🔴 jelenlegi helyzet</div>" if felszallas else
                  "🟢 felszállás · 🔴 utolsó ismert pont (alacsonyan elveszhet a jel, ezért a leszállóhely "
                  "pár száz méterrel arrébb is lehet)</div>") if terkep else "")
            + ea.gomb("Flightradar24 adatlap", fr24_url, masodlagos=True))

    jelveny = ('<span style="display:inline-block;font-weight:bold;font-size:13px;line-height:1;'
               'padding:6px 9px;border-radius:4px;background:#c8102e;color:#ffffff;'
               f'font-family:Arial,sans-serif;letter-spacing:.5px">🚁 {ea.esc(callsign)}</span>')
    html = ea.keret(
        ea.kartya(ea.SZIN["piros"] if felszallas else ea.SZIN["kek"],
                  "⬆️ Felszállt" if felszallas else "⬇️ Leszállt",
                  f"Mentőhelikopter – {callsign}", test, jelvenyek=jelveny),
        "Mentőhelikopter Figyelő · Flightradar24 adatai alapján")

    targy = (f"🚁⬆️ {callsign} felszállt · {atd_hu or 'most'}" if felszallas
             else f"🚁⬇️ {callsign} leszállt · {landed_hu}")
    szoveges = (f"Mentőhelikopter {tipus_hu} – {callsign} {reg_upper}\n"
                f"Felszállás: {datum_hu} {atd_hu}\n" + ("" if felszallas else f"Leszállás: {landed_hu}\n")
                + "".join(f"{x}\n" for x in poz_szoveg) + f"{play_url or fr24_url}\n")

    valtozatok = MIMEMultipart("alternative")
    valtozatok.attach(MIMEText(szoveges, "plain", "utf-8"))
    valtozatok.attach(MIMEText(html, "html", "utf-8"))
    if terkep:
        msg = MIMEMultipart("related")
        msg.attach(valtozatok)
        kep = MIMEImage(terkep, "png")
        kep.add_header("Content-ID", "<terkep>")
        kep.add_header("Content-Disposition", "inline", filename="terkep.png")
        msg.attach(kep)
    else:
        msg = valtozatok
    msg["Subject"] = targy
    msg["From"]    = f"Mentőhelikopter Figyelő <{EMAIL_KULDO}>"
    msg["To"]      = EMAIL_CIMZETT

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

    # ---- 3. Pozíciók (adsb.lol / adsb.fi) a nyomvonalhoz ----
    print("\n🛰️ Pozíciók...")
    nyom = regi_allapot.get("_nyom", {})
    for reg in MENTO_GEPEK:
        hp.frissit(nyom, reg)

    esemenyek = osszehasonlit(regi_allapot, uj_adatok, esemeny_naplo)

    print(f"\n⚡ Változások: {len(esemenyek)}")
    for e in esemenyek:
        email_kuldes(e, nyom)
    for e in esemenyek:
        if e["tipus"] == "LESZALLAS":
            reg = _gep_reg(e["kulcs"], e["adat"].get("callsign"), e["adat"].get("aktualis_reg", ""), nyom)
            if reg:
                hp.lezar(nyom, reg)
    regi_allapot["_nyom"] = nyom

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
