"""
🚧 BKK KÖZÚTI BALESET-FIGYELŐ (Playwright, valódi böngészővel)
Forrás: https://bkk.hu/bkk-info/#!t=kozut&e=3&d=today (baleset szűrővel előszűrve)

FONTOS: ez a script egy VALÓDI, headless Chrome böngészőt indít (Playwright),
ami kiállja a Cloudflare-védelmet, mert úgy viselkedik, mint egy igazi
felhasználó böngészője - nem hamisított kéréseket küld.

ELSŐ LÉPÉS: futtasd TESZT módban (lásd lent), hogy lássuk a nyers
kiolvasott szöveget - abból pontosítjuk a végleges feldolgozó logikát.

--- VÁLTOZÁSOK ---
1) Minden időbélyeg explicit "Europe/Budapest" időzónában készül, nem a
   szerver (gyakran UTC) rendszeridejében - ezért nem csúszik többé 1-2 órát.
2) Az oldalbetöltés több próbálkozást és exponenciális várakozást kap
   (Cloudflare / hálózati akadozás esetére).
3) Ha a futás bármilyen okból elhasal, egy KÜLÖN hiba-jelző e-mail megy ki
   Neked a hibaüzenettel - így akkor is tudsz róla, ha a szkript leáll.
4) Minden futás (siker vagy hiba) frissíti a "heartbeat" fájlt az utolsó
   futás időpontjával - ezt egy külső ütemező is tudja figyelni.
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
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # nagyon régi Python, gyakorlatilag nem várható
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

TESZT_KATEGORIA = os.environ.get("TESZT_KATEGORIA", "3")  # 3=Baleset, 8=Lezárás, 9=Sávlezárás
BKK_KOZUT_URL = f"https://bkk.hu/bkk-info/#!t=kozut&e={TESZT_KATEGORIA}&d=today"
ALLAPOT_FAJL = "bkk_kozut_allapot.json"
HEARTBEAT_FAJL = "bkk_kozut_utolso_futas.txt"
LOG_FAJL = "bkk_kozut_monitor.log"

EMAIL_KULDO   = os.environ.get("EMAIL_KULDO", "")
EMAIL_JELSZO  = os.environ.get("EMAIL_JELSZO", "")
EMAIL_CIMZETT = os.environ.get("EMAIL_CIMZETT_BKK", "")

TESZT_MOD = os.environ.get("TESZT_MOD", "0") == "1"

# --- Hány próbálkozás és mennyi várakozás az oldalbetöltésre ---
MAX_PROBALKOZAS = int(os.environ.get("MAX_PROBALKOZAS", "3"))
UJRAPROBALKOZAS_ALAP_VARAKOZAS_MP = 10  # másodperc, minden próbálkozásnál duplázódik

logging.basicConfig(
    filename=LOG_FAJL,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def _het_utolso_vasarnapja_utc(ev, honap):
    """Egy adott hónap utolsó vasárnapja, 01:00 UTC-kor - az EU óraátállítás
    hivatalos időpontja (ez a szabály minden EU-tagállamra, így Magyarországra
    is érvényes)."""
    utolso_nap = calendar.monthrange(ev, honap)[1]
    d = datetime(ev, honap, utolso_nap, tzinfo=timezone.utc)
    while d.weekday() != 6:  # hétfő=0 ... vasárnap=6
        d -= timedelta(days=1)
    return d.replace(hour=1, minute=0, second=0, microsecond=0)


def _eu_nyari_ido_van(utc_datetime):
    """True, ha az adott UTC időpontban EU nyári időszámítás (CEST, UTC+2)
    van érvényben, False ha téli (CET, UTC+1)."""
    ev = utc_datetime.year
    marc_atallas = _het_utolso_vasarnapja_utc(ev, 3)
    okt_atallas = _het_utolso_vasarnapja_utc(ev, 10)
    return marc_atallas <= utc_datetime < okt_atallas


def _budapesti_zona_biztonsagos():
    """ZoneInfo-t próbál használni; ha a rendszeren/csomagban nincs
    tz-adatbázis (pl. csupasz GitHub Actions runner, hiányzó 'tzdata'
    csomag), akkor None-t ad vissza, és a most() manuálisan számol tovább."""
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo("Europe/Budapest")
    except ZoneInfoNotFoundError:
        logging.warning(
            "ZoneInfo('Europe/Budapest') nem található (hiányzó tzdata) - "
            "manuális EU nyári/téli időszámítás fallback aktiválva."
        )
        return None


_BUDAPESTI_ZONA = _budapesti_zona_biztonsagos()


def most():
    """Aktuális idő, mindig budapesti (nyári/téli) idő szerint - akkor is,
    ha a rendszeren nincs telepítve tz-adatbázis."""
    utc_most = datetime.now(timezone.utc)

    if _BUDAPESTI_ZONA is not None:
        return utc_most.astimezone(_BUDAPESTI_ZONA)

    # Fallback: kézi EU DST-szabály, külső tzdata nélkül is helyes.
    eltolas = timedelta(hours=2) if _eu_nyari_ido_van(utc_most) else timedelta(hours=1)
    nev = "CEST" if eltolas == timedelta(hours=2) else "CET"
    return utc_most.astimezone(timezone(eltolas, name=nev))


def oldal_szoveg_lekerese():
    """Elindít egy valódi Chrome-ot, betölti a baleset-szűrt BKK közúti oldalt,
    és visszaadja a látható szöveget. Több próbálkozással, ha a betöltés
    elhasal (pl. Cloudflare-lassulás, hálózati hiba)."""
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
                page = context.new_page()

                print(f"🌐 Betöltés ({probalkozas}/{MAX_PROBALKOZAS}): {BKK_KOZUT_URL}")
                page.goto(BKK_KOZUT_URL, wait_until="load", timeout=30000)

                # Várunk, hogy a JS tényleg lefusson és a lista betöltődjön
                # (a "networkidle" nem megbízható itt, mert az oldal folyamatos
                # háttér-kéréseket küldhet, pl. térkép-csempéket - emiatt inkább
                # fix várakozással biztosítjuk, hogy a JS lefusson)
                page.wait_for_timeout(5000)

                teljes_szoveg = page.inner_text("body")
                browser.close()
                return teljes_szoveg

        except Exception as e:
            utolso_hiba = e
            logging.warning(f"Oldalbetöltés sikertelen ({probalkozas}/{MAX_PROBALKOZAS}): {e}")
            print(f"  ⚠️ Sikertelen próbálkozás ({probalkozas}/{MAX_PROBALKOZAS}): {e}")
            if probalkozas < MAX_PROBALKOZAS:
                varakozas = UJRAPROBALKOZAS_ALAP_VARAKOZAS_MP * (2 ** (probalkozas - 1))
                print(f"  ⏳ Várakozás {varakozas} másodpercet újrapróbálkozás előtt...")
                time.sleep(varakozas)

    # Ha minden próbálkozás elfogyott, feldobjuk a hibát - ezt a main()
    # elkapja és hiba-e-mailt küld róla.
    raise RuntimeError(f"Az oldal betöltése {MAX_PROBALKOZAS} próbálkozás után is sikertelen volt: {utolso_hiba}")


def teszt_futtatas():
    """Csak kiírja a nyers szöveget a logba, e-mail küldés nélkül -
    ebből pontosítjuk a feldolgozó logikát."""
    szoveg = oldal_szoveg_lekerese()
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
    """Minden futás után (siker vagy hiba) felülírja ezt a fájlt az aktuális
    budapesti idővel - egy külső ütemező ebből tudná megállapítani, ha
    régóta nem futott le a szkript."""
    try:
        with open(HEARTBEAT_FAJL, "w", encoding="utf-8") as f:
            f.write(f"utolso_futas: {most().strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
            f.write(f"statusz: {statusz}\n")
            if reszletek:
                f.write(f"reszletek: {reszletek}\n")
    except Exception as e:
        logging.error(f"Heartbeat fájl írása sikertelen: {e}")


def email_kuldes(targy, szoveg):
    """Általános e-mail küldő - eseményekhez és hibaértesítéshez is."""
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


def esemeny_email_kuldes(uj_esemenyek):
    ido = most().strftime("%Y-%m-%d %H:%M:%S")
    targy = f"🚧 BKK KÖZÚTi (bal)eset - {len(uj_esemenyek)} új esemény | {ido}"

    sorok = [f"BKK közúti baleset-figyelő - {ido} (budapesti idő)", ""]
    for e in uj_esemenyek:
        sorok.append(f"• {e['cim']}")
        sorok.append(f"   Kezdete: {e['kezdes']}")
        if e["befejezes"]:
            sorok.append(f"   Vége: {e['befejezes']}")
        sorok.append("")

    email_kuldes(targy, "\n".join(sorok))
    print(f"📧 E-mail elküldve: {len(uj_esemenyek)} új esemény")


def hiba_email_kuldes(hiba):
    """Ez megy ki, ha a szkript futása bármilyen okból elhasal - így akkor is
    tudsz róla, ha maga a monitor áll le, nem csak akkor, ha nincs új esemény."""
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
    email_kuldes(targy, szoveg)


def main():
    if TESZT_MOD:
        teszt_futtatas()
        return

    szoveg = oldal_szoveg_lekerese()
    esemenyek = esemenyek_kinyerese(szoveg)
    print(f"📊 Talált baleset-bejegyzések: {len(esemenyek)}")

    allapot = allapot_betoltes()
    uj_esemenyek = []

    for e in esemenyek:
        if e["id"] not in allapot:
            uj_esemenyek.append(e)
            allapot[e["id"]] = {
                "cim": e["cim"],
                "kezdes": e["kezdes"],
                "befejezes": e["befejezes"],
                "eloszor_latva": most().isoformat(),
            }

    if uj_esemenyek:
        print(f"🆕 Új esemény: {len(uj_esemenyek)}")
        esemeny_email_kuldes(uj_esemenyek)
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
        # Nem nyeljük el a kivételt: ha ezt egy ütemező hívja (cron,
        # Feladatütemező), a nem-nulla exit code önmagában is jelezné a
        # hibát a rendszernek. De mi ehelyett garantáltan elküldjük az
        # e-mailt is, mielőtt a kivétel tovaterjed.
        raise
