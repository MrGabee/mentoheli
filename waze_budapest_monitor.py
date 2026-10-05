"""
🚧 WAZE BUDAPEST + PEST MEGYE FIGYELŐ - PLAYWRIGHT, "LEHALLGATÓS" VÁLTOZAT
Forrás: a Waze Live Map (https://www.waze.com/live-map) saját georss hívásai.

MIÉRT ÍGY?
A georss végpont reCAPTCHA tokent kér (x-recaptcha-token fejléc), ezért
nem mi kérdezünk le közvetlenül: megnyitjuk a live-mapet egy valódi
Chromiumban, és a térkép SAJÁT georss kérését (a saját friss tokenjével)
a Playwright route-jával egy budapesti csempére irányítjuk át. A többi
csempét ugyanazzal a tokennel, a böngészőn belülről kérjük le, és ha a
Waze ezt elutasítja, az oldal újratöltésével kérünk új tokent.
(Egy georss válasz max. ~200 riasztás, ezért Budapest 6 csempe minden
körben (2x3), Pest megye 4x4 csempéje körbeforgatva, körönként 2.)

PERCENKÉNTI FIGYELÉS:
A böngésző nyitva marad, és KOR_MP másodpercenként (alap: 60) újra lekérjük
az adatokat, FUTASIDO_PERC percig (a GitHub job max. 6 órás, ezért ~5,75 óra
után kilép, és a következő ütemezett futás folytatja). FUTASIDO_PERC=0
esetén egyetlen kört fut.

FONTOS:
  - nem hivatalos, dokumentálatlan végpont; a Waze ÁSZF tiltja az
    automatizált lekérdezést. Csak saját használatra.
  - a Waze bármikor változtathat rajta, ilyenkor ez is elromlik.
  - a GitHub adatközponti IP-jéről a reCAPTCHA gyakran elutasít (HTTP 403),
    ezért a workflow Cloudflare WARP proxyn keresztül fut.

KIMENETEK:
  - waze_budapest_aktiv.json   - a legutóbbi kör összes riasztása + dugója
  - waze_budapest_allapot.json - látott riasztás-azonosítók (az utolsó észlelés után 3 napig);
                                 egy riasztásról csak egyszer megy e-mail
  - waze_naplo/YYYY-MM.jsonl   - minden újonnan látott riasztás, soronként
  - HTML e-mail az új riasztásokról (EMAIL_TIPUSOK szerint szűrve)

KÖRNYEZETI VÁLTOZÓK:
  EMAIL_KULDO, EMAIL_JELSZO, EMAIL_CIMZETT_WAZE - Gmail küldéshez
  EMAIL_TIPUSOK - vesszővel elválasztott Waze típusok, amikről e-mail megy
                  (alap: ACCIDENT,ROAD_CLOSED,HAZARD,POLICE; üres = mind)
  TESZT_MOD=1   - az első sikeres körig fut; nem ment semmit (EMAIL_TESZT=1 esetén
                  amíg minden csempéről van adat)
  EMAIL_TESZT=1 - TESZT_MOD mellett minta e-mailt küld a talált riasztásokból
  FUTASIDO_PERC - meddig fusson percenként (0 = egy kör)
  KOR_MP        - két kör között eltelt idő másodpercben (alap: 60)
  GIT_MENTES_PERC - ennyi percenként commitolja/pusholja az állapotot (0 = soha)
  FEJLES=1      - látható (nem headless) böngésző; xvfb-run alatt ajánlott
  PROXY_SZERVER - pl. socks5://127.0.0.1:40000 (Cloudflare WARP proxy mód)
"""

import os
import json
import time
import html
import hashlib
import random
import smtplib
import subprocess
import traceback
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from playwright.sync_api import sync_playwright

try:
    from zoneinfo import ZoneInfo
    _BUDAPESTI_ZONA = ZoneInfo("Europe/Budapest")
except Exception:
    _BUDAPESTI_ZONA = None

# --- Figyelt terület (lon/lat) ---
# BBOX: Budapest + Pest megye befoglaló téglalapja (a szomszédos megyék
# széleiből is belelóg egy kevés). BBOX_BP: Budapest + közvetlen agglomeráció,
# ahol a sűrű bejelentések miatt kisebb csempék kellenek.
BBOX = {"left": 18.65, "bottom": 46.92, "right": 20.15, "top": 47.86}
BBOX_BP = {"left": 18.90, "bottom": 47.35, "right": 19.35, "top": 47.60}
KOZEP = (47.4979, 19.0402)

# A ul?ll=... link átirányít a live-mapre, a megadott pontra középre igazítva.
WAZE_INDITO_URL = f"https://www.waze.com/ul?ll={KOZEP[0]}%2C{KOZEP[1]}&navigate=no&zoom=12"
GEORSS_RESZ = "/live-map/api/georss"

ALLAPOT_FAJL = "waze_budapest_allapot.json"
AKTIV_FAJL = "waze_budapest_aktiv.json"
NAPLO_MAPPA = "waze_naplo"
LOG_FAJL = "waze_budapest_monitor.log"
ALLAPOT_MEGORZES = timedelta(days=3)
# Ha a mentett állapot ennél régebbi, az első kör csak feltölti (nem e-mailez),
# különben egy hosszabb kiesés után több száz "új" riasztás menne ki.
ALLAPOT_FRISS = timedelta(minutes=30)

EMAIL_KULDO = os.environ.get("EMAIL_KULDO", "")
EMAIL_JELSZO = os.environ.get("EMAIL_JELSZO", "")
EMAIL_CIMZETT = os.environ.get("EMAIL_CIMZETT_WAZE", "")
EMAIL_TIPUSOK = [
    t.strip()
    for t in os.environ.get("EMAIL_TIPUSOK", "ACCIDENT,ROAD_CLOSED,HAZARD,POLICE").split(",")
    if t.strip()
]

TESZT_MOD = os.environ.get("TESZT_MOD", "0") == "1"
EMAIL_TESZT = os.environ.get("EMAIL_TESZT", "0") == "1"
FEJLES = os.environ.get("FEJLES", "0") == "1"
PROXY_SZERVER = os.environ.get("PROXY_SZERVER", "")
# Valódi Google Chrome (a GitHub runneren telepítve van); ha nincs, a Playwright
# saját Chromiuma. A reCAPTCHA a "Chrome for Testing"-et gyanúsabbnak láthatja.
CHROME_CSATORNA = os.environ.get("CHROME_CSATORNA", "chrome")
FUTASIDO_PERC = float(os.environ.get("FUTASIDO_PERC", "0"))
KOR_MP = int(os.environ.get("KOR_MP", "60"))
GIT_MENTES_PERC = float(os.environ.get("GIT_MENTES_PERC", "0"))
KOR_IDOKORLAT_MP = 55          # egy kör legfeljebb ennyi ideig próbálkozik
MAX_UJRATOLTES = 3             # körönként ennyi oldal-újratöltés
UJRAINDITAS_HIBA_UTAN = 3      # ennyi sikertelen kör után új böngésző

logging.basicConfig(
    filename=LOG_FAJL,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def most():
    utc = datetime.now(timezone.utc)
    return utc.astimezone(_BUDAPESTI_ZONA) if _BUDAPESTI_ZONA else utc


# ------------------------------------------------------------------
# Csempék, URL-átírás
# ------------------------------------------------------------------
def _csempek(terulet, sorok, oszlopok):
    dlat = (terulet["top"] - terulet["bottom"]) / sorok
    dlon = (terulet["right"] - terulet["left"]) / oszlopok
    return [
        {
            "bottom": round(terulet["bottom"] + i * dlat, 5),
            "top": round(terulet["bottom"] + (i + 1) * dlat, 5),
            "left": round(terulet["left"] + j * dlon, 5),
            "right": round(terulet["left"] + (j + 1) * dlon, 5),
        }
        for i in range(sorok)
        for j in range(oszlopok)
    ]


# Több, kisebb csempe = kisebb esély a 200-as plafonra, de több kérés is
# (a Waze 429-cel lassít). Budapest 6 csempéjét minden körben lekérjük; a
# megye 16 (ritkább) csempéjéből körönként MEGYE_KORONKENT darabot,
# körbeforgatva (így ~8 percenként frissül mind).
BP_CSEMPEK = _csempek(BBOX_BP, 2, 3)
MEGYE_CSEMPEK = _csempek(BBOX, 4, 4)
CSEMPEK = BP_CSEMPEK + MEGYE_CSEMPEK
MEGYE_KORONKENT = 2


def _georss_atiras(url, csempe):
    """A georss kérés bbox-át a megadott csempére cseréli, és biztosítja,
    hogy riasztásokat és dugókat is kérjen."""
    resz = urlparse(url)
    parameterek = {k: v[-1] for k, v in parse_qs(resz.query).items()}
    parameterek.update({k: str(v) for k, v in csempe.items()})
    parameterek["types"] = "alerts,traffic"
    parameterek.setdefault("env", "row")
    return urlunparse(resz._replace(query=urlencode(parameterek, safe=",")))


# ------------------------------------------------------------------
# Böngésző-munkamenet: nyitva marad, körönként frissít
# ------------------------------------------------------------------
class WazeMunkamenet:
    def __init__(self):
        self._pw = None
        self.browser = None
        self.page = None
        self.betoltve = False
        self.token_fejlecek = {}
        self.utolso = {}       # csempe index -> utolsó sikeres válasz (a megyéhez)
        self.megye_mutato = 0
        self._uj_kor([])

    def _uj_kor(self, korcsempek):
        self.korcsempek = korcsempek  # ebben a körben lekérendő csempék indexei
        self.valaszok = {}     # csempe index -> georss JSON
        self.statuszok = []
        self.kiosztas = {}     # átírt URL -> csempe index
        self.fuggo = []        # kiadott csempék, kérés-sorrendben
        self.kovetkezo = 0

    def indit(self):
        self._pw = sync_playwright().start()
        inditas = dict(
            headless=not FEJLES,
            args=["--disable-blink-features=AutomationControlled"],
            proxy={"server": PROXY_SZERVER} if PROXY_SZERVER else None,
        )
        try:
            self.browser = self._pw.chromium.launch(channel=CHROME_CSATORNA or None, **inditas)
        except Exception as e:
            print(f"ℹ️ '{CHROME_CSATORNA}' nem indult ({type(e).__name__}), beépített Chromium.")
            self.browser = self._pw.chromium.launch(**inditas)
        print(f"🧭 Böngésző: {self.browser.browser_type.name} {self.browser.version}")
        # Saját user-agentet szándékosan nem adunk meg: ha eltér a valódi
        # verziótól (a Client Hints-ben is látszik), az robotgyanús.
        context = self.browser.new_context(
            viewport={"width": 1600, "height": 1000},
            locale="hu-HU",
            timezone_id="Europe/Budapest",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self.page = context.new_page()
        self.page.route(f"**{GEORSS_RESZ}*", self._utvonal)
        self.page.on("response", self._valasz)
        self.betoltve = False

    def bezar(self):
        for lepes in (lambda: self.browser.close(), lambda: self._pw.stop()):
            try:
                lepes()
            except Exception:
                pass
        self.browser = self._pw = self.page = None

    def _utvonal(self, route):
        fejlecek = route.request.headers
        if fejlecek.get("x-recaptcha-token"):
            self.token_fejlecek = {k: v for k, v in fejlecek.items() if k.startswith("x-")}
        hianyzo = [i for i in self.korcsempek if i not in self.valaszok]
        if not hianyzo:
            route.continue_()
            return
        index = hianyzo[self.kovetkezo % len(hianyzo)]
        self.kovetkezo += 1
        uj_url = _georss_atiras(route.request.url, CSEMPEK[index])
        self.kiosztas[uj_url] = index
        self.fuggo.append(index)
        route.continue_(url=uj_url)

    def _valasz(self, resp):
        if GEORSS_RESZ not in resp.url:
            return
        self.statuszok.append(resp.status)
        # Ha a válasz URL-je az eredeti (nem átírt) kérésé, a kiadás
        # sorrendje alapján párosítjuk a csempével.
        index = self.kiosztas.get(resp.url)
        if index is not None and index in self.fuggo:
            self.fuggo.remove(index)
        elif self.fuggo:
            index = self.fuggo.pop(0)
        if resp.status == 200 and index is not None:
            try:
                self.valaszok[index] = resp.json()
            except Exception as e:
                logging.warning(f"Nem JSON georss válasz: {e}")

    def _egermozgas(self):
        """Apró, emberi egérmozgás - a reCAPTCHA v3 a viselkedést is pontozza."""
        try:
            self.page.mouse.move(random.randint(200, 1400), random.randint(150, 850),
                                 steps=random.randint(5, 15))
        except Exception:
            pass

    def _varj(self, feltetel, meddig):
        while not feltetel() and time.monotonic() < meddig:
            self._egermozgas()
            self.page.wait_for_timeout(random.randint(400, 900))

    def kor(self):
        """Egy lekérési kör. Visszaadja (e kör sikeres válaszai, az összes csempe
        legutóbbi ismert válasza) párost."""
        megye = [len(BP_CSEMPEK) + (self.megye_mutato + k) % len(MEGYE_CSEMPEK)
                 for k in range(MEGYE_KORONKENT)]
        self._uj_kor(list(range(len(BP_CSEMPEK))) + megye)
        hatarido = time.monotonic() + KOR_IDOKORLAT_MP

        # 1) Ha van még tokenünk, először azzal próbálkozunk (újratöltés
        #    nélkül), különben betöltjük / újratöltjük a térképet.
        if self.betoltve and self.token_fejlecek:
            self._csempek_tokennel(hatarido)
        if not self.valaszok:
            if self.betoltve:
                self.page.reload(wait_until="domcontentloaded", timeout=30000)
            else:
                self.page.goto(WAZE_INDITO_URL, wait_until="domcontentloaded", timeout=45000)
                self.betoltve = True
            self._varj(lambda: self.valaszok, min(time.monotonic() + 20, hatarido))

        # 2) A hiányzó csempék a böngészőn belülről, a térkép tokenjével.
        self._csempek_tokennel(hatarido)

        # 3) Ha a token nem újrahasznosítható, oldal-újratöltéssel kérünk újat.
        ujratoltes = 0
        while (len(self.valaszok) < len(self.korcsempek) and time.monotonic() < hatarido
               and ujratoltes < MAX_UJRATOLTES):
            ujratoltes += 1
            self.page.wait_for_timeout(10000 if 429 in self.statuszok[-3:] else 2000)
            elotte = len(self.valaszok)
            self.page.reload(wait_until="domcontentloaded", timeout=30000)
            self._varj(lambda: len(self.valaszok) > elotte, min(time.monotonic() + 15, hatarido))
        self.page.wait_for_timeout(500)
        # A megyei mutatót csak a sikeresen lekért megyei csempék után léptetjük.
        if all(i in self.valaszok for i in megye):
            self.megye_mutato = (self.megye_mutato + MEGYE_KORONKENT) % len(MEGYE_CSEMPEK)
        self.utolso.update(self.valaszok)
        return dict(self.valaszok), dict(self.utolso)

    def _csempek_tokennel(self, hatarido):
        hibas_sorozat = 0
        while (len(self.valaszok) < len(self.korcsempek) and time.monotonic() < hatarido
               and self.token_fejlecek and hibas_sorozat < 2):
            elotte = len(self.valaszok)
            try:
                self.page.evaluate(
                    """async ([url, fejlecek]) => {
                        const r = await fetch(url, { headers: fejlecek });
                        await r.text();
                    }""",
                    [f"https://www.waze.com{GEORSS_RESZ}?env=row&types=alerts,traffic",
                     dict(self.token_fejlecek)],
                )
            except Exception as e:
                logging.warning(f"Böngészőn belüli fetch hiba: {e}")
            if 429 in self.statuszok[-1:]:
                self.page.wait_for_timeout(8000)   # rate limit: kivárjuk
            else:
                self.page.wait_for_timeout(random.randint(2500, 4000))
            hibas_sorozat = 0 if len(self.valaszok) > elotte else hibas_sorozat + 1


# ------------------------------------------------------------------
# Feldolgozás
# ------------------------------------------------------------------
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
    """Az elkapott georss válaszokból egyedi riasztás- és dugólistát épít."""
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


def json_betoltes(fajl, alap):
    try:
        with open(fajl, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return alap


def json_mentes(fajl, adat):
    with open(fajl, "w", encoding="utf-8") as f:
        json.dump(adat, f, ensure_ascii=False, indent=2)


def allapot_betoltes():
    """{"mentve": iso, "latott": {id: iso}, "csempek": [feltöltött csempék]}
    - a régi (lapos) formátumot is kezeli."""
    nyers = json_betoltes(ALLAPOT_FAJL, {})
    if "latott" in nyers:
        return nyers.get("mentve"), nyers["latott"], set(nyers.get("csempek", []))
    return None, nyers, set()


def allapot_mentes(latott, csempek):
    json_mentes(ALLAPOT_FAJL, {"mentve": most().isoformat(timespec="seconds"),
                               "latott": latott, "csempek": sorted(csempek)})


def naplo_iras(uj_riasztasok):
    os.makedirs(NAPLO_MAPPA, exist_ok=True)
    fajl = os.path.join(NAPLO_MAPPA, f"{most().strftime('%Y-%m')}.jsonl")
    ido = most().isoformat(timespec="seconds")
    with open(fajl, "a", encoding="utf-8") as f:
        for r in uj_riasztasok:
            f.write(json.dumps({**r, "eloszor_latva": ido}, ensure_ascii=False) + "\n")


def git_mentes():
    """Futás közbeni commit + push (a workflow-ban a checkout tokenjével)."""
    parancs = (
        "git add waze_budapest_allapot.json waze_budapest_aktiv.json waze_naplo 2>/dev/null; "
        "git diff --staged --quiet && exit 0; "
        "git commit -q -m 'waze budapest állapot [skip ci]' && "
        "for i in 1 2 3; do git pull -q --rebase -X theirs origin main && git push -q origin HEAD:main && exit 0; sleep 3; done; exit 1"
    )
    try:
        r = subprocess.run(["bash", "-c", parancs], capture_output=True, text=True, timeout=120)
        print("💾 Állapot pusholva." if r.returncode == 0 else f"⚠️ Git mentés hiba: {r.stderr[-300:]}")
    except Exception as e:
        print(f"⚠️ Git mentés hiba: {e}")


# ------------------------------------------------------------------
# E-mail
# ------------------------------------------------------------------
TIPUS_NEVEK = {
    "ACCIDENT": ("💥", "Baleset", "#c62828"),
    "ROAD_CLOSED": ("⛔", "Útlezárás", "#6a1b9a"),
    "POLICE": ("🚓", "Rendőr", "#1565c0"),
    "HAZARD": ("⚠️", "Veszély", "#ef6c00"),
    "JAM": ("🚗", "Torlódás", "#5d4037"),
}
ALTIPUS_NEVEK = {
    "ACCIDENT_MAJOR": "Súlyos baleset",
    "ACCIDENT_MINOR": "Kisebb baleset",
    "POLICE_VISIBLE": "Látható rendőr",
    "POLICE_HIDING": "Rejtett rendőr",
    "HAZARD_ON_ROAD_POT_HOLE": "Kátyú",
    "HAZARD_ON_ROAD_OBJECT": "Tárgy az úton",
    "HAZARD_ON_ROAD_CAR_STOPPED": "Álló jármű az úton",
    "HAZARD_ON_SHOULDER_CAR_STOPPED": "Álló jármű a leállósávban",
    "HAZARD_ON_ROAD_CONSTRUCTION": "Útépítés",
    "HAZARD_ON_ROAD_TRAFFIC_LIGHT_FAULT": "Lámpahiba",
    "HAZARD_ON_ROAD_ROAD_KILL": "Elütött állat",
    "HAZARD_ON_SHOULDER_ANIMALS": "Állat az út szélén",
    "HAZARD_ON_ROAD_ICE": "Jeges út",
    "HAZARD_ON_ROAD_LANE_CLOSED": "Sávlezárás",
    "HAZARD_WEATHER_FOG": "Köd",
    "HAZARD_WEATHER_HAIL": "Jégeső",
    "HAZARD_WEATHER_FLOOD": "Elöntött út",
    "HAZARD_WEATHER_HEAVY_SNOW": "Erős havazás",
}
# A fontosabbak kerüljenek az e-mail tetejére.
TIPUS_SORREND = {"ACCIDENT": 0, "ROAD_CLOSED": 1, "POLICE": 2, "HAZARD": 3, "JAM": 4}


def _sorrend(r):
    return (TIPUS_SORREND.get(r["tipus"], 9), -(r["bejelentve_ms"] or 0))


def tipus_szoveg(r):
    ikon, nev, szin = TIPUS_NEVEK.get(r["tipus"], ("📍", r["tipus"], "#455a64"))
    reszlet = ALTIPUS_NEVEK.get(r["altipus"], "")
    return ikon, (f"{nev} – {reszlet}" if reszlet and reszlet != nev else nev), szin


def cim_szoveg(r):
    cim = ", ".join(x for x in (r["utca"], r["varos"]) if x)
    if not cim and r["szelesseg"] and r["hosszusag"]:
        cim = f"{r['szelesseg']:.5f}, {r['hosszusag']:.5f}"
    return cim or "Ismeretlen hely"


def terkep_linkek(r):
    lat, lon = r["szelesseg"], r["hosszusag"]
    if not (lat and lon):
        return None, None
    return (
        f"https://www.waze.com/ul?ll={lat}%2C{lon}&navigate=no&zoom=17",
        f"https://www.google.com/maps/search/?api=1&query={lat}%2C{lon}",
    )


def _gomb(url, felirat, szin):
    return (
        f'<a href="{html.escape(url)}" style="display:inline-block;padding:6px 12px;'
        f'border-radius:6px;background:{szin};color:#ffffff;text-decoration:none;'
        f'font-size:13px;font-weight:600;white-space:nowrap">{felirat}</a>'
    )


def email_html(riasztasok, cim):
    sorok = []
    for r in riasztasok:
        ikon, tipus, szin = tipus_szoveg(r)
        waze, google = terkep_linkek(r)
        leiras = f'<div style="color:#666;font-size:12px">{html.escape(r["leiras"])}</div>' if r["leiras"] else ""
        cella = 'style="padding:8px;border-bottom:1px solid #eee"'
        sorok.append(
            "<tr>"
            f'<td {cella}><span style="color:{szin};font-weight:700;white-space:nowrap">{ikon} {html.escape(tipus)}</span></td>'
            f"<td {cella}>{html.escape(cim_szoveg(r))}{leiras}</td>"
            f'<td {cella}>{_gomb(waze, "Waze", "#33ccff") if waze else ""}</td>'
            f'<td {cella}>{_gomb(google, "Google Maps", "#1a73e8") if google else ""}</td>'
            "</tr>"
        )
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222">'
        f'<h2 style="margin:0 0 4px">{html.escape(cim)}</h2>'
        f'<div style="color:#666;margin-bottom:12px">{most().strftime("%Y-%m-%d %H:%M")} (budapesti idő)</div>'
        '<table style="border-collapse:collapse;width:100%">'
        '<tr style="background:#f5f5f5;text-align:left">'
        '<th style="padding:8px">Értesítés típusa</th><th style="padding:8px">Cím</th>'
        '<th style="padding:8px">Waze</th><th style="padding:8px">Google Maps</th></tr>'
        + "".join(sorok)
        + "</table></div>"
    )


def email_szoveg(riasztasok, cim):
    sorok = [cim, ""]
    for r in riasztasok:
        _, tipus, _ = tipus_szoveg(r)
        waze, google = terkep_linkek(r)
        sorok.append(f"• {tipus} | {cim_szoveg(r)}")
        if waze:
            sorok.append(f"  Waze: {waze}")
            sorok.append(f"  Google Maps: {google}")
    return "\n".join(sorok)


def email_kuldes(targy, szoveg, html_torzs=None):
    if not (EMAIL_KULDO and EMAIL_JELSZO and EMAIL_CIMZETT):
        print("⚠️ Hiányzó e-mail környezeti változók - kihagyva.")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = targy
        msg["From"] = EMAIL_KULDO
        msg["To"] = EMAIL_CIMZETT
        msg.attach(MIMEText(szoveg, "plain", "utf-8"))
        if html_torzs:
            msg.attach(MIMEText(html_torzs, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_KULDO, EMAIL_JELSZO)
            server.sendmail(EMAIL_KULDO, [EMAIL_CIMZETT], msg.as_string())
        print(f"📧 E-mail elküldve: {targy}")
    except Exception as ex:
        logging.error(f"E-mail küldési hiba: {ex}")
        print(f"❌ E-mail hiba: {ex}")


def riasztas_email(riasztasok, teszt=False):
    riasztasok = sorted(riasztasok, key=_sorrend)
    if teszt:
        cim = f"🧪 Waze Budapest + Pest megye TESZT – {len(riasztasok)} esemény (minta)"
    else:
        cim = f"🚧 Waze Budapest + Pest megye – {len(riasztasok)} új esemény"
    email_kuldes(f"{cim} | {most().strftime('%H:%M')}", email_szoveg(riasztasok, cim), email_html(riasztasok, cim))


def teszt_minta(riasztasok, darab=25):
    """A teszt e-mailbe vegyes minta: típusonként legfeljebb 8, a fontosabbak elöl."""
    minta, tipusonkent = [], {}
    for r in sorted(riasztasok, key=_sorrend):
        if tipusonkent.get(r["tipus"], 0) < 8:
            minta.append(r)
            tipusonkent[r["tipus"]] = tipusonkent.get(r["tipus"], 0) + 1
        if len(minta) >= darab:
            break
    return minta


# ------------------------------------------------------------------
# Fő ciklus
# ------------------------------------------------------------------
def feldolgozas(riasztasok, dugok, latott, feltoltott, csendes=frozenset()):
    """csendes: azon riasztások azonosítói, amelyek csak most először lekért
    csempéről jöttek - ezeket megjegyezzük, de nem küldünk róluk e-mailt."""
    json_mentes(AKTIV_FAJL, {
        "frissitve": most().isoformat(timespec="seconds"),
        "riasztasok": riasztasok,
        "dugok": dugok,
    })
    uj = [r for r in riasztasok if r["id"] not in latott]
    # Minden most is látható riasztás "utoljára látva" idejét frissítjük, így
    # egy hetekig fennálló bejelentés (pl. kátyú) sem esik ki az állapotból,
    # és nem megy ki róla újra e-mail. Csak a 3 napja nem látottak törlődnek.
    ido = most().isoformat(timespec="seconds")
    for r in riasztasok:
        latott[r["id"]] = ido
    hatar = (most() - ALLAPOT_MEGORZES).isoformat(timespec="seconds")
    for k in [k for k, v in latott.items() if v < hatar]:
        del latott[k]
    allapot_mentes(latott, feltoltott)
    if uj:
        naplo_iras(uj)
    uj_emailre = [r for r in uj if r["id"] not in csendes]
    print(f"  🆕 Új riasztás: {len(uj)}" + (f" (ebből {len(uj) - len(uj_emailre)} először lekért csempéről: csak feltöltés)" if len(uj_emailre) < len(uj) else ""))
    emailre = [r for r in uj_emailre if not EMAIL_TIPUSOK or r["tipus"] in EMAIL_TIPUSOK]
    if emailre:
        riasztas_email(emailre)


def main():
    print(f"🌐 Proxy: {PROXY_SZERVER or 'nincs (közvetlen)'} | kör: {KOR_MP} mp | futásidő: {FUTASIDO_PERC} perc")
    vege = time.monotonic() + FUTASIDO_PERC * 60
    mentve, latott, mentett_csempek = allapot_betoltes()
    friss = False
    if mentve:
        try:
            friss = most() - datetime.fromisoformat(mentve) < ALLAPOT_FRISS
        except Exception:
            pass
    # Egy csempe első sikeres lekérésekor a rajta lévő riasztásokat csak
    # megjegyezzük, e-mailt csak a később megjelenőkről küldünk (a csempék
    # körönként változó sikerrel jönnek, ezért ez csempénként megy). Friss
    # állapotnál az előző futásban már feltöltött csempék ismertek maradnak.
    feltoltott = set(mentett_csempek) if (latott and friss) else set()

    munkamenet = WazeMunkamenet()
    munkamenet.indit()
    sikertelen_sorozat = 0
    kor_szam = 0
    volt_adat = False
    utolso_git = time.monotonic()
    try:
        while True:
            kor_szam += 1
            kor_kezdet = time.monotonic()
            try:
                valaszok, osszes = munkamenet.kor()
            except Exception as e:
                logging.warning(f"Kör hiba: {e}\n{traceback.format_exc()}")
                print(f"⚠️ Kör hiba: {type(e).__name__}: {e}")
                valaszok, osszes = {}, {}
            print(f"[{most().strftime('%H:%M:%S')}] #{kor_szam} csempék: {len(valaszok)}/{len(munkamenet.korcsempek)} "
                  f"(ismert: {len(osszes)}/{len(CSEMPEK)}) | HTTP: {munkamenet.statuszok}")

            if valaszok:
                sikertelen_sorozat = 0
                for i, v in valaszok.items():
                    if len(v.get("alerts", []) or []) >= 200:
                        print(f"  ⚠️ A(z) {i}. csempe elérte a 200-as plafont.")
                riasztasok, dugok = osszefesules(osszes.values())
                tipusok = {}
                for r in riasztasok:
                    tipusok[r["tipus"]] = tipusok.get(r["tipus"], 0) + 1
                print(f"  📊 Riasztások: {len(riasztasok)} {tipusok} | dugók: {len(dugok)}")
                if TESZT_MOD:
                    # Tesztben az első sikeres kör elég (minta e-mailhez
                    # viszont megvárjuk, hogy minden csempéről legyen adat).
                    volt_adat = True
                    if not EMAIL_TESZT or len(osszes) == len(CSEMPEK):
                        if EMAIL_TESZT:
                            riasztas_email(teszt_minta(riasztasok), teszt=True)
                        return
                else:
                    elso_csempek = [valaszok[i] for i in valaszok if i not in feltoltott]
                    csendes = {r["id"] for r in osszefesules(elso_csempek)[0]} if elso_csempek else set()
                    feltoltott.update(valaszok)
                    feldolgozas(riasztasok, dugok, latott, feltoltott, csendes)
            else:
                sikertelen_sorozat += 1
                if sikertelen_sorozat >= UJRAINDITAS_HIBA_UTAN:
                    print("🔁 Több sikertelen kör - új böngésző indul.")
                    munkamenet.bezar()
                    time.sleep(20)
                    munkamenet = WazeMunkamenet()
                    munkamenet.indit()
                    sikertelen_sorozat = 0

            if GIT_MENTES_PERC and time.monotonic() - utolso_git >= GIT_MENTES_PERC * 60:
                git_mentes()
                utolso_git = time.monotonic()

            kovetkezo = kor_kezdet + KOR_MP
            if kovetkezo >= vege:
                break
            time.sleep(max(0, kovetkezo - time.monotonic()))
    finally:
        munkamenet.bezar()

    if TESZT_MOD and not volt_adat:
        raise RuntimeError("Tesztmódban egyetlen körben sem jött adat (valószínűleg reCAPTCHA 403).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        hiba = f"{type(e).__name__}: {e}"
        logging.error(f"Végzetes hiba: {hiba}\n{traceback.format_exc()}")
        print(f"❌ VÉGZETES HIBA: {hiba}")
        raise
