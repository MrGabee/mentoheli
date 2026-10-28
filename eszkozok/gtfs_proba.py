# Ideiglenes: BKK GTFS-realtime Alerts – mi érinti most Csepelt? (nem küld semmit)
import os
from datetime import datetime, timezone, timedelta
import requests
from google.transit import gtfs_realtime_pb2

KULCS = os.environ["BKK_API_KEY"]
ALAP = "https://futar.bkk.hu/api/query/v1/ws/otp/api/where"
UA = {"User-Agent": "mentoheli-monitor/1.0"}


def kerdez(vegpont, **p):
    p.update(key=KULCS, version=3, appVersion="mrgabee-1.0")
    try:
        r = requests.get(f"{ALAP}/{vegpont}.json", params=p, headers=UA, timeout=25)
        return r.json()
    except Exception as ex:
        print("hiba:", vegpont, type(ex).__name__)
        return {}


# Csepeli megállók és járatok
d = kerdez("stops-for-location", lat=47.425, lon=19.075, latSpan=0.075, lonSpan=0.075)
ref = (d.get("data") or {}).get("references") or {}
megallok = ref.get("stops") or {}
jaratok = ref.get("routes") or {}
print("Csepeli megállók:", len(megallok), "járatok:", len(jaratok))
print("Járatok:", sorted({r.get("shortName", "") for r in jaratok.values()}))
# Csak a Csepel-sziget északi része (XXI. ker.), koordinátával szűrve
bent = {k: m for k, m in megallok.items() if 47.385 <= m.get("lat", 0) <= 47.455 and 19.035 <= m.get("lon", 0) <= 19.115}
nyers = lambda x: x.split("_", 1)[1] if "_" in x else x
csepeli_stop = {nyers(k) for k in bent}
csepeli_route = {nyers(r) for m in bent.values() for r in (m.get("routeIds") or [])}
jaratok = {nyers(k): v for k, v in jaratok.items()}
print("Szűrt csepeli megállók:", len(bent), "járatok:", sorted({jaratok[r].get("shortName", r) for r in csepeli_route if r in jaratok}))
print("Minta megálló-id:", list(megallok)[:3], "route-id:", list(ref.get("routes") or {})[:3])

try:
    r = requests.get("https://go.bkk.hu/api/query/v1/ws/gtfs-rt/full/Alerts.pb",
                     params={"key": KULCS}, headers=UA, timeout=30)
    print("Alerts.pb HTTP", r.status_code, len(r.content), "bájt")
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(r.content)
except Exception as ex:
    print("Alerts hiba:", type(ex).__name__)
    feed = gtfs_realtime_pb2.FeedMessage()

TZ = timezone(timedelta(hours=1))


def szoveg(ts):
    for t in ts.translation:
        if t.language in ("hu", ""):
            return t.text
    return ts.translation[0].text if ts.translation else ""


print("Összes riasztás:", len(feed.entity))
for e in feed.entity[:3]:
    print("Minta informed_entity:", [(i.route_id, i.stop_id, i.agency_id) for i in e.alert.informed_entity][:4], "|", szoveg(e.alert.header_text)[:80])
talalt = 0
for e in feed.entity:
    a = e.alert
    routes = {i.route_id for i in a.informed_entity if i.route_id}
    stops = {i.stop_id for i in a.informed_entity if i.stop_id}
    if not (routes & csepeli_route or stops & csepeli_stop):
        continue
    talalt += 1
    idok = [(datetime.fromtimestamp(p.start, TZ).strftime("%m.%d %H:%M") if p.start else "?",
             datetime.fromtimestamp(p.end, TZ).strftime("%m.%d %H:%M") if p.end else "?") for p in a.active_period]
    nevek = sorted({jaratok[x].get("shortName", x) for x in routes if x in jaratok})
    print("\n=== ", e.id, "| ok:", a.cause, "hatás:", a.effect)
    print("Járatok:", nevek, "| egyéb route:", len(routes - csepeli_route), "| megállók:", len(stops))
    print("Időszak:", idok[:4])
    print("Cím:", szoveg(a.header_text))
    print("Leírás:", szoveg(a.description_text)[:700].replace("\n", " "))
    print("URL:", szoveg(a.url))
print("\nCsepelt érintő riasztás:", talalt)
