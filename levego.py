"""
🌫️ Levegőminőség és pollen – Csepel
Adatforrás: Open-Meteo Air Quality API (Copernicus CAMS előrejelzés),
ingyenes, kulcs nélkül. Csak akkor ad sort, ha valami figyelemre méltó:
rossz levegő, vagy legalább közepes pollenterhelés.
"""

import requests

URL = ("https://air-quality-api.open-meteo.com/v1/air-quality"
       "?latitude=47.42&longitude=19.07&timezone=Europe%2FBudapest&forecast_days=1"
       "&hourly=european_aqi,birch_pollen,grass_pollen,ragweed_pollen")

# (mező, név, közepes küszöb, magas küszöb) – pollenszem/m³
POLLENEK = [
    ("ragweed_pollen", "parlagfű", 10, 30),
    ("grass_pollen", "fűfélék", 20, 50),
    ("birch_pollen", "nyírfa", 30, 100),
]


def _napi_max(adat, mezo):
    """A nappali órák (7–21) legnagyobb értéke."""
    idok = adat.get("time", [])
    ertekek = adat.get(mezo, [])
    napi = [v for t, v in zip(idok, ertekek) if v is not None and 7 <= int(t[11:13]) <= 21]
    return max(napi) if napi else None


def sorok():
    try:
        adat = requests.get(URL, timeout=20).json()["hourly"]
    except Exception as e:
        print(f"  ⚠️ Levegőminőség nem elérhető: {e}")
        return []
    ki = []
    aqi = _napi_max(adat, "european_aqi")
    if aqi is not None and aqi >= 60:
        szint = "nagyon rossz" if aqi >= 80 else "rossz"
        ki.append(f"😷 Ma {szint} levegőminőség várható Csepelen (európai index: {round(aqi)}). "
                  "Érzékenyeknek, kisgyerekeseknek érdemes kevesebbet a szabadban lenni.")
    for mezo, nev, kozepes, magas in POLLENEK:
        v = _napi_max(adat, mezo)
        if v is None or v < kozepes:
            continue
        szint = "magas" if v >= magas else "közepes"
        ki.append(f"🤧 Pollen, {nev}: {szint} terhelés várható ({round(v)} szem/m³).")
    return ki
