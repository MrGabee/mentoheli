"""
📊 Make.com keret-figyelő
Naponta megnézi mindkét Make-fiók havi műveleti keretét (ingyenes csomag:
1000 művelet/hó), és e-mailt küld, ha fogy:
  - ha a felhasznált rész eléri a FIGYELMEZTETES_SZAZALEK-ot, vagy
  - ha az eddigi ütem alapján a keret a hónap vége előtt elfogyna.
Fiókok (GitHub titkok):
  - MAKE_API_TOKEN  – a régi fiók (rendőrség, Csili, áramszünet stb.)
  - MAKE2_API_TOKEN – az új fiók (színes posztok)
"""

import os
import smtplib
import requests
from datetime import datetime, timezone
from email.mime.text import MIMEText

FIOKOK = [("Régi fiók (rendőrség, Csili, áramszünet…)", "MAKE_API_TOKEN"),
          ("Új fiók (színes posztok)", "MAKE2_API_TOKEN")]
ZONAK = ["eu1", "eu2", "us1", "us2"]
FIGYELMEZTETES_SZAZALEK = 80


def org_adatok(token):
    """Az első szervezet keretadatai, vagy None."""
    h = {"Authorization": f"Token {token}"}
    for z in ZONAK:
        try:
            r = requests.get(f"https://{z}.make.com/api/v2/organizations", headers=h, timeout=30)
        except Exception as ex:
            print(f"  ❌ {z}: {ex}")
            continue
        if r.status_code != 200:
            continue
        for o in r.json().get("organizations", []):
            r2 = requests.get(f"https://{o['zone']}/api/v2/organizations/{o['id']}", headers=h, timeout=30)
            if r2.status_code == 200:
                return r2.json()["organization"]
    return None


def _ido(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def ertekel(nev, o, most):
    """(szöveg, riasztás-e)"""
    keret = int(o.get("license", {}).get("operations") or 1000)
    hasznalt = int(o.get("operations") or 0)
    kezd, vege = _ido(o["lastReset"]), _ido(o["nextReset"])
    eltelt = max((most - kezd).total_seconds() / 86400, 0.5)
    hossz = (vege - kezd).total_seconds() / 86400
    becsult = round(hasznalt / eltelt * hossz)
    szazalek = round(hasznalt * 100 / keret)
    szoveg = (f"{nev}: {hasznalt} / {keret} művelet ({szazalek}%), a hó végére várhatóan kb. {becsult}. "
              f"Újraindul: {vege.strftime('%Y.%m.%d.')}")
    # Az első napokban a becslés még nagyon bizonytalan, ezért csak 3 nap után számít
    return szoveg, szazalek >= FIGYELMEZTETES_SZAZALEK or (eltelt >= 3 and becsult > keret)


def email(tema, sorok):
    kuldo, jelszo, cimzett = (os.environ.get(k, "") for k in ("EMAIL_KULDO", "EMAIL_JELSZO", "EMAIL_CIMZETT"))
    if not (kuldo and jelszo and cimzett):
        print("  ⚠️ Nincs e-mail beállítás, nem küldök levelet.")
        return
    msg = MIMEText("<br>".join(sorok), "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = tema, kuldo, cimzett
    with smtplib.SMTP_SSL(os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", 465)), timeout=20) as s:
        s.login(kuldo, jelszo)
        s.sendmail(kuldo, [cimzett], msg.as_string())
    print("  📧 Figyelmeztető e-mail elküldve.")


def main():
    most = datetime.now(timezone.utc)
    print(f"📊 Make keret-figyelő – {most.strftime('%Y.%m.%d %H:%M')} UTC")
    riasztasok = []
    for nev, kulcs in FIOKOK:
        token = os.environ.get(kulcs, "")
        if not token:
            print(f"  ⚠️ {nev}: nincs {kulcs} titok, kihagyva.")
            continue
        o = org_adatok(token)
        if o is None:
            print(f"  ❌ {nev}: nem sikerült lekérdezni.")
            riasztasok.append(f"❌ {nev}: a keretet nem sikerült lekérdezni (lejárt vagy hibás token?).")
            continue
        szoveg, riaszt = ertekel(nev, o, most)
        print(("  ⚠️ " if riaszt else "  ✅ ") + szoveg)
        if riaszt:
            riasztasok.append("⚠️ " + szoveg)
    if riasztasok:
        email("⚠️ Make.com: fogy a posztolási keret",
              riasztasok + ["", "Ha a keret elfogy, a Make a hónap végéig nem posztol tovább."])


if __name__ == "__main__":
    main()
