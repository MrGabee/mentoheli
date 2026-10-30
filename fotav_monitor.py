"""
🔥 FŐTÁV Távhő Monitor – Csepel (XXI. kerület)
Adatforrás: gmp.fotav.hu/KMZ/munkatabl.html
Szűrés: Csepeli irányítószámok (1211-1215)
Futtatás: GitHub Actions (percenként, self-loop)

Az új csepeli eseményekről:
- e-mail megy a szerkesztőségnek (EMAIL_CIMZETT_FOTAV, ha nincs: EMAIL_CIMZETT_ARAM, mint a Vízműveké és az áramszüneté),
- és egy összevont Facebook-poszt a Make.com webhookon át (MAKE_WEBHOOK_URL).
  Éjszaka a poszt reggelig vár (ejszakai_sor).
"""

import os
import re
import json
import hashlib
import smtplib
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

import email_arculat as ea
import ejszakai_sor
import poszt_valtozatos
from poszt_valtozatos import Stilus

MAGYAR_TZ = ZoneInfo("Europe/Budapest")

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ.get("EMAIL_CIMZETT_FOTAV") or os.environ["EMAIL_CIMZETT_ARAM"]
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")
FACEBOOK_POSZTOLAS_AKTIV = True
# Ugyanarról a címről ennyi napon belül nem megy új poszt (e-mail igen).
CIM_ISMETLES_NAP = 7

FOTAV_URL    = "https://gmp.fotav.hu/KMZ/munkatabl.html"
FOTAV_TERKEP = "https://gmp.fotav.hu/mappublic.aspx"
ALLAPOT_FAJL = "fotav_allapot.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
    "Referer": "https://gmp.fotav.hu/mappublic.aspx",
}

# Csepel irányítószámok (csak XXI. kerület valódi csepeli részei)
CSEPEL_IRSZ = ["1211", "1212", "1213", "1214", "1215"]


# ════════════════════════════════════════════
#  💾  ÁLLAPOT
# ════════════════════════════════════════════
def betolt_allapot():
    if os.path.exists(ALLAPOT_FAJL):
        try:
            with open(ALLAPOT_FAJL) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def ment_allapot(allapot):
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=2)

def hash_id(szoveg):
    return hashlib.md5(szoveg.encode("utf-8")).hexdigest()[:12]


# ════════════════════════════════════════════
#  📍  CSEPEL SZŰRŐ
# ════════════════════════════════════════════
def csepel_e(cim):
    """Ellenőrzi hogy a cím csepeli irányítószámot tartalmaz-e."""
    for irsz in CSEPEL_IRSZ:
        if irsz in cim:
            return True
    return False


# ════════════════════════════════════════════
#  📡  LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez():
    """FŐTÁV munkatabl.html scraping."""
    try:
        print(f"🌐 Lekérdezés: {FOTAV_URL}")
        r = requests.get(FOTAV_URL, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ HTTP {r.status_code}")
            return []

        soup = BeautifulSoup(r.content, "html.parser")
        esemenyek = []

        # GridView1 – Jelenlegi munkavégzések
        gv1 = soup.find("table", id="GridView1")
        if gv1:
            for sor in gv1.find_all("tr")[1:]:  # fejléc kihagyása
                cellak = sor.find_all("td")
                if len(cellak) >= 4:
                    cim     = cellak[0].get_text(strip=True)
                    kezdes  = cellak[1].get_text(strip=True)
                    veg     = cellak[2].get_text(strip=True)
                    info    = cellak[3].get_text(strip=True)
                    utfelb  = cellak[4].get_text(strip=True) if len(cellak) > 4 else "—"
                    if csepel_e(cim):
                        esemenyek.append({
                            "tipus": "JELENLEGI_MUNKA",
                            "cim": cim, "kezdes": kezdes,
                            "veg": veg, "info": info,
                            "utfelbontas": utfelb
                        })

        # GridView2 – Jelenlegi kiesett épületek
        gv2 = soup.find("table", id="GridView2")
        if gv2:
            for sor in gv2.find_all("tr")[1:]:
                cellak = sor.find_all("td")
                if len(cellak) >= 3:
                    cim    = cellak[0].get_text(strip=True)
                    kezdes = cellak[1].get_text(strip=True)
                    veg    = cellak[2].get_text(strip=True)
                    if csepel_e(cim) and "nincsenek" not in cim.lower():
                        esemenyek.append({
                            "tipus": "KIESETT_EPULET",
                            "cim": cim, "kezdes": kezdes,
                            "veg": veg, "info": "Kiesett épület",
                            "utfelbontas": "—"
                        })

        # GridView3 – Tervezett munkavégzések
        gv3 = soup.find("table", id="GridView3")
        if gv3:
            for sor in gv3.find_all("tr")[1:]:
                cellak = sor.find_all("td")
                if len(cellak) >= 4:
                    cim     = cellak[0].get_text(strip=True)
                    kezdes  = cellak[1].get_text(strip=True)
                    veg     = cellak[2].get_text(strip=True)
                    info    = cellak[3].get_text(strip=True)
                    utfelb  = cellak[4].get_text(strip=True) if len(cellak) > 4 else "—"
                    if csepel_e(cim):
                        esemenyek.append({
                            "tipus": "TERVEZETT_MUNKA",
                            "cim": cim, "kezdes": kezdes,
                            "veg": veg, "info": info,
                            "utfelbontas": utfelb
                        })

        # GridView4 – Tervezett kiesett épületek
        gv4 = soup.find("table", id="GridView4")
        if gv4:
            for sor in gv4.find_all("tr")[1:]:
                cellak = sor.find_all("td")
                if len(cellak) >= 3:
                    cim    = cellak[0].get_text(strip=True)
                    kezdes = cellak[1].get_text(strip=True)
                    veg    = cellak[2].get_text(strip=True)
                    if csepel_e(cim) and "nincsenek" not in cim.lower():
                        esemenyek.append({
                            "tipus": "TERVEZETT_KIESETT",
                            "cim": cim, "kezdes": kezdes,
                            "veg": veg, "info": "Tervezett kiesés",
                            "utfelbontas": "—"
                        })

        print(f"  📊 Csepeli találatok: {len(esemenyek)}")
        return esemenyek

    except Exception as ex:
        print(f"  ❌ Hiba: {ex}")
        import traceback
        traceback.print_exc()
        return []


# ════════════════════════════════════════════
#  🏠  CÍMEK
# ════════════════════════════════════════════
# Az oldal kétféle címformát ad ugyanarra a házra:
#   "Budapest, Kossuth Lajos u. 105, 1211 Magyarország"
#   "1211 Budapest, Kossuth Lajos utca 105."
def szep_cim(cim):
    c = re.sub(r"\b\d{4}\b", "", cim)
    c = re.sub(r"\b(Budapest|Magyarország)\b", "", c)
    c = re.sub(r"\s*,\s*", ", ", c).strip(" ,")
    c = re.sub(r"\s{2,}", " ", c)
    if re.search(r"\d[a-zA-Z/-]*$", c):
        c += "."
    return c or cim


def cim_kulcs(cim):
    c = szep_cim(cim).lower()
    c = re.sub(r"\b(utca|u)\b\.?", "u", c)
    c = re.sub(r"\b(út|ut)\b\.?", "ut", c)
    return re.sub(r"[^0-9a-záéíóöőúüű]", "", c)


# ════════════════════════════════════════════
#  📧  E-MAIL
# ════════════════════════════════════════════
# típus: (rövid név, kártyaszín, címkeszín, folyamatban-e)
TIPUSOK = {
    "JELENLEGI_MUNKA":   ("Munkavégzés",           ea.SZIN["piros"], None, True),
    "KIESETT_EPULET":    ("Szünetel a szolgáltatás", ea.SZIN["piros"], None, True),
    "TERVEZETT_MUNKA":   ("Tervezett munkavégzés", ea.SZIN["sarga"], ea.SZIN["sarga_szoveg"], False),
    "TERVEZETT_KIESETT": ("Tervezett szünet",      ea.SZIN["sarga"], ea.SZIN["sarga_szoveg"], False),
}

TAVHO_JELVENY = ('<span style="display:inline-block;font-weight:bold;font-size:13px;line-height:1;'
                 'padding:6px 9px;border-radius:4px;background:#e8590c;color:#ffffff;'
                 'font-family:Arial,sans-serif;letter-spacing:.5px">🔥 TÁVHŐ</span>')


def _ures(x):
    return not x or x.strip() in ("—", "-", "&nbsp;")


def gmaps_link(cim):
    return f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(cim)}"


def email_kartya(e):
    nev, szin, cimke_szin, _ = TIPUSOK.get(e["tipus"], (e["tipus"], ea.SZIN["kek"], None, False))
    info = e.get("info", "")
    if info in ("Kiesett épület", "Tervezett kiesés"):
        info = ""
    sorok = [
        ("Kezdés", e.get("kezdes", "")),
        ("Vége", e.get("veg", "")),
        ("Részletek", info),
        ("Útfelbontás", "" if _ures(e.get("utfelbontas")) else e["utfelbontas"]),
        ("Teljes cím", e["cim"]),
    ]
    test = (ea.adat_tabla(sorok)
            + ea.gomb("📍 Térkép", gmaps_link(e["cim"]))
            + ea.gomb("Főtáv térkép", FOTAV_TERKEP, masodlagos=True))
    return ea.kartya(szin, nev, szep_cim(e["cim"]), test,
                     jelvenyek=TAVHO_JELVENY, cimke_szin=cimke_szin)


def email_kuldes(uj_esetek):
    db = len(uj_esetek)
    elso = uj_esetek[0]
    if db == 1:
        targy = f"🔥 Főtáv · {TIPUSOK.get(elso['tipus'], (elso['tipus'],))[0]} · {szep_cim(elso['cim'])}"
    else:
        targy = f"🔥 Főtáv: {db} új csepeli esemény · {szep_cim(elso['cim'])} és még {db - 1}"

    # A folyamatban lévők elöl, utána a tervezettek
    rendezett = sorted(uj_esetek, key=lambda e: not TIPUSOK.get(e["tipus"], ("", "", None, False))[3])
    html = ea.keret("".join(email_kartya(e) for e in rendezett),
                    "Főtáv Figyelő · Csepel (1211–1215) · ugyanarról a bejegyzésről több levél nem jön")

    szoveges = "Főtáv Figyelő – új csepeli események\n"
    for e in rendezett:
        szoveges += (f"\n{TIPUSOK.get(e['tipus'], (e['tipus'],))[0]}: {szep_cim(e['cim'])}\n"
                     f"  {e.get('kezdes', '')} – {e.get('veg', '')}\n")
    szoveges += f"\nFőtáv térkép: {FOTAV_TERKEP}\n"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"Főtáv Figyelő <{EMAIL_KULDO}>"
    msg["To"]      = EMAIL_CIMZETT
    msg.attach(MIMEText(szoveges, "plain", "utf-8"))
    msg.attach(MIMEText(html,     "html",  "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
        smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
    print(f"📧 E-mail elküldve: {targy}")


# ════════════════════════════════════════════
#  📘  FACEBOOK (Make.com webhookon keresztül)
# ════════════════════════════════════════════
FB_CSOPORTOK = [
    ("KIESETT_EPULET",    "🔴 Most szünetel a távhőszolgáltatás"),
    ("JELENLEGI_MUNKA",   "🛠️ Most zajló munkák"),
    ("TERVEZETT_KIESETT", "🟠 Tervezett szünet"),
    ("TERVEZETT_MUNKA",   "🗓️ Tervezett munkák"),
]


def _ido(e):
    k, v = e.get("kezdes", ""), e.get("veg", "")
    if not _ures(k) and not _ures(v):
        return f"🕐 {k} – {v}"
    if not _ures(k):
        return f"🕐 Kezdete: {k}"
    return f"🕐 Várható vége: {v}" if not _ures(v) else ""


def facebook_szoveg(esetek):
    st = Stilus("fotav")
    sorok = [st.cim, st.vonal(), "", st.bevezeto]
    for tipus, felirat in FB_CSOPORTOK:
        csoport = [e for e in esetek if e["tipus"] == tipus]
        if not csoport:
            continue
        sorok += ["", felirat]
        for e in csoport:
            sorok.append(f"📍 {szep_cim(e['cim'])}")
            ido = _ido(e)
            if ido:
                sorok.append(ido)
            info = (e.get("info") or "").strip()
            if info and not info.lower().startswith("tel") and info not in ("Kiesett épület", "Tervezett kiesés"):
                sorok.append(f"ℹ️ Oka: {info}")
            if not _ures(e.get("utfelbontas")) and e["utfelbontas"].lower().startswith("i"):
                sorok.append("🚧 Útfelbontással jár")
    sorok += ["", f"🔗 A Főtáv térképe: {FOTAV_TERKEP}", "Forrás: FŐTÁV"]
    if st.zaro:
        sorok += ["", st.zaro]
    sorok += ["", "#Csepel #távhő #FŐTÁV"]
    return "\n".join(sorok)


def facebook_poszt_kuldese(szoveg):
    if not MAKE_WEBHOOK_URL:
        print("  ⚠️  Nincs beállítva MAKE_WEBHOOK_URL - Facebook-posztolás kihagyva.")
        return False
    try:
        resp = requests.post(MAKE_WEBHOOK_URL, json={"message": poszt_valtozatos.atrendez(szoveg)}, timeout=20)
        if resp.status_code == 200:
            print("  ✅ Facebook poszt elküldve (Make.com-on keresztül).")
            return True
        print(f"  ⚠️  Facebook poszt sikertelen (HTTP {resp.status_code})")
    except Exception as ex:
        print(f"  ⚠️  Facebook poszt hiba: {type(ex).__name__}")
    return False


def posztolando(uj, allapot):
    """Címenként egy bejegyzés (a kiesés erősebb a munkánál), és ami az
    utóbbi napokban már kiment, az nem megy ki újra."""
    t = magyar_ido()
    posztolt = allapot.setdefault("fb_cimek", {})
    sorrend = [t for t, _ in FB_CSOPORTOK]
    valasztott = {}
    for e in sorted(uj, key=lambda e: sorrend.index(e["tipus"]) if e["tipus"] in sorrend else 9):
        k = cim_kulcs(e["cim"])
        if k in valasztott:
            continue
        try:
            if (t - datetime.fromisoformat(posztolt[k])).days < CIM_ISMETLES_NAP:
                print(f"🔁 Nemrég posztolt cím, kihagyva: {szep_cim(e['cim'])}")
                continue
        except (KeyError, ValueError):
            pass
        valasztott[k] = e
    for k in valasztott:
        posztolt[k] = t.isoformat()
    return list(valasztott.values())


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"🔥 FŐTÁV Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    if FACEBOOK_POSZTOLAS_AKTIV:
        ejszakai_sor.sor_kiurites(regi, facebook_poszt_kuldese)
    uj   = []

    esemenyek = lekerdez()

    for e in esemenyek:
        rid = hash_id(e["tipus"] + e["cim"] + e["kezdes"])
        if rid not in regi:
            uj.append(e)
            regi[rid] = {
                "cim": e["cim"][:100],
                "talalt": magyar_ido().isoformat()
            }

    print(f"\n🔥 Új csepeli FŐTÁV esemény: {len(uj)}")
    if uj:
        # Most zajló munka/kiesés: azonnal posztolok és levél is megy. Tervezett:
        # a poszt a következő szabad sávba kerül, levél nem jön róla.
        surgos = [e for e in uj if not e["tipus"].startswith("TERVEZETT")]
        if surgos:
            email_kuldes(surgos)
        if FACEBOOK_POSZTOLAS_AKTIV:
            fb = posztolando(uj, regi)
            fb_surgos = [e for e in fb if not e["tipus"].startswith("TERVEZETT")]
            fb_raeros = [e for e in fb if e["tipus"].startswith("TERVEZETT")]
            if fb_surgos:
                print("\n📘 Facebook poszt küldése...")
                ejszakai_sor.kuld_vagy_sorba(regi, facebook_szoveg(fb_surgos), facebook_poszt_kuldese, surgos=True)
            if fb_raeros:
                print("\n🗓️ Tervezett munka: a poszt sorba kerül...")
                ejszakai_sor.kuld_vagy_sorba(regi, facebook_szoveg(fb_raeros), facebook_poszt_kuldese, surgos=False)
    else:
        print("✅ Nincs új esemény.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
