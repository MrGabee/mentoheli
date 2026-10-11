"""
🌙 Esti időjárás holnapra – Csepel (Open-Meteo előrejelzés)
"""

import requests
from datetime import timedelta

from poszt_valtozatos import Stilus

URL = "https://api.open-meteo.com/v1/forecast"
CSEPEL = {"latitude": 47.43, "longitude": 19.07}

NAPOK = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]

# WMO időjárás-kódok
KODOK = [
    ((0,),            "☀️", "derült, napos idő"),
    ((1, 2),          "🌤️", "többnyire napos, néhol felhős"),
    ((3,),            "☁️", "borult, felhős idő"),
    ((45, 48),        "🌫️", "ködös idő"),
    ((51, 53, 55),    "🌦️", "szitáló eső"),
    ((56, 57, 66, 67), "🧊", "ónos eső"),
    ((61, 63),        "🌧️", "eső"),
    ((65,),           "🌧️", "erős eső"),
    ((71, 73, 75, 77), "🌨️", "havazás"),
    ((80, 81, 82),    "🌦️", "záporok"),
    ((85, 86),        "🌨️", "hózáporok"),
    ((95, 96, 99),    "⛈️", "zivatar"),
]


def kod_szoveg(kod):
    for kodok, jel, nev in KODOK:
        if kod in kodok:
            return jel, nev
    return "🌡️", "változékony idő"


def tanacsok(d):
    t = []
    if d["eso"] >= 50:
        t.append("☂️ Esernyő ne maradjon otthon!")
    if d["min"] <= 0:
        t.append("🧊 Reggel fagyhat, autósok, kaparót elő!")
    elif d["min"] <= 6:
        t.append("🧥 Reggel hűvös lesz, érdemes rétegesen öltözni.")
    if d["max"] >= 30:
        t.append("🥤 Kánikula: sok folyadék, árnyék, naptej!")
    if d["szel"] >= 40:
        t.append("💨 Erős szél várható, figyeljetek a kint hagyott tárgyakra.")
    if not t:
        t.append("😊 Kellemes napnak ígérkezik, jó program lehet egy séta a Duna-parton.")
    return t


def lekerdez(holnap):
    try:
        r = requests.get(URL, timeout=20, params=dict(CSEPEL,
            daily="weathercode,temperature_2m_max,temperature_2m_min,"
                  "precipitation_probability_max,windspeed_10m_max,sunrise,sunset",
            timezone="Europe/Budapest", start_date=holnap.isoformat(), end_date=holnap.isoformat()))
        if r.status_code != 200:
            print(f"  ⚠️ Open-Meteo HTTP {r.status_code}")
            return None
        d = r.json()["daily"]
        return {
            "kod": d["weathercode"][0], "max": round(d["temperature_2m_max"][0]),
            "min": round(d["temperature_2m_min"][0]),
            "eso": d["precipitation_probability_max"][0] or 0,
            "szel": round(d["windspeed_10m_max"][0] or 0),
            "kel": d["sunrise"][0][11:16], "nyugszik": d["sunset"][0][11:16],
        }
    except Exception as ex:
        print(f"  ❌ Open-Meteo: {ex}")
        return None


def szoveg(nap, adat=None):
    holnap = nap + timedelta(days=1)
    d = adat or lekerdez(holnap)
    if not d:
        return None
    jel, nev = kod_szoveg(d["kod"])
    st = Stilus("esti_idojaras", nap.isoformat())
    sorok = [st.cim, f"📅 Holnap, {holnap.strftime('%m.%d.')} ({NAPOK[holnap.weekday()]})", st.vonal(), "",
             st.bevezeto, "",
             f"{jel} {nev[0].upper() + nev[1:]}",
             f"🌡️ {d['min']}° és {d['max']}° között",
             f"💧 Csapadék esélye: {d['eso']}%",
             f"💨 Szél: legfeljebb {d['szel']} km/h",
             f"🌅 Napkelte {d['kel']}, 🌇 napnyugta {d['nyugszik']}",
             ""]
    sorok += tanacsok(d)
    sorok += ["", "🌙 Jó éjszakát mindenkinek!", "ℹ️ Előrejelzés: Open-Meteo"]
    if st.zaro:
        sorok.append(st.zaro)
    sorok.append("#időjárás #Csepel #Pesterzsébet #Szigetszentmiklós")
    return "\n".join(sorok)
