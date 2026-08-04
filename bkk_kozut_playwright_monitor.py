"""
🚧 BKK KÖZÚTI BALESET-FIGYELŐ (Playwright, valódi böngészővel)
Forrás: https://bkk.hu/bkk-info/#!t=kozut&e=3&d=today (baleset szűrővel előszűrve)

FONTOS: ez a script egy VALÓDI, headless Chrome böngészőt indít (Playwright),
ami kiállja a Cloudflare-védelmet, mert úgy viselkedik, mint egy igazi
felhasználó böngészője - nem hamisított kéréseket küld.

ÚJ FUNKCIÓ - TÉRKÉP CSATOLÁSA:
Amikor egy eseményre rákattintasz a bkk.hu oldalon, a fölötte lévő térkép
pin-t (piros jelölőt) tesz ki a pontos helyszínre, és odaközelít. Ennek
nincs egyszerűen kinyerhető nyers koordinátája a DOM-ban (a térkép egy
MapLibre GL WebGL-vászon), ezért a megoldás: minden ÚJ eseménynél a
szkript rákattint a sorra, megvárja, hogy a térkép a pin-re ugorjon, és
egy képernyőképet készít a térképről - ezt csatolja az e-mailhez a
szöveges adatok mellé.

--- VÁLTOZÁSOK ---
1) Minden időbélyeg explicit "Europe/Budapest" időzónában készül, tzdata
   nélkül is működő fallback-kal (kézi EU nyári/téli időszámítás).
2) Az oldalbetöltés több próbálkozást és exponenciális várakozást kap.
3) Ha a futás bármilyen okból elhasal, hiba-jelző e-mail megy ki.
4) Minden futás frissíti a heartbeat fájlt.
5) ÚJ: minden új eseményhez térkép-képernyőkép csatolva az e-mailhez.
"""

import os
import json
import time
import calendar
import hashlib
import smtplib
import traceback
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception
from playwright.sync_api import sync_playwright

TESZT_KATEGORIA = os.environ.get("TESZT_KATEGORIA", "3")  # 3=Baleset, 8=Lezárás, 9=Sávlezárás
BKK_KOZUT_URL = f"https://bkk.hu/bkk-info/#!t=kozut&e={TESZT_KATEGORIA}&d=today"
ALLAPOT_FAJL = "bkk_kozut_allapot.json"
HEARTBEAT_FAJL = "bkk_kozut_utolso_futas.txt"
LOG_FAJL = "bkk_kozut_monitor.log"
TERKEP_MENTES_MAPPA = "bkk_kozut_terkepek"

EMAIL_KULDO   = os.environ.get("EMAIL_KULDO", "")
EMAIL_JELSZO  = os.environ.get("EMAIL_JELSZO", "")
EMAIL_CIMZETT = os.environ.get("EMAIL_CIMZETT_BKK", "")

TESZT_MOD = os.environ.get("TESZT_MOD", "0") == "1"

MAX_PROBALKOZAS = int(os.environ.get("MAX_PROBALKOZAS", "3"))
UJRAPROBALKOZAS_ALAP_VARAKOZAS_MP = 10

# A térkép elem CSS szelektora a bkk.hu oldalon (MapLibre GL vászon).
TERKEP_SZELEKTOR = ".maplibregl-map"

# Ezt a kódot MÉG A BKK OLDAL SAJÁT JAVASCRIPT-JE ELŐTT fecskendezzük be
# (Playwright add_init_script) - egy "csapdát" állít a window.maplibregl
# globálisra: amint az oldal ráírja (a könyvtár betöltésekor), rögtön
# "belehallgatunk" a Marker.setLngLat hívásaiba, és minden valódi GPS
# koordinátát elmentünk egy tömbbe. Ez megbízhatóbb, mint utólag a DOM-ból
# próbálni kibányászni a koordinátákat.
GPS_ELCSIPO_SCRIPT = """
window.__bkk_koordinatak = [];
let _maplibregl_belso;
Object.defineProperty(window, 'maplibregl', {
  configurable: true,
  get() { return _maplibregl_belso; },
  set(ertek) {
    _maplibregl_belso = ertek;
    try {
      if (ertek && ertek.Marker && ertek.Marker.prototype && !ertek.Marker.prototype.__bkk_patched) {
        const eredeti = ertek.Marker.prototype.setLngLat;
        ertek.Marker.prototype.setLngLat = function (lngLat) {
          try { window.__bkk_koordinatak.push(lngLat); } catch (e) {}
          return eredeti.call(this, lngLat);
        };
        ertek.Marker.prototype.__bkk_patched = true;
      }
    } catch (e) {}
  }
});
"""

logging.basicConfig(
    filename=LOG_FAJL,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# ------------------------------------------------------------------
# Időzóna - tzdata nélkül is működő fallback-kal
# ------------------------------------------------------------------
def _het_utolso_vasarnapja_utc(ev, honap):
    utolso_nap = calendar.monthrange(ev, honap)[1]
    d = datetime(ev, honap, utolso_nap, tzinfo=timezone.utc)
    while d.weekday() != 6:
        d -= timedelta(days=1)
    return d.replace(hour=1, minute=0, second=0, microsecond=0)


def _eu_nyari_ido_van(utc_datetime):
    ev = utc_datetime.year
    marc_atallas = _het_utolso_vasarnapja_utc(ev, 3)
    okt_atallas = _het_utolso_vasarnapja_utc(ev, 10)
    return marc_atallas <= utc_datetime < okt_atallas


def _budapesti_zona_biztonsagos():
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo("Europe/Budapest")
    except ZoneInfoNotFoundError:
        logging.warning("ZoneInfo('Europe/Budapest') nem található - manuális fallback aktiválva.")
        return None


_BUDAPESTI_ZONA = _budapesti_zona_biztonsagos()


def most():
    utc_most = datetime.now(timezone.utc)
    if _BUDAPESTI_ZONA is not None:
        return utc_most.astimezone(_BUDAPESTI_ZONA)
    eltolas = timedelta(hours=2) if _eu_nyari_ido_van(utc_most) else timedelta(hours=1)
    nev = "CEST" if eltolas == timedelta(hours=2) else "CET"
    return utc_most.astimezone(timezone(eltolas, name=nev))


# ------------------------------------------------------------------
# Oldal betöltése + esemény-lista szöveg + (új eseményekhez) térkép-screenshot
# ------------------------------------------------------------------
def oldal_feldolgozasa(csak_ezen_azonositokhoz_kell_terkep):
    """Elindít egy valódi Chrome-ot, betölti a baleset-szűrt BKK közúti
    oldalt, kiolvassa a lista szövegét, és a MÉG NEM LÁTOTT eseményekhez
    (amiknek az azonosítója benne van a csak_ezen_azonositokhoz_kell_terkep
    halmazban) rákattint, és térkép-screenshotot készít róluk.

    Visszaadja: (nyers_lista_szoveg, {esemeny_id: terkep_png_bytes})
    """
    utolso_hiba = None

    for probalkozas in range(1, MAX_PROBALKOZAS + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    viewport={"width": 1400, "height": 1000},
                )
                context.add_init_script(GPS_ELCSIPO_SCRIPT)
                page = context.new_page()

                print(f"🌐 Betöltés ({probalkozas}/{MAX_PROBALKOZAS}): {BKK_KOZUT_URL}")
                page.goto(BKK_KOZUT_URL, wait_until="load", timeout=30000)
                page.wait_for_timeout(5000)
                cookie_sav_elfogadasa(page)

                teljes_szoveg = page.inner_text("body")

                # Az esemény-sorok szövegének kinyerése ideiglenesen (hogy
                # tudjuk, mely címekre kell rákattintani a térképhez) -
                # a végleges feldolgozást az esemenyek_kinyerese() végzi.
                esemenyek = esemenyek_kinyerese(teljes_szoveg)

                terkepek = {}
                for e in esemenyek:
                    if e["id"] not in csak_ezen_azonositokhoz_kell_terkep:
                        continue
                    try:
                        png_bajtok, koordinata = terkep_adat_egy_esemenyhez(page, e["cim"])
                        if png_bajtok:
                            terkepek[e["id"]] = {"png": png_bajtok, "koordinata": koordinata}
                    except Exception as terkep_hiba:
                        logging.warning(f"Térkép-adat sikertelen ehhez: {e['cim']} - {terkep_hiba}")

                browser.close()
                return teljes_szoveg, terkepek

        except Exception as ex:
            utolso_hiba = ex
            logging.warning(f"Oldalbetöltés sikertelen ({probalkozas}/{MAX_PROBALKOZAS}): {ex}")
            print(f"  ⚠️ Sikertelen próbálkozás ({probalkozas}/{MAX_PROBALKOZAS}): {ex}")
            if probalkozas < MAX_PROBALKOZAS:
                varakozas = UJRAPROBALKOZAS_ALAP_VARAKOZAS_MP * (2 ** (probalkozas - 1))
                print(f"  ⏳ Várakozás {varakozas} másodpercet újrapróbálkozás előtt...")
                time.sleep(varakozas)

    raise RuntimeError(f"Az oldal betöltése {MAX_PROBALKOZAS} próbálkozás után is sikertelen volt: {utolso_hiba}")


def terkep_adat_egy_esemenyhez(page, cim):
    """Rákattint a megadott című esemény-sorra (ettől a térkép a helyszínre
    ugrik egy pin-nel), megvárja az animációt, majd visszaadja:
    (térkép_png_bájtok, gps_koordináta_vagy_None).
    A GPS-koordinátát a GPS_ELCSIPO_SCRIPT által elcsípett valódi
    MapLibre setLngLat()-hívásokból olvassuk ki - ez a kattintás által
    kiváltott UTOLSÓ koordináta lesz. Ha bármi nem sikerül, a screenshot
    None, a koordináta is None - a hívó fél ilyenkor egyszerűen kihagyja
    ezt a részt, de a szöveges adat attól még megy."""
    # Ürítjük az elcsípett koordináták listáját, hogy csak az EBBEN a
    # kattintásban keletkezőt kapjuk el, ne egy korábbi eseményét.
    page.evaluate("window.__bkk_koordinatak = []")

    sor_lokator = page.get_by_text(cim, exact=False)
    talalt_db = sor_lokator.count()
    print(f"    🔎 '{cim}' szövegre illeszkedő elem(ek) száma az oldalon: {talalt_db}")
    if talalt_db == 0:
        print("    ⚠️ Nem található a sor szövege az oldalon - kihagyva (kép/koordináta nélkül).")
        return None, None

    try:
        sor_lokator.first.click(timeout=5000)
        print("    ✅ Sikeres kattintás a sorra.")
    except Exception as kattintas_hiba:
        print(f"    ⚠️ Kattintás sikertelen (pl. lefedő elem/cookie-sáv állhat az útban): {kattintas_hiba}")
        logging.warning(f"Kattintás sikertelen ehhez: {cim} - {kattintas_hiba}")
        return None, None

    page.wait_for_timeout(1800)  # a térkép pan/zoom animációjának ideje

    koordinata = None
    try:
        elcsipett = page.evaluate("window.__bkk_koordinatak")
        print(f"    🔎 GPS-elcsípő tömb tartalma a kattintás után: {elcsipett}")
        if elcsipett:
            utolso = elcsipett[-1]
            # A MapLibre LngLat vagy {lng,lat} objektum, vagy [lng,lat]
            # tömb lehet a hívó kód szerint - mindkettőt kezeljük.
            if isinstance(utolso, dict) and "lng" in utolso and "lat" in utolso:
                koordinata = (utolso["lat"], utolso["lng"])
            elif isinstance(utolso, list) and len(utolso) == 2:
                koordinata = (utolso[1], utolso[0])
            else:
                print(f"    ⚠️ Az elcsípett koordináta ismeretlen formátumú: {utolso!r}")
        else:
            print("    ⚠️ Nem csípett el egyetlen setLngLat()-hívást sem a kattintás alatt.")
    except Exception as koord_hiba:
        print(f"    ⚠️ GPS-koordináta kiolvasása sikertelen: {koord_hiba}")
        logging.warning(f"GPS-koordináta kiolvasása sikertelen: {koord_hiba}")

    terkep = page.locator(TERKEP_SZELEKTOR).first
    terkep_darab = terkep.count()
    print(f"    🔎 Térkép elem található-e a szelektorral ({TERKEP_SZELEKTOR}): {terkep_darab} db")
    png_bajtok = terkep.screenshot() if terkep_darab > 0 else None
    print(f"    🔎 Screenshot elkészült: {'igen, ' + str(len(png_bajtok)) + ' bájt' if png_bajtok else 'NEM'}")

    return png_bajtok, koordinata


def cookie_sav_elfogadasa(page):
    """Automatizált, nem bejelentkezett böngészőnél gyakran megjelenik egy
    cookie-elfogadó sáv, ami LEFEDHETI az esemény-sorokat, és emiatt a
    rájuk kattintás "csendben" sikertelen lehet (a kattintás technikailag
    a cookie-sávot találja el, nem a mögötte lévő sort). Ez a függvény
    megpróbálja a leggyakoribb "Elfogadom" jellegű gombokat megnyomni -
    ha nem talál ilyet, egyszerűen nem csinál semmit (nem hiba)."""
    jelolt_szovegek = ["Elfogadom", "Rendben", "Elfogad", "Accept", "OK", "Értem"]
    for szoveg in jelolt_szovegek:
        try:
            gomb = page.get_by_role("button", name=szoveg, exact=False)
            if gomb.count() > 0 and gomb.first.is_visible():
                gomb.first.click(timeout=2000)
                print(f"    🍪 Cookie-sáv elfogadva ('{szoveg}' gombbal).")
                page.wait_for_timeout(500)
                return
        except Exception:
            continue
    print("    🍪 Nem található/nem kellett cookie-elfogadó gomb.")
    """Csak kiírja a nyers szöveget a logba, e-mail küldés nélkül -
    ebből pontosítjuk a feldolgozó logikát. Térkép-screenshotot NEM
    készít, hogy a teszt gyors maradjon."""
    szoveg, _ = oldal_feldolgozasa(csak_ezen_azonositokhoz_kell_terkep=set())
    print("═" * 60)
    print(f"NYERS OLDAL SZÖVEG (kategória: {TESZT_KATEGORIA}, első 8000 karakter):")
    print("═" * 60)
    print(szoveg[:8000])
    print("═" * 60)
    print(f"Teljes hossz: {len(szoveg)} karakter")


def esemenyek_kinyerese(szoveg):
    """
    A felfedezett, konzisztens minta alapján: a lista minden bejegyzése
    PONTOSAN 2 sorból áll - cím, majd "kezdés - befejezés" dátum-tartomány.
    A listát a "Közúti közlekedési változások" fejléc és a "Keresés" mező
    (a szűrőpanel eleje) között találjuk.
    """
    kezdo_jelzo = "Közúti közlekedési változások"
    zaro_jelzo = "Keresés"

    kezdo_idx = szoveg.find(kezdo_jelzo)
    if kezdo_idx == -1:
        return []
    kezdo_idx += len(kezdo_jelzo)

    zaro_idx = szoveg.find(zaro_jelzo, kezdo_idx)
    lista_resz = szoveg[kezdo_idx:zaro_idx if zaro_idx > -1 else None]

    if "Nincs találat a keresési feltételekre" in lista_resz:
        return []

    sorok = [s.strip() for s in lista_resz.split("\n") if s.strip()]
    sorok = [s for s in sorok if s != "Szűrők törlése"]

    esemenyek = []
    i = 0
    while i < len(sorok) - 1:
        cim = sorok[i]
        datum_sor = sorok[i + 1]

        if " - " in datum_sor:
            kezdes, befejezes = datum_sor.split(" - ", 1)
        else:
            kezdes, befejezes = datum_sor, ""

        azonosito = hashlib.md5(f"{cim}|{kezdes}".encode("utf-8")).hexdigest()[:12]
        esemenyek.append({
            "id": azonosito,
            "cim": cim,
            "kezdes": kezdes.strip(),
            "befejezes": befejezes.strip(),
        })
        i += 2

    return esemenyek


def allapot_betoltes():
    if os.path.exists(ALLAPOT_FAJL):
        try:
            with open(ALLAPOT_FAJL, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def allapot_mentes(allapot):
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=2)


def heartbeat_iras(statusz, reszletek=""):
    try:
        with open(HEARTBEAT_FAJL, "w", encoding="utf-8") as f:
            f.write(f"utolso_futas: {most().strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
            f.write(f"statusz: {statusz}\n")
            if reszletek:
                f.write(f"reszletek: {reszletek}\n")
    except Exception as e:
        logging.error(f"Heartbeat fájl írása sikertelen: {e}")


def email_kuldes_egyszeru(targy, szoveg):
    """Sima szöveges e-mail, melléklet nélkül - hiba-értesítésekhez."""
    if not (EMAIL_KULDO and EMAIL_JELSZO and EMAIL_CIMZETT):
        print("⚠️ Hiányzó e-mail környezeti változók - kihagyva.")
        logging.warning("E-mail küldés kihagyva: hiányzó környezeti változók.")
        return
    try:
        msg = MIMEText(szoveg, "plain", "utf-8")
        msg["Subject"] = targy
        msg["From"] = EMAIL_KULDO
        msg["To"] = EMAIL_CIMZETT
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_KULDO, EMAIL_JELSZO)
            server.sendmail(EMAIL_KULDO, [EMAIL_CIMZETT], msg.as_string())
        print(f"📧 E-mail elküldve: {targy}")
    except Exception as ex:
        logging.error(f"E-mail küldési hiba: {ex}")
        print(f"❌ E-mail hiba: {ex}")


def esemeny_email_kuldes(uj_esemenyek, terkepek):
    """Az új eseményekről szóló e-mail. A térkép most a LEVÉL SZÖVEGÉBE van
    beágyazva (nem letöltendő melléklet), plusz - ha sikerült elcsípni a
    GPS-koordinátát - egy Google Maps-linkkel is kiegészítve."""
    if not (EMAIL_KULDO and EMAIL_JELSZO and EMAIL_CIMZETT):
        print("⚠️ Hiányzó e-mail környezeti változók - kihagyva.")
        logging.warning("E-mail küldés kihagyva: hiányzó környezeti változók.")
        return

    ido = most().strftime("%Y-%m-%d %H:%M:%S")
    targy = f"🚧 BKK KÖZÚTi (bal)eset - {len(uj_esemenyek)} új esemény | {ido}"

    szoveg_sorok = [f"BKK közúti baleset-figyelő - {ido} (budapesti idő)", ""]
    html_reszek = [
        f'<div style="font-family: Arial, sans-serif; font-size: 14px; color: #1f2d2b;">',
        f'<p><strong>BKK közúti baleset-figyelő</strong> - {ido} (budapesti idő)</p>',
    ]

    for idx, e in enumerate(uj_esemenyek):
        adat = terkepek.get(e["id"])
        cid = f"terkep{idx}"

        szoveg_sorok.append(f"• {e['cim']}")
        szoveg_sorok.append(f"   Kezdete: {e['kezdes']}")
        if e["befejezes"]:
            szoveg_sorok.append(f"   Vége: {e['befejezes']}")

        html_reszek.append('<hr style="border:none;border-top:1px solid #e4e9e7;margin:16px 0;">')
        html_reszek.append(f'<p style="font-weight:700;margin:0 0 4px;">{e["cim"]}</p>')
        html_reszek.append(f'<p style="margin:0 0 4px;color:#55605e;">Kezdete: {e["kezdes"]}</p>')
        if e["befejezes"]:
            html_reszek.append(f'<p style="margin:0 0 8px;color:#55605e;">Vége: {e["befejezes"]}</p>')

        if adat:
            html_reszek.append(f'<img src="cid:{cid}" alt="Térkép" style="max-width:100%;border-radius:8px;border:1px solid #dfe6e4;margin-top:6px;">')
            if adat.get("koordinata"):
                lat, lng = adat["koordinata"]
                maps_url = f"https://www.google.com/maps?q={lat},{lng}"
                szoveg_sorok.append(f"   Térkép: {maps_url}")
                html_reszek.append(f'<p style="margin:6px 0 0;"><a href="{maps_url}">Megnyitás Google Maps-ben ({lat:.5f}, {lng:.5f})</a></p>')

        szoveg_sorok.append("")

    html_reszek.append("</div>")
    szoveg = "\n".join(szoveg_sorok)
    html_szoveg = "\n".join(html_reszek)

    try:
        msg = MIMEMultipart("related")
        msg["Subject"] = targy
        msg["From"] = EMAIL_KULDO
        msg["To"] = EMAIL_CIMZETT

        alternativ = MIMEMultipart("alternative")
        alternativ.attach(MIMEText(szoveg, "plain", "utf-8"))
        alternativ.attach(MIMEText(html_szoveg, "html", "utf-8"))
        msg.attach(alternativ)

        for idx, e in enumerate(uj_esemenyek):
            adat = terkepek.get(e["id"])
            if not adat:
                continue
            kep = MIMEImage(adat["png"], _subtype="png")
            kep.add_header("Content-ID", f"<terkep{idx}>")
            kep.add_header("Content-Disposition", "inline", filename=f"terkep_{idx + 1}.png")
            msg.attach(kep)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_KULDO, EMAIL_JELSZO)
            server.sendmail(EMAIL_KULDO, [EMAIL_CIMZETT], msg.as_string())

        db_koordinataval = sum(1 for a in terkepek.values() if a.get("koordinata"))
        print(f"📧 E-mail elküldve: {len(uj_esemenyek)} új esemény ({len(terkepek)} térképpel, {db_koordinataval} GPS-koordinátával)")
    except Exception as ex:
        logging.error(f"E-mail küldési hiba: {ex}")
        print(f"❌ E-mail hiba: {ex}")


def hiba_email_kuldes(hiba):
    ido = most().strftime("%Y-%m-%d %H:%M:%S")
    targy = f"❌ BKK közúti monitor HIBA - {ido}"
    szoveg = (
        f"A BKK közúti baleset-figyelő szkript hibával leállt: {ido} (budapesti idő)\n\n"
        f"Hiba:\n{hiba}\n\n"
        f"Részletes traceback a(z) {LOG_FAJL} fájlban.\n\n"
        "Ha ez a levél nem érkezik meg legközelebb ismét, az azt jelentheti, hogy "
        "maga az ütemezés (cron / Feladatütemező / stb.) állt le - azt érdemes "
        "kívülről is ellenőrizni."
    )
    email_kuldes_egyszeru(targy, szoveg)


def main():
    if TESZT_MOD:
        teszt_futtatas()
        return

    allapot = allapot_betoltes()

    # Első körben csak a szöveget nézzük meg (térkép-screenshot nélkül),
    # hogy tudjuk, mely eseményEK ÚJAK - csak azokhoz kell térkép, a már
    # ismertekhez nem érdemes újra kattintgatni/screenshotolni.
    elozetes_szoveg, _ = oldal_feldolgozasa(csak_ezen_azonositokhoz_kell_terkep=set())
    elozetes_esemenyek = esemenyek_kinyerese(elozetes_szoveg)
    uj_azonositok = {e["id"] for e in elozetes_esemenyek if e["id"] not in allapot}

    if not uj_azonositok:
        print("✅ Nincs új esemény.")
        return

    # Második körben (ugyanazzal a logikával, de most már tudjuk, mely
    # ID-khez kell térkép) újra betöltjük az oldalt, és a térképeket is
    # elkészítjük az új eseményekhez.
    szoveg, terkepek = oldal_feldolgozasa(csak_ezen_azonositokhoz_kell_terkep=uj_azonositok)
    esemenyek = esemenyek_kinyerese(szoveg)
    print(f"📊 Talált baleset-bejegyzések: {len(esemenyek)}")

    uj_esemenyek = []
    for e in esemenyek:
        if e["id"] not in allapot:
            uj_esemenyek.append(e)
            allapot[e["id"]] = {
                "cim": e["cim"],
                "kezdes": e["kezdes"],
                "befejezes": e["befejezes"],
                "eloszor_latva": most().isoformat(),
                "volt_terkep": e["id"] in terkepek,
            }

    if uj_esemenyek:
        print(f"🆕 Új esemény: {len(uj_esemenyek)} (ebből {len(terkepek)} db-hoz sikerült térkép)")
        esemeny_email_kuldes(uj_esemenyek, terkepek)
    else:
        print("✅ Nincs új esemény.")

    allapot_mentes(allapot)


if __name__ == "__main__":
    try:
        main()
        heartbeat_iras("OK")
    except Exception as e:
        hiba_uzenet = f"{type(e).__name__}: {e}"
        logging.error(f"Végzetes hiba a futás során: {hiba_uzenet}\n{traceback.format_exc()}")
        print(f"❌ VÉGZETES HIBA: {hiba_uzenet}")
        heartbeat_iras("HIBA", hiba_uzenet)
        hiba_email_kuldes(hiba_uzenet)
        raise
