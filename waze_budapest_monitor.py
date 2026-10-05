"""
🚧 WAZE BUDAPEST FIGYELŐ - PLAYWRIGHT, "LEHALLGATÓS" VÁLTOZAT
Forrás: a Waze Live Map (https://www.waze.com/live-map) saját georss hívásai.

MIÉRT ÍGY?
A georss végpont ma már reCAPTCHA tokent kér (x-recaptcha-token fejléc).
A korábbi változat maga hívta a végpontot token nélkül, ezért hibára futott;
a külön tokenfrissítő workflow tokenje pedig percek alatt lejárt, mire a
monitor használta volna. Ez a változat ezért NEM maga kérdez le: megnyitja
a live-mapet egy valódi Chromiumban, és a térkép SAJÁT georss kérését
(a saját friss tokenjével együtt) a Playwright route-jával úgy módosítja,
hogy a teljes budapesti bounding boxra kérdezzen. A válaszokat elkapjuk,
összefésüljük, és ebből dolgozunk.

FONTOS:
  - nem hivatalos, dokumentálatlan végpont; a Waze ÁSZF tiltja az
    automatizált lekérdezést. Csak saját használatra, ritkán (10 percenként).
  - a Waze bármikor változtathat rajta, ilyenkor ez is elromlik.
  - a GitHub adatközponti IP-jéről a reCAPTCHA elutasíthat (HTTP 403);
    ilyenkor otthoni gépről (pl. Raspberry Pi) érdemes futtatni.

KIMENETEK:
  - waze_budapest_aktiv.json   - a legutóbbi futás összes riasztása + dugója
  - waze_budapest_allapot.json - már látott riasztás-azonosítók (3 napig)
  - waze_naplo/YYYY-MM.jsonl   - minden újonnan látott riasztás, soronként
  - e-mail az új riasztásokról (EMAIL_TIPUSOK szerint szűrve)

KÖRNYEZETI VÁLTOZÓK:
  EMAIL_KULDO, EMAIL_JELSZO, EMAIL_CIMZETT_WAZE - Gmail küldéshez
  EMAIL_TIPUSOK - vesszővel elválasztott Waze típusok, amikről e-mail megy
                  (alap: ACCIDENT,ROAD_CLOSED,HAZARD,POLICE; üres = mind)
  TESZT_MOD=1   - csak kiírja, mit talált; nem ment és nem küld e-mailt
  FEJLES=1      - látható (nem headless) böngésző; xvfb-run alatt ajánlott
"""

import os
import json
import time
import hashlib
import smtplib
import traceback
import logging
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from playwright.sync_api import sync_playwright

try:
    from zoneinfo import ZoneInfo
    _BUDAPESTI_ZONA = ZoneInfo("Europe/Budapest")
except Exception:
    _BUDAPESTI_ZONA = None

# --- Budapest + közvetlen agglomeráció (lon/lat) ---
BBOX = {"left": 18.90, "bottom": 47.35, "right": 19.35, "top": 47.60}
KOZEP = (47.4979, 19.0402)

# A ul?ll=... link átirányít a live-mapre, a megadott pontra középre igazítva.
WAZE_INDITO_URL = f"https://www.waze.com/ul?ll={KOZEP[0]}%2C{KOZEP[1]}&navigate=no&zoom=12"
GEORSS_RESZ = "/live-map/api/georss"

ALLAPOT_FAJL = "waze_budapest_allapot.json"
AKTIV_FAJL = "waze_budapest_aktiv.json"
NAPLO_MAPPA = "waze_naplo"
LOG_FAJL = "waze_budapest_monitor.log"
ALLAPOT_MEGORZES = timedelta(days=3)

EMAIL_KULDO = os.environ.get("EMAIL_KULDO", "")
EMAIL_JELSZO = os.environ.get("EMAIL_JELSZO", "")
EMAIL_CIMZETT = os.environ.get("EMAIL_CIMZETT_WAZE", "")
EMAIL_TIPUSOK = [
    t.strip()
    for t in os.environ.get("EMAIL_TIPUSOK", "ACCIDENT,ROAD_CLOSED,HAZARD,POLICE").split(",")
    if t.strip()
]

TESZT_MOD = os.environ.get("TESZT_MOD", "0") == "1"
FEJLES = os.environ.get("FEJLES", "0") == "1"
MAX_PROBALKOZAS = int(os.environ.get("MAX_PROBALKOZAS", "2"))
VARAKOZAS_MP = 20

logging.basicConfig(
    filename=LOG_FAJL,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def most():
    utc = datetime.now(timezone.utc)
    return utc.astimezone(_BUDAPESTI_ZONA) if _BUDAPESTI_ZONA else utc


# ------------------------------------------------------------------
# Waze lekérdezés - a térkép saját kéréseinek átírásával és elkapásával
# ------------------------------------------------------------------
def _georss_atiras(url):
    """A térkép georss kérésének bbox-át a teljes budapesti BBOX-ra cseréli,
    és biztosítja, hogy riasztásokat és dugókat is kérjen."""
    resz = urlparse(url)
    parameterek = {k: v[-1] for k, v in parse_qs(resz.query).items()}
    parameterek.update({k: str(v) for k, v in BBOX.items()})
    parameterek["types"] = "alerts,traffic"
    parameterek.setdefault("env", "row")
    return urlunparse(resz._replace(query=urlencode(parameterek, safe=",")))


def waze_adat_lekerese():
    utolso_hiba = None
    for probalkozas in range(1, MAX_PROBALKOZAS + 1):
        valaszok = []
        statuszok = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=not FEJLES,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    viewport={"width": 1600, "height": 1000},
                    locale="hu-HU",
                    timezone_id="Europe/Budapest",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
                    ),
                )
                context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )
                page = context.new_page()

                def utvonal(route):
                    route.continue_(url=_georss_atiras(route.request.url))

                def valasz(resp):
                    if GEORSS_RESZ not in resp.url:
                        return
                    statuszok.append(resp.status)
                    if resp.status == 200:
                        try:
                            valaszok.append(resp.json())
                        except Exception as e:
                            logging.warning(f"Nem JSON georss válasz: {e}")

                page.route(f"**{GEORSS_RESZ}*", utvonal)
                page.on("response", valasz)

                print(f"🌐 Live Map betöltése ({probalkozas}/{MAX_PROBALKOZAS})...")
                page.goto(WAZE_INDITO_URL, wait_until="domcontentloaded", timeout=45000)

                # Várunk, amíg a térkép legalább egyszer lekéri az adatokat.
                for _ in range(30):
                    if valaszok:
                        break
                    page.wait_for_timeout(1000)
                # Egy kis plusz idő, hátha jön még egy (frissebb) válasz.
                page.wait_for_timeout(3000)
                browser.close()

            print(f"  georss válaszok HTTP kódjai: {statuszok or 'egy sem érkezett'}")
            if valaszok:
                return valaszok
            raise RuntimeError(
                f"Nem jött sikeres georss válasz (HTTP kódok: {statuszok or 'nincs kérés'}). "
                "403 esetén valószínűleg a reCAPTCHA utasította el a kérést."
            )
        except Exception as e:
            utolso_hiba = e
            logging.warning(f"Waze lekérdezés sikertelen ({probalkozas}/{MAX_PROBALKOZAS}): {e}")
            print(f"  ⚠️ Sikertelen próbálkozás ({probalkozas}/{MAX_PROBALKOZAS}): {e}")
            if probalkozas < MAX_PROBALKOZAS:
                time.sleep(VARAKOZAS_MP)

    raise RuntimeError(f"A Waze adat {MAX_PROBALKOZAS} próbálkozás után sem jött meg: {utolso_hiba}")


def _azonosito(elem):
    azon = elem.get("uuid") or elem.get("id")
    if azon is None:
        azon = hashlib.md5(json.dumps(elem, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return str(azon)


def _bboxban(lat, lon):
    if lat is None or lon is None:
        return False
    return BBOX["bottom"] <= lat <= BBOX["top"] and BBOX["left"] <= lon <= BBOX["right"]


def osszefesules(valaszok):
    """Az összes elkapott georss válaszból egyedi riasztás- és dugólistát épít."""
    riasztasok, dugok = {}, {}
    for v in valaszok:
        for a in v.get("alerts", []) or []:
            hely = a.get("location", {}) or {}
            if not _bboxban(hely.get("y"), hely.get("x")):
                continue
            riasztasok[_azonosito(a)] = {
                "id": _azonosito(a),
                "tipus": a.get("type", "ISMERETLEN"),
                "altipus": a.get("subtype", ""),
                "utca": a.get("street", ""),
                "varos": a.get("city", ""),
                "leiras": a.get("reportDescription", ""),
                "szelesseg": hely.get("y"),
                "hosszusag": hely.get("x"),
                "megbizhatosag": a.get("reliability"),
                "megerositesek": a.get("nThumbsUp", 0),
                "bejelentve_ms": a.get("pubMillis"),
            }
        for j in v.get("jams", []) or []:
            dugok[_azonosito(j)] = {
                "id": _azonosito(j),
                "utca": j.get("street", ""),
                "varos": j.get("city", ""),
                "szint": j.get("level"),
                "hossz_m": j.get("length"),
                "keses_mp": j.get("delay"),
                "sebesseg_kmh": j.get("speedKMH"),
            }
    return list(riasztasok.values()), list(dugok.values())


# ------------------------------------------------------------------
# Állapot, napló, e-mail
# ------------------------------------------------------------------
def json_betoltes(fajl, alap):
    try:
        with open(fajl, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return alap


def json_mentes(fajl, adat):
    with open(fajl, "w", encoding="utf-8") as f:
        json.dump(adat, f, ensure_ascii=False, indent=2)


def naplo_iras(uj_riasztasok):
    os.makedirs(NAPLO_MAPPA, exist_ok=True)
    fajl = os.path.join(NAPLO_MAPPA, f"{most().strftime('%Y-%m')}.jsonl")
    ido = most().isoformat(timespec="seconds")
    with open(fajl, "a", encoding="utf-8") as f:
        for r in uj_riasztasok:
            f.write(json.dumps({**r, "eloszor_latva": ido}, ensure_ascii=False) + "\n")


def email_kuldes(targy, szoveg):
    if not (EMAIL_KULDO and EMAIL_JELSZO and EMAIL_CIMZETT):
        print("⚠️ Hiányzó e-mail környezeti változók - kihagyva.")
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


def riasztas_email(riasztasok):
    ido = most().strftime("%Y-%m-%d %H:%M")
    sorok = [f"Waze Budapest - {ido} (budapesti idő)", ""]
    for r in riasztasok:
        hely = f"{r['utca']}, {r['varos']}".strip(", ") or "ismeretlen hely"
        tipus = r["tipus"] + (f"/{r['altipus']}" if r["altipus"] else "")
        sorok.append(f"• [{tipus}] {hely}")
        if r["leiras"]:
            sorok.append(f"   Leírás: {r['leiras']}")
        if r["szelesseg"] and r["hosszusag"]:
            sorok.append(
                f"   Térkép: https://www.waze.com/ul?ll={r['szelesseg']}%2C{r['hosszusag']}&navigate=no&zoom=17"
            )
        sorok.append(f"   Megerősítések: {r['megerositesek']}")
        sorok.append("")
    email_kuldes(f"🚧 Waze - {len(riasztasok)} új esemény | {ido}", "\n".join(sorok))


def main():
    valaszok = waze_adat_lekerese()
    riasztasok, dugok = osszefesules(valaszok)
    tipusok = {}
    for r in riasztasok:
        tipusok[r["tipus"]] = tipusok.get(r["tipus"], 0) + 1
    print(f"📊 Riasztások: {len(riasztasok)} {tipusok} | dugók: {len(dugok)}")

    if TESZT_MOD:
        print("🧪 TESZT_MOD - semmit nem mentünk, e-mailt nem küldünk. Minta:")
        print(json.dumps(riasztasok[:5], ensure_ascii=False, indent=2))
        return

    json_mentes(AKTIV_FAJL, {
        "frissitve": most().isoformat(timespec="seconds"),
        "riasztasok": riasztasok,
        "dugok": dugok,
    })

    allapot = json_betoltes(ALLAPOT_FAJL, {})
    elso_futas = not allapot
    hatar = (most() - ALLAPOT_MEGORZES).isoformat(timespec="seconds")
    allapot = {k: v for k, v in allapot.items() if v >= hatar}

    uj = [r for r in riasztasok if r["id"] not in allapot]
    for r in uj:
        allapot[r["id"]] = most().isoformat(timespec="seconds")
    json_mentes(ALLAPOT_FAJL, allapot)

    if uj:
        naplo_iras(uj)
    print(f"🆕 Új riasztás: {len(uj)}")

    if elso_futas:
        print("ℹ️ Első futás: csak feltöltjük az állapotot, e-mail nem megy.")
        return
    emailre = [r for r in uj if not EMAIL_TIPUSOK or r["tipus"] in EMAIL_TIPUSOK]
    if emailre:
        riasztas_email(emailre)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        hiba = f"{type(e).__name__}: {e}"
        logging.error(f"Végzetes hiba: {hiba}\n{traceback.format_exc()}")
        print(f"❌ VÉGZETES HIBA: {hiba}")
        raise
