"""Ideiglenes: a csepeli és szigetszentmiklósi boltláncok nyitvatartása az OpenStreetMapből."""
import requests

Q = """[out:json][timeout:90];
(area["name"="XXI. kerület"]["admin_level"="9"];area["name"="Szigetszentmiklós"]["admin_level"="8"];)->.a;
(nwr["shop"~"supermarket|convenience"]["brand"~"ALDI|Lidl|PENNY|SPAR|Reál|CBA|Tesco|Auchan",i](area.a);
 nwr["amenity"="marketplace"](area.a););
out tags center;"""
for url in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
    try:
        r = requests.post(url, data={"data": Q}, timeout=120)
        r.raise_for_status()
        for e in sorted(r.json()["elements"], key=lambda e: str(e["tags"].get("brand", e["tags"].get("name")))):
            t = e["tags"]
            print(f"{t.get('brand') or t.get('name')} | {t.get('name','')} | {t.get('addr:city','')} "
                  f"{t.get('addr:postcode','')} {t.get('addr:street','')} {t.get('addr:housenumber','')} | "
                  f"{t.get('opening_hours','-')} | ellenőrizve: {t.get('check_date:opening_hours', t.get('check_date','-'))}")
        break
    except Exception as ex:
        print("hiba:", url, ex)
