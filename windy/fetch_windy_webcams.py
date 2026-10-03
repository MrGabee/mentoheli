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
import time
from datetime import datetime, timezone

import requests

API_KEY = os.environ.get("WINDY_API_KEY")
OUTPUT_FILE = "windy/data/webcams_hu.json"

# ld. windy_webcams_monitor.yml "cron" - ez a workflow 30 percenként fut
# (NEM percenként/önindító láncban, az a Waze-monitornál igaz, ez a komment
# korábban onnan lett átmásolva, félrevezetően), futásonként akár 24 külön
# kérést küldve a Windy szerverének (6 régió x max. 4 oldal). Ennek a 24
# kérésnek ÖNMAGÁBAN, 30 percre elosztva semmi köze a napi kvótához - a
# 2026.10. folyamán többször jelentkező HTTP 429-ek oka az volt, hogy ezt a
# 24 kérést EGYMÁS UTÁN, SZÜNET NÉLKÜL küldtük - ez egy rövid, másodperces
# "burst" rate-limitet is kiválthat, még egy amúgy alacsony, 30 perces
# átlagos terhelés mellett is. Ezért most minden kérés előtt egy rövid
# szünetet tartunk (ld. REQUEST_PACING_SECONDS), ÉS - mivel egy sporadikus,
# pillanatnyi Windy-oldali akadás/rate-limit NEM indokolja, hogy az egész
# futás "pirosra" fusson (ld. lejjebb: egy adott régió retry-jainak
# kimerülése esetén csak AZ a régió marad abbahagyva, a többi folytatódik) -
# a teljes futás csak akkor áll le hibával (exit 1), ha VÉGÜL egyetlen
# kamerát sem sikerült lekérdezni (ld. main() lentebb), hogy egy teljes
# Windy-kiesést még mindig jelezzen, de egy részleges/átmeneti akadást ne.
RETRYABLE_STATUS_CODES = {403, 429, 500, 502, 503, 504}
MAX_RETRIES = 4
RETRY_BASE_DELAY_SECONDS = 4
REQUEST_PACING_SECONDS = 1.5


def windy_get(url, params, headers):
    """Visszaadja a response-t, vagy None-t, ha MAX_RETRIES próbálkozás
    után sem sikerült - a hívó (fetch_hungarian_webcams()) ekkor NEM
    crashel, hanem lezárja az éppen aktuális régió lekérdezését, és megy a
    következő régióra (ld. ott a kommentet)."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        # Minden kérés előtt rövid szünet - ld. a fájl elején lévő komment
        # a "burst" rate-limit elkerüléséről.
        time.sleep(REQUEST_PACING_SECONDS)
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt == MAX_RETRIES:
                break
            delay = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            print(f"   ⚠️  Hálózati hiba (kísérlet {attempt}/{MAX_RETRIES}): {e} - újrapróbálás {delay}s múlva...")
            time.sleep(delay)
            continue

        if response.status_code in RETRYABLE_STATUS_CODES:
            if attempt == MAX_RETRIES:
                last_error = requests.exceptions.HTTPError(
                    f"HTTP {response.status_code} a {MAX_RETRIES}. próbálkozás után is"
                )
                break
            # Ha a Windy küld "Retry-After" fejlécet (429-nél gyakori), azt
            # vesszük figyelembe a saját exponenciális backoff helyett -
            # pontosabb, mint a találgatás.
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            except ValueError:
                delay = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            print(f"   ⚠️  HTTP {response.status_code} érkezett (kísérlet {attempt}/{MAX_RETRIES}) - valószínűleg a Windy szerver pillanatnyi akadása/rate-limitje, újrapróbálás {delay:.0f}s múlva...")
            time.sleep(delay)
            continue

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # Egyéb, nem a RETRYABLE_STATUS_CODES-ban szereplő hiba (pl.
            # 400/404) - ezt nem érdemes újrapróbálni, de a hívó itt is a
            # "csak ez a régió marad abbahagyva" ágra kerül.
            last_error = e
            break
        return response

    print(f"   ⚠️  Ez a kérés {MAX_RETRIES} próbálkozás után sem járt sikerrel ({last_error}) - ez a régió itt megszakad, a már begyűjtött kamerákkal folytatjuk a következővel.")
    return None

# A Windy API a régiókat angolul adja vissza - ez fordítja magyarra a
# weboldalon való megjelenítéshez. Ha egy régiónév nem szerepel itt,
# az eredeti angol marad (lásd translate_region lent).
REGION_TRANSLATIONS = {
    "Transdanubia": "Dunántúl",
    "Central Hungary": "Közép-Magyarország",
    "Great Plain and North": "Alföld és Észak-Magyarország",
}


def translate_region(region_name):
    if not region_name:
        return region_name
    return REGION_TRANSLATIONS.get(region_name, region_name)

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
            response = windy_get(url, params, headers)
            if response is None:
                # ld. windy_get() kommentje - ez a régió itt megszakad
                # (a már begyűjtött oldalaival), de a FUTÁS folytatódik a
                # következő régióval, nem crashel az egész script.
                print(f"   ⚠️  A '{region['name']}' régió lekérdezése idő előtt megszakadt - a már begyűjtött kamerákkal megyünk tovább.")
                break

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

    # A Windy saját katalógusában időnként UGYANAZ a fizikai kamera két
    # külön webcamId-vel is szerepel, azonos címmel és koordinátával
    # (pl. két "Abda: Bécs" bejegyzés). Az id-alapú deduplikálás ezeket
    # nem szűri ki, mert technikailag különböző ID-k - ezért itt még
    # egyszer, cím+koordináta alapján is deduplikálunk, az elsőt tartva meg.
    deduped_by_content = []
    seen_content_keys = set()
    for cam in hungarian_only:
        loc = cam.get("location", {}) or {}
        content_key = (
            cam.get("title", "").strip().lower(),
            round(loc.get("latitude", 0) or 0, 4),
            round(loc.get("longitude", 0) or 0, 4),
        )
        if content_key in seen_content_keys:
            continue
        seen_content_keys.add(content_key)
        deduped_by_content.append(cam)

    duplicates_removed = len(hungarian_only) - len(deduped_by_content)
    if duplicates_removed:
        print(f"   -> {duplicates_removed} valódi duplikátum (azonos cím+koordináta) eltávolítva.")

    print(f"   -> {len(all_webcams)} kamera a 250 km-es körben, ebből {len(deduped_by_content)} egyedi magyarországi.")

    if all_webcams and not hungarian_only:
        # Ha a szűrés váratlanul 0-t adna, valószínűleg a "country" mező
        # más formátumban jön vissza (pl. "Hungary" az "HU" helyett) -
        # ez segít kideríteni, mit kell a szűrőn pontosítani.
        print("   ⚠️  Egyetlen kamera sem maradt HU szűrés után - néhány nyers 'location' mező diagnosztikához:")
        for cam in all_webcams[:5]:
            print(f"      {cam.get('location')}")

    return {"webcams": deduped_by_content}


def main():
    print("🔍 Magyarországi webkamerák lekérdezése a Windy API-ból...")
    data = fetch_hungarian_webcams()
    webcams = data.get("webcams", [])
    print(f"   -> {len(webcams)} kamera található.")

    if not webcams:
        # Ha a fenti, régiónkénti türelem ellenére VÉGÜL egyetlen kamerát
        # sem sikerült lekérdezni (pl. teljes Windy-kiesés, vagy hibás/
        # lejárt API-kulcs), akkor NEM írjuk felül a meglévő adatfájlt egy
        # üres listával (ez elveszítené a korábbi, jó adatot) - ilyenkor a
        # futás tényleg hibával áll le (exit 1), hogy ez a VALÓDI probléma
        # még mindig jelzést kapjon, ellentétben egy csak részleges/
        # átmeneti akadással (ld. a fájl elején lévő komment).
        print("❌ HIBA: egyetlen kamerát sem sikerült lekérdezni (teljes Windy-kiesés vagy hibás API-kulcs lehet) - a meglévő adatfájlt NEM írjuk felül.")
        sys.exit(1)

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
                "region": translate_region(cam.get("location", {}).get("region")),
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
