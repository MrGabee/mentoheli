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
    params = {
        "country": "HU",
        "limit": 50,
        "include": "images,location",
    }
    headers = {"x-windy-api-key": API_KEY}

    response = requests.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()


def main():
    print("🔍 Magyarországi webkamerák lekérdezése a Windy API-ból...")
    data = fetch_hungarian_webcams()
    webcams = data.get("webcams", [])
    print(f"   -> {len(webcams)} kamera található.")

    # Csak a ténylegesen szükséges mezőket mentjük, hogy a fájl kicsi maradjon
    simplified = []
    for cam in webcams:
        simplified.append({
            "id": cam.get("webcamId"),
            "title": cam.get("title"),
            "city": cam.get("location", {}).get("city"),
            "region": cam.get("location", {}).get("region"),
            "latitude": cam.get("location", {}).get("latitude"),
            "longitude": cam.get("location", {}).get("longitude"),
            "image_preview": cam.get("images", {}).get("current", {}).get("preview"),
            "image_thumbnail": cam.get("images", {}).get("current", {}).get("thumbnail"),
        })

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
