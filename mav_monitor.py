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
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

import email_arculat as ea

MAGYAR_TZ = ZoneInfo("Europe/Budapest")

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
    "kerékpáros biztonság", "közlekedésbiztonsági", "meghibásodott",
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

def jovobeli_e(cim, reszlet=""):
    """Igaz, ha a cikk egy mai napnál későbbi dátumról szól (pl. „november 3. és 5. között”).
    Gábor kérése: jövőbeli tervről, előre bejelentett változásról nem kell levél."""
    import re
    ma = magyar_ido().date()
    for ev, ho, nap in re.findall(r"(?:(\d{4})\.\s*)?(" + "|".join(HONAPOK) + r")\s+(\d{1,2})\b",
                                   (cim + " " + reszlet).lower()):
        try:
            datum = datetime(int(ev) if ev else ma.year, HONAPOK[ho], int(nap)).date()
        except ValueError:
            continue
        # Év nélküli dátumnál az év eleji dátum decemberben már jövő évet jelent
        if not ev and (ma - datum).days > 180:
            datum = datum.replace(year=ma.year + 1)
        if datum > ma:
            return True
    return False


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


HONAPOK = {"január": 1, "február": 2, "március": 3, "április": 4, "május": 5, "június": 6,
           "július": 7, "augusztus": 8, "szeptember": 9, "október": 10, "november": 11, "december": 12}


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
        # A MÁVINFORM cikkein a dátum betűs hónappal áll a node-date dobozban:
        # "2026. október 28. szerda, 19.12 / Utolsó módosítás: 2026. október 28. szerda, 20.29"
        node_datum = soup.find(class_="node-date")
        betus = re.findall(r"(\d{4})\.\s*([a-záéíóöőúüű]+)\s+(\d{1,2})\.[^,\d]*,\s*(\d{1,2})[.:](\d{2})",
                           node_datum.get_text(" ", strip=True).lower()) if node_datum else []
        betus = [d for d in betus if d[1] in HONAPOK]
        if betus:
            ev, ho, nap, ora, perc = betus[-1]
            datum = f"{ev}.{HONAPOK[ho]:02d}.{int(nap):02d}. {int(ora):02d}:{perc}"
            print(f"    📅 Dátum (node-date): {datum}")
        elif cimke_match:
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

        # A MÁVINFORM cikk szövege a field-body-ban: sárga doboz (összefoglaló), kék
        # doboz(ok), alatta címek és felsorolások (pl. a kimaradó járatok listája).
        dobozok = []
        torzs = soup.find("div", class_="field-body")
        if torzs:
            for elem in torzs.find_all(["div", "p", "h2", "h3", "h4", "li"]):
                if elem.name == "div" and not set(elem.get("class") or []) & {"yellowbox", "bluebox"}:
                    continue
                if elem.find_parent(class_=["yellowbox", "bluebox"]) or (elem.name == "p" and elem.find_parent("li")):
                    continue
                t = elem.get_text(" ", strip=True)
                if t:
                    dobozok.append(("• " + t) if elem.name == "li" else t)
        if not dobozok:
            dobozok = [d.get_text(" ", strip=True) for d in soup.find_all("div", class_=["yellowbox", "bluebox"])]
            dobozok = [d for d in dobozok if d]
        # Rövid (pl. baleseti) cikkeknél nincs doboz, a szöveg a field-body soraiban van
        if not dobozok:
            if torzs:
                sorok = [d.get_text(" ", strip=True) for d in torzs.find_all(["div", "p"], recursive=False)]
                dobozok = [s for s in sorok if s] or [torzs.get_text(" ", strip=True)]
                dobozok = [d for d in dobozok if d]
        tartalom_div = None if dobozok else (
            soup.find("div", class_="field-type-text-with-summary") or
            soup.find("div", class_="field-name-body") or
            soup.find("article")
        )
        if dobozok:
            reszlet = "\n\n".join(dobozok)[:3000]
        elif tartalom_div:
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


# Jelvények: MÁV kék, Volánbusz narancs
MAV_JELVENY = ('<span style="display:inline-block;font-weight:bold;font-size:13px;line-height:1;'
               'padding:6px 9px;border-radius:4px;background:#003f87;color:#ffffff;'
               'font-family:Arial,sans-serif;letter-spacing:.5px">🚂 MÁV</span>')
VOLAN_JELVENY = ('<span style="display:inline-block;font-weight:bold;font-size:13px;line-height:1;'
                 'padding:6px 9px;border-radius:4px;background:#f39200;color:#ffffff;'
                 'font-family:Arial,sans-serif;letter-spacing:.5px">🚌 VOLÁNBUSZ</span>')


VOLAN_BEVEZETO = "A Volánbusz tájékoztatása szerint: "


def email_kartya(e):
    volan = e.get("tipus") == "VOLAN"
    reszlet = e.get("reszlet", "")
    if volan and reszlet:
        reszlet = VOLAN_BEVEZETO + reszlet
    if len(reszlet) > 2500:
        reszlet = reszlet[:2500].rsplit(" ", 1)[0] + " …"
    test = (ea.adat_tabla([("Utolsó módosítás", "" if e.get("datum") in (None, "—") else e["datum"])])
            + "".join(ea.bekezdes(b) for b in reszlet.split("\n\n"))
            + ea.gomb("Teljes cikk", e.get("url", ""))
            + ea.gomb("MÁVINFORM", MAV_URL, masodlagos=True))
    return ea.kartya(ea.SZIN["sarga"] if volan else ea.SZIN["piros"],
                     "Forgalmi / menetrendi változás" if volan else "Baleset / gázolás",
                     e.get("cim", "—"), test,
                     jelvenyek=VOLAN_JELVENY if volan else MAV_JELVENY,
                     cimke_szin=ea.SZIN["sarga_szoveg"] if volan else None)


def email_kuldes(uj_esetek):
    db = len(uj_esetek)
    elso = uj_esetek[0]
    elotag = "🚌 Volánbusz" if elso.get("tipus") == "VOLAN" else "🚂 MÁV"
    if db == 1:
        targy = f"{elotag} · {elso.get('cim', '')[:90]}"
    else:
        targy = f"🚂 MÁV/Volán: {db} új esemény · {elso.get('cim', '')[:60]} és még {db - 1}"

    # a balesetek elöl
    rendezett = sorted(uj_esetek, key=lambda e: e.get("tipus") == "VOLAN")
    html = ea.keret("".join(email_kartya(e) for e in rendezett),
                    "MÁV/Volán Figyelő · MÁVINFORM · ugyanarról a cikkről több levél nem jön")

    szoveges = "MÁV/Volán Figyelő – új események\n"
    for e in rendezett:
        szoveges += (f"\n{'Volánbusz' if e.get('tipus') == 'VOLAN' else 'MÁV baleset'}: {e.get('cim', '')}\n"
                     f"  {e.get('datum', '')}\n")
        if e.get("tipus") == "VOLAN" and e.get("reszlet"):
            szoveges += f"  {VOLAN_BEVEZETO}{e['reszlet'][:400]}\n"
        szoveges += f"  {e.get('url', '')}\n"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"MÁV/Volán Figyelő <{EMAIL_KULDO}>"
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

        if jovobeli_e(e["cim"], reszlet):
            print("    ⏩ Jövőbeli változásról szól, kihagyva.")
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
