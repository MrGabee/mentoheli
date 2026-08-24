#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BKK KIJELZŐ-FIGYELŐ
==================================================================
Lekérdezi az összes aktív BKK jármű célállomás-kijelzőjének szövegét
(FUTÁR API), és megkülönbözteti:

  - NORMÁL: rendes végállomás-szöveg (pl. "Örs vezér tere")
  - RENDELLENES: a szöveg egyezik valamelyik figyelt kulcsszóval
    (pl. "Mentőre vár", "Baleseti helyszínelőre vár")

Csak a RENDELLENES találatokról megy email, a kért mezőkkel:
járat neve, rendszám/jármű-azonosító, kijelző szövege, pozíció.

⚠️ FONTOS: az itt megadott RENDELLENES_KULCSSZAVAK lista egy induló
becslés - az ELSŐ ÉLES FUTÁS UTÁN érdemes megnézni a naplóban
(GitHub Actions log) ténylegesen milyen szövegek jönnek, és pontosítani
ezt a listát a valós adatok alapján.
"""

import os
import re
import json
import time
import smtplib
import requests
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

MAGYAR_TZ = timezone(timedelta(hours=2))

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT_BKK"]

FUTAR_ALAP_URL = "https://futar.bkk.hu/api/query/v1/ws/otp/api/where"
# A webalkalmazás saját, a frontend-kódjába ágyazott (tehát bárki számára
# látható, publikus) kulcsa - élő böngésző-forgalomból derült ki 2026.08.24-én.
# Ha a BKK frissíti az alkalmazást, ez az appVersion és/vagy a kulcs is
# megváltozhat - ha újra elakad, ellenőrizd böngészőben (F12 → Hálózat).
FUTAR_KULCS = "web-54feeb28-a942-48ae-89a5-9955879ebb2c"
FUTAR_VERZIO = "4"
FUTAR_APP_VERZIO = "3.18.0-251972-2069795-86d980c0"
GTFS_RT_VEHICLE_POSITIONS_URL = "https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/VehiclePositions.pb"
BKK_API_KULCS = os.environ.get("BKK_API_KULCS", "")  # opendata.bkk.hu-n regisztrálva szerezhető

ALLAPOT_FAJL = "bkk_kijelzo_allapot.json"

# ⬇️⬇️⬇️ ITT ÁLLÍTSD BE, MILYEN KIJELZŐ-SZÖVEGEK SZÁMÍTANAK "RENDELLENES"-NEK ⬇️⬇️⬇️
# Kis-nagybetűtől független, RÉSZLEGES egyezés (bárhol a szövegben előfordulhat).
# AZ ELSŐ ÉLES FUTÁS UTÁN nézd meg a naplóban a tényleges kijelző-szövegeket,
# és pontosítsd ezt a listát!
RENDELLENES_KULCSSZAVAK = [
    "mentőre vár",
    "mentő",
    "baleseti helyszínelő",
    "helyszínelő",
    "baleset",
    "rendőrségi intézkedés",
    "rendőr",
    "műszaki hiba",
    "meghibásodás",
    "forgalmi akadály",
    "nem közlekedik",
    "üzemzavar",
    "torlódás",
    "terelés",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BkkKijelzoFigyelo/1.0)"}


# ════════════════════════════════════════════
#  💾  ÁLLAPOT
# ════════════════════════════════════════════
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


# ════════════════════════════════════════════
#  📡  AKTÍV JÁRMŰVEK LEKÉRDEZÉSE (GTFS-RT VehiclePositions, protobuf)
# ════════════════════════════════════════════
def aktiv_jarmuvek_lekerdezese():
    """A GTFS-RT VehiclePositions feed protobuf formátumú - a Google saját
    gtfs-realtime-bindings csomagja kell a feldolgozásához."""
    try:
        from google.transit import gtfs_realtime_pb2
    except ImportError:
        print("  ❌ Hiányzó függőség: pip install gtfs-realtime-bindings")
        return []

    try:
        if not BKK_API_KULCS:
            print("  ⚠️  Nincs beállítva BKK_API_KULCS - regisztrálj: https://opendata.bkk.hu/data-sources")
            return []

        resp = requests.get(
            GTFS_RT_VEHICLE_POSITIONS_URL,
            params={"key": BKK_API_KULCS},
            headers=HEADERS,
            timeout=20,
        )
        resp.raise_for_status()

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(resp.content)

        jarmuvek = []
        for entity in feed.entity:
            if not entity.HasField("vehicle"):
                continue
            v = entity.vehicle
            jarmuvek.append({
                "vehicle_id": v.vehicle.id if v.vehicle.HasField("id") else entity.id,
                "vehicle_label": v.vehicle.label if v.vehicle.HasField("label") else "",
                "trip_id": v.trip.trip_id if v.HasField("trip") and v.trip.HasField("trip_id") else "",
                "route_id": v.trip.route_id if v.HasField("trip") and v.trip.HasField("route_id") else "",
                "lat": v.position.latitude if v.HasField("position") else None,
                "lon": v.position.longitude if v.HasField("position") else None,
            })

        print(f"  📊 Aktív járművek: {len(jarmuvek)}")
        return jarmuvek
    except Exception as e:
        print(f"  ❌ Hiba a jármű-lekérdezésnél: {e}")
        return []


# ════════════════════════════════════════════
#  🚏  ÚTVONAL-RÉSZLETEK LEKÉRDEZÉSE (FUTÁR trip-details - kijelző-szöveg)
# ════════════════════════════════════════════
_VONAL_GYORSITOTAR = {}  # route_id -> vonalszám (ne kérdezzük le ugyanazt többször egy futáson belül)
_VONAL_DIAGNOSZTIKA_SZAMLALO = {"ertek": 0}
_VONAL_DIAGNOSZTIKA_MAX = 3


def vonalszam_lekerdezese(route_id):
    if not route_id:
        return None
    if route_id in _VONAL_GYORSITOTAR:
        return _VONAL_GYORSITOTAR[route_id]

    diagnosztika_kell = _VONAL_DIAGNOSZTIKA_SZAMLALO["ertek"] < _VONAL_DIAGNOSZTIKA_MAX
    cache_torles = str(int(time.time() * 1000))
    url = (
        f"{FUTAR_ALAP_URL}/route-details.json"
        f"?routeId={route_id}"
        f"&key={FUTAR_KULCS}&version={FUTAR_VERZIO}&appVersion={FUTAR_APP_VERZIO}"
        f"&locale=hu&_={cache_torles}"
    )

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except Exception as e:
        if diagnosztika_kell:
            print(f"      ⚠️  [route {route_id}] KAPCSOLÓDÁSI hiba: {type(e).__name__}: {e}")
        _VONAL_GYORSITOTAR[route_id] = None
        return None

    if diagnosztika_kell:
        print(f"      ℹ️  [route {route_id}] HTTP {resp.status_code} | hossz: {len(resp.content)} byte | "
              f"eleje: {resp.content[:300]!r}")
        _VONAL_DIAGNOSZTIKA_SZAMLALO["ertek"] += 1

    vonalszam = None
    if resp.status_code == 200 and resp.content.strip():
        try:
            adat = resp.json()
            entry = adat.get("data", {}).get("entry", {})
            # Több lehetséges mezőnevet is megpróbálunk - az élő tesztelés
            # dönti majd el, melyik a helyes (lásd a fenti diagnosztikai sort).
            for kulcs in ("shortName", "routeShortName", "shortTitle", "designation"):
                if entry.get(kulcs):
                    vonalszam = entry[kulcs]
                    break
        except Exception as e:
            if diagnosztika_kell:
                print(f"      ⚠️  [route {route_id}] JSON-értelmezési hiba: {type(e).__name__}: {e}")

    _VONAL_GYORSITOTAR[route_id] = vonalszam
    return vonalszam


_DIAGNOSZTIKA_SZAMLALO = {"ertek": 0}
_DIAGNOSZTIKA_MAX = 5


def trip_reszletek_lekerdezese(trip_id):
    """Lekéri a FUTÁR-tól az adott trip (járat-menet) részleteit, benne a
    célállomás-kijelző szövegével (headsign)."""
    if not trip_id:
        return None

    datum = magyar_ido().strftime("%Y%m%d")
    # A FUTÁR API "BKK_" előtaggal várja a trip_id-t (élő böngésző-forgalom
    # alapján derült ki: tripId=BKK_D1617810, nem simán D1617810).
    trip_id_elotaggal = trip_id if trip_id.startswith("BKK_") else f"BKK_{trip_id}"
    cache_torles = str(int(time.time() * 1000))
    url = (
        f"{FUTAR_ALAP_URL}/trip-details.json"
        f"?tripId={trip_id_elotaggal}&date={datum}"
        f"&key={FUTAR_KULCS}&version={FUTAR_VERZIO}&appVersion={FUTAR_APP_VERZIO}"
        f"&locale=hu&_={cache_torles}"
    )

    diagnosztika_kell = _DIAGNOSZTIKA_SZAMLALO["ertek"] < _DIAGNOSZTIKA_MAX

    # Szándékosan EGYETLEN, tág except-ág - így nem számít, milyen
    # kivétel-hierarchiát használ a requests könyvtár verziója, a
    # diagnosztika mindenképp egyértelműen kiíródik.
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except Exception as e:
        print(f"      ⚠️  [{trip_id}] KAPCSOLÓDÁSI hiba (a kérés el sem jutott célba): {type(e).__name__}: {e}")
        return None

    if diagnosztika_kell:
        print(f"      ℹ️  [{trip_id}] HTTP {resp.status_code} | hossz: {len(resp.content)} byte | "
              f"content-type: {resp.headers.get('Content-Type', '?')} | "
              f"eleje: {resp.content[:120]!r}")
        _DIAGNOSZTIKA_SZAMLALO["ertek"] += 1

    if resp.status_code != 200:
        return None
    if not resp.content.strip():
        return None

    try:
        return resp.json()
    except Exception as e:
        if diagnosztika_kell:
            print(f"      ⚠️  [{trip_id}] JSON-értelmezési hiba: {type(e).__name__}: {e}")
        return None


def jarmu_adatok_kinyerese(trip_adat):
    """A FUTÁR válaszból kinyeri az ÖSSZES elérhető jármű-adatot - élő
    böngésző-forgalom alapján azonosított, valódi mezőnevek (2026.08.24)."""
    if not trip_adat or "data" not in trip_adat:
        return None

    vehicle = trip_adat.get("data", {}).get("entry", {}).get("vehicle", {})
    if not vehicle:
        return None

    return {
        "kijelzo_szoveg": vehicle.get("label"),
        "rendszam": vehicle.get("licensePlate"),
        "modell": vehicle.get("model"),
        "eszkoz_tipus": vehicle.get("vehicleRouteType"),  # BUS / TRAM / TROLLEYBUS / RAIL stb.
        "statusz": vehicle.get("status"),
        "elteres": vehicle.get("deviated"),
        "torlodas": vehicle.get("congestionLevel"),
        "akadalymentes": vehicle.get("wheelchairAccessible"),
        "kovetkezo_megallo_id": vehicle.get("stopId"),
        "megallo_sorszam": vehicle.get("stopSequence"),
        "iranyszog": vehicle.get("bearing"),
        "utolso_frissites": vehicle.get("lastUpdateTime"),
    }


# ════════════════════════════════════════════
#  🚨  RENDELLENES SZŰRÉS
# ════════════════════════════════════════════
def rendellenes_e(kijelzo_szoveg):
    if not kijelzo_szoveg:
        return False
    szoveg_kisbetus = kijelzo_szoveg.lower()
    for kulcsszo in RENDELLENES_KULCSSZAVAK:
        if kulcsszo.lower() in szoveg_kisbetus:
            return kulcsszo
    return False


# ════════════════════════════════════════════
#  📧  EMAIL KÜLDÉS
# ════════════════════════════════════════════
def formaz_unix_ido(unix_masodperc):
    if not unix_masodperc:
        return "—"
    try:
        dt = datetime.fromtimestamp(int(unix_masodperc), tz=timezone.utc).astimezone(MAGYAR_TZ)
        return dt.strftime("%Y.%m.%d %H:%M:%S")
    except Exception:
        return "—"


def email_kuldes(talalatok):
    ido = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    db = len(talalatok)
    targy = f"🚨 BKK kijelző - rendellenes üzenet ({db} db) | {ido}"

    sorok_html = ""
    sorok_txt = ""

    for i, t in enumerate(talalatok, 1):
        gmaps = f"https://www.google.com/maps?q={t['lat']},{t['lon']}&z=17" if t["lat"] and t["lon"] else None
        futar_link = f"https://futar.bkk.hu/?vehicleId={t['vehicle_id']}"

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:#c0392b;color:#fff;padding:5px 12px;border-radius:4px;
                         font-size:13px;font-weight:bold">🚨 {t['egyezo_kulcsszo'].upper()}</span>
            <table style="font-size:13px;width:100%;margin-top:10px">
              <tr><td style="color:#888;width:140px">🚌 Vonal:</td><td><strong>{t['vonal_szam'] or '—'}</strong> <span style="color:#aaa">({t['route_id'] or '—'})</span></td></tr>
              <tr><td style="color:#888">💬 Kijelző szövege:</td><td><strong>{t['kijelzo_szoveg']}</strong></td></tr>
              <tr><td style="color:#888">🔢 Rendszám:</td><td>{t['rendszam'] or '—'}</td></tr>
              <tr><td style="color:#888">🚐 Jármű típusa:</td><td>{t['eszkoz_tipus'] or '—'} · {t['modell'] or '—'}</td></tr>
              <tr><td style="color:#888">🆔 Jármű-azonosító:</td><td>{t['vehicle_label'] or t['vehicle_id']}</td></tr>
              <tr><td style="color:#888">📡 Állapot:</td><td>{t['statusz'] or '—'}</td></tr>
              <tr><td style="color:#888">🕐 Utolsó frissítés:</td><td>{formaz_unix_ido(t.get('utolso_frissites'))}</td></tr>
            </table>
            <div style="margin-top:8px">
              {f'<a href="{gmaps}" style="background:#4285f4;color:#fff;padding:6px 12px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:bold;margin-right:6px">📍 Google Maps</a>' if gmaps else ''}
              <a href="{futar_link}" style="background:#2c5f6f;color:#fff;padding:6px 12px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:bold">🚋 FUTÁR pozíció</a>
            </div>
          </td>
        </tr>"""

        sorok_txt += (
            f"\n{'─'*45}\n{i}. 🚨 {t['egyezo_kulcsszo']}\n"
            f"Vonal: {t['vonal_szam']} ({t['route_id']})\nKijelző: {t['kijelzo_szoveg']}\n"
            f"Rendszám: {t['rendszam']}\nTípus: {t['eszkoz_tipus']} · {t['modell']}\n"
            f"Jármű: {t['vehicle_label'] or t['vehicle_id']}\nÁllapot: {t['statusz']}\n"
            f"Maps: {gmaps or '—'}\nFUTÁR: {futar_link}\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="hu"><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}}
  .wrap{{max-width:650px;margin:20px auto;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.15)}}
  .hdr{{background:#c0392b;color:#fff;padding:22px 28px}}
  .hdr h1{{margin:0;font-size:20px}}
  .hdr small{{opacity:.85;font-size:13px}}
  .body{{padding:20px 28px}}
  .foot{{background:#ecf0f1;padding:12px 28px;font-size:11px;color:#95a5a6;text-align:center}}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>🚨 BKK kijelző - rendellenes üzenet</h1>
    <small>{ido} | {db} találat</small>
  </div>
  <div class="body">
    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>
  </div>
  <div class="foot">Automatikus figyelő – GitHub Actions | FUTÁR API adatok alapján</div>
</div></body></html>"""

    szoveges = f"🚨 BKK kijelző - rendellenes üzenet\nIdőpont: {ido}\n{sorok_txt}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"] = f"🚌 BKK Kijelző Figyelő <{EMAIL_KULDO}>"
    msg["To"] = EMAIL_CIMZETT
    msg.attach(MIMEText(szoveges, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
        smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
    print(f"📧 E-mail elküldve: {targy}")


# ════════════════════════════════════════════
#  🌐  WEBOLDAL-ADAT EXPORT
# ════════════════════════════════════════════
AKTIV_JSON_FAJL = "bkk_kijelzo_aktiv.json"


def ment_aktiv_json(osszes_jarmu_adat):
    """Kiírja az ÖSSZES, jelenleg feldolgozott jármű adatát (normál ÉS
    rendellenes egyaránt) egy külön JSON-fájlba, amit a weboldal
    (bkk_kijelzo.html) tölt be és jelenít meg élőben."""
    with open(AKTIV_JSON_FAJL, "w", encoding="utf-8") as fjson:
        json.dump({
            "frissitve": magyar_ido().isoformat(),
            "jarmuvek": osszes_jarmu_adat,
        }, fjson, ensure_ascii=False, indent=2)
    print(f"🌐 Weboldal-adat mentve: {AKTIV_JSON_FAJL} ({len(osszes_jarmu_adat)} jármű)")


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"🚌 BKK Kijelző Figyelő – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    elso_futas = not os.path.exists(ALLAPOT_FAJL)

    jarmuvek = aktiv_jarmuvek_lekerdezese()
    if not jarmuvek:
        print("⚠️  Nincs lekérdezhető jármű-adat, kilépés.")
        return

    talalatok = []
    osszes_jarmu_export = []
    ismeretlen_mezo_naplo_szamlalo = 0

    for jarmu in jarmuvek:
        trip_id = jarmu["trip_id"]
        if not trip_id:
            continue

        trip_adat = trip_reszletek_lekerdezese(trip_id)
        time.sleep(0.03)  # minimális, csak hogy ne egyszerre záporozzon a kérés

        vonal_szam = vonalszam_lekerdezese(jarmu["route_id"])

        adatok = jarmu_adatok_kinyerese(trip_adat)

        # Az ELSŐ néhány esetben, ha nem találtunk adatot, kiírjuk a
        # teljes választ a naplóba, hogy utólag pontosítani lehessen a
        # jarmu_adatok_kinyerese() függvényt.
        if adatok is None and trip_adat and ismeretlen_mezo_naplo_szamlalo < 3:
            print(f"  🔍 ISMERETLEN MEZŐSZERKEZET (trip {trip_id}):")
            print(f"     {json.dumps(trip_adat, ensure_ascii=False)[:1000]}")
            ismeretlen_mezo_naplo_szamlalo += 1

        if adatok is None:
            # Nincs részletes adat (pl. a trip-nek nincs "vehicle" mezője a
            # válaszban) - a weboldalra ETTŐL FÜGGETLENÜL bekerül, csak az
            # alap (VehiclePositions-ból már ismert) adatokkal, kijelző-
            # szöveg nélkül. E-mail-riasztáshoz értelemszerűen nem jó, mert
            # nincs mit kulcsszó szerint megvizsgálni.
            osszes_jarmu_export.append({
                "vehicle_id": jarmu["vehicle_id"],
                "vehicle_label": jarmu["vehicle_label"],
                "route_id": jarmu["route_id"],
                "vonal_szam": vonal_szam,
                "lat": jarmu["lat"],
                "lon": jarmu["lon"],
                "kategoria": "ismeretlen",
                "egyezo_kulcsszo": None,
                "kijelzo_szoveg": None,
                "rendszam": None,
                "modell": None,
                "eszkoz_tipus": None,
                "statusz": None,
                "elteres": None,
                "torlodas": None,
                "akadalymentes": None,
                "kovetkezo_megallo_id": None,
                "megallo_sorszam": None,
                "iranyszog": None,
                "utolso_frissites": None,
            })
            continue

        kijelzo_szoveg = adatok["kijelzo_szoveg"]
        if not kijelzo_szoveg:
            continue
        egyezo_kulcsszo = rendellenes_e(kijelzo_szoveg)

        # A weboldal-exportba MINDEN jármű bekerül, kategóriával együtt
        osszes_jarmu_export.append({
            "vehicle_id": jarmu["vehicle_id"],
            "vehicle_label": jarmu["vehicle_label"],
            "route_id": jarmu["route_id"],
            "vonal_szam": vonal_szam,
            "lat": jarmu["lat"],
            "lon": jarmu["lon"],
            "kategoria": "rendellenes" if egyezo_kulcsszo else "normal",
            "egyezo_kulcsszo": egyezo_kulcsszo or None,
            **adatok,
        })

        if not egyezo_kulcsszo:
            continue  # normál végállomás-szöveg, e-mailhez nem érdekes

        # Azonosító: jármű + kijelző-szöveg kombinációja, hogy ugyanarra a
        # rendellenességre ne küldjünk emailt minden egyes futásnál újra.
        azonosito = f"{jarmu['vehicle_id']}::{kijelzo_szoveg}"
        if azonosito in regi:
            continue

        regi[azonosito] = magyar_ido().isoformat()

        if elso_futas:
            continue  # első futásnál csak alapállapotot mentünk

        talalatok.append({
            "vehicle_id": jarmu["vehicle_id"],
            "vehicle_label": jarmu["vehicle_label"],
            "route_id": jarmu["route_id"],
            "vonal_szam": vonal_szam,
            "lat": jarmu["lat"],
            "lon": jarmu["lon"],
            "egyezo_kulcsszo": egyezo_kulcsszo,
            **adatok,
        })

    # Weboldal-adat mentése minden futáskor - új rendellenesség nélkül is
    ment_aktiv_json(osszes_jarmu_export)

    print(f"\n🚨 Rendellenes találatok: {len(talalatok)}")
    if elso_futas:
        print("✅ Első futás - alapállapot elmentve, email nem ment.")
    elif talalatok:
        email_kuldes(talalatok)
    else:
        print("✅ Nincs új rendellenes kijelző-üzenet.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
