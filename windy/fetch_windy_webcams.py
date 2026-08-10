"""
Windy Webcams API lekérdezés - Magyarországi kamerák

Ez a script GitHub Actionben fut, szerver oldalon - itt nincs CORS
korlátozás, mert nem böngészőből, hanem szerverről indul a kérés.
Az eredményt egy statikus JSON fájlba menti, amit a weboldal
(magyar_webkamerak.html) egyszerű fetch()-csel tud beolvasni,
API-kulcs nélkül.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

API_KEY = os.environ.get("WINDY_API_KEY")
OUTPUT_FILE = "windy/data/webcams_hu.json"

if not API_KEY:
    print("❌ HIBA: a WINDY_API_KEY környezeti változó nincs beállítva.")
    sys.exit(1)


def fetch_hungarian_webcams():
    url = "https://api.windy.com/webcams/api/v3/webcams"
    headers = {"x-windy-api-key": API_KEY}

    # Magyarország egyetlen 250 km-es körből nem fedhető le teljesen
    # (az ország átlója kb. 600 km) - ezért 6 régióra bontjuk, hasonlóan
    # a Waze monitornál már bevált 6-csempés felosztáshoz. A körök kicsit
    # átfednek egymással, hogy ne maradjon ki terület a szélek mentén.
    regions = [
        {"name": "Északnyugat (Győr)", "lat": 47.68, "lon": 17.63, "radius": 140},
        {"name": "Északkelet (Miskolc)", "lat": 48.10, "lon": 20.78, "radius": 140},
        {"name": "Közép (Budapest)", "lat": 47.35, "lon": 18.90, "radius": 140},
        {"name": "Keleti (Debrecen)", "lat": 47.53, "lon": 21.62, "radius": 140},
        {"name": "Délnyugat (Pécs)", "lat": 46.07, "lon": 18.23, "radius": 140},
        {"name": "Délkelet (Szeged)", "lat": 46.25, "lon": 20.15, "radius": 140},
    ]

    page_size = 50
    max_pages_per_region = 4  # 4 x 50 = 200 kamera / régió - bőven elég

    seen_ids = set()
    all_webcams = []

    for region in regions:
        print(f"🔍 Régió: {region['name']}...")
        offset = 0

        for page in range(max_pages_per_region):
            params = {
                "nearby": f"{region['lat']},{region['lon']},{region['radius']}",
                "limit": page_size,
                "offset": offset,
                "include": "images,location,player",
            }
            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            page_data = response.json().get("webcams", [])

            if not page_data:
                break

            new_in_page = 0
            for cam in page_data:
                cam_id = cam.get("webcamId")
                if cam_id not in seen_ids:
                    seen_ids.add(cam_id)
                    all_webcams.append(cam)
                    new_in_page += 1

            print(f"   -> {page + 1}. oldal: {len(page_data)} kamera ({new_in_page} új).")

            if len(page_data) < page_size:
                break

            offset += page_size

    hungarian_only = [
        cam for cam in all_webcams
        if (cam.get("location", {}) or {}).get("country_code") == "HU"
    ]

    print(f"   -> {len(all_webcams)} kamera a 250 km-es körben, ebből {len(hungarian_only)} magyarországi.")

    if all_webcams and not hungarian_only:
        # Ha a szűrés váratlanul 0-t adna, valószínűleg a "country" mező
        # más formátumban jön vissza (pl. "Hungary" az "HU" helyett) -
        # ez segít kideríteni, mit kell a szűrőn pontosítani.
        print("   ⚠️  Egyetlen kamera sem maradt HU szűrés után - néhány nyers 'location' mező diagnosztikához:")
        for cam in all_webcams[:5]:
            print(f"      {cam.get('location')}")

    return {"webcams": hungarian_only}


def main():
    print("🔍 Magyarországi webkamerák lekérdezése a Windy API-ból...")
    data = fetch_hungarian_webcams()
    webcams = data.get("webcams", [])
    print(f"   -> {len(webcams)} kamera található.")

    # Csak a ténylegesen szükséges mezőket mentjük, hogy a fájl kicsi maradjon
    simplified = []
    for cam in webcams:
        try:
            player = cam.get("player", {}) or {}
            # FONTOS: a hivatalos Windy API v3 séma szerint player.day/month/
            # year/lifetime KÖZVETLENÜL string (maga az embed URL), NEM egy
            # beágyazott {embed: "..."} objektum - csak player.live van így
            # becsomagolva (available + embed). Ha ezt összekevernénk, egy
            # string-en meghívott .get("embed") AttributeError-t dobna és
            # leállítaná a teljes futást.
            player_day = player.get("day")
            player_embed = player_day if isinstance(player_day, str) else None
            if not player_embed:
                live = player.get("live")
                if isinstance(live, dict):
                    player_embed = live.get("embed")

            simplified.append({
                "id": cam.get("webcamId"),
                "title": cam.get("title"),
                "city": cam.get("location", {}).get("city"),
                "region": cam.get("location", {}).get("region"),
                "latitude": cam.get("location", {}).get("latitude"),
                "longitude": cam.get("location", {}).get("longitude"),
                "image_preview": cam.get("images", {}).get("current", {}).get("preview"),
                "image_thumbnail": cam.get("images", {}).get("current", {}).get("thumbnail"),
                # A hivatalos Windy visszajátszó (timelapse) beágyazó URL-je,
                # csúszkával - ezt tudja a weboldal iframe-be tenni.
                "player_embed": player_embed,
            })
        except Exception as e:
            cam_id = cam.get("webcamId", "ismeretlen")
            print(f"   ⚠️  Kamera #{cam_id} feldolgozása sikertelen, kihagyva: {e}")

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
