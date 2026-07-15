"""
🚗 WAZE BALESET-FIGYELŐ – BUDAPEST (hivatalos embed.waze.com iframe)

Forrás: https://embed.waze.com/iframe - ez a Google/Waze hivatalosan
dokumentált, kulcs nélküli beágyazási terméke (developers.google.com/waze/iframe),
NEM egy nem hivatalos, belső API.

Módszer:
 1. Playwright-tal betöltjük az iframe-et Budapest egyes "csempéire" (zoom=12,
    mert kisebb zoomnál a jelölők klaszterekbe (csoportokba) vonódnak össze).
 2. A jelölők (.wm-alert-icon) CSS-osztályneve elárulja a típust
    (pl. wm-alert-icon--accident).
 3. A jelölő pixel-pozíciójából (translate3d) szabványos Web Mercator
    matekkal kiszámoljuk a valós GPS-koordinátát - NEM képfelismerés,
    hanem nyilvános, dokumentált vetítési képlet.

TESZT MÓD: mivel még nem láttunk élő "accident" típusú jelölőt, a script
minden talált típust logol is, hogy pontosítani tudjuk a szűrést.
"""

import os
import json
import hashlib
import smtplib
import math
from email.mime.text import MIMEText
from datetime import datetime
from playwright.sync_api import sync_playwright

# Budapest határoló téglalapja
TERULET_HATAR = {"lonMin": 18.92, "lonMax": 19.33, "latMin": 47.35, "latMax": 47.61}
CSEMPE_OSZLOPOK = 2
CSEMPE_SOROK = 2
ZOOM = 12

ALLAPOT_FAJL = "waze_budapest_allapot.json"

EMAIL_KULDO   = os.environ.get("EMAIL_KULDO", "")
EMAIL_JELSZO  = os.environ.get("EMAIL_JELSZO", "")
EMAIL_CIMZETT = os.environ.get("EMAIL_CIMZETT_WAZE", "")

TESZT_MOD = os.environ.get("TESZT_MOD", "0") == "1"

# Csak ezekre a típusokra figyelünk - "accident" karakterláncot tartalmazó
# osztályneveket keresünk, hogy rugalmasak legyünk, ha több accident-alfaj van
# (pl. wm-alert-icon--accident-major, --accident-minor).
FIGYELT_TIPUS_KULCSSZO = "accident"


def generalCsempek():
    h = TERULET_HATAR
    lon_lepes = (h["lonMax"] - h["lonMin"]) / CSEMPE_OSZLOPOK
    lat_lepes = (h["latMax"] - h["latMin"]) / CSEMPE_SOROK

    csempek = []
    for col in range(CSEMPE_OSZLOPOK):
        for row in range(CSEMPE_SOROK):
            lon_min = h["lonMin"] + col * lon_lepes
            lon_max = lon_min + lon_lepes
            lat_min = h["latMin"] + row * lat_lepes
            lat_max = lat_min + lat_lepes
            kozep_lon = (lon_min + lon_max) / 2
            kozep_lat = (lat_min + lat_max) / 2
            csempek.append({"lat": kozep_lat, "lon": kozep_lon})
    return csempek


def px_from_latlon(lat, lon, zoom):
    world = 256 * (2 ** zoom)
    x = (lon + 180) / 360 * world
    lat_rad = math.radians(lat)
    merc_n = math.log(math.tan(math.pi / 4 + lat_rad / 2))
    y = (0.5 - merc_n / (2 * math.pi)) * world
    return x, y


def latlon_from_px(px, py, zoom):
    world = 256 * (2 ** zoom)
    lon = px / world * 360 - 180
    n = math.pi - 2 * math.pi * py / world
    lat = math.degrees(math.atan(0.5 * (math.exp(n) - math.exp(-n))))
    return lat, lon


def csempe_feldolgozasa(page, csempe):
    url = f"https://embed.waze.com/iframe?zoom={ZOOM}&lat={csempe['lat']}&lon={csempe['lon']}&pin=1&desc=1"
    print(f"🌐 Csempe betöltése: lat={csempe['lat']:.4f}, lon={csempe['lon']:.4f}")

    try:
        page.goto(url, wait_until="load", timeout=30000)
    except Exception as e:
        print(f"  ⚠️ Betöltési hiba, újrapróbálkozás: {e}")
        page.goto(url, wait_until="load", timeout=30000)

    page.wait_for_timeout(3000)

    adat = page.evaluate("""
        () => {
            const mapDiv = document.querySelector('.wm-map__leaflet');
            if (!mapDiv) return null;
            const rect = mapDiv.getBoundingClientRect();
            const markerek = document.querySelectorAll('.leaflet-marker-icon.wm-alert-icon');

            const eredmeny = [];
            markerek.forEach(m => {
                const stilus = m.getAttribute('style') || '';
                const match = stilus.match(/translate3d\\(([\\d.-]+)px,\\s*([\\d.-]+)px/);
                if (!match) return;

                const tipus = Array.from(m.classList).find(c =>
                    c.startsWith('wm-alert-icon--') &&
                    c.indexOf('zoom') === -1 &&
                    c.indexOf('badge') === -1 &&
                    c !== 'wm-alert-icon--hazard'
                );

                eredmeny.push({
                    tipus: tipus || 'ismeretlen',
                    offsetX: parseFloat(match[1]),
                    offsetY: parseFloat(match[2])
                });
            });

            return { containerSzelesseg: rect.width, containerMagassag: rect.height, markerek: eredmeny };
        }
    """)

    if not adat:
        return []

    kozep_px_x, kozep_px_y = px_from_latlon(csempe["lat"], csempe["lon"], ZOOM)
    top_left_x = kozep_px_x - adat["containerSzelesseg"] / 2
    top_left_y = kozep_px_y - adat["containerMagassag"] / 2

    esemenyek = []
    for m in adat["markerek"]:
        abs_x = top_left_x + m["offsetX"]
        abs_y = top_left_y + m["offsetY"]
        lat, lon = latlon_from_px(abs_x, abs_y, ZOOM)
        esemenyek.append({"tipus": m["tipus"], "lat": round(lat, 5), "lon": round(lon, 5)})

    return esemenyek


def osszes_csempe_lekerdezese():
    csempek = generalCsempek()
    minden_esemeny = {}
    tipus_eloszlas = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1200, "height": 700},
        )
        page = context.new_page()

        for csempe in csempek:
            try:
                esemenyek = csempe_feldolgozasa(page, csempe)
                for e in esemenyek:
                    tipus_eloszlas[e["tipus"]] = tipus_eloszlas.get(e["tipus"], 0) + 1
                    kulcs = hashlib.md5(f"{e['tipus']}|{round(e['lat'],4)}|{round(e['lon'],4)}".encode()).hexdigest()[:12]
                    minden_esemeny[kulcs] = e
            except Exception as ex:
                print(f"  ❌ Hiba a csempénél: {ex}")

        browser.close()

    print(f"📊 Típus-eloszlás (összes csempe, összes kategória): {tipus_eloszlas}")
    return minden_esemeny


def balesetek_szurese(minden_esemeny):
    return {k: v for k, v in minden_esemeny.items() if FIGYELT_TIPUS_KULCSSZO in v["tipus"].lower()}


def allapot_betoltes():
    if os.path.exists(ALLAPOT_FAJL):
        try:
            with open(ALLAPOT_FAJL, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def allapot_mentes(allapot):
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=2)


def email_kuldes(uj_esemenyek, eltunt_kulcsok, regi_allapot):
    if not (EMAIL_KULDO and EMAIL_JELSZO and EMAIL_CIMZETT):
        print("⚠️ Hiányzó e-mail környezeti változók - kihagyva.")
        return

    ido = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    targy = f"🚗 Waze baleset (Budapest) - {len(uj_esemenyek)} új, {len(eltunt_kulcsok)} megszűnt | {ido}"

    sorok = [f"Waze baleset-figyelő (Budapest) - {ido}", ""]

    if uj_esemenyek:
        sorok.append(f"ÚJ BALESETEK ({len(uj_esemenyek)}):")
        for kulcs, e in uj_esemenyek.items():
            gmaps = f"https://www.google.com/maps?q={e['lat']},{e['lon']}"
            sorok.append(f"• {e['tipus']} - {e['lat']}, {e['lon']}")
            sorok.append(f"   {gmaps}")
        sorok.append("")

    if eltunt_kulcsok:
        sorok.append(f"MEGSZŰNT BALESETEK ({len(eltunt_kulcsok)}):")
        for kulcs in eltunt_kulcsok:
            regi = regi_allapot.get(kulcs, {})
            sorok.append(f"• {regi.get('tipus', '?')} - {regi.get('lat', '?')}, {regi.get('lon', '?')}")
        sorok.append("")

    szoveg = "\n".join(sorok)

    try:
        msg = MIMEText(szoveg, "plain", "utf-8")
        msg["Subject"] = targy
        msg["From"] = EMAIL_KULDO
        msg["To"] = EMAIL_CIMZETT

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_KULDO, EMAIL_JELSZO)
            server.sendmail(EMAIL_KULDO, [EMAIL_CIMZETT], msg.as_string())
        print(f"📧 E-mail elküldve.")
    except Exception as ex:
        print(f"❌ E-mail hiba: {ex}")


def main():
    minden_esemeny = osszes_csempe_lekerdezese()

    if TESZT_MOD:
        print(f"🧪 TESZT MÓD - nem küld e-mailt, csak logol.")
        print(f"Összes jelölő (minden típus): {len(minden_esemeny)}")
        balesetek = balesetek_szurese(minden_esemeny)
        print(f"Ebből 'accident' típusú: {len(balesetek)}")
        for k, v in balesetek.items():
            print(f"  {v}")
        return

    balesetek = balesetek_szurese(minden_esemeny)
    print(f"🚗 Talált baleset-jelölők: {len(balesetek)}")

    regi_allapot = allapot_betoltes()
    aktualis_kulcsok = set(balesetek.keys())
    regi_kulcsok = set(regi_allapot.keys())

    uj_kulcsok = aktualis_kulcsok - regi_kulcsok
    eltunt_kulcsok = regi_kulcsok - aktualis_kulcsok

    uj_esemenyek = {k: balesetek[k] for k in uj_kulcsok}

    if uj_esemenyek or eltunt_kulcsok:
        email_kuldes(uj_esemenyek, eltunt_kulcsok, regi_allapot)
    else:
        print("✅ Nincs változás.")

    uj_allapot = {k: balesetek[k] for k in aktualis_kulcsok}
    allapot_mentes(uj_allapot)


if __name__ == "__main__":
    main()
