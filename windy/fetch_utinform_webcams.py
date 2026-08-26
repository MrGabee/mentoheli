"""
Útinform (Magyar Közút) Webkamerák lekérdezés - Magyarországi közúti kamerák

Ez a script GitHub Actionben fut, szerver oldalon - itt nincs CORS
korlátozás, mert nem böngészőből, hanem szerverről indul a kérés.
(Böngészőből egyébként sem menne: az Útinform API-ja nem küld
Access-Control-Allow-Origin fejlécet idegen domainek felé, tehát a
weboldal saját maga nem tudná közvetlenül lekérdezni ezt az API-t -
ezért van szükség erre a szerveroldali köztes lépésre, pont úgy, mint
a windy-s fetch_windy_webcams.py esetében.)

Az eredményt egy statikus JSON fájlba menti, amit a weboldal
(magyar_webkamerak.html) egyszerű fetch()-csel tud beolvasni, API-kulcs
nélkül - a windy adatokkal együtt jelenítve meg, forrás-jelöléssel.

FORRÁS FELDERÍTÉSE (böngésző hálózati forgalom alapján, mivel az
utinform.hu közvetlen géppel/scripttel történő elérése egyes útvonalakon
átirányítást ad, ha az "Accept: application/json" fejléc hiányzik):
  - Lista végpont : https://www.utinform.hu/api/public/webcam/all
    -> GeoJSON FeatureCollection, "helyszínenként" (properties.id, pl.
       "mcs217") csoportosítva, minden helyszínhez 1-4 db kamera tartozik
       a properties.webcams tömbben (több nézőirány ugyanarról a pontról).
  - Képek        : https://cdnuiwebcams.utinform.hu/webcamimages/{cameraPlaceId}_{cameraNum}.jpg?lid={lastImage}
    -> a "lid" (lastImage, ezredmásodperces unix time) a cache-busting és
       egyben a frissesség jelzője is - ezt minden lekérdezéskor frissen
       az API válaszából vesszük.

Csak a hazai (magyarországi) útinform-kamerákat gyűjti - az oldalon
elérhető osztrák/szlovén határmenti kamerákat szándékosan NEM.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

API_URL = "https://www.utinform.hu/api/public/webcam/all"
OUTPUT_FILE = "windy/data/webcams_utinform.json"

# Az útinform.hu API néhány elérési módnál (pl. böngésző címsorba írt
# közvetlen navigáció) a weboldalra irányít vissza, ha nem kap explicit
# JSON Accept fejlécet - ezért ezt mindig kifejezetten kérjük, plusz egy
# valódi böngészőre hasonlító User-Agent-et adunk meg.
HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.utinform.hu/hu/map",
}

IMAGE_BASE = "https://cdnuiwebcams.utinform.hu/webcamimages"


def fetch_utinform_webcams():
    print("🔍 Útinform közúti kamerák lekérdezése...")
    response = requests.get(API_URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    data = response.json()

    features = data.get("features", [])
    print(f"   -> {len(features)} helyszín érkezett az API-ból.")
    return features


def main():
    try:
        features = fetch_utinform_webcams()
    except Exception as e:
        # Az útinform API időnként instabil / átmenetileg elérhetetlen lehet -
        # ilyenkor NEM írjuk felül a meglévő adatfájlt egy üressel, inkább
        # kilépünk hibával, hogy a weboldalon a korábbi (még mindig jó) adat
        # maradjon látható a következő sikeres futásig.
        print(f"❌ HIBA az Útinform API lekérdezésekor: {e}")
        sys.exit(1)

    simplified = []
    kihagyott = 0

    for feature in features:
        props = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}
        coords = geometry.get("coordinates") or [None, None]
        longitude, latitude = (coords + [None, None])[:2]

        # Csak a ténylegesen publikált/aktív helyszíneket vesszük figyelembe -
        # egy nem publikált helyszín kameráinak a képe sem biztos, hogy
        # elérhető/friss.
        if not props.get("published", True):
            continue

        place_name = props.get("placeName")
        county = props.get("county")
        road_number = props.get("roadNumber")

        for cam in props.get("webcams", []) or []:
            try:
                if not cam.get("published", True):
                    continue

                camera_place_id = cam.get("cameraPlaceId") or props.get("id")
                camera_num = cam.get("cameraNum")
                last_image = cam.get("lastImage")

                if not camera_place_id or camera_num is None:
                    kihagyott += 1
                    continue

                image_url = f"{IMAGE_BASE}/{camera_place_id}_{camera_num}.jpg"
                if last_image:
                    image_url += f"?lid={last_image}"

                # A longDescription már eleve tartalmazza a nézetirányt is,
                # pl. "...csomópontja (Karancsalja felé)" - ez a legjobb
                # megjelenítendő cím. Ha ez hiányozna, visszaesünk a rövidebb
                # helynévre.
                title = cam.get("longDescription") or cam.get("shortDescription") or place_name or "Ismeretlen kamera"

                simplified.append({
                    "id": f"{camera_place_id}_{camera_num}",
                    "source": "utinform",
                    "title": title,
                    "city": place_name,
                    "county": county,
                    "road": road_number,
                    "latitude": latitude,
                    "longitude": longitude,
                    "image_preview": image_url,
                    "image_thumbnail": image_url,
                    "player_embed": None,
                })
            except Exception as e:
                kihagyott += 1
                print(f"   ⚠️  Kamera feldolgozása sikertelen, kihagyva: {e}")

    if kihagyott:
        print(f"   -> {kihagyott} kamera kihagyva (hiányos/hibás adat).")

    print(f"   -> {len(simplified)} kamera található és feldolgozva.")

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(simplified),
        "webcams": simplified,
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"✅ Elmentve: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
