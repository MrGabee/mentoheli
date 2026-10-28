"""
🛰️ Mentőhelikopter pozíciók – nyílt, közösségi ADS-B forrásokból
(adsb.lol, tartalék: adsb.fi). Amíg a gép a levegőben van, minden futáskor
elmentem a helyzetét, így a felszállás és a leszállás levelébe bekerülhet
a felszállási pont, az utolsó ismert pont, az útvonal és egy kis térkép.

Az utolsó ismert pont nem mindig a pontos leszállóhely: alacsonyan a jel
gyakran elvész, ezért pár száz méterrel arrébb lehet.
"""

import io
import math
import time

import requests

UA = {"User-Agent": "mentoheli-monitor/1.0 (github.com/MrGabee)"}
FORRASOK = [
    "https://api.adsb.lol/v2/reg/{reg}",
    "https://opendata.adsb.fi/api/v2/registration/{reg}",
]
UJ_UT_PERC = 30          # ennyi szünet után új útnak számít
MAX_PONT = 400
CSEPEL = (47.4245, 19.0660)


# ── pozíció és nyomvonal ─────────────────────────────────────────
def lekerdez(reg):
    """A gép mostani helyzete: dict vagy None (földön van / nincs adat)."""
    for minta in FORRASOK:
        try:
            r = requests.get(minta.format(reg=reg.upper()), headers=UA, timeout=8)
            if r.status_code != 200:
                continue
            for ac in r.json().get("ac") or []:
                if ac.get("lat") is None or ac.get("lon") is None:
                    continue
                alt = ac.get("alt_baro")
                return {
                    "lat": round(float(ac["lat"]), 5),
                    "lon": round(float(ac["lon"]), 5),
                    "alt_m": 0 if alt == "ground" or alt is None else round(float(alt) * 0.3048),
                    "kmh": round(float(ac.get("gs") or 0) * 1.852),
                    "foldon": alt == "ground",
                }
            return None
        except Exception as ex:
            print(f"  ⚠️ ADS-B hiba ({reg}): {ex}")
    return None


def frissit(nyom, reg):
    """Egy gép nyomvonalának frissítése. nyom: {reg: {"pontok": [[ts, lat, lon, alt_m, kmh], ...]}}"""
    p = lekerdez(reg)
    if not p:
        return
    most = int(time.time())
    ut = nyom.setdefault(reg, {"pontok": []})
    lezarva = ut.get("lezarva", 0)
    if (ut["pontok"] and most - ut["pontok"][-1][0] > UJ_UT_PERC * 60) or (lezarva and most > lezarva + 300):
        ut["pontok"] = []
        ut.pop("lezarva", None)
    if not ut["pontok"] or ut["pontok"][-1][1:3] != [p["lat"], p["lon"]]:
        ut["pontok"].append([most, p["lat"], p["lon"], p["alt_m"], p["kmh"]])
        ut["pontok"] = ut["pontok"][-MAX_PONT:]
        print(f"  🛰️ {reg}: {p['lat']}, {p['lon']} · {p['alt_m']} m · {p['kmh']} km/h")


def lezar(nyom, reg):
    """Leszállás után: a következő útnál új nyomvonal indul."""
    if reg in nyom and not nyom[reg].get("lezarva"):
        nyom[reg]["lezarva"] = int(time.time())


def aktualis_ut(nyom, reg, max_perc=UJ_UT_PERC):
    """A gép friss útjának pontjai (üres, ha régi vagy nincs)."""
    pontok = (nyom.get(reg) or {}).get("pontok") or []
    if pontok and time.time() - pontok[-1][0] <= max_perc * 60:
        return pontok
    return []


def tavolsag_km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def statisztika(pontok):
    if len(pontok) < 2:
        return {}
    ut = sum(tavolsag_km(pontok[i][1:3], pontok[i + 1][1:3]) for i in range(len(pontok) - 1))
    return {
        "km": round(ut, 1),
        "max_m": max(p[3] for p in pontok),
        "max_kmh": max(p[4] for p in pontok),
    }


# ── hely szövegesen ──────────────────────────────────────────────
def hely_neve(lat, lon):
    """Pl. "Budapest XXI. kerület, Kossuth Lajos utca" (Nominatim)."""
    try:
        r = requests.get("https://nominatim.openstreetmap.org/reverse",
                         params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 17,
                                 "accept-language": "hu"}, headers=UA, timeout=8)
        c = r.json().get("address", {})
        telepules = c.get("city") or c.get("town") or c.get("village") or c.get("municipality") or ""
        resz = c.get("city_district") or c.get("suburb") or ""
        ut = c.get("road") or c.get("hamlet") or ""
        return ", ".join(x for x in (" ".join(y for y in (telepules, resz) if y), ut) if x)
    except Exception as ex:
        print(f"  ⚠️ Nominatim hiba: {ex}")
        return ""


def korhaz_kozel(lat, lon, sugar=500):
    """A közeli kórház vagy helikopter-leszálló neve (Overpass), vagy ""."""
    q = (f'[out:json][timeout:10];(nwr(around:{sugar},{lat},{lon})[amenity=hospital];'
         f'nwr(around:300,{lat},{lon})[aeroway=helipad];);out tags center 5;')
    try:
        r = requests.post("https://overpass-api.de/api/interpreter", data={"data": q}, headers=UA, timeout=12)
        elemek = r.json().get("elements", [])
        for e in sorted(elemek, key=lambda e: e.get("tags", {}).get("amenity") != "hospital"):
            nev = e.get("tags", {}).get("name")
            if nev:
                return nev
        return "helikopter-leszálló" if elemek else ""
    except Exception as ex:
        print(f"  ⚠️ Overpass hiba: {ex}")
        return ""


def gmaps(lat, lon):
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"


# ── térképkép (OpenStreetMap csempékből) ─────────────────────────
def _csempe_xy(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def terkep_png(pontok, szel=600, mag=320):
    """PNG bájtok: útvonal, zöld pont a felszállásnál, piros az utolsó pontnál. None, ha nem megy."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    if not pontok:
        return None
    try:
        lats = [p[1] for p in pontok]
        lons = [p[2] for p in pontok]
        z = 16
        while z > 6:
            x1, y1 = _csempe_xy(max(lats), min(lons), z)
            x2, y2 = _csempe_xy(min(lats), max(lons), z)
            if (x2 - x1) * 256 < szel - 80 and (y2 - y1) * 256 < mag - 80:
                break
            z -= 1
        kx, ky = _csempe_xy((max(lats) + min(lats)) / 2, (max(lons) + min(lons)) / 2, z)
        bal, fent = kx * 256 - szel / 2, ky * 256 - mag / 2
        kep = Image.new("RGB", (szel, mag), "#e5e3df")
        for tx in range(int(bal // 256), int((bal + szel) // 256) + 1):
            for ty in range(int(fent // 256), int((fent + mag) // 256) + 1):
                r = requests.get(f"https://tile.openstreetmap.org/{z}/{tx}/{ty}.png", headers=UA, timeout=8)
                if r.status_code == 200:
                    kep.paste(Image.open(io.BytesIO(r.content)).convert("RGB"),
                              (int(tx * 256 - bal), int(ty * 256 - fent)))
        rajz = ImageDraw.Draw(kep)

        def xy(p):
            x, y = _csempe_xy(p[1], p[2], z)
            return x * 256 - bal, y * 256 - fent

        if len(pontok) > 1:
            rajz.line([xy(p) for p in pontok], fill="#dc2626", width=4)
        for p, szin in ((pontok[0], "#16a34a"), (pontok[-1], "#dc2626")):
            x, y = xy(p)
            rajz.ellipse((x - 8, y - 8, x + 8, y + 8), fill=szin, outline="white", width=3)
        rajz.rectangle((szel - 150, mag - 16, szel, mag), fill="white")
        rajz.text((szel - 146, mag - 14), "© OpenStreetMap", fill="#555555")
        buf = io.BytesIO()
        kep.save(buf, "PNG")
        return buf.getvalue()
    except Exception as ex:
        print(f"  ⚠️ Térképkép hiba: {ex}")
        return None
