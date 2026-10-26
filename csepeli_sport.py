"""
⚽ Csepeli sport – a csepeli csapatok meccsei az MLSZ adatbankból,
a többi sportágé (kézilabda stb.) a mas_sportagak.py-ból
  - elozetes_szoveg: pénteken a hétvégi (péntek–vasárnap) meccsek
  - eredmeny_szoveg: hétfőn az elmúlt hét eredményei
  - hetkoznapi_szoveg: a Csepel SC hétközi meccse előtti napon külön poszt
A Csepel SC felnőtt csapatának (NB III, kupa) meccsei mindig a poszt elején,
kiemelve szerepelnek.

A csapatokat a klubok csapatlistájából gyűjti össze (KLUB_KEZDOLAPOK):
egy-egy csapatoldal "Megnézem a klub többi csapatát" listája a klub összes
csapatát tartalmazza, a felnőttektől az utánpótlásig.
Új évad (nyáron) előtt a KLUB_KEZDOLAPOK linkjeit frissíteni kell.

Kézi próba (nem posztol): python csepeli_sport.py elozetes|eredmeny
"""

import re
import sys
import random
import html
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from poszt_valtozatos import Stilus
import mas_sportagak

MAGYAR_TZ = ZoneInfo("Europe/Budapest")
ADATBANK = "https://adatbank.mlsz.hu"

# Klubonként egy csapatoldal (2026/2027-es évad): Csepel SC, Csepel UFC,
# Csepel FC, Csepel FC USE
KLUB_KEZDOLAPOK = [
    ADATBANK + "/club/67/0/34054/12/328687.html",
    ADATBANK + "/club/67/5/33753/1/330199.html",
    ADATBANK + "/club/67/0/33634/1/330512.html",
    ADATBANK + "/club/67/5/33817/1/335288.html",
]
# Ezekről a bajnokságokról nem írok
MAX_MECCS = 40
# A klubok csapatlistája mellett végignézem az évad összes bajnokságát is
# (ezek azonosítói ebbe a tartományba esnek), és minden csapatot felveszek,
# amelyiknek a nevében ott van a Csepel (pl. más klubok csepeli csapatai).
EVAD = 67
BAJNOKSAG_TARTOMANY = range(33300, 34600)
CSEPELI_NEV = re.compile(r"CSEPEL|CSFC|CSHC", re.I)   # CsHC 94 SE: Csepel Hungary Club

# A kiemelt csapat: a Csepel SC felnőtt csapata (bajnokság és kupa)
KIEMELT_CSAPAT = "CSEPEL SC"
KIEMELT_SOROZATOK = ["NB III", "Magyar Kupa"]
# Kézzel felvett meccsek, ha az adatbankban még nincsenek fent
# (ha aznapra már van ott meccse a csapatnak, a kézi kimarad)
KEZI_MECCSEK = [
    {"csapat": "CSEPEL SC", "hazai": "CSEPEL SC", "vendeg": "DVSC", "nap": date(2026, 10, 28),
     "ido": "12:30", "bajnoksag": "MOL Magyar Kupa", "helyszin": "Csepel SC Stadion (Béke tér)"},
]

NAPOK = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]
NAGYBETUS_SZAVAK = {"FC", "SC", "SE", "SK", "AK", "FS", "ISSIMO", "UFC", "USE", "MTE",
                    "BSE", "TFSE", "VSE", "KSE", "MÁV", "NB", "BLSZ", "MLSZ", "HNP", "REAC",
                    "AFC", "LSE", "DSE", "ESE", "TC", "UTE"}
# Rövid szavak, amelyek nem betűszók (a többi legfeljebb 4 betűs szó nagybetűs marad: BVSC, REAC)
KISBETUS_ROVIDITESEK = {"BP", "SZ", "KFT", "ÚJ", "DÉL", "ÉSZAK", "KUPA", "NŐI", "VÁC", "PEST", "DUNA", "TATA", "EGER", "PÁPA", "BAJA", "GYŐR", "PÉCS", "MAKÓ", "ÓZD", "MÓR", "ÉRD", "SZOB", "ONGA"}
ROMAI = re.compile(r"^(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XV|XX|XXI)\.?$")


def _letolt(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/129.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=25) as f:
        return f.read().decode("utf-8", "replace")


def _tiszta(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def szep_nev(nev):
    """CSEPEL FC USE -> Csepel FC USE (csak a csupa nagybetűs neveknél)."""
    if nev != nev.upper():
        return nev
    def resz(szo):
        alap = szo.rstrip(".")
        betuk = [c for c in alap if c.isalpha()]
        if (alap in NAGYBETUS_SZAVAK or ROMAI.match(szo) or any(c.isdigit() for c in alap)
                or (len(betuk) <= 4 and alap.strip('"') not in KISBETUS_ROVIDITESEK)):
            return szo
        return szo.capitalize()
    return " ".join(szo if re.match(r"^U-?\d+$", szo) else "-".join(resz(r) for r in szo.split("-"))
                    for szo in nev.split())


def klub_csapatai(html_szoveg):
    """A "klub többi csapata" lista: [(bajnokság, csapatoldal URL)]."""
    blokk = re.search(r'id="ClubSelector".*?</select>', html_szoveg, re.S)
    if not blokk:
        return []
    lista = []
    for ertek, nev in re.findall(r'<option\s+value="([^"]+)"[^>]*>([^<]+)</option>', blokk.group(0)):
        p = dict(re.findall(r"(\w+)=([^&]+)", html.unescape(ertek)))
        if not all(k in p for k in ("teamId", "evad", "szervezet", "verseny", "fordulo")):
            continue
        url = f"{ADATBANK}/club/{p['evad']}/{p['szervezet']}/{p['verseny']}/{p['fordulo']}/{p['teamId']}.html"
        lista.append((html.unescape(nev).strip(), url))
    return lista


def csapat_meccsei(html_szoveg, bajnoksag):
    """A csapatoldal sorsolása: meccsek listája (dict)."""
    nev = re.search(r'id="team_name"[^>]*>([^<]+)<', html_szoveg)
    csapat = html.unescape(nev.group(1)).strip() if nev else ""
    meccsek = []
    darabok = re.split(r'<div class="schedule\s*"\s+rel="', html_szoveg)[1:]
    for d in darabok:
        azon = d.split('"', 1)[0]
        hazai = re.search(r'class="home_team".*?title="([^"]+)"', d, re.S)
        vendeg = re.search(r'class="away_team".*?title="([^"]+)"', d, re.S)
        datum = re.search(r'class="team_sorsolas_date">(.*?)</div>', d, re.S)
        if not (hazai and vendeg and datum):
            continue
        dt = re.search(r"(\d{4})\. (\d{1,2})\. (\d{1,2})\.(?:\s+(\d{1,2}):(\d{2}))?", _tiszta(datum.group(1)))
        if not dt:
            continue
        ev, ho, nap, ora, perc = dt.groups()
        eredmeny = re.search(r'class="schedule-points">\s*(\d+)\s*-\s*(\d+)\s*<', d)
        helyszin = re.search(r'class="team_sorsolas_arena">(.*?)</div>', d, re.S)
        meccsek.append({
            "id": azon,
            "csapat": html.unescape(csapat),
            "bajnoksag": bajnoksag,
            "hazai": html.unescape(hazai.group(1)).strip(),
            "vendeg": html.unescape(vendeg.group(1)).strip(),
            "nap": date(int(ev), int(ho), int(nap)),
            "ido": f"{int(ora)}:{perc}" if ora else "",
            "golok": (int(eredmeny.group(1)), int(eredmeny.group(2))) if eredmeny else None,
            "helyszin": _tiszta(helyszin.group(1)) if helyszin else "",
        })
    return meccsek


def _csapat_kulcs(url):
    """(bajnokság, csapat) azonosító egy csapatoldal URL-jéből."""
    r = re.search(r"/club/\d+/\d+/(\d+)/\d+/(\d+)\.html", url)
    return (r.group(1), r.group(2)) if r else url


def bajnoksag_csepeli_csapatai(azon):
    """Egy bajnokság csepeli csapatai: [(bajnokság neve, csapatoldal URL)]."""
    try:
        t = _letolt(f"{ADATBANK}/league/{EVAD}/0/{azon}/1.html")
    except Exception:
        return []
    if not CSEPELI_NEV.search(t):
        return []
    cim = re.search(r"<title>(.*?)</title>", t, re.S)
    nev = re.sub(r"\s+\d+\. forduló\s*-\s*MLSZ adatbank\s*$", "", html.unescape(cim.group(1)).strip()) if cim else ""
    lista = []
    latott = set()
    for a in re.finditer(r'<a\b[^>]*href="((?:https://adatbank\.mlsz\.hu)?/club/\d+/\d+/%d/\d+/\d+\.html)"[^>]*>(.*?)</a>' % azon, t, re.S):
        url, tag = a.group(1), a.group(0)
        if url.startswith("/"):
            url = ADATBANK + url
        if url in latott:
            continue
        cim_attr = re.search(r'title="([^"]+)"', tag)
        csapat = html.unescape(cim_attr.group(1) if cim_attr else _tiszta(a.group(2)))
        if CSEPELI_NEV.search(csapat):
            latott.add(url)
            lista.append((nev, url))
    if not lista:
        print(f"  ⚠️ {azon}: csepeli név van az oldalon, de csapatlinket nem találtam")
    return lista


def osszes_meccs(teljes=True):
    """Minden csepeli csapat minden meccse. None, ha az adatbank nem elérhető.
    teljes=False: csak a klubok csapatlistája (gyors, a Csepel SC-hez elég)."""
    csapatok = {}
    for kezdo in KLUB_KEZDOLAPOK:
        try:
            for bajnoksag, url in klub_csapatai(_letolt(kezdo)):
                csapatok.setdefault(_csapat_kulcs(url), (url, bajnoksag))
        except Exception as ex:
            print(f"  ❌ {kezdo}: {ex}")
    if not csapatok:
        return None
    if teljes:
        with ThreadPoolExecutor(16) as ex:
            for lista in ex.map(bajnoksag_csepeli_csapatai, BAJNOKSAG_TARTOMANY):
                for bajnoksag, url in lista:
                    csapatok.setdefault(_csapat_kulcs(url), (url, bajnoksag))

    def letolt_csapat(par):
        url, bajnoksag = par
        try:
            return csapat_meccsei(_letolt(url), bajnoksag)
        except Exception as ex:
            print(f"  ❌ {url}: {ex}")
            return None

    meccsek, hibak = {}, 0
    with ThreadPoolExecutor(8) as ex:
        for eredmeny in ex.map(letolt_csapat, csapatok.values()):
            if eredmeny is None:
                hibak += 1
                continue
            for m in eredmeny:
                meccsek.setdefault(m["id"], m)
    print(f"  ⚽ {len(csapatok)} csapat, {len(meccsek)} meccs, {hibak} hiba")
    if hibak > len(csapatok) // 2:
        return None
    for k in KEZI_MECCSEK:
        if not any(m["nap"] == k["nap"] and m["csapat"] == k["csapat"] for m in meccsek.values()):
            meccsek[f"kezi-{k['nap']}"] = dict(k, id=f"kezi-{k['nap']}", golok=None)
    if teljes:
        # a többi sportág (kézilabda stb.) csepeli csapatai
        for m in mas_sportagak.osszes(datetime.now(MAGYAR_TZ).date()):
            meccsek.setdefault(m["id"], m)
    return sorted(meccsek.values(), key=lambda m: (m["nap"], m["ido"] or "99", m["bajnoksag"]))


def kiemelt(m):
    """A Csepel SC felnőtt csapatának bajnoki vagy kupameccse."""
    return (m["csapat"].strip().upper() == KIEMELT_CSAPAT
            and any(s.lower() in m["bajnoksag"].lower() for s in KIEMELT_SOROZATOK))


def _kiemelt_sorok(lista, eredmennyel=False):
    sorok = []
    for m in lista:
        nap = f"{NAPOK[m['nap'].weekday()]} {m['nap'].strftime('%m.%d.')}" + (f" {m['ido']}" if m["ido"] else "")
        if eredmennyel:
            h, v = m["golok"]
            sorok.append(f"{_kimenet(m)} {_parositas(m)}  {h}–{v}")
        else:
            sorok.append(f"⚽ {_parositas(m)}")
        sorok.append(f"   🏆 {_bajnoksag(m)}  📅 {nap}" + (f"  📍 {m['helyszin']}" if m["helyszin"] and not eredmennyel else ""))
    return sorok


def _emoji(m):
    return mas_sportagak.EMOJI.get(m.get("sport", "foci"), "🏅")


def _lablec(lista, *cimkek):
    """Forrás és hashtagek a posztban szereplő sportágak szerint."""
    sportok = sorted({m.get("sport", "foci") for m in lista}, key=lambda s: s != "foci")
    forras = ", ".join(mas_sportagak.FORRAS.get(s, s) for s in sportok)
    cimkek = ["#Csepel", *(mas_sportagak.HASHTAG.get(s, "") for s in sportok), *cimkek]
    return [f"Forrás: {forras}", " ".join(c for c in cimkek if c)]


def _bajnoksag(m):
    return szep_nev(m["bajnoksag"])


def _parositas(m):
    return f"{szep_nev(m['hazai'])} – {szep_nev(m['vendeg'])}"


def _kimenet(m):
    """✅/🤝/❌ a csepeli csapat szemszögéből (csepeli rangadón nincs)."""
    h, v = m["golok"]
    hazai_csepeli = bool(CSEPELI_NEV.search(m["hazai"]))
    vendeg_csepeli = bool(CSEPELI_NEV.search(m["vendeg"]))
    if h == v:
        return "🤝"
    if hazai_csepeli == vendeg_csepeli:
        return ""
    return "✅" if (h > v) == hazai_csepeli else "❌"


def elozetes_szoveg(ma, meccsek=None):
    """None = az adatbank nem elérhető, "" = nincs meccs."""
    if meccsek is None:
        meccsek = osszes_meccs()
        if meccsek is None:
            return None
    vasarnap = ma + timedelta(days=(6 - ma.weekday()) % 7)
    most = datetime.now(MAGYAR_TZ)
    # A mai, már elkezdődött meccsek kimaradnak
    elmult = most.strftime("%H:%M") if ma == most.date() else ""
    lista = [m for m in meccsek if ma <= m["nap"] <= vasarnap and m["golok"] is None
             and not (m["nap"] == ma and m["ido"] and m["ido"].zfill(5) < elmult)][:MAX_MECCS]
    if not lista:
        return ""
    st = Stilus("sport_elozetes", ma.isoformat())
    sorok = [st.cim, st.vonal(), "", st.bevezeto, ""]
    fo = [m for m in lista if kiemelt(m)]
    if fo:
        sorok += ["❤️💙 CSEPEL SC – FELNŐTT CSAPAT ❤️💙", *_kiemelt_sorok(fo), "", "👟 A TÖBBI CSEPELI CSAPAT", ""]
    tobbi = [m for m in lista if not kiemelt(m)]
    for nap in sorted({m["nap"] for m in tobbi}):
        sorok.append(f"▶️ {NAPOK[nap.weekday()].upper()} ({nap.strftime('%m.%d.')})")
        for m in [m for m in tobbi if m["nap"] == nap]:
            ido = f"{m['ido']} " if m["ido"] else ""
            sorok.append(f"{_emoji(m)} {ido}{_parositas(m)}")
            sorok.append(f"   🏆 {_bajnoksag(m)}" + (f"  📍 {m['helyszin']}" if m["helyszin"] else ""))
        sorok.append("")
    sorok.append("Hajrá, Csepel! 💪 Ha kimentek, írjátok meg az eredményt kommentben!")
    if st.zaro:
        sorok.append(st.zaro)
    sorok += _lablec(lista, "#CsepelSC", "#utánpótlás")
    return "\n".join(sorok)


def eredmeny_szoveg(ma, meccsek=None):
    """Az elmúlt 7 nap eredményei. None = nem elérhető, "" = nincs eredmény."""
    if meccsek is None:
        meccsek = osszes_meccs()
        if meccsek is None:
            return None
    lista = [m for m in meccsek if ma - timedelta(days=7) <= m["nap"] < ma and m["golok"] is not None][:MAX_MECCS]
    if not lista:
        return ""
    st = Stilus("sport_eredmeny", ma.isoformat())
    sorok = [st.cim, st.vonal(), "", st.bevezeto, ""]
    fo = [m for m in lista if kiemelt(m)]
    if fo:
        sorok += ["❤️💙 CSEPEL SC – FELNŐTT CSAPAT ❤️💙", *_kiemelt_sorok(fo, eredmennyel=True), "", "👟 A TÖBBI CSEPELI CSAPAT", ""]
    for m in [m for m in lista if not kiemelt(m)]:
        h, v = m["golok"]
        jel = _kimenet(m)
        sorok.append(f"{jel or _emoji(m)} {_parositas(m)}  {h}–{v}")
        sorok.append(f"   🏆 {_bajnoksag(m)}, {m['nap'].strftime('%m.%d.')} {NAPOK[m['nap'].weekday()]}")
    gyozelem = sum(1 for m in lista if _kimenet(m) == "✅")
    sorok += ["", f"Összesen {len(lista)} meccs, ebből {gyozelem} csepeli győzelem."
              if gyozelem else f"Összesen {len(lista)} meccs. Jövő héten jobban megy majd! 💪"]
    if st.zaro:
        sorok.append(st.zaro)
    sorok += _lablec(lista, "#CsepelSC", "#eredmények")
    return "\n".join(sorok)


HETKOZI_MONDATOK = [
    "Hétközben is játszik a Csepel SC, holnap meccsnap!",
    "Nem kell hétvégéig várni: holnap pályára lép a Csepel SC.",
    "Holnap hétközi meccs jön, aki teheti, menjen ki szurkolni!",
    "Szólok előre, holnap játszik a Csepel SC:",
]


def hetkoznapi_szoveg(ma, meccsek=None):
    """A Csepel SC holnapi hétközi (hétfő–csütörtöki) meccse. "" = nincs ilyen."""
    holnap = ma + timedelta(days=1)
    if holnap.weekday() > 3:
        return ""  # a péntek–vasárnapi meccsek a pénteki beharangozóban vannak
    if meccsek is None:
        meccsek = osszes_meccs(teljes=False)
        if meccsek is None:
            return None
    lista = [m for m in meccsek if m["nap"] == holnap and kiemelt(m) and m["golok"] is None]
    if not lista:
        return ""
    st = Stilus("sport_hetkoz", ma.isoformat())
    sorok = [st.cim, st.vonal(), "", random.Random(f"{ma}|hetkoz").choice(HETKOZI_MONDATOK), "",
             *_kiemelt_sorok(lista), "", "Hajrá, Csepel! ❤️💙"]
    if st.zaro:
        sorok.append(st.zaro)
    sorok += ["Forrás: MLSZ adatbank", "#Csepel #CsepelSC #foci"]
    return "\n".join(sorok)


if __name__ == "__main__":
    ma = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else datetime.now(MAGYAR_TZ).date()
    mod = sys.argv[1] if len(sys.argv) > 1 else "elozetes"
    meccsek = osszes_meccs()
    if meccsek is not None:
        for b in sorted({(m["bajnoksag"], m["csapat"]) for m in meccsek}):
            print(f"   🏷️ {b[0]} | {b[1]}")
        for m in meccsek:
            print(f"   {m['nap']} {m['ido']:>5} | {m['bajnoksag']} | {m['hazai']} – {m['vendeg']} | {m['golok']}")
    fv = {"elozetes": elozetes_szoveg, "eredmeny": eredmeny_szoveg, "hetkoz": hetkoznapi_szoveg}[mod]
    szoveg = fv(ma, meccsek) if meccsek is not None else None
    print("═" * 60)
    print(szoveg)
