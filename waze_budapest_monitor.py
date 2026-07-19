"""
🚧 WAZE KÖZVETLEN FIGYELŐ - PLAYWRIGHT VÁLTOZAT (nem hivatalos GeoRSS végpont)
Forrás: https://www.waze.com/live-map/api/georss

ELŐZMÉNY: a sima requests-es hívás 403 Forbidden hibát adott, MÉG OTTHONI
IP-ről is - tehát nem IP-alapú blokkolás, hanem hiányzó böngésző-munkamenet/
-ujjlenyomat okozza. Ezért ez a verzió egy valódi (headless) Chrome-ot indít
Playwrighttal, megnyitja a Waze Live Map oldalt (így megkapja a szükséges
sütiket/munkamenetet), és MAGÁN AZ OLDALON BELÜL, a böngésző saját
JavaScript fetch()-ével hívja meg a georss végpontot - így a kérés
gyakorlatilag megkülönböztethetetlen egy valódi felhasználó kérésétől.

FONTOS - OLVASD EL, MIELŐTT ÉLESBE ÁLLÍTOD:
Ez továbbra is egy nem hivatalos, dokumentálatlan végpont:
  - a Waze ÁSZF technikailag tiltja az automatizált, engedély nélküli lekérdezést,
  - a végpont/védelem bármikor változhat, és ez a megoldás is elromolhat,
  - agresszív lekérdezési gyakoriság blokkot eredményezhet.
Tartsd alacsonyan a lekérdezési gyakoriságot, és számíts rá, hogy előbb-utóbb
újra hozzá kell majd nyúlni.

--- MI VAN BENNE ---
1) Playwright (headless Chromium) - megnyitja a live-map oldalt, onnan
   fetch()-eli a georss adatot, budapesti bounding box-szal.
2) Ugyanaz a robusztussági csomag, mint a többi monitornál:
   - retry + exponenciális várakozás hiba esetén,
   - budapesti időzóna (tzdata nélkül is működő fallback-kal),
   - hiba-jelző e-mail, ha a futás elhasal,
   - heartbeat fájl az utolsó futás állapotával.
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
from playwright.sync_api import sync_playwright
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

# --- Budapest bounding box (bal, alsó, jobb, felső - lon/lat) ---
# Kicsit bővebbre véve, hogy az agglomerációt is lefedje.
BBOX = {
    "left": 18.90,
    "bottom": 47.35,
    "right": 19.35,
    "top": 47.60,
}

WAZE_LIVE_MAP_URL = "https://www.waze.com/live-map/"
WAZE_GEORSS_URL = "https://www.waze.com/live-map/api/georss"

ALLAPOT_FAJL = "waze_direkt_allapot.json"
HEARTBEAT_FAJL = "waze_direkt_utolso_futas.txt"
LOG_FAJL = "waze_direkt_monitor.log"

EMAIL_KULDO   = os.environ.get("EMAIL_KULDO", "")
EMAIL_JELSZO  = os.environ.get("EMAIL_JELSZO", "")
EMAIL_CIMZETT = os.environ.get("EMAIL_CIMZETT_WAZE", "")

# Ha csak bizonyos alert-típusokra vagy kíváncsi (pl. csak baleset+rendőr),
# ide írd be a Waze belső típusneveit. Üresen hagyva mindent továbbenged.
# Gyakori típusok: ACCIDENT, POLICE, HAZARD, JAM, ROAD_CLOSED
SZURT_TIPUSOK = [t.strip() for t in os.environ.get("SZURT_TIPUSOK", "").split(",") if t.strip()]

TESZT_MOD = os.environ.get("TESZT_MOD", "0") == "1"

MAX_PROBALKOZAS = int(os.environ.get("MAX_PROBALKOZAS", "3"))
UJRAPROBALKOZAS_ALAP_VARAKOZAS_MP = 10

logging.basicConfig(
    filename=LOG_FAJL,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# ------------------------------------------------------------------
# Időzóna - ugyanaz a tzdata-független megoldás, mint a BKK monitornál
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
# Waze lekérdezés
# ------------------------------------------------------------------
# ------------------------------------------------------------------
# Waze lekérdezés - Playwrighttal, a böngészőn belülről
# ------------------------------------------------------------------
def waze_adat_lekerese():
    """Elindít egy valódi (headless) Chrome-ot, megnyitja a Waze Live Map
    oldalt (hogy megkapja a szükséges sütiket/munkamenetet), majd MAGÁN
    AZ OLDALON BELÜL, a böngésző saját fetch()-ével kéri le a georss
    adatot - ez a szükséges lépés ahhoz, hogy a kérés ne 403-mal térjen
    vissza (sima szerver-szerver kérésként igen, böngészőn belülről nem)."""
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

                print(f"🌐 Live Map betöltése ({probalkozas}/{MAX_PROBALKOZAS})...")
                page.goto(WAZE_LIVE_MAP_URL, wait_until="load", timeout=30000)
                page.wait_for_timeout(4000)  # süti/munkamenet-felállás ideje

                georss_url = (
                    f"{WAZE_GEORSS_URL}?top={BBOX['top']}&bottom={BBOX['bottom']}"
                    f"&left={BBOX['left']}&right={BBOX['right']}&env=row&types=alerts,traffic"
                )

                eredmeny = page.evaluate(
                    """async (url) => {
                        const resp = await fetch(url, { headers: { 'Accept': 'application/json' } });
                        const szoveg = await resp.text();
                        return { statusz: resp.status, szoveg: szoveg };
                    }""",
                    georss_url,
                )

                browser.close()

                if eredmeny["statusz"] != 200:
                    raise RuntimeError(
                        f"A böngészőn belüli fetch is hibát adott: HTTP {eredmeny['statusz']} - "
                        f"{eredmeny['szoveg'][:300]}"
                    )

                return json.loads(eredmeny["szoveg"])

        except Exception as e:
            utolso_hiba = e
            logging.warning(f"Waze lekérdezés sikertelen ({probalkozas}/{MAX_PROBALKOZAS}): {e}")
            print(f"  ⚠️ Sikertelen próbálkozás ({probalkozas}/{MAX_PROBALKOZAS}): {e}")
            if probalkozas < MAX_PROBALKOZAS:
                varakozas = UJRAPROBALKOZAS_ALAP_VARAKOZAS_MP * (2 ** (probalkozas - 1))
                print(f"  ⏳ Várakozás {varakozas} másodpercet...")
                time.sleep(varakozas)

    raise RuntimeError(f"A Waze végpont {MAX_PROBALKOZAS} próbálkozás után is elérhetetlen: {utolso_hiba}")


def esemenyek_kinyerese(nyers_json):
    """A Waze 'alerts' tömbjéből épít egyszerű, magyar mezőnevű eseménylistát.
    A nyers JSON szerkezete nem hivatalos, dokumentálatlan - ha a Waze
    megváltoztatja, ezt a függvényt kell majd hozzáigazítani."""
    alertek = nyers_json.get("alerts", [])
    esemenyek = []

    for a in alertek:
        tipus = a.get("type", "ISMERETLEN")
        altipus = a.get("subtype", "")

        if SZURT_TIPUSOK and tipus not in SZURT_TIPUSOK:
            continue

        alert_id = a.get("uuid") or a.get("id")
        if alert_id is None:
            # Ha nincs egyedi azonosító, generálunk egyet a tartalomból.
            alert_id = hashlib.md5(json.dumps(a, sort_keys=True).encode("utf-8")).hexdigest()[:12]

        esemenyek.append({
            "id": str(alert_id),
            "tipus": tipus,
            "altipus": altipus,
            "utca": a.get("street", ""),
            "varos": a.get("city", ""),
            "leiras": a.get("reportDescription", ""),
            "szelesseg": a.get("location", {}).get("y"),
            "hosszusag": a.get("location", {}).get("x"),
            "megbizhatosag": a.get("reliability"),
            "megerositesek": a.get("nThumbsUp", 0),
        })

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


def email_kuldes(targy, szoveg):
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
    targy = f"🚧 Waze - {len(uj_esemenyek)} új esemény | {ido}"

    sorok = [f"Waze közvetlen figyelő - {ido} (budapesti idő)", ""]
    for e in uj_esemenyek:
        cim_resz = f"{e['utca']}, {e['varos']}".strip(", ")
        sorok.append(f"• [{e['tipus']}{'/' + e['altipus'] if e['altipus'] else ''}] {cim_resz or 'ismeretlen hely'}")
        if e["leiras"]:
            sorok.append(f"   Leírás: {e['leiras']}")
        if e["szelesseg"] and e["hosszusag"]:
            sorok.append(f"   Térkép: https://www.waze.com/live-map/directions?ll={e['szelesseg']}%2C{e['hosszusag']}")
        sorok.append(f"   Megerősítések: {e['megerositesek']}")
        sorok.append("")

    email_kuldes(targy, "\n".join(sorok))
    print(f"📧 E-mail elküldve: {len(uj_esemenyek)} új esemény")


def hiba_email_kuldes(hiba):
    ido = most().strftime("%Y-%m-%d %H:%M:%S")
    targy = f"❌ Waze közvetlen monitor HIBA - {ido}"
    szoveg = (
        f"A Waze közvetlen figyelő szkript hibával leállt: {ido} (budapesti idő)\n\n"
        f"Hiba:\n{hiba}\n\n"
        f"Részletes traceback a(z) {LOG_FAJL} fájlban.\n\n"
        "Mivel ez egy nem hivatalos, dokumentálatlan Waze végpont, gyakori hibaok "
        "lehet az is, hogy a Waze megváltoztatta a végpontot vagy blokkolta az IP-t "
        "- ha a hiba tartósan visszatér, ezt érdemes elsőként megnézni."
    )
    email_kuldes(targy, szoveg)


def main():
    nyers = waze_adat_lekerese()

    if TESZT_MOD:
        print("═" * 60)
        print("NYERS JSON (TESZT_MOD=1) - ebből ellenőrizzük a mezőneveket:")
        print("═" * 60)
        print(json.dumps(nyers, ensure_ascii=False, indent=2)[:6000])
        print("═" * 60)
        print(
            "Ha a fenti szerkezet eltér attól, amit az esemenyek_kinyerese() "
            "függvény vár (type, subtype, street, city, reportDescription, "
            "location.x/y, reliability, nThumbsUp), azt a függvényt kell "
            "hozzáigazítani a valós mezőnevekhez."
        )
        return

    esemenyek = esemenyek_kinyerese(nyers)
    print(f"📊 Talált esemény (szűrés után): {len(esemenyek)}")

    allapot = allapot_betoltes()
    uj_esemenyek = []

    for e in esemenyek:
        if e["id"] not in allapot:
            uj_esemenyek.append(e)
            allapot[e["id"]] = {**e, "eloszor_latva": most().isoformat()}

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
        raise
