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
        # A "country" paraméter a V3 API dokumentált paraméterei között
        # NEM szerepel - a korábbi teszt is megerősítette, hogy csendben
        # figyelmen kívül marad (nincs hiba, csak nem szűr vele).
        # A "nearby" paraméter dokumentált és működik: lat,lon,sugár(km).
        # Budapest körül 250 km-es sugár lefedi egész Magyarországot,
        # de belóg belőle egy kis szomszédos terület is - ezért lent
        # kliens oldalon még egyszer leszűrünk országkód szerint.
        "nearby": "47.1625,19.5033,250",
        "limit": 50,
        "include": "images,location",
    }
    headers = {"x-windy-api-key": API_KEY}

    response = requests.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()

    all_webcams = data.get("webcams", [])

    # Biztonsági háló: csak a ténylegesen magyarországi kamerákat tartjuk meg,
    # a nearby kör szélén becsúszó szomszédos országbelieket kiszűrjük.
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
