#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SZÁMLA FIGYELŐ
====================================================================

Források:
  1. IMAP:
     - Fővárosi Vízművek
     - MVM
  2. Díjnet:
     - közvetlen portál-lekérdezés, ha a Díjnet secret-ek be vannak állítva

Fő célok:
  - ne tárgysablonokra, hanem tartalomra támaszkodjunk
  - számlát ne lehessen könnyen összekeverni mérőállás-értesítéssel
  - fizetési visszaigazolás ne jelöljön ki találomra egy számlát
  - ismeretlen levelet soha ne dobjunk el csendben
  - számlaadat csak AES-GCM-mel titkosítva kerüljön állapotfájlba
  - PDF-et ne mentsünk fájlba
  - GitHub Actions környezetben is biztonságosan működjön

Környezeti változók:

  SZAMLA_IMAP_HOST
  SZAMLA_IMAP_PORT
  SZAMLA_IMAP_USER
  SZAMLA_IMAP_JELSZO
  SZAMLA_IMAP_MAPPA

  SMTP_HOST
  SMTP_PORT
  EMAIL_KULDO_SZAMLA
  EMAIL_JELSZO_SZAMLA
  EMAIL_CIMZETT_SZAMLA

  SZAMLA_TITKOSITAS_JELSZO

  SZAMLA_DIJNET_USER
  SZAMLA_DIJNET_JELSZO

  SZAMLA_DRY_RUN=1             # opcionális
  SZAMLA_DEBUG=1               # opcionális

Függőségek:

  pip install cryptography requests beautifulsoup4 lxml pdfplumber
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

from html import escape as html_escape
from email.header import decode_header, make_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import parseaddr, parsedate_to_datetime

from datetime import datetime, timedelta, timezone, date

import requests
from bs4 import BeautifulSoup


# ════════════════════════════════════════════════════════════════
# KONFIGURÁCIÓ
# ════════════════════════════════════════════════════════════════

MAGYAR_TZ = timezone(timedelta(hours=2))

IMAP_HOST = os.environ.get("SZAMLA_IMAP_HOST") or "imap.gmail.com"
IMAP_PORT = int(os.environ.get("SZAMLA_IMAP_PORT") or "993")
IMAP_USER = os.environ.get("SZAMLA_IMAP_USER") or ""
IMAP_JELSZO = os.environ.get("SZAMLA_IMAP_JELSZO") or ""
IMAP_MAPPA = os.environ.get("SZAMLA_IMAP_MAPPA") or "INBOX"

SMTP_HOST = os.environ.get("SMTP_HOST") or "smtp.gmail.com"
SMTP_PORT = int(os.environ.get("SMTP_PORT") or "465")

EMAIL_KULDO = (
    os.environ.get("EMAIL_KULDO_SZAMLA")
    or IMAP_USER
)
EMAIL_JELSZO_KULDES = (
    os.environ.get("EMAIL_JELSZO_SZAMLA")
    or IMAP_JELSZO
)
EMAIL_CIMZETT = os.environ.get("EMAIL_CIMZETT_SZAMLA") or ""

TITKOSITAS_JELSZO = (
    os.environ.get("SZAMLA_TITKOSITAS_JELSZO")
    or ""
)

DIJNET_USER = os.environ.get("SZAMLA_DIJNET_USER") or ""
DIJNET_JELSZO = os.environ.get("SZAMLA_DIJNET_JELSZO") or ""

DRY_RUN = (
    os.environ.get("SZAMLA_DRY_RUN", "").strip().lower()
    in ("1", "true", "yes", "igen")
)

DEBUG = (
    os.environ.get("SZAMLA_DEBUG", "").strip().lower()
    in ("1", "true", "yes", "igen")
)

# IMAP feldolgozási ablak.
# 30 nap helyett szándékosan hosszabb.
IMAP_LEKERDEZES_NAPOK = 90

# Egyszerre legfeljebb ennyi új email feldolgozása.
IMAP_MAX_UJ_EMAIL = 100

# Összesítő:
SZAMLA_EMLEKEZTETO_NAPOK_ELOTTE = 5

# Mérőállás-email:
MEROALLAS_ERTESITES_EMAIL = True

# Ismeretlen levél:
ISMERETLEN_ERTESITES_EMAIL = True

# Ismeretlen fizetés:
ISMERETLEN_FIZETES_ERTESITES_EMAIL = True

# Díjnet:
DIJNET_LEKERDEZES_NAPOK_VISSZA = 120
DIJNET_MAX_PDF_LETOLTES_FUTASONKENT = 8

ALLAPOT_FAJL = "szamlak/szamla_allapot.enc.json"


# ════════════════════════════════════════════════════════════════
# SZOLGÁLTATÓK
# ════════════════════════════════════════════════════════════════

SZOLGALTATOK = {
    "vizmuvek": {
        "nev": "Fővárosi Vízművek",
        "feladok": (
            "vizmuvek.hu",
            "fovarosivizmuvek.hu",
        ),
    },
    "mvm": {
        "nev": "MVM",
        "feladok": (
            "mvmnext.hu",
            "mvm.hu",
            "mvmenergia.hu",
        ),
    },
}


# ════════════════════════════════════════════════════════════════
# SEGÉDFÜGGVÉNYEK
# ════════════════════════════════════════════════════════════════

def magyar_ido():
    return datetime.now(MAGYAR_TZ)


def magyar_ma():
    return magyar_ido().date()


def log(msg):
    print(msg, flush=True)


def debug(msg):
    if DEBUG:
        print(f"      🔍 {msg}", flush=True)


def norm_szoveg(szoveg):
    """
    Unicode-szöveg normalizálása kereséshez.
    """
    if not szoveg:
        return ""

    szoveg = szoveg.replace("\xa0", " ")
    szoveg = szoveg.replace("\u200b", "")
    szoveg = re.sub(r"[ \t]+", " ", szoveg)
    szoveg = re.sub(r"\n{3,}", "\n\n", szoveg)

    return szoveg.strip()


def normalizalt_kisbetus(szoveg):
    return norm_szoveg(szoveg).lower()


def szolgaltato_azonositasa(felado_cim):
    felado = (felado_cim or "").lower()

    for kulcs, cfg in SZOLGALTATOK.items():
        for domain in cfg["feladok"]:
            if felado.endswith("@" + domain) or domain in felado:
                return kulcs

    return None


def _fejlec_dekodolas(nyers):
    if not nyers:
        return ""

    try:
        return str(make_header(decode_header(nyers)))
    except Exception:
        return str(nyers)


def _felado_cim(msg):
    _, cim = parseaddr(msg.get("From", ""))
    return cim.lower().strip()


def html_szoveg_tisztitasa(html):
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    return soup.get_text(" ", strip=True)


# ════════════════════════════════════════════════════════════════
# TARTALOMFELISMERÉS
# ════════════════════════════════════════════════════════════════

FIZETVE_MINTA = re.compile(
    r"""
    (?:
        fizetés.{0,40}(?:sikeres|beérkezett|jóváírva|teljesült|megtörtént)
        |
        befizetés.{0,40}(?:sikeres|beérkezett|jóváírva|visszaigazol)
        |
        sikeres.{0,25}(?:fizetés|befizetés)
        |
        számla.{0,35}(?:kiegyenlítve|rendezve)
        |
        (?:kiegyenlítve|rendezve).{0,35}számla
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


EMLEKEZTETO_MINTA = re.compile(
    r"""
    (?:
        fizetési\s+emlékeztető
        |
        emlékeztető
        |
        lejárt\s+(?:számla|tartozás)
        |
        fizetésre\s+felszólít
        |
        tartozás\s+fizetés
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


MEROALLAS_MINTA = re.compile(
    r"""
    (?:
        mérőállás
        |
        óraállás
        |
        mérő\s*csere
        |
        mérőcsere
        |
        leolvasás
        |
        diktálás
        |
        diktálni
        |
        diktál
        |
        bekötési\s*mérő
        |
        plomba
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


SZAMLA_MINTA = re.compile(
    r"""
    (?:
        számla
        |
        díjbekérő
        |
        fizetendő
        |
        fizetési\s+határidő
        |
        számlaszám
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


# Kifejezetten erős számlaindikátorok.
EROS_SZAMLA_MINTA = re.compile(
    r"""
    (?:
        fizetési\s+határidő
        |
        fizetendő\s+összeg
        |
        számlaszám
        |
        számla\s+kelte
        |
        számla\s+összege
        |
        végösszeg
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def tartalom_tipus_azonositas(targy, teljes_szoveg):
    """
    Tartalom-alapú felismerés.

    Fontos:
      - fizetve a legszigorúbb
      - emlékeztető külön kategória
      - számla erős indikátorai elsőbbséget élveznek
        egy önmagában gyenge "mérőállás" szóval szemben
    """

    egyesitett = norm_szoveg(
        f"{targy}\n{teljes_szoveg}"
    )

    if FIZETVE_MINTA.search(egyesitett):
        return "fizetve"

    if EMLEKEZTETO_MINTA.search(egyesitett):
        return "fizetesi_emlekezteto"

    van_szamla = bool(SZAMLA_MINTA.search(egyesitett))
    eros_szamla = bool(EROS_SZAMLA_MINTA.search(egyesitett))
    van_mero = bool(MEROALLAS_MINTA.search(egyesitett))

    # Ha valódi számlára utaló erős jel van,
    # nem engedjük, hogy egy "mérőállás" szó elvigye.
    if eros_szamla:
        return "uj_szamla"

    # Ha számlára utaló szó és mérőállás is van,
    # a teljes szöveg mennyiségi súlyozásával döntünk.
    if van_szamla and van_mero:
        szamla_talalatok = len(
            SZAMLA_MINTA.findall(egyesitett)
        )
        mero_talalatok = len(
            MEROALLAS_MINTA.findall(egyesitett)
        )

        if szamla_talalatok >= mero_talalatok:
            return "uj_szamla"

        return "meroallas"

    if van_szamla:
        return "uj_szamla"

    if van_mero:
        return "meroallas"

    return "ismeretlen"


# ════════════════════════════════════════════════════════════════
# ÖSSZEG / DÁTUM / MÉRŐÁLLÁS
# ════════════════════════════════════════════════════════════════

OSSZEG_MINTA = re.compile(
    r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?)\s*(Ft|HUF)",
    re.IGNORECASE,
)


FIZETENDO_OSSZEG_MINTA = re.compile(
    r"""
    (?:
        fizetendő
        |
        fizetendő\s+összeg
        |
        végösszeg
        |
        összesen
        |
        fizetendő\s+számlaösszeg
    )
    \D{0,50}
    (\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?)
    \s*(?:Ft|HUF)
    """,
    re.IGNORECASE | re.VERBOSE,
)


HATARIDO_MINTA = re.compile(
    r"""
    (?:
        fizetési\s*határidő
        |
        határidő
        |
        esedékesség
        |
        esedékes
    )
    \D{0,30}
    (
        \d{4}
        [.\-/\s]+
        \d{1,2}
        [.\-/\s]+
        \d{1,2}
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


HATARIDO_MAGYAR_MINTA = re.compile(
    r"""
    (?:
        fizetési\s*határidő
        |
        határidő
        |
        esedékesség
        |
        esedékes
    )
    \D{0,30}
    (
        \d{1,2}
        \.\s*
        \d{1,2}
        \.\s*
        \d{4}
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


MEROALLAS_ERTEK_MINTA = re.compile(
    r"""
    (?:
        mérőállás
        |
        óraállás
    )
    \D{0,15}
    (\d[\d\s]{0,12})
    \s*(m3|m³|kwh)?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def szam_float(szam):
    if szam is None:
        return None

    szam = str(szam).strip()

    # Magyar formátum:
    # 12 345,67
    # 12.345,67
    # 12345
    szam = szam.replace(" ", "")

    if "," in szam:
        szam = szam.replace(".", "")
        szam = szam.replace(",", ".")
    else:
        # Ha pont van, és az ezres tagolásnak tűnik.
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", szam):
            szam = szam.replace(".", "")

    try:
        return float(szam)
    except ValueError:
        return None


def osszeg_kinyerese(szoveg):
    """
    Először célzottan a fizetendő összeget keresi.
    Csak utána használ általános Ft-mintát.
    """

    szoveg = norm_szoveg(szoveg)

    talalat = FIZETENDO_OSSZEG_MINTA.search(szoveg)

    if talalat:
        osszeg = szam_float(talalat.group(1))
        if osszeg is not None:
            return osszeg

    talalatok = list(OSSZEG_MINTA.finditer(szoveg))

    if not talalatok:
        return None

    # Ha több összeg van, próbáljuk meg a "fizetendő" környezetét.
    for talalat in talalatok:
        start = max(0, talalat.start() - 80)
        context = szoveg[start:talalat.end()].lower()

        if any(
            kulcsszo in context
            for kulcsszo in (
                "fizetendő",
                "végösszeg",
                "összesen",
            )
        ):
            return szam_float(talalat.group(1))

    # Végső fallback.
    return szam_float(talalatok[0].group(1))


def _datum_ellenorzes(ev, ho, nap):
    try:
        d = date(int(ev), int(ho), int(nap))
        return d.isoformat()
    except ValueError:
        return None


def hatarido_kinyerese(szoveg):
    szoveg = norm_szoveg(szoveg)

    talalat = HATARIDO_MINTA.search(szoveg)

    if talalat:
        raw = talalat.group(1)

        nums = re.findall(r"\d+", raw)

        if len(nums) == 3:
            ev, ho, nap = nums
            if len(ev) == 4:
                eredmeny = _datum_ellenorzes(ev, ho, nap)
                if eredmeny:
                    return eredmeny

    talalat = HATARIDO_MAGYAR_MINTA.search(szoveg)

    if talalat:
        nums = re.findall(r"\d+", talalat.group(1))

        if len(nums) == 3:
            nap, ho, ev = nums
            if len(ev) == 4:
                eredmeny = _datum_ellenorzes(ev, ho, nap)
                if eredmeny:
                    return eredmeny

    return None


def meroallas_ertek_kinyerese(szoveg):
    talalat = MEROALLAS_ERTEK_MINTA.search(norm_szoveg(szoveg))

    if not talalat:
        return None

    ertek = re.sub(r"\s+", "", talalat.group(1))
    egyseg = (talalat.group(2) or "").strip()

    return {
        "ertek": ertek,
        "mertekegyseg": egyseg or None,
    }


# ════════════════════════════════════════════════════════════════
# EMAIL PARSING
# ════════════════════════════════════════════════════════════════

def email_szoveg_kinyerese(msg):
    reszek = []

    for resz in msg.walk():
        ctype = resz.get_content_type()

        if ctype not in ("text/plain", "text/html"):
            continue

        try:
            charset = resz.get_content_charset() or "utf-8"
            payload = resz.get_payload(decode=True)

            if not payload:
                continue

            darab = payload.decode(
                charset,
                errors="ignore",
            )

            if ctype == "text/html":
                darab = html_szoveg_tisztitasa(darab)

            reszek.append(darab)

        except Exception as e:
            debug(f"Email-rész feldolgozási hiba: {e}")

    return norm_szoveg("\n".join(reszek))


def pdf_csatolmany(msg):
    for resz in msg.walk():

        content_type = resz.get_content_type()
        fajlnev = resz.get_filename()

        if fajlnev:
            fajlnev = _fejlec_dekodolas(fajlnev)

        if (
            content_type == "application/pdf"
            or (
                fajlnev
                and fajlnev.lower().endswith(".pdf")
            )
        ):
            try:
                payload = resz.get_payload(decode=True)

                if payload:
                    return (
                        fajlnev or "szamla.pdf",
                        payload,
                    )

            except Exception as e:
                debug(f"PDF payload hiba: {e}")

    return None, None


def pdf_szoveg_kinyerese(pdf_bytes):
    if not pdf_bytes:
        return ""

    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            oldalak = []

            for oldal in pdf.pages[:3]:
                try:
                    oldalak.append(
                        oldal.extract_text() or ""
                    )
                except Exception:
                    continue

            return norm_szoveg("\n".join(oldalak))

    except Exception as e:
        debug(f"PDF-szöveg kiolvasása sikertelen: {e}")
        return ""


def email_erkezesi_ido(msg):
    """
    Az email Date fejlécéből próbál valódi dátumot készíteni.
    """
    raw = msg.get("Date")

    if not raw:
        return None

    try:
        dt = parsedate_to_datetime(raw)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(MAGYAR_TZ).isoformat()

    except Exception:
        return None


# ════════════════════════════════════════════════════════════════
# TITKOSÍTÁS
# ════════════════════════════════════════════════════════════════

PBKDF2_ITERATIONS = 600_000


def _kulcs_szarmaztatas(jelszo, salt):
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )

    return kdf.derive(
        jelszo.encode("utf-8")
    )


def titkosit_es_ment(adat, jelszo, fajl):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not jelszo:
        raise RuntimeError(
            "Nincs SZAMLA_TITKOSITAS_JELSZO. "
            "Titkosítás nélküli mentés tiltva."
        )

    salt = os.urandom(16)
    nonce = os.urandom(12)

    kulcs = _kulcs_szarmaztatas(
        jelszo,
        salt,
    )

    aesgcm = AESGCM(kulcs)

    nyers = json.dumps(
        adat,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    titkositott = aesgcm.encrypt(
        nonce,
        nyers,
        None,
    )

    csomag = {
        "verzio": 3,
        "kdf": "PBKDF2-SHA256",
        "iterations": PBKDF2_ITERATIONS,
        "cipher": "AES-256-GCM",
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "adat": base64.b64encode(titkositott).decode("ascii"),
        "frissitve": magyar_ido().isoformat(),
    }

    konyvtar = os.path.dirname(fajl)

    if konyvtar:
        os.makedirs(konyvtar, exist_ok=True)

    with open(fajl, "w", encoding="utf-8") as f:
        json.dump(
            csomag,
            f,
            ensure_ascii=False,
            indent=2,
        )


def alap_allapot():
    return {
        "szamlak": {},
        "meroallasok": {},
        "ismeretlen_dokumentumok": {},
        "ismeretlen_fizetesek": {},
        "feldolgozott_uidok": [],
        "imap_uidvalidity": None,
        "utolso_emlekezteto_nap": None,
    }


def visszafejt(jelszo, fajl):
    alap = alap_allapot()

    if not os.path.exists(fajl):
        return alap

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    with open(fajl, "r", encoding="utf-8") as f:
        csomag = json.load(f)

    if csomag.get("verzio") not in (2, 3):
        raise RuntimeError(
            f"Ismeretlen állapotfájl-verzió: "
            f"{csomag.get('verzio')}"
        )

    salt = base64.b64decode(
        csomag["salt"]
    )
    nonce = base64.b64decode(
        csomag["nonce"]
    )
    titkositott = base64.b64decode(
        csomag["adat"]
    )

    kulcs = _kulcs_szarmaztatas(
        jelszo,
        salt,
    )

    aesgcm = AESGCM(kulcs)

    try:
        nyers = aesgcm.decrypt(
            nonce,
            titkositott,
            None,
        )
    except Exception as e:
        raise RuntimeError(
            "Az állapotfájl visszafejtése sikertelen. "
            "Valószínűleg hibás a SZAMLA_TITKOSITAS_JELSZO."
        ) from e

    betoltott = json.loads(
        nyers.decode("utf-8")
    )

    alap.update(betoltott)

    return alap


# ════════════════════════════════════════════════════════════════
# IMAP
# ════════════════════════════════════════════════════════════════

def imap_kapcsolat():
    conn = imaplib.IMAP4_SSL(
        IMAP_HOST,
        IMAP_PORT,
    )

    conn.login(
        IMAP_USER,
        IMAP_JELSZO,
    )

    tipus, adat = conn.select(
        IMAP_MAPPA,
        readonly=True,
    )

    if tipus != "OK":
        raise RuntimeError(
            f"IMAP mappa megnyitása sikertelen: {IMAP_MAPPA}"
        )

    return conn


def imap_uidvalidity(conn):
    """
    UIDVALIDITY kiolvasása.
    Ha megváltozik, a korábbi UID-ket nem tekintjük automatikusan
    ugyanahhoz a mailboxhoz tartozónak.
    """
    try:
        response = conn.response("UIDVALIDITY")

        if not response:
            return None

        _, adat = response

        if adat and adat[0]:
            raw = adat[0]

            if isinstance(raw, bytes):
                raw = raw.decode(
                    "ascii",
                    errors="ignore",
                )

            return str(raw)

    except Exception as e:
        debug(f"UIDVALIDITY kiolvasási hiba: {e}")

    return None


def uj_uidok_lekerese(
    conn,
    feldolgozott_uidok,
    max_uj=IMAP_MAX_UJ_EMAIL,
):
    kezdo_datum = (
        magyar_ma()
        - timedelta(days=IMAP_LEKERDEZES_NAPOK)
    ).strftime("%d-%b-%Y")

    tipus, adat = conn.uid(
        "search",
        None,
        f'(SINCE "{kezdo_datum}")',
    )

    if tipus != "OK" or not adat or not adat[0]:
        return []

    osszes_uid = adat[0].split()

    uj = []

    for uid in osszes_uid:
        uid_str = uid.decode(
            "ascii",
            errors="ignore",
        )

        if uid_str not in feldolgozott_uidok:
            uj.append(uid)

    # UID szerint növekvő sorrend.
    try:
        uj.sort(key=lambda x: int(x))
    except Exception:
        pass

    return uj[:max_uj]


def uid_letoltese(conn, uid):
    tipus, adat = conn.uid(
        "fetch",
        uid,
        "(RFC822)",
    )

    if (
        tipus != "OK"
        or not adat
        or not adat[0]
    ):
        return None

    try:
        nyers = adat[0][1]
        return email_lib.message_from_bytes(nyers)
    except Exception as e:
        debug(f"Email parse hiba: {e}")
        return None


# ════════════════════════════════════════════════════════════════
# EMAIL KÜLDÉS
# ════════════════════════════════════════════════════════════════

def email_kuldes(
    targy,
    html_torzs,
    csatolmanyok=None,
):
    if DRY_RUN:
        log(f"  🧪 DRY-RUN: email nem lett elküldve: {targy}")
        return True

    if not (
        EMAIL_KULDO
        and EMAIL_JELSZO_KULDES
        and EMAIL_CIMZETT
    ):
        log(
            "  ⚠️ Email-küldés nincs teljesen konfigurálva - kihagyva."
        )
        return False

    msg = MIMEMultipart("mixed")

    msg["Subject"] = targy
    msg["From"] = EMAIL_KULDO
    msg["To"] = EMAIL_CIMZETT

    msg.attach(
        MIMEText(
            html_torzs,
            "html",
            "utf-8",
        )
    )

    for fajlnev, tartalom in (
        csatolmanyok or []
    ):
        if not tartalom:
            continue

        resz = MIMEApplication(
            tartalom,
            _subtype="pdf",
        )

        resz.add_header(
            "Content-Disposition",
            "attachment",
            filename=fajlnev,
        )

        msg.attach(resz)

    try:
        with smtplib.SMTP_SSL(
            SMTP_HOST,
            SMTP_PORT,
            timeout=20,
        ) as server:
            server.login(
                EMAIL_KULDO,
                EMAIL_JELSZO_KULDES,
            )

            server.send_message(msg)

        log(f"  ✅ Email elküldve: {targy}")
        return True

    except Exception as e:
        log(
            f"  ⚠️ Email-küldési hiba: {e}"
        )
        return False


def forint(osszeg):
    if osszeg is None:
        return "ismeretlen összeg"

    return (
        f"{osszeg:,.0f} Ft"
        .replace(",", " ")
    )


# ════════════════════════════════════════════════════════════════
# EMAIL HTML
# ════════════════════════════════════════════════════════════════

def uj_szamla_email_html(rekord):
    szolgaltato = html_escape(
        str(rekord["szolgaltato_nev"])
    )
    targy = html_escape(
        str(rekord["targy"])
    )

    figyelmeztetes = ""

    if (
        rekord.get("osszeg") is None
        or rekord.get("hatarido") is None
    ):
        figyelmeztetes = """
        <p style="
            color:#b45309;
            background:#fffbeb;
            padding:10px 14px;
            border-radius:8px;">
            ⚠️ Az összeg és/vagy a határidő automatikus kiolvasása
            nem volt teljesen sikeres. Ellenőrizd a csatolt PDF-et.
        </p>
        """

    return f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:560px;
        margin:0 auto;">

      <h2 style="color:#1d4ed8;">
        📄 Új számla érkezett – {szolgaltato}
      </h2>

      <table style="
          width:100%;
          border-collapse:collapse;">

        <tr>
          <td style="padding:7px 0;color:#555;">
            Tárgy
          </td>
          <td style="padding:7px 0;">
            <strong>{targy}</strong>
          </td>
        </tr>

        <tr>
          <td style="padding:7px 0;color:#555;">
            Összeg
          </td>
          <td style="padding:7px 0;">
            <strong>{forint(rekord.get("osszeg"))}</strong>
          </td>
        </tr>

        <tr>
          <td style="padding:7px 0;color:#555;">
            Fizetési határidő
          </td>
          <td style="padding:7px 0;">
            <strong>
              {html_escape(str(
                  rekord.get("hatarido")
                  or "ismeretlen"
              ))}
            </strong>
          </td>
        </tr>

        <tr>
          <td style="padding:7px 0;color:#555;">
            Érkezett
          </td>
          <td style="padding:7px 0;">
            {html_escape(str(
                rekord.get("erkezett")
                or ""
            ))}
          </td>
        </tr>

      </table>

      {figyelmeztetes}

      <p style="
          color:#777;
          font-size:13px;
          margin-top:20px;">
        Ha volt PDF-csatolmány az eredeti levélben,
        azt ehhez az értesítőhöz is csatoltuk.
      </p>

    </div>
    """


def uj_meroallas_email_html(rekord):
    szolgaltato = html_escape(
        str(rekord["szolgaltato_nev"])
    )

    targy = html_escape(
        str(rekord["targy"])
    )

    ertek = rekord.get("ertek")

    if ertek:
        ertek_sor = html_escape(str(ertek))

        if rekord.get("mertekegyseg"):
            ertek_sor += (
                " "
                + html_escape(
                    str(rekord["mertekegyseg"])
                )
            )
    else:
        ertek_sor = (
            "ismeretlen – nézd meg az eredeti levelet"
        )

    return f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:560px;
        margin:0 auto;">

      <h2 style="color:#0f766e;">
        🔢 Mérőállással kapcsolatos levél –
        {szolgaltato}
      </h2>

      <table style="
          width:100%;
          border-collapse:collapse;">

        <tr>
          <td style="padding:7px 0;color:#555;">
            Tárgy
          </td>
          <td style="padding:7px 0;">
            <strong>{targy}</strong>
          </td>
        </tr>

        <tr>
          <td style="padding:7px 0;color:#555;">
            Kiolvasott érték
          </td>
          <td style="padding:7px 0;">
            <strong>{ertek_sor}</strong>
          </td>
        </tr>

      </table>

      <p style="
          color:#777;
          font-size:13px;
          margin-top:20px;">
        Ez tájékoztató bejegyzés, nem számla.
      </p>

    </div>
    """


def ismeretlen_email_html(rekord):
    szolgaltato = html_escape(
        str(rekord["szolgaltato_nev"])
    )

    targy = html_escape(
        str(rekord["targy"])
    )

    reszlet = html_escape(
        str(rekord.get("reszlet") or "")
    )

    return f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:600px;
        margin:0 auto;">

      <h2 style="color:#b45309;">
        ❓ Fel nem ismert levél
      </h2>

      <p>
        A figyelt szolgáltatótól ({szolgaltato})
        érkezett egy olyan levél, amelyet a jelenlegi
        felismerő nem tudott biztonságosan besorolni.
      </p>

      <p>
        <strong>Tárgy:</strong> {targy}
      </p>

      <pre style="
          white-space:pre-wrap;
          background:#f9fafb;
          padding:12px;
          border-radius:8px;
          font-family:Arial,sans-serif;
          font-size:13px;">{reszlet}</pre>

    </div>
    """


def ismeretlen_fizetes_email_html(rekord):
    szolgaltato = html_escape(
        str(rekord["szolgaltato_nev"])
    )

    targy = html_escape(
        str(rekord["targy"])
    )

    return f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:560px;
        margin:0 auto;">

      <h2 style="color:#dc2626;">
        ⚠️ Nem azonosítható fizetési visszaigazolás
      </h2>

      <p>
        Fizetési visszaigazolás érkezett a
        <strong>{szolgaltato}</strong> szolgáltatótól,
        de a program nem talált olyan számlát, amelyet
        biztonságosan ehhez lehetne rendelni.
      </p>

      <p>
        <strong>Tárgy:</strong> {targy}
      </p>

      <p>
        A program szándékosan <strong>nem</strong> jelölt
        találomra egy számlát fizetettnek.
      </p>

    </div>
    """


def osszesito_email_html(
    fizetetlen_lista,
    vegosszeg,
    provider_osszegek,
):
    sorok = ""

    for rekord in fizetetlen_lista:
        hatarido = rekord.get("hatarido")

        lejart = bool(
            hatarido
            and hatarido < magyar_ma().isoformat()
        )

        szin = (
            "#dc2626"
            if lejart
            else "#111827"
        )

        szolgaltato = html_escape(
            str(rekord["szolgaltato_nev"])
        )

        targy = html_escape(
            str(rekord["targy"])
        )

        hatarido_html = html_escape(
            str(hatarido or "ismeretlen")
        )

        sorok += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">
            {szolgaltato}
          </td>

          <td style="padding:8px;border-bottom:1px solid #eee;">
            {targy}
          </td>

          <td style="
              padding:8px;
              border-bottom:1px solid #eee;
              text-align:right;">
            {forint(rekord.get("osszeg"))}
          </td>

          <td style="
              padding:8px;
              border-bottom:1px solid #eee;
              color:{szin};">
            {hatarido_html}
            {" ⏰ LEJÁRT" if lejart else ""}
          </td>
        </tr>
        """

    provider_sorok = "".join(
        f"""
        <li>
          {html_escape(str(nev))}:
          <strong>{forint(osszeg)}</strong>
        </li>
        """
        for nev, osszeg
        in provider_osszegek.items()
    )

    return f"""
    <div style="
        font-family:Arial,sans-serif;
        max-width:700px;
        margin:0 auto;">

      <h2 style="color:#b91c1c;">
        💰 Fizetetlen számlák összesítője
      </h2>

      <p>
        Az alábbi számlák még nincsenek fizetettként
        nyilvántartva, és legalább egy határideje
        {SZAMLA_EMLEKEZTETO_NAPOK_ELOTTE} napon belül
        esedékes vagy már lejárt.
      </p>

      <table style="
          width:100%;
          border-collapse:collapse;
          font-size:14px;">

        <tr style="background:#f3f4f6;">
          <th style="padding:8px;text-align:left;">
            Szolgáltató
          </th>

          <th style="padding:8px;text-align:left;">
            Számla
          </th>

          <th style="padding:8px;text-align:right;">
            Összeg
          </th>

          <th style="padding:8px;text-align:left;">
            Határidő
          </th>
        </tr>

        {sorok}

      </table>

      <h3 style="margin-top:24px;">
        Szolgáltatónkénti bontás
      </h3>

      <ul>
        {provider_sorok}
      </ul>

      <p style="
          font-size:20px;
          margin-top:20px;">
        <strong>
          Végösszeg: {forint(vegosszeg)}
        </strong>
      </p>

      <p style="
          color:#777;
          font-size:13px;
          margin-top:20px;">
        Ahol lehetséges volt, a PDF-eket friss IMAP-lekérdezéssel
        csatoltuk az emailhez.
      </p>

    </div>
    """


# ════════════════════════════════════════════════════════════════
# REKORDOK
# ════════════════════════════════════════════════════════════════

def rekord_id(uid_str, tipus):
    return hashlib.sha256(
        f"{uid_str}|{tipus}".encode("utf-8")
    ).hexdigest()[:20]


def dijnet_rekord_id(
    szolgaltato,
    szamlaszam,
):
    return hashlib.sha256(
        f"dijnet|{szolgaltato}|{szamlaszam}"
        .encode("utf-8")
    ).hexdigest()[:20]


# ════════════════════════════════════════════════════════════════
# DÍJNET
# ════════════════════════════════════════════════════════════════

DIJNET_BASE = "https://www.dijnet.hu"

DIJNET_FIZETVE_KULCSSZAVAK = (
    "rendezett",
    "fizetve",
)


def dijnet_bejelentkezes():
    if not (
        DIJNET_USER
        and DIJNET_JELSZO
    ):
        return None

    session = requests.Session()

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; SzamlaFigyelo/2.0)"
        )
    })

    try:
        session.get(
            DIJNET_BASE + "/",
            timeout=15,
        )

        valasz = session.post(
            DIJNET_BASE
            + "/ekonto/login/login_check_ajax",
            data={
                "username": DIJNET_USER,
                "password": DIJNET_JELSZO,
            },
            timeout=15,
        )

        try:
            adat = valasz.json()
        except Exception:
            log(
                "  ⚠️ Díjnet: a bejelentkezési válasz "
                "nem JSON."
            )
            return None

        if not adat.get("success"):
            log(
                "  ⚠️ Díjnet: bejelentkezés sikertelen."
            )
            debug(f"Díjnet login válasz: {adat}")
            return None

        log("  ✅ Díjnet: bejelentkezés sikeres.")

        return session

    except Exception as e:
        log(
            f"  ⚠️ Díjnet bejelentkezési hiba: {e}"
        )
        return None


def _dijnet_vfw_token(session):
    try:
        session.get(
            DIJNET_BASE
            + "/ekonto/control/main",
            timeout=15,
        )

        valasz = session.get(
            DIJNET_BASE
            + "/ekonto/control/szamla_search",
            timeout=15,
        )

        valasz.encoding = "iso-8859-2"

        soup = BeautifulSoup(
            valasz.text,
            "lxml",
        )

        mezo = soup.select_one(
            'input[name="vfw_token"]'
        )

        if mezo:
            return mezo.get("value")

        input_nevek = [
            i.get("name")
            for i in soup.find_all("input")
            if i.get("name")
        ]

        debug(
            "Díjnet: nincs vfw_token; "
            f"URL={valasz.url}; "
            f"status={valasz.status_code}; "
            f"inputok={input_nevek}"
        )

        return None

    except Exception as e:
        log(
            f"  ⚠️ Díjnet token lekérése sikertelen: {e}"
        )
        return None


def _dijnet_datum_konvertalas(nyers):
    if not nyers:
        return None

    talalat = re.search(
        r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})",
        str(nyers),
    )

    if talalat:
        ev, ho, nap = talalat.groups()

        return _datum_ellenorzes(
            ev,
            ho,
            nap,
        )

    # 15.09.2026
    talalat = re.search(
        r"(\d{1,2})\D+(\d{1,2})\D+(\d{4})",
        str(nyers),
    )

    if talalat:
        nap, ho, ev = talalat.groups()

        return _datum_ellenorzes(
            ev,
            ho,
            nap,
        )

    return None


def _dijnet_osszeg_konvertalas(nyers):
    if not nyers:
        return None

    szoveg = str(nyers).strip()

    # Csak számokat, pontot, vesszőt, szóközt hagyunk.
    szoveg = re.sub(
        r"[^0-9,.\-\s]",
        "",
        szoveg,
    ).strip()

    if not szoveg:
        return None

    # Magyar formátum.
    if "," in szoveg:
        szoveg = (
            szoveg
            .replace(" ", "")
            .replace(".", "")
            .replace(",", ".")
        )
    else:
        szoveg = szoveg.replace(" ", "")

        if re.fullmatch(
            r"\d{1,3}(?:\.\d{3})+",
            szoveg,
        ):
            szoveg = szoveg.replace(
                ".",
                "",
            )

    try:
        return float(szoveg)
    except ValueError:
        return None


def _dijnet_allapot_fizetett(allapot):
    allapot = normalizalt_kisbetus(
        allapot
    )

    if not allapot:
        return False

    return any(
        re.search(
            rf"\b{re.escape(kulcs)}\b",
            allapot,
        )
        for kulcs in DIJNET_FIZETVE_KULCSSZAVAK
    )


def dijnet_szamlak_lekerdezese(
    session,
    napok_vissza=DIJNET_LEKERDEZES_NAPOK_VISSZA,
):
    nap_ig = magyar_ma()
    naptol = (
        nap_ig
        - timedelta(days=napok_vissza)
    )

    token = _dijnet_vfw_token(session)

    if not token:
        log(
            "  ⚠️ Díjnet: vfw_token nem található."
        )

    adatok = {
        "vfw_form": "szamla_search_submit",
        "vfw_coll": "szamla_search_params",
        "vfw_token": token or "",
        "szlaszolgnev": "",
        "regszolgid": "",
        "datumtol": naptol.strftime(
            "%Y.%m.%d"
        ),
        "datumig": nap_ig.strftime(
            "%Y.%m.%d"
        ),
    }

    try:
        valasz = session.post(
            DIJNET_BASE
            + "/ekonto/control/"
            + "szamla_search_submit",
            data=adatok,
            timeout=25,
        )

        valasz.encoding = "iso-8859-2"

        soup = BeautifulSoup(
            valasz.text,
            "lxml",
        )

    except Exception as e:
        log(
            f"  ⚠️ Díjnet számlakeresési hiba: {e}"
        )
        return []

    sorok = soup.select(
        "table.table tr"
    )

    if not sorok:
        log(
            "  ⚠️ Díjnet: nem találtam "
            "feldolgozható táblázatsorokat."
        )

        debug(
            f"status={valasz.status_code}; "
            f"url={valasz.url}; "
            f"table={len(soup.find_all('table'))}; "
            f"tr={len(soup.find_all('tr'))}"
        )

        return []

    talalt = []

    for idx, sor in enumerate(sorok):
        cellak = sor.find_all("td")

        if len(cellak) < 9:
            continue

        szoveg = [
            norm_szoveg(
                c.get_text(" ", strip=True)
            )
            for c in cellak
        ]

        try:
            szolgaltato = szoveg[1]
            megjelenitett_nev = (
                szoveg[2]
                or szolgaltato
            )
            szamlaszam = szoveg[3]
            kiallitas = szoveg[4]
            hatarido = szoveg[6]
            osszeg = szoveg[7]
            allapot = szoveg[8]

        except IndexError:
            debug(
                f"Díjnet nem várt sor: {szoveg}"
            )
            continue

        # Biztonsági validáció.
        if not szamlaszam:
            debug(
                f"Díjnet sor {idx}: nincs számlaszám."
            )
            continue

        parsed_osszeg = (
            _dijnet_osszeg_konvertalas(
                osszeg
            )
        )

        parsed_hatarido = (
            _dijnet_datum_konvertalas(
                hatarido
            )
        )

        parsed_kiallitas = (
            _dijnet_datum_konvertalas(
                kiallitas
            )
        )

        if parsed_osszeg is None:
            debug(
                f"Díjnet sor {idx}: "
                f"értelmezhetetlen összeg: {osszeg!r}"
            )

        if parsed_hatarido is None:
            debug(
                f"Díjnet sor {idx}: "
                f"értelmezhetetlen határidő: {hatarido!r}"
            )

        talalt.append({
            "sor_index": idx,
            "szolgaltato_nyers": szolgaltato,
            "megjelenitett_nev": megjelenitett_nev,
            "szamlaszam": szamlaszam,
            "kiallitas_nyers": kiallitas,
            "hatarido_nyers": hatarido,
            "osszeg_nyers": osszeg,
            "allapot_szoveg": allapot,
            "osszeg": parsed_osszeg,
            "hatarido": parsed_hatarido,
            "kiallitas": parsed_kiallitas,
        })

    log(
        f"  🧾 Díjnet: {len(talalt)} számla-sor."
    )

    return talalt


def dijnet_pdf_letoltese(
    session,
    sor_index,
):
    try:
        session.get(
            DIJNET_BASE
            + "/ekonto/control/"
            + "szamla_select",
            params={
                "vfw_coll": "szamla_list",
                "vfw_rowid": sor_index,
                "exp": "K",
            },
            timeout=15,
        )

        valasz = session.get(
            DIJNET_BASE
            + "/ekonto/control/"
            + "szamla_letolt",
            timeout=15,
        )

        valasz.encoding = "iso-8859-2"

        soup = BeautifulSoup(
            valasz.text,
            "lxml",
        )

        link = soup.select_one(
            'a[href*="szamla_pdf"]'
        )

        if not link:
            return None

        href = link.get("href")

        if not href:
            return None

        if href.startswith("http"):
            pdf_url = href
        else:
            pdf_url = (
                DIJNET_BASE
                + "/ekonto/control/"
                + href.lstrip("/")
            )

        pdf_valasz = session.get(
            pdf_url,
            timeout=25,
        )

        if (
            pdf_valasz.status_code == 200
            and pdf_valasz.content
        ):
            # Ne mentsük fájlba.
            return pdf_valasz.content

    except Exception as e:
        debug(
            f"Díjnet PDF-letöltési hiba: {e}"
        )

    return None


# ════════════════════════════════════════════════════════════════
# IMAP EMAIL FELDOLGOZÁS
# ════════════════════════════════════════════════════════════════

def feldolgoz_fizetesi_visszaigazolast(
    szamlak,
    ismeretlen_fizetesek,
    szolgaltato,
    cfg,
    targy,
    teljes_szoveg,
    uid_str,
    stat,
):
    fizetett_osszeg = osszeg_kinyerese(
        teljes_szoveg
    )

    jeloltek = [
        (rid, rekord)
        for rid, rekord in szamlak.items()
        if rekord.get("szolgaltato")
        == szolgaltato
        and not rekord.get("fizetve", False)
    ]

    talalat = None

    # Elsődleges: összeg + szolgáltató.
    if fizetett_osszeg is not None:
        egyezesek = []

        for rid, rekord in jeloltek:
            rekord_osszeg = rekord.get(
                "osszeg"
            )

            if rekord_osszeg is None:
                continue

            if abs(
                rekord_osszeg
                - fizetett_osszeg
            ) < 0.01:
                egyezesek.append(
                    (rid, rekord)
                )

        # Csak akkor automatikus, ha pontosan egy egyezés van.
        if len(egyezesek) == 1:
            talalat = egyezesek[0][0]

        elif len(egyezesek) > 1:
            # Ha több azonos összegű számla van,
            # ne találgassunk.
            debug(
                "Több azonos összegű számla "
                "található; nincs automatikus "
                "hozzárendelés."
            )

    # NINCS többé:
    # "ha nincs találat, jelöljük a legrégebbit fizetettnek"

    if talalat:
        rekord = szamlak[talalat]

        rekord["fizetve"] = True
        rekord["fizetve_datum"] = (
            magyar_ido().isoformat()
        )

        stat["fizetve"] += 1

        log(
            "      ✅ Fizetettre állítva: "
            f"{cfg['nev']} / "
            f"{rekord['targy'][:60]}"
        )

        return

    # Nem biztonságosan hozzárendelhető.
    iid = hashlib.sha256(
        f"{uid_str}|ismeretlen_fizetes"
        .encode("utf-8")
    ).hexdigest()[:20]

    if iid not in ismeretlen_fizetesek:
        rekord = {
            "szolgaltato": szolgaltato,
            "szolgaltato_nev": cfg["nev"],
            "targy": targy,
            "erkezett": magyar_ido().isoformat(),
            "uid": uid_str,
            "osszeg": fizetett_osszeg,
        }

        ismeretlen_fizetesek[iid] = rekord

        stat["ismeretlen_fizetes"] += 1

        log(
            "      ⚠️ Fizetési visszaigazolás "
            "nem rendelhető biztonságosan "
            "számlához."
        )

        if ISMERETLEN_FIZETES_ERTESITES_EMAIL:
            email_kuldes(
                f"⚠️ Nem azonosítható fizetés – "
                f"{cfg['nev']}",
                ismeretlen_fizetes_email_html(
                    rekord
                ),
            )


def feldolgoz_meroallast(
    meroallasok,
    szolgaltato,
    cfg,
    targy,
    erkezett,
    erkezett_fejlec,
    teljes_szoveg,
    uid_str,
    stat,
):
    mid = rekord_id(
        uid_str,
        "meroallas",
    )

    if mid in meroallasok:
        return

    ertek_info = (
        meroallas_ertek_kinyerese(
            teljes_szoveg
        )
        or {}
    )

    rekord = {
        "szolgaltato": szolgaltato,
        "szolgaltato_nev": cfg["nev"],
        "targy": targy,
        "erkezett": erkezett,
        "erkezett_fejlec": erkezett_fejlec,
        "ertek": ertek_info.get(
            "ertek"
        ),
        "mertekegyseg": ertek_info.get(
            "mertekegyseg"
        ),
        "uid": uid_str,
    }

    meroallasok[mid] = rekord

    stat["meroallas"] += 1

    log(
        f"      🔢 Mérőállás: "
        f"{cfg['nev']} – "
        f"{targy[:60]}"
    )

    if MEROALLAS_ERTESITES_EMAIL:
        email_kuldes(
            f"🔢 Mérőállás – {cfg['nev']}",
            uj_meroallas_email_html(
                rekord
            ),
        )


def feldolgoz_uj_szamlat(
    szamlak,
    szolgaltato,
    cfg,
    targy,
    erkezett,
    erkezett_fejlec,
    szoveg,
    pdf_szoveg,
    pdf_nev,
    pdf_bytes,
    uid_str,
    stat,
):
    rid = rekord_id(
        uid_str,
        "uj_szamla",
    )

    if rid in szamlak:
        return

    teljes_szoveg = norm_szoveg(
        f"{szoveg}\n{pdf_szoveg}"
    )

    osszeg = osszeg_kinyerese(
        szoveg
    )

    hatarido = hatarido_kinyerese(
        szoveg
    )

    if osszeg is None:
        osszeg = osszeg_kinyerese(
            pdf_szoveg
        )

    if hatarido is None:
        hatarido = hatarido_kinyerese(
            pdf_szoveg
        )

    rekord = {
        "szolgaltato": szolgaltato,
        "szolgaltato_nev": cfg["nev"],
        "targy": targy,
        "erkezett": erkezett,
        "erkezett_fejlec": erkezett_fejlec,
        "osszeg": osszeg,
        "hatarido": hatarido,
        "fizetve": False,
        "fizetve_datum": None,
        "uid": uid_str,
        "forras": "imap",
    }

    szamlak[rid] = rekord

    stat["uj_szamla"] += 1

    log(
        f"      🆕 Új számla: "
        f"{cfg['nev']} – "
        f"{forint(osszeg)} – "
        f"határidő: {hatarido}"
    )

    email_kuldes(
        f"📄 Új számla – {cfg['nev']}",
        uj_szamla_email_html(
            rekord
        ),
        (
            [
                (
                    pdf_nev
                    or "szamla.pdf",
                    pdf_bytes,
                )
            ]
            if pdf_bytes
            else None
        ),
    )


def feldolgoz_ismeretlent(
    ismeretlen_dokumentumok,
    szolgaltato,
    cfg,
    targy,
    erkezett,
    erkezett_fejlec,
    teljes_szoveg,
    uid_str,
    stat,
):
    iid = rekord_id(
        uid_str,
        "ismeretlen",
    )

    if iid in ismeretlen_dokumentumok:
        return

    reszlet = re.sub(
        r"\s+",
        " ",
        teljes_szoveg.strip(),
    )[:600]

    rekord = {
        "szolgaltato": szolgaltato,
        "szolgaltato_nev": cfg["nev"],
        "targy": targy,
        "erkezett": erkezett,
        "erkezett_fejlec": erkezett_fejlec,
        "reszlet": reszlet,
        "uid": uid_str,
    }

    ismeretlen_dokumentumok[iid] = rekord

    stat["ismeretlen"] += 1

    log(
        f"      ❓ Ismeretlen levél: "
        f"{cfg['nev']} – "
        f"{targy[:60]}"
    )

    if ISMERETLEN_ERTESITES_EMAIL:
        email_kuldes(
            f"❓ Fel nem ismert levél – "
            f"{cfg['nev']}",
            ismeretlen_email_html(
                rekord
            ),
        )


# ════════════════════════════════════════════════════════════════
# DÍJNET FELDOLGOZÁS
# ════════════════════════════════════════════════════════════════

def feldolgoz_dijnet(
    szamlak,
    stat,
):
    if not (
        DIJNET_USER
        and DIJNET_JELSZO
    ):
        log(
            "  ℹ️ Díjnet: nincs konfigurálva."
        )
        return

    session = dijnet_bejelentkezes()

    if not session:
        return

    try:
        sorok = dijnet_szamlak_lekerdezese(
            session
        )

        pdf_letoltesek = 0

        for sor in sorok:
            szolgaltato_nyers = (
                sor["szolgaltato_nyers"]
            )

            szamlaszam = (
                sor["szamlaszam"]
            )

            did = dijnet_rekord_id(
                szolgaltato_nyers,
                szamlaszam,
            )

            fizetve = (
                _dijnet_allapot_fizetett(
                    sor["allapot_szoveg"]
                )
            )

            osszeg = sor.get(
                "osszeg"
            )

            hatarido = sor.get(
                "hatarido"
            )

            kiallitas = sor.get(
                "kiallitas"
            )

            if did in szamlak:
                rekord = szamlak[did]

                # Díjnet a hitelesebb állapotforrás.
                if fizetve and not rekord.get(
                    "fizetve",
                    False,
                ):
                    rekord["fizetve"] = True
                    rekord["fizetve_datum"] = (
                        magyar_ido().isoformat()
                    )

                    stat["fizetve"] += 1

                    log(
                        "      ✅ Díjnet: fizetettre állítva – "
                        f"{szamlaszam}"
                    )

                if osszeg is not None:
                    rekord["osszeg"] = osszeg

                if hatarido is not None:
                    rekord["hatarido"] = hatarido

                continue

            # Új Díjnet-számla.
            pdf_bytes = None

            if (
                not fizetve
                and pdf_letoltesek
                < DIJNET_MAX_PDF_LETOLTES_FUTASONKENT
            ):
                pdf_bytes = (
                    dijnet_pdf_letoltese(
                        session,
                        sor["sor_index"],
                    )
                )

                pdf_letoltesek += 1

            rekord = {
                "szolgaltato": "dijnet",
                "szolgaltato_nev": (
                    f"{sor['megjelenitett_nev']} "
                    f"(Díjnet)"
                ),
                "targy": (
                    f"Számla – {szamlaszam}"
                ),
                "erkezett": (
                    kiallitas
                    or magyar_ido().isoformat()
                ),
                "erkezett_fejlec": None,
                "osszeg": osszeg,
                "hatarido": hatarido,
                "fizetve": fizetve,
                "fizetve_datum": (
                    magyar_ido().isoformat()
                    if fizetve
                    else None
                ),
                "uid": None,
                "forras": "dijnet_portal",
                "szamlaszam": szamlaszam,
            }

            szamlak[did] = rekord

            stat["dijnet_uj"] += 1

            log(
                "      🆕 Új Díjnet-számla: "
                f"{rekord['szolgaltato_nev']} – "
                f"{forint(osszeg)} – "
                f"határidő: {hatarido}"
            )

            # Már fizetett számláról nem küldünk új számla-riasztást.
            if not fizetve:
                email_kuldes(
                    f"📄 Új számla – "
                    f"{rekord['szolgaltato_nev']}",
                    uj_szamla_email_html(
                        rekord
                    ),
                    (
                        [
                            (
                                f"{szamlaszam}.pdf",
                                pdf_bytes,
                            )
                        ]
                        if pdf_bytes
                        else None
                    ),
                )

    except Exception as e:
        log(
            f"  ⚠️ Díjnet feldolgozási hiba: {e}"
        )


# ════════════════════════════════════════════════════════════════
# IMAP FELDOLGOZÁS
# ════════════════════════════════════════════════════════════════

def feldolgoz_imap(
    allapot,
    stat,
):
    szamlak = allapot.setdefault(
        "szamlak",
        {},
    )

    meroallasok = allapot.setdefault(
        "meroallasok",
        {},
    )

    ismeretlen_dokumentumok = (
        allapot.setdefault(
            "ismeretlen_dokumentumok",
            {},
        )
    )

    ismeretlen_fizetesek = (
        allapot.setdefault(
            "ismeretlen_fizetesek",
            {},
        )
    )

    feldolgozott_uidok = set(
        allapot.setdefault(
            "feldolgozott_uidok",
            [],
        )
    )

    conn = None

    try:
        conn = imap_kapcsolat()

        aktualis_uidvalidity = (
            imap_uidvalidity(conn)
        )

        regi_uidvalidity = (
            allapot.get(
                "imap_uidvalidity"
            )
        )

        if (
            regi_uidvalidity
            and aktualis_uidvalidity
            and regi_uidvalidity
            != aktualis_uidvalidity
        ):
            log(
                "  ⚠️ IMAP UIDVALIDITY megváltozott. "
                "A korábbi UID checkpointot töröljük."
            )

            feldolgozott_uidok.clear()

        if aktualis_uidvalidity:
            allapot[
                "imap_uidvalidity"
            ] = aktualis_uidvalidity

        uj_uidok = uj_uidok_lekerese(
            conn,
            feldolgozott_uidok,
        )

        log(
            f"📬 {len(uj_uidok)} új/feldolgozatlan "
            "email."
        )

        for uid in uj_uidok:
            uid_str = uid.decode(
                "ascii",
                errors="ignore",
            )

            # FONTOS:
            # feldolgozottnak csak akkor tekintjük,
            # ha ténylegesen végigmentünk rajta.
            msg = uid_letoltese(
                conn,
                uid,
            )

            if msg is None:
                log(
                    f"  ⚠️ UID {uid_str}: "
                    "nem tölthető le."
                )
                continue

            feldolgozott_uidok.add(
                uid_str
            )

            stat["email"] += 1

            felado = _felado_cim(msg)

            szolgaltato = (
                szolgaltato_azonositasa(
                    felado
                )
            )

            if not szolgaltato:
                stat["nem_relevans"] += 1
                continue

            cfg = SZOLGALTATOK[
                szolgaltato
            ]

            targy = _fejlec_dekodolas(
                msg.get("Subject", "")
            )

            erkezett = (
                email_erkezesi_ido(msg)
                or magyar_ido().isoformat()
            )

            erkezett_fejlec = (
                msg.get("Date", "")
            )

            szoveg = (
                email_szoveg_kinyerese(
                    msg
                )
            )

            pdf_nev, pdf_bytes = (
                pdf_csatolmany(msg)
            )

            tipus = (
                tartalom_tipus_azonositas(
                    targy,
                    szoveg,
                )
            )

            pdf_szoveg = ""

            # Csak akkor olvassuk a PDF-et,
            # ha az emailből még nem tudtuk azonosítani.
            if (
                tipus == "ismeretlen"
                and pdf_bytes
            ):
                pdf_szoveg = (
                    pdf_szoveg_kinyerese(
                        pdf_bytes
                    )
                )

                tipus = (
                    tartalom_tipus_azonositas(
                        targy,
                        f"{szoveg}\n"
                        f"{pdf_szoveg}",
                    )
                )

            teljes_szoveg = norm_szoveg(
                f"{szoveg}\n"
                f"{pdf_szoveg}"
            )

            debug(
                f"UID={uid_str}; "
                f"szolgáltató={szolgaltato}; "
                f"típus={tipus}; "
                f"tárgy={targy[:80]!r}"
            )

            if tipus == "fizetve":
                feldolgoz_fizetesi_visszaigazolast(
                    szamlak,
                    ismeretlen_fizetesek,
                    szolgaltato,
                    cfg,
                    targy,
                    teljes_szoveg,
                    uid_str,
                    stat,
                )
                continue

            if tipus == "fizetesi_emlekezteto":
                stat[
                    "emlekezteto"
                ] += 1

                log(
                    f"      ℹ️ Fizetési emlékeztető – "
                    f"{cfg['nev']} "
                    "(nem hoz létre új számlát)"
                )
                continue

            if tipus == "meroallas":
                feldolgoz_meroallast(
                    meroallasok,
                    szolgaltato,
                    cfg,
                    targy,
                    erkezett,
                    erkezett_fejlec,
                    teljes_szoveg,
                    uid_str,
                    stat,
                )
                continue

            if tipus == "uj_szamla":
                feldolgoz_uj_szamlat(
                    szamlak,
                    szolgaltato,
                    cfg,
                    targy,
                    erkezett,
                    erkezett_fejlec,
                    szoveg,
                    pdf_szoveg,
                    pdf_nev,
                    pdf_bytes,
                    uid_str,
                    stat,
                )
                continue

            feldolgoz_ismeretlent(
                ismeretlen_dokumentumok,
                szolgaltato,
                cfg,
                targy,
                erkezett,
                erkezett_fejlec,
                teljes_szoveg,
                uid_str,
                stat,
            )

    finally:
        if conn is not None:
            try:
                conn.logout()
            except Exception:
                pass

    # UID-k maximuma.
    try:
        rendezett_uidok = sorted(
            feldolgozott_uidok,
            key=lambda x: int(x),
        )
    except Exception:
        rendezett_uidok = list(
            feldolgozott_uidok
        )

    allapot[
        "feldolgozott_uidok"
    ] = rendezett_uidok[-5000:]


# ════════════════════════════════════════════════════════════════
# NAPI ÖSSZESÍTŐ
# ════════════════════════════════════════════════════════════════

def osszesito_feldolgozasa(
    allapot,
    stat,
):
    szamlak = allapot.get(
        "szamlak",
        {},
    )

    if not szamlak:
        return

    ma = magyar_ma()

    ma_str = ma.isoformat()

    kuszob = (
        ma
        + timedelta(
            days=SZAMLA_EMLEKEZTETO_NAPOK_ELOTTE
        )
    ).isoformat()

    fizetetlen = [
        r
        for r in szamlak.values()
        if not r.get(
            "fizetve",
            False,
        )
    ]

    figyelmeztetendo = [
        r
        for r in fizetetlen
        if r.get("hatarido")
        and r["hatarido"] <= kuszob
    ]

    if not figyelmeztetendo:
        return

    if (
        allapot.get(
            "utolso_emlekezteto_nap"
        )
        == ma_str
    ):
        return

    vegosszeg = sum(
        (
            r.get("osszeg")
            or 0
        )
        for r in fizetetlen
    )

    provider_osszegek = {}

    for rekord in fizetetlen:
        nev = rekord[
            "szolgaltato_nev"
        ]

        provider_osszegek[nev] = (
            provider_osszegek.get(
                nev,
                0,
            )
            + (
                rekord.get(
                    "osszeg"
                )
                or 0
            )
        )

    csatolmanyok = []

    # Csak IMAP-os rekordoknak van UID-ja.
    # Díjnet PDF-et itt nem próbálunk visszaszerezni,
    # mert az eredeti portál-session már lezárult.
    try:
        conn = imap_kapcsolat()

        for rekord in fizetetlen:
            uid = rekord.get("uid")

            if not uid:
                continue

            msg = uid_letoltese(
                conn,
                uid.encode("ascii"),
            )

            if msg is None:
                continue

            pdf_nev, pdf_bytes = (
                pdf_csatolmany(msg)
            )

            if pdf_bytes:
                csatolmanyok.append(
                    (
                        pdf_nev
                        or (
                            f"{rekord['szolgaltato']}"
                            "_szamla.pdf"
                        ),
                        pdf_bytes,
                    )
                )

        conn.logout()

    except Exception as e:
        log(
            f"  ⚠️ Összesítő PDF-ek "
            f"visszatöltése sikertelen: {e}"
        )

    email_kuldes(
        (
            f"💰 Fizetetlen számlák – "
            f"{len(fizetetlen)} db – "
            f"{forint(vegosszeg)}"
        ),
        osszesito_email_html(
            fizetetlen,
            vegosszeg,
            provider_osszegek,
        ),
        csatolmanyok,
    )

    allapot[
        "utolso_emlekezteto_nap"
    ] = ma_str

    stat[
        "osszesito"
    ] = True


# ════════════════════════════════════════════════════════════════
# ÁLLAPOT TAKARÍTÁSA
# ════════════════════════════════════════════════════════════════

def allapot_takaritasa(allapot):
    """
    A naplók ne nőjenek a végtelenségig.

    A számlákat nem töröljük automatikusan.
    """

    meroallasok = allapot.get(
        "meroallasok",
        {},
    )

    if len(meroallasok) > 500:
        rendezett = sorted(
            meroallasok.items(),
            key=lambda x: x[1].get(
                "erkezett",
                "",
            ),
        )

        allapot[
            "meroallasok"
        ] = dict(
            rendezett[-500:]
        )

    ismeretlenek = allapot.get(
        "ismeretlen_dokumentumok",
        {},
    )

    if len(ismeretlenek) > 300:
        rendezett = sorted(
            ismeretlenek.items(),
            key=lambda x: x[1].get(
                "erkezett",
                "",
            ),
        )

        allapot[
            "ismeretlen_dokumentumok"
        ] = dict(
            rendezett[-300:]
        )

    ismeretlen_fizetesek = allapot.get(
        "ismeretlen_fizetesek",
        {},
    )

    if len(ismeretlen_fizetesek) > 200:
        rendezett = sorted(
            ismeretlen_fizetesek.items(),
            key=lambda x: x[1].get(
                "erkezett",
                "",
            ),
        )

        allapot[
            "ismeretlen_fizetesek"
        ] = dict(
            rendezett[-200:]
        )


# ════════════════════════════════════════════════════════════════
# STATISZTIKA
# ════════════════════════════════════════════════════════════════

def statisztika_kiirasa(
    stat,
    allapot,
):
    log("")
    log("📊 FUTÁSI ÖSSZESÍTŐ")
    log("────────────────────────────────")

    log(
        f"  Email feldolgozva:      "
        f"{stat['email']}"
    )

    log(
        f"  Nem releváns email:     "
        f"{stat['nem_relevans']}"
    )

    log(
        f"  Új számla:              "
        f"{stat['uj_szamla']}"
    )

    log(
        f"  Fizetettként frissítve: "
        f"{stat['fizetve']}"
    )

    log(
        f"  Fizetési emlékeztető:   "
        f"{stat['emlekezteto']}"
    )

    log(
        f"  Mérőállás:              "
        f"{stat['meroallas']}"
    )

    log(
        f"  Ismeretlen levél:       "
        f"{stat['ismeretlen']}"
    )

    log(
        f"  Ismeretlen fizetés:     "
        f"{stat['ismeretlen_fizetes']}"
    )

    log(
        f"  Új Díjnet-számla:       "
        f"{stat['dijnet_uj']}"
    )

    log(
        f"  Napi összesítő:         "
        f"{'igen' if stat['osszesito'] else 'nem'}"
    )

    log(
        f"  Nyilvántartott számla:  "
        f"{len(allapot.get('szamlak', {}))}"
    )

    log(
        f"  Fizetetlen számla:      "
        f"{sum("
        f"1 for r in allapot.get('szamlak', {}).values()"
        f" if not r.get('fizetve', False)"
        f")}"
    )

    log(
        f"  DRY-RUN:                "
        f"{'igen' if DRY_RUN else 'nem'}"
    )

    log("────────────────────────────────")


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    log("")
    log(
        "💰 SZÁMLA FIGYELŐ – "
        + magyar_ido().strftime(
            "%Y.%m.%d %H:%M:%S"
        )
    )

    if DRY_RUN:
        log(
            "🧪 DRY-RUN mód aktív – "
            "email nem kerül kiküldésre."
        )

    # ─────────────────────────────────────────────
    # Kötelező konfigurációk
    # ─────────────────────────────────────────────

    if not TITKOSITAS_JELSZO:
        log(
            "❌ Nincs "
            "SZAMLA_TITKOSITAS_JELSZO."
        )
        log(
            "   Biztonsági okból leállás."
        )
        return

    if not (
        IMAP_USER
        and IMAP_JELSZO
    ):
        log(
            "❌ Nincs "
            "SZAMLA_IMAP_USER / "
            "SZAMLA_IMAP_JELSZO."
        )
        return

    # ─────────────────────────────────────────────
    # Állapot betöltése
    # ─────────────────────────────────────────────

    try:
        allapot = visszafejt(
            TITKOSITAS_JELSZO,
            ALLAPOT_FAJL,
        )

    except Exception as e:
        log(
            f"❌ Állapot betöltési hiba: {e}"
        )
        return

    stat = {
        "email": 0,
        "nem_relevans": 0,
        "uj_szamla": 0,
        "fizetve": 0,
        "emlekezteto": 0,
        "meroallas": 0,
        "ismeretlen": 0,
        "ismeretlen_fizetes": 0,
        "dijnet_uj": 0,
        "osszesito": False,
    }

    # ─────────────────────────────────────────────
    # 1. IMAP
    # ─────────────────────────────────────────────

    try:
        feldolgoz_imap(
            allapot,
            stat,
        )

    except Exception as e:
        log(
            f"❌ IMAP feldolgozási hiba: {e}"
        )

    # ─────────────────────────────────────────────
    # 2. Díjnet
    # ─────────────────────────────────────────────

    feldolgoz_dijnet(
        allapot.get(
            "szamlak",
            {},
        ),
        stat,
    )

    # ─────────────────────────────────────────────
    # 3. Napi összesítő
    # ─────────────────────────────────────────────

    try:
        osszesito_feldolgozasa(
            allapot,
            stat,
        )

    except Exception as e:
        log(
            f"⚠️ Napi összesítő hiba: {e}"
        )

    # ─────────────────────────────────────────────
    # 4. Állapot takarítása
    # ─────────────────────────────────────────────

    allapot_takaritasa(
        allapot
    )

    # ─────────────────────────────────────────────
    # 5. Titkosított mentés
    # ─────────────────────────────────────────────

    try:
        titkosit_es_ment(
            allapot,
            TITKOSITAS_JELSZO,
            ALLAPOT_FAJL,
        )

        log(
            "💾 Állapot titkosítva elmentve."
        )

    except Exception as e:
        log(
            f"❌ Állapot mentési hiba: {e}"
        )
        return

    # ─────────────────────────────────────────────
    # 6. Statisztika
    # ─────────────────────────────────────────────

    statisztika_kiirasa(
        stat,
        allapot,
    )

    log("")
    log("✅ Kész.")
    log("")


if __name__ == "__main__":
    main()
