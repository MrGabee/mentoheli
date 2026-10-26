"""
🤾 A foci mellett a többi sportág csepeli csapatainak meccsei.
A csepeli_sport.osszes_meccs() ugyanabban a formában kapja meg őket,
mint az MLSZ-meccseket, csak a "sport" mezőben más áll.

  - kézilabda: az MKSZ nyilvános API-ja (public.mksz.hu), sportszervezet szerint
  - kosárlabda: az mkosz.hu bajnoksági műsora (HTML), a csepeli nevű csapatok meccsei

Kézi próba (nem posztol): python mas_sportagak.py [YYYY-MM-DD]
"""

import html
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

MKSZ_API = "https://public.mksz.hu/public/api/v1/"
MKSZ_FEJLEC = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/129.0 Safari/537.36",
               "Accept": "application/json", "Origin": "https://www.mksz.hu",
               "Referer": "https://www.mksz.hu/"}
# Csepeli kézilabda-egyesületek az MKSZ nyilvántartásában (azonosító: név)
MKSZ_KLUBOK = {328: "Csepel DSE", 899: "Csepel SZSE", 336: "Csepeli KSE"}

# Sportáganként az emoji és a forrás neve a posztban
EMOJI = {"foci": "⚽", "kezilabda": "🤾", "kosar": "🏀"}
FORRAS = {"foci": "MLSZ adatbank", "kezilabda": "MKSZ", "kosar": "MKOSZ"}
HASHTAG = {"foci": "#foci", "kezilabda": "#kézilabda", "kosar": "#kosárlabda"}

# Kosárlabda: az mkosz.hu bajnokságai, amelyekben csepeli csapat játszik
# (2026/27: Csepel Basket, férfi NB II Közép A). Új évadnál az évadkódot is frissíteni kell.
MKOSZ = "https://mkosz.hu"
MKOSZ_EVAD = "x2627"
MKOSZ_BAJNOKSAGOK = {"hun3koa": "Férfi NB II Közép A"}
CSEPELI = re.compile(r"csepel", re.I)
HONAPOK = ["január", "február", "március", "április", "május", "június", "július",
           "augusztus", "szeptember", "október", "november", "december"]


def _json(url):
    req = urllib.request.Request(url, headers=MKSZ_FEJLEC)
    with urllib.request.urlopen(req, timeout=25) as f:
        return json.loads(f.read().decode("utf-8", "replace"))


def mksz_meccs(m, klub):
    """Egy MKSZ-meccs a csepeli_sport formájában."""
    ido = datetime.fromisoformat(m["merkozesDatum"][:19])
    # a jegyzőkönyv elfogadása után is végleges az eredmény, csak még nincs lezárva
    lezart = m.get("merkozesStatusz") in ("JEGYZOK_LEZARVA", "JEGYZOK_ELFOGADVA")
    h, v = m.get("hazaiCsapatGol"), m.get("vendegCsapatGol")
    helyszin = (m.get("letesitmenyNev") or "").strip()
    bajnoksag = (m.get("alversenyNev") or m.get("foversenyRovidNev") or "").strip()
    korosztaly = (m.get("korosztalyNev") or "").strip()
    if korosztaly and korosztaly.lower() not in bajnoksag.lower():
        bajnoksag = f"{korosztaly} {bajnoksag}".strip()
    return {
        "id": f"mksz-{m['merkozesId']}",
        "sport": "kezilabda",
        "csapat": klub,
        "bajnoksag": bajnoksag or "kézilabda",
        "hazai": (m.get("hazaiCsapatNev") or "").strip(),
        "vendeg": (m.get("vendegCsapatNev") or "").strip(),
        "nap": ido.date(),
        "ido": "" if (ido.hour, ido.minute) == (0, 0) else f"{ido.hour}:{ido.minute:02d}",
        "golok": (int(h), int(v)) if lezart and h is not None and v is not None else None,
        "helyszin": "" if helyszin in ("", "Nincs megadva") else helyszin,
    }


def kezilabda(tol, ig):
    """A csepeli kézilabdacsapatok meccsei tol..ig között. Hiba esetén üres lista."""
    meccsek = {}
    for azon, klub in MKSZ_KLUBOK.items():
        p = {"sportszervezetId.equals": azon,
             "merkozesDatum.greaterThanOrEqual": f"{tol}T00:00:00.000",
             "merkozesDatum.lessThanOrEqual": f"{ig}T23:59:59.000",
             "size": 200, "page": 0}
        try:
            adat = _json(MKSZ_API + "versenyek/program?" + urllib.parse.urlencode(p))
        except Exception as ex:
            print(f"  ❌ MKSZ {klub}: {ex}")
            continue
        if isinstance(adat, dict):
            adat = adat.get("content") or []
        for m in adat:
            try:
                meccsek.setdefault(f"mksz-{m['merkozesId']}", mksz_meccs(m, klub))
            except Exception as ex:
                print(f"  ⚠️ MKSZ meccs kimaradt: {ex}")
    print(f"  🤾 {len(meccsek)} kézilabdameccs")
    return list(meccsek.values())


def _szoveg(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def mkosz_meccsek(lap, bajnoksag):
    """Az mkosz.hu bajnokság-műsor lapjáról a csepeli csapatok meccsei."""
    meccsek = []
    for sor in re.split(r"<tr[\s>]", lap):
        csapatok = re.findall(r'<a href="[^"]*/csapat/[^"]*" title="([^"]+)" class="hasLogo"', sor)
        datum = re.search(r"<b>\s*(\d{4})\.\s*([a-záéíóöőúüű]+)\s+(\d{1,2})\.\s*</b>", sor)
        if len(csapatok) != 2 or not datum or not any(CSEPELI.search(c) for c in csapatok):
            continue
        if datum.group(2) not in HONAPOK:
            continue
        nap = date(int(datum.group(1)), HONAPOK.index(datum.group(2)) + 1, int(datum.group(3)))
        ido = re.search(r'<td style="width: 70px">\s*(\d{1,2}):(\d{2})\s*</td>', sor)
        link = re.search(r'href="[^"]*/merkozes/[^"]*?_(\d+)"', sor)
        eredmeny = re.search(r'/merkozes/[^"]*">\s*(\d+)\s*-\s*(\d+)\s*</a>', sor)
        helyszin = re.search(r'non-breaking" title="([^"]*)"', sor)
        hazai, vendeg = (html.unescape(c).strip() for c in csapatok)
        meccsek.append({
            "id": f"mkosz-{link.group(1) if link else f'{nap}-{hazai}'}",
            "sport": "kosar",
            "csapat": hazai if CSEPELI.search(hazai) else vendeg,
            "bajnoksag": bajnoksag,
            "hazai": hazai,
            "vendeg": vendeg,
            "nap": nap,
            "ido": f"{int(ido.group(1))}:{ido.group(2)}" if ido else "",
            # a még le nem játszott meccsnél 0 - 0 áll
            "golok": (int(eredmeny.group(1)), int(eredmeny.group(2)))
                     if eredmeny and eredmeny.group(1, 2) != ("0", "0") else None,
            "helyszin": html.unescape(helyszin.group(1)).strip() if helyszin else "",
        })
    return meccsek


def kosar(tol, ig):
    """A csepeli kosárlabdacsapatok meccsei tol..ig között. Hiba esetén üres lista."""
    meccsek = {}
    for kod, nev in MKOSZ_BAJNOKSAGOK.items():
        url = f"{MKOSZ}/bajnoksag-musor/{MKOSZ_EVAD}/{kod}/"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": MKSZ_FEJLEC["User-Agent"]})
            with urllib.request.urlopen(req, timeout=25) as f:
                lap = f.read().decode("utf-8", "replace")
        except Exception as ex:
            print(f"  ❌ MKOSZ {nev}: {ex}")
            continue
        for m in mkosz_meccsek(lap, nev):
            if tol <= m["nap"] <= ig:
                meccsek.setdefault(m["id"], m)
    print(f"  🏀 {len(meccsek)} kosárlabdameccs")
    return list(meccsek.values())


def osszes(ma=None):
    """Minden nem foci meccs a mai nap körül (2 hét vissza, 2 hét előre)."""
    ma = ma or date.today()
    tol, ig = ma - timedelta(days=14), ma + timedelta(days=14)
    return kezilabda(tol, ig) + kosar(tol, ig)


if __name__ == "__main__":
    nap = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    for m in sorted(osszes(nap), key=lambda m: (m["nap"], m["ido"] or "99")):
        print(f"   {m['nap']} {m['ido']:>5} | {m['bajnoksag']} | {m['hazai']} – {m['vendeg']} | {m['golok']} | {m['helyszin']}")
