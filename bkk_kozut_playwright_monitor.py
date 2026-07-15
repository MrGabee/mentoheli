"""
🚧 BKK KÖZÚTI BALESET-FIGYELŐ (Playwright, valódi böngészővel)
Forrás: https://bkk.hu/bkk-info/#!t=kozut&e=3&d=today (baleset szűrővel előszűrve)

FONTOS: ez a script egy VALÓDI, headless Chrome böngészőt indít (Playwright),
ami kiállja a Cloudflare-védelmet, mert úgy viselkedik, mint egy igazi
felhasználó böngészője - nem hamisított kéréseket küld.

ELSŐ LÉPÉS: futtasd TESZT módban (lásd lent), hogy lássuk a nyers
kiolvasott szöveget - abból pontosítjuk a végleges feldolgozó logikát.
"""

import os
import json
import hashlib
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from playwright.sync_api import sync_playwright

BKK_KOZUT_URL = "https://bkk.hu/bkk-info/#!t=kozut&e=3&d=today"
ALLAPOT_FAJL = "bkk_kozut_allapot.json"

EMAIL_KULDO   = os.environ.get("EMAIL_KULDO", "")
EMAIL_JELSZO  = os.environ.get("EMAIL_JELSZO", "")
EMAIL_CIMZETT = os.environ.get("EMAIL_CIMZETT_BKK", "")

TESZT_MOD = os.environ.get("TESZT_MOD", "0") == "1"


def oldal_szoveg_lekerese():
    """Elindít egy valódi Chrome-ot, betölti a baleset-szűrt BKK közúti oldalt,
    és visszaadja a látható szöveget."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1400, "height": 1000},
        )
        page = context.new_page()

        print(f"🌐 Betöltés: {BKK_KOZUT_URL}")
        page.goto(BKK_KOZUT_URL, wait_until="networkidle", timeout=30000)

        # Várunk, hogy a JS tényleg lefusson és a lista betöltődjön
        page.wait_for_timeout(3000)

        # A hash-alapú URL (#!t=kozut&e=3) önmagában is a helyes fület és
        # szűrést tölti be - nincs szükség külön kattintásra.

        teljes_szoveg = page.inner_text("body")

        browser.close()
        return teljes_szoveg


def teszt_futtatas():
    """Csak kiírja a nyers szöveget a logba, e-mail küldés nélkül -
    ebből pontosítjuk a feldolgozó logikát."""
    szoveg = oldal_szoveg_lekerese()
    print("═" * 60)
    print("NYERS OLDAL SZÖVEG (első 5000 karakter):")
    print("═" * 60)
    print(szoveg[:5000])
    print("═" * 60)
    print(f"Teljes hossz: {len(szoveg)} karakter")


def esemenyek_kinyerese(szoveg):
    """
    ELŐZETES, MÉG FINOMÍTANDÓ parser - a teszt-futtatás kimenete alapján
    kell pontosítani. Egyelőre sor-alapú heurisztikával dolgozik: azokat
    a sorblokkokat keresi, amik "Baleset" szót tartalmaznak, és utánuk
    néhány sort dátum/idő infóként vesz.
    """
    sorok = [s.strip() for s in szoveg.split("\n") if s.strip()]
    esemenyek = []

    for i, sor in enumerate(sorok):
        if "baleset" in sor.lower() and len(sor) > 10:
            # A cím maga a sor; a következő 1-3 sor gyakran idő/hely infó
            kontextus = sorok[i:i + 4]
            azonosito = hashlib.md5("|".join(kontextus).encode("utf-8")).hexdigest()[:12]
            esemenyek.append({
                "id": azonosito,
                "cim": sor,
                "kontextus": kontextus,
            })

    return esemenyek


def allapot_betoltes():
    if os.path.exists(ALLAPOT_FAJL):
        try:
            with open(ALLAPOT_FAJL, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def allapot_mentes(allapot):
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=2)


def email_kuldes(uj_esemenyek):
    if not (EMAIL_KULDO and EMAIL_JELSZO and EMAIL_CIMZETT):
        print("⚠️ Hiányzó e-mail környezeti változók - kihagyva.")
        return

    ido = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    targy = f"🚧 BKK közúti baleset - {len(uj_esemenyek)} új esemény | {ido}"

    sorok = [f"BKK közúti baleset-figyelő - {ido}", ""]
    for e in uj_esemenyek:
        sorok.append(f"• {e['cim']}")
        for k in e["kontextus"][1:]:
            sorok.append(f"   {k}")
        sorok.append("")

    szoveg = "\n".join(sorok)

    try:
        msg = MIMEText(szoveg, "plain", "utf-8")
        msg["Subject"] = targy
        msg["From"] = EMAIL_KULDO
        msg["To"] = EMAIL_CIMZETT

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_KULDO, EMAIL_JELSZO)
            server.sendmail(EMAIL_KULDO, [EMAIL_CIMZETT], msg.as_string())
        print(f"📧 E-mail elküldve: {len(uj_esemenyek)} új esemény")
    except Exception as ex:
        print(f"❌ E-mail hiba: {ex}")


def main():
    if TESZT_MOD:
        teszt_futtatas()
        return

    szoveg = oldal_szoveg_lekerese()
    esemenyek = esemenyek_kinyerese(szoveg)
    print(f"📊 Talált baleset-bejegyzések: {len(esemenyek)}")

    allapot = allapot_betoltes()
    uj_esemenyek = []

    for e in esemenyek:
        if e["id"] not in allapot:
            uj_esemenyek.append(e)
            allapot[e["id"]] = {"cim": e["cim"], "eloszor_latva": datetime.now().isoformat()}

    if uj_esemenyek:
        print(f"🆕 Új esemény: {len(uj_esemenyek)}")
        email_kuldes(uj_esemenyek)
    else:
        print("✅ Nincs új esemény.")

    allapot_mentes(allapot)


if __name__ == "__main__":
    main()
