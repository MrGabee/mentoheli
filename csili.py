"""
🎭 Csili Művelődési Központ (Pesterzsébet) – programok
Adatforrás: a csili.hu eseménynaptárának nyilvános REST API-ja
(The Events Calendar: /wp-json/tribe/events/v1/events)
Csak a figyelt kategóriák eseményeit adja vissza.
Futtatva: minden esemény külön Facebook posztot kap, amikor a következő
HORIZONT_NAP napba kerül (az újonnan feltett is), és a kiposztolt események
előtti napon reggel egy összefoglaló emlékeztető is kimegy.
A posztok POSZT_ORA_TOL és POSZT_ORA_IG között, futásonként egyesével
mennek ki (félóránként), hogy ne egyszerre zúduljanak az oldalra.
"""

import os
import re
import json
import html
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from poszt_valtozatos import Stilus

MAGYAR_TZ = ZoneInfo("Europe/Budapest")

MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")

# ⬇️⬇️⬇️ ITT KAPCSOLOD KI/BE AZ AUTOMATA FACEBOOK-POSZTOLÁST ⬇️⬇️⬇️
FACEBOOK_POSZTOLAS_AKTIV = True

ALLAPOT_FAJL = "csili_allapot.json"

# Az eseményleírásból legfeljebb ennyi karakter kerül a posztba
MAX_LEIRAS = 350

# Ennyi nappal előre posztolja ki az eseményeket
HORIZONT_NAP = 14

# Naponta legfeljebb egy Csili-poszt megy ki (új esemény vagy emlékeztető),
# az új esemény helyi idő szerint ebben a sávban
POSZT_ORA_TOL = 17
POSZT_ORA_IG = 21

# Az emlékeztető hány nappal az esemény előtt, és helyi idő szerint
# legkorábban hány órakor menjen ki
EMLEKEZTETO_NAPPAL_ELOTTE = 1
EMLEKEZTETO_ORA = 9

API_URL = "https://www.csili.hu/wp-json/tribe/events/v1/events"

# A figyelt kategóriák (a csili.hu/esemenyek/category/<slug>/ oldalak)
KATEGORIAK = {
    "szinhaz":           "🎭",
    "koncert":           "🎵",
    "rendezveny":        "🎉",
    "csaladi":           "👨‍👩‍👧",
    "kiallitas":         "🖼️",
    "ismeretterjesztes": "📚",
}
KATEGORIA_NEV = {
    "szinhaz": "Színház", "koncert": "Koncert", "rendezveny": "Rendezvény",
    "csaladi": "Családi program", "kiallitas": "Kiállítás",
    "ismeretterjesztes": "Ismeretterjesztés",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (mentoheli csili figyelo)"}


def _esemeny(e):
    slugok = [k.get("slug", "") for k in e.get("categories") or []]
    figyelt = [s for s in slugok if s in KATEGORIAK]
    if not figyelt:
        return None
    venue = e.get("venue") or {}
    return {
        "id":      e.get("id"),
        "cim":     html.unescape(e.get("title") or "").strip(),
        "link":    e.get("url") or "",
        "kezdes":  datetime.fromisoformat(e["start_date"]),
        "veg":     datetime.fromisoformat(e["end_date"]) if e.get("end_date") else None,
        "hely":    html.unescape(venue.get("venue") or "") if isinstance(venue, dict) else "",
        "jel":     KATEGORIAK[figyelt[0]],
        "kategoria": figyelt[0],
        "leiras":  _tiszta(e.get("description") or ""),
        "ar":      html.unescape(e.get("cost") or ""),
    }


def _tiszta(szoveg):
    """HTML-címkék és entitások eltávolítása."""
    szoveg = re.sub(r"<[^>]+>", " ", szoveg)
    return " ".join(html.unescape(szoveg).split())


def esemenyek(tol, ig):
    """A [tol, ig] napok között KEZDŐDŐ figyelt események, időrendben.
    tol, ig: date. Hiba esetén None."""
    params = {
        "start_date": f"{tol.isoformat()} 00:00:00",
        "end_date":   f"{ig.isoformat()} 23:59:59",
        "per_page":   50,
    }
    url, lista = API_URL, []
    try:
        for _ in range(40):  # legfeljebb 2000 esemény
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                print(f"  ⚠️ Csili API HTTP {r.status_code}")
                return None
            adat = r.json()
            for e in adat.get("events", []):
                x = _esemeny(e)
                if x and tol <= x["kezdes"].date() <= ig:
                    lista.append(x)
            url, params = adat.get("next_rest_url"), None
            if not url:
                break
    except Exception as ex:
        print(f"  ❌ Csili API: {ex}")
        return None
    lista.sort(key=lambda x: x["kezdes"])
    return lista


WAI = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]


def facebook_szoveg(e):
    st = Stilus("csili")
    k = e["kezdes"]
    ido = f"{k.strftime('%Y.%m.%d.')} ({WAI[k.weekday()]}) {k.strftime('%H:%M')}"
    if e["veg"] and e["veg"].date() != k.date():
        ido = f"{k.strftime('%Y.%m.%d.')} – {e['veg'].strftime('%Y.%m.%d.')}"
    leiras = e["leiras"]
    if len(leiras) > MAX_LEIRAS:
        leiras = leiras[:MAX_LEIRAS].rsplit(" ", 1)[0] + "…"

    sorok = [st.cim, st.vonal(), "", st.bevezeto, "",
             f"{e['jel']} {e['cim']}",
             f"🏷️ {KATEGORIA_NEV.get(e['kategoria'], '')}",
             f"📅 {ido}"]
    if e["hely"]:
        sorok.append(f"📍 {e['hely']}, Budapest XX., Baross utca 55.")
    if e["ar"]:
        sorok.append(f"🎟️ {e['ar']}")
    if leiras:
        sorok += ["", leiras]
    sorok += ["", f"🔗 Részletek: {e['link']}"]
    if st.zaro:
        sorok += ["", st.zaro]
    sorok.append("#Csili #Pesterzsébet #programajánló")
    return "\n".join(sorok)


def facebook_poszt_kuldese(szoveg):
    """Szöveges poszt a Facebook Oldalra a Make.com webhookon keresztül."""
    if not MAKE_WEBHOOK_URL:
        print("  ⚠️  Nincs beállítva MAKE_WEBHOOK_URL - Facebook-posztolás kihagyva.")
        return False
    try:
        resp = requests.post(MAKE_WEBHOOK_URL, json={"message": szoveg}, timeout=20)
        if resp.status_code == 200:
            print("  ✅ Facebook poszt elküldve (Make.com-on keresztül).")
            return True
        print(f"  ⚠️  Facebook poszt sikertelen (HTTP {resp.status_code}): {resp.text[:300]}")
        return False
    except Exception as ex:
        print(f"  ⚠️  Facebook poszt hiba: {ex}")
        return False


def emlekezteto_szoveg(lista):
    st = Stilus("csili_emlekezteto")
    sorok = [st.cim, st.vonal(), "", st.bevezeto, ""]
    for e in lista:
        k = e["kezdes"]
        sorok.append(f"{e['jel']} {k.strftime('%m.%d.')} {WAI[k.weekday()]} {k.strftime('%H:%M')} – {e['cim']}")
        sorok.append(f"   🔗 {e['link']}")
    sorok += ["", "📍 Csili Művelődési Központ, Budapest XX., Baross utca 55."]
    if st.zaro:
        sorok += ["", st.zaro]
    sorok.append("#Csili #Pesterzsébet #emlékeztető")
    return "\n".join(sorok)


def betolt_allapot():
    try:
        with open(ALLAPOT_FAJL, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    most = datetime.now(MAGYAR_TZ)
    ma = most.date()
    print(f"🎭 Csili figyelő – {most.strftime('%Y.%m.%d %H:%M:%S')}")
    lista = esemenyek(ma, ma + timedelta(days=HORIZONT_NAP))
    if lista is None:
        print("⚠️ A Csili oldala nem elérhető, az állapot változatlan marad.")
        return

    allapot = betolt_allapot()
    # {esemény id: a kiposztolás napja}
    bejelentett  = {int(k): v for k, v in (allapot.get("bejelentett") or {}).items()} \
        if isinstance(allapot.get("bejelentett"), dict) else {}
    emlekeztetve = set(allapot.get("emlekeztetve", []))
    # A legutóbbi Csili-poszt napja: naponta legfeljebb egy megy ki
    mai_poszt = allapot.get("utolso_poszt_nap") or max(bejelentett.values(), default="")

    # Ami még előttünk van és nem posztoltuk ki, a legkorábbi elöl
    varo = [e for e in lista
            if e["id"] not in bejelentett
            and e["kezdes"].replace(tzinfo=MAGYAR_TZ) > most]
    print(f"📊 Esemény a következő {HORIZONT_NAP} napban: {len(lista)}, kiposztolásra vár: {len(varo)}")

    # ⏰ Emlékeztető a kiposztolt eseményekről, előtte való nap reggel.
    # Ha ma esedékes, ez a nap egyetlen Csili-posztja.
    cel_nap = ma + timedelta(days=EMLEKEZTETO_NAPPAL_ELOTTE)
    esedekes = [e for e in lista
                if e["id"] in bejelentett and e["id"] not in emlekeztetve
                and e["kezdes"].date() == cel_nap
                # ha csak ma posztoltuk ki, felesleges ma emlékeztetni
                and bejelentett[e["id"]] != ma.isoformat()]

    if mai_poszt == ma.isoformat():
        print("✋ Ma már ment ki Csili-poszt, holnap jön a következő.")
    elif esedekes:
        if most.hour >= EMLEKEZTETO_ORA:
            szoveg = emlekezteto_szoveg(esedekes)
            print("\n" + szoveg + "\n")
            if not FACEBOOK_POSZTOLAS_AKTIV or facebook_poszt_kuldese(szoveg):
                emlekeztetve |= {e["id"] for e in esedekes}
                mai_poszt = ma.isoformat()
        else:
            print("⏰ Ma emlékeztető megy ki, új eseményt nem posztol.")
    elif varo and POSZT_ORA_TOL <= most.hour < POSZT_ORA_IG:
        e = varo[0]
        szoveg = facebook_szoveg(e)
        print("\n" + szoveg + "\n")
        if not FACEBOOK_POSZTOLAS_AKTIV or facebook_poszt_kuldese(szoveg):
            bejelentett[e["id"]] = ma.isoformat()
            mai_poszt = ma.isoformat()
    elif varo:
        print("🌙 Posztolási sávon kívül - most nem posztol.")

    # Az elmúlt események kikerülnek az állapotból
    aktualis = {e["id"] for e in lista}
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump({
            "bejelentett":  {str(k): v for k, v in bejelentett.items() if k in aktualis},
            "emlekeztetve": sorted(emlekeztetve & aktualis),
            "utolso_poszt_nap": mai_poszt,
        }, f)
    print("💾 Állapot mentve. ✅ Kész.")


if __name__ == "__main__":
    main()
