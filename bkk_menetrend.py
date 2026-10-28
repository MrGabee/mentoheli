"""
🚏 BKK menetrendi változások – Csepel és Pesterzsébet
Adatforrás: BKK OpenData GTFS-realtime Alerts (saját kulccsal: BKK_API_KEY titok)
Futtatás: GitHub Actions, félóránként

A BKK riasztásaiból (terelés, pótlóbusz, megállóáthelyezés, ideiglenes járat)
csak azokat tartja meg, amelyek csepeli vagy pesterzsébeti megállót érintenek.
Minden új változásról kártyás levél megy, alatta kész posztszöveggel; este
(a jó éjszakát előtt) emlékeztető a másnap induló változásokról.
Posztolni nem posztol, a szöveget én nézem át és osztom meg.
"""

import os
import re
import json
import smtplib
import hashlib
import requests
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import email_arculat as ea

MAGYAR_TZ = ZoneInfo("Europe/Budapest")
KULCS = os.environ.get("BKK_API_KEY", "")
ALAP = "https://futar.bkk.hu/api/query/v1/ws/otp/api/where"
ALERTS_URL = "https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/Alerts.pb"
HEADERS = {"User-Agent": "mentoheli-monitor/1.0 (github.com/MrGabee)"}
ALLAPOT_FAJL = "bkk_menetrend_allapot.json"
ELONEZET = os.environ.get("ELONEZET") == "1"

# Este ebben a sávban megy az emlékeztető a holnap induló változásokról (a 21:30-as jó éjszakát előtt)
ESTI_TOL, ESTI_IG = time(20, 0), time(21, 15)
# Ennyi megálló kell a területen, hogy egy járat „csepelinek” számítson (egy-egy átszállóhely kevés)
MIN_MEGALLO = 3

# GTFS-realtime hatás → (címke, szín)
HATAS = {
    1: ("Nem közlekedik / pótlóbusz", "piros"),
    2: ("Ritkább járatok", "sarga"),
    3: ("Jelentős késés", "sarga"),
    4: ("Terelés", "sarga"),
    5: ("Plusz járat", "kek"),
    6: ("Módosított menetrend", "sarga"),
    9: ("Megállóáthelyezés", "sarga"),
}

BEVEZETOK = [
    "A BKK tájékoztatása szerint változik a közlekedés nálunk:",
    "Szólok, mert érinti a csepeli és erzsébeti utasokat is – a BKK tájékoztatása szerint:",
    "Menetrendi változásról értesített a BKK, ami minket is érint:",
    "Ha mostanában errefelé utazol, erre figyelj – a BKK tájékoztatása szerint:",
    "Összeszedtem, mi változik a környékünkön a BKK tájékoztatása szerint:",
]

HONAPOK = ["január", "február", "március", "április", "május", "június", "július",
           "augusztus", "szeptember", "október", "november", "december"]


def most():
    return datetime.now(MAGYAR_TZ)


# ── terület ──────────────────────────────────────────────────────
def teruleten(lat, lon):
    """XXI. kerület (Csepel-sziget északi része, Szigetszentmiklós széléig) és XX. kerület (Pesterzsébet), durva határral.
    Nyugaton a Duna (19.05), északon a Határ út / Kvassay híd vonala, keleten Kispest/Soroksár."""
    if not (47.33 <= lat <= 47.455 and 19.05 <= lon <= 19.165):
        return False
    if lat < 47.405 and lon > 19.105:   # Soroksár
        return False
    if lat > 47.44 and lon > 19.13:     # Kispest déli széle (Wekerle, Győri Ottmár tér)
        return False
    return True


def _nyers(azon):
    """A FUTÁR "BKK_0300" azonosítója a GTFS-RT-ben "0300". Más szolgáltatóé (pl. volan_…)
    nem szerepel a BKK riasztásaiban, azt nem csonkolom, hogy ne ütközzön."""
    return azon[4:] if azon.startswith("BKK_") else azon


def futar(vegpont, **p):
    p.update(key=KULCS, version=3, appVersion="mrgabee-1.0")
    try:
        r = requests.get(f"{ALAP}/{vegpont}.json", params=p, headers=HEADERS, timeout=25)
        return r.json()
    except Exception as ex:
        print(f"⚠️ FUTÁR hiba ({vegpont}): {type(ex).__name__}")
        return {}


def terulet_adatai():
    """(megállók halmaza, járat → rövid név, járat → típus) a területen."""
    # A FUTÁR nagy területre nem ad választ, ezért három kisebb ablakból rakom össze
    stops, routes = {}, {}
    for lat, lon, dlat, dlon in ((47.425, 19.075, 0.075, 0.075), (47.425, 19.14, 0.06, 0.06),
                                 (47.36, 19.07, 0.06, 0.06)):
        d = futar("stops-for-location", lat=lat, lon=lon, latSpan=dlat, lonSpan=dlon)
        ref = (d.get("data") or {}).get("references") or {}
        if not ref:
            print(f"⚠️ Üres FUTÁR válasz ({lat}, {lon}): {str(d)[:200]}")
        stops.update(ref.get("stops") or {})
        routes.update(ref.get("routes") or {})
    jaratok = {_nyers(k): v for k, v in routes.items()}
    megallok, szamlalo = set(), {}
    for k, m in stops.items():
        if teruleten(m.get("lat", 0), m.get("lon", 0)):
            megallok.add(_nyers(k))
            for r in m.get("routeIds") or []:
                szamlalo[_nyers(r)] = szamlalo.get(_nyers(r), 0) + 1
    helyi = {r for r, db in szamlalo.items() if db >= MIN_MEGALLO}
    print(f"📍 Területen: {len(megallok)} megálló, {len(helyi)} járat")
    return megallok, helyi, jaratok


# ── riasztások ───────────────────────────────────────────────────
def _forditas(ts):
    for t in ts.translation:
        if t.language in ("hu", ""):
            return t.text
    return ts.translation[0].text if ts.translation else ""


def html_szoveg(h):
    """A BKK leírás HTML-jéből bekezdések listája."""
    h = re.sub(r"<li[^>]*>", "\n• ", h or "")
    h = re.sub(r"<br\s*/?>|</p>|</li>|</ul>", "\n", h)
    h = re.sub(r"<[^>]+>", "", h)
    from html import unescape
    sorok = [re.sub(r"\s+", " ", s).strip() for s in unescape(h).split("\n")]
    return [s for s in sorok if s and s != "•"]


def riasztasok():
    from google.transit import gtfs_realtime_pb2
    try:
        r = requests.get(ALERTS_URL, params={"key": KULCS}, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as ex:
        print(f"❌ Alerts lekérés hiba: {type(ex).__name__}")
        return None
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(r.content)
    ki = []
    for e in feed.entity:
        a = e.alert
        idok = [(p.start or None, p.end or None) for p in a.active_period]
        ki.append({
            "id": e.id,
            "hatas": int(a.effect),
            "routes": sorted({i.route_id for i in a.informed_entity if i.route_id}),
            "stops": sorted({i.stop_id for i in a.informed_entity if i.stop_id}),
            "kezdet": min((s for s, _ in idok if s), default=None),
            "veg": max((v for _, v in idok if v), default=None),
            "cim": _forditas(a.header_text).strip(),
            "leiras": html_szoveg(_forditas(a.description_text)),
            "url": _forditas(a.url),
        })
    print(f"📥 BKK riasztás összesen: {len(ki)}")
    return ki


def helyiek(lista, megallok, helyi_jaratok, jaratok):
    ki = []
    for r in lista:
        # Ha a riasztás megállókat is megnevez, azok döntenek (pl. egy kispesti megálló
        # áthelyezése nem csepeli hír, akkor sem, ha a járat erre is jár); ha nem, a járatok.
        if r["stops"]:
            if not set(r["stops"]) & megallok:
                continue
        elif not set(r["routes"]) & helyi_jaratok:
            continue
        r["vonalak"] = sorted({jaratok[x].get("shortName", x) for x in r["routes"] if x in jaratok},
                              key=lambda v: (len(re.sub(r"\D", "", v) or "999"), v))
        r["tipusok"] = {jaratok[x].get("shortName", x): jaratok[x].get("type") for x in r["routes"] if x in jaratok}
        ki.append(r)
    return sorted(ki, key=lambda r: r["kezdet"] or 0)


# ── szövegek ─────────────────────────────────────────────────────
def _nap(ts):
    d = datetime.fromtimestamp(ts, MAGYAR_TZ)
    return f"{HONAPOK[d.month - 1]} {d.day}."


def idoszak(r):
    k, v = r["kezdet"], r["veg"]
    if not k and not v:
        return ""
    if k and v:
        dk, dv = datetime.fromtimestamp(k, MAGYAR_TZ), datetime.fromtimestamp(v, MAGYAR_TZ)
        if dk.date() == dv.date():
            return f"{_nap(k)} {dk:%H:%M} – {dv:%H:%M}"
        if (dv - dk).days > 60:
            return f"{_nap(k)} – {_nap(v)} (hosszabb ideig)"
        return f"{_nap(k)} – {_nap(v)}"
    return f"{_nap(k)}-tól" if k else f"{_nap(v)}-ig"


def cim(r):
    c = r["cim"] or "menetrendi változás"
    return c[:1].upper() + c[1:]


def poszt_szoveg(r):
    vonalak = ", ".join(r["vonalak"])
    bev = BEVEZETOK[int(hashlib.md5(r["id"].encode()).hexdigest(), 16) % len(BEVEZETOK)]
    sorok = [f"🚏 MENETRENDI VÁLTOZÁS{' – ' + vonalak if vonalak else ''} 🚏", "", bev, ""]
    sorok += [s for s in r["leiras"] if not s.lower().startswith("megjegyzés")]
    ido = idoszak(r)
    if ido:
        sorok += ["", f"📅 {ido}"]
    sorok += ["", "Részletek a BKK oldalán.", "", "#Csepel #Pesterzsébet #BKK"]
    return "\n".join(sorok)


def kartya(r):
    cimke, szin = HATAS.get(r["hatas"], ("Változás", "sarga"))
    jelvenyek = "".join(ea.jarat_jelveny(v, r["tipusok"].get(v)) for v in r["vonalak"][:12])
    test = (ea.adat_tabla([("Időszak", idoszak(r))])
            + "".join(ea.bekezdes(s) for s in r["leiras"])
            + ea.gomb("BKK Info", r["url"])
            + '<div style="margin:14px 0 4px;font-size:12px;letter-spacing:1px;text-transform:uppercase;'
              'font-weight:bold;color:#6b7682">Posztszöveg</div>'
            + '<div style="white-space:pre-wrap;background:#f6f8fa;border:1px solid #e3e8ee;border-radius:6px;'
              f'padding:12px 14px;font-size:14px;line-height:1.5">{ea.esc(poszt_szoveg(r))}</div>')
    return ea.kartya(ea.SZIN[szin], cimke, cim(r), test, jelvenyek=jelvenyek,
                     cimke_szin=ea.SZIN["sarga_szoveg"] if szin == "sarga" else None)


def level(lista, fejlec=""):
    elo = (f'<div style="font-size:15px;color:#1b232c;margin:0 0 14px">{ea.esc(fejlec)}</div>' if fejlec else "")
    return ea.keret(elo + "".join(kartya(r) for r in lista), "BKK menetrendi változások · Csepel, Pesterzsébet")


def kuldes(targy, lista, fejlec=""):
    html = level(lista, fejlec)
    if ELONEZET:
        with open("bkk_menetrend_elonezet.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"(előnézet, nem küldöm) {targy}")
        return
    kuldo, jelszo = os.environ["EMAIL_KULDO"], os.environ["EMAIL_JELSZO"]
    cimzett = os.environ.get("EMAIL_CIMZETT_BKK") or os.environ["EMAIL_CIMZETT"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"] = f"🚏 BKK változások <{kuldo}>"
    msg["To"] = cimzett
    msg.attach(MIMEText("\n\n———\n\n".join(poszt_szoveg(r) for r in lista), "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(kuldo, jelszo)
        smtp.sendmail(kuldo, cimzett, msg.as_string())
    print(f"📧 Elküldve: {targy}")


def targy_egy(r):
    v = ", ".join(r["vonalak"][:5]) + (" …" if len(r["vonalak"]) > 5 else "")
    return f"🚏 BKK · {v + ': ' if v else ''}{cim(r)}"[:150]


# ── főprogram ────────────────────────────────────────────────────
def main():
    t = most()
    print(f"🚏 BKK menetrendi változások – {t:%Y.%m.%d %H:%M}")
    if not KULCS:
        print("⚠️ Nincs BKK_API_KEY titok – kihagyva.")
        return
    lista = riasztasok()
    if lista is None:
        return  # hiba esetén nem nyúlok az állapothoz
    megallok, helyi_jaratok, jaratok = terulet_adatai()
    if not megallok:
        print("⚠️ Nem jött megállólista – kihagyva, az állapot marad.")
        return
    sajat = helyiek(lista, megallok, helyi_jaratok, jaratok)
    for r in sajat:
        print(f"  • {', '.join(r['vonalak']) or '-'} | {cim(r)[:80]} | {idoszak(r)}")

    if ELONEZET:
        kuldes(f"🚏 BKK · {len(sajat)} változás Csepelen és Pesterzsébeten (előnézet)", sajat,
               "Ezek a most érvényes vagy bejelentett változások a környékünkön.")
        return

    try:
        with open(ALLAPOT_FAJL, encoding="utf-8") as f:
            allapot = json.load(f)
    except (OSError, ValueError):
        allapot = {}
    latott = allapot.setdefault("latott", {})
    elso = not latott

    uj = [r for r in sajat if r["id"] not in latott]
    if uj:
        if elso:
            kuldes(f"🚏 BKK · {len(uj)} érvényes változás Csepelen és Pesterzsébeten", uj,
                   "Indul a figyelő: ezek a most érvényes vagy bejelentett változások a környékünkön.")
        elif len(uj) == 1:
            kuldes(targy_egy(uj[0]), uj)
        else:
            kuldes(f"🚏 BKK · {len(uj)} új változás Csepelen és Pesterzsébeten", uj)
    for r in sajat:
        latott.setdefault(r["id"], t.isoformat(timespec="minutes"))

    # Esti emlékeztető a holnap induló változásokról (egyszer naponta, a jó éjszakát előtt)
    holnap = t.date() + timedelta(days=1)
    if ESTI_TOL <= t.time() <= ESTI_IG and allapot.get("esti") != t.date().isoformat():
        holnapiak = [r for r in sajat if r["kezdet"]
                     and datetime.fromtimestamp(r["kezdet"], MAGYAR_TZ).date() == holnap]
        if holnapiak:
            kuldes(f"🚏 BKK · holnaptól: {len(holnapiak)} változás Csepelen és Pesterzsébeten", holnapiak,
                   "Holnap induló változások – ha még nem ment ki, most érdemes megosztani.")
        allapot["esti"] = t.date().isoformat()

    # Régi, már nem szereplő riasztások takarítása (30 nap után)
    aktiv = {r["id"] for r in lista}
    hatar = (t - timedelta(days=30)).isoformat()
    for k in [k for k, v in latott.items() if k not in aktiv and v < hatar]:
        del latott[k]

    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=1)
    print(f"💾 Állapot mentve ({len(latott)} ismert, {len(uj)} új).")


if __name__ == "__main__":
    main()
