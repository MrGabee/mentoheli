"""
🚌 BKK INFO Monitor – Baleset miatt terelések
Adatforrás: m.bkkinfo.hu (scraping)
Futtatás: GitHub Actions (percenként, self-loop)
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


EMAIL_KULDO   = os.environ["EMAIL_KULDO"]
EMAIL_JELSZO  = os.environ["EMAIL_JELSZO"]
EMAIL_CIMZETT = os.environ["EMAIL_CIMZETT"]
EMAIL_CIMZETT_KERULET = os.environ.get("EMAIL_CIMZETT_KERULET", "")

# Figyelt vonalak – dél-pesti kerületek (IX., X., XIX., XVIII., XX., XXI., XXIII.)
# Ha az esemény címe ezzel a vonalszámmal kezdődik, külön e-mail is megy
FIGYELT_VONALAK = [
    # IX. kerület (Ferencváros)
    "1", "2", "2B", "3", "4", "6", "23", "24", "47", "48", "49", "51", "51A", "52",
    "M3", "M4", "15", "54", "55", "84E", "89E", "94E", "99", "119", "123", "123A",
    "166", "179", "181", "194", "194B", "212", "212A", "212B", "223E", "224", "224E",
    "254E", "255E", "281", "901", "909", "909A", "914", "914A", "918",
    # X. kerület (Kőbánya)
    "28", "28A", "37", "37A", "37B", "42", "50", "62", "62A", "M2", "9", "10", "32",
    "44", "45", "66", "66B", "66E", "67", "68", "85", "85E", "95", "97E", "98", "117",
    "130", "142E", "151", "161", "161A", "161E", "162", "168E", "169E", "176E",
    # XIX. kerület (Kispest)
    "36", "93", "93A", "132E", "136", "148", "182", "182A", "184", "193E", "198",
    "200E", "202E", "217", "217E", "268", "282E", "284E", "294E", "923", "946", "948",
    "950", "950A", "968", "984", "985", "994", "994B", "999",
    # XVIII. kerület (Pestszentlőrinc-Pestszentimre)
    "183", "236", "236A", "266", "983",
    # XX. kerület (Pesterzsébet)
    "35", "934", "966",
    # XXI. kerület (Csepel)
    "38", "38A", "71", "138", "152", "159", "238", "278", "938", "979", "979A", "H7",
    # XXIII. kerület (Soroksár)
    "135", "H6",
]

BKK_URL      = "https://m.bkkinfo.hu/"
BKK_BASE_URL = "https://m.bkkinfo.hu"
ALLAPOT_FAJL = "bkk_allapot.json"

# Szűrő kulcsszavak – a szó benne van a cím/leírásban
BALESET_KULCSSZAVAK = [
    # Baleset
    "baleset", "gázolás", "gazolas", "ütközés", "utkozés", "karambol",
    # Tűzoltó
    "tűzoltó", "tuzolto",
    # Mentő
    "mentő", "mento",
    # Hatósági zárás
    "hatósági", "hatosagi",
    # Terelés
    "terelve", "terelt", "terelés",
]

# Kizáró szavak – ha ezek szerepelnek a szövegben, NEM küldi el
KIZARO_KULCSSZAVAK = [
    "utas rosszul", "utasrosszul", "utas rosszullét", "utasrosszullét",
    "rosszullét", "rosszul lett", "rosszullette",
    "szabálytalan parkolás", "szabálytalan parkol", "szabálytalanul parkol",
    "parkolási", "parkolás miatt",
    "akadályozó jármű", "akadályozó autó",
    "közműjavítás", "közmű",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9",
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
#  🔍  SZŰRŐK
# ════════════════════════════════════════════
def baleset_e(szoveg):
    s = szoveg.lower()
    return any(k in s for k in BALESET_KULCSSZAVAK)

def kizaras_e(szoveg):
    """Ha kizáró szó szerepel a szövegben, NEM küldi el."""
    s = szoveg.lower()
    return any(k in s for k in KIZARO_KULCSSZAVAK)

def figyelt_vonal_e(cim, reszlet=""):
    """
    Csak pontosan a FIGYELT_VONALAK listában szereplő vonalszámra küld értesítést.
    '10' NEM egyezik '105'-tel vagy '210'-zel.
    Szóköz, vessző, pont, kötőjel, zárójel határolhatja csak.
    """
    import re
    teljes_szoveg = " " + (cim + " " + reszlet).upper() + " "
    for vonal in FIGYELT_VONALAK:
        pattern = r'(?<=[\s,.(/-])' + re.escape(vonal.upper()) + r'(?=[\s,.(/-])'
        if re.search(pattern, teljes_szoveg):
            return True
    return False


# ════════════════════════════════════════════
#  📡  BKK INFO LEKÉRDEZÉS
# ════════════════════════════════════════════
def lekerdez_esemeny_reszlet(url):
    """Egy esemény részletes oldalát tölti le."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")

        # Érvényesség
        ervenyes = ""
        erv_div = soup.find(string=lambda t: t and "Érvényes" in t)
        if erv_div:
            erv_parent = erv_div.find_parent()
            if erv_parent:
                ervenyes = erv_parent.get_text(separator=" ", strip=True)

        # Részletek szöveg
        reszlet = ""
        reszlet_div = soup.find(string=lambda t: t and "Részletek" in t)
        if reszlet_div:
            reszlet_parent = reszlet_div.find_parent()
            if reszlet_parent:
                # Következő testvér elemek
                next_sib = reszlet_parent.find_next_sibling()
                if next_sib:
                    reszlet = next_sib.get_text(separator=" ", strip=True)

        # Ha nincs külön részletek blokk, az egész oldal szövege
        if not reszlet:
            body = soup.find("body")
            if body:
                reszlet = body.get_text(separator=" ", strip=True)[:1000]

        return {"ervenyes": ervenyes, "reszlet": reszlet}

    except Exception as e:
        print(f"  ⚠️ Részlet hiba ({url}): {e}")
        return None

def lekerdez_bkk():
    """BKK INFO főoldal scraping + baleset szűrés."""
    try:
        print(f"🚌 BKK INFO lekérdezés: {BKK_URL}")
        r = requests.get(BKK_URL, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  ⚠️ HTTP {r.status_code}")
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        linkek = soup.find_all("a", href=True)

        esemenyek = []
        for link in linkek:
            href = link.get("href", "")
            if "/zavarok/" not in href:
                continue

            cim = link.get_text(strip=True)
            if not cim or len(cim) < 10:
                continue

            # Teljes URL
            if href.startswith("http"):
                full_url = href
            else:
                full_url = BKK_BASE_URL + href

            # Azonosító kinyerése
            esemeny_id = href.split("/zavarok/")[-1].strip("/")

            esemenyek.append({
                "id": esemeny_id,
                "cim": cim,
                "url": full_url
            })

        print(f"  📊 Összes esemény: {len(esemenyek)}")

        # Baleset szűrés – először a cím alapján
        balesetes = []
        for e in esemenyek:
            if baleset_e(e["cim"]):
                # Részletek letöltése
                reszlet = lekerdez_esemeny_reszlet(e["url"])
                if reszlet:
                    e.update(reszlet)
                else:
                    e["ervenyes"] = ""
                    e["reszlet"] = e["cim"]
                balesetes.append(e)

        # Ha a cím nem tartalmaz baleset szót,
        # de az esemény részlete igen → megnézzük
        for e in esemenyek:
            if e in balesetes:
                continue
            reszlet = lekerdez_esemeny_reszlet(e["url"])
            if reszlet and baleset_e(reszlet.get("reszlet", "")):
                e.update(reszlet)
                balesetes.append(e)
                print(f"  🚨 Baleset a részletben: {e['cim'][:60]}")

        print(f"  🚨 Balesetes esemény: {len(balesetes)}")
        return balesetes

    except Exception as ex:
        print(f"  ❌ Hiba: {ex}")
        import traceback
        traceback.print_exc()
        return []


# ════════════════════════════════════════════
#  📧  E-MAIL
# ════════════════════════════════════════════
def email_kuldes(uj_esetek, cimzett=None):
    cimzett = cimzett or EMAIL_CIMZETT
    ido   = magyar_ido().strftime("%Y.%m.%d %H:%M:%S")
    db    = len(uj_esetek)
    targy = f"🚨 BKK forgalmi esemény – {db} új | {ido}"

    sorok_html = ""
    sorok_txt  = ""

    for i, e in enumerate(uj_esetek, 1):
        cim      = e.get("cim", "—")
        ervenyes = e.get("ervenyes", "—")
        reszlet  = e.get("reszlet", "")[:500]
        url      = e.get("url", "")

        # Badge meghatározása a cím alapján
        cim_lower = cim.lower()
        if any(k in cim_lower for k in ["tűzoltó", "tűzeset", "tuzolto"]):
            badge = "🔥 TŰZOLTÓ – TERELÉS"
            szin  = "#e74c3c"
        elif any(k in cim_lower for k in ["mentő", "mentés", "mento"]):
            badge = "🚑 MENTŐ – TERELÉS"
            szin  = "#e67e22"
        elif any(k in cim_lower for k in ["hatósági", "hatóság", "rendőr", "hatosagi"]):
            badge = "👮 HATÓSÁGI ZÁRÁS"
            szin  = "#8e44ad"
        elif any(k in cim_lower for k in ["forgalmi", "lezárás", "útlezárás"]):
            badge = "🚧 FORGALMI AKADÁLY"
            szin  = "#f39c12"
        else:
            badge = "🚨 FORGALMI ESEMÉNY – TERELÉS"
            szin  = "#c0392b"

        sorok_html += f"""
        <tr style="border-bottom:2px solid #eee">
          <td style="padding:14px;vertical-align:top;color:#999;width:24px">{i}.</td>
          <td style="padding:14px">
            <span style="background:{szin};color:#fff;padding:5px 12px;
                         border-radius:4px;font-size:13px;font-weight:bold">
              {badge}
            </span>
            <div style="font-size:14px;font-weight:bold;margin:10px 0;color:#2c3e50">
              {cim}
            </div>
            {"<div style='font-size:12px;color:#888;margin-bottom:8px'>⏰ " + ervenyes + "</div>" if ervenyes else ""}
            {"<div style='font-size:13px;color:#555;margin-bottom:10px'>" + reszlet + "</div>" if reszlet else ""}
            <a href="{url}" style="background:#2980b9;color:#fff;padding:7px 14px;
                                    border-radius:4px;text-decoration:none;
                                    font-size:12px;font-weight:bold">
              🔗 BKK INFO oldal
            </a>
          </td>
        </tr>"""

        sorok_txt += (
            f"\n{'─'*45}\n"
            f"{i}. {badge}\n"
            f"{cim}\n"
            f"Érvényes: {ervenyes}\n"
            f"Link: {url}\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="hu"><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0}}
  .wrap{{max-width:650px;margin:20px auto;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.15)}}
  .hdr{{background:#c0392b;color:#fff;padding:22px 28px}}
  .hdr h1{{margin:0;font-size:20px}}
  .hdr small{{opacity:.85;font-size:13px}}
  .body{{padding:20px 28px}}
  .foot{{background:#ecf0f1;padding:12px 28px;font-size:11px;
         color:#95a5a6;text-align:center}}
</style>
</head><body><div class="wrap">
  <div class="hdr">
    <h1>🚨 BKK – Baleset miatti terelés</h1>
    <small>{ido} | {db} új esemény</small>
  </div>
  <div class="body">
    <table style="width:100%;border-collapse:collapse">{sorok_html}</table>
    <div style="text-align:center;margin-top:16px">
      <a href="https://m.bkkinfo.hu/"
         style="background:#c0392b;color:#fff;padding:9px 16px;border-radius:6px;
                text-decoration:none;font-weight:bold;font-size:12px">
        🚌 BKK INFO oldal
      </a>
    </div>
  </div>
  <div class="foot">Automatikus értesítő – GitHub Actions | BKK INFO adatai alapján</div>
</div></body></html>"""

    szoveges = f"🚨 BKK Baleset Terelés\nIdőpont: {ido}\n{sorok_txt}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = targy
    msg["From"]    = f"🚨 BKK Monitor <{EMAIL_KULDO}>"
    msg["To"]      = cimzett
    msg.attach(MIMEText(szoveges, "plain", "utf-8"))
    msg.attach(MIMEText(html,     "html",  "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_KULDO, EMAIL_JELSZO)
        smtp.sendmail(EMAIL_KULDO, cimzett, msg.as_string())
    print(f"📧 E-mail elküldve: {targy}")


# ════════════════════════════════════════════
#  🚀  FŐPROGRAM
# ════════════════════════════════════════════
def main():
    print(f"\n{'='*55}")
    print(f"🚌 BKK Baleset Monitor – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")
    print(f"{'='*55}")

    regi = betolt_allapot()
    uj   = []

    esemenyek = lekerdez_bkk()

    for e in esemenyek:
        rid = hash_id(e["id"] + e["cim"])
        if rid not in regi:
            # Kizáró szavak ellenőrzése
            szoveg = e.get("cim", "") + " " + e.get("reszlet", "")
            if kizaras_e(szoveg):
                print(f"  ⏭️ Kizárva: {e['cim'][:60]}")
                regi[rid] = {"cim": e["cim"][:100], "talalt": magyar_ido().isoformat()}
                continue
            uj.append(e)
            regi[rid] = {
                "cim": e["cim"][:100],
                "talalt": magyar_ido().isoformat()
            }

    print(f"\n🚨 Új balesetes esemény: {len(uj)}")
    if uj:
        email_kuldes(uj)

        # Plusz: dél-pesti kerületeket érintő vonalak külön címre is
        if EMAIL_CIMZETT_KERULET:
            kerulet_esetek = [e for e in uj if figyelt_vonal_e(e.get("cim", ""), e.get("reszlet", ""))]
            if kerulet_esetek:
                print(f"🚨 Ebből figyelt vonal: {len(kerulet_esetek)} → külön e-mail")
                email_kuldes(kerulet_esetek, cimzett=EMAIL_CIMZETT_KERULET)
    else:
        print("✅ Nincs új baleseti terelés.")

    ment_allapot(regi)
    print("💾 Állapot mentve. ✅ Kész.\n")


if __name__ == "__main__":
    main()
