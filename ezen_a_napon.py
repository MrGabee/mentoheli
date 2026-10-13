"""
📜 Ezen a napon történt – a magyar Wikipédia napi oldaláról (pl. "Október 11.")
Az "Események" szakaszból a hazai (Csepel, Budapest, magyar) események
előnyben, plusz egy ismert születésnap.
"""

import re
import random
import requests

from poszt_valtozatos import Stilus

API = "https://hu.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "mentoheli/1.0 (https://github.com/MrGabee/mentoheli)"}

HONAPOK = ["Január", "Február", "Március", "Április", "Május", "Június", "Július",
           "Augusztus", "Szeptember", "Október", "November", "December"]

# Erősorrend: minél előbb van a szó, annál inkább előnyben
HAZAI = ["Csepel", "Pesterzsébet", "Szigetszentmiklós", "Budapest", "Pest", "Buda", "magyar", "Magyar"]

MAX_ESEMENY = 3


def wiki_tiszta(s):
    """Wikiszöveg → sima szöveg."""
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\{\{szám\|([^|}]*)\|?([^}]*)\}\}", lambda m: f"{m.group(1)} {m.group(2)}".strip(), s)
    for _ in range(3):
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[https?://\S+ ([^\]]*)\]", r"\1", s)
    s = s.replace("'''", "").replace("''", "")
    return " ".join(s.split())


def szakasz(wikiszoveg, cim):
    """Egy == Cím == szakasz felsorolás-sorai: [(év, szöveg)]."""
    m = re.search(rf"^==\s*{cim}\s*==\s*$(.*?)(?=^==[^=])", wikiszoveg + "\n== vége ==", re.S | re.M)
    if not m:
        return []
    sorok = []
    for sor in m.group(1).splitlines():
        t = re.match(r"\*\s*\[\[(\d{1,4})\]\]\s*[–-]\s*(.+)", sor.strip())
        if t:
            szoveg = wiki_tiszta(t.group(2))
            if szoveg:
                sorok.append((int(t.group(1)), szoveg))
    return sorok


def hazai_sulya(szoveg):
    for i, szo in enumerate(HAZAI):
        if szo in szoveg:
            return i
    return len(HAZAI)


def valogat(esemenyek, nap):
    """A legközelebbi hazai események, napi szinten fix véletlennel."""
    rnd = random.Random(f"ezen|{nap}")
    kevert = esemenyek[:]
    rnd.shuffle(kevert)
    kevert.sort(key=lambda e: hazai_sulya(e[1]))
    return sorted(kevert[:MAX_ESEMENY])


def lekerdez(nap):
    oldal = f"{HONAPOK[nap.month - 1]} {nap.day}."
    try:
        r = requests.get(API, headers=HEADERS, timeout=20, params={
            "action": "parse", "page": oldal, "prop": "wikitext",
            "format": "json", "formatversion": 2})
        if r.status_code != 200:
            print(f"  ⚠️ Wikipédia HTTP {r.status_code}")
            return None
        return r.json()["parse"]["wikitext"]
    except Exception as ex:
        print(f"  ❌ Wikipédia: {ex}")
        return None


def szoveg(nap, wikiszoveg=None):
    wikiszoveg = wikiszoveg or lekerdez(nap)
    if not wikiszoveg:
        return None
    esemenyek = valogat(szakasz(wikiszoveg, "Események"), nap)
    if not esemenyek:
        return ""
    szuletesek = szakasz(wikiszoveg, "Születések")
    szuletes = None
    if szuletesek:
        szuletes = min(szuletesek, key=lambda e: (hazai_sulya(e[1]), random.Random(f"szul|{nap}|{e}").random()))

    st = Stilus("ezen_a_napon", nap.isoformat())
    sorok = [st.cim, f"📅 {HONAPOK[nap.month - 1].lower()} {nap.day}.", st.vonal(), "", st.bevezeto, ""]
    for ev, t in esemenyek:
        sorok.append(f"🕰️ {ev}: {t}")
        sorok.append("")
    if szuletes:
        sorok += [f"🎂 Ezen a napon született ({szuletes[0]}): {szuletes[1]}", ""]
    sorok.append("ℹ️ Forrás: Wikipédia")
    if st.zaro:
        sorok.append(st.zaro)
    sorok.append("#ezenanapon #történelem #Csepel")
    return "\n".join(sorok)
