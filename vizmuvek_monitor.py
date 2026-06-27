"""
💧 Fővárosi Vízművek Monitor – Csepel (XXI. kerület)
Adatforrás: vizmuvek.hu munkatérkép
Szűrés: XXI. kerület prefix
Értesítés: E-mail (EMAIL_CIMZETT_ARAM) + Facebook poszt (Mr.Gabee oldal)
"""

import os
import json
import hashlib
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT_ARAM"]
FB_PAGE_TOKEN = os.environ["FB_PAGE_TOKEN"]
FB_PAGE_ID    = os.environ["FB_PAGE_ID"]

VIZMUVEK_URL = "https://www.vizmuvek.hu/hu/kezdolap/informaciok/munkaterkep-hol-dolgozunk"
ALLAPOT_FAJL = "vizmuvek_allapot.json"

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
#  📍  CSEPEL SZŰRŐ
# ════════════════════════════════════════════
def csepel_e(cim):
    return cim.strip().startswith("XXI.")


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

            gmaps = f"https://www.google.com/maps?q={lat},{lon}&z=15"
            esemenyek.append({
                "tipus": tipus, "cim": cim, "munka": munka,
                "kezdes": kezdes, "veg": veg,
                "lat": lat, "lon": lon, "gmaps": gmaps,
            })
            print(f"  🎯 {cim}")

        print(f"  📊 Csepeli találat: {len(esemenyek)}")
        return esemenyek

    except Exception as ex:
        print(f"  ❌ {ex}")
        import traceback
        traceback.print_exc()
        return []


# ════════════════════════════════════════════
#  📘  FACEBOOK POSZT
# ════════════════════════════════════════════
def facebook_poszt(esetek):
    """Egy összesített Facebook posztot küld az összes új eseményről."""
    ido = datetime.now().strftime("%Y.%m.%d %H:%M")
    db  = len(esetek)

    sorok = []
    for e in esetek:
        emoji, label, _ = TIPUS_MAP.get(e["tipus"], ("💧", e["tipus"], ""))
        sor = (
            f"{emoji} {label}\n"
            f"📍 {e['cim']}\n"
            f"🔧 {e['munka'] or '—'}\n"
            f"⏰ {e['kezdes'] or '—'} → {e['veg'] or '—'}\n"
            f"🗺️ {e['gmaps']}"
        )
        sorok.append(sor)

    szoveg = (
        f"💧 Fővárosi Vízművek – Csepeli értesítő\n"
        f"🕐 {ido} | {db} új esemény\n\n"
        + "\n\n─────────────────\n\n".join(sorok)
        + "\n\n🔗 Vízművek munkatérkép:\n"
        f"https://www.vizmuvek.hu/hu/kezdolap/informaciok/munkaterkep-hol-dolgozunk"
    )

    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        r = requests.post(url, data={
            "message": szoveg,
            "access_token": FB_PAGE_TOKEN
        }, timeout=15)
        if r.status_code == 200:
            post_id = r.json().get("id", "?")
            print(f"📘 Facebook poszt elküldve! ID: {post_id}")
        else:
            print(f"⚠️ Facebook hiba: {r.status_code} – {r.text}")
    except Exception as ex:
        print(f"❌ Facebook poszt hiba: {ex}")


# ════════════════════════════════════════════
#  📧  E-MAIL
# ════════════════════════════════════════════
def email_kuldes(uj_esetek):
    ido   = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)
    targy = f"💧 Vízművek Csepel – {db} új esemény | {ido}"

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
              <tr><td style="color:#888;width:160px">🔧 Munka típusa:</td>
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

    # Facebook poszt szöveg összeállítása
    fb_sorok = []
    for e in uj_esetek:
        emoji, label, _ = TIPUS_MAP.get(e["tipus"], ("💧", e["tipus"], ""))
        sor = (
            f"{emoji} {label}\n"
            f"📍 {e['cim']}\n"
            f"🔧 {e['munka'] or '—'}\n"
            f"⏰ {e['kezdes'] or '—'} → {e['veg'] or '—'}\n"
            f"🗺️ {e['gmaps']}"
        )
        fb_sorok.append(sor)

    fb_szoveg = (
        f"💧 Fővárosi Vízművek – Csepeli értesítő\n"
        f"🕐 {ido} | {db} új esemény\n\n"
        + "\n\n─────────────────\n\n".join(fb_sorok)
        + "\n\n🔗 Vízművek munkatérkép:\n"
        f"https://www.vizmuvek.hu/hu/kezdolap/informaciok/munkaterkep-hol-dolgozunk"
    )

    import urllib.parse
    fb_share_url = f"https://www.facebook.com/dialog/share?app_id=10064353121037736&display=popup&quote={urllib.parse.quote(fb_szoveg)}&href=https://www.vizmuvek.hu"

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
  .fb-box{{background:#f0f2f5;border:2px dashed #1877f2;
           border-radius:8px;padding:16px;margin:20px 0}}
  .fb-box h3{{margin:0 0 10px;color:#1877f2;font-size:14px}}
  .fb-box pre{{margin:0;font-family:Arial,sans-serif;font-size:13px;
              white-space:pre-wrap;word-break:break-word;
              color:#1c1e21;line-height:1.6}}
  .foot{{background:#ecf0f1;padding:12px 28px;font-size:11px;
         color:#95a5a6;text-align:center}}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>💧 Fővárosi Vízművek – Csepeli értesítő</h1>
    <small>{ido} | {db} új esemény (XXI. kerület)</small>
  </div>
  <div class="body">

    <div class="bevezeto">
      ℹ️ A Fővárosi Vízművek az alábbi csepeli helyszíneken végez jelenleg hálózati munkálatokat.
      A munkák ideje alatt az érintett területeken <strong>vízhiány, nyomáscsökkenés
      vagy forgalomkorlátozás</strong> tapasztalható.
    </div>

    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>

    <div class="fb-box">
      <h3>📘 Facebook poszt szövege – jelöld ki és másold (Ctrl+A majd Ctrl+C):</h3>
      <pre id="fb">{fb_szoveg}</pre>
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

    szoveges = f"💧 Fővárosi Vízművek Csepel\nIdőpont: {ido}\n{sorok_txt}"

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
    print(f"💧 Vízművek Monitor – {datetime.now().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    uj   = []

    for e in lekerdez():
        rid = hash_id(e["tipus"] + e["cim"] + e["kezdes"])
        if rid not in regi:
            uj.append(e)
            regi[rid] = {"cim": e["cim"][:100], "talalt": datetime.now().isoformat()}

    print(f"\n💧 Új esemény: {len(uj)}")
    if uj:
        email_kuldes(uj)
        facebook_poszt(uj)
    else:
        print("✅ Nincs új esemény.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
