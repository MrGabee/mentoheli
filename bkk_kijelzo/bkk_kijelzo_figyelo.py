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

FUTAR_ALAP_URL = "http://futar.bkk.hu/bkk-utvonaltervezo-api/ws/otp/api/where"
FUTAR_KULCS = "apaiary-test"  # publikusan ismert, széles körben használt teszt-kulcs
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
def trip_reszletek_lekerdezese(trip_id):
    """Lekéri a FUTÁR-tól az adott trip (járat-menet) részleteit, benne a
    célállomás-kijelző szövegével (headsign)."""
    if not trip_id:
        return None
    try:
        datum = magyar_ido().strftime("%Y%m%d")
        url = (
            f"{FUTAR_ALAP_URL}/trip-details.json"
            f"?key={FUTAR_KULCS}&version=3&appVersion=apiary-1.0"
            f"&includeReferences=true&tripId={trip_id}&date={datum}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"      ⚠️  trip-details hiba ({trip_id}): {e}")
        return None


def kijelzo_szoveg_kinyerese(trip_adat):
    """A FUTÁR válaszból megpróbálja kinyerni a kijelző-szöveget - mivel
    ELŐSZÖR fut ez a kód éles adaton, több lehetséges mezőnevet is
    megpróbálunk, és NAPLÓBA ÍRJUK a teljes struktúrát az első pár
    esetben, hogy utólag pontosítani lehessen."""
    if not trip_adat or "data" not in trip_adat:
        return None

    entry = trip_adat.get("data", {}).get("entry", {})

    # Lehetséges mezőnevek, amikben a kijelző-szöveg lehet - a GTFS-szabvány
    # szerint ez jellemzően "tripHeadsign" vagy "headsign".
    for kulcs in ("tripHeadsign", "headsign", "displayName", "routeShortName"):
        if entry.get(kulcs):
            return entry[kulcs]

    # Ha semmilyen ismert mezőben nincs, a teljes entry-t visszaadjuk, hogy
    # a naplóban látszódjon, és pontosítani lehessen a fenti listát.
    return None


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
              <tr><td style="color:#888;width:140px">🚌 Járat:</td><td><strong>{t['route_id'] or '—'}</strong></td></tr>
              <tr><td style="color:#888">🔢 Jármű/rendszám:</td><td>{t['vehicle_label'] or t['vehicle_id']}</td></tr>
              <tr><td style="color:#888">💬 Kijelző szövege:</td><td><strong>{t['kijelzo_szoveg']}</strong></td></tr>
            </table>
            <div style="margin-top:8px">
              {f'<a href="{gmaps}" style="background:#4285f4;color:#fff;padding:6px 12px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:bold;margin-right:6px">📍 Google Maps</a>' if gmaps else ''}
              <a href="{futar_link}" style="background:#2c5f6f;color:#fff;padding:6px 12px;border-radius:4px;text-decoration:none;font-size:12px;font-weight:bold">🚋 FUTÁR pozíció</a>
            </div>
          </td>
        </tr>"""

        sorok_txt += (
            f"\n{'─'*45}\n{i}. 🚨 {t['egyezo_kulcsszo']}\n"
            f"Járat: {t['route_id']}\nJármű: {t['vehicle_label'] or t['vehicle_id']}\n"
            f"Kijelző: {t['kijelzo_szoveg']}\n"
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
        time.sleep(0.15)  # udvarias várakozás a FUTÁR API felé

        kijelzo_szoveg = kijelzo_szoveg_kinyerese(trip_adat)

        # Az ELSŐ néhány esetben, ha nem találtunk ismert mezőt, kiírjuk a
        # teljes választ a naplóba, hogy utólag pontosítani lehessen a
        # kijelzo_szoveg_kinyerese() függvényt.
        if kijelzo_szoveg is None and trip_adat and ismeretlen_mezo_naplo_szamlalo < 3:
            print(f"  🔍 ISMERETLEN MEZŐSZERKEZET (trip {trip_id}):")
            print(f"     {json.dumps(trip_adat, ensure_ascii=False)[:1000]}")
            ismeretlen_mezo_naplo_szamlalo += 1
            continue

        if not kijelzo_szoveg:
            continue

        egyezo_kulcsszo = rendellenes_e(kijelzo_szoveg)

        # A weboldal-exportba MINDEN jármű bekerül, kategóriával együtt
        osszes_jarmu_export.append({
            "vehicle_id": jarmu["vehicle_id"],
            "vehicle_label": jarmu["vehicle_label"],
            "route_id": jarmu["route_id"],
            "lat": jarmu["lat"],
            "lon": jarmu["lon"],
            "kijelzo_szoveg": kijelzo_szoveg,
            "kategoria": "rendellenes" if egyezo_kulcsszo else "normal",
            "egyezo_kulcsszo": egyezo_kulcsszo or None,
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
            "lat": jarmu["lat"],
            "lon": jarmu["lon"],
            "kijelzo_szoveg": kijelzo_szoveg,
            "egyezo_kulcsszo": egyezo_kulcsszo,
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
