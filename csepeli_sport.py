"""
⚽ Csepeli foci – a csepeli csapatok meccsei az MLSZ adatbankból
  - elozetes_szoveg: pénteken a hétvégi (péntek–vasárnap) meccsek
  - eredmeny_szoveg: hétfőn az elmúlt hét eredményei

A csapatokat a klubok csapatlistájából gyűjti össze (KLUB_KEZDOLAPOK):
egy-egy csapatoldal "Megnézem a klub többi csapatát" listája a klub összes
csapatát tartalmazza, a felnőttektől az utánpótlásig.
Új évad (nyáron) előtt a KLUB_KEZDOLAPOK linkjeit frissíteni kell.

Kézi próba (nem posztol): python csepeli_sport.py elozetes|eredmeny
"""

import re
import sys
import html
import urllib.request
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from poszt_valtozatos import Stilus

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
KIHAGYOTT_BAJNOKSAGOK = ["veterán", "öregfiúk", "old boys"]
MAX_MECCS = 25

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


def osszes_meccs():
    """Minden csepeli csapat minden meccse. None, ha az adatbank nem elérhető."""
    csapatok = {}
    for kezdo in KLUB_KEZDOLAPOK:
        try:
            for bajnoksag, url in klub_csapatai(_letolt(kezdo)):
                if not any(k in bajnoksag.lower() for k in KIHAGYOTT_BAJNOKSAGOK):
                    csapatok.setdefault(url, bajnoksag)
        except Exception as ex:
            print(f"  ❌ {kezdo}: {ex}")
    if not csapatok:
        return None
    meccsek, hibak = {}, 0
    for url, bajnoksag in csapatok.items():
        try:
            for m in csapat_meccsei(_letolt(url), bajnoksag):
                meccsek.setdefault(m["id"], m)
        except Exception as ex:
            hibak += 1
            print(f"  ❌ {url}: {ex}")
    print(f"  ⚽ {len(csapatok)} csapat, {len(meccsek)} meccs, {hibak} hiba")
    if hibak > len(csapatok) // 2:
        return None
    return sorted(meccsek.values(), key=lambda m: (m["nap"], m["ido"] or "99", m["bajnoksag"]))


def _bajnoksag(m):
    return szep_nev(m["bajnoksag"])


def _parositas(m):
    return f"{szep_nev(m['hazai'])} – {szep_nev(m['vendeg'])}"


def _kimenet(m):
    """✅/🤝/❌ a csepeli csapat szemszögéből (csepeli rangadón nincs)."""
    h, v = m["golok"]
    hazai_csepeli = "CSEPEL" in m["hazai"].upper()
    vendeg_csepeli = "CSEPEL" in m["vendeg"].upper()
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
    for nap in sorted({m["nap"] for m in lista}):
        sorok.append(f"▶️ {NAPOK[nap.weekday()].upper()} ({nap.strftime('%m.%d.')})")
        for m in [m for m in lista if m["nap"] == nap]:
            ido = f"{m['ido']} " if m["ido"] else ""
            sorok.append(f"⚽ {ido}{_parositas(m)}")
            sorok.append(f"   🏆 {_bajnoksag(m)}" + (f"  📍 {m['helyszin']}" if m["helyszin"] else ""))
        sorok.append("")
    sorok.append("Hajrá, Csepel! 💪 Ha kimentek, írjátok meg az eredményt kommentben!")
    if st.zaro:
        sorok.append(st.zaro)
    sorok += ["Forrás: MLSZ adatbank", "#Csepel #foci #CsepelSC #utánpótlás"]
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
    for m in lista:
        h, v = m["golok"]
        jel = _kimenet(m)
        sorok.append(f"{jel or '⚽'} {_parositas(m)}  {h}–{v}")
        sorok.append(f"   🏆 {_bajnoksag(m)}, {m['nap'].strftime('%m.%d.')} {NAPOK[m['nap'].weekday()]}")
    gyozelem = sum(1 for m in lista if _kimenet(m) == "✅")
    sorok += ["", f"Összesen {len(lista)} meccs, ebből {gyozelem} csepeli győzelem."
              if gyozelem else f"Összesen {len(lista)} meccs. Jövő héten jobban megy majd! 💪"]
    if st.zaro:
        sorok.append(st.zaro)
    sorok += ["Forrás: MLSZ adatbank", "#Csepel #foci #CsepelSC #eredmények"]
    return "\n".join(sorok)


if __name__ == "__main__":
    ma = datetime.now(MAGYAR_TZ).date()
    mod = sys.argv[1] if len(sys.argv) > 1 else "elozetes"
    meccsek = osszes_meccs()
    if meccsek is not None:
        for m in meccsek:
            print(f"   {m['nap']} {m['ido']:>5} | {m['bajnoksag']} | {m['hazai']} – {m['vendeg']} | {m['golok']}")
    szoveg = (elozetes_szoveg if mod == "elozetes" else eredmeny_szoveg)(ma, meccsek) if meccsek is not None else None
    print("═" * 60)
    print(szoveg)
