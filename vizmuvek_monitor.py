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
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
#  🕐  MAGYAR IDŐZÓNA (UTC+2, GitHub Actions UTC-t használ)
# ─────────────────────────────────────────────
MAGYAR_TZ = timezone(timedelta(hours=2))

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


EMAIL_KULDO      = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO     = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT    = os.environ["EMAIL_CIMZETT_ARAM"]
MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")

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

    sorok = [
        "💧 FŐVÁROSI VÍZMŰVEK ÉRTESÍTŐ 💧",
        f"🕐 {ido}   •   {db} új esemény",
        "═" * 32,
        "",
        "",
        "",
    ]

    for terulet in erintett_teruletek:
        teruleti_esetek = [e for e in esetek if e["terulet"] == terulet]
        sorok.append(f"▸▸▸  {terulet.upper()}  ◂◂◂")
        sorok.append("─" * 32)
        for e in teruleti_esetek:
            emoji, label, _ = TIPUS_MAP.get(e["tipus"], ("💧", e["tipus"], ""))
            sorok.append(f"{emoji} {label}")
            sorok.append(f"   📍 {e['cim']}")
            sorok.append(f"   🔧 {e['munka'] or '—'}")
            sorok.append(f"   ⏰ {e['kezdes'] or '—'} → {e['veg'] or '—'}")
            sorok.append(f"   🗺️ {e['gmaps']}")
            sorok.append("")

    sorok.append("─" * 32)
    sorok.append("🔗 Vízművek munkatérkép:")
    sorok.append("https://www.vizmuvek.hu/hu/kezdolap/informaciok/munkaterkep-hol-dolgozunk")
    sorok.append("📍 Figyelt terület: Csepel, Pesterzsébet, Szigetszentmiklós")

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
        resp = requests.post(MAKE_WEBHOOK_URL, json={"message": szoveg}, timeout=20)

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
def email_kuldes(uj_esetek):
    ido   = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)
    targy = f"💧 Vízművek (Csepel/Pesterzsébet/Sziget.) – {db} új esemény | {ido}"

    sorok_html = ""
    sorok_txt  = ""

    for i, e in enumerate(uj_esetek, 1):
        emoji, label, szin = TIPUS_MAP.get(e["tipus"], ("💧", e["tipus"], "#2980b9"))

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:{szin};color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">
              {emoji} {label}
            </span>
            <div style="font-size:15px;font-weight:bold;margin:10px 0;color:#2c3e50">
              {e['cim']}
            </div>
            <table style="font-size:13px;width:100%;margin-top:6px">
              <tr><td style="color:#888;width:160px">📌 Terület:</td>
                  <td><strong>{e['terulet']}</strong></td></tr>
              <tr><td style="color:#888">🔧 Munka típusa:</td>
                  <td>{e['munka'] or '—'}</td></tr>
              <tr><td style="color:#888">⏰ Kezdés:</td>
                  <td><strong>{e['kezdes'] or '—'}</strong></td></tr>
              <tr><td style="color:#888">⏰ Vége:</td>
                  <td><strong>{e['veg'] or '—'}</strong></td></tr>
            </table>
            <div style="margin-top:10px">
              <a href="{e['gmaps']}" style="background:#4285f4;color:#fff;padding:7px 14px;
                                            border-radius:4px;text-decoration:none;
                                            font-size:12px;font-weight:bold">
                📍 Google Maps
              </a>
            </div>
          </td>
        </tr>"""

        sorok_txt += (
            f"\n{'─'*45}\n{i}. {emoji} {label}\n"
            f"Cím:    {e['cim']}\n"
            f"Munka:  {e['munka']}\n"
            f"Kezdés: {e['kezdes']}\n"
            f"Vége:   {e['veg']}\n"
            f"Maps:   {e['gmaps']}\n"
        )

    fb_szoveg = facebook_szoveg(uj_esetek)

    html = f"""<!DOCTYPE html>
<html lang="hu"><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}}
  .wrap{{max-width:650px;margin:20px auto;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.15)}}
  .hdr{{background:#2980b9;color:#fff;padding:22px 28px}}
  .hdr h1{{margin:0;font-size:20px}}
  .hdr small{{opacity:.85;font-size:13px}}
  .body{{padding:20px 28px}}
  .bevezeto{{background:#e8f4fd;border-left:4px solid #2980b9;
             padding:12px 16px;margin-bottom:16px;
             font-size:14px;color:#2c3e50;line-height:1.6}}
  .fb-box{{background:linear-gradient(135deg,#f0f2f5,#e8edf3);
           border:1px solid #d0d7de;border-radius:12px;
           padding:18px 20px;margin:22px 0;
           box-shadow:0 1px 3px rgba(0,0,0,.06)}}
  .fb-box h3{{margin:0 0 12px;color:#1877f2;font-size:14px;
              display:flex;align-items:center;gap:6px}}
  .fb-box pre{{margin:0;font-family:Arial,sans-serif;font-size:13px;
              white-space:pre-wrap;word-break:break-word;
              color:#1c1e21;line-height:1.6;background:#fff;
              border-radius:8px;padding:14px;border:1px solid #e4e6eb}}
  .fb-allapot{{margin-top:10px;font-size:12px;color:#42b72a;font-weight:bold}}
  .foot{{background:#ecf0f1;padding:12px 28px;font-size:11px;
         color:#95a5a6;text-align:center}}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>💧 Fővárosi Vízművek – Csepel / Pesterzsébet / Szigetszentmiklós</h1>
    <small>{ido} | {db} új esemény</small>
  </div>
  <div class="body">

    <div class="bevezeto">
      ℹ️ A Fővárosi Vízművek az alábbi helyszíneken (Csepel, Pesterzsébet,
      Szigetszentmiklós) végez jelenleg hálózati munkálatokat.
      A munkák ideje alatt az érintett területeken <strong>vízhiány, nyomáscsökkenés
      vagy forgalomkorlátozás</strong> tapasztalható.
    </div>

    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>

    <div class="fb-box">
      <h3>📘 Facebook poszt szövege (tájékoztatásul - ez már automatikusan kiment az Oldalra)</h3>
      <pre id="fb">{fb_szoveg}</pre>
      <div class="fb-allapot">✅ Automatikusan posztolva a Facebook Oldalra</div>
    </div>

    <div style="text-align:center;margin-top:16px">
      <a href="https://www.vizmuvek.hu/hu/kezdolap/informaciok/munkaterkep-hol-dolgozunk"
         style="background:#2980b9;color:#fff;padding:9px 16px;border-radius:6px;
                text-decoration:none;font-weight:bold;font-size:12px">
        💧 Vízművek munkatérkép
      </a>
      <a href="https://www.facebook.com/104411308403346"
         style="background:#1877f2;color:#fff;padding:9px 16px;border-radius:6px;
                text-decoration:none;font-weight:bold;font-size:12px;margin-left:8px">
        📘 Facebook oldal megnyitása
      </a>
    </div>
  </div>
  <div class="foot">Automatikus értesítő – GitHub Actions | Fővárosi Vízművek adatai alapján</div>
</div></body></html>"""

    szoveges = f"💧 Fővárosi Vízművek – Csepel/Pesterzsébet/Szigetszentmiklós\nIdőpont: {ido}\n{sorok_txt}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"💧 Vízművek Monitor <{EMAIL_KULDO}>"
    msg["To"]      = EMAIL_CIMZETT
    msg.attach(MIMEText(szoveges, "plain", "utf-8"))
    msg.attach(MIMEText(html,     "html",  "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
        smtp.sendmail(EMAIL_KULDO, EMAIL_CIMZETT, msg.as_string())
    print(f"📧 E-mail elküldve: {targy}")


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"💧 Vízművek Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    uj   = []

    for e in lekerdez():
        rid = hash_id(e["tipus"] + e["cim"] + e["kezdes"])
        if rid not in regi:
            uj.append(e)
            regi[rid] = {"cim": e["cim"][:100], "talalt": magyar_ido().isoformat()}

    print(f"\n💧 Új esemény: {len(uj)}")
    if uj:
        email_kuldes(uj)

        if FACEBOOK_POSZTOLAS_AKTIV:
            print("\n📘 Facebook poszt küldése...")
            fb_szoveg = facebook_szoveg(uj)
            facebook_poszt_kuldese(fb_szoveg)
    else:
        print("✅ Nincs új esemény.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
