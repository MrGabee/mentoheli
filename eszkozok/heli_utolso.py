"""Egyszeri: e-mail a legutóbbi felszállásról és leszállásról (az új arculattal)."""
import json, sys, time
sys.path.insert(0, ".")
import requests
import monitor as m


def nyomvonal(flight_id):
    """Az FR24 visszajátszás pontjai, ha elérhető: [[ts, lat, lon, alt_m, kmh], ...]"""
    try:
        r = requests.get("https://api.flightradar24.com/common/v1/flight-playback.json",
                         params={"flightId": flight_id}, headers=m.HEADERS, timeout=20)
        print(f"  FR24 playback {flight_id}: HTTP {r.status_code}")
        track = r.json()["result"]["response"]["data"]["flight"]["track"]
        pontok = [[p["timestamp"], round(p["latitude"], 5), round(p["longitude"], 5),
                   round(p["altitude"]["meters"]), round(p["speed"]["kmh"])] for p in track]
        print(f"  {len(pontok)} pont")
        return pontok
    except Exception as ex:
        print(f"  ⚠️ nincs nyomvonal: {ex}")
        return []


allapot = json.load(open("allapot.json"))
gepek = {k: v for k, v in allapot.items() if k.startswith("reg:") and v.get("flight_id")}
felsz = max(gepek, key=lambda k: int(gepek[k]["flight_id"], 16))
lesz = max((k for k in gepek if gepek[k].get("landed")), key=lambda k: int(gepek[k]["flight_id"], 16))
for tipus, kulcs in (("FELSZALLAS", felsz), ("LESZALLAS", lesz)):
    adat = dict(gepek[kulcs], elo=False)
    print(f"{tipus}: {kulcs} {adat}")
    pontok = nyomvonal(adat["flight_id"])
    if pontok:
        # az aktualis_ut friss pontot vár: időbélyeg-eltolás a mostani időhöz
        eltolas = int(time.time()) - pontok[-1][0]
        pontok = [[p[0] + eltolas] + p[1:] for p in pontok]
    m.email_kuldes({"tipus": tipus, "kulcs": kulcs, "adat": adat}, {kulcs[4:]: {"pontok": pontok}})
