"""
Útinform (Magyar Közút) Webkamerák lekérdezés - Magyarországi közúti kamerák

Ez a script GitHub Actionben fut, szerver oldalon - itt nincs CORS
korlátozás, mert nem böngészőből, hanem szerverről indul a kérés.
(Böngészőből egyébként sem menne: az Útinform API-ja nem küld
Access-Control-Allow-Origin fejlécet idegen domainek felé, tehát a
weboldal saját maga nem tudná közvetlenül lekérdezni ezt az API-t -
ezért van szükség erre a szerveroldali köztes lépésre, pont úgy, mint
a windy-s fetch_windy_webcams.py esetében.)

FONTOS - MIÉRT PLAYWRIGHT ÉS NEM SIMA "requests":
Az első verzió sima `requests.get()`-tel hívta az API-t - ez helyben
(böngészőből) és a felderítéskor is működött, de GitHub Actionből futtatva
403 Forbidden-t adott vissza. Ez feltehetően bot-védelem: az útinform.hu
szűri a nem-valódi-böngésző kéréseket (más TLS/HTTP-ujjlenyomat, hiányzó
böngésző-fejlécek). A megoldás - ugyanaz a minta, mint a repóban már
meglévő bkk_kozut_playwright_monitor.py-nál -: egy VALÓDI, headless Chrome
böngészőt indítunk (Playwright), betöltjük vele az Útinform térkép-oldalát
(ettől valódi böngésző-munkamenet jön létre), és MAGÁBÓL AZ OLDAL
KONTEXTUSÁBÓL, egy page.evaluate()-be csomagolt fetch()-csel hívjuk az
API-t - ez ugyanaz a hívás, amit egy valódi látogató böngészője is
indítana, ezért nem szűri a bot-védelem.

Az eredményt egy statikus JSON fájlba menti, amit a weboldal
(magyar_webkamerak.html) egyszerű fetch()-csel tud beolvasni, API-kulcs
nélkül - a windy adatokkal együtt jelenítve meg, forrás-jelöléssel.

FORRÁS FELDERÍTÉSE (böngésző hálózati forgalom alapján):
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

from playwright.sync_api import sync_playwright

MAP_URL = "https://www.utinform.hu/hu/map"
API_URL = "https://www.utinform.hu/api/public/webcam/all"
OUTPUT_FILE = "windy/data/webcams_utinform.json"
IMAGE_BASE = "https://cdnuiwebcams.utinform.hu/webcamimages"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

MAX_PROBALKOZAS = 3


def fetch_utinform_features():
    print("🔍 Útinform közúti kamerák lekérdezése (Playwright, valódi böngészővel)...")

    utolso_hiba = None
    for probalkozas in range(1, MAX_PROBALKOZAS + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1400, "height": 1000},
                )
                page = context.new_page()

                print(f"🌐 Betöltés ({probalkozas}/{MAX_PROBALKOZAS}): {MAP_URL}")
                page.goto(MAP_URL, wait_until="load", timeout=30000)
                page.wait_for_timeout(2000)

                # Az API-hívást MAGÁBÓL AZ OLDAL KONTEXTUSÁBÓL indítjuk (nem
                # külön Python http-kliensből) - lásd a fenti modul-szintű
                # magyarázatot arról, hogy ez miért kerüli el a 403-at.
                result = page.evaluate(
                    """async (apiUrl) => {
                        try {
                            const res = await fetch(apiUrl, { headers: { 'Accept': 'application/json' } });
                            if (!res.ok) {
                                return { ok: false, status: res.status };
                            }
                            const data = await res.json();
                            return { ok: true, data };
                        } catch (e) {
                            return { ok: false, error: String(e) };
                        }
                    }""",
                    API_URL,
                )

                browser.close()

                if not result.get("ok"):
                    raise RuntimeError(
                        f"Az Útinform API hívása a böngésző-kontextusból sem sikerült "
                        f"(status={result.get('status')}, error={result.get('error')})."
                    )

                features = result["data"].get("features", [])
                print(f"   -> {len(features)} helyszín érkezett az API-ból.")
                return features

        except Exception as ex:
            utolso_hiba = ex
            print(f"  ⚠️ Sikertelen próbálkozás ({probalkozas}/{MAX_PROBALKOZAS}): {ex}")
            if probalkozas < MAX_PROBALKOZAS:
                page_wait = 5 * probalkozas
                print(f"  ⏳ Várakozás {page_wait} másodpercet újrapróbálkozás előtt...")
                import time
                time.sleep(page_wait)

    raise RuntimeError(f"Az Útinform lekérdezés {MAX_PROBALKOZAS} próbálkozás után is sikertelen: {utolso_hiba}")


def main():
    try:
        features = fetch_utinform_features()
    except Exception as e:
        # Az útinform API/oldal időnként instabil / átmenetileg elérhetetlen
        # lehet - ilyenkor NEM írjuk felül a meglévő adatfájlt egy üressel,
        # inkább kilépünk hibával, hogy a weboldalon a korábbi (még mindig
        # jó) adat maradjon látható a következő sikeres futásig.
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
