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
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

from poszt_valtozatos import Stilus

MAGYAR_TZ = ZoneInfo("Europe/Budapest")

MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")

# ⬇️⬇️⬇️ ITT KAPCSOLOD KI/BE AZ AUTOMATA FACEBOOK-POSZTOLÁST ⬇️⬇️⬇️
FACEBOOK_POSZTOLAS_AKTIV = True

OLDALAK_FAJL = "fb_oldalak.json"
ALLAPOT_FAJL = "fb_oldal_allapot.json"

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
        })
    return bejegyzesek

def lekerdez(rss_url):
    try:
        r = requests.get(rss_url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ HTTP {r.status_code}")
            return None
        return feldolgoz(r.content)
    except Exception as ex:
        print(f"  ❌ {ex}")
        return None


# ════════════════════════════════════════════
#  📘  FACEBOOK POSZT
# ════════════════════════════════════════════
def facebook_szoveg(oldal_nev, b):
    st = Stilus("megosztas")
    szoveg = b["szoveg"] or b["cim"]
    if len(szoveg) > MAX_SZOVEG:
        szoveg = szoveg[:MAX_SZOVEG].rsplit(" ", 1)[0] + "…"
    sorok = [st.bevezeto.format(nev=oldal_nev), ""]
    if szoveg:
        sorok += [f"„{szoveg}”", ""]
    if b["link"]:
        sorok.append(f"👉 {b['link']}")
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

        # Régebbitől az újabb felé osztja meg
        for b in reversed(bejegyzesek):
            if b["azonosito"] in latott:
                continue
            szoveg = facebook_szoveg(nev, b)
            print("\n" + szoveg + "\n")
            if FACEBOOK_POSZTOLAS_AKTIV and not facebook_poszt_kuldese(szoveg):
                break  # sikertelen: a következő futás újra megpróbálja
            latott.append(b["azonosito"])

        allapot[rss] = latott[-200:]

    ment_allapot(allapot)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
