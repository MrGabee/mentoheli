"""
🏛️ Környékbeli érdekesség – egy-egy Wikipédia-szócikk bevezetője
Csepel, Pesterzsébet és Szigetszentmiklós kategóriáiból (és egy szint
alkategóriából) választ egy még nem posztolt szócikket.
"""

import re
import random
import requests

from poszt_valtozatos import Stilus

API = "https://hu.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "mentoheli/1.0 (https://github.com/MrGabee/mentoheli)"}

KATEGORIAK = [
    "Kategória:Budapest XXI. kerülete",
    "Kategória:Budapest XX. kerülete",
    "Kategória:Szigetszentmiklós",
]

# Ezek a szócikkek nem érdekességek (járatok, megállók, utak, listák), vagy
# politikai/közéleti témák, amik nem illenek egy környékbeli oldalra
KIZART = re.compile(r"busz\b|villamos|HÉV\b|megállóhely|vasútállomás|mellékút|főút|vasútvonal|"
                    r"választókerület|^Lista|listája|^Budapest X|politikus|Kövér László|PestiSrácok|Pesti srác", re.I)

MAX_HOSSZ = 650


def _api(**params):
    params.update(format="json", formatversion=2)
    r = requests.get(API, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def tagok(kategoria, tipus="page|subcat"):
    adat = _api(action="query", list="categorymembers", cmtitle=kategoria,
                cmtype=tipus, cmlimit=200)
    return adat["query"]["categorymembers"]


def jeloltek():
    """Szócikk-címek a kategóriákból és azok alkategóriáiból."""
    cimek = set()
    for kat in KATEGORIAK:
        for t in tagok(kat):
            if t["ns"] == 14:
                for al in tagok(t["title"], "page"):
                    cimek.add(al["title"])
            elif t["ns"] == 0:
                cimek.add(t["title"])
    return sorted(c for c in cimek if not KIZART.search(c))


def bevezeto(cim):
    adat = _api(action="query", prop="extracts", exintro=1, explaintext=1,
                redirects=1, titles=cim)
    oldal = adat["query"]["pages"][0]
    return (oldal.get("extract") or "").strip()


def rovidit(szoveg):
    szoveg = " ".join(szoveg.split())
    if len(szoveg) <= MAX_HOSSZ:
        return szoveg
    vag = szoveg[:MAX_HOSSZ]
    pont = vag.rfind(". ")
    return vag[:pont + 1] if pont > 200 else vag.rsplit(" ", 1)[0] + "…"


def szoveg(nap, volt):
    """volt: a már posztolt címek listája (ezt bővíti). None = hiba."""
    try:
        lista = jeloltek()
        friss = [c for c in lista if c not in volt]
        if not friss:          # mindegyik volt már: elölről
            volt.clear()
            friss = lista
        rnd = random.Random(f"erdekesseg|{nap}")
        rnd.shuffle(friss)
        for cim in friss[:8]:
            kivonat = bevezeto(cim)
            if len(kivonat) >= 150:
                break
        else:
            return ""
    except Exception as ex:
        print(f"  ❌ Wikipédia: {ex}")
        return None

    volt.append(cim)
    st = Stilus("erdekesseg", nap.isoformat())
    link = "https://hu.wikipedia.org/wiki/" + cim.replace(" ", "_")
    sorok = [st.cim, st.vonal(), "", st.bevezeto, "",
             f"📍 {cim}", "", rovidit(kivonat), "",
             f"📖 Bővebben: {link}"]
    if st.zaro:
        sorok += ["", st.zaro]
    sorok.append("#helytörténet #Csepel #Pesterzsébet #Szigetszentmiklós")
    return "\n".join(sorok)
