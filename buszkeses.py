"""
🚌 Buszkésés-mérő – 35, 36, 148, 151 (Csepel ↔ Pesterzsébet)
Adatforrás: BKK FUTÁR (OpenData, saját kulccsal: BKK_API_KEY titok)
Hétköznap reggel 6 és 9 között 10 percenként felírja minden úton lévő
busz aktuális késését (előrejelzett – menetrend szerinti indulás a
következő megállónál). Az adatok a buszkeses/ÉÉÉÉ-HH-NN.json fájlba kerülnek,
ebből készül később az összesítő.
A kulcs soha nem kerül a naplóba vagy a repóba.
"""

import os
import json
import time
import requests
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

MAGYAR_TZ = ZoneInfo("Europe/Budapest")
ALAP = "https://futar.bkk.hu/api/query/v1/ws/otp/api/where"
KULCS = os.environ.get("BKK_API_KEY", "")
JARATOK = {"BKK_0350": "35", "BKK_0360": "36", "BKK_1480": "148", "BKK_1510": "151"}
TOL, IG = dtime(6, 0), dtime(9, 0)
MAPPA = "buszkeses"
HEADERS = {"User-Agent": "MrGabee-buszkeses/1.0"}


def _kerdez(vegpont, **param):
    param.update(key=KULCS, version=3, appVersion="mrgabee-1.0")
    try:
        r = requests.get(f"{ALAP}/{vegpont}.json", params=param, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ {vegpont}: HTTP {r.status_code}")
            return None
        return r.json().get("data")
    except Exception as e:
        print(f"  ⚠️ {vegpont}: {type(e).__name__}")   # a kivétel szövege tartalmazhatná a kulcsot
        return None


def meres(most):
    sorok = []
    for route_id, nev in JARATOK.items():
        d = _kerdez("vehicles-for-route", routeId=route_id, related="false")
        if not d:
            continue
        for v in d.get("list") or []:
            trip_id, stop_id = v.get("tripId"), v.get("stopId")
            if not trip_id or not stop_id:
                continue
            t = _kerdez("trip-details", tripId=trip_id, includeReferences="stops")
            if not t:
                continue
            megallok = (t.get("references") or {}).get("stops") or {}
            for st in (t.get("entry") or {}).get("stopTimes") or []:
                if st.get("stopId") != stop_id:
                    continue
                menetrend = st.get("departureTime") or st.get("arrivalTime")
                elore = st.get("predictedDepartureTime") or st.get("predictedArrivalTime")
                if menetrend and elore:
                    sorok.append({
                        "ido": most.strftime("%H:%M"),
                        "jarat": nev,
                        "jarmu": v.get("vehicleId"),
                        "trip": trip_id,
                        "megallo": megallok.get(stop_id, {}).get("name", stop_id),
                        "keses_perc": round((elore - menetrend) / 60, 1),
                    })
                break
            time.sleep(0.2)
    return sorok


def main():
    most = datetime.now(MAGYAR_TZ)
    print(f"🚌 Buszkésés-mérő – {most.strftime('%Y.%m.%d %H:%M')}")
    if not KULCS:
        print("⚠️ Nincs BKK_API_KEY titok beállítva – kihagyva.")
        return
    teszt = bool(os.environ.get("TESZT"))
    if not teszt and (most.weekday() > 4 or not (TOL <= most.time() < IG)):
        print("⏭️ Nem hétköznap reggel 6–9 van – kihagyva.")
        return
    sorok = meres(most)
    for jarat in JARATOK.values():
        k = [s["keses_perc"] for s in sorok if s["jarat"] == jarat]
        if k:
            print(f"  {jarat}: {len(k)} busz, átlag {sum(k)/len(k):.1f} perc, max {max(k):.1f} perc")
        else:
            print(f"  {jarat}: nincs adat")
    if teszt:
        for s in sorok[:8]:
            print("   ", s)
        return
    os.makedirs(MAPPA, exist_ok=True)
    fajl = os.path.join(MAPPA, most.strftime("%Y-%m-%d") + ".json")
    try:
        with open(fajl, encoding="utf-8") as f:
            regi = json.load(f)
    except (OSError, ValueError):
        regi = []
    with open(fajl, "w", encoding="utf-8") as f:
        json.dump(regi + sorok, f, ensure_ascii=False, indent=1)
    print(f"💾 {len(sorok)} mérés mentve: {fajl}")


if __name__ == "__main__":
    main()
