"""
📢 Hivatali hírek – csak ami a környéket vagy a mindennapi ügyintézést érinti
Források:
  - Magyar Posta, aktualitások (https://posta.hu/aktualitasok): a hírlista a
    lapba ágyazott JSON-ban van (PostaHu.constant('newsListArray', [...]))
  - Budapest Főváros Kormányhivatala, hírek
A posztolt hírek címét az állapotfájl tárolja, így egy hír csak egyszer megy ki.
"""

import re
import json
import html
import requests

from poszt_valtozatos import Stilus

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
}

POSTA_URL = "https://posta.hu/aktualitasok"
POSTA_ALAP = "https://www.posta.hu"
KH_URL = "https://kormanyhivatalok.hu/kormanyhivatalok/budapest/megye/hirek"
KH_ALAP = "https://kormanyhivatalok.hu"

# A környék neve a hírben: ez mindig érdekes
KORNYEK = re.compile(r"Csepel|XXI\. ?kerület|Pesterzsébet|XX\. ?kerület|Szigetszentmikl[oó]s|Soroksár", re.I)
# Ügyintézést érintő hírek (leállás, zárva tartás, csalás stb.)
POSTA_FONTOS = re.compile(r"karbantart|leáll|szünetel|nem (lesz|lesznek) elérhető|zárva|nyitvatart|ünnep|"
                          r"adathalász|csal[óá]|hamis|figyelmeztet|sztrájk|késés|kézbesítés", re.I)
KH_FONTOS = re.compile(r"leáll|szünetel|zárva|nyitvatart|ügyfélfogadás|kormányablak|okmány|"
                       r"adathalász|csal[óá]|hamis|figyelmeztet|határidő|változ", re.I)

MAX_LATOTT = 300


def _szoveg(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def _get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            print(f"  ⚠️ {url} HTTP {r.status_code}")
            return None
        return r.text
    except Exception as ex:
        print(f"  ❌ {url}: {ex}")
        return None


def posta_feldolgoz(oldal):
    """[{"forras", "cim", "datum", "bevezeto", "link"}]"""
    m = re.search(r"newsListArray'\s*,\s*(\[.*?\])\s*\)", oldal, re.S)
    if not m:
        return []
    nyers = re.sub(r",\s*\]", "]", m.group(1))   # a lista végén vessző marad
    try:
        elemek = json.loads(nyers)
    except ValueError as ex:
        print(f"  ⚠️ Posta JSON: {ex}")
        return []
    return [{"forras": "Magyar Posta", "cim": _szoveg(e.get("title")), "datum": _szoveg(e.get("date")),
             "bevezeto": _szoveg(e.get("lead")),
             "link": POSTA_ALAP + e["url"] if e.get("url", "").startswith("/") else e.get("url", "")}
            for e in elemek if e.get("title")]


def kh_feldolgoz(oldal):
    """A hírlista linkjei: <a href="/kormanyhivatalok/budapest/megye/hirek/hir/…">Cím 2026. október 09. 09:25 Bevezető…</a>"""
    lista, latott = [], set()
    for link, belso in re.findall(r'<a[^>]+href="(/kormanyhivatalok/budapest/megye/hirek/hir/[^"]+)"[^>]*>(.*?)</a>', oldal, re.S):
        if link in latott:
            continue
        latott.add(link)
        t = _szoveg(belso)
        m = re.match(r"(.*?)\s*(\d{4}\. [a-zá-ű]+ \d{1,2}\.)\s*(?:\d{1,2}:\d{2})?\s*(.*)", t)
        cim, datum, bevezeto = (m.group(1), m.group(2), m.group(3)) if m else (t, "", "")
        lista.append({"forras": "Kormányhivatal", "cim": cim, "datum": datum, "bevezeto": bevezeto,
                      "link": KH_ALAP + link})
    return lista


def erdekes(h):
    szoveg = f"{h['cim']} {h['bevezeto']}"
    if KORNYEK.search(szoveg):
        return True
    return bool((POSTA_FONTOS if h["forras"] == "Magyar Posta" else KH_FONTOS).search(szoveg))


def hirek():
    """Az összes hír a két forrásból, vagy None, ha mindkettő hibás."""
    posta, kh = _get(POSTA_URL), _get(KH_URL)
    if posta is None and kh is None:
        return None
    lista = (posta_feldolgoz(posta) if posta else []) + (kh_feldolgoz(kh) if kh else [])
    print(f"  📢 Hivatali hírek: {len(lista)} db")
    return lista


def _rovid(s, n=260):
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def szoveg(nap, allapot, lista=None):
    """Az új, érdekes hivatali hírek. None = minden forrás hibás, "" = nincs új."""
    if lista is None:
        lista = hirek()
        if lista is None:
            return None
    elso_futas = "hivatali_latott" not in allapot
    volt = allapot.setdefault("hivatali_latott", [])
    uj = [h for h in lista if h["link"] not in volt]
    volt.extend(h["link"] for h in uj)
    del volt[:-MAX_LATOTT]
    if elso_futas:
        # Az első futáskor a régi híreket csak megjegyezzük, nem posztoljuk
        print(f"  ℹ️ Első futás: {len(uj)} régi hír megjegyezve")
        return ""
    uj = [h for h in uj if erdekes(h)]
    if not uj:
        return ""

    st = Stilus("hivatali", nap.isoformat())
    sorok = [st.cim, st.vonal(), "", st.bevezeto, ""]
    for h in uj[:5]:
        jel = "📮" if h["forras"] == "Magyar Posta" else "🏛️"
        sorok.append(f"{jel} {h['cim']}" + (f" ({h['datum']})" if h["datum"] else ""))
        if h["bevezeto"]:
            sorok.append(_rovid(h["bevezeto"]))
        sorok += [f"🔗 {h['link']}", ""]
    if st.zaro:
        sorok.append(st.zaro)
    sorok.append("#Csepel #ügyintézés #posta #kormányhivatal")
    return "\n".join(sorok)
