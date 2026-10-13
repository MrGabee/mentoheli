"""
⚠️ Időjárási Riasztás Monitor – Budapest + Pest megye
Adatforrás: MeteoAlarm Atom feed (a HungaroMet hivatalos veszélyjelzései)
Szűrés: figyelt területek (Budapest, Pest megye), legalább sárga szint
Értesítés: Facebook poszt (Mr.Gabee oldal, Make.com webhookon keresztül)
Posztol, ha új riasztás jelenik meg, vagy egy meglévő szintje emelkedik.
"""

import os
import json
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from poszt_valtozatos import Stilus

# ─────────────────────────────────────────────
#  🕐  MAGYAR IDŐZÓNA (UTC+2, GitHub Actions UTC-t használ)
# ─────────────────────────────────────────────
MAGYAR_TZ = timezone(timedelta(hours=2))

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")

# ⬇️⬇️⬇️ ITT KAPCSOLOD KI/BE AZ AUTOMATA FACEBOOK-POSZTOLÁST ⬇️⬇️⬇️
# True  = automatikusan posztol a Facebook Oldalra (Make.com webhook)
# False = csak kiírja a naplóba, mit posztolna
FACEBOOK_POSZTOLAS_AKTIV = True

FEED_URL    = "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-hungary"
ALLAPOT_FAJL = "idojaras_riasztas_allapot.json"

# Figyelt területek (a feed területnevei között keresi, pontos szóra).
FIGYELT_TERULETEK = ["Budapest", "Pest"]

# Legalacsonyabb szint, amiről posztol: 2 = sárga, 3 = narancs, 4 = piros
MIN_SZINT = 2

SZINT_NEV = {
    2: ("🟡", "SÁRGA"),
    3: ("🟠", "NARANCS"),
    4: ("🔴", "PIROS"),
}

# MeteoAlarm awareness_type kódok → magyar név
TIPUS_NEV = {
    1:  ("💨", "Szél"),
    2:  ("❄️", "Hó, ónos eső"),
    3:  ("⛈️", "Zivatar"),
    4:  ("🌫️", "Köd"),
    5:  ("🌡️", "Hőség"),
    6:  ("🥶", "Hideg"),
    7:  ("🌊", "Parti esemény"),
    8:  ("🔥", "Erdőtűz"),
    9:  ("🏔️", "Lavina"),
    10: ("🌧️", "Eső"),
    12: ("🌊", "Árvíz"),
    13: ("🌧️", "Eső, árvíz"),
}

HEADERS = {"User-Agent": "Mozilla/5.0 (mentoheli riasztas monitor)"}


# ════════════════════════════════════════════
#  💾  ÁLLAPOT
# ════════════════════════════════════════════
def betolt_allapot():
    if os.path.exists(ALLAPOT_FAJL):
        try:
            with open(ALLAPOT_FAJL, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def ment_allapot(allapot):
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=2)


# ════════════════════════════════════════════
#  📡  FEED FELDOLGOZÁS
# ════════════════════════════════════════════
def _helyi_nev(tag):
    return tag.rsplit("}", 1)[-1]

def _mezok(entry):
    """Az entry közvetlen gyerekeinek szövege, névtér nélküli kulccsal."""
    m = {}
    for gyerek in entry:
        nev = _helyi_nev(gyerek.tag)
        if nev not in m:
            m[nev] = (gyerek.text or "").strip()
    return m

def _szam_elol(szoveg):
    """'3; orange; Severe' → 3, '1; wind' → 1."""
    talalat = re.match(r"\s*(\d+)", szoveg or "")
    return int(talalat.group(1)) if talalat else 0

def _ido(szoveg):
    try:
        return datetime.fromisoformat(szoveg.replace("Z", "+00:00"))
    except Exception:
        return None

def figyelt_terulet(terulet):
    for nev in FIGYELT_TERULETEK:
        if re.search(rf"(?<![\wÁÉÍÓÖŐÚÜŰáéíóöőúüű]){re.escape(nev)}(?![\wÁÉÍÓÖŐÚÜŰáéíóöőúüű])", terulet or ""):
            return True
    return False

def feldolgoz(xml_szoveg, most=None):
    """A feed XML-jéből a figyelt területek érvényes riasztásai."""
    most = most or datetime.now(timezone.utc)
    gyoker = ET.fromstring(xml_szoveg)
    riasztasok = []

    for entry in gyoker.iter():
        if _helyi_nev(entry.tag) != "entry":
            continue
        m = _mezok(entry)

        terulet = m.get("areaDesc", "")
        if not figyelt_terulet(terulet):
            continue

        szint = _szam_elol(m.get("awareness_level"))
        tipus = _szam_elol(m.get("awareness_type"))
        if szint < MIN_SZINT:
            continue

        lejar = _ido(m.get("expires", ""))
        if lejar and lejar < most:
            continue

        riasztasok.append({
            "terulet": "Pest megye" if terulet == "Pest" else terulet,
            "szint":   szint,
            "tipus":   tipus,
            "esemeny": m.get("event", ""),
            "kezdet":  m.get("onset", "") or m.get("effective", ""),
            "lejar":   m.get("expires", ""),
        })

    return riasztasok

def lekerdez():
    try:
        print(f"🌐 Lekérdezés: {FEED_URL}")
        r = requests.get(FEED_URL, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ HTTP {r.status_code}")
            return None
        riasztasok = feldolgoz(r.content)
        print(f"  📊 Figyelt területi riasztás: {len(riasztasok)}")
        return riasztasok
    except Exception as ex:
        print(f"  ❌ {ex}")
        return None


# ════════════════════════════════════════════
#  🔑  ÚJ / EMELKEDETT RIASZTÁSOK
# ════════════════════════════════════════════
def kulcs(r):
    """Ugyanaz a riasztás: terület + típus + kezdőnap."""
    return f"{r['terulet']}|{r['tipus']}|{r['kezdet'][:10]}"

def valtozasok(riasztasok, allapot):
    uj = []
    for r in riasztasok:
        k = kulcs(r)
        if allapot.get(k, {}).get("szint", 0) < r["szint"]:
            uj.append(r)
    return uj


# ════════════════════════════════════════════
#  📘  FACEBOOK POSZT
# ════════════════════════════════════════════
def ido_szoveg(iso):
    t = _ido(iso)
    if not t:
        return "?"
    return t.astimezone(MAGYAR_TZ).strftime("%m.%d. %H:%M")

def facebook_szoveg(riasztasok):
    legmagasabb = max(r["szint"] for r in riasztasok)
    jel, nev = SZINT_NEV.get(legmagasabb, ("⚠️", ""))
    st = Stilus("idojaras")

    sorok = [
        f"{jel} {st.cim} – {nev} FOKOZAT {jel}",
        f"🕐 {magyar_ido().strftime('%Y.%m.%d %H:%M')}",
        st.vonal(),
        "",
        st.bevezeto,
        "",
    ]

    for r in sorted(riasztasok, key=lambda x: (-x["szint"], x["terulet"])):
        sjel, snev = SZINT_NEV.get(r["szint"], ("⚠️", ""))
        tjel, tnev = TIPUS_NEV.get(r["tipus"], ("⚠️", r["esemeny"] or "Veszélyes időjárás"))
        sorok.append(f"{sjel} {r['terulet']}: {tjel} {tnev} ({snev.lower()})")
        sorok.append(f"   ⏰ {ido_szoveg(r['kezdet'])} – {ido_szoveg(r['lejar'])}")
        sorok.append("")

    sorok += [
        "ℹ️ Forrás: HungaroMet veszélyjelzés (met.hu)",
    ]
    if st.zaro:
        sorok.append(st.zaro)
    sorok.append("#időjárás #riasztás #Csepel #Pesterzsébet #Szigetszentmiklós")
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
    except Exception as e:
        print(f"  ⚠️  Facebook poszt hiba: {e}")
        return False


# ════════════════════════════════════════════
#  ▶️  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"⚠️ Időjárási riasztás monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    riasztasok = lekerdez()
    if riasztasok is None:
        print("⚠️ A feed nem elérhető, az állapot változatlan marad.")
        return

    allapot = betolt_allapot()
    uj = valtozasok(riasztasok, allapot)
    print(f"\n⚠️ Új vagy emelkedett riasztás: {len(uj)}")

    if uj:
        szoveg = facebook_szoveg(uj)
        print("\n" + szoveg + "\n")

        if not FACEBOOK_POSZTOLAS_AKTIV:
            print("ℹ️ Facebook-posztolás kikapcsolva.")
        elif not facebook_poszt_kuldese(szoveg):
            # Sikertelen küldés: a következő futás újra megpróbálja.
            return

        for r in uj:
            allapot[kulcs(r)] = {"szint": r["szint"], "lejar": r["lejar"]}

    # Lejárt riasztások takarítása (2 nap után)
    hatar = datetime.now(timezone.utc) - timedelta(days=2)
    for k in list(allapot):
        lejar = _ido(allapot[k].get("lejar", ""))
        if lejar and lejar < hatar:
            del allapot[k]

    ment_allapot(allapot)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
