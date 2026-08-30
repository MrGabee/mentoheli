#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SZÁMLA FIGYELŐ
==================================================================
IMAP-on keresztül figyel egy dedikált email-postafiókot (vagy egy
meglévő postafiók egy külön mappáját/címkéjét), és a Vízművek, MVM és
Díjnet leveleit dolgozza fel.

FONTOS - TARTALOM-ALAPÚ FELISMERÉS (nem tárgy-sablon)
------------------------------------------------------
A korábbi verzió szolgáltatónként fix, kézzel írt tárgy-mintákkal
("uj_szamla_minta", "fizetve_minta") döntötte el, milyen levél
érkezett - ez törékeny volt, mert minden új tárgysor-variáció (pl.
"Diktálást visszaigazoló e-mail", "Bekötési mérő cseréje") vagy nem
lett felismerve, vagy tévesen lett besorolva.

Ehelyett most a program a levél VALÓDI TARTALMÁT (tárgy + törzs +
szükség esetén a csatolt PDF szövege) nézi meg, és általános,
szolgáltatótól független MINTÁK alapján dönti el, milyen FAJTA
dokumentumról van szó:

    fizetve              - fizetés-visszaigazolás  ("sikeres", "jóváírva", ...)
    fizetesi_emlekezteto - emlékeztető egy MEGLÉVŐ, még fizetetlen számláról
                            (ez szándékosan NEM hoz létre új számla-tételt)
    meroallas             - mérőállással/leolvasással/diktálással/mérőcserével
                            kapcsolatos értesítés
    uj_szamla             - új számla / díjbekérő
    ismeretlen             - a feladó a figyelt szolgáltatók egyike, de a
                            tartalom egyik fenti mintára sem illik rá

A feladó email-domainje csak azt dönti el, MELYIK szolgáltatóról van
szó (hogy legyen egy megjeleníthető név) - a szűrés innentől nem
"vállalkozás nélkül" tárgy-alapú, hanem tartalom-alapú.

Az "ismeretlen" eset NEM lesz csendben eldobva: bekerül az állapotba
(rövid szöveg-részlettel) és - ha be van kapcsolva - egy figyelmeztető
emailt is küld, hogy a valódi tapasztalat alapján finomítani lehessen a
mintákat. Ugyanez a szemlélet, mint amit egy korábbi, hasonló célú
(TV2-s teljesítési igazolás feldolgozó) programban is használtunk: soha
ne dobjunk el csendben fel nem ismert tartalmat, inkább jelöljük meg és
jelezzük.

MŰKÖDÉS
--------
1. Új, "uj_szamla" típusú email esetén: azonnal küld egy értesítő
   emailt, csatolva a PDF-számlát (ha volt csatolva) és egy HTML-es
   összefoglalóval (szolgáltató, összeg, határidő).
2. Új, "meroallas" típusú email esetén: elmenti egy külön, mérőállás-
   naplóba (nem keveredik a számlákkal), és - ha be van kapcsolva - egy
   rövid értesítőt küld.
3. Naponta ELLENŐRZI, hogy van-e olyan még fizetetlen számla, aminek a
   határideje SZAMLA_EMLEKEZTETO_NAPOK_ELOTTE napon belül lejár (vagy
   már le is járt) - ha igen, egy ÖSSZESÍTŐ emailt küld az ÖSSZES
   fizetetlen számláról, kimutatással, végösszeggel, és - amennyire
   lehetséges - újra csatolva az érintett PDF-eket (ezeket ilyenkor a
   script friss lekérdezéssel, közvetlenül az IMAP-postafiókból tölti
   vissza, nem egy korábban elmentett másolatból).
4. "fizetve" típusú email esetén a hozzá tartozó (legjobb egyezés
   szerinti) számlát fizetettre állítja.

ADATVÉDELEM - EZ FONTOS
------------------------
Ez a repó GitHub Pages-en fut, ami NYILVÁNOS URL - bárki eléri, aki
ismeri a linket. Emiatt:

  - A számla- és mérőállás-adatokat egy jelszóval AES-GCM-mel
    TITKOSÍTOTT fájlba mentjük (szamlak/szamla_allapot.enc.json).
    Titkosítás nélkül BÁRKI elolvashatná a lakcímedhez köthető
    adataidat - ez nem kozmetikai "jelszó-képernyő", hanem valódi
    titkosítás: a fájl tartalma értelmezhetetlen bájtkupac a jelszó
    (SZAMLA_TITKOSITAS_JELSZO titok) ismerete nélkül.
  - A PDF-számlák SOHA nem kerülnek be a git-repóba, és semmilyen
    formában nem kerülnek tartós tárolásra. Egy adott futás során
    csak átmenetileg, a memóriában léteznek, amíg az emailhez csatolva
    kimennek - utána a futtató gép (GitHub Actions runner) megszűnik,
    semmi nem marad utána. A határidő-előtti összesítőhöz a script
    live, friss IMAP-lekérdezéssel tölti vissza az eredeti leveleket a
    PDF-csatolmányért - nem egy korábban elmentett másolatból.
  - A dashboard oldal (szamlak.html) is ugyanezt a titkosított fájlt
    olvassa be, és a böngészőben, a Web Crypto API-val fejti vissza -
    a jelszót te írod be minden megnyitáskor, sehol nincs elmentve.

Szükséges GitHub Secretek:
  SZAMLA_IMAP_HOST        (opcionális, alapértelmezett: imap.gmail.com)
  SZAMLA_IMAP_USER        a figyelt postafiók email-címe
  SZAMLA_IMAP_JELSZO      Gmail esetén App Password (NEM a valódi jelszavad)
  SZAMLA_IMAP_MAPPA       (opcionális, alapértelmezett: INBOX)
  EMAIL_KULDO_SZAMLA      (opcionális, ha nincs, az IMAP-fiók küld SMTP-n is)
  EMAIL_JELSZO_SZAMLA     (opcionális, ha nincs, az IMAP jelszót használja)
  EMAIL_CIMZETT_SZAMLA    ide mennek az értesítők
  SZAMLA_TITKOSITAS_JELSZO  a titkosításhoz használt jelszó (Te találod ki -
                            ugyanezt kell majd beírnod a dashboard oldalon is)
"""

import os
import re
import io
import json
import base64
import hashlib
import imaplib
import smtplib
import email as email_lib
from email.header import decode_header, make_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, timezone

# ────────────────────────────────────────────
#  🕐  MAGYAR IDŐZÓNA
# ────────────────────────────────────────────
MAGYAR_TZ = timezone(timedelta(hours=2))


def magyar_ido():
    return datetime.now(MAGYAR_TZ)


def magyar_ma():
    return magyar_ido().date()


# ────────────────────────────────────────────
#  ⚙️  BEÁLLÍTÁSOK
# ────────────────────────────────────────────
# FONTOS: itt szándékosan "os.environ.get(NEV) or alapérték" mintát
# használunk, NEM "os.environ.get(NEV, alapérték)"-et. A GitHub Actions
# workflow ugyanis egy nem létező secretet is behelyettesít - üres
# szöveggel, nem hagyja ki a környezeti változót. A sima .get(NEV, alap)
# csak akkor adná vissza az alapértéket, ha a változó EGYÁLTALÁN NINCS
# beállítva - üresen beállított változónál nem, és pont ez okozott
# korábban "Connection refused" hibát (üres hostname -> a script a
# futtatógépet magát próbálta elérni). Az "or" forma mindkét esetben
# (hiányzó VAGY üres) helyesen az alapértékre esik vissza.
IMAP_HOST = os.environ.get("SZAMLA_IMAP_HOST") or "imap.gmail.com"
IMAP_PORT = int(os.environ.get("SZAMLA_IMAP_PORT") or "993")
IMAP_USER = os.environ.get("SZAMLA_IMAP_USER", "")
IMAP_JELSZO = os.environ.get("SZAMLA_IMAP_JELSZO", "")
IMAP_MAPPA = os.environ.get("SZAMLA_IMAP_MAPPA") or "INBOX"

SMTP_HOST = os.environ.get("SMTP_HOST") or "smtp.gmail.com"
SMTP_PORT = int(os.environ.get("SMTP_PORT") or "465")
EMAIL_KULDO = os.environ.get("EMAIL_KULDO_SZAMLA") or IMAP_USER
EMAIL_JELSZO_KULDES = os.environ.get("EMAIL_JELSZO_SZAMLA") or IMAP_JELSZO
EMAIL_CIMZETT = os.environ.get("EMAIL_CIMZETT_SZAMLA", "")

TITKOSITAS_JELSZO = os.environ.get("SZAMLA_TITKOSITAS_JELSZO", "")

# ⬇️⬇️⬇️ ITT ÁLLÍTSD BE, HÁNY NAPPAL A HATÁRIDŐ ELŐTT MENJEN AZ ÖSSZESÍTŐ ⬇️⬇️⬇️
SZAMLA_EMLEKEZTETO_NAPOK_ELOTTE = 5  # <-- írd át a saját igényed szerint

# Kapcsolók - vedd ki/tedd be az igényed szerint, ha valamelyik
# értesítés-típus túl sok/kevés emailt eredményezne.
MEROALLAS_ERTESITES_EMAIL = True   # küldjön-e emailt új mérőállás-eseménynél
ISMERETLEN_ERTESITES_EMAIL = True  # küldjön-e emailt fel nem ismert levélnél

ALLAPOT_FAJL = "szamlak/szamla_allapot.enc.json"  # TITKOSÍTVA, ez kerül git-be

# ── Szolgáltatók - csak a feladó-domain -> megjelenítendő név társítás ──
# A milyen FAJTA levél érkezett kérdést innentől NEM ez dönti el (ld. a
# TARTALOM-ALAPÚ FELISMERÉS részt a fájl elején), csak azt, hogy melyik
# szolgáltatóhoz tartozik egy már megismert levél.
SZOLGALTATOK = {
    "vizmuvek": {
        "nev": "Fővárosi Vízművek",
        "feladok": ["vizmuvek.hu", "fovarosivizmuvek.hu"],
    },
    "mvm": {
        "nev": "MVM",
        "feladok": ["mvmnext.hu", "mvm.hu", "mvmenergia.hu"],
    },
    "dijnet": {
        "nev": "Díjnet",
        "feladok": ["dijnet.hu"],
    },
}


def szolgaltato_azonositasa(feladó_cim: str):
    """A feladó email-címe alapján visszaadja a szolgáltató kulcsát, vagy
    None-t, ha a feladó nem tartozik a figyelt szolgáltatók egyikéhez sem
    (ilyenkor a levéllel egyáltalán nem foglalkozunk - ez a szűrés adja
    meg, hogy csak a dedikált postafiókba érkező, releváns leveleket
    dolgozzuk fel)."""
    for kulcs, cfg in SZOLGALTATOK.items():
        if any(domain in feladó_cim for domain in cfg["feladok"]):
            return kulcs
    return None


# ════════════════════════════════════════════
#  🔎  TARTALOM-ALAPÚ FELISMERÉS - általános minták
# ════════════════════════════════════════════
# Ezek a minták szándékosan NEM szolgáltatónkéntiek - a levél/PDF valódi
# szövegében keresnek jelentést hordozó kulcsszavakat, ahelyett hogy egy
# adott szolgáltató egy adott tárgysor-variációjára támaszkodnának.

# 1) Fizetés-visszaigazolás - ez a legszigorúbb minta (csak konkrét
#    "sikeres/beérkezett/jóváírva/teljesült/kiegyenlítve" jellegű
#    megfogalmazásra illeszkedik), hogy egy sima "fizetés" szó ne
#    generáljon téves találatot.
FIZETVE_MINTA = re.compile(
    r"fizetés\D{0,20}(sikeres|beérkezett|jóváírva|teljesült|megtörtént)|"
    r"befizetés\D{0,20}(sikeres|beérkezett|visszaigazol)|"
    r"köszönjük.{0,20}fizet|"
    r"számla.{0,20}kiegyenlít|kiegyenlít.{0,20}számla",
    re.IGNORECASE,
)

# 2) Emlékeztető egy MEGLÉVŐ, még fizetetlen számláról - ezt szándékosan
#    a fizetve-ellenőrzés UTÁN, de minden más előtt nézzük, mert egy
#    emlékeztető levél tárgya/szövege gyakran tartalmazza a "számla" vagy
#    akár a "fizetés" szót is, de ettől még nem szabad új tételt
#    létrehozni belőle (duplikációt okozna).
EMLEKEZTETO_MINTA = re.compile(r"emlékeztet", re.IGNORECASE)

# 3) Mérőállással/leolvasással/diktálással/mérőcserével kapcsolatos
#    értesítés.
MEROALLAS_MINTA = re.compile(
    r"mérőállás|óraállás|mérő\s*csere|mérőcsere|leolvasás|diktál|"
    r"bekötési\s*mérő|plomba",
    re.IGNORECASE,
)

# 4) Új számla / díjbekérő.
SZAMLA_MINTA = re.compile(
    r"számla|díjbekérő|fizetendő",
    re.IGNORECASE,
)

# Összeg-minta: "12 345 Ft", "12.345 Ft", "12345 HUF", ezres-tagolással is
OSSZEG_MINTA = re.compile(
    r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?)\s*(Ft|HUF)", re.IGNORECASE
)
# Dátum-minta: 2026.09.15, 2026-09-15, 2026. 09. 15.
HATARIDO_MINTA = re.compile(
    r"(?:fizetési\s*határidő|határidő|esedékesség)\D{0,15}"
    r"(\d{4})[.\-]\s*(\d{1,2})[.\-]\s*(\d{1,2})",
    re.IGNORECASE,
)
# Mérőállás-érték minta: "mérőállás: 1234", "óraállás 1234 m3" stb. -
# best-effort, ha nem talál semmit, a rekord üres értékkel kerül be (a
# dashboardon/eredeti levélben még mindig megnézhető).
MEROALLAS_ERTEK_MINTA = re.compile(
    r"(?:mérőállás|óraállás)\D{0,10}(\d[\d\s]{0,9})\s*(m3|m³|kwh)?",
    re.IGNORECASE,
)


def tartalom_tipus_azonositas(targy: str, teljes_szoveg: str) -> str:
    """A tárgy + a levél (és szükség esetén a csatolt PDF) szövege
    alapján visszaadja, MILYEN FAJTA dokumentumról van szó. Ez a program
    szíve - itt nem szolgáltatónkénti tárgy-sablonokra támaszkodunk,
    hanem általános, tartalmi jelentésre utaló kulcsszavakra."""
    egyesitett = f"{targy}\n{teljes_szoveg}"
    if FIZETVE_MINTA.search(egyesitett):
        return "fizetve"
    if EMLEKEZTETO_MINTA.search(egyesitett):
        return "fizetesi_emlekezteto"
    if MEROALLAS_MINTA.search(egyesitett):
        return "meroallas"
    if SZAMLA_MINTA.search(egyesitett):
        return "uj_szamla"
    return "ismeretlen"


# ════════════════════════════════════════════
#  🔐  TITKOSÍTÁS (AES-GCM, jelszó-alapú, PBKDF2)
# ════════════════════════════════════════════
def _kulcs_szarmaztatas(jelszo: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000
    )
    return kdf.derive(jelszo.encode("utf-8"))


def titkosit_es_ment(adat: dict, jelszo: str, fajl: str):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not jelszo:
        raise RuntimeError(
            "Nincs beállítva SZAMLA_TITKOSITAS_JELSZO - számlaadatot "
            "titkosítás nélkül NEM szabad menteni egy publikus repóba."
        )
    salt = os.urandom(16)
    nonce = os.urandom(12)
    kulcs = _kulcs_szarmaztatas(jelszo, salt)
    aesgcm = AESGCM(kulcs)
    nyers = json.dumps(adat, ensure_ascii=False).encode("utf-8")
    titkositott = aesgcm.encrypt(nonce, nyers, None)

    csomag = {
        "verzio": 2,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "adat": base64.b64encode(titkositott).decode("ascii"),
        "frissitve": magyar_ido().isoformat(),
    }
    os.makedirs(os.path.dirname(fajl), exist_ok=True)
    with open(fajl, "w", encoding="utf-8") as f:
        json.dump(csomag, f, ensure_ascii=False, indent=2)


def visszafejt(jelszo: str, fajl: str) -> dict:
    alap = {
        "szamlak": {},
        "meroallasok": {},
        "ismeretlen_dokumentumok": {},
        "feldolgozott_uidok": [],
        "utolso_emlekezteto_nap": None,
    }
    if not os.path.exists(fajl):
        return alap

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    with open(fajl, "r", encoding="utf-8") as f:
        csomag = json.load(f)

    salt = base64.b64decode(csomag["salt"])
    nonce = base64.b64decode(csomag["nonce"])
    titkositott = base64.b64decode(csomag["adat"])
    kulcs = _kulcs_szarmaztatas(jelszo, salt)
    aesgcm = AESGCM(kulcs)
    nyers = aesgcm.decrypt(nonce, titkositott, None)
    betoltott = json.loads(nyers.decode("utf-8"))
    alap.update(betoltott)
    return alap


# ════════════════════════════════════════════
#  📥  IMAP - EMAILEK BEOLVASÁSA
# ════════════════════════════════════════════
def imap_kapcsolat():
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(IMAP_USER, IMAP_JELSZO)
    conn.select(IMAP_MAPPA)
    return conn


def _fejlec_dekodolas(nyers):
    if not nyers:
        return ""
    return str(make_header(decode_header(nyers)))


def _feladó_cim(msg) -> str:
    from email.utils import parseaddr

    _, cim = parseaddr(msg.get("From", ""))
    return cim.lower()


def uj_uidok_lekerese(conn, mar_feldolgozott: set, max_uj=60):
    """Az utolsó ~30 nap emailjei közül visszaadja azokat az UID-kat,
    amiket még nem dolgoztunk fel. Nem jelöli olvasottnak a postafiókban
    lévő eredeti leveleket (nem piszkáljuk a te postaládád állapotát)."""
    harminc_napja = (magyar_ma() - timedelta(days=30)).strftime("%d-%b-%Y")
    tipus, adat = conn.uid("search", None, f'(SINCE "{harminc_napja}")')
    if tipus != "OK" or not adat or not adat[0]:
        return []
    osszes_uid = adat[0].split()
    uj = [u for u in osszes_uid if u.decode() not in mar_feldolgozott]
    return uj[:max_uj]


def uid_letoltese(conn, uid):
    tipus, adat = conn.uid("fetch", uid, "(RFC822)")
    if tipus != "OK" or not adat or not adat[0]:
        return None
    nyers = adat[0][1]
    return email_lib.message_from_bytes(nyers)


def pdf_csatolmany(msg):
    """Visszaadja az első PDF-csatolmány (fájlnév, bytes) párost, vagy
    (None, None)-t, ha nincs PDF csatolva a levélhez."""
    for resz in msg.walk():
        content_type = resz.get_content_type()
        fajlnev = resz.get_filename()
        if fajlnev:
            fajlnev = _fejlec_dekodolas(fajlnev)
        if content_type == "application/pdf" or (
            fajlnev and fajlnev.lower().endswith(".pdf")
        ):
            try:
                return fajlnev or "szamla.pdf", resz.get_payload(decode=True)
            except Exception:
                continue
    return None, None


def email_szoveg_kinyerese(msg) -> str:
    """Az email szöveges (plain + HTML-ből egyszerűsített) tartalmát adja
    vissza, hogy abból tudjunk tartalmat felismerni / összeget/határidőt
    keresni."""
    reszek = []
    if msg.is_multipart():
        for resz in msg.walk():
            ctype = resz.get_content_type()
            if ctype in ("text/plain", "text/html"):
                try:
                    charset = resz.get_content_charset() or "utf-8"
                    darab = resz.get_payload(decode=True).decode(charset, errors="ignore")
                    if ctype == "text/html":
                        darab = re.sub(r"<[^>]+>", " ", darab)
                    reszek.append(darab)
                except Exception:
                    continue
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            darab = msg.get_payload(decode=True).decode(charset, errors="ignore")
            reszek.append(re.sub(r"<[^>]+>", " ", darab))
        except Exception:
            pass
    return "\n".join(reszek)


def pdf_szoveg_kinyerese(pdf_bytes) -> str:
    """Tartalék: ha az email szövegéből nem sikerült elég információt
    kiolvasni (sem a fajta felismeréséhez, sem összeg/határidő/mérőállás
    kinyeréséhez), megpróbáljuk a csatolt PDF szöveges tartalmából."""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return "\n".join((oldal.extract_text() or "") for oldal in pdf.pages[:2])
    except Exception as e:
        print(f"      ⚠️  PDF-szöveg kiolvasása sikertelen: {e}")
        return ""


def osszeg_kinyerese(szoveg: str):
    talalat = OSSZEG_MINTA.search(szoveg)
    if not talalat:
        return None
    szam = talalat.group(1).replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(szam)
    except ValueError:
        return None


def hatarido_kinyerese(szoveg: str):
    talalat = HATARIDO_MINTA.search(szoveg)
    if not talalat:
        return None
    ev, ho, nap = talalat.groups()
    try:
        return f"{int(ev):04d}-{int(ho):02d}-{int(nap):02d}"
    except ValueError:
        return None


def meroallas_ertek_kinyerese(szoveg: str):
    talalat = MEROALLAS_ERTEK_MINTA.search(szoveg)
    if not talalat:
        return None
    szam = talalat.group(1).replace(" ", "")
    mertekegyseg = (talalat.group(2) or "").strip()
    return {"ertek": szam, "mertekegyseg": mertekegyseg or None}


# ════════════════════════════════════════════
#  📧  EMAIL KÜLDÉS
# ════════════════════════════════════════════
def email_kuldes(targy, html_torzs, csatolmanyok=None):
    """csatolmanyok: [(fajlnev, bytes), ...] - lehet üres/None."""
    if not (EMAIL_KULDO and EMAIL_JELSZO_KULDES and EMAIL_CIMZETT):
        print("  ⚠️  Nincs teljesen beállítva az email-küldés - kihagyva.")
        return False

    msg = MIMEMultipart("mixed")
    msg["Subject"] = targy
    msg["From"] = EMAIL_KULDO
    msg["To"] = EMAIL_CIMZETT
    msg.attach(MIMEText(html_torzs, "html", "utf-8"))

    for fajlnev, tartalom in (csatolmanyok or []):
        if not tartalom:
            continue
        resz = MIMEApplication(tartalom, _subtype="pdf")
        resz.add_header("Content-Disposition", "attachment", filename=fajlnev)
        msg.attach(resz)

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(EMAIL_KULDO, EMAIL_JELSZO_KULDES)
            server.send_message(msg)
        print(f"  ✅ Email elküldve: {targy}")
        return True
    except Exception as e:
        print(f"  ⚠️  Email-küldési hiba: {e}")
        return False


def forint(osszeg):
    if osszeg is None:
        return "ismeretlen összeg"
    return f"{osszeg:,.0f} Ft".replace(",", " ")


def uj_szamla_email_html(rekord):
    ismeretlen_jelzes = ""
    if rekord["osszeg"] is None or rekord["hatarido"] is None:
        ismeretlen_jelzes = (
            '<p style="color:#b45309;background:#fffbeb;padding:10px 14px;'
            'border-radius:8px;">⚠️ Az összeget és/vagy a határidőt nem '
            "sikerült automatikusan kiolvasni ebből az emailből - nézd meg "
            "a csatolt PDF-et / az eredeti levelet a pontos adatokért.</p>"
        )
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;">
      <h2 style="color:#1d4ed8;">📄 Új számla érkezett - {rekord['szolgaltato_nev']}</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:6px 0;color:#555;">Tárgy</td>
            <td style="padding:6px 0;"><strong>{rekord['targy']}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#555;">Összeg</td>
            <td style="padding:6px 0;"><strong>{forint(rekord['osszeg'])}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#555;">Fizetési határidő</td>
            <td style="padding:6px 0;"><strong>{rekord['hatarido'] or 'ismeretlen'}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#555;">Érkezett</td>
            <td style="padding:6px 0;">{rekord['erkezett']}</td></tr>
      </table>
      {ismeretlen_jelzes}
      <p style="color:#777;font-size:13px;margin-top:20px;">
        Ha volt csatolt PDF az eredeti levélben, azt ehhez az emailhez is
        csatoltuk.
      </p>
    </div>
    """


def uj_meroallas_email_html(rekord):
    ertek_sor = "ismeretlen (nézd meg az eredeti levelet)"
    if rekord.get("ertek"):
        ertek_sor = rekord["ertek"] + (f" {rekord['mertekegyseg']}" if rekord.get("mertekegyseg") else "")
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;">
      <h2 style="color:#0f766e;">🔢 Mérőállással kapcsolatos levél - {rekord['szolgaltato_nev']}</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:6px 0;color:#555;">Tárgy</td>
            <td style="padding:6px 0;"><strong>{rekord['targy']}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#555;">Kiolvasott érték</td>
            <td style="padding:6px 0;"><strong>{ertek_sor}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#555;">Érkezett</td>
            <td style="padding:6px 0;">{rekord['erkezett']}</td></tr>
      </table>
      <p style="color:#777;font-size:13px;margin-top:20px;">
        Ez csak tájékoztató bejegyzés (nem számla) - a dashboardon a
        "Mérőállások" részben is megtalálod.
      </p>
    </div>
    """


def ismeretlen_email_html(rekord):
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;">
      <h2 style="color:#b45309;">❓ Fel nem ismert levél a számla-postafiókban</h2>
      <p>Egy figyelt szolgáltatótól ({rekord['szolgaltato_nev']}) érkezett levél,
         de a tartalma egyik ismert mintára (új számla / mérőállás / fizetés-
         visszaigazolás / emlékeztető) sem illett rá.</p>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:6px 0;color:#555;">Tárgy</td>
            <td style="padding:6px 0;"><strong>{rekord['targy']}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#555;">Érkezett</td>
            <td style="padding:6px 0;">{rekord['erkezett']}</td></tr>
      </table>
      <p style="color:#555;font-size:13px;margin-top:14px;background:#f9fafb;
                padding:10px 14px;border-radius:8px;white-space:pre-wrap;">{rekord.get('reszlet', '')}</p>
      <p style="color:#777;font-size:13px;margin-top:20px;">
        Ha ez egy valódi számla/mérőállás-értesítés volt, szólj, hogy a
        felismerő mintákat pontosítsuk ez alapján.
      </p>
    </div>
    """


def osszesito_email_html(fizetetlen_lista, vegosszeg, provider_osszegek):
    sorok = ""
    for r in fizetetlen_lista:
        lejart = r["hatarido"] and r["hatarido"] < magyar_ma().isoformat()
        szin = "#dc2626" if lejart else "#111827"
        sorok += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">{r['szolgaltato_nev']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{r['targy']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">{forint(r['osszeg'])}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;color:{szin};">
            {r['hatarido'] or 'ismeretlen'}{' ⏰ LEJÁRT' if lejart else ''}
          </td>
        </tr>"""

    provider_sorok = "".join(
        f'<li>{nev}: <strong>{forint(osszeg)}</strong></li>'
        for nev, osszeg in provider_osszegek.items()
    )

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;">
      <h2 style="color:#b91c1c;">💰 Fizetetlen számlák összesítője</h2>
      <p>Az alábbi számlák még nincsenek kifizetve, és valamelyik határideje
         {SZAMLA_EMLEKEZTETO_NAPOK_ELOTTE} napon belül lejár (vagy már lejárt):</p>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr style="background:#f3f4f6;">
          <th style="padding:8px;text-align:left;">Szolgáltató</th>
          <th style="padding:8px;text-align:left;">Tárgy</th>
          <th style="padding:8px;text-align:right;">Összeg</th>
          <th style="padding:8px;text-align:left;">Határidő</th>
        </tr>
        {sorok}
      </table>
      <h3 style="margin-top:24px;">Szolgáltatónkénti bontás</h3>
      <ul>{provider_sorok}</ul>
      <p style="font-size:18px;margin-top:16px;">
        <strong>Végösszeg: {forint(vegosszeg)}</strong>
      </p>
      <p style="color:#777;font-size:13px;margin-top:20px;">
        Ahol sikerült, a PDF-számlákat is csatoltuk ehhez az emailhez.
      </p>
    </div>
    """


# ════════════════════════════════════════════
#  🚀  FŐ FOLYAMAT
# ════════════════════════════════════════════
def main():
    print(f"💰 Számla Figyelő – {magyar_ido().strftime('%Y.%m.%d %H:%M:%S')}")

    if not TITKOSITAS_JELSZO:
        print("❌ Nincs beállítva SZAMLA_TITKOSITAS_JELSZO - leállás (adatvédelmi okból "
              "nem menthetünk számlaadatot titkosítás nélkül).")
        return
    if not (IMAP_USER and IMAP_JELSZO):
        print("❌ Nincs beállítva SZAMLA_IMAP_USER / SZAMLA_IMAP_JELSZO - leállás.")
        return

    allapot = visszafejt(TITKOSITAS_JELSZO, ALLAPOT_FAJL)
    szamlak = allapot.setdefault("szamlak", {})
    meroallasok = allapot.setdefault("meroallasok", {})
    ismeretlen_dokumentumok = allapot.setdefault("ismeretlen_dokumentumok", {})
    feldolgozott_uidok = set(allapot.setdefault("feldolgozott_uidok", []))

    # ---- 1. Új emailek beolvasása ----
    try:
        conn = imap_kapcsolat()
    except Exception as e:
        print(f"❌ IMAP-bejelentkezés sikertelen: {e}")
        return

    try:
        uj_uidok = uj_uidok_lekerese(conn, feldolgozott_uidok)
        print(f"📬 {len(uj_uidok)} még feldolgozatlan email az elmúlt 30 napból.")

        for uid in uj_uidok:
            uid_str = uid.decode()
            msg = uid_letoltese(conn, uid)
            feldolgozott_uidok.add(uid_str)
            if msg is None:
                continue

            feladó = _feladó_cim(msg)
            szolgaltato = szolgaltato_azonositasa(feladó)
            if not szolgaltato:
                continue  # nem a figyelt szolgáltatók egyikétől jött

            cfg = SZOLGALTATOK[szolgaltato]
            targy = _fejlec_dekodolas(msg.get("Subject", ""))
            erkezett_fejlec = msg.get("Date", "")

            szoveg = email_szoveg_kinyerese(msg)
            pdf_nev, pdf_bytes = pdf_csatolmany(msg)

            # Elsőként a tárgy + email-törzs alapján próbálunk fajtát
            # felismerni - csak ha ez "ismeretlen"-t ad, és van csatolt
            # PDF, próbáljuk meg a PDF szövegével kiegészítve újra (lehet,
            # hogy a lényeg csak a PDF-ben van benne, nem az email
            # törzsében).
            tipus = tartalom_tipus_azonositas(targy, szoveg)
            pdf_szoveg = ""
            if tipus == "ismeretlen" and pdf_bytes:
                pdf_szoveg = pdf_szoveg_kinyerese(pdf_bytes)
                tipus = tartalom_tipus_azonositas(targy, szoveg + "\n" + pdf_szoveg)

            teljes_szoveg_egyesitve = f"{szoveg}\n{pdf_szoveg}"

            # ---- fizetve ----
            if tipus == "fizetve":
                fizetett_osszeg = osszeg_kinyerese(teljes_szoveg_egyesitve)
                jeloltek = [
                    (rid, r) for rid, r in szamlak.items()
                    if r["szolgaltato"] == szolgaltato and not r["fizetve"]
                ]
                talalat = None
                if fizetett_osszeg is not None:
                    for rid, r in jeloltek:
                        if r["osszeg"] is not None and abs(r["osszeg"] - fizetett_osszeg) < 1:
                            talalat = rid
                            break
                if not talalat and jeloltek:
                    jeloltek.sort(key=lambda x: x[1]["erkezett"])
                    talalat = jeloltek[0][0]
                if talalat:
                    szamlak[talalat]["fizetve"] = True
                    szamlak[talalat]["fizetve_datum"] = magyar_ido().isoformat()
                    print(f"      ✅ Fizetettre állítva: {szolgaltato} / {szamlak[talalat]['targy'][:50]}")
                else:
                    print(f"      ⚠️  Fizetési visszaigazolás érkezett ({szolgaltato}), "
                          "de nem találtunk hozzá illő fizetetlen számlát.")
                continue

            # ---- fizetesi_emlekezteto: szándékosan nem hoz létre semmit ----
            if tipus == "fizetesi_emlekezteto":
                print(f"      ℹ️  Fizetési emlékeztető ({szolgaltato}) - kihagyva, "
                      "nem hoz létre új tételt.")
                continue

            # ---- meroallas ----
            if tipus == "meroallas":
                mid = hashlib.md5(f"{uid_str}|meroallas".encode("utf-8")).hexdigest()[:16]
                if mid in meroallasok:
                    continue
                ertek_info = meroallas_ertek_kinyerese(teljes_szoveg_egyesitve) or {}
                mrekord = {
                    "szolgaltato": szolgaltato,
                    "szolgaltato_nev": cfg["nev"],
                    "targy": targy,
                    "erkezett": magyar_ido().isoformat(),
                    "erkezett_fejlec": erkezett_fejlec,
                    "ertek": ertek_info.get("ertek"),
                    "mertekegyseg": ertek_info.get("mertekegyseg"),
                    "uid": uid_str,
                }
                meroallasok[mid] = mrekord
                print(f"      🔢 Mérőállás-esemény: {cfg['nev']} – {targy[:60]}")
                if MEROALLAS_ERTESITES_EMAIL:
                    email_kuldes(
                        f"🔢 Mérőállás – {cfg['nev']}",
                        uj_meroallas_email_html(mrekord),
                    )
                continue

            # ---- uj_szamla ----
            if tipus == "uj_szamla":
                rid = hashlib.md5(f"{uid_str}|uj_szamla".encode("utf-8")).hexdigest()[:16]
                if rid in szamlak:
                    continue

                osszeg = osszeg_kinyerese(szoveg)
                hatarido = hatarido_kinyerese(szoveg)
                if (osszeg is None or hatarido is None) and pdf_bytes:
                    if not pdf_szoveg:
                        pdf_szoveg = pdf_szoveg_kinyerese(pdf_bytes)
                    if osszeg is None:
                        osszeg = osszeg_kinyerese(pdf_szoveg)
                    if hatarido is None:
                        hatarido = hatarido_kinyerese(pdf_szoveg)

                rekord = {
                    "szolgaltato": szolgaltato,
                    "szolgaltato_nev": cfg["nev"],
                    "targy": targy,
                    "erkezett": magyar_ido().isoformat(),
                    "erkezett_fejlec": erkezett_fejlec,
                    "osszeg": osszeg,
                    "hatarido": hatarido,
                    "fizetve": False,
                    "fizetve_datum": None,
                    "uid": uid_str,
                }
                szamlak[rid] = rekord
                print(f"      🆕 Új számla: {cfg['nev']} – {forint(osszeg)} – határidő: {hatarido}")

                email_kuldes(
                    f"📄 Új számla – {cfg['nev']}",
                    uj_szamla_email_html(rekord),
                    [(pdf_nev or "szamla.pdf", pdf_bytes)] if pdf_bytes else None,
                )
                continue

            # ---- ismeretlen: soha nem dobjuk el csendben ----
            iid = hashlib.md5(f"{uid_str}|ismeretlen".encode("utf-8")).hexdigest()[:16]
            if iid in ismeretlen_dokumentumok:
                continue
            reszlet = teljes_szoveg_egyesitve.strip()
            reszlet = re.sub(r"\s+", " ", reszlet)[:400]
            irekord = {
                "szolgaltato": szolgaltato,
                "szolgaltato_nev": cfg["nev"],
                "targy": targy,
                "erkezett": magyar_ido().isoformat(),
                "erkezett_fejlec": erkezett_fejlec,
                "reszlet": reszlet,
                "uid": uid_str,
            }
            ismeretlen_dokumentumok[iid] = irekord
            print(f"      ❓ Fel nem ismert levél ({szolgaltato}): {targy[:60]}")
            if ISMERETLEN_ERTESITES_EMAIL:
                email_kuldes(
                    f"❓ Fel nem ismert levél – {cfg['nev']}",
                    ismeretlen_email_html(irekord),
                )
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    # ---- 2. Határidő-előtti összesítő (naponta legfeljebb egyszer) ----
    ma_str = magyar_ma().isoformat()
    kuszob = (magyar_ma() + timedelta(days=SZAMLA_EMLEKEZTETO_NAPOK_ELOTTE)).isoformat()

    fizetetlen = [r for r in szamlak.values() if not r["fizetve"]]
    figyelmeztetendo = [
        r for r in fizetetlen
        if r["hatarido"] and r["hatarido"] <= kuszob
    ]

    if figyelmeztetendo and allapot.get("utolso_emlekezteto_nap") != ma_str:
        vegosszeg = sum(r["osszeg"] or 0 for r in fizetetlen)
        provider_osszegek = {}
        for r in fizetetlen:
            provider_osszegek[r["szolgaltato_nev"]] = (
                provider_osszegek.get(r["szolgaltato_nev"], 0) + (r["osszeg"] or 0)
            )

        # PDF-ek friss visszatöltése az IMAP-ból (nem tartósan tárolt
        # másolatból), amennyire lehetséges.
        csatolmanyok = []
        try:
            conn2 = imap_kapcsolat()
            for r in fizetetlen:
                uid = r.get("uid")
                if not uid:
                    continue
                msg = uid_letoltese(conn2, uid.encode())
                if msg is None:
                    continue
                pdf_nev, pdf_bytes = pdf_csatolmany(msg)
                if pdf_bytes:
                    csatolmanyok.append((pdf_nev or f"{r['szolgaltato']}_szamla.pdf", pdf_bytes))
            conn2.logout()
        except Exception as e:
            print(f"  ⚠️  PDF-ek friss visszatöltése sikertelen: {e}")

        email_kuldes(
            f"💰 Fizetetlen számlák – {len(fizetetlen)} db – {forint(vegosszeg)}",
            osszesito_email_html(fizetetlen, vegosszeg, provider_osszegek),
            csatolmanyok,
        )
        allapot["utolso_emlekezteto_nap"] = ma_str

    # ---- 3. Állapot mentése (titkosítva) ----
    allapot["feldolgozott_uidok"] = list(feldolgozott_uidok)[-2000:]  # ne nőjön a végtelenségig
    # A mérőállás- és ismeretlen-naplók se nőjenek a végtelenségig -
    # a legutóbbi néhány száz bejegyzést tartjuk meg (érkezés szerint).
    if len(meroallasok) > 500:
        rendezett = sorted(meroallasok.items(), key=lambda kv: kv[1]["erkezett"])
        allapot["meroallasok"] = dict(rendezett[-500:])
    if len(ismeretlen_dokumentumok) > 300:
        rendezett = sorted(ismeretlen_dokumentumok.items(), key=lambda kv: kv[1]["erkezett"])
        allapot["ismeretlen_dokumentumok"] = dict(rendezett[-300:])

    titkosit_es_ment(allapot, TITKOSITAS_JELSZO, ALLAPOT_FAJL)
    print("💾 Állapot mentve (titkosítva). ✅ Kész.\n")


if __name__ == "__main__":
    main()
