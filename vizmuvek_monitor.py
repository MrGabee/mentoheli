"""
💧 Fővárosi Vízművek Monitor – Csepel (XXI.) + Pesterzsébet (XX.)
   + Szigetszentmiklós
Adatforrás: vizmuvek.hu munkatérkép
Szűrés: kerület-prefix vagy településnév
Értesítés: E-mail (EMAIL_CIMZETT_ARAM) + Facebook poszt (Mr.Gabee oldal, AUTOMATA, szövegesen)
"""

import os
import json
import hashlib
import smtplib
import requests

import poszt_valtozatos
import ejszakai_sor
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

from poszt_valtozatos import Stilus
import email_arculat as ea

# ─────────────────────────────────────────────
#  🕐  MAGYAR IDŐZÓNA (UTC+2, GitHub Actions UTC-t használ)
# ─────────────────────────────────────────────
from zoneinfo import ZoneInfo
MAGYAR_TZ = ZoneInfo("Europe/Budapest")

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


EMAIL_KULDO      = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO     = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT    = os.environ["EMAIL_CIMZETT_ARAM"]
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")

# ⬇️ E-MAIL KAPCSOLÓ: Gábor kérésére (2026.10.21.) az oldalra szánt értesítések
# nem mennek e-mailben (a kollégája kapta őket). A Facebook-posztolás marad.
# 2026.10.28.: Gábor kérésére újra megy, a kollégának (EMAIL_CIMZETT_ARAM).
EMAIL_AKTIV = True

# ⬇️⬇️⬇️ ITT KAPCSOLOD KI/BE AZ AUTOMATA FACEBOOK-POSZTOLÁST ⬇️⬇️⬇️
# True  = automatikusan posztol a Facebook Oldalra is, egy Make.com
#         automatizáción keresztül (webhook -> Facebook Pages modul) -
#         ehhez csak egy érvényes MAKE_WEBHOOK_URL GitHub Secret kell,
#         Meta fejlesztői app / token NEM szükséges hozzá.
# False = csak emailt küld, a Facebook-szöveg ott lesz kimásolható
FACEBOOK_POSZTOLAS_AKTIV = True

VIZMUVEK_URL = "https://www.vizmuvek.hu/hu/kezdolap/informaciok/munkaterkep-hol-dolgozunk"
ALLAPOT_FAJL = "vizmuvek_allapot.json"

# Ide írd be a saját rajzolt képed URL-jét, ha van - a Facebook-posztba
# automatikusan bekerül a másolható szöveg alá. Ha nincs kép, hagyd üresen.
KEP_URL = "https://mrgabee.hu/vizmuvek.png"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

TIPUS_MAP = {
    "geo_0": ("🔴", "VÍZHIÁNY",           "#c0392b"),
    "geo_1": ("🟠", "VÁRHATÓ VÍZHIÁNY",   "#e67e22"),
    "geo_2": ("🔵", "FORGALOMKORLÁTOZÁS", "#2980b9"),
}


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
#  📍  TERÜLET SZŰRŐ – Csepel (XXI.) + Pesterzsébet (XX.)
#      + Szigetszentmiklós
# ════════════════════════════════════════════
def terulet_cimke(cim):
    """Visszaadja a megjelenítendő terület-címkét, ha a cím a figyelt
    kerületek/települések egyikével kezdődik, vagy None-t, ha nem."""
    c = (cim or "").strip()
    if c.startswith("XXI."):
        return "XXI. kerület (Csepel)"
    if c.startswith("XX."):
        return "XX. kerület (Pesterzsébet)"
    if "szigetszentmiklós" in c.lower():
        return "Szigetszentmiklós"
    return None


def csepel_e(cim):
    """Megtartva kompatibilitásból: True, ha bármelyik figyelt területtel egyezik."""
    return terulet_cimke(cim) is not None


# ════════════════════════════════════════════
#  📡  LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez():
    try:
        print(f"🌐 Lekérdezés: {VIZMUVEK_URL}")
        r = requests.get(VIZMUVEK_URL, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ HTTP {r.status_code}")
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        esemenyek = []

        geo_divek = soup.find_all("div", class_=lambda c: c and "geo" in c.split())
        print(f"  📊 Összes geo elem: {len(geo_divek)}")

        for div in geo_divek:
            classes = div.get("class", [])
            tipus = None
            for c in classes:
                if c in TIPUS_MAP:
                    tipus = c
                    break
            if not tipus:
                continue

            title = div.get("title", "")
            if not title:
                continue

            lat_abbr = div.find("abbr", class_="latitude")
            lon_abbr = div.find("abbr", class_="longitude")
            if not lat_abbr or not lon_abbr:
                continue

            try:
                lat = float(lat_abbr.get("title", "0"))
                lon = float(lon_abbr.get("title", "0"))
            except (ValueError, TypeError):
                continue

            cim = munka = kezdes = veg = ""
            # BR tagek eltávolítása
            title_clean = title.replace("<br />", "\n").replace("<br>", "\n")
            for sor in title_clean.split("\n"):
                sor = sor.strip()
                if sor.startswith("Postacím:"):
                    cim = sor.replace("Postacím:", "").strip()
                elif sor.startswith("A munka megnevezése:"):
                    munka = sor.replace("A munka megnevezése:", "").strip()
                elif sor.startswith("Munka tervezett kezdete:"):
                    kezdes = sor.replace("Munka tervezett kezdete:", "").strip()
                elif sor.startswith("Munka tervezett vége:"):
                    veg = sor.replace("Munka tervezett vége:", "").strip()

            if not cim or not csepel_e(cim):
                continue

            terulet = terulet_cimke(cim)

            gmaps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            esemenyek.append({
                "tipus": tipus, "cim": cim, "munka": munka,
                "kezdes": kezdes, "veg": veg,
                "lat": lat, "lon": lon, "gmaps": gmaps,
                "terulet": terulet,
            })
            print(f"  🎯 [{terulet}] {cim}")

        print(f"  📊 Figyelt területi találat: {len(esemenyek)}")
        return esemenyek

    except Exception as ex:
        print(f"  ❌ {ex}")
        import traceback
        traceback.print_exc()
        return []


# ════════════════════════════════════════════
#  📘  FACEBOOK POSZT SZÖVEG (megosztott - e-mail és a Graph API is ezt használja)
# ════════════════════════════════════════════
def facebook_szoveg(esetek):
    ido = magyar_ido().strftime("%Y.%m.%d %H:%M")
    db  = len(esetek)

    erintett_teruletek = sorted(set(e["terulet"] for e in esetek))
    st = Stilus("vizmuvek")

    sorok = [
        st.cim,
        f"🕐 {ido}   •   {db} új esemény",
        st.vonal(),
        "",
        st.bevezeto,
        "",
        "",
    ]

    for terulet in erintett_teruletek:
        teruleti_esetek = [e for e in esetek if e["terulet"] == terulet]
        sorok.append(st.terulet(terulet.upper()))
        sorok.append(st.vekony())
        for e in teruleti_esetek:
            emoji, label, _ = TIPUS_MAP.get(e["tipus"], ("💧", e["tipus"], ""))
            sorok.append(f"{emoji} {label}")
            sorok.append(f"   📍 {e['cim']}")
            sorok.append(f"   🔧 {e['munka'] or '—'}")
            sorok.append(f"   ⏰ {e['kezdes'] or '—'} → {e['veg'] or '—'}")
            sorok.append(f"   🗺️ {e['gmaps']}")
            sorok.append("")

    sorok.append(st.vekony())
    sorok.append("🔗 Vízművek munkatérkép:")
    sorok.append("https://www.vizmuvek.hu/hu/kezdolap/informaciok/munkaterkep-hol-dolgozunk")
    sorok.append("📍 Figyelt terület: Csepel, Pesterzsébet, Szigetszentmiklós")
    if st.zaro:
        sorok += ["", st.zaro]

    return "\n".join(sorok)


# ════════════════════════════════════════════
#  📘  FACEBOOK AUTOMATA POSZTOLÁS (Make.com webhookon keresztül)
# ════════════════════════════════════════════
def facebook_poszt_kuldese(szoveg):
    """Szöveges posztot küld a Facebook Oldalra - nem közvetlenül a Meta
    Graph API-n keresztül, hanem egy Make.com automatizáción (Scenario)
    keresztül: ide küldünk egy egyszerű webhook-hívást a szöveggel, a
    Make.com pedig ezt posztolja ki a Facebook Oldalra. Ez elkerüli a
    Meta fejlesztői app / Business Portfolio beállítását."""
    if not MAKE_WEBHOOK_URL:
        print("  ⚠️  Nincs beállítva MAKE_WEBHOOK_URL - Facebook-posztolás kihagyva.")
        return False

    try:
        resp = requests.post(MAKE_WEBHOOK_URL, json={"message": poszt_valtozatos.atrendez(szoveg)}, timeout=20)

        if resp.status_code == 200:
            print("  ✅ Facebook poszt elküldve (Make.com-on keresztül).")
            return True
        else:
            print(f"  ⚠️  Facebook poszt sikertelen (HTTP {resp.status_code}): {resp.text[:300]}")
            return False
    except Exception as e:
        print(f"  ⚠️  Facebook poszt hiba: {e}")
        return False


# ════════════════════════════════════════════
#  📧  E-MAIL
# ════════════════════════════════════════════
VIZ_JELVENY = ('<span style="display:inline-block;font-weight:bold;font-size:13px;line-height:1;'
               'padding:6px 9px;border-radius:4px;background:#0077c8;color:#ffffff;'
               'font-family:Arial,sans-serif;letter-spacing:.5px">💧 VÍZ</span>')

# típus: (kártyacímke, csíkszín, címkeszín)
VIZ_KARTYA = {
    "geo_0": ("Vízhiány",           ea.SZIN["piros"], None),
    "geo_1": ("Várható vízhiány",   ea.SZIN["sarga"], ea.SZIN["sarga_szoveg"]),
    "geo_2": ("Forgalomkorlátozás", ea.SZIN["kek"],   None),
}


def email_kuldes(uj_esetek, fb=None):
    db = len(uj_esetek)
    rendezett = sorted(uj_esetek, key=lambda e: e["tipus"])   # vízhiány elöl
    elso = rendezett[0]
    elso_cimke = VIZ_KARTYA.get(elso["tipus"], ("Vízműves munka",))[0]
    targy = (f"💧 {elso_cimke} · {elso['terulet']} · {elso['cim']}" if db == 1
             else f"💧 Vízművek: {db} új munka · {elso['cim']} és még {db - 1}")

    kartyak = ""
    szoveges = "Vízművek Figyelő – új munkák\n"
    for e in rendezett:
        cimke, szin, cimke_szin = VIZ_KARTYA.get(e["tipus"], ("Vízműves munka", ea.SZIN["kek"], None))
        test = (ea.adat_tabla([("Terület", e["terulet"]), ("Munka", e["munka"]),
                               ("Kezdés", e["kezdes"]), ("Vége", e["veg"])])
                + ea.gomb("📍 Térkép", e["gmaps"])
                + ea.gomb("Vízművek munkatérkép", VIZMUVEK_URL, masodlagos=True))
        kartyak += ea.kartya(szin, cimke, e["cim"] or e["terulet"], test,
                             jelvenyek=VIZ_JELVENY, cimke_szin=cimke_szin)
        szoveges += f"\n{cimke}: {e['cim']} ({e['terulet']})\n  {e['munka']}\n  {e['kezdes']} – {e['veg']}\n"
    if fb:
        kartyak += ea.kartya("#1877f2", "Facebook", "Ez a poszt megy ki az oldalra",
                             '<div style="white-space:pre-wrap;font-size:13px;line-height:1.55;background:#f6f8fa;'
                             f'border:1px solid #e4e6eb;border-radius:6px;padding:12px">{ea.esc(fb)}</div>')
    html = ea.keret(kartyak, "Vízművek Figyelő · Csepel, Pesterzsébet, Szigetszentmiklós · a Fővárosi Vízművek adatai alapján")
    szoveges += f"\nVízművek munkatérkép: {VIZMUVEK_URL}\n"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"Vízművek Figyelő <{EMAIL_KULDO}>"
    msg["To"]      = EMAIL_CIMZETT
    msg.attach(MIMEText(szoveges, "plain", "utf-8"))
    msg.attach(MIMEText(html,     "html",  "utf-8"))

    if EMAIL_AKTIV:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
            smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
        print(f"📧 E-mail elküldve: {targy}")
    else:
        print(f"ℹ️ E-mail kikapcsolva (EMAIL_AKTIV = False), nem ment ki: {targy}")


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"💧 Vízművek Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    if FACEBOOK_POSZTOLAS_AKTIV:
        ejszakai_sor.sor_kiurites(regi, facebook_poszt_kuldese)
    uj   = []

    for e in lekerdez():
        rid = hash_id(e["tipus"] + e["cim"] + e["kezdes"])
        if rid not in regi:
            uj.append(e)
            regi[rid] = {"cim": e["cim"][:100], "talalt": magyar_ido().isoformat()}

    print(f"\n💧 Új esemény: {len(uj)}")
    if uj:
        # Vízhiány (geo_0): azonnal posztolok és levél is megy. Várható vízhiány,
        # forgalomkorlátozás: a poszt a következő szabad sávba kerül, levél nélkül.
        surgos = [e for e in uj if e["tipus"] == "geo_0"]
        raeros = [e for e in uj if e["tipus"] != "geo_0"]
        if surgos:
            fb_szoveg = facebook_szoveg(surgos) if FACEBOOK_POSZTOLAS_AKTIV else None
            email_kuldes(surgos, fb_szoveg)
            if FACEBOOK_POSZTOLAS_AKTIV:
                print("\n📘 Facebook poszt küldése...")
                ejszakai_sor.kuld_vagy_sorba(regi, fb_szoveg, facebook_poszt_kuldese, surgos=True)
        if raeros and FACEBOOK_POSZTOLAS_AKTIV:
            print("\n🗓️ Előre bejelentett munka: a poszt sorba kerül...")
            ejszakai_sor.kuld_vagy_sorba(regi, facebook_szoveg(raeros), facebook_poszt_kuldese, surgos=False)
    else:
        print("✅ Nincs új esemény.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
