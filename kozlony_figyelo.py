"""
📰 Magyar Közlöny figyelő – a Dél-Pesti Tankerületi Központ új igazgatója

A magyarkozlony.hu "Legfrissebb közlönyök" listájának minden új számát
(Magyar Közlöny, Hivatalos Értesítő) letölti, és a PDF szövegében keresi a
Dél-Pesti Tankerületi Központ igazgatójának kinevezését.

Ha megvan a név:
  - éjjel (20:45 és 06:00 között) talált hírt reggel 07:40-re,
  - nappal talált hírt aznap 21:05-re, az esti búcsúzó poszt elé
időzíti (a posztot a szines_posztok.py teszi ki a poszt_szoveg() alapján),
és e-mailben is szól a kivonattal. Utána nem figyel tovább.

Állapot: kozlony_allapot.json
"""

import io
import json
import os
import re
import smtplib
import sys
import urllib.request
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from html import unescape
from zoneinfo import ZoneInfo

ALLAPOT_FAJL = "kozlony_allapot.json"
FOOLDAL = "https://magyarkozlony.hu/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
TZ = ZoneInfo("Europe/Budapest")

REGGELI_IDO = "07:40"
ESTI_IDO = "21:05"
ESTI_HATAR = (20, 45)   # ez után talált hír már másnap reggel megy
REGGEL_KEZD = 6         # ez előtt talált hír aznap reggel megy

TANKERULET = re.compile(r"D\s*é\s*l\s*-\s*[Pp]\s*e\s*s\s*t\s*i\s+Tankerületi\s+Központ", re.S)
NAGY = "A-ZÁÉÍÓÖŐÚÜŰ"
KIS = "a-záéíóöőúüű"
# 2–3 tagú név tárgyesetben (pl. "Dr. Kovács Pétert", "Nagy-Szabó Annát")
NEV_TARGYESET = re.compile(
    rf"((?:[Dd]r\.\s+)?[{NAGY}][{KIS}]+(?:-[{NAGY}][{KIS}]+)?(?:\s+[{NAGY}][{KIS}]+(?:-[{NAGY}][{KIS}]+)?){{1,2}}t)\b"
)
NEM_NEV = {"Központ", "Tankerületi", "Magyar", "Közlöny", "Hivatalos", "Értesítő", "Pesti", "Dél",
           "Oktatási", "Hivatal", "Belügyminisztérium", "Kormány", "Miniszter", "Budapest"}


def ido():
    return datetime.now(TZ)


def letolt(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def betolt():
    try:
        with open(ALLAPOT_FAJL, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"latott": [], "talalat": None}


def ment(a):
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False, indent=2)


def lapok():
    """[(azonosító, lap neve, megjelenés napja, pdf-link)] a nyitóoldal összes PDF-jéről."""
    h = letolt(FOOLDAL).decode("utf-8", "ignore")
    ki, volt = [], set()
    for m in re.finditer(r'href="([^"]+/dokumentumok/([0-9a-f]{20,})/letoltes)"', h):
        azon = m.group(2)
        if azon in volt:
            continue
        volt.add(azon)
        elotte = h[max(0, m.start() - 2500): m.start()]
        utana = h[m.end(): m.end() + 600]
        nevek = re.findall(r'itemprop="name"\s*>([^<]+)<', elotte + utana)
        nevek = [n for n in nevek if "Kiadó" not in n]
        nap = re.findall(r'itemprop="datePublished" content="([^"]+)"', elotte + utana)
        ki.append((azon, unescape(nevek[-1] if nevek else "Magyar Közlöny").strip(), nap[-1] if nap else "", m.group(1)))
    return ki


def pdf_szoveg(adat):
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(adat))
    t = "\n".join((p.extract_text() or "") for p in r.pages)
    t = re.sub(r"-\s*\n\s*(?=[a-záéíóöőúüű])", "", t)   # sorvégi elválasztás
    return re.sub(r"\s+", " ", t)


def alanyeset(nev):
    """Tárgyesetből alanyeset: Pétert→Péter, Annát→Anna, Bencét→Bence, Juditot→Judit, Erzsébetet→Erzsébet."""
    if nev.endswith("át"):
        return nev[:-2] + "a"
    if nev.endswith("ét"):
        return nev[:-2] + "e"
    if re.search(r"[bcdfghjklmnpqrstvwxyzß](ot|et|öt)$", nev):
        return nev[:-2]
    return nev[:-1]


def keres(szoveg):
    """(név, hatály, kivonat) vagy None. A név lehet üres, ha a mondat nem egyértelmű."""
    for m in TANKERULET.finditer(szoveg):
        ablak = szoveg[max(0, m.start() - 500): m.end() + 500]
        if not re.search(r"igazgat", ablak, re.I) or not re.search(r"kinevez", ablak, re.I):
            continue
        kivonat = szoveg[max(0, m.start() - 300): m.end() + 300].strip()
        mondat_kezd = max(szoveg.rfind(".", 0, max(0, m.start() - 250)), 0)
        mondat = szoveg[mondat_kezd: m.end() + 350]
        nevek = []
        tk_pozicio = mondat.find(m.group(0))
        for n in NEV_TARGYESET.finditer(mondat):
            szavak = n.group(1).replace("Dr. ", "").replace("dr. ", "").split()
            if any(s.rstrip("t") in NEM_NEV or s in NEM_NEV for s in szavak):
                continue
            nevek.append((n.start(), n.group(1)))
        hataly = re.search(r"(\d{4}\.\s*[a-záéíóöőúüű]+\s*\d{1,2}\.?)\s*(?:-?(?:jei|ai|ei|i|jétől|ától|étől|től|tól))?\s*hatállyal", mondat)
        nev = ""
        # Több név esetén (pl. felmentés + kinevezés egy mondatban) a tankerület előtti utolsó az új vezető
        elotte = [n for poz, n in nevek if poz < tk_pozicio]
        jelolt = elotte[-1] if elotte else (nevek[0][1] if len({n for _, n in nevek}) == 1 else "")
        if jelolt:
            reszek = jelolt.split()
            reszek[-1] = alanyeset(reszek[-1])
            nev = " ".join(reszek)
        return nev, (hataly.group(1) if hataly else ""), kivonat
    return None


def idosav(most):
    """Melyik napon, melyik sávban menjen ki."""
    if most.hour < REGGEL_KEZD:
        return most.date().isoformat(), "reggel"
    if (most.hour, most.minute) >= ESTI_HATAR:
        return (most.date() + timedelta(days=1)).isoformat(), "reggel"
    return most.date().isoformat(), "este"


def email(targy, szoveg):
    try:
        kuldo, jelszo, cimzett = os.environ["EMAIL_KULDO"], os.environ["EMAIL_JELSZO"], os.environ["EMAIL_CIMZETT"]
    except KeyError:
        print("ℹ️ Nincs e-mail beállítás, levél kihagyva.")
        return
    msg = MIMEText(szoveg, "plain", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = targy, f"Közlöny figyelő <{kuldo}>", cimzett
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(kuldo, jelszo)
        s.sendmail(kuldo, cimzett, msg.as_string())
    print("📧 E-mail elküldve:", targy)


def poszt_szoveg(nap, sav):
    """A szines_posztok.py hívja 07:40-kor ('reggel') és 21:05-kor ('este')."""
    t = betolt().get("talalat") or {}
    if not t.get("nev") or t.get("poszt_nap") != nap.isoformat() or t.get("sav") != sav:
        return ""
    hataly = f" (hatályos: {t['hataly'].rstrip('.')}.)" if t.get("hataly") else ""
    return (
        "🏫 ÚJ VEZETŐ A DÉL-PESTI TANKERÜLET ÉLÉN\n\n"
        f"A hivatalos lapban ({t['lap']}) megjelent: a Dél-Pesti Tankerületi Központ új igazgatója {t['nev']} lett{hataly}.\n\n"
        "A tankerülethez tartoznak a csepeli, a pesterzsébeti és a soroksári állami iskolák is, "
        "így a döntés sok családot és pedagógust érint a környékünkön.\n\n"
        "Az új vezetőnek jó munkát kívánok! Ti mit vártok a tankerület új vezetésétől? Írjátok meg kommentben! 👇\n\n"
        "#Csepel #Pesterzsébet #Soroksár #tankerület #oktatás"
    )


def main():
    a = betolt()
    if a.get("talalat", {}) and a["talalat"].get("nev"):
        print(f"✅ Már megvan: {a['talalat']['nev']} – nem figyelek tovább.")
        return
    latott = set(a.get("latott", []))
    for azon, nev, nap, link in lapok():
        if azon in latott:
            continue
        print(f"📄 {nev} ({nap})")
        try:
            szoveg = pdf_szoveg(letolt(link, timeout=120))
        except Exception as e:
            print(f"⚠️ Nem sikerült feldolgozni: {e}")
            continue
        print(f"   {len(szoveg)} karakter szöveg")
        latott.add(azon)
        a["latott"] = sorted(latott)
        ment(a)
        lelet = keres(szoveg)
        if not lelet:
            continue
        tnev, hataly, kivonat = lelet
        most = ido()
        poszt_nap, sav = idosav(most)
        a["talalat"] = {"nev": tnev, "hataly": hataly, "lap": nev, "link": link, "kivonat": kivonat[:1200],
                        "talalt": most.isoformat(timespec="minutes"), "poszt_nap": poszt_nap, "sav": sav}
        ment(a)
        mikor = f"{poszt_nap} {REGGELI_IDO if sav == 'reggel' else ESTI_IDO}"
        if tnev:
            print(f"🎯 Megvan: {tnev} ({nev}) – poszt: {mikor}")
            email(f"Dél-Pesti Tankerület: új igazgató – {tnev}",
                  f"A {nev} szerint a Dél-Pesti Tankerületi Központ új igazgatója: {tnev}\n"
                  f"Hatály: {hataly or '—'}\nA poszt időpontja: {mikor}\n\nKivonat:\n{kivonat}\n\n{link}")
        else:
            print(f"❓ Találat név nélkül ({nev}) – nem posztolok, e-mailt küldök.")
            email("Dél-Pesti Tankerület: kinevezés a Közlönyben, a nevet nem tudtam kiolvasni",
                  f"{nev}\n\nKivonat:\n{kivonat}\n\n{link}\n\nPoszt nem lett időzítve.")
        return
    print("ℹ️ Még nincs kinevezés a friss számokban.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "proba":
        print(keres(re.sub(r"\s+", " ", sys.stdin.read())))
    else:
        main()
