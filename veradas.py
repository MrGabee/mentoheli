"""
🩸 Heti véradás-ajánló – az OVSZ (Országos Vérellátó Szolgálat) keresőjéből
Hétfőnként a hét véradásai Csepelen, a XX., XIX. és IX. kerületben és
Szigetszentmiklóson (az irányítószám alapján szűrve).
Forrás: https://www.ovsz.hu/hu/ver/veradasok (a két hétre előre látható események)
"""

import re
import html
import requests
from datetime import date, timedelta

from poszt_valtozatos import Stilus

OLDAL = "https://www.ovsz.hu/hu/ver/veradasok"
KERESO = "https://www.ovsz.hu/sites/all/scripts/gps2020/esemenyek-table.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "hu",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": OLDAL,
}

# A kereső térképes koordinátái (a telepulesek.js "Budapest XXI. kerület"
# sora alapján) és a sugár km-ben; a pontos szűrés az irányítószám alapján megy.
XXI_KERULET = (0.5835, 0.4457)
SUGAR_KM = 20

# XX. (120x), XXI. (121x), XIX. (119x), IX. (109x) kerület, Szigetszentmiklós (2310)
CIM_MINTA = re.compile(r"^(12[01]\d|119\d|109\d)\s+Budapest|^2310\b|Szigetszentmikl[oó]s", re.I)

# Az állandó véradóhelyek (pl. a Köves úti Délpesti Területi Vérellátó) minden
# héten szerepelnek; True = a heti poszt csak akkor megy, ha kitelepült véradás is van.
# A kitelepült véradásokról előző este külön emlékeztető megy (emlekezteto_szoveg).
CSAK_HA_VAN_KITELEPULT = False
ALLANDO_MINTA = re.compile(r"Vérellátó|RVK", re.I)

NAPOK = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]
NAP_ROVID = ["H", "K", "Sze", "Cs", "P", "Szo", "V"]


def _szoveg(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def feldolgoz(valasz):
    """A kereső táblázatának sorai: {"nap", "kezd", "zar", "hely", "cim"}."""
    lista = []
    for sor in re.findall(r"<tr>(.*?)</tr>", valasz, re.S):
        cellak = [_szoveg(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", sor, re.S)]
        if len(cellak) < 5:
            continue
        datum = re.match(r"(\d{4})-(\d{2})-(\d{2})", cellak[0])
        if not datum:
            continue
        lista.append({
            "nap":  date(int(datum.group(1)), int(datum.group(2)), int(datum.group(3))),
            "kezd": cellak[1][:5],
            "zar":  cellak[2][:5],
            "hely": cellak[3],
            "cim":  cellak[4],
        })
    return lista


def esemenyek():
    """A környékbeli véradások, vagy None, ha a forrás nem érhető el."""
    try:
        r = requests.post(KERESO, headers=HEADERS, timeout=40, data={
            "latitude_percent": 1.0 - XXI_KERULET[0], "longitude_percent": XXI_KERULET[1],
            "kereses_radius": SUGAR_KM, "idopontfoglalas": "off"})
        if r.status_code != 200:
            print(f"  ⚠️ OVSZ HTTP {r.status_code}")
            return None
        lista = [e for e in feldolgoz(r.text) if CIM_MINTA.search(e["cim"])]
        print(f"  🩸 OVSZ: {len(lista)} környékbeli véradás")
        return lista
    except Exception as ex:
        print(f"  ❌ OVSZ: {ex}")
        return None


def _rovid_ido(ido):
    return ido[1:] if ido.startswith("0") else ido


def heti_szoveg(hetfo, lista=None):
    """A hét (hétfőtől vasárnapig) véradásai helyszínenként.
    None = a forrás hibás (később újrapróbálja), "" = nincs véradás."""
    if lista is None:
        lista = esemenyek()
        if lista is None:
            return None
    vasarnap = hetfo + timedelta(days=6)
    heti = sorted((e for e in lista if hetfo <= e["nap"] <= vasarnap), key=lambda e: (e["nap"], e["kezd"]))
    if not heti:
        return ""
    if CSAK_HA_VAN_KITELEPULT and all(ALLANDO_MINTA.search(e["hely"]) for e in heti):
        print("  ℹ️ A héten csak az állandó véradóhely szerepel, nincs új véradás.")
        return ""

    helyek = {}
    for e in heti:
        helyek.setdefault((e["hely"], e["cim"]), []).append(e)

    st = Stilus("veradas", hetfo.isoformat())
    sorok = [st.cim, f"📅 {hetfo.strftime('%m.%d.')} – {vasarnap.strftime('%m.%d.')}", st.vonal(), "",
             st.bevezeto, ""]
    for (hely, cim), napok in helyek.items():
        sorok.append(f"🏥 {hely}")
        sorok.append(f"   📍 {cim}")
        idopontok = [f"{NAP_ROVID[e['nap'].weekday()]} {e['nap'].strftime('%m.%d.')} "
                     f"{_rovid_ido(e['kezd'])}–{_rovid_ido(e['zar'])}" for e in napok]
        sorok.append("   🕒 " + ", ".join(idopontok))
        sorok.append("")
    sorok += ["📝 Időpontot foglalni (nem kötelező) és minden részletet itt találsz:", OLDAL, "",
              "❤️ Egy véradással akár három életet is megmenthetsz. Vigyél magaddal személyit, "
              "lakcímkártyát és TAJ-kártyát, és előtte egyél, igyál rendesen!"]
    if st.zaro:
        sorok += ["", st.zaro]
    sorok.append("#véradás #Csepel #Pesterzsébet #Szigetszentmiklós")
    return "\n".join(sorok)


def emlekezteto_szoveg(ma, lista=None):
    """Előző esti emlékeztető a holnapi kitelepült (nem állandó helyszínű) véradásokról.
    None = a forrás hibás, "" = holnap nincs kitelepült véradás."""
    if lista is None:
        lista = esemenyek()
        if lista is None:
            return None
    holnap = ma + timedelta(days=1)
    holnapi = sorted((e for e in lista if e["nap"] == holnap and not ALLANDO_MINTA.search(e["hely"])),
                     key=lambda e: e["kezd"])
    if not holnapi:
        return ""
    st = Stilus("veradas_emlekezteto", ma.isoformat())
    sorok = [st.cim, f"📅 Holnap, {holnap.strftime('%m.%d.')} ({NAPOK[holnap.weekday()]})", st.vonal(), "",
             st.bevezeto, ""]
    for e in holnapi:
        sorok += [f"🏥 {e['hely']}", f"   📍 {e['cim']}",
                  f"   🕒 {_rovid_ido(e['kezd'])}–{_rovid_ido(e['zar'])}", ""]
    sorok += ["📝 Részletek és időpontfoglalás:", OLDAL, "",
              "🪪 Vigyél személyit, lakcímkártyát és TAJ-kártyát, és előtte egyél, igyál rendesen!"]
    if st.zaro:
        sorok += ["", st.zaro]
    sorok.append("#véradás #Csepel #Pesterzsébet #Szigetszentmiklós")
    return "\n".join(sorok)
