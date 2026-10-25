"""
📣 Facebook-oldal figyelő – más oldalak posztjainak továbbosztása
Adatforrás: az fb_oldalak.json-ban megadott RSS-csatornák (rss.app /
FetchRSS készíti őket a nyilvános Facebook-oldalakból)
Értesítés: Facebook poszt (Mr.Gabee oldal, Make.com webhookon keresztül)
egy rövid, személyes bevezetővel és az eredeti poszt linkjével.
Első futáskor egy oldal meglévő posztjait csak megjegyzi, nem osztja meg,
hogy ne zúdítson ki egyszerre sok régi bejegyzést.
"""

import os
import json
import re
import hashlib
import requests

import poszt_valtozatos
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from poszt_valtozatos import Stilus

MAGYAR_TZ = ZoneInfo("Europe/Budapest")

MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")
# A képes posztokat a színes posztok Make-forgatókönyve teszi ki ("kep" mező)
KEPES_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL_SZINES", "")

# ⬇️⬇️⬇️ ITT KAPCSOLOD KI/BE AZ AUTOMATA FACEBOOK-POSZTOLÁST ⬇️⬇️⬇️
FACEBOOK_POSZTOLAS_AKTIV = True

OLDALAK_FAJL = "fb_oldalak.json"
ALLAPOT_FAJL = "fb_oldal_allapot.json"
# Közös csendes ablak: amíg tart, a színes posztok várnak (szines_posztok.py olvassa)
CSENDES_FAJL = "csendes_ablak.json"

# Egy bejegyzés szövegéből legfeljebb ennyi karakter kerül a posztba
MAX_SZOVEG = 400

HEADERS = {"User-Agent": "Mozilla/5.0 (mentoheli fb oldal figyelo)"}


def magyar_ido():
    return datetime.now(MAGYAR_TZ)


# ════════════════════════════════════════════
#  💾  ÁLLAPOT
# ════════════════════════════════════════════
def betolt(fajl, alap):
    if os.path.exists(fajl):
        try:
            with open(fajl, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return alap

def ment_allapot(allapot):
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=2)

def hash_id(szoveg):
    return hashlib.md5(szoveg.encode("utf-8")).hexdigest()[:12]


# ════════════════════════════════════════════
#  📡  RSS FELDOLGOZÁS
# ════════════════════════════════════════════
def _helyi_nev(tag):
    return tag.rsplit("}", 1)[-1]

def _tiszta_szoveg(html):
    """HTML-címkék és felesleges szóközök eltávolítása."""
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup
        szoveg = BeautifulSoup(html, "html.parser").get_text(" ")
    except Exception:
        szoveg = html
    return " ".join(szoveg.split())

def _elso_kep(html):
    """Az eredeti poszt első képe (a Facebook-emojik nélkül), vagy ""."""
    for src in re.findall(r'<img[^>]+src="([^"]+)"', html or ""):
        src = src.replace("&amp;", "&")
        if src.startswith("http") and "emoji" not in src and "/images/" not in src:
            return src
    return ""

def feldolgoz(xml_szoveg):
    """RSS 2.0 és Atom bejegyzések: [{azonosito, cim, szoveg, link}], legújabb elöl."""
    gyoker = ET.fromstring(xml_szoveg)
    bejegyzesek = []
    for elem in gyoker.iter():
        if _helyi_nev(elem.tag) not in ("item", "entry"):
            continue
        m = {}
        for gyerek in elem:
            nev = _helyi_nev(gyerek.tag)
            if nev == "link" and gyerek.get("href"):
                m.setdefault("link", gyerek.get("href"))
            elif nev not in m:
                m[nev] = (gyerek.text or "").strip()
        link = m.get("link", "")
        azonosito = m.get("guid") or m.get("id") or link
        if not azonosito:
            continue
        bejegyzesek.append({
            "azonosito": hash_id(azonosito),
            "cim": _tiszta_szoveg(m.get("title", "")),
            "szoveg": _tiszta_szoveg(m.get("description") or m.get("summary") or m.get("content", "")),
            "link": link,
            "kep": _elso_kep(m.get("content") or m.get("description") or m.get("summary") or ""),
        })
    return bejegyzesek

def lekerdez(rss_url):
    try:
        r = requests.get(rss_url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ HTTP {r.status_code}")
            return None
        bejegyzesek = feldolgoz(r.content)
    except Exception as ex:
        print(f"  ❌ {ex}")
        return None
    # Az RSS-Bridge a saját hibáit is bejegyzésként adja vissza: ezek nem posztok,
    # sosem mehetnek ki, és az oldal lekérése ilyenkor sikertelennek számít.
    hibak = [b for b in bejegyzesek if bridge_hiba(b)]
    for b in hibak:
        print(f"  ⚠️ RSS-Bridge hiba: {b['cim'][:120]}")
    return None if hibak else bejegyzesek

def bridge_hiba(b):
    return (b["cim"].startswith("Bridge returned error")
            or "localhost" in b["link"]
            or "RssBridge" in b["szoveg"]
            or "HttpException" in b["szoveg"])


# ════════════════════════════════════════════
#  📘  FACEBOOK POSZT
# ════════════════════════════════════════════
def facebook_szoveg(oldal_nev, b, max_szoveg=MAX_SZOVEG):
    st = Stilus("megosztas")
    szoveg = b["szoveg"] or b["cim"]
    if len(szoveg) > max_szoveg:
        szoveg = szoveg[:max_szoveg].rsplit(" ", 1)[0] + "…"
    sorok = [st.bevezeto.format(nev=oldal_nev), ""]
    if szoveg:
        sorok += [f"„{szoveg}”", ""]
    if b["link"]:
        sorok.append(f"👉 {b['link']}")
    return "\n".join(sorok)

def csendes_ablak(perc):
    """A színes posztokat `perc` percig hátrébb tolja (a meglévő ablakot csak hosszabbítja)."""
    ig = (magyar_ido() + timedelta(minutes=perc)).strftime("%Y-%m-%d %H:%M")
    regi = betolt(CSENDES_FAJL, {}).get("ig", "")
    if ig > regi:
        with open(CSENDES_FAJL, "w", encoding="utf-8") as f:
            json.dump({"ig": ig}, f, ensure_ascii=False, indent=2)
        print(f"  🤫 Színes posztok szünetelnek eddig: {ig}")

def facebook_poszt_kuldese(szoveg, kep=""):
    """Poszt a Facebook Oldalra a Make.com webhookon keresztül. Ha az eredeti
    posztnak van képe, képes posztként megy ki, hogy látszódjon is."""
    if kep and KEPES_WEBHOOK_URL:
        try:
            resp = requests.post(KEPES_WEBHOOK_URL, json={"message": poszt_valtozatos.atrendez(szoveg), "kep": kep}, timeout=60)
            if resp.status_code == 200:
                print("  ✅ Képes Facebook poszt elküldve (Make.com-on keresztül).")
                return True
            print(f"  ⚠️  Képes poszt sikertelen (HTTP {resp.status_code}), kép nélkül próbálom.")
        except Exception as e:
            print(f"  ⚠️  Képes poszt hiba: {e}, kép nélkül próbálom.")
    if not MAKE_WEBHOOK_URL:
        print("  ⚠️  Nincs beállítva MAKE_WEBHOOK_URL - Facebook-posztolás kihagyva.")
        return False
    try:
        resp = requests.post(MAKE_WEBHOOK_URL, json={"message": poszt_valtozatos.atrendez(szoveg)}, timeout=20)
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
    print(f"📣 Facebook-oldal figyelő – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    oldalak = betolt(OLDALAK_FAJL, {}).get("oldalak", [])
    if not oldalak:
        print("ℹ️ Nincs még figyelt oldal az fb_oldalak.json-ban.")
        return

    allapot = betolt(ALLAPOT_FAJL, {})

    for oldal in oldalak:
        nev, rss = oldal.get("nev", ""), oldal.get("rss", "")
        if not rss:
            continue
        print(f"\n🌐 {nev}: {rss}")
        bejegyzesek = lekerdez(rss)
        if bejegyzesek is None:
            continue

        latott = allapot.get(rss)
        if latott is None:
            # Első futás ennél az oldalnál: csak megjegyzi a meglévőket
            allapot[rss] = [b["azonosito"] for b in bejegyzesek]
            print(f"  🆕 Új oldal, {len(bejegyzesek)} meglévő bejegyzés megjegyezve (nem osztja meg).")
            continue

        szuro = re.compile(oldal["szuro"]) if oldal.get("szuro") else None
        # Régebbitől az újabb felé osztja meg
        for b in reversed(bejegyzesek):
            if b["azonosito"] in latott:
                continue
            if szuro and not szuro.search(f"{b['cim']} {b['szoveg']}"):
                print(f"  ⏭️ Nem illik a szűrőre: {b['cim'][:80]}")
                latott.append(b["azonosito"])
                continue
            szoveg = facebook_szoveg(nev, b, oldal.get("max_szoveg", MAX_SZOVEG))
            print("\n" + szoveg + "\n")
            if FACEBOOK_POSZTOLAS_AKTIV and not facebook_poszt_kuldese(szoveg, b.get("kep", "")):
                break  # sikertelen: a következő futás újra megpróbálja
            latott.append(b["azonosito"])
            if FACEBOOK_POSZTOLAS_AKTIV and oldal.get("csendes_perc"):
                csendes_ablak(oldal["csendes_perc"])

        allapot[rss] = latott[-200:]

    ment_allapot(allapot)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
