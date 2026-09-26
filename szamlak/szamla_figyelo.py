#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SZÁMLA FIGYELŐ
==================================================================
Két forrásból dolgozik:
  1. IMAP-on keresztül figyel egy dedikált email-postafiókot (vagy egy
     meglévő postafiók egy külön mappáját/címkéjét), és a Vízművek és
     MVM leveleit dolgozza fel.
  2. A Díjnet-számlákat NEM emailből, hanem közvetlenül a dijnet.hu
     portálról olvassa ki, bejelentkezve (ld. lentebb a "DÍJNET -
     KÖZVETLEN PORTÁL-LEKÉRDEZÉS" szekciót) - ez megbízhatóbb, mert nem
     attól függ, küld-e egyáltalán emailt a Díjnet.

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
  SZAMLA_DIJNET_USER      a dijnet.hu bejelentkezési felhasználóneved (opcionális -
                          ha kihagyod, a Díjnet-lekérdezés egyszerűen kimarad)
  SZAMLA_DIJNET_JELSZO    a dijnet.hu jelszavad (opcionális, ld. fent)
  SZAMLA_VIZMUVEK_USER    a ugyfelszolgalat.vizmuvek.hu bejelentkezési felhasználóneved
                          (opcionális - ha kihagyod, a Vízművek-portál közvetlen
                          lekérdezése egyszerűen kimarad; ld. lentebb a "VÍZMŰVEK -
                          KÖZVETLEN PORTÁL-LEKÉRDEZÉS" szekciót)
  SZAMLA_VIZMUVEK_JELSZO  a ugyfelszolgalat.vizmuvek.hu jelszavad (opcionális, ld. fent)
  SZAMLA_DRIVE_WEBAPP_URL   egy már telepített Google Apps Script Web App URL-je, ami a
                            számla-PDF-eket Drive-mappákba menti (opcionális - ha kihagyod,
                            a Drive-feltöltés egyszerűen kimarad, ld. "GOOGLE DRIVE - PDF-
                            FELTÖLTÉS" szekció)
  SZAMLA_DRIVE_WEBAPP_TOKEN a fenti Web App-on beállított hitelesítő token (opcionális, ld. fent)
  CEGES_IMAP_HOST         a céges számlákra dedikált postafiók IMAP-szervere (pl. mail.sajatdomain.hu -
                          nincs alapérték, mert ez NEM feltétlenül Gmail, ld. "CÉGES SZÁMLÁK" szekció)
  CEGES_IMAP_PORT         (opcionális, alapértelmezett: 993)
  CEGES_IMAP_USER         a céges számlákra dedikált postafiók email-címe
  CEGES_IMAP_JELSZO       a fenti postafiók jelszava (vagy app-jelszava)
  CEGES_IMAP_MAPPA        (opcionális, alapértelmezett: INBOX)
  Mind az öt CÉGES_* opcionális - ha valamelyik hiányzik, a "Céges számlák" modul egyszerűen
  kimarad, minden más (a fő számla-figyelés) változatlanul működik.
  NAV_TECHNIKAI_LOGIN     a NAV Online Számla technikai felhasználó bejelentkezési neve
                          (a NAV honlapján, "Technikai felhasználó létrehozása" menüben kapod)
  NAV_TECHNIKAI_JELSZO    a fenti technikai felhasználó jelszava
  NAV_ALAIRO_KULCS        a technikai felhasználóhoz tartozó "Aláíró kulcs" (signing key) -
                          EZ NEM a cserekulcs, azt itt nem is használjuk, ld. "NAV ONLINE
                          SZÁMLA" szekció kommentje
  NAV_ADOSZAM             a céged 8 jegyű adószáma (a "-" előtti rész, kötőjelek nélkül)
  Mind a négy NAV_* opcionális - ha valamelyik hiányzik, a NAV-összekötés/párosítás egyszerűen
  kimarad (a "Céges számlák" email-alapú begyűjtése ettől függetlenül változatlanul működik).
"""

import os
import re
import io
import json
import time
import base64
import hashlib
import uuid
import calendar
import imaplib
import smtplib
import email as email_lib
from email.header import decode_header, make_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import parsedate_to_datetime
from datetime import date, datetime, timedelta, timezone
from html import escape as _esc
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as _xml_esc

import requests
from bs4 import BeautifulSoup

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

# ── Bérlői körök - RÉGI (visszafelé-kompatibilis) email-cím GitHub
# Secretekben ──
# A Díjneten/Vízműveknél érkező számlákat a felhasználó a dashboardon
# (ld. "Bérlői körök" panel) sorolja be az egyik körbe (a kibocsátó
# azonosítója, ill. a Vízművek esetén az egész fiók alapján) - ld. a
# "BÉRLŐI KÖRÖK" szekciót lentebb.
#
# FONTOS - 3 CÍMZETTI KÖR (könyvelő / bérlő / tulajdonos) BEVEZETÉSE: a
# felhasználó kérésére a bérlői körönként EGY email-cím helyett mostantól
# TÖBB cím is megadható, és ezeket a dashboardról, a TITKOSÍTOTT
# állapotban (allapot["kor_emailek"]) kezeli - ld. "BÉRLŐI KÖRÖK" szekció
# lentebb, _kor_cimzettek(). Ez a két, itt lévő GitHub Secret ("SZAMLA_
# KOR_A_EMAIL"/"SZAMLA_KOR_B_EMAIL") SZÁNDÉKOSAN NEM lett eltávolítva -
# amíg valaki be van állítva itt, a hozzá tartozó kör küldésénél az ÚJ,
# titkosított listával EGYÜTT, UNIÓBAN kapja meg az emailt (ld.
# _kor_cimzettek() kommentjét) - ez a visszafelé-kompatibilitás miatt
# kell, hogy egy már működő beállítás az átállás alatt ne "némuljon el"
# csendben. Új beállításnál a dashboard listás mezője az elsődleges út.
KOR_EMAIL_CIMEK = {
    "kor_a": os.environ.get("SZAMLA_KOR_A_EMAIL", "").strip(),
    "kor_b": os.environ.get("SZAMLA_KOR_B_EMAIL", "").strip(),
}

TITKOSITAS_JELSZO = os.environ.get("SZAMLA_TITKOSITAS_JELSZO", "")

# Díjnet - közvetlen portál-bejelentkezéshez (nem email-alapú, ld. lentebb).
# Ha ezt a kettőt nem állítod be, a Díjnet-lekérdezés egyszerűen kimarad,
# minden más (Vízművek/MVM email-figyelés) változatlanul működik.
DIJNET_USER = os.environ.get("SZAMLA_DIJNET_USER") or ""
DIJNET_JELSZO = os.environ.get("SZAMLA_DIJNET_JELSZO") or ""
# Hány napra visszamenőleg kérdezze le a Díjnet-számlákat minden futáskor.
# Ez szándékosan egy mozgó ablak (nem "csak az újakat" nézzük) - így a
# már ismert, még fizetetlen számláknak az esetleges fizetve-állapot-
# váltását is elkapja, nem csak a vadonatúj számlákat.
DIJNET_LEKERDEZES_NAPOK_VISSZA = 120
# Egy futáson belül legfeljebb ennyi PDF-letöltést próbál meg - ez védi
# ki, hogy egy első/bulk lekérdezés (amikor sok "új" számlát talál
# egyszerre, mert még semmi nincs elmentve) ne fusson percekig azzal,
# hogy egyenként, sorban próbál PDF-et letölteni mindegyikhez. A sapkán
# túli számlák PDF-csatolmány nélkül kerülnek be (attól még rögzülnek és
# az email is kimegy értük).
DIJNET_MAX_PDF_LETOLTES_FUTASONKENT = 8

# Ugyanaz a védelem, mint a Díjnetnél fent, csak a Vízművek-lekérdezéshez.
VIZMUVEK_MAX_PDF_LETOLTES_FUTASONKENT = 8

# ── KÜLÖN keret a PDF-PÓTLÁSHOZ (visszamenőleges, MÁR ISMERT számlák) ──
# A fenti két sapka (DIJNET_MAX_PDF_LETOLTES_FUTASONKENT /
# VIZMUVEK_MAX_PDF_LETOLTES_FUTASONKENT) korábban EGYETLEN, KÖZÖS
# számlálót védett: azt is, amikor egy VADONATÚJ számlához töltünk le
# PDF-et, ÉS azt is, amikor egy MÁR ISMERT, de PDF nélkül maradt
# (korábban a sapkán túl volt) számlához próbálunk utólag PDF-et pótolni
# (ld. lentebb a "Utólagos PDF-pótlás" ágakat). A GYAKORLATBAN ez azt
# eredményezte, hogy minden futáskor előbb az ÚJ számlák ették fel a
# teljes keretet, és a régebbi, még PDF nélküli számlák pótlása SOHA nem
# jutott sorra - néhány régebbi számla emiatt TARTÓSAN "nincs PDF"
# állapotban ragadt a dashboardon, pedig lett volna rá keret, csak azt
# mindig az új számlák vitték el előbb.
#
# A megoldás: a pótlásnak SAJÁT, FÜGGETLEN kerete van (ez a két konstans),
# ami NEM oszt(oz)ik az új-számla letöltési kerettel - így egy sok-új-
# számlás futás sem tudja teljesen kiéheztetni a pótlást, és fordítva. Az
# érték szándékosan nagyvonalúbb (20), mert ez a művelet a régi
# lemaradást dolgozza le, több futáson keresztül fokozatosan - nem kell
# annyira védekezni egy "bulk" elsőindulási tömeg ellen, mint az új
# számláknál.
DIJNET_PDF_POTLAS_MAX_FUTASONKENT = 20
VIZMUVEK_PDF_POTLAS_MAX_FUTASONKENT = 20

# Vízművek - közvetlen portál-bejelentkezéshez (nem email-alapú, ugyanaz
# az elv, mint a Díjnetnél fent - ld. lentebb a "VÍZMŰVEK - KÖZVETLEN
# PORTÁL-LEKÉRDEZÉS" szekciót). Ha ezt a kettőt nem állítod be, a
# Vízművek-portál közvetlen lekérdezése egyszerűen kimarad, minden más
# (email-figyelés, Díjnet) változatlanul működik.
VIZMUVEK_USER = os.environ.get("SZAMLA_VIZMUVEK_USER") or ""
VIZMUVEK_JELSZO = os.environ.get("SZAMLA_VIZMUVEK_JELSZO") or ""

# ── Google Drive - PDF-feltöltés (opcionális) ──
# EGY KÜLÖN, a felhasználó által már telepített és üzemeltetett Google
# Apps Script Web App-ra épül (ld. lentebb a "GOOGLE DRIVE - PDF-
# FELTÖLTÉS" szekciót a pontos szerződésért) - ezt a script NEM hozza
# létre/kezeli, csak HÍVJA. Ha ezt a kettőt (URL + token) nem állítod
# be, a teljes funkció egyszerűen kimarad, ugyanaz az elv, mint a
# Díjnet/Vízművek portál-integrációknál fent - minden más változatlanul
# működik.
SZAMLA_DRIVE_WEBAPP_URL = os.environ.get("SZAMLA_DRIVE_WEBAPP_URL") or ""
SZAMLA_DRIVE_WEBAPP_TOKEN = os.environ.get("SZAMLA_DRIVE_WEBAPP_TOKEN") or ""

# Egy futáson belül legfeljebb ennyi PDF-et próbál feltölteni a Drive-ra -
# ugyanaz az indoklás, mint DIJNET_MAX_PDF_LETOLTES_FUTASONKENT-nél fent:
# ez védi ki, hogy egy első/bulk feltöltés (amikor sok, még fel nem
# töltött számla gyűlik össze egyszerre, pl. a funkció bekapcsolásának
# napján) ne fusson percekig egyetlen futás alatt. A sapkán túli számlák
# egyszerűen a KÖVETKEZŐ futáskor kerülnek sorra - ez a workflow mostani,
# 10 percenkénti ütemezése mellett különösen gyorsan megy, egy esetleges
# lemaradás (backlog) néhány futás alatt lecsökken.
DRIVE_FELTOLTES_MAX_FUTASONKENT = 15

# ── Céges számlák - dedikált postafiók (opcionális) ──
# EGY ÚJ, KÜLÖN, kizárólag céges (a cég nevében vásárolt) számlák
# begyűjtésére szánt email-postafiók figyelése - ld. lentebb a "CÉGES
# SZÁMLÁK" szekciót a pontos működésért. Ez SZÁNDÉKOSAN teljesen
# FÜGGETLEN a fenti (SZAMLA_IMAP_*) fő postafióktól - más cél, más
# feldolgozási logika (nincs itt "ismert szolgáltató" szűrés, MINDEN
# email számla-jelöltnek számít), és más a tárolási/törlési szabály is
# (ld. lentebb). Nincs alapértelmezett host (pl. imap.gmail.com), mert ez
# a postafiók a felhasználó saját döntése szerint bármilyen szolgáltatónál
# lehet (jelen esetben egy saját domain-es webhosting-postafiók) - ha a
# host nincs megadva, a modul egyszerűen kimarad (ld. lentebb
# ceges_szamlak_feldolgozasa()).
CEGES_IMAP_HOST = os.environ.get("CEGES_IMAP_HOST") or ""
CEGES_IMAP_PORT = int(os.environ.get("CEGES_IMAP_PORT") or "993")
CEGES_IMAP_USER = os.environ.get("CEGES_IMAP_USER") or ""
CEGES_IMAP_JELSZO = os.environ.get("CEGES_IMAP_JELSZO") or ""
CEGES_IMAP_MAPPA = os.environ.get("CEGES_IMAP_MAPPA") or "INBOX"

# Egy futáson belül legfeljebb ennyi céges számla-emailt dolgoz fel (a
# Drive-feltöltés + email-törlés miatt ez itt is védendő, ugyanaz az elv,
# mint DIJNET_MAX_PDF_LETOLTES_FUTASONKENT-nél fent) - a sapkán túli
# levelek egyszerűen a postafiókban maradnak, a KÖVETKEZŐ futás dolgozza
# fel őket (nem vesznek el, csak később kerülnek sorra).
CEGES_MAX_FELDOLGOZAS_FUTASONKENT = 20

# ── NAV Online Számla - bejövő számlák lekérdezése/párosítás (opcionális) ──
# Ld. lentebb a "NAV ONLINE SZÁMLA" szekciót a pontos működésért. Mind a
# négy alábbi env-változó opcionális - ha valamelyik hiányzik, a modul
# egyszerűen kimarad (a "Céges számlák" email-alapú begyűjtése ettől
# függetlenül változatlanul működik, csak a NAV-párosítás oszlop marad
# üresen a dashboardon).
#
# FONTOS - CSERE-KULCS ("exchangeKey") NEM KELL: a NAV API v3-ban a
# "tokenExchange" hívás (és az ahhoz tartozó cserekulcsos AES-dekódolás)
# KIZÁRÓLAG a számla-FELTÖLTÉSHEZ (manageInvoice) szükséges - mi itt csak
# OLVASUNK (queryInvoiceDigest), ami közvetlenül, a login/passwordHash/
# requestSignature hármassal hitelesít, tokenExchange nélkül. Emiatt
# SZÁNDÉKOSAN nincs itt "NAV_CSEREKULCS" env-változó.
NAV_TECHNIKAI_LOGIN = os.environ.get("NAV_TECHNIKAI_LOGIN") or ""
NAV_TECHNIKAI_JELSZO = os.environ.get("NAV_TECHNIKAI_JELSZO") or ""
NAV_ALAIRO_KULCS = os.environ.get("NAV_ALAIRO_KULCS") or ""
NAV_ADOSZAM = os.environ.get("NAV_ADOSZAM") or ""

# A felhasználó kifejezett kérése szerint az ÉLES (nem teszt) NAV-környezet
# van itt beállítva - a valódi céges bejövő számlákat kérdezzük le.
NAV_API_BASE_URL = "https://api.onlineszamla.nav.gov.hu/invoiceService/v3"

# A NAV előírja, hogy minden integráló szoftvernek legyen egy 18
# karakteres, csak betűket/számokat tartalmazó azonosítója - ez NEM
# titkos adat (nem kell Secretbe tenni), csak egy fix szoftver-azonosító.
NAV_SOFTWARE_ID = "SZAMLAFIGYELOBOT01"
NAV_SOFTWARE_NEV = "Szamla Figyelo"
NAV_SOFTWARE_FEJLESZTO_NEV = "Balogh Gabor Jozsef"
NAV_SOFTWARE_FEJLESZTO_EMAIL = "baloghgabee@gmail.com"

# Hány napra visszamenőleg kérdezze le a NAV-tól a bejövő számlákat minden
# futáskor - ugyanaz a "mozgó ablak" elv, mint a Díjnetnél/Vízműveknél
# (DIJNET_LEKERDEZES_NAPOK_VISSZA kommentje). A NAV EGY lekérdezésen belül
# legfeljebb 35 napos intervallumot enged (ld. lentebb _nav_datum_szeletek()) -
# ha ennél nagyobb a visszatekintés, a lekérdezés automatikusan több,
# egymást követő <=30 napos "szeletre" bontva fut le.
NAV_LEKERDEZES_NAPOK_VISSZA = 90

# ⬇️⬇️⬇️ ITT ÁLLÍTSD BE, HÁNY NAPPAL A HATÁRIDŐ ELŐTT MENJEN AZ ÖSSZESÍTŐ ⬇️⬇️⬇️
SZAMLA_EMLEKEZTETO_NAPOK_ELOTTE = 5  # <-- írd át a saját igényed szerint

# Kapcsolók - vedd ki/tedd be az igényed szerint, ha valamelyik
# értesítés-típus túl sok/kevés emailt eredményezne.
MEROALLAS_ERTESITES_EMAIL = True   # küldjön-e emailt új mérőállás-eseménynél
ISMERETLEN_ERTESITES_EMAIL = True  # küldjön-e emailt fel nem ismert levélnél

# Hány napra visszamenőleg nézze át a postafiókot minden futáskor (ez a
# MINIMÁLIS visszatekintés - a TÉNYLEGES SINCE-dátumot ld. _imap_kezdo_nap()
# lentebb, ami ezt az ablakot MINDIG kiterjeszti az aktuális év január
# 1-jéig is, a felhasználó kifejezett kérésére: "nekem az egész aktuális
# év kell"). 30 nap kockázatos, ha a workflow valamiért 30+ napig nem
# futna (pl. GitHub-leállás, secret lejár stb.) - egy ennél régebbi, még
# feldolgozatlan levél örökre kimaradna. 90 nap bőven elég puffer, és az
# IMAP SINCE keresés sebességét/terhelését gyakorlatilag nem érinti.
IMAP_LEKERDEZES_NAPOK = 90


def _imap_kezdo_nap():
    """A uj_uidok_lekerese() SINCE-keresésének kezdő dátuma - MINDIG
    legalább az AKTUÁLIS ÉV JANUÁR 1-jéig visszamegy (a felhasználó
    kérésére: "nekem az egész aktuális év kell" - korábban ez egy sima,
    mindig csak IMAP_LEKERDEZES_NAPOK (90) napos "mozgó ablak" volt, ami
    miatt a január elejétől érkezett, de csak most (pl. szeptemberben)
    bekapcsolt postafiókok/kategóriák - ld. a "further postafiokok" →
    Céges áthelyezés esetét - sosem látták a 90 napnál régebbi leveleket,
    hiába voltak még ott a postafiókban). Emellett a szokásos
    IMAP_LEKERDEZES_NAPOK-os mozgó ablakot IS megtartjuk (a kettő közül a
    KORÁBBI, azaz messzebb visszamenő dátumot használjuk) - ez január-
    március környékén ad egy kis extra puffert az évforduló körül (ld. az
    IMAP_LEKERDEZES_NAPOK kommentjét a workflow-kiesés elleni védelemről),
    az év további részében pedig január 1-je lesz a meghatározó (mert az
    messzebb van vissza, mint "ma - 90 nap")."""
    ma = magyar_ma()
    ev_eleje = ma.replace(month=1, day=1)
    gorgo_ablak = ma - timedelta(days=IMAP_LEKERDEZES_NAPOK)
    return min(ev_eleje, gorgo_ablak)


# Hány ÚJ (még feldolgozatlan) levelet nézzen meg legfeljebb EGY postafiókból
# EGY futás alatt (ld. uj_uidok_lekerese() lentebb) - a dedikált Céges-
# postafióknál (ceges_osszes_uid_lekerese()) már korábban is volt egy ilyen
# limit (CEGES_MAX_FELDOLGOZAS_FUTASONKENT = 20), most ugyanezt vezetjük be
# a fő postafióknál ÉS minden "további postafióknál" is (korábban ott 60 volt
# a limit) - FONTOS INDOK: minden újonnan talált levélhez tartozik legalább
# egy Drive-feltöltés (hálózati hívás) és 1-2 email-küldés (SMTP, ugyancsak
# hálózati) - ha egyszerre sok ÚJ levél kerül elő (pl. az _imap_kezdo_nap()
# "egész évig visszamenő" ablaka miatt egy most bekapcsolt postafióknál),
# ez a futást sokáig nyújthatja, ami két problémát okoz: (1) könnyen
# összeütközik a "timeout-minutes" korlátba, (2) minél tovább tart a futás,
# annál nagyobb az esélye, hogy a dashboardról épp ekkor mentő felhasználó a
# git-commit ütközésbe (HTTP 409) fut - ld. allapotFrissitesEsMentese()
# kommentje a szamlak.html-ben. Egy kisebb, egyenletesebb "adag" (20 db)
# minden 20 perces futásnál rövidebb, kiszámíthatóbb futásidőt ad - egy
# nagyobb visszamenő backfill (pl. az egész éves ablak miatt felszínre
# kerülő régi levelek) emiatt több futáson keresztül, fokozatosan zajlik le,
# nem egyszerre - ez VÁRT és RENDBEN VAN, nem hiba.
IMAP_MAX_FELDOLGOZAS_FUTASONKENT = 20

# Teszt-mód: ha "1"-re állítod (SZAMLA_DRY_RUN=1 secret/env), a script
# mindent ugyanúgy lekérdez és felismer, de TÉNYLEGESEN NEM küld emailt
# és NEM menti/pusholja el az állapotfájlt - csak naplózza, mit tenne.
# Így az első éles teszteknél (vagy egy új felismerő minta kipróbálásakor)
# nem kell attól tartani, hogy feleslegesen email-lavina indul, vagy
# hibás adat kerül a titkosított állapotba.
DRY_RUN = os.environ.get("SZAMLA_DRY_RUN") == "1"

# A dashboardon (Beállítások panel, "Email-küldés engedélyezve" kapcsoló)
# ki/bekapcsolható - ez a modul-szintű alapérték, amit main() a
# beallitasok_betoltese() eredményével felülír, MIELŐTT bármelyik
# email_kuldes()-hívás megtörténne. SZÁNDÉKOSAN True (=letiltva) az
# alapállapot: amíg a felhasználó a dashboardon kifejezetten be nem
# kapcsolja (és el nem menti) a küldést, egyetlen email se menjen ki.
EMAIL_KIKAPCSOLVA = True

# Dátum-intervallumos, tetszőleges címzettnek szóló küldés (a dashboard
# "Számlák küldése emailben" panelje indítja egy workflow_dispatch hívással,
# ld. .github/workflows/szamla_monitor.yml). Mindhárom üres/hiányzik
# normál (ütemezett) futásnál - csak akkor van tartalmuk, ha valaki a
# dashboardon keresztül kifejezetten kérte ezt a küldést.
SZAMLA_DATUMTOL = os.environ.get("SZAMLA_DATUMTOL", "").strip()
SZAMLA_DATUMIG = os.environ.get("SZAMLA_DATUMIG", "").strip()
SZAMLA_CEL_EMAIL = os.environ.get("SZAMLA_CEL_EMAIL", "").strip()

# Manuális, azonnali küldés-gombok a dashboardról (ld. "3 címzetti kör"
# funkció) - ugyanaz a minta, mint a fenti dátum-intervallumos küldésnél:
# mindegyik üres/false egy ütemezett futásnál, csak workflow_dispatch-nál
# kaphat tartalmat (ld. .github/workflows/szamla_monitor.yml).
#   SZAMLA_BERLO_OSSZESITO_KOR: ""/"mind"/"kor_a"/"kor_b" - ha nem üres,
#     azonnal elküldi a fizetetlen-számla összesítőt a megadott bérlői
#     körnek (vagy "mind" esetén mindkettőnek), a szokásos ütemezéstől
#     függetlenül.
#   SZAMLA_TULAJDONOS_OSSZESITO_MOST: "1", ha a tulajdonos "Küldés most"
#     gombját nyomták meg - ilyenkor az ÖSSZES (minden kör + be nem
#     sorolt) jelenleg fizetetlen számla összesítője megy ki neki.
#   SZAMLA_KONYVELO_EMLEKEZTETO_MOST: "1", ha a könyvelői "Küldés most"
#     gombot nyomták meg - a havi, sablonos Drive-emlékeztetőt küldi ki
#     azonnal, a hónap-végi automatikus ütemezéstől függetlenül.
#   SZAMLA_PDF_CSATOLAS_MANUALIS: "1"/"" - a dashboard "PDF-ek csatolása"
#     jelölőnégyzete (ld. 7. pont) - KIZÁRÓLAG ezekre a MANUÁLIS
#     küldésekre vonatkozik, a meglévő (ütemezett) küldések PDF-csatolási
#     viselkedése ettől függetlenül, változatlanul megmarad.
SZAMLA_BERLO_OSSZESITO_KOR = os.environ.get("SZAMLA_BERLO_OSSZESITO_KOR", "").strip()
SZAMLA_TULAJDONOS_OSSZESITO_MOST = os.environ.get("SZAMLA_TULAJDONOS_OSSZESITO_MOST") == "1"
SZAMLA_KONYVELO_EMLEKEZTETO_MOST = os.environ.get("SZAMLA_KONYVELO_EMLEKEZTETO_MOST") == "1"
SZAMLA_PDF_CSATOLAS_MANUALIS = os.environ.get("SZAMLA_PDF_CSATOLAS_MANUALIS") == "1"
# A dashboard "NAV Online Számla összekötés" paneljének "Emlékeztető
# küldése a kijelölteknek" gombja - vesszővel elválasztott adószám-lista
# (a felhasználó által kijelölt, NAV-on megtalált, de emailben meg nem
# érkezett számlák szállítóinak adószáma) - ld. "NAV-ON TALÁLT, HIÁNYZÓ
# SZÁMLÁK EMLÉKEZTETŐJE" szekció lentebb. Csak workflow_dispatch-nál
# kaphat tartalmat, ütemezett futásnál mindig üres.
SZAMLA_NAV_EMLEKEZTETO_ADOSZAMOK = os.environ.get("SZAMLA_NAV_EMLEKEZTETO_ADOSZAMOK", "").strip()

# A hónap utolsó hány napjában menjen ki a könyvelői havi emlékeztető (ld.
# "KÖNYVELŐI KÖR" szekció) - egy kis "ablak", nem egyetlen fix nap, mert a
# workflow mostantól 10 percenként fut (ld. .github/workflows/
# szamla_monitor.yml), és egy adott naptári nap simán "kimaradhatna" (pl.
# egy átmeneti hiba miatt) - egy több-napos ablak esélyt ad az újra-
# próbálkozásra, az "utolso_konyvelo_emlekezteto_honap" jelző pedig
# gondoskodik arról, hogy egy hónapban CSAK EGYSZER menjen ki.
KONYVELO_EMLEKEZTETO_UTOLSO_N_NAP = 3

ALLAPOT_FAJL = "szamlak/szamla_allapot.enc.json"  # TITKOSÍTVA, ez kerül git-be

# A dashboardon (szamlak.html) beállítható paraméterek fájlja - a
# felhasználó a saját GitHub tokenjével közvetlenül a böngészőből írja
# felül (ld. szamlak.html "Beállítások" panelje). SZÁNDÉKOSAN NEM
# titkosított: csak számokat (napok száma, hónap napja) és a számlák
# saját (amúgy is értelmezhetetlen, hash-alapú) belső azonosítóit
# tartalmazza, ezekből nem olvasható ki személyes/pénzügyi adat - ezért
# nem indokolt, hogy a Python-oldalnak a titkosítási jelszóra is
# szüksége legyen csak ennek beolvasásához.
BEALLITASOK_FAJL = "szamlak/szamla_beallitasok.json"

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
    # A Díjnet SZÁNDÉKOSAN nincs itt - a Díjnet-számlákat mostantól nem az
    # emailjeiből ismerjük fel, hanem közvetlenül a dijnet.hu portálról,
    # bejelentkezve olvassuk ki (ld. lentebb, "DÍJNET - KÖZVETLEN PORTÁL-
    # LEKÉRDEZÉS" szekció) - ez megbízhatóbb, mint az email-alapú
    # felismerés, mert nem attól függ, küld-e egyáltalán emailt a Díjnet.
    # Ha egy dijnet.hu-ról érkező email mégis bejön a postafiókba, azt az
    # email-alapú ág innentől figyelmen kívül hagyja (nincs "dijnet" kulcs
    # a szolgáltató-azonosításban), hogy ne keletkezzen duplikált tétel.
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
#    FONTOS: a korábbi "köszönjük.{0,20}fizet" ág szándékosan KIKERÜLT
#    innen - túl megengedő volt, pl. egy "Köszönjük, hogy fizetésre ezt
#    a számlát választotta" jellegű mondat is illett volna rá, miközben
#    az nem fizetés-visszaigazolás. Fizetettnek jelölni egy számlát téves
#    pozitív esetben komolyabb hiba, mint egy valódi visszaigazolást
#    kihagyni (az legfeljebb egy futással később, a szigorúbb mintával is
#    felismerhető, vagy kézzel ellenőrizhető a dashboardon).
# FONTOS: a "száml" (nem a teljes "számla") a keresett szótő - a magyar
# nyelvtani toldalékolás (pl. tárgyeset: "számlát", birtokos: "számláját",
# "-ról/-ről": "számláról") a szó végi "a"-t "á"-ra nyújtja, emiatt a
# TELJES "számla" szó szó szerint NEM lenne benne pl. a "számlát" alakban
# ("számla" != "száml" + "át" eleje) - ezt egy teszt-futtatás közben
# vettük észre (egy "Kérjük, rendezze a számlát" jellegű, valós
# számlalevelekben gyakori mondat a teljes "számla" mintával nem lett
# volna felismerve). A "száml" tő minden gyakori toldalékolt alakot fed.
FIZETVE_MINTA = re.compile(
    r"fizetés\D{0,30}(sikeres|beérkezett|jóváírva|teljesült|megtörtént)|"
    r"sikeres\D{0,20}(fizetés|befizetés)|"
    r"befizetés\D{0,30}(sikeres|beérkezett|jóváírva|visszaigazol)|"
    r"száml\D{0,30}(kiegyenlít|rendez)|"
    r"(kiegyenlít|rendez)\D{0,30}száml",
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
# "száml" tő itt is (ld. FIZETVE_MINTA fenti kommentjét a toldalékolt
# alakok miatt), NEM a teljes "számla" szó.
SZAMLA_MINTA = re.compile(
    r"száml|díjbekérő|fizetendő",
    re.IGNORECASE,
)

# Összeg-minta: "12 345 Ft", "12.345 Ft", "12345 HUF", ezres-tagolással is.
# Ez az ÁLTALÁNOS/tartalék minta - az ELSŐ Ft/HUF-bal ellátott számot
# veszi a szövegből, ami egy számlán (nettó/ÁFA/bruttó/előző egyenleg/
# fizetendő sorokkal) könnyen a ROSSZ összeget adhatja vissza. Ezért a
# osszeg_kinyerese() ELŐSZÖR a FIZETENDO_OSSZEG_MINTA-val próbálkozik
# (ami kifejezetten "fizetendő/összesen/bruttó" címkéjű összeget keres),
# és csak ha az nem talál semmit, esik vissza erre az általános mintára.
OSSZEG_MINTA = re.compile(
    r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?)\s*(Ft|HUF)", re.IGNORECASE
)
# Címkézett összeg-minta - ezt próbáljuk ELŐSZÖR, mert egy számlalevélben
# gyakran több Ft-összeg is szerepel (nettó, ÁFA, előző egyenleg stb.),
# és minket a ténylegesen fizetendő végösszeg érdekel, nem az első
# előforduló szám.
FIZETENDO_OSSZEG_MINTA = re.compile(
    r"(?:fizetendő\s*összeg|fizetendő|bruttó\s*összeg|bruttó|mindösszesen|összesen)"
    r"\D{0,30}"
    r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?)\s*(Ft|HUF)",
    re.IGNORECASE,
)
# EUR-megfelelője a fenti két Ft/HUF-mintának - a felhasználó kifejezett
# kérésére ("van olyan számlám, ami nem forint, hanem EUR, kérlek a
# forintot és az eurót is jelöld"), mert a rendszer eddig KIZÁRÓLAG "Ft"/
# "HUF" jelölésű összeget ismert fel (ld. OSSZEG_MINTA/FIZETENDO_OSSZEG_
# MINTA fent) - egy EUR-számlánál ez korábban egyszerűen None-t adott
# (nem hibásan Ft-ként jelölve, csak "nem ismerte fel" - a felhasználó
# kézzel be tudta írni a dashboardon, de a mező mindig "Ft"-ként jelent
# meg). A "€" szimbólum ELŐL és HÁTUL is állhat ("€150" vagy "150 €"),
# ezért két alternatívát engedünk a mintában.
EUR_OSSZEG_MINTA = re.compile(
    r"(?:(?:€|EUR)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?))"
    r"|(?:(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\s*(?:€|EUR))",
    re.IGNORECASE,
)
FIZETENDO_EUR_OSSZEG_MINTA = re.compile(
    r"(?:fizetendő\s*összeg|fizetendő|total|amount\s*due|due)"
    r"\D{0,30}"
    r"(?:(?:€|EUR)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)"
    r"|(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\s*(?:€|EUR))",
    re.IGNORECASE,
)
# Határidő-minták - EGY formátumra (2026.09.15) hagyatkozni túl szigorú
# volt, a magyar számlalevelek több formátumban is írhatják a dátumot.
# Ezért három mintát próbálunk sorban: 1) "2026.09.15" (év elöl - a
# leggyakoribb magyar formátum, ezt próbáljuk először), 2) hónap NÉVVEL
# írva ("2026. szeptember 15." vagy csak "szeptember 15."), 3) "15.09.2026"
# (nap elöl - fordított sorrend).
HATARIDO_MINTA = re.compile(
    r"(?:fizetési\s*határidő|határidő|esedékesség)\D{0,15}"
    r"(\d{4})[.\-]\s*(\d{1,2})[.\-]\s*(\d{1,2})",
    re.IGNORECASE,
)
HUN_HONAPOK = {
    "január": 1, "február": 2, "március": 3, "április": 4,
    "május": 5, "június": 6, "július": 7, "augusztus": 8,
    "szeptember": 9, "október": 10, "november": 11, "december": 12,
}
_HONAP_MINTA_RESZ = "|".join(HUN_HONAPOK.keys())
HATARIDO_MINTA_HONAPNEVVEL = re.compile(
    r"(?:fizetési\s*határidő|határidő|esedékesség)\D{0,20}"
    r"(?:(\d{4})[.\s]+)?"
    r"(" + _HONAP_MINTA_RESZ + r")\D{0,5}(\d{1,2})",
    re.IGNORECASE,
)
HATARIDO_MINTA_FORDITOTT = re.compile(
    r"(?:fizetési\s*határidő|határidő|esedékesség)\D{0,15}"
    r"(\d{1,2})[.\-](\d{1,2})[.\-](\d{4})",
    re.IGNORECASE,
)
# Mérőállás-érték minta: "mérőállás: 1234", "óraállás 1234 m3" stb. -
# best-effort, ha nem talál semmit, a rekord üres értékkel kerül be (a
# dashboardon/eredeti levélben még mindig megnézhető).
MEROALLAS_ERTEK_MINTA = re.compile(
    r"(?:mérőállás|óraállás)\D{0,10}(\d[\d\s]{0,9})\s*(m3|m³|kwh)?",
    re.IGNORECASE,
)

# Általános (best-effort) számlaszám-minta - a "Céges számlák" postafiókba
# TETSZŐLEGES, ismeretlen formátumú eladótól jöhet PDF (nincs itt "ismert
# szolgáltató" szűrés/struktúra, mint a Díjnetnél/Vízműveknél), ezért csak
# egy általános, "számlaszám/sorszám"-címke utáni alfanumerikus kódot
# keresünk - ez a NAV-párosításhoz (ld. "NAV ONLINE SZÁMLA" szekció) egy
# TOVÁBBI (nem kizárólagos) egyező-jel, az összeg+dátum-egyezés mellett -
# ha nem talál semmit, a párosítás egyszerűen csak az összegre/dátumra
# hagyatkozik.
SZAMLASZAM_MINTA_ALTALANOS = re.compile(
    r"(?:számla\s*sorszáma|számlaszám|sorszám|számla\s*száma|invoice\s*(?:number|no))"
    r"\s*[:\-]?\s*"
    r"([A-Z0-9][A-Z0-9/\-]{3,24})",
    re.IGNORECASE,
)


def szamlaszam_kinyerese_altalanos(szoveg: str):
    """Ld. a fenti SZAMLASZAM_MINTA_ALTALANOS kommentjét - best-effort,
    None-t ad vissza, ha nem talált semmit (ez NEM hiba, csak azt jelenti,
    hogy a párosítás nem tud számlaszám-egyezésre hagyatkozni ennél a
    tételnél)."""
    talalat = SZAMLASZAM_MINTA_ALTALANOS.search(szoveg or "")
    if not talalat:
        return None
    return talalat.group(1).strip().upper() or None


# Negáció-őr: a FIZETVE_MINTA önmagában illeszkedne olyan mondatokra is,
# amik valójában TAGADÓ vagy FELSZÓLÍTÓ értelműek, pl. "a számla MÉG NEM
# került kiegyenlítésre" vagy "KÉRJÜK rendezze a számlát" - ezek éppen az
# ELLENKEZŐJÉT jelentik annak, mint egy valódi fizetés-visszaigazolás.
# Enélkül egy sima emlékeztető-levél tévesen "fizetve"-ként lett volna
# felismerve, és egy VALÓJÁBAN FIZETETLEN számlát jelölt volna fizetettnek
# (ezt egy teszt-futtatás közben vettük észre, a review-ban felsorolt
# hibákon felül).
NEGACIO_MINTA = re.compile(
    r"\b(nem|ne|nincs|kérjük|kérünk|szíveskedjen)\b",
    re.IGNORECASE,
)


def _fizetes_visszaigazolas_e(szoveg: str) -> bool:
    """A FIZETVE_MINTA minden találatát megvizsgálja - csak akkor számít
    valódi fizetés-visszaigazolásnak, ha a találat előtti kb. 25
    karakterben NINCS tagadó/felszólító szó (ld. NEGACIO_MINTA fenti
    kommentjét). Ha van több találat, és akár csak EGY valódi (nem
    tagadott) van közöttük, azt már fizetve-ként kezeljük."""
    for talalat in FIZETVE_MINTA.finditer(szoveg):
        # A tagadó/felszólító szó (pl. "nem", "kérjük") gyakran MAGÁN a
        # találaton belül van (pl. "számla\D{0,30}rendez" mintánál a
        # "még nem" a "\D{0,30}" résbe esik, tehát a match.group(0)
        # RÉSZE) - ezért a match kezdete előtti ~25 karaktert ÉS magát a
        # találatot is meg kell nézni, nem elég csak az előtte lévő részt.
        kezdet = max(0, talalat.start() - 25)
        korulotte = szoveg[kezdet:talalat.end()]
        if not NEGACIO_MINTA.search(korulotte):
            return True
    return False


def tartalom_tipus_azonositas(targy: str, teljes_szoveg: str) -> str:
    """A tárgy + a levél (és szükség esetén a csatolt PDF) szövege
    alapján visszaadja, MILYEN FAJTA dokumentumról van szó. Ez a program
    szíve - itt nem szolgáltatónkénti tárgy-sablonokra támaszkodunk,
    hanem általános, tartalmi jelentésre utaló kulcsszavakra.

    FONTOS SORREND: a SZAMLA_MINTA-t szándékosan a MEROALLAS_MINTA ELŐTT
    nézzük. Egy valódi számlalevél szövege gyakran hivatkozik a
    mérőállásra is (pl. "A számla alapjául szolgáló mérőállás..."), és a
    korábbi sorrendnél (mérőállás-minta előbb) egy ilyen levél tévesen
    "meroallas"-ként lett besorolva, elnyelve egy valódi számlát. A
    "számla" szó jelenléte erősebb jel, mint a "mérőállás" említése,
    ezért ha mindkettő szerepel, számlaként kezeljük."""
    egyesitett = f"{targy}\n{teljes_szoveg}"
    if _fizetes_visszaigazolas_e(egyesitett):
        return "fizetve"
    if EMLEKEZTETO_MINTA.search(egyesitett):
        return "fizetesi_emlekezteto"
    if SZAMLA_MINTA.search(egyesitett):
        return "uj_szamla"
    if MEROALLAS_MINTA.search(egyesitett):
        return "meroallas"
    return "ismeretlen"


# ════════════════════════════════════════════
#  🔐  TITKOSÍTÁS (AES-GCM, jelszó-alapú, PBKDF2)
# ════════════════════════════════════════════
# Az iterációszámot egy helyen tartjuk, ÉS bele is írjuk a titkosított
# csomagba ("iterations" mező) - így ha egyszer erősítünk rajta (vagy
# akár más KDF-re váltunk), a régebbi, kisebb iterációszámmal mentett
# fájlok is visszafejthetők maradnak (a dashboard a fájlból olvassa ki
# az akkor használt értéket, nem egy fixen beégetett számot).
PBKDF2_ITERACIOSZAM = 200_000


def _kulcs_szarmaztatas(jelszo: str, salt: bytes, iteraciok: int = PBKDF2_ITERACIOSZAM) -> bytes:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iteraciok
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
    kulcs = _kulcs_szarmaztatas(jelszo, salt, PBKDF2_ITERACIOSZAM)
    aesgcm = AESGCM(kulcs)
    nyers = json.dumps(adat, ensure_ascii=False).encode("utf-8")
    titkositott = aesgcm.encrypt(nonce, nyers, None)

    csomag = {
        "verzio": 3,
        "kdf": "PBKDF2-SHA256",
        "iterations": PBKDF2_ITERACIOSZAM,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "adat": base64.b64encode(titkositott).decode("ascii"),
        "frissitve": magyar_ido().isoformat(),
    }

    # A "felhasznaloi_csomag" egy OPCIONÁLIS, ettől a függvénytől teljesen
    # független mellék-mező a fájl legkülső JSON-objektumában (a dashboard
    # "Felhasználói (korlátozott) jelszó" panelje írja/törli, ld.
    # szamlak.html) - egy MÁSIK, korlátozott ("user") jelszóval becsomagolt
    # valódi admin-jelszót tartalmaz, hogy a dashboard egy második
    # jelszóval is megnyitható legyen, admin-csak funkciók nélkül.
    # Mivel ez a függvény MINDEN futáskor (naponta többször, ütemezetten)
    # a teljes fájlt friss "csomag" dict-ként ÍRJA ÚJRA, ha itt simán
    # figyelmen kívül hagynánk a korábbi tartalmat, a legközelebbi
    # ütemezett futás CSENDBEN KITÖRÖLNÉ a felhasznaloi_csomag mezőt - a
    # felhasználói jelszó a következő pillanattól nem működne, anélkül,
    # hogy bárki bármit is "törölt" volna. Ezért: ha a célfájl már
    # létezik, beolvassuk a jelenlegi (akár egy régebbi Python-futásból,
    # akár a dashboardról frissen mentett) tartalmát, és ha van benne
    # felhasznaloi_csomag, azt VÁLTOZATLANUL átemeljük az újonnan írt
    # csomagba - a fő adatblokk (adat/salt/nonce/stb.) titkosítási
    # logikáját ez nem érinti, csak ezt a mellék-mezőt őrzi meg.
    if os.path.exists(fajl):
        try:
            with open(fajl, "r", encoding="utf-8") as f:
                regi_csomag = json.load(f)
            if isinstance(regi_csomag, dict) and "felhasznaloi_csomag" in regi_csomag:
                csomag["felhasznaloi_csomag"] = regi_csomag["felhasznaloi_csomag"]
        except (OSError, ValueError):
            # Egy sérült/olvashatatlan régi fájl nem akadályozhatja meg az
            # új állapot mentését - ilyenkor legfeljebb a felhasznaloi_csomag
            # marad ki (mintha sose lett volna beállítva), a fő adat mentése
            # attól függetlenül sikeresen lefut.
            pass

    os.makedirs(os.path.dirname(fajl), exist_ok=True)
    with open(fajl, "w", encoding="utf-8") as f:
        json.dump(csomag, f, ensure_ascii=False, indent=2)


def visszafejt(jelszo: str, fajl: str) -> dict:
    alap = {
        "szamlak": {},
        "meroallasok": {},
        "ismeretlen_dokumentumok": {},
        "ismeretlen_fizetesek": {},
        "feldolgozott_uidok": [],
        "utolso_emlekezteto_nap": None,
        "utolso_fix_osszesito_datum": None,
        # invoice-id -> base64-kódolt PDF bytes. Ez a felhasználó KIFEJEZETT
        # kérésére/döntésére került be (ld. commit-üzenet) - korábban a
        # PDF-eket szándékosan SOHA nem tároltuk tartósan, csak átmenetileg,
        # az emailhez csatolva. Mivel ez az egész "adat" dict egyben megy át
        # az AES-GCM titkosításon (titkosit_es_ment), a PDF-ek is ugyanazzal
        # a jelszóval védettek, mint a számla-adatok - nincs szükség külön
        # titkosítási rétegre.
        "pdf_adatok": {},
        # ── Bérlői körök (ld. "BÉRLŐI KÖRÖK" szekció lentebb) ──
        # kibocsato_csoportok: {kibocsato_azonosito: "kor_a"/"kor_b"} - a
        # Díjnetes számlák "Számlakibocsátói azonosítója" alapján, a
        # felhasználó a dashboardon állítja be. Ez SZÁNDÉKOSAN a
        # TITKOSÍTOTT állapotban van (nem a publikus beallitasok-fájlban),
        # mert a kibocsátó-azonosító (pl. egy cím vagy cégnév-töredék)
        # önmagában is beazonosító adat lehet - ezt a felhasználó
        # kifejezetten így kérte (privát maradjon, de a dashboardról
        # kezelhető legyen).
        "kibocsato_csoportok": {},
        # vizmuvek_kor: "kor_a"/"kor_b"/None - a Vízművek-fiók (a benne lévő
        # összes mérő/számla) EGYBEN tartozik az egyik körhöz, NINCS
        # számlánkénti szétválasztás (a felhasználó kifejezett döntése).
        "vizmuvek_kor": None,
        # kor_nevek: a két kör (kor_a/kor_b) felhasználó által megadott,
        # emberi neve - csak megjelenítéshez kell, ha üres/None, a dashboard
        # egy generikus "1. kör"/"2. kör" feliratra esik vissza.
        "kor_nevek": {"kor_a": None, "kor_b": None},
        # ── 3 CÍMZETTI KÖR (könyvelő / bérlő / tulajdonos) ──────────────
        # kor_emailek: {"kor_a": [cím, ...], "kor_b": [cím, ...]} - a
        # bérlői körök email-CÍM-LISTÁJA (a felhasználó kérésére kör
        # per email-cím lehet TÖBB is, nem csak egy). Ez SZÁNDÉKOSAN a
        # TITKOSÍTOTT állapotban van, NEM a publikus szamla_beallitasok.
        # json-ban (ld. annak fenti kommentjét) - egy email-cím önmagában
        # is személyes adat. A tényleges küldésnél ez a lista a RÉGI (ld.
        # KOR_EMAIL_CIMEK fenti kommentje) GitHub Secret-alapú címmel
        # UNIÓBAN kerül felhasználásra (visszafelé-kompatibilitás), ld.
        # _kor_cimzettek().
        "kor_emailek": {"kor_a": [], "kor_b": []},
        # tulajdonos_emailek: a TULAJDONOS (a rendszer üzemeltetője) saját,
        # egy vagy több email-címe. Ő kap MINDEN "új számla érkezett"
        # értesítést (forrástól/kör-besorolástól függetlenül, AZONNAL), és
        # minden bérlői-kör-összesítő EGY MÁSOLATÁT is (ld. "BÉRLŐI KÖRÖK"
        # szekció lentebb, _uj_szamla_ertesites_kuldese() és
        # _tulajdonos_osszesito_masolat()).
        "tulajdonos_emailek": [],
        # konyvelo_emailek: a KÖNYVELŐ email-cím(ei) - ez a kör SZÁNDÉKOSAN
        # NEM kap semmilyen számla-adatot/csatolmányt ebből a rendszerből
        # (a tulajdonos ezeket egy KÜLÖN, kézzel megosztott Google Drive
        # mappán keresztül adja át neki) - az egyetlen dolog, amit itt
        # kap, egy egyszerű, havi, hónap-végi emlékeztető-email (ld.
        # konyvelo_emlekezteto_email_html()).
        "konyvelo_emailek": [],
        # utolso_konyvelo_emlekezteto_honap: "ÉÉÉÉ-HH" - melyik hónapra
        # ment már ki a könyvelői emlékeztető, hogy a (mostantól 10
        # percenkénti) ütemezett futás ne küldje el ugyanazt a hónapban
        # tucatszor - ugyanaz a minta, mint "utolso_fix_osszesito_datum".
        "utolso_konyvelo_emlekezteto_honap": None,
        # szamla_kor_felulbiralas: {invoice_id: "kor_a"/"kor_b"} - PER
        # SZÁMLA kézi kör-felülbírálás, a kibocsátó-szintű (Díjnet) / fiók-
        # szintű (Vízművek) alapértelmezett besorolástól FÜGGETLENÜL.
        #
        # MIÉRT KELL EZ (MOHU-probléma): a Díjneten érkező MOHU-számláknál
        # a "kibocsátói azonosító" oszlop NEM különbözteti meg a
        # tulajdonos különböző szerződéseit/bérleményeit - emiatt a
        # kibocsátó-szintű automatikus besorolás egy MOHU-számlát a ROSSZ
        # bérlő email-címére is küldhetne, ami valódi ADATVÉDELMI
        # probléma lenne (más bérlő adatai jutnának el egy harmadik
        # félhez). Mivel jelenleg NINCS elég megbízható MINTA/valós
        # tapasztalat ahhoz, hogy egy automatikus szöveg-elemzést
        # (regex a "tárgy" mezőn) biztonságosan felépítsünk, EZ a
        # rendszer SZÁNDÉKOSAN NEM próbál kitalálni/parse-olni semmit -
        # helyette a dashboardon a felhasználó SAJÁT SZEMÉVEL nézi meg az
        # újonnan felfedett "dijnet_extra_oszlop" mezőt (ld. lentebb) és
        # KÉZZEL választja ki a helyes kört, számlánként. Ez itt, a
        # kézi felülbírálás mezőben rögzül, és MINDIG ERŐSEBB, mint az
        # automatikus alapértelmezés (ld. _szamla_kor_override()). Ha a
        # jövőben elég valós "dijnet_extra_oszlop"-mintát összegyűjt a
        # felhasználó, ez egy automatikus szabállyal kiegészíthető/
        # felváltható lesz - de amíg nincs elég adat, a BIZTOS (kézi)
        # megoldás mindig előnyösebb egy TALÁLT (és esetleg hibás)
        # automatikusnál.
        "szamla_kor_felulbiralas": {},
        # drive_feltoltott_id_k: azon számla-id-k listája, amik MÁR
        # sikeresen felkerültek a Google Drive-ra (ld. "GOOGLE DRIVE -
        # PDF-FELTÖLTÉS" szekció lentebb). Ez egy append-only "kész"-
        # jelző-halmaz - a cél csak az, hogy egy újrafutás (a workflow
        # mostantól 10 percenként fut) NE töltse fel ismét ugyanazt a
        # PDF-et minden alkalommal (a Web App-nak van saját, "mar_letezett"
        # nevű dedup-ja is, ez itt a MÁSODIK, a python-oldali védelmi
        # vonal - ld. drive_pdf_feltoltesek() kommentjét). LISTÁT
        # választottunk (nem pl. a "kibocsato_csoportok"-hoz hasonló
        # dict-et), mert itt nincs szükség kulcs->érték társításra (pl.
        # dátumra vagy kör-azonosítóra) - csak egy "tagja-e a halmaznak"
        # kérdésre, amihez egy egyszerű, append-only lista is elég.
        "drive_feltoltott_id_k": [],
    }
    if not os.path.exists(fajl):
        return alap

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag

    with open(fajl, "r", encoding="utf-8") as f:
        csomag = json.load(f)

    salt = base64.b64decode(csomag["salt"])
    nonce = base64.b64decode(csomag["nonce"])
    titkositott = base64.b64decode(csomag["adat"])
    # Régebbi (verzio<3) fájloknál nincs "iterations" mező - akkor a
    # jelenlegi alapértékkel próbálkozunk (ez volt akkoriban is a fix
    # beégetett érték).
    iteraciok = csomag.get("iterations", PBKDF2_ITERACIOSZAM)
    kulcs = _kulcs_szarmaztatas(jelszo, salt, iteraciok)
    aesgcm = AESGCM(kulcs)
    try:
        nyers = aesgcm.decrypt(nonce, titkositott, None)
    except InvalidTag:
        # Ez NEM egy váratlan/programozási hiba - az AES-GCM szándékosan
        # ezt dobja, ha a levezetett kulcs (vagyis a megadott jelszó) NEM
        # egyezik azzal, amivel a fájlt eredetileg titkosították. Egy
        # nyers Python-traceback helyett egy világos, magyar, ok-okozatot
        # is megadó hibaüzenetet adunk - ez a leggyakrabban akkor
        # jelentkezik, ha valaki megváltoztatja a SZAMLA_TITKOSITAS_JELSZO
        # secretet, miközben a repóban még a RÉGI jelszóval titkosított
        # fájl van.
        raise RuntimeError(
            f"Nem sikerült visszafejteni a titkosított állapotfájlt ({fajl}) "
            "a megadott SZAMLA_TITKOSITAS_JELSZO jelszóval. Két gyakori ok: "
            "1) megváltoztattad a SZAMLA_TITKOSITAS_JELSZO secretet, de a "
            "meglévő fájl még a RÉGI jelszóval van titkosítva - ha "
            "szándékosan váltottál jelszót, töröld ezt a fájlt a repóból "
            "(GitHub webes felületén), hogy a script friss, üres "
            "állapotból induljon újra az ÚJ jelszóval; 2) elgépelted / "
            "hibásan másoltad be a secret értékét (pl. felesleges "
            "szóköz/sortörés került bele)."
        ) from None
    betoltott = json.loads(nyers.decode("utf-8"))
    alap.update(betoltott)
    return alap


def beallitasok_betoltese() -> dict:
    """A dashboardon beállítható paraméterek beolvasása (ld.
    BEALLITASOK_FAJL fenti kommentjét - ez NEM titkosított). Ha a fájl
    nem létezik, vagy egy adott mező hiányzik/érvénytelen belőle, a
    biztonságos alapérték marad érvényben (visszafelé kompatibilis - a
    dashboard "Beállítások" panelje nélkül, vagy annak első használata
    előtt is minden a régi módon működik)."""
    alap = {
        "emlekezteto_napok_elotte": None,   # None = a SZAMLA_EMLEKEZTETO_NAPOK_ELOTTE modul-konstans marad érvényben
        "osszesito_honap_nap": None,        # None = nincs fix-napi tételes összesítő beállítva
        "kivalasztott_szamlak": None,       # None = a fix-napi összesítő (ha be van kapcsolva) minden fizetetlen számlát tartalmaz
        "email_kikapcsolva": True,          # True = NINCS email-küldés - ez a biztonságos alapállapot, amíg a dashboardon valaki kifejezetten be nem kapcsolja
        # A dashboard "X" (végleges elrejtés) gombjával törölt számlák saját,
        # amúgy is értelmezhetetlen, hash-alapú belső azonosítói (ld. a
        # BEALLITASOK_FAJL fenti kommentjét - ezért NEM titkosított: ezekből
        # nem olvasható ki semmilyen személyes/pénzügyi adat). A script
        # minden futáskor véglegesen eltávolítja ezeket a szamlak/pdf_adatok
        # közül - ha a forrás-portálon később ismét megjelenne UGYANAZ a
        # számla (ugyanaz a hash-azonosító adódna ki belőle), azonnal újra
        # törlődik, tehát tartósan "el van némítva".
        "torolt_szamla_id_k": [],
    }
    if not os.path.exists(BEALLITASOK_FAJL):
        return alap
    try:
        with open(BEALLITASOK_FAJL, "r", encoding="utf-8") as f:
            betoltott = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ⚠️  A beállítások fájl ({BEALLITASOK_FAJL}) nem olvasható be, alapértékekkel "
              f"folytatjuk: {e}")
        return alap

    napok = betoltott.get("emlekezteto_napok_elotte")
    if isinstance(napok, int) and 0 < napok <= 90:
        alap["emlekezteto_napok_elotte"] = napok

    honap_nap = betoltott.get("osszesito_honap_nap")
    if isinstance(honap_nap, int) and 1 <= honap_nap <= 28:
        alap["osszesito_honap_nap"] = honap_nap

    kivalasztott = betoltott.get("kivalasztott_szamlak")
    if isinstance(kivalasztott, list) and all(isinstance(x, str) for x in kivalasztott):
        alap["kivalasztott_szamlak"] = kivalasztott

    torolt = betoltott.get("torolt_szamla_id_k")
    if isinstance(torolt, list) and all(isinstance(x, str) for x in torolt):
        alap["torolt_szamla_id_k"] = torolt

    # FONTOS: itt (a többi mezővel ellentétben) a hiányzó/érvénytelen érték
    # NEM a "régi működést" jelenti, hanem a biztonságos "nincs email"
    # alapállapotot (ld. fent az "alap" szótárban) - csak egy explicit
    # "email_kikapcsolva": false menti felül, azt is csak akkor, ha a
    # dashboard "Email-küldés engedélyezve" kapcsolóját valaki bepipálva
    # mentette.
    email_kikapcsolva = betoltott.get("email_kikapcsolva")
    if isinstance(email_kikapcsolva, bool):
        alap["email_kikapcsolva"] = email_kikapcsolva

    return alap


# ════════════════════════════════════════════
#  📥  IMAP - EMAILEK BEOLVASÁSA
# ════════════════════════════════════════════
def imap_kapcsolat(host=None, port=None, user=None, jelszo=None, mappa=None):
    """Paraméterezhető - a fő (SZAMLA_IMAP_*) postafiókhoz simán
    argumentum nélkül hívható (a globális alapértékeket használja,
    változatlan viselkedéssel), a "Céges számlák" modul (ld. lentebb)
    viszont egy MÁSIK, teljesen független postafiókhoz saját
    (CEGES_IMAP_*) adatokkal hívja."""
    conn = imaplib.IMAP4_SSL(host or IMAP_HOST, port or IMAP_PORT)
    conn.login(user or IMAP_USER, jelszo or IMAP_JELSZO)
    conn.select(mappa or IMAP_MAPPA)
    return conn


def _fejlec_dekodolas(nyers):
    if not nyers:
        return ""
    return str(make_header(decode_header(nyers)))


def _feladó_cim(msg) -> str:
    from email.utils import parseaddr

    _, cim = parseaddr(msg.get("From", ""))
    return cim.lower()


def _email_datum_iso(erkezett_fejlec: str) -> str:
    """A levél VALÓDI (Date fejlécből olvasott) küldési idejét adja
    vissza ISO formátumban, ha sikerül értelmezni - egyébként a
    feldolgozás pillanatát (ez a korábbi, kevésbé pontos viselkedés volt
    mindenhol). A nyers fejléc mindig külön is elmentésre kerül
    ("erkezett_fejlec" mezőben), úgyhogy ez utólag is ellenőrizhető."""
    if erkezett_fejlec:
        try:
            return parsedate_to_datetime(erkezett_fejlec).astimezone(MAGYAR_TZ).isoformat()
        except (TypeError, ValueError):
            pass
    return magyar_ido().isoformat()


def uj_uidok_lekerese(conn, mar_feldolgozott: set, max_uj=IMAP_MAX_FELDOLGOZAS_FUTASONKENT):
    """A postafiók emailjei közül visszaadja azokat az UID-kat, amiket még
    nem dolgoztunk fel - a keresés kezdő dátumát ld. _imap_kezdo_nap()
    (MINDIG legalább az aktuális év január 1-jéig visszamegy). Nem jelöli
    olvasottnak a postafiókban lévő eredeti leveleket (nem piszkáljuk a
    te postaládád állapotát).

    ISMERT KORLÁT: ha a feldolgozott UID-ok listája (ld. lentebb,
    feldolgozott_uidok) bármikor elveszne VAGY a postafiók UIDVALIDITY-je
    megváltozna (pl. postafiók újraépítése), a program nem tudná
    biztonságosan megkülönböztetni a "már láttam" és "még nem láttam"
    UID-kat - ez egy ritka, de elméletben lehetséges eset. Egy teljesen
    robusztus megoldás az IMAP UIDVALIDITY expliciten kezelné; erre most
    nem került sor, a gyakorlati kockázatot az "egész év" ablak csökkenti."""
    kezdo_nap = _imap_kezdo_nap().strftime("%d-%b-%Y")
    tipus, adat = conn.uid("search", None, f'(SINCE "{kezdo_nap}")')
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


# ════════════════════════════════════════════
#  📎  PDF-EK TARTÓS (TITKOSÍTOTT) TÁROLÁSA
# ════════════════════════════════════════════
# A felhasználó kifejezett kérésére/döntésére a PDF-számlákat mostantól
# NEM csak átmenetileg (email-csatolmányként), hanem tartósan, a
# titkosított állapotfájl részeként is eltároljuk - ez teszi lehetővé a
# dashboardon a soronkénti letöltés-gombot és a dátum-intervallumos
# email-küldést, mindkettő új adatot nem igényel, a már eltárolt PDF-t
# használja. Mivel az egész állapot-dict egyben megy át az AES-GCM
# titkosításon, a PDF-ek is a számla-adatokkal AZONOS szintű védelmet
# kapnak, külön réteg nélkül.
#
# MÉRETKORLÁT: ez a fájl mérete jelentősen megnő (a PDF-ek base64-ben,
# ~37%-os többlettel kerülnek be) - ezt a felhasználó tudatosan
# vállalta. Hogy ne nőjön a végtelenségig, a _pdf_tarolas_ritkitasa()
# függvény minden mentés előtt lefut: a FIZETETLEN számlák PDF-jét
# mindig megtartja, a FIZETETT számláknál viszont csak az utóbbi
# PDF_MEGORZESI_NAPOK napból tartja meg (a számla-METAADAT ettől
# függetlenül megmarad örökre, csak a hozzá tartozó PDF-bájtok esnek ki,
# ha egy fizetett számla PDF-je ennél régebbi).
PDF_MEGORZESI_NAPOK = 400


def pdf_tarolas(allapot: dict, invoice_id: str, pdf_bytes):
    """Eltárolja (base64-ben) egy adott számlához tartozó PDF-et az
    állapotban, HA van mit tárolni és MÉG NINCS ott (ne töltsük le/
    tároljuk feleslegesen újra ugyanazt minden futáskor)."""
    if not pdf_bytes:
        return
    pdf_tar = allapot.setdefault("pdf_adatok", {})
    if invoice_id in pdf_tar:
        return
    pdf_tar[invoice_id] = base64.b64encode(pdf_bytes).decode("ascii")


def _pdf_tarolas_ritkitasa(allapot: dict):
    """Ld. a fenti szekció-komment MÉRETKORLÁT részét - fizetetlen
    számláknál mindig megtartjuk a PDF-et, fizetetteknél csak
    PDF_MEGORZESI_NAPOK napig. Az árva bejegyzéseket (olyan invoice-id,
    ami már nincs a szamlak dict-ben) is eltávolítja."""
    szamlak = allapot.get("szamlak", {})
    pdf_tar = allapot.get("pdf_adatok", {})
    if not pdf_tar:
        return
    hatar_nap = (magyar_ma() - timedelta(days=PDF_MEGORZESI_NAPOK)).isoformat()
    megtartando = {}
    for invoice_id, b64_adat in pdf_tar.items():
        rekord = szamlak.get(invoice_id)
        if rekord is None:
            continue  # árva bejegyzés - a számla-metaadat már nincs meg, a PDF-et sem tartjuk
        if not rekord.get("fizetve"):
            megtartando[invoice_id] = b64_adat
            continue
        fizetve_datum = (rekord.get("fizetve_datum") or "")[:10]
        if fizetve_datum >= hatar_nap:
            megtartando[invoice_id] = b64_adat
    allapot["pdf_adatok"] = megtartando


def _forint_szoveg_szamma(nyers: str):
    szam = nyers.replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(szam)
    except ValueError:
        return None


def osszeg_kinyerese(szoveg: str):
    """ELŐSZÖR a címkézett ("fizetendő"/"összesen"/"bruttó") összeget
    keresi - egy számlán több Ft-összeg is szerepelhet (nettó, ÁFA,
    előző egyenleg stb.), és minket a ténylegesen fizetendő végösszeg
    érdekel. Csak ha ilyen címke nincs a szövegben, esik vissza az első
    talált Ft/HUF-os számra."""
    cimkezett = FIZETENDO_OSSZEG_MINTA.search(szoveg)
    if cimkezett:
        return _forint_szoveg_szamma(cimkezett.group(1))
    talalat = OSSZEG_MINTA.search(szoveg)
    if not talalat:
        return None
    return _forint_szoveg_szamma(talalat.group(1))


def _szamla_osszeg_szamma(nyers: str):
    """_forint_szoveg_szamma() ÁLTALÁNOSABB változata, EUR-összegekhez -
    a magyar (Ft) számlák MINDIG "." ezres-/","-tizedes-elválasztót
    használnak, egy EUR-számla viszont (a kiállító nemzetiségétől függően)
    lehet FORDÍTOTT (angolszász: "," ezres/"." tizedes) konvenciójú is -
    ezért itt nem hagyatkozunk egy fix konvencióra: a KÉT elválasztó közül
    azt tekintjük TIZEDES-elválasztónak, amelyik UTOLJÁRA szerepel a
    számban (ha csak egyik fajta van, ezres-elválasztónak vesszük - egy
    számlaösszegben 3 tizedesjegy rendkívül ritka). Best-effort, mint a
    többi kinyerő függvény - a dashboardon mindig kézzel javítható, ha
    rosszul sikerülne."""
    szam = nyers.replace(" ", "").replace("\xa0", "")
    utolso_pont = szam.rfind(".")
    utolso_vesszo = szam.rfind(",")
    if utolso_pont == -1 and utolso_vesszo == -1:
        pass
    elif utolso_pont > utolso_vesszo:
        szam = szam.replace(",", "")
    else:
        szam = szam.replace(".", "").replace(",", ".")
    try:
        return float(szam)
    except ValueError:
        return None


def osszeg_es_penznem_kinyerese(szoveg: str):
    """osszeg_kinyerese() KIBŐVÍTETT változata, ami a pénznemet IS
    visszaadja - (osszeg, penznem) párost ad, "penznem" mindig "HUF" vagy
    "EUR" (a felhasználó kifejezett kérésére: "van olyan számlám, ami nem
    forint, hanem EUR - kérlek a forintot és az eurót is jelöld"). ELŐSZÖR
    a forint-mintákat próbálja (ld. osszeg_kinyerese() fent) - ha ott
    talál, "HUF"-ot ad vissza. Csak ha a szövegben SEHOL nincs Ft/HUF-os
    összeg, próbálkozik az EUR-mintákkal (EUR_OSSZEG_MINTA/FIZETENDO_EUR_
    OSSZEG_MINTA) is - ez a sorrend szándékos: egy magyar nyelvű
    számlalevélben elvétve előfordulhat egy "€" jel (pl. egy árfolyam-
    tájékoztatóban), miközben a TÉNYLEGES fizetendő összeg valójában
    forint - a forint-minta elsőbbsége ez ellen véd. Ha semelyik minta nem
    talál semmit, (None, "HUF")-ot ad vissza - a "HUF" itt csak egy
    alapérték (a felhasználó a dashboard "Pénznem" mezőjén kézzel
    átállíthatja EUR-ra, ha kézzel írja be az összeget egy fel nem
    ismert EUR-számlánál)."""
    huf_osszeg = osszeg_kinyerese(szoveg)
    if huf_osszeg is not None:
        return huf_osszeg, "HUF"
    cimkezett = FIZETENDO_EUR_OSSZEG_MINTA.search(szoveg)
    if cimkezett:
        nyers = cimkezett.group(1) or cimkezett.group(2)
        eur_osszeg = _szamla_osszeg_szamma(nyers)
        if eur_osszeg is not None:
            return eur_osszeg, "EUR"
    talalat = EUR_OSSZEG_MINTA.search(szoveg)
    if talalat:
        nyers = talalat.group(1) or talalat.group(2)
        eur_osszeg = _szamla_osszeg_szamma(nyers)
        if eur_osszeg is not None:
            return eur_osszeg, "EUR"
    return None, "HUF"


def hatarido_kinyerese(szoveg: str):
    """Sorban próbálja a három ismert formátumot - lásd a minták fenti
    kommentjét. Az első sikeres illeszkedést adja vissza."""
    talalat = HATARIDO_MINTA.search(szoveg)
    if talalat:
        ev, ho, nap = talalat.groups()
        try:
            return f"{int(ev):04d}-{int(ho):02d}-{int(nap):02d}"
        except ValueError:
            pass

    talalat = HATARIDO_MINTA_HONAPNEVVEL.search(szoveg)
    if talalat:
        ev_nyers, honap_nev, nap = talalat.groups()
        honap = HUN_HONAPOK.get(honap_nev.lower())
        if honap:
            ev = int(ev_nyers) if ev_nyers else magyar_ma().year
            try:
                return f"{ev:04d}-{honap:02d}-{int(nap):02d}"
            except ValueError:
                pass

    talalat = HATARIDO_MINTA_FORDITOTT.search(szoveg)
    if talalat:
        nap, ho, ev = talalat.groups()
        try:
            if 1 <= int(ho) <= 12 and 1 <= int(nap) <= 31:
                return f"{int(ev):04d}-{int(ho):02d}-{int(nap):02d}"
        except ValueError:
            pass

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
def email_kuldes(targy, html_torzs, csatolmanyok=None, cimzett=None):
    """csatolmanyok: [(fajlnev, bytes), ...] - lehet üres/None.
    cimzett: ha None, az alapértelmezett EMAIL_CIMZETT-re megy (a szokásos
    értesítők) - a dashboard "dátum-intervallumos küldés" funkciója viszont
    egy tetszőleges, a felhasználó által megadott címre is tud küldeni."""
    if EMAIL_KIKAPCSOLVA:
        print(f"  🔕 Email-küldés le van tiltva a dashboard beállításaiban - kihagyva: {targy!r}")
        return False
    cimzett_vegso = cimzett or EMAIL_CIMZETT
    if DRY_RUN:
        csatolmany_nevek = [fajlnev for fajlnev, _ in (csatolmanyok or [])]
        print(f"  🧪 [DRY RUN] Email KIMENNE (de nem megy ki): {targy!r} -> "
              f"{cimzett_vegso!r} (csatolmányok: {csatolmany_nevek or 'nincs'})")
        return True
    if not (EMAIL_KULDO and EMAIL_JELSZO_KULDES and cimzett_vegso):
        print("  ⚠️  Nincs teljesen beállítva az email-küldés - kihagyva.")
        return False

    msg = MIMEMultipart("mixed")
    msg["Subject"] = targy
    msg["From"] = EMAIL_KULDO
    msg["To"] = cimzett_vegso
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


def osszeg_szoveg(osszeg, penznem=None):
    """forint() pénznem-tudatos változata - naplózáshoz/emailhez, ahol egy
    EUR-számla összegét NE "Ft"-ként írjuk ki (ld. a felhasználó kérése a
    forint()-nál/osszeg_es_penznem_kinyerese()-nél). "penznem" hiányában
    (pl. régi, e mező előtti rekordoknál) HUF-ot tételez fel - ez a
    korábbi, kizárólag-forint viselkedéssel egyező alapérték."""
    if osszeg is None:
        return "ismeretlen összeg"
    if (penznem or "HUF").strip().upper() == "EUR":
        return f"{osszeg:,.2f} EUR".replace(",", " ")
    return forint(osszeg)


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
      <h2 style="color:#1d4ed8;">📄 Új számla érkezett - {_esc(rekord['szolgaltato_nev'])}</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:6px 0;color:#555;">Tárgy</td>
            <td style="padding:6px 0;"><strong>{_esc(rekord['targy'])}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#555;">Összeg</td>
            <td style="padding:6px 0;"><strong>{osszeg_szoveg(rekord['osszeg'], rekord.get('penznem'))}</strong></td></tr>
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
      <h2 style="color:#0f766e;">🔢 Mérőállással kapcsolatos levél - {_esc(rekord['szolgaltato_nev'])}</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:6px 0;color:#555;">Tárgy</td>
            <td style="padding:6px 0;"><strong>{_esc(rekord['targy'])}</strong></td></tr>
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
      <p>Egy figyelt szolgáltatótól ({_esc(rekord['szolgaltato_nev'])}) érkezett levél,
         de a tartalma egyik ismert mintára (új számla / mérőállás / fizetés-
         visszaigazolás / emlékeztető) sem illett rá.</p>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:6px 0;color:#555;">Tárgy</td>
            <td style="padding:6px 0;"><strong>{_esc(rekord['targy'])}</strong></td></tr>
        <tr><td style="padding:6px 0;color:#555;">Érkezett</td>
            <td style="padding:6px 0;">{rekord['erkezett']}</td></tr>
      </table>
      <p style="color:#555;font-size:13px;margin-top:14px;background:#f9fafb;
                padding:10px 14px;border-radius:8px;white-space:pre-wrap;">{_esc(rekord.get('reszlet', ''))}</p>
      <p style="color:#777;font-size:13px;margin-top:20px;">
        Ha ez egy valódi számla/mérőállás-értesítés volt, szólj, hogy a
        felismerő mintákat pontosítsuk ez alapján.
      </p>
    </div>
    """


def osszesito_email_html(fizetetlen_lista, vegosszeg, provider_osszegek, cim=None, bevezeto=None):
    """cim/bevezeto: felülírható fejléc/bevezető szöveg - a küszöb-alapú
    (határidő-vezérelt) és a fix-napi, kézzel kiválasztott összesítő más
    szöveget indokol, ezért paraméterezhető, alapértéken a régi
    (küszöb-alapú) szöveg marad."""
    sorok = ""
    for r in fizetetlen_lista:
        lejart = r["hatarido"] and r["hatarido"] < magyar_ma().isoformat()
        szin = "#dc2626" if lejart else "#111827"
        sorok += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">{_esc(r['szolgaltato_nev'])}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{_esc(r['targy'])}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">{forint(r['osszeg'])}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;color:{szin};">
            {r['hatarido'] or 'ismeretlen'}{' ⏰ LEJÁRT' if lejart else ''}
          </td>
        </tr>"""

    provider_sorok = "".join(
        f'<li>{_esc(nev)}: <strong>{forint(osszeg)}</strong></li>'
        for nev, osszeg in provider_osszegek.items()
    )

    cim_vegso = cim or "💰 Fizetetlen számlák összesítője"
    bevezeto_vegso = bevezeto or (
        "<p>Az alábbi számlák még nincsenek kifizetve, és valamelyik határideje "
        f"{SZAMLA_EMLEKEZTETO_NAPOK_ELOTTE} napon belül lejár (vagy már lejárt):</p>"
    )
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;">
      <h2 style="color:#b91c1c;">{cim_vegso}</h2>
      {bevezeto_vegso}
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


def konyvelo_emlekezteto_email_html():
    """A könyvelői kör EGYETLEN emailje - havonta egyszer, hónap-vég körül.
    SZÁNDÉKOSAN nem tartalmaz semmilyen számla-adatot/összeget/csatolmányt -
    a könyvelő a tényleges anyagokat egy KÜLÖN, a tulajdonos által kézzel
    megosztott Google Drive mappából éri el (ld. "KÖNYVELŐI KÖR" komment a
    "BÉRLŐI KÖRÖK" szekció elején) - ennek a rendszernek itt csak egy
    egyszerű figyelmeztető/emlékeztető szerep jut."""
    return """
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
      <h2 style="color:#0f766e;">📁 Hónap vége van</h2>
      <p>Nézd meg kérlek a megosztott Google Drive mappát - hónap végén
      szokott bekerülni bele az adott havi számla-anyag.</p>
      <p style="color:#777;font-size:13px;margin-top:20px;">
        Ez egy automatikus, havi emlékeztető-email, szándékosan semmilyen
        számla-adatot vagy csatolmányt nem tartalmaz - a Drive mappa a
        hiteles forrás.
      </p>
    </div>
    """


# ════════════════════════════════════════════
#  🧾  DÍJNET - KÖZVETLEN PORTÁL-LEKÉRDEZÉS
# ════════════════════════════════════════════
# Nem email-alapú! Ez a rész közvetlenül bejelentkezik a dijnet.hu
# oldalra a Te felhasználóneveddel/jelszavaddal, és onnan olvassa ki a
# számláid pontos állapotát (összeg, határidő, fizetve-e) - így nem
# számít, hogy a Díjnet küld-e egyáltalán emailt, és nem kell a levél
# tárgyából/törzséből találgatni.
#
# A bejelentkezési/lekérdezési lépéseket egy nyílt forráskódú, aktívan
# karbantartott Home Assistant integráció (laszlojakab/homeassistant-
# dijnet, MIT licenc) alapján építettük fel - onnan ismertek a pontos
# végpontok. Mivel nincs saját, éles Díjnet-fiókunk a teszteléshez, az
# oszlop-beosztást (melyik táblázat-oszlopban mi van) és a PDF-letöltést
# az ELSŐ ÉLES FUTÁS naplójából kell majd megerősíteni/finomítani - a
# kód emiatt védekezően van megírva: ha egy sor nem a várt szerkezetű,
# nem áll le, csak kihagyja és naplózza a nyers sort.
DIJNET_BASE = "https://www.dijnet.hu"

# Ezekre a (kisbetűs) kulcsszavakra KEZDŐDŐ állapot-szöveg jelenti azt,
# hogy egy Díjnet-számla ki van fizetve. Minden más állapot-szöveg
# ("Tovább a fizetéshez", "Rendezetlen", "Csoportos beszedés" stb.)
# fizetetlennek számít.
# FONTOS: szándékosan "kezdődik ezzel" (startswith), NEM "tartalmazza
# valahol" (substring-anywhere) - utóbbi túl megengedő lenne, pl. egy
# "Rendezetlen" állapot-szöveg is TARTALMAZZA a "rendez" töredéket, egy
# substring-keresés emiatt tévesen fizetettnek jelölhetne egy valójában
# fizetetlen számlát.
DIJNET_FIZETVE_KULCSSZAVAK = ("rendezett", "fizetve")


def _dijnet_fizetve_e(allapot_szoveg: str) -> bool:
    szoveg = (allapot_szoveg or "").strip().lower()
    return any(szoveg.startswith(k) for k in DIJNET_FIZETVE_KULCSSZAVAK)


def dijnet_bejelentkezes():
    """Bejelentkezik a dijnet.hu portálra, és a bejelentkezett
    requests.Session()-t adja vissza - vagy None-t, ha nincs beállítva a
    Díjnet-hozzáférés, vagy a bejelentkezés sikertelen."""
    if not (DIJNET_USER and DIJNET_JELSZO):
        return None

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; SzamlaFigyelo/1.0)"})
    try:
        session.get(DIJNET_BASE + "/", timeout=12)  # session-cookie felvétele
        valasz = session.post(
            DIJNET_BASE + "/ekonto/login/login_check_ajax",
            data={"username": DIJNET_USER, "password": DIJNET_JELSZO},
            timeout=12,
        )
        try:
            adat = valasz.json()
        except Exception:
            print("  ⚠️  Díjnet bejelentkezés: a válasz nem JSON - valószínűleg megváltozott a portál.")
            return None
        if not adat.get("success"):
            print(f"  ⚠️  Díjnet bejelentkezés sikertelen (rossz felhasználónév/jelszó?): {adat}")
            return None
        print("  ✅ Díjnet bejelentkezés sikeres.")
        return session
    except Exception as e:
        print(f"  ⚠️  Díjnet bejelentkezési hiba: {e}")
        return None


def _dijnet_vfw_token(session):
    """A számla-kereső oldalról kiolvassa a rejtett 'vfw_token' mezőt,
    ami a keresési űrlap beküldéséhez kell (CSRF-szerű védelem).

    FONTOS: bejelentkezés után előbb a portál "főoldalát" kell
    meglátogatni (/ekonto/control/main) - enélkül a keresőoldal úgy
    viselkedhet, mintha a session nem lenne bejelentkezve (ez okozta az
    első éles futásnál, hogy nem találtunk vfw_token mezőt)."""
    session.get(DIJNET_BASE + "/ekonto/control/main", timeout=12)

    valasz = session.get(DIJNET_BASE + "/ekonto/control/szamla_search", timeout=12)
    valasz.encoding = "iso-8859-2"  # a Díjnet ezt a régi kódlapot használja
    # "html.parser" (a Python beépített parsere) szándékosan, NEM "lxml" -
    # a Díjnet válasza <?xml ...?> deklarációval kezdődik, ami az lxml-t
    # XML-szerű módba kapcsolja (ld. korábbi "XMLParsedAsHTMLWarning" a
    # naplóban) - ilyenkor nem szúr be automatikus <tbody>-t egy explicit
    # <tbody> nélküli <table>-be, ami kiszámíthatatlanná tette a CSS
    # szelektorokat. A html.parser mindig HTML5-ként értelmezi a
    # dokumentumot, a deklarációtól függetlenül - kiszámíthatóbb, és nem
    # igényel külön csomagot.
    soup = BeautifulSoup(valasz.text, "html.parser")
    mezo = soup.select_one('input[name="vfw_token"]')
    if mezo:
        return mezo.get("value")

    # Diagnosztika, hogy KÖVETKEZŐ alkalommal ne kelljen találgatni, ha
    # ismét nem találjuk a mezőt - a napló megmutatja, valójában milyen
    # oldalt kaptunk vissza (pl. ha visszairányított egy bejelentkező
    # oldalra, vagy a mezőnév/oldal-szerkezet megváltozott).
    # FONTOS - ADATVÉDELEM: a diagnosztika itt SZÁNDÉKOSAN csak
    # SZERKEZETI infót ír ki (URL, státuszkód, mező-NEVEK, <title> szövege) -
    # SOHA nem írjuk ki a válasz nyers tartalmát/szövegét, mert egy
    # bejelentkezett Díjnet-oldal akár személyes adatot (pl. regisztrált
    # szolgáltatók, ügyfélazonosítók) is tartalmazhat, és ez a napló egy
    # PUBLIKUS GitHub Actions futás naplójába kerülne (a repó nyilvános,
    # a GitHub Pages miatt). Egy korábbi verzió ezt hibásan mégis kiírta -
    # ez javítva lett.
    input_nevek = [i.get("name") for i in soup.find_all("input") if i.get("name")]
    cim_elem = soup.find("title")
    print(f"      🔍 Díjnet diagnosztika - végső URL: {valasz.url} | "
          f"státuszkód: {valasz.status_code} | oldal <title>: {cim_elem.get_text(strip=True) if cim_elem else '(nincs)'} | "
          f"talált <input name=...> mezők: {input_nevek}")
    return None


def _dijnet_datum_konvertalas(nyers: str):
    """"2026.09.15." / "2026-09-15" -> "2026-09-15". None, ha nem talál dátumot."""
    talalat = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", nyers or "")
    if not talalat:
        return None
    ev, ho, nap = talalat.groups()
    return f"{int(ev):04d}-{int(ho):02d}-{int(nap):02d}"


def _dijnet_osszeg_konvertalas(nyers: str):
    szam = re.sub(r"[^0-9\-]", "", nyers or "")
    try:
        return float(szam) if szam not in ("", "-") else None
    except ValueError:
        return None


def dijnet_szamlak_lekerdezese(session, napok_vissza=DIJNET_LEKERDEZES_NAPOK_VISSZA):
    """Lekérdezi a Díjnet-fiókhoz tartozó számlákat az elmúlt N napból,
    és egy listát ad vissza (Python dict-ek), soronként egy számlával."""
    nap_ig = magyar_ma()
    naptol = nap_ig - timedelta(days=napok_vissza)

    token = _dijnet_vfw_token(session)
    if not token:
        print("  ⚠️  Díjnet: nem található vfw_token a keresőoldalon - a portál felülete "
              "valószínűleg megváltozott, a lekérdezés így is megpróbálkozik, de lehet, "
              "hogy üres eredményt ad.")

    # FONTOS: a dátumokat "%Y-%m-%d" (kötőjeles, ISO) formátumban küldjük,
    # NEM "%Y.%m.%d" (pontos, magyar) formátumban - ez utóbbi volt a
    # tényleges hiba oka a "0 érvényes számla-sor" mögött (a szerver a
    # rosszul formázott dátumot nem tudta értelmezni, és emiatt
    # valószínűleg a keresőoldalt adta vissza eredmények helyett - nulla
    # <table> elemmel). Ezt az aktívan karbantartott laszlojakab/
    # homeassistant-dijnet integráció jelenlegi forráskódjából ellenőriztük
    # (ők DATE_FORMAT = "%Y-%m-%d"-t használnak a keresési kéréshez).
    adatok = {
        "vfw_form": "szamla_search_submit",
        "vfw_coll": "szamla_search_params",
        "vfw_token": token or "",
        "szlaszolgnev": "",  # üres = minden szolgáltató
        "regszolgid": "",    # üres = minden regisztrált szolgáltató
        "datumtol": naptol.strftime("%Y-%m-%d"),
        "datumig": nap_ig.strftime("%Y-%m-%d"),
    }
    valasz = session.post(DIJNET_BASE + "/ekonto/control/szamla_search_submit", data=adatok, timeout=20)
    valasz.encoding = "iso-8859-2"
    soup = BeautifulSoup(valasz.text, "html.parser")  # ld. _dijnet_vfw_token() kommentje a parser-választásról

    talalt_szamlak = []
    # A "table.table tr" leszármazott-szelektor (nem szigorú " > tbody > "
    # gyerek-szelektor) szándékos - html.parser-rel ez már nem lenne
    # kritikus (automatikusan beszúr <tbody>-t), de a bővebb szelektor
    # attól még biztonságosabb, ha a Díjnet oldalán a táblázat szerkezete
    # bármikor máshogy alakulna.
    sorok = soup.select("table.table tr")
    if not sorok:
        # FONTOS - ADATVÉDELEM: itt SOHA nem írjuk ki a válasz nyers
        # tartalmát/szövegét (sem az elejét, sem a közepét) - egy korábbi
        # verzió ezt hibásan megtette, és egy éles futásnál ez ténylegesen
        # kiírta a Díjnet-fiókhoz regisztrált szolgáltatók/ügyfélazonosítók
        # egy részét egy PUBLIKUS GitHub Actions napló-fájlba (a repó
        # nyilvános, a GitHub Pages miatt). Ez javítva lett - a
        # diagnosztika mostantól KIZÁRÓLAG szerkezeti információt ír ki
        # (darabszámok, igaz/hamis jelzők, statikus - minden felhasználónál
        # egyforma - felületi feliratok), sosem a tényleges tartalmat.
        osszes_table = soup.find_all("table")
        also_szoveg = valasz.text.lower()

        # Van-e a szövegben "nincs találat" jellegű üzenet - ha igen, az
        # azt jelentené, hogy a keresés lefutott, csak tényleg nincs
        # számla a lekérdezett időszakban (nem hibáról van szó).
        NINCS_TALALAT_KULCSSZAVAK = ["nincs találat", "nem talál", "nincs megjeleníthető", "0 db", "nincs adat"]
        talalt_kulcsszo = next((k for k in NINCS_TALALAT_KULCSSZAVAK if k in also_szoveg), None)

        # Van-e bejelentkező-űrlapra utaló mező (jelszó-mező) - ha igen,
        # az azt jelentené, hogy a session valójában NEM bejelentkezett
        # állapotban kapta ezt a választ (pl. lejárt/érvénytelen session),
        # és minket visszairányított egy login-oldalra.
        van_jelszo_mezo = soup.select_one('input[type="password"]') is not None

        # Van-e olyan beágyazott <script>, ami a számla-adatok jellemző
        # JSON-kulcsait tartalmazza (pl. "szamlaszam", "osszeg",
        # "hatarido") - ez arra utalna, hogy az oldal az eredményeket már
        # NEM szerver-oldalon renderelt HTML-táblázatként, hanem
        # kliens-oldali JS-sel, beágyazott JSON-ból építi fel, és emiatt
        # nem találunk <table>-t. Csak a kulcsNEVEK jelenlétét/darabszámát
        # nézzük, a script-tartalmat magát nem írjuk ki.
        script_szovegek = [s.get_text() for s in soup.find_all("script")]
        JSON_KULCS_JELOLTEK = ["szamlaszam", "számlaszám", "osszeg", "összeg", "hatarido", "határidő"]
        json_szeru_script_db = sum(
            1 for sz in script_szovegek
            if any(kulcs in sz.lower() for kulcs in JSON_KULCS_JELOLTEK)
        )

        cim_elem = soup.find("title")
        print(f"      🔍 Díjnet diagnosztika - válasz státuszkód: {valasz.status_code} | "
              f"végső URL: {valasz.url} | oldal <title>: "
              f"{cim_elem.get_text(strip=True) if cim_elem else '(nincs)'} | "
              f"teljes válasz hossza: {len(valasz.text)} karakter")
        print(f"      🔍 Díjnet diagnosztika - talált <table> elemek száma: {len(osszes_table)} | "
              f"összes <tr> a teljes oldalon: {len(soup.find_all('tr'))} | "
              f"jelszó-mező jelen van (session-probléma jele): {van_jelszo_mezo} | "
              f"számla-adatra utaló JSON-kulcsot tartalmazó <script> elemek száma: {json_szeru_script_db}")
        if talalt_kulcsszo:
            print(f"      🔍 Díjnet diagnosztika - a válaszban szerepel egy 'nincs találat'-szerű "
                  f"kifejezés ('{talalt_kulcsszo}') - lehet, hogy a keresés lefutott, csak "
                  f"tényleg nincs számla a lekérdezett {DIJNET_LEKERDEZES_NAPOK_VISSZA} napban.")
        elif json_szeru_script_db > 0:
            print("      🔍 Díjnet diagnosztika - úgy tűnik, az eredmények nem szerver-oldali HTML-"
                  "táblázatként, hanem beágyazott JSON-ból, kliens-oldali JS-sel épülnek fel - ez "
                  "esetben a jelenlegi HTML-táblázat-kereső logika nem fog működni, más "
                  "megközelítés (a JSON kiolvasása) kellene.")
    # Oszlop-index térkép - az aktívan karbantartott laszlojakab/
    # homeassistant-dijnet integráció JELENLEGI forráskódjából ellenőrizve
    # (1-indexelt oszlopszámaikat 0-indexre átszámolva): 0=szolgáltató,
    # 1=megjelenített név, 2=számlaszám, 3=kiállítás dátuma, 4=(nem
    # használt - a referencia-kód sem hivatkozik rá), 5=fizetési
    # határidő, 6=összeg, 7=fizetési állapot. Ez a KORÁBBI (hibás)
    # verzióhoz képest eggyel el volt tolva mindenhol, és emiatt a
    # minimum-cellaszám ellenőrzés is 9 helyett most helyesen 8.
    MIN_CELLASZAM = 8
    kihagyott_db = 0
    cellaszam_eloszlas = {}  # csak SZÁMOK (darabszám cellánként), nem tartalom - diagnosztikához
    for idx, sor in enumerate(sorok):
        cellak = sor.find_all("td")
        cellaszam_eloszlas[len(cellak)] = cellaszam_eloszlas.get(len(cellak), 0) + 1
        if len(cellak) < MIN_CELLASZAM:
            continue  # fejléc/üres/eltérő szerkezetű sor - kihagyjuk (nem számít bele a kihagyott_db-be, ez várható zaj pl. fejléc-soroknál)
        szoveg = [c.get_text(strip=True) for c in cellak]
        try:
            szamlaszam = szoveg[2]
            kiallitas_nyers = szoveg[3]
            # A 4. (0-indexű) oszlop eddig "nem használt" volt (ld. a
            # fenti oszlop-index-térkép komment) - a felhasználó
            # kifejezett kérésére (MOHU-probléma, ld. "BÉRLŐI KÖRÖK"
            # szekció / szamla_kor_felulbiralas komментje) MOSTANTÓL
            # BEST-EFFORT módon ezt is elmentjük. Lehet, hogy ez a
            # szerződésszám, lehet, hogy valami más - jelen pillanatban
            # nincs megerősített, valós mintánk rá, ezért csak
            # SURFACE-eljük a dashboardon (a felhasználó nézi meg saját
            # szemével), nem próbálunk belőle automatikusan
            # következtetni semmit. A `len(szoveg) > 4` ellenőrzés
            # SZÁNDÉKOSAN védekező - ha egy sor mégsem ennyi cellás
            # lenne (a MIN_CELLASZAM=8 ellenőrzés fentebb ezt már
            # gyakorlatilag kizárja, de itt egy plusz védelmi réteg,
            # hogy ez az apró kiegészítés SOHA ne dobjon kivételt).
            extra_oszlop_nyers = szoveg[4] if len(szoveg) > 4 else ""
            hatarido_nyers = szoveg[5]
            osszeg_nyers = szoveg[6]
            allapot_szoveg = szoveg[7]
        except IndexError:
            # FONTOS - ADATVÉDELEM: itt SOHA nem írjuk ki a sor tényleges
            # celláinak tartalmát (szoveg) - az valódi számla-adatokat
            # (szolgáltató, összeg, számlaszám) tartalmazhat, ami egy
            # PUBLIKUS Actions naplóba kerülne. Csak a cellaszámot írjuk ki.
            print(f"  ⚠️  Díjnet: nem várt oszlopszerkezetű sor, kihagyva "
                  f"(talált cellák száma: {len(cellak)}, {MIN_CELLASZAM} kellene minimum).")
            kihagyott_db += 1
            continue

        # VALIDÁCIÓ - ne csak az oszlopszámot nézzük, hanem hogy az adat
        # is értelmezhető-e. A Díjnet HTML-szerkezete/oszlop-sorrendje
        # bármikor változhat (belső, nem dokumentált végpontok), és egy
        # puszta "elég cella van-e" ellenőrzés simán átengedne egy olyan
        # sort, ahol a cellák tartalma már nem azt jelenti, amit várunk -
        # ez rossz adat (pl. hibás összeg) csendes elmentéséhez vezetne.
        # ADATVÉDELEM: itt sem írjuk ki a sor tartalmát, csak azt, hogy
        # hányadik sorról (sor_index) van szó.
        if not szamlaszam:
            print(f"  ⚠️  Díjnet: nincs számlaszám a(z) {idx}. sorban, kihagyva "
                  "(nem tudnánk stabil azonosítót képezni belőle).")
            kihagyott_db += 1
            continue
        osszeg = _dijnet_osszeg_konvertalas(osszeg_nyers)
        if osszeg is None:
            print(f"  ⚠️  Díjnet: a(z) {idx}. sorban nem sikerült értelmezhető összeget "
                  "kiolvasni, a sor rögzül, de összeg nélkül.")

        talalt_szamlak.append({
            "sor_index": idx,
            "szolgaltato_nyers": szoveg[0],
            "megjelenitett_nev": szoveg[1] or szoveg[0],
            "szamlaszam": szamlaszam,
            "kiallitas_nyers": kiallitas_nyers,
            "extra_oszlop_nyers": extra_oszlop_nyers,
            "hatarido_nyers": hatarido_nyers,
            "osszeg_nyers": osszeg_nyers,
            "allapot_szoveg": allapot_szoveg,
        })

    print(f"  🧾 Díjnet: {len(talalt_szamlak)} érvényes számla-sor az elmúlt {napok_vissza} "
          f"napból (kihagyva: {kihagyott_db}).")
    if not talalt_szamlak and sorok:
        # Volt <tr>, de egyetlen érvényes számla-sor sem lett belőle - a
        # cellaszám-eloszlás (csak darabszámok, nem tartalom) segít
        # eldönteni, hogy a MIN_CELLASZAM küszöb még mindig rossz-e.
        print(f"      🔍 Díjnet diagnosztika - talált <tr> sorok száma: {len(sorok)} | "
              f"cellaszám-eloszlás (cellák/db): {cellaszam_eloszlas}")
    return talalt_szamlak


def dijnet_pdf_letoltese(session, sor_index: int):
    """Best-effort PDF-letöltés egy adott számla-sorhoz. Ha bármi nem a
    várt módon viselkedik (a portál felülete változott, nincs PDF-link
    stb.), None-t ad vissza - ez NEM állítja meg a számla rögzítését,
    csak a PDF-csatolmány marad el az értesítő emailből."""
    try:
        session.get(
            DIJNET_BASE + "/ekonto/control/szamla_select",
            params={"vfw_coll": "szamla_list", "vfw_rowid": sor_index, "exp": "K"},
            timeout=12,
        )
        valasz = session.get(DIJNET_BASE + "/ekonto/control/szamla_letolt", timeout=12)
        valasz.encoding = "iso-8859-2"
        soup = BeautifulSoup(valasz.text, "html.parser")  # ld. _dijnet_vfw_token() kommentje a parser-választásról
        link = soup.select_one('a[href*="szamla_pdf"]')
        if not link or not link.get("href"):
            return None
        pdf_url = DIJNET_BASE + "/ekonto/control/" + link["href"].lstrip("/")
        pdf_valasz = session.get(pdf_url, timeout=20)
        if pdf_valasz.status_code == 200 and pdf_valasz.content:
            return pdf_valasz.content
    except Exception as e:
        print(f"      ⚠️  Díjnet PDF-letöltés sikertelen (nem kritikus): {e}")
    return None


# ════════════════════════════════════════════
#  🚰  VÍZMŰVEK - KÖZVETLEN PORTÁL-LEKÉRDEZÉS (nem email-alapú)
# ════════════════════════════════════════════
# Ugyanaz az elv, mint a Díjnetnél fent: NEM a beérkező emailekre
# támaszkodunk, hanem közvetlenül bejelentkezünk a Te
# ugyfelszolgalat.vizmuvek.hu fiókodba, és onnan olvassuk ki a valódi
# számlaállapotot. Erre azért volt szükség, mert egy élő, bejelentkezett
# böngészős ellenőrzéssel kiderült, hogy ennek a Vízművek-fióknak a
# számlái NEM a Díjneten, és eddigi tapasztalat szerint NEM is a
# figyelt IMAP-postafiókba érkező emailen keresztül érhetők el, hanem
# KIZÁRÓLAG ezen a közvetlen portálon.
#
# EZ A TELJES FOLYAMAT ÉLŐBEN, a felhasználó saját, bejelentkezett
# böngészőjén keresztül (jelszó nélkül - vagy a böngésző saját, már
# hitelesített session-jét felhasználva, a jelszót az asszisztens SOHA
# nem látta/írta be) lett feltérképezve és valódi hálózati hívásokkal
# megerősítve - ez NEM feltételezés, minden alábbi végpont/mezőnév/fejléc
# egy tényleges, sikeres kérés-válasz párral lett ellenőrizve:
#
# 1) BEJELENTKEZÉS: GET /Fiok/Bejelentkezes?ReturnUrl=%2F - KRITIKUS: a
#    kérésnek tartalmaznia kell az "X-Requested-With: XMLHttpRequest"
#    fejlécet, KÜLÖNBEN a szerver a kezdőlapra irányít vissza (0 forms) -
#    ez volt a korábbi verzió hibájának valódi oka (NEM egy hiányzó
#    "bemelegítő" cookie-látogatás, ahogy korábban feltételeztük). A
#    visszaadott HTML-ben lévő form mezőneveit (LoginEmail, LoginPassword,
#    __RequestVerificationToken) továbbra is dinamikusan, a
#    _vizmuvek_login_form_mezok() függvénnyel azonosítjuk be, nem
#    beégetve - a bejelentkező POST-nál ugyanezt az X-Requested-With
#    fejlécet is elküldjük (védekező jelleggel, mert a portál AJAX-
#    végpontjainál ez általános konvenciónak tűnik - ezt magát a login
#    POST-ot nem tudtuk élőben, valódi jelszóval tesztelni, mert az
#    asszisztens sosem ír be jelszót).
#
# 2) SZÁMLALISTA: a táblázat NEM szerver-oldali HTML-ként érkezik, hanem
#    egy kétlépéses JSON AJAX-folyamattal:
#      a) GET /Szamlazas/GetSzamlakDijfizetesSzfszFogyh?_=<cachebuster>
#         (X-Requested-With fejléccel) -> egy view-model JSON, benne a
#         szerződéses folyószámlák listája (FogyH.SzerzFolyoszamlak,
#         elemenként {"VKONT": "..."}) és egy DijfizSzamlak-sablon.
#      b) a view-modelben a "KivVKONT" mezőt beállítjuk a LISTA UTOLSÓ
#         elemének VKONT-jára (a felhasználó kifejezett utasítására:
#         "mindig a legutolsó. Többivel ne foglalkozz." - ha valakinek
#         több szerződéses folyószámlája van, csak az utolsóval
#         foglalkozunk, a többivel szándékosan nem).
#      c) a TELJES, mutált view-modelt visszaküldjük JSON body-ként:
#         POST /Szamlazas/GetSzamlakDijfizetesSzamlak, fejlécek:
#         Content-Type: application/json, X-Requested-With: XMLHttpRequest,
#         és - EZ VOLT A KULCS-FELFEDEZÉS - egy "VerificationToken" nevű
#         egyedi fejléc (NEM "RequestVerificationToken", NEM a szokásos
#         "X-CSRF-TOKEN"), aminek az értéke a betöltött oldal
#         __RequestVerificationToken rejtett mezőjének értéke. Enélkül a
#         végpont HTTP 500-at ad.
#      d) a válasz DataModel.DijfizSzamlak.SzamlaLista tömbje tartalmazza
#         a valódi számlasorokat, VALÓDI (8 tényleges számlával
#         összevetve megerősített) mezőnevekkel: INVID, MEGNEV, INV_DATE,
#         FAEDN (fizetési határidő), AMOUNT (már szám, nem szöveg - negatív
#         stornó számláknál), STATUS_MEGNEV (pl. "Kiegyenlített" /
#         "Lejárt tartozás" / "Befizetésre vár"), ARCHIV_ID, ARC_DOC_ID,
#         és egy beágyazott ArchivItem.AR_OBJECT_MEGNEV (a PDF-fájlnév
#         alapja).
#
# 3) PDF-LETÖLTÉS: szintén élőben, ténylegesen letöltött (136 KB-os, valódi)
#    PDF-fel megerősítve:
#      a) POST /Home/DownloadPDFFromSAP, JSON body:
#         {"ARCHIVE_ID": sor["ARCHIV_ID"], "ARC_DOC_ID": sor["ARC_DOC_ID"],
#          "filename": sor["ArchivItem"]["AR_OBJECT_MEGNEV"]} (ugyanazok a
#         fejlécek, mint fent) -> JSON {"FileGuid": ..., "FileName": ...,
#         "ContentType": "application/pdf"}.
#      b) GET /Home/Download?fileGuid=<guid>&filename=<...>&contentType=
#         application/pdf -> a PDF nyers bájtjai. Ez a lépés a portál
#         eredeti feltérképezése szerint néha aszinkron (első próbálkozásra
#         HTTP 503-at adhat) - ezért rövid késleltetéses újrapróbálkozással
#         hívjuk (ld. vizmuvek_pdf_letoltese()).
VIZMUVEK_BASE = "https://ugyfelszolgalat.vizmuvek.hu"
VIZMUVEK_BEJELENTKEZES_URL = VIZMUVEK_BASE + "/Fiok/Bejelentkezes?ReturnUrl=%2F"
VIZMUVEK_SZAMLAK_OLDAL_URL = VIZMUVEK_BASE + "/Szamlazas/FizetendoSzamlak"
VIZMUVEK_SZFSZ_URL = VIZMUVEK_BASE + "/Szamlazas/GetSzamlakDijfizetesSzfszFogyh"
VIZMUVEK_SZAMLALISTA_URL = VIZMUVEK_BASE + "/Szamlazas/GetSzamlakDijfizetesSzamlak"
VIZMUVEK_PDF_INDITAS_URL = VIZMUVEK_BASE + "/Home/DownloadPDFFromSAP"
VIZMUVEK_PDF_LETOLTES_URL = VIZMUVEK_BASE + "/Home/Download"

# Ezekre a (kisbetűs) kulcsszavakra KEZDŐDŐ állapot-szöveg jelenti azt,
# hogy egy Vízművek-számla ki van fizetve/rendezve - ezt egy élő,
# bejelentkezett böngészős ellenőrzéssel láttuk (a portál ténylegesen
# "Kiegyenlített" / "Befizetésre vár" / "Lejárt tartozás" feliratokat
# használ - a "Stornó számla" tételek is "Kiegyenlített"-ként jelennek
# meg, mert a portál már nettósítva/rendezve mutatja őket). Minden más
# állapot-szöveg fizetetlennek számít.
VIZMUVEK_FIZETVE_KULCSSZAVAK = ("kiegyenlített", "rendezett", "fizetve")


def _vizmuvek_fizetve_e(allapot_szoveg: str) -> bool:
    szoveg = (allapot_szoveg or "").strip().lower()
    return any(szoveg.startswith(k) for k in VIZMUVEK_FIZETVE_KULCSSZAVAK)


def _vizmuvek_login_form_mezok(soup):
    """Megkeresi a bejelentkező-oldal formját (azt, amelyikben van
    type="password" mező), és visszaadja: (form_elem, mezok_dict,
    felhasznalonev_mezonev, jelszo_mezonev). A mezok_dict MINDEN, a
    formban talált input mezőt tartalmazza a jelenlegi (rejtett mezőknél
    - pl. CSRF-token - a szerver által előre beállított) értékével, hogy
    ezeket változtatás nélkül vissza tudjuk küldeni. Bármelyik
    visszatérési érték lehet None, ha nem sikerül beazonosítani - ezt a
    hívó fél kezeli (nem dob kivételt)."""
    for form in soup.find_all("form"):
        jelszo_input = form.find("input", {"type": "password"})
        if not jelszo_input or not jelszo_input.get("name"):
            continue
        mezok = {}
        felhasznalonev_mezonev = None
        for inp in form.find_all("input"):
            nev = inp.get("name")
            if not nev:
                continue
            tipus = (inp.get("type") or "text").lower()
            mezok[nev] = inp.get("value") or ""
            if tipus == "password":
                continue
            if tipus in ("text", "email") and felhasznalonev_mezonev is None:
                felhasznalonev_mezonev = nev
        return form, mezok, felhasznalonev_mezonev, jelszo_input.get("name")
    return None, {}, None, None


def _vizmuvek_user_logged_attr(soup):
    """A <html ... user-logged="be"/"ki" ...> attribútumot olvassa ki (ha
    van) - ez egy ÉLŐ, bejelentkezett böngészős ellenőrzéssel megismert,
    a portál által ténylegesen kiírt jelző arról, hogy a szerver
    bejelentkezettnek látja-e az adott kérést (user-logged="out", ha
    nincs bejelentkezve). Megbízhatóbb jel, mint pusztán a jelszó-mező
    hiánya/jelenléte, ezért ezt is felhasználjuk a diagnosztikában és a
    sikeresség-ellenőrzésben."""
    html_tag = soup.find("html")
    return html_tag.get("user-logged") if html_tag else None


def vizmuvek_bejelentkezes():
    """Bejelentkezik a ugyfelszolgalat.vizmuvek.hu portálra, és a
    bejelentkezett requests.Session()-t adja vissza - vagy None-t, ha
    nincs beállítva a hozzáférés, vagy a bejelentkezés sikertelen.

    FONTOS - ÉLŐ TESZTTEL MEGERŐSÍTETT VISELKEDÉS (ld. a szekció elején
    lévő részletes komment): a bejelentkező URL-re küldött kérésnek
    tartalmaznia kell az "X-Requested-With: XMLHttpRequest" fejlécet,
    KÜLÖNBEN a szerver - session-cookie-tól függetlenül - egyszerűen a
    kezdőlapra irányít vissza (0 forms). Ez volt a korábbi ("bemelegítő
    látogatás hiányzik") diagnózis valódi, végleges javítása."""
    if not (VIZMUVEK_USER and VIZMUVEK_JELSZO):
        return None

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "hu-HU,hu;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
    })
    try:
        valasz = session.get(
            VIZMUVEK_BEJELENTKEZES_URL, timeout=15,
            headers={"Referer": VIZMUVEK_BASE + "/"},
        )
        soup = BeautifulSoup(valasz.text, "html.parser")
        form, mezok, felhasznalonev_mezo, jelszo_mezo = _vizmuvek_login_form_mezok(soup)

        if not form or not felhasznalonev_mezo or not jelszo_mezo:
            # ADATVÉDELEM: csak mezőNEVEKET és típusokat írunk ki, sosem
            # a mezők/oldal tényleges tartalmát/értékét.
            osszes_input = [
                f"{i.get('name')}(type={i.get('type') or 'text'})"
                for i in soup.find_all("input") if i.get("name")
            ]
            cim_elem = soup.find("title")
            print(f"  ⚠️  Vízművek bejelentkezés: nem sikerült beazonosítani a "
                  f"bejelentkező-űrlap mezőit - státuszkód: {valasz.status_code} | "
                  f"végső URL: {valasz.url} | oldal <title>: "
                  f"{cim_elem.get_text(strip=True) if cim_elem else '(nincs)'} | "
                  f"user-logged attribútum: {_vizmuvek_user_logged_attr(soup)!r} | "
                  f"talált <form> elemek száma: {len(soup.find_all('form'))} | "
                  f"talált <input name=... type=...> mezők: {osszes_input}")
            return None

        mezok[felhasznalonev_mezo] = VIZMUVEK_USER
        mezok[jelszo_mezo] = VIZMUVEK_JELSZO

        action = form.get("action") or VIZMUVEK_BEJELENTKEZES_URL
        if action.startswith("/"):
            action = VIZMUVEK_BASE + action
        elif not action.startswith("http"):
            action = VIZMUVEK_BEJELENTKEZES_URL

        valasz2 = session.post(action, data=mezok, timeout=15, headers={"Referer": valasz.url})
        soup2 = BeautifulSoup(valasz2.text, "html.parser")
        meg_van_jelszo_mezo = soup2.find("input", {"type": "password"}) is not None
        user_logged_attr = _vizmuvek_user_logged_attr(soup2)

        if meg_van_jelszo_mezo or user_logged_attr == "out":
            cim_elem = soup2.find("title")
            print(f"  ⚠️  Vízművek bejelentkezés sikertelen (rossz felhasználónév/jelszó, vagy "
                  f"a portál felülete megváltozott) - státuszkód: {valasz2.status_code} | "
                  f"végső URL: {valasz2.url} | oldal <title>: "
                  f"{cim_elem.get_text(strip=True) if cim_elem else '(nincs)'} | "
                  f"user-logged attribútum: {user_logged_attr!r}")
            return None

        print("  ✅ Vízművek bejelentkezés sikeres.")
        return session
    except Exception as e:
        print(f"  ⚠️  Vízművek bejelentkezési hiba: {e}")
        return None


def _vizmuvek_verification_token(soup):
    """A __RequestVerificationToken rejtett mezőt olvassa ki egy
    bejelentkezett oldal HTML-jéből - ezt kell visszaküldeni a
    "VerificationToken" egyedi HTTP fejlécben minden további JSON AJAX-
    hívásnál. Ez volt a kulcs-felfedezés, ami feloldotta a számlalista-
    végpont korábbi HTTP 500 hibáját (ld. a szekció elején lévő
    komment) - a fejléc neve SZÁNDÉKOSAN "VerificationToken", NEM
    "RequestVerificationToken" és NEM "X-CSRF-TOKEN"."""
    mezo = soup.find("input", {"name": "__RequestVerificationToken"})
    return mezo.get("value") if mezo and mezo.get("value") else None


def vizmuvek_szamlak_lekerdezese(session):
    """Lekérdezi a bejelentkezett fiókhoz tartozó "Fizetendő számlák"
    listát a portál valódi, élőben feltérképezett és megerősített
    kétlépéses JSON AJAX-folyamatával (ld. a szekció elején lévő
    részletes komment). Egy (talalt_szamlak, token) párost ad vissza - a
    tokenre a PDF-letöltéshez (vizmuvek_pdf_letoltese()) is szükség van,
    ezért adjuk vissza itt, nem kérdezzük le még egyszer feleslegesen."""
    # 1) A számlaoldal HTML-jéből kiolvassuk az érvényes anti-forgery
    #    tokent - ugyanezt küldi vissza a portál saját JS-e is minden
    #    AJAX-híváshoz "VerificationToken" fejlécként.
    oldal_valasz = session.get(VIZMUVEK_SZAMLAK_OLDAL_URL, timeout=15)
    oldal_soup = BeautifulSoup(oldal_valasz.text, "html.parser")
    token = _vizmuvek_verification_token(oldal_soup)
    if not token:
        # ADATVÉDELEM: itt SOHA nem írjuk ki a válasz nyers tartalmát -
        # csak szerkezeti infót (státuszkód, URL, cím, jelzők).
        cim_elem = oldal_soup.find("title")
        print(f"  ⚠️  Vízművek: nem található __RequestVerificationToken a számlaoldalon - "
              f"státuszkód: {oldal_valasz.status_code} | végső URL: {oldal_valasz.url} | "
              f"oldal <title>: {cim_elem.get_text(strip=True) if cim_elem else '(nincs)'} | "
              f"user-logged attribútum: {_vizmuvek_user_logged_attr(oldal_soup)!r}")
        return [], None

    ajax_fejlecek = {
        "X-Requested-With": "XMLHttpRequest",
        "VerificationToken": token,
    }

    # 2) View-model lekérése - ebben szerepelnek a szerződéses
    #    folyószámlák (FogyH.SzerzFolyoszamlak) és egy DijfizSzamlak-sablon.
    cachebuster = str(int(time.time() * 1000))
    szfsz_valasz = session.get(
        VIZMUVEK_SZFSZ_URL, params={"_": cachebuster}, timeout=15, headers=ajax_fejlecek,
    )
    try:
        model = szfsz_valasz.json()
    except ValueError:
        print(f"  ⚠️  Vízművek: a szerződéses folyószámla lekérdezés nem JSON választ adott - "
              f"státuszkód: {szfsz_valasz.status_code} | végső URL: {szfsz_valasz.url}")
        return [], token

    folyoszamlak = ((model or {}).get("FogyH") or {}).get("SzerzFolyoszamlak") or []
    if not folyoszamlak:
        print(f"  ⚠️  Vízművek: nincs szerződéses folyószámla a fiókhoz - "
              f"státuszkód: {szfsz_valasz.status_code} | "
              f"talált JSON kulcsok: {list((model or {}).keys())}")
        return [], token

    # A felhasználó kifejezett utasítására MINDIG a lista UTOLSÓ elemét
    # használjuk ("mindig a legutolsó. Többivel ne foglalkozz.") - ha
    # több szerződéses folyószámla is van, a többivel szándékosan nem
    # foglalkozunk.
    model["KivVKONT"] = folyoszamlak[-1].get("VKONT")

    # 3) A TELJES (mutált) view-modelt visszaküldjük - a végpont ezt
    #    "echo-back" stílusban várja (a teljes korábban kapott objektumot,
    #    csak a KivVKONT mezővel módosítva), nem egy minimál/konstruált
    #    payloadot.
    lista_valasz = session.post(
        VIZMUVEK_SZAMLALISTA_URL, json=model, timeout=20,
        headers={**ajax_fejlecek, "Content-Type": "application/json"},
    )
    try:
        lista_json = lista_valasz.json()
    except ValueError:
        print(f"  ⚠️  Vízművek: a számlalista lekérdezés nem JSON választ adott - "
              f"státuszkód: {lista_valasz.status_code} | végső URL: {lista_valasz.url}")
        return [], token

    sorok = (
        ((lista_json or {}).get("DataModel") or {}).get("DijfizSzamlak") or {}
    ).get("SzamlaLista") or []

    print(f"  🚰 Vízművek: {len(sorok)} érvényes számla-sor.")
    if not sorok:
        # ADATVÉDELEM: itt is csak szerkezeti infót írunk ki.
        print(f"      🔍 Vízművek diagnosztika - státuszkód: {lista_valasz.status_code} | "
              f"végső URL: {lista_valasz.url} | "
              f"válasz JSON kulcsok: {list((lista_json or {}).keys())}")

    return sorok, token


def vizmuvek_pdf_letoltese(session, token, sor, probalkozasok=3, varakozas_masodperc=2):
    """Best-effort PDF-letöltés egy adott Vízművek-számlasorhoz, a portál
    élőben megerősített, kétlépéses folyamatával (ld. a szekció elején
    lévő komment). Ha bármi nem a várt módon viselkedik (a portál
    felülete változott, hiányzó azonosítók stb.), None-t ad vissza - ez
    NEM állítja meg a számla rögzítését, csak a PDF-csatolmány marad el."""
    try:
        archiv_id = sor.get("ARCHIV_ID")
        arc_doc_id = sor.get("ARC_DOC_ID")
        fajlnev = (sor.get("ArchivItem") or {}).get("AR_OBJECT_MEGNEV") or sor.get("AR_OBJECT_MEGNEV")
        if not (archiv_id and arc_doc_id):
            return None

        fejlecek = {
            "X-Requested-With": "XMLHttpRequest",
            "VerificationToken": token or "",
            "Content-Type": "application/json",
        }
        inditas_valasz = session.post(
            VIZMUVEK_PDF_INDITAS_URL,
            json={"ARCHIVE_ID": archiv_id, "ARC_DOC_ID": arc_doc_id, "filename": fajlnev},
            timeout=15, headers=fejlecek,
        )
        try:
            inditas_json = inditas_valasz.json()
        except ValueError:
            return None

        file_guid = inditas_json.get("FileGuid")
        if not file_guid:
            return None
        file_name = inditas_json.get("FileName") or fajlnev or "szamla.pdf"
        content_type = inditas_json.get("ContentType") or "application/pdf"

        # A tényleges letöltés a feltérképezés szerint néha aszinkron
        # (HTTP 503 az első próbálkozásra) - ezért rövid késleltetéses
        # újrapróbálkozással hívjuk.
        for kiserlet in range(probalkozasok):
            letoltes_valasz = session.get(
                VIZMUVEK_PDF_LETOLTES_URL,
                params={"fileGuid": file_guid, "filename": file_name, "contentType": content_type},
                timeout=20,
            )
            if letoltes_valasz.status_code == 200 and letoltes_valasz.content:
                return letoltes_valasz.content
            if kiserlet < probalkozasok - 1:
                time.sleep(varakozas_masodperc)
    except Exception as e:
        print(f"      ⚠️  Vízművek PDF-letöltés sikertelen (nem kritikus): {e}")
    return None


# ════════════════════════════════════════════
#  👥  3 CÍMZETTI KÖR: KÖNYVELŐ / BÉRLŐ / TULAJDONOS
# ════════════════════════════════════════════
# A Díjneten/Vízműveken érkező számlák két BÉRLŐI körhöz (két külön "cég")
# tartoznak - a besorolást a felhasználó a dashboardon (szamlak.html
# "Bérlői körök" panelje) végzi:
#   - Díjnet: kibocsátónként (a "Számlakibocsátói azonosító" alapján,
#     ld. allapot["kibocsato_csoportok"]) - EZ SZÁMLÁNKÉNT ELTÉRHET, mert
#     egy Díjnet-fiókban több kibocsátó (több cég/cím) számlája is
#     keveredhet.
#   - Vízművek: EGYBEN, az egész fiók egy körhöz tartozik (ld.
#     allapot["vizmuvek_kor"]) - a felhasználó kifejezett döntése szerint
#     itt NINCS számlánkénti szétválasztás, még akkor sem, ha a fiók több
#     mérőt/felhasználási helyet is tartalmaz.
#   - EGYEDI (per-számla) FELÜLBÍRÁLÁS (MOHU-probléma): a fenti két
#     szabály csak "alapértelmezés" - ha a felhasználó egy KONKRÉT
#     számlára kézzel kör-felülbírálást állított be a dashboardon
#     (allapot["szamla_kor_felulbiralas"]), az MINDIG ERŐSEBB (ld.
#     _szamla_kor_override() és a "szamla_kor_felulbiralas" mező fenti,
#     részletes kommentjét a visszafejt()-ben - ott van kifejtve, MIÉRT
#     kézi felülbírálás lett a megoldás, nem egy automatikus
#     szöveg-elemzés).
#
# A rendszer MOSTANTÓL HÁROM, EGYMÁSTÓL FÜGGETLEN cím(lista)-kört ismer:
#   1) KÖNYVELŐ (konyvelo_emailek): NEM kap számla-adatot/csatolmányt
#      ebből a rendszerből - a tulajdonos a számlaanyagot egy KÜLÖN,
#      kézzel megosztott Google Drive mappán keresztül adja át neki. Az
#      EGYETLEN dolog, amit itt kap: egy egyszerű, havi, hónap-végi
#      emlékeztető-email (ld. main() "Könyvelő - havi emlékeztető"
#      szekcióját, konyvelo_emlekezteto_email_html()).
#   2) BÉRLŐ (kor_a/kor_b, kor_emailek): CSAK az időszakos/kézi
#      "jelenleg fizetetlen számlák" ÖSSZESÍTŐJÉT kapja (ld.
#      "Fix-napi tételes összesítő" + az új, manuális "Küldés most"
#      gombok) - SZÁNDÉKOSAN NEM kap azonnali, számlánkénti "új számla"
#      értesítőt (ez korábban így volt, ld. lentebb a
#      _uj_szamla_ertesites_kuldese() kommentjét, hogy miért szűnt meg).
#   3) TULAJDONOS (tulajdonos_emailek): Ő kapja MOSTANTÓL az AZONNALI "új
#      számla érkezett" értesítést, MINDEN számláról, forrástól/kör-
#      besorolástól FÜGGETLENÜL (ld. _uj_szamla_ertesites_kuldese()) - ÉS
#      minden bérlői-kör-összesítő EGY MÁSOLATÁT is (ld.
#      _tulajdonos_osszesito_masolat()).
#
# Amíg egy kibocsátó (ill. a Vízművek-fiók) nincs besorolva egy bérlői
# körbe, az onnan érkező számlák "fuggoben" állapotban vannak: rögzülnek
# és PDF-jük is letöltődik, ÉS a TULAJDONOS ettől függetlenül azonnal
# értesítést kap róluk (ld. fent) - csak a BÉRLŐI-kör-összesítőkbe nem
# kerülnek bele, amíg a felhasználó be nem sorolja a kibocsátót/fiókot
# valamelyik körbe a dashboardon.
def _dijnet_kor_meghatarozasa(allapot: dict, invoice_id: str, kibocsato_azonosito: str) -> str:
    """"kor_a" / "kor_b" / "fuggoben". Előbb a SZÁMLÁNKÉNTI kézi
    felülbírálást nézi (ld. _szamla_kor_override() - MOHU-probléma miatt
    ez MINDIG erősebb), csak ha az nincs beállítva, esik vissza a
    kibocsátó-szintű alapértelmezésre."""
    felulbiralas = _szamla_kor_override(allapot, invoice_id)
    if felulbiralas:
        return felulbiralas
    if not kibocsato_azonosito:
        return "fuggoben"
    return allapot.get("kibocsato_csoportok", {}).get(kibocsato_azonosito) or "fuggoben"


def _vizmuvek_kor_meghatarozasa(allapot: dict, invoice_id: str) -> str:
    """"kor_a" / "kor_b" / "fuggoben". Ugyanaz a felülbírálás-elsőbbség,
    mint a Díjnetnél fent (ld. _dijnet_kor_meghatarozasa() kommentje) - itt
    a fiók-szintű allapot["vizmuvek_kor"] az alapértelmezés."""
    felulbiralas = _szamla_kor_override(allapot, invoice_id)
    if felulbiralas:
        return felulbiralas
    return allapot.get("vizmuvek_kor") or "fuggoben"


def _szamla_kor_override(allapot: dict, invoice_id: str):
    """A SZÁMLÁNKÉNTI kézi kör-felülbírálás lekérdezése (ld. a
    "szamla_kor_felulbiralas" mező részletes kommentjét visszafejt()-ben) -
    "kor_a"/"kor_b"/None. Ez a MOHU-probléma biztonságos megoldása: amíg
    nincs elég valós minta egy automatikus szöveg-elemzéshez, a
    felhasználó a dashboardon KÉZZEL, számlánként dönt - ez itt mindig
    erősebb, mint a kibocsátó-/fiók-szintű alapértelmezés."""
    return (allapot.get("szamla_kor_felulbiralas") or {}).get(invoice_id) or None


def _emailek_egyesitese(*listak):
    """Több email-cím-listát egyesít - kisbetűsítve hasonlítja össze (a
    duplikátum-szűréshez), de az EREDETI írásmódot tartja meg a
    kimenetben, és megtartja a beérkezési sorrendet. Ez adja a "UNIÓ"
    logikát a titkosított állapotban tárolt (dashboardos) és a régi,
    GitHub Secret-alapú kör-email(ek) között (ld. KOR_EMAIL_CIMEK fenti
    kommentje, "3 CÍMZETTI KÖR" bevezetése)."""
    latott = set()
    eredmeny = []
    for lista in listak:
        for cim in (lista or []):
            cim_tiszta = (cim or "").strip()
            if not cim_tiszta:
                continue
            kulcs = cim_tiszta.lower()
            if kulcs in latott:
                continue
            latott.add(kulcs)
            eredmeny.append(cim_tiszta)
    return eredmeny


def _kor_cimzettek(allapot: dict, kor_kulcs: str):
    """A megadott bérlői kör (kor_a/kor_b) ÖSSZES email-címét adja vissza
    listaként: a titkosított állapotban (dashboardon) tárolt lista ÉS a
    régi, GitHub Secret-alapú cím UNIÓJA (ld. KOR_EMAIL_CIMEK fenti
    kommentje) - amíg valaki nem törli a régi SZAMLA_KOR_A_EMAIL/
    SZAMLA_KOR_B_EMAIL secretet, az onnan jövő cím TOVÁBBRA IS kap
    emailt, hogy egy átállás közben senki ne maradjon csendben ki a
    listáról."""
    titkositott_lista = (allapot.get("kor_emailek") or {}).get(kor_kulcs) or []
    legacy = KOR_EMAIL_CIMEK.get(kor_kulcs) or ""
    return _emailek_egyesitese(titkositott_lista, [legacy] if legacy else [])


def _cimzett_string(email_lista):
    """Egy email-cím-listát EGYETLEN, vesszővel elválasztott 'To' fejléc-
    értékké alakít (több cím EGY emailben, egy SMTP-hívással) - vagy
    None-t, ha a lista üres. Az email_kuldes() egyetlen 'cimzett' stringet
    vár, ezért ez a csatolópont a listás (több-cím) és a régi,
    egy-cím-alapú API között."""
    egyesitett = _emailek_egyesitese(email_lista)
    if not egyesitett:
        return None
    return ", ".join(egyesitett)


def _uj_szamla_ertesites_kuldese(rekord: dict, pdf_bytes, statisztika: dict, allapot: dict, kor_kulcs=None):
    """Egységesen kezeli az "új számla" AZONNALI értesítő email kiküldését -
    ezt hívja a Díjnet- és a Vízművek-ág (az IMAP-os/MVM-ág külön, saját
    maga küld tulajdonosi másolatot, ld. main()).

    FONTOS VÁLTOZÁS ("3 CÍMZETTI KÖR" bevezetése): korábban ez a függvény
    a bérlői kör (kor_a/kor_b) email-címére küldte AZONNAL az "új számla"
    értesítőt, és a "fuggoben" (még be nem sorolt) számláknál teljesen
    kihagyta a küldést. A felhasználó kifejezett kérésére ez megszűnt: a
    BÉRLŐ mostantól CSAK az időszakos/kézi összesítőt kapja (ld. "3
    CÍMZETTI KÖR" szekció eleje) - nem kell neki minden egyes beérkező
    számláról külön emailt kapnia. Az AZONNALI "új számla" értesítést
    mostantól a TULAJDONOS kapja, MINDEN számláról (kör-besorolástól/
    "fuggoben" állapottól FÜGGETLENÜL) - ő az, akinek tényleg szüksége
    van rá, hogy azonnal lássa, mi érkezett.

    kor_kulcs: csak INFORMATÍV/naplózási célra kapja meg (pl. hogy a log
    mutassa, egy "fuggoben" kibocsátóról van-e szó) - a tényleges
    címzett-döntésben már NEM játszik szerepet."""
    if kor_kulcs == "fuggoben":
        print(f"      ⏳ Új számla érkezett egy még bérlői körbe nem sorolt kibocsátótól/fiókból "
              f"({rekord['targy']}) - a bérlői-kör-összesítőkbe majd csak a besorolás után kerül "
              "bele, de a tulajdonosi azonnali értesítés ettől függetlenül kimegy.")
    tulajdonos_cimzett = _cimzett_string(allapot.get("tulajdonos_emailek"))
    if not tulajdonos_cimzett:
        print(f"      ℹ️  Nincs beállítva tulajdonosi email-cím (dashboard 'Tulajdonos' kezelése) - "
              f"az azonnali 'új számla' értesítő NEM megy ki senkinek: {rekord['targy']}")
        return
    statisztika["email_ertesitesek"] += 1
    email_kuldes(
        f"📄 Új számla – {rekord['szolgaltato_nev']}",
        uj_szamla_email_html(rekord),
        [(f"{rekord.get('szamlaszam') or rekord['szolgaltato']}.pdf", pdf_bytes)] if pdf_bytes else None,
        cimzett=tulajdonos_cimzett,
    )


def _kor_utolagos_ertesites_ha_kell(rid: str, rekord: dict, allapot: dict, statisztika: dict, kor_kulcs: str):
    """MÁR ISMERT (nem most érkezett) számláknál hívjuk, miután frissen
    újraszámoltuk a "kor" mezőjét.

    TÖRTÉNETI HÁTTÉR / MIÉRT NO-OP MOSTANTÓL: ez a mechanizmus korábban
    egy AZONNALI, bérlői-kör-címre szóló "új számla" emailt küldött ki,
    amint egy korábban "fuggoben" kibocsátó/fiók végre besorolásra
    kerül egy bérlői körbe (ld. dashboard "utólagos értesítő email is
    menjen..." kapcsolója). A "3 CÍMZETTI KÖR" bevezetésével (ld.
    _uj_szamla_ertesites_kuldese() fenti kommentje) a BÉRLŐ már
    EGYÁLTALÁN nem kap azonnali, számlánkénti emailt - csak a
    TULAJDONOS, és ő ezt MÁR megkapta, amikor a számla ELŐSZÖR bekerült
    (a kör-besorolástól teljesen függetlenül, ld. fent). Ha itt MOST is
    elküldenénk, az egy FELESLEGES DUPLIKÁTUM lenne a tulajdonosnak.
    A függvény ezért csak a jelzőt törli (hogy ne maradjon örökre
    "bekapcsolva" állapotban), tényleges küldés nélkül - a dashboard
    kapcsolóját SZÁNDÉKOSAN nem távolítottuk el (visszafelé-
    kompatibilitás régebbi mentett állapotokkal), de gyakorlati hatása
    mostantól nincs."""
    if not rekord.get("ertesites_szukseges"):
        return
    if kor_kulcs == "fuggoben":
        # Még mindig nincs besorolva - a jelzőt SZÁNDÉKOSAN nem töröljük,
        # hogy a következő futás újra megnézze, amint tényleg besorolásra
        # kerül (bár - ld. fent - ma már ennek nincs tényleges hatása).
        return
    rekord["ertesites_szukseges"] = False


def _fizetetlen_szamlak_korhoz(szamlak: dict, kor_kulcs):
    """Az ÖSSZES, MÉG FIZETETLEN (azaz "fizetendő" - határidőn belüli VAGY
    már lejárt) számlát adja vissza [(rid, rekord), ...] alakban, egy adott
    bérlői körhöz szűrve. kor_kulcs=None esetén MINDEN kört (és a be nem
    sorolt/"fuggoben" tételeket is) visszaadja - ezt használja a tulajdonos
    "minden fizetetlen, minden kör" összesítője.

    FONTOS (5. pont - általánosítás): ez a rekord "kor" MEZŐJE alapján
    szűr, NEM forrás-specifikus (nem néz külön Díjnet/Vízművek ágat) -
    ha egy jövőbeli harmadik forrás is beállítja a saját rekordjain a
    "kor" mezőt, az automatikusan idekerül, további speciális eset
    hozzáadása nélkül."""
    return [
        (rid, r) for rid, r in szamlak.items()
        if not r.get("fizetve") and (kor_kulcs is None or r.get("kor") == kor_kulcs)
    ]


def csatolmanyok_osszegyujtese(allapot: dict, rid_rekord_lista):
    """rid_rekord_lista: [(rid, rekord), ...]. Elsőként a MÁR TÁROLT
    (titkosított állapotban lévő) PDF-eket használja - ez lefedi mind az
    email-, mind a Díjnet-/Vízművek-eredetű számlákat. Csak azokhoz
    próbál meg élőben, IMAP-on keresztül PDF-et szerezni, amikhez sem
    tárolt PDF, sem uid nincs elmentve - ez egy ritka, visszafelé-
    kompatibilitási tartalék ág.

    (Ez korábban main() belsejében, zárt függvényként élt - a "3
    CÍMZETTI KÖR" funkció (bérlő/tulajdonos "Küldés most" gombjai) miatt
    modul-szintre került, hogy main()-en KÍVÜLI segédfüggvények (ld.
    _osszesito_kuldese() lentebb) is használhassák.)"""
    csatolmanyok = []
    potlando = []
    for rid, r in rid_rekord_lista:
        b64 = allapot.get("pdf_adatok", {}).get(rid)
        if b64:
            fajlnev = f"{r.get('szamlaszam') or r['szolgaltato']}_szamla.pdf"
            csatolmanyok.append((fajlnev, base64.b64decode(b64)))
        elif r.get("uid"):
            potlando.append((rid, r))

    if potlando:
        try:
            conn2 = imap_kapcsolat()
            for rid, r in potlando:
                msg = uid_letoltese(conn2, r["uid"].encode())
                if msg is None:
                    continue
                pdf_nev, pdf_bytes = pdf_csatolmany(msg)
                if pdf_bytes:
                    csatolmanyok.append((pdf_nev or f"{r['szolgaltato']}_szamla.pdf", pdf_bytes))
            conn2.logout()
        except Exception as e:
            print(f"  ⚠️  PDF-ek pótlólagos IMAP-visszatöltése sikertelen: {e}")
    return csatolmanyok


def _osszesito_kuldese(allapot: dict, erintett, cim_resz: str, bevezeto: str, cimzett, statisztika: dict, pdf_csatolas: bool = True):
    """Közös segédfüggvény MINDEN "fizetetlen számlák összesítője" jellegű
    emailhez - a küszöb-alapú (2. pont), a fix-napi (2b), és az ÚJ,
    manuális "Küldés most" gombok (2d) is ezt hívják. erintett: [(rid,
    rekord), ...]. pdf_csatolas=False esetén SZÁNDÉKOSAN nem gyűjtünk/
    csatolunk PDF-et (ld. a dashboard "PDF-ek csatolása" jelölőnégyzete,
    7. pont - ez a manuális küldéseknél a felhasználó döntése)."""
    erintett_rekordok = [r for _, r in erintett]
    vegosszeg = sum(r["osszeg"] or 0 for r in erintett_rekordok)
    provider_osszegek = {}
    for r in erintett_rekordok:
        provider_osszegek[r["szolgaltato_nev"]] = (
            provider_osszegek.get(r["szolgaltato_nev"], 0) + (r["osszeg"] or 0)
        )
    csatolmanyok = csatolmanyok_osszegyujtese(allapot, erintett) if pdf_csatolas else None
    statisztika["email_ertesitesek"] += 1
    email_kuldes(
        f"📅 Fizetendő számlák összesítője{cim_resz} – {len(erintett_rekordok)} db – {forint(vegosszeg)}",
        osszesito_email_html(
            erintett_rekordok, vegosszeg, provider_osszegek,
            cim=f"📅 Fizetendő számlák összesítője{cim_resz}",
            bevezeto=bevezeto,
        ),
        csatolmanyok,
        cimzett=cimzett,
    )
    print(f"      📤 Összesítő elküldve{cim_resz} ({len(erintett_rekordok)} számla).")


def _tulajdonos_osszesito_masolat(allapot: dict, erintett, cim_resz: str, statisztika: dict, pdf_csatolas: bool):
    """A tulajdonos MINDEN bérlői-kör-összesítőről automatikus MÁSOLATOT
    kap (ld. "3 CÍMZETTI KÖR" szekció, 2. pont/b) - ezt hívjuk MINDEN
    olyan helyen, ahol egy bérlői körnek tényleg kiment egy összesítő
    (ha a körnek nincs email-címe VAGY nincs mit összesítenie, ide sem
    jutunk el - "erintett" ilyenkor üres, vagy a hívó ezt már kiszűrte)."""
    if not erintett:
        return
    tulajdonos_cimzett = _cimzett_string(allapot.get("tulajdonos_emailek"))
    if not tulajdonos_cimzett:
        return
    _osszesito_kuldese(
        allapot, erintett, cim_resz,
        "<p>Ez egy bérlői kör összesítőjének MÁSOLATA - a tulajdonos minden "
        "bérlői-kör-összesítőről automatikusan másolatot kap:</p>",
        tulajdonos_cimzett, statisztika, pdf_csatolas,
    )


def _berlo_kor_osszesito_kuldese_most(allapot: dict, szamlak: dict, kor_kulcs: str, statisztika: dict, pdf_csatolas: bool):
    """A dashboard bérlői-kör "Küldés most" gombja hívja (ld. 6/7. pont,
    SZAMLA_BERLO_OSSZESITO_KOR workflow_dispatch input) - a szokásos,
    fix-napi ütemezéstől FÜGGETLENÜL, AZONNAL elküldi a megadott kör
    jelenleg fizetetlen számláinak összesítőjét, és a tulajdonosnak is
    másolatot küld róla (ugyanaz a szabály, mint az ütemezett küldésnél)."""
    cimzett = _cimzett_string(_kor_cimzettek(allapot, kor_kulcs))
    if not cimzett:
        print(f"      ⚠️  A(z) '{kor_kulcs}' bérlői körnek nincs beállítva egyetlen email-címe sem "
              "(dashboard 'Bérlői körök' email-kezelése) - manuális összesítő kihagyva.")
        return
    erintett = _fizetetlen_szamlak_korhoz(szamlak, kor_kulcs)
    if not erintett:
        print(f"      ℹ️  A(z) '{kor_kulcs}' körnek jelenleg nincs fizetetlen számlája - "
              "manuális összesítő kihagyva.")
        return
    kor_nev = (allapot.get("kor_nevek") or {}).get(kor_kulcs) or ("1. kör" if kor_kulcs == "kor_a" else "2. kör")
    cim_resz = f" – {_esc(kor_nev)} (azonnali, dashboard)"
    _osszesito_kuldese(
        allapot, erintett, cim_resz,
        f"<p>Ez a(z) <strong>{_esc(kor_nev)}</strong> jelenleg fizetetlen számláinak összesítője - "
        "a dashboardról kifejezetten kért, azonnali küldés:</p>",
        cimzett, statisztika, pdf_csatolas,
    )
    _tulajdonos_osszesito_masolat(allapot, erintett, cim_resz, statisztika, pdf_csatolas)


def _tulajdonos_osszesito_kuldese_most(allapot: dict, szamlak: dict, statisztika: dict, pdf_csatolas: bool):
    """A dashboard tulajdonosi "Küldés most" gombja hívja (ld. 6/7. pont,
    SZAMLA_TULAJDONOS_OSSZESITO_MOST workflow_dispatch input) - az ÖSSZES
    (minden bérlői kör + be nem sorolt/"fuggoben") jelenleg fizetetlen
    számla összesítőjét küldi el a tulajdonosnak, azonnal."""
    cimzett = _cimzett_string(allapot.get("tulajdonos_emailek"))
    if not cimzett:
        print("      ⚠️  Nincs beállítva tulajdonosi email-cím (dashboard 'Tulajdonos' kezelése) - "
              "manuális 'mindent mutass' összesítő kihagyva.")
        return
    erintett = _fizetetlen_szamlak_korhoz(szamlak, None)
    if not erintett:
        print("      ℹ️  Jelenleg nincs egyetlen fizetetlen számla sem - tulajdonosi összesítő kihagyva.")
        return
    _osszesito_kuldese(
        allapot, erintett, " – Tulajdonos (azonnali, összes kör)",
        "<p>Ez az ÖSSZES jelenleg fizetetlen számla összesítője (minden bérlői kör + be nem "
        "sorolt tételek) - a dashboardról kifejezetten kért, azonnali küldés:</p>",
        cimzett, statisztika, pdf_csatolas,
    )


def _honap_utolso_napja(datum: date) -> int:
    """A megadott dátum hónapjának utolsó naptári napja (28/29/30/31) - a
    könyvelői havi emlékeztető "hónap vége" ablakának kiszámításához."""
    return calendar.monthrange(datum.year, datum.month)[1]


# ════════════════════════════════════════════
#  ☁️  GOOGLE DRIVE - PDF-FELTÖLTÉS (opcionális)
# ════════════════════════════════════════════
# Minden számla PDF-jét feltölti egy KÜLÖN (a felhasználó által már
# telepített és üzemeltetett) Google Apps Script Web App-ra, hogy a
# könyvelő/tulajdonos közvetlenül a Drive-on is elérje őket, email
# nélkül is. Ez a script NEM hozza létre/kezeli a Web App-ot, csak HÍVJA,
# a vele megállapodott szerződés szerint:
#
#   POST <SZAMLA_DRIVE_WEBAPP_URL>
#   {"token": <SZAMLA_DRIVE_WEBAPP_TOKEN>, "forras": "Vízművek"/"Díjnet"/
#    "MVM"/egyéb, "szolgaltato_nev": <csak Díjnetnél számít - al-mappát
#    hoz létre szolgáltatónként>, "fajlnev": <kívánt fájlnév>,
#    "pdf_base64": <a PDF base64-kódolva>}
#   ->  {"ok": true, "mar_letezett": bool, "file_id": ..., "url": ...}
#       VAGY {"ok": false, "hiba": ...}
#
# A "mar_letezett" mező a Web App SAJÁT (második vonalbeli) dedup-jelzése
# - ettől függetlenül itt, a python-oldalon is nyilvántartjuk, mit
# töltöttünk már fel (ld. "drive_feltoltott_id_k" az állapotban), hogy ne
# kelljen minden 10 perces futásnál újra elküldeni ugyanazt a PDF-et a
# Web App-nak.


def _drive_forras_meghatarozasa(rekord: dict) -> str:
    """A számla-rekord "forras"/"szolgaltato" mezői alapján visszaadja,
    MELYIK Drive-al-mappába kell feltölteni ("Vízművek"/"Díjnet"/"MVM"/
    "Egyéb") - ld. a szekció elején a Web App szerződését. Ezt a
    leképezést SZÁNDÉKOSAN egy külön, jól kommentelt függvénybe
    szerveztük ki (ahelyett hogy a hívás helyén találgatnánk), mert a
    "forras"/"szolgaltato" mezők eltérően vannak kitöltve a három forrás
    szerint (ld. a beolvasó ágakat fentebb a fájlban):
      - IMAP-email (Vízművek/MVM): "szolgaltato" = "vizmuvek"/"mvm",
        "forras" mező EGYÁLTALÁN NINCS a rekordban.
      - Díjnet portál: "szolgaltato" = "dijnet", "forras" = "dijnet_portal".
      - Vízművek portál: "szolgaltato" = "vizmuvek", "forras" =
        "vizmuvek_portal".
    Egy ide nem illő/jövőbeli forrás esetén SZÁNDÉKOSAN "Egyéb"-et adunk
    vissza, nem hibázunk/hagyjuk ki - egy fel nem ismert forrás PDF-je is
    kerüljön fel valahova, csak legyen jól látható, hogy nem illeszkedett
    a három ismert kategóriába."""
    if rekord.get("forras") == "dijnet_portal" or rekord.get("szolgaltato") == "dijnet":
        return "Díjnet"
    if rekord.get("forras") == "vizmuvek_portal" or rekord.get("szolgaltato") == "vizmuvek":
        return "Vízművek"
    if rekord.get("szolgaltato") == "mvm":
        return "MVM"
    # "További postafiókok" (ld. "TOVÁBBI POSTAFIÓKOK" szekció lentebb) -
    # a felhasználó által a dashboardon adott "cimke" (pl. "Csatornázási
    # Művek") lesz a Drive-on a SAJÁT, top-szintű almappa neve - ugyanaz
    # az elv, mint a Vízművek/MVM/Díjnet fix mappáinál, csak dinamikusan
    # névre szabva, hogy minden hozzáadott postafióknak külön mappája
    # legyen, ne mind az "Egyéb"-be keveredjen.
    if str(rekord.get("szolgaltato") or "").startswith("postafiok_") and rekord.get("szolgaltato_nev"):
        return rekord["szolgaltato_nev"]
    return "Egyéb"


def _drive_fajlnev(invoice_id: str, rekord: dict) -> str:
    """Biztonságos (ékezet- és speciális karakter nélküli), ÜTKÖZÉS-
    MENTES fájlnevet készít egy adott számlához a Drive-feltöltéshez - a
    szellemisége megegyezik a dashboard (szamlak.html)
    fajlnevBiztonsagos() függvényével, csak ennek a Python-oldali
    megfelelője. Az invoice_id (a számla saját, belső, amúgy is egyedi
    azonosítója) MINDIG a fájlnév része - ez garantálja, hogy két
    különböző számla SOHA ne kapja ugyanazt a fájlnevet, még akkor sem,
    ha a szamlaszam/targy mező hiányzik vagy véletlenül megegyezik."""
    import unicodedata

    azonosito_resz = rekord.get("szamlaszam") or rekord.get("targy") or "szamla"
    nyers = f"{rekord.get('szolgaltato_nev') or ''}_{azonosito_resz}_{invoice_id}"
    ekezet_nelkul = "".join(
        ch for ch in unicodedata.normalize("NFD", nyers) if not unicodedata.combining(ch)
    )
    biztonsagos = re.sub(r"[^a-zA-Z0-9._-]+", "_", ekezet_nelkul)
    biztonsagos = re.sub(r"^_+|_+$", "", biztonsagos) or "szamla"
    return biztonsagos[:100] + ".pdf"


def _drive_feltoltes_probalkozas(invoice_id: str, rekord: dict, pdf_b64: str) -> bool:
    """Egyetlen feltöltési kísérlet a Drive Web App-ra - best-effort,
    ugyanúgy, mint pl. dijnet_pdf_letoltese()/vizmuvek_pdf_letoltese():
    bármilyen hiba (hálózati, időtúllépés, HTTP, JSON-parse) esetén
    csendben, csak szerkezeti naplózással (a számlaszám/id KIVÉTELÉVEL
    semmilyen tartalom, válasz-szöveg vagy URL nélkül) False-t ad vissza
    - egyetlen számla feltöltési hibája nem szabad, hogy megállítsa a
    teljes futást.

    A visszatérési érték True, ha a Web App "ok": true választ adott -
    FÜGGETLENÜL attól, hogy "mar_letezett" true vagy false volt, mert
    mindkét eset azt jelenti, hogy a PDF ETTŐL KEZDVE elérhető a
    Drive-on (a "mar_letezett" csak a Web App saját, második védelmi
    vonalbeli dedup-jelzése, ld. a szekció elején lévő kommentet)."""
    azonosito_log = rekord.get("szamlaszam") or invoice_id
    try:
        valasz = requests.post(
            SZAMLA_DRIVE_WEBAPP_URL,
            json={
                "token": SZAMLA_DRIVE_WEBAPP_TOKEN,
                "forras": _drive_forras_meghatarozasa(rekord),
                "szolgaltato_nev": rekord.get("szolgaltato_nev") or "",
                "fajlnev": _drive_fajlnev(invoice_id, rekord),
                "pdf_base64": pdf_b64,
            },
            timeout=20,
        )
        eredmeny = valasz.json()
    except Exception:
        # SZÁNDÉKOSAN NINCS itt a kivétel szövege kiírva - egy hálózati
        # hibaüzenet elméletben tartalmazhatja a kérés URL-jét (a Web App
        # URL-je), amit a nyilvános Actions naplóba nem szabad
        # bekerülnie.
        print(f"  ⚠️  Drive-feltöltés sikertelen (hálózati hiba): {azonosito_log}")
        return False
    if not isinstance(eredmeny, dict) or not eredmeny.get("ok"):
        print(f"  ⚠️  Drive-feltöltés sikertelen (a Web App hibát jelzett): {azonosito_log}")
        return False
    return True


def drive_pdf_feltoltesek(allapot: dict):
    """Minden olyan számla PDF-jét feltölti a Drive-ra, amihez már van
    tárolt PDF (allapot["pdf_adatok"]), de MÉG NINCS a
    "drive_feltoltott_id_k" listában (ld. visszafejt() kommentjét).

    Teljesen no-op (ugyanaz az elv, mint a Díjnet/Vízművek
    portál-integrációknál), ha a két kötelező env-változó (URL+token)
    nincs beállítva. Teljesen no-op akkor is, ha DRY_RUN aktív - a
    feltöltés egy TÉNYLEGES mellékhatás (a Web App valóban ír a
    Drive-ba), pont úgy, mint az email-küldés (ld. email_kuldes() DRY_RUN
    ágát), ezért DRY_RUN alatt nem szabad megtörténnie."""
    if not (SZAMLA_DRIVE_WEBAPP_URL and SZAMLA_DRIVE_WEBAPP_TOKEN):
        print("  ℹ️  Drive-feltöltés: SZAMLA_DRIVE_WEBAPP_URL / SZAMLA_DRIVE_WEBAPP_TOKEN "
              "nincs beállítva - kihagyva.")
        return
    if DRY_RUN:
        print("  🧪 [DRY RUN] Drive-feltöltés kihagyva (ez egy tényleges mellékhatás, "
              "ugyanúgy mint az email-küldés).")
        return

    szamlak = allapot.get("szamlak", {})
    pdf_adatok = allapot.get("pdf_adatok", {})
    mar_feltoltott = allapot.setdefault("drive_feltoltott_id_k", [])
    mar_feltoltott_szet = set(mar_feltoltott)

    jelolt_id_k = [
        rid for rid in szamlak
        if rid in pdf_adatok and rid not in mar_feltoltott_szet
    ]

    feltoltve_db = 0
    hiba_db = 0
    # DRIVE_FELTOLTES_MAX_FUTASONKENT-es sapka - ld. a konstans fenti
    # kommentjét: a sapkán túli, még feltöltendő számlák egyszerűen a
    # KÖVETKEZŐ futásra maradnak, nem vesznek el.
    for rid in jelolt_id_k[:DRIVE_FELTOLTES_MAX_FUTASONKENT]:
        sikeres = _drive_feltoltes_probalkozas(rid, szamlak[rid], pdf_adatok[rid])
        if sikeres:
            mar_feltoltott.append(rid)
            feltoltve_db += 1
        else:
            hiba_db += 1

    hatralevo_db = len(jelolt_id_k) - feltoltve_db - hiba_db
    # Szerkezeti (csak darabszám) összefoglaló - ugyanaz a stílus, mint a
    # Díjnet/Vízművek "nincs (még) tárolt PDF-je" logok fentebb ebben a
    # fájlban.
    print(f"  ☁️  Drive-feltöltés: {feltoltve_db} db feltöltve, {hiba_db} db sikertelen, "
          f"{hatralevo_db} db a következő futásra marad ebben a körben "
          f"(sapka: {DRIVE_FELTOLTES_MAX_FUTASONKENT}/futás).")


# ════════════════════════════════════════════
#  🏢  CÉGES SZÁMLÁK - dedikált postafiók (opcionális, ld. CEGES_IMAP_*)
# ════════════════════════════════════════════
# TELJESEN KÜLÖN, önálló modul - a felhasználó egy MÁSIK célra, egy
# ÚJ, kizárólag céges (a cég nevében vásárolt) beszerzésekhez kapcsolódó
# számlák begyűjtésére szánt email-postafiókot hoz létre, és minden ide
# beérkező levelet (amit maga kér el az eladóktól emailben) számla-
# jelöltnek tekintünk - NINCS itt "ismert szolgáltató" szűrés
# (szolgaltato_azonositasa()), mint a fenti fő IMAP-ágnál, mert ez a
# postafiók kizárólag erre a célra van, és bárkitől jöhet számla.
#
# KÉT LÉNYEGES ELTÉRÉS A FENTIEKHEZ KÉPEST (a felhasználó kifejezett,
# tudatos döntése alapján - ld. a dashboard-beszélgetés "tárhely kevés"
# indoklását):
#   1. A PDF-et NEM tároljuk tartósan a titkosított állapotban (nem
#      hívjuk a pdf_tarolas()-t) - KIZÁRÓLAG a Google Drive-on marad meg
#      (ld. _ceges_drive_feltoltes()), az állapotban csak a metaadat +
#      a Drive-link kerül el (ceges_szamlak dict) - ez jelentősen
#      kisebb állapotfájlt eredményez, mint ha PDF-eket is base64-ben
#      tárolnánk itt.
#   2. Sikeres Drive-feltöltés UTÁN a forrás email-t AZONNAL, VÉGLEGESEN
#      töröljük a postafiókból (nincs Kuka-időzár - a felhasználó ezt a
#      lehetőséget SZÁNDÉKOSAN nem választotta, mert a cél a
#      tárhely-felszabadítás). Ha a Drive-feltöltés sikertelen, a levél
#      ÉRINTETLENÜL marad a postafiókban - a KÖVETKEZŐ futás újra
#      megpróbálja. Emiatt NINCS itt "feldolgozott UID"-lista sem: a
#      postafiók MAGA a "még feldolgozandó" sor - egy sikeresen
#      feltöltött és törölt levél sosem térhet vissza, egy sikertelen
#      pedig automatikusan újra esélyt kap a következő futáskor.
def _ceges_kuldo_nev_kinyerese(msg) -> str:
    """A feladó megjelenítendő neve (a From fejléc "név" része, pl. "Kis
    Kft. Számlázás") - ha ez hiányzik (csak egy csupasz email-cím van),
    a domain-részt adjuk vissza tájékoztató jelleggel (pl. "cegneve.hu"),
    hogy a Drive-almappa és a dashboard-lista sose kapjon üres nevet."""
    from email.utils import parseaddr

    nev_nyers, cim = parseaddr(msg.get("From", ""))
    nev = _fejlec_dekodolas(nev_nyers).strip()
    if nev:
        return nev[:80]
    domain = cim.split("@")[-1] if cim and "@" in cim else ""
    return domain or "ismeretlen feladó"


def ceges_osszes_uid_lekerese(conn, max_db=40):
    """A fő postafiók uj_uidok_lekerese()-jével ellentétben itt NINCS
    dátum-szűrés (SINCE) és nincs "már feldolgozott" halmaz sem - ld. a
    szekció elején lévő kommentet: ez a postafiók MAGA a feldolgozandó
    sor (a sikeresen feldolgozott levelek törlődnek), ezért egyszerűen
    MINDENT lekérünk, ami a mappában (jellemzően INBOX) éppen ott van."""
    tipus, adat = conn.uid("search", None, "ALL")
    if tipus != "OK" or not adat or not adat[0]:
        return []
    return adat[0].split()[:max_db]


def _ceges_fajlnev(cid: str, kuldo_nev: str, eredeti_fajlnev: str) -> str:
    """Ugyanaz az elv, mint a _drive_fajlnev()-nél: ékezet- és speciális
    karakter nélküli, ÜTKÖZÉS-MENTES fájlnév - a "cid" (ez a levél saját,
    egyedi azonosítója) MINDIG a fájlnév része, hogy két külön levél SOHA
    ne kapja ugyanazt a nevet, ÉS hogy egy esetlegesen kétszer feldolgozott
    (pl. törlés/expunge közben megszakadt futás miatt még a postafiókban
    maradt) levél a Web App saját dedup-ellenőrzésén (azonos fájlnév a
    célmappában) NE hozzon létre duplikátumot a Drive-on."""
    import unicodedata

    alap = eredeti_fajlnev or "szamla.pdf"
    if alap.lower().endswith(".pdf"):
        alap = alap[:-4]
    nyers = f"{kuldo_nev}_{alap}_{cid}"
    ekezet_nelkul = "".join(
        ch for ch in unicodedata.normalize("NFD", nyers) if not unicodedata.combining(ch)
    )
    biztonsagos = re.sub(r"[^a-zA-Z0-9._-]+", "_", ekezet_nelkul)
    biztonsagos = re.sub(r"^_+|_+$", "", biztonsagos) or "szamla"
    return biztonsagos[:100] + ".pdf"


def _ceges_drive_feltoltes(fajlnev: str, kuldo_nev: str, pdf_b64: str):
    """Egyetlen feltöltési kísérlet a Drive Web App-ra - ugyanaz a
    szerződés, mint _drive_feltoltes_probalkozas()-nál, DE itt (bool
    helyett) a Web App által adott Drive-URL-t adjuk vissza (vagy None-t
    hiba esetén), mert a dashboardnak ez kell a "Megnyitás Drive-on"
    linkhez - a fenti szekció-komment szerint itt NEM tárolunk PDF-et
    tartósan az állapotban, csak ezt a linket.

    A "forras" mezőt SZÁNDÉKOSAN "Céges számlák"-nak küldjük (nem
    "dijnet"/"vizmuvek"/"mvm", mint a többi ág) - a Web App
    (drive-feltoltes-webapp/Code.gs) ebből képezi a felső szintű
    Drive-almappa nevét, és - a "kuldo_nev" (eladó/cég neve) miatt - egy
    második szintű, eladónkénti almappát is létrehoz, ugyanúgy, mint a
    Díjnetnél a szolgáltató szerint (ld. Code.gs almappaBiztositasa_()
    hívások)."""
    try:
        valasz = requests.post(
            SZAMLA_DRIVE_WEBAPP_URL,
            json={
                "token": SZAMLA_DRIVE_WEBAPP_TOKEN,
                "forras": "Céges számlák",
                "szolgaltato_nev": kuldo_nev,
                "fajlnev": fajlnev,
                "pdf_base64": pdf_b64,
            },
            timeout=20,
        )
        eredmeny = valasz.json()
    except Exception:
        # SZÁNDÉKOSAN NINCS itt a kivétel szövege kiírva - ld.
        # _drive_feltoltes_probalkozas() hasonló kommentje fentebb.
        print(f"      ⚠️  Céges számla Drive-feltöltése sikertelen (hálózati hiba): {fajlnev}")
        return None
    if not isinstance(eredmeny, dict) or not eredmeny.get("ok"):
        print(f"      ⚠️  Céges számla Drive-feltöltése sikertelen (a Web App hibát jelzett): {fajlnev}")
        return None
    return eredmeny.get("url")


def ceges_szamlak_feldolgozasa(allapot: dict):
    """A dedikált céges-számla postafiók feldolgozása - ld. a szekció
    elején lévő kommentet a két lényeges eltérésről (nincs tartós
    PDF-tárolás, azonnali végleges email-törlés sikeres Drive-feltöltés
    után). Teljesen no-op, ha az öt CEGES_IMAP_* env-változó bármelyike
    hiányzik, VAGY ha a Drive-feltöltéshez szükséges két env-változó
    (SZAMLA_DRIVE_WEBAPP_URL/TOKEN) hiányzik - ez utóbbi SZÁNDÉKOS: a
    levél törlése csak egy IGAZOLTAN sikeres Drive-mentés után
    történhet, Drive nélkül nem tudnánk biztonságosan (adatvesztés
    kockázata nélkül) feldolgozni ezt a postafiókot.

    A "ceges_allapot" mező (a fő "ceges_szamlak" listától külön) MINDIG
    frissül (a "nincs beállítva" ág kivételével), hogy a dashboard
    "Céges számlák" fülén megjelenhessen egy visszajelzés arról, sikerült-e
    az utolsó futáskor bejelentkezni a postafiókba - a felhasználó
    kifejezett kérése, hogy ez látható legyen, ne csak az Actions naplóban."""
    ceges_allapot = allapot.setdefault("ceges_allapot", {})

    def _allapot_rogzitese(sikeres: bool, hiba=None):
        ceges_allapot["utolso_probalkozas"] = magyar_ido().isoformat()
        ceges_allapot["sikeres_bejelentkezes"] = sikeres
        ceges_allapot["hiba"] = hiba

    if not (CEGES_IMAP_HOST and CEGES_IMAP_USER and CEGES_IMAP_JELSZO):
        ceges_allapot["beallitva"] = False
        print("  ℹ️  Céges számlák: CEGES_IMAP_HOST / CEGES_IMAP_USER / CEGES_IMAP_JELSZO "
              "nincs (teljesen) beállítva - a modul kihagyva.")
        return
    ceges_allapot["beallitva"] = True
    if not (SZAMLA_DRIVE_WEBAPP_URL and SZAMLA_DRIVE_WEBAPP_TOKEN):
        _allapot_rogzitese(False, "A Drive-feltöltés nincs beállítva (SZAMLA_DRIVE_WEBAPP_URL/"
                                   "TOKEN hiányzik) - emiatt a postafiók-bejelentkezés ki van hagyva.")
        print("  ℹ️  Céges számlák: Drive-feltöltés nélkül (SZAMLA_DRIVE_WEBAPP_URL/TOKEN "
              "hiányzik) nem dolgozható fel biztonságosan ez a postafiók (a levelek törlése "
              "csak SIKERES Drive-mentés után történhetne) - a modul kihagyva.")
        return
    if DRY_RUN:
        # DRY_RUN alatt SZÁNDÉKOSAN nem írjuk felül a korábbi (valódi
        # futásból származó) állapotot - a dashboard így a legutóbbi ÉLES
        # futás eredményét mutatja, nem egy teszt-futásét.
        print("  🧪 [DRY RUN] Céges számlák feldolgozása kihagyva (Drive-feltöltés + "
              "email-törlés tényleges mellékhatás, ugyanúgy mint a Drive-feltöltésnél/"
              "email-küldésnél fentebb).")
        return

    ceges_szamlak = allapot.setdefault("ceges_szamlak", {})

    try:
        conn = imap_kapcsolat(CEGES_IMAP_HOST, CEGES_IMAP_PORT, CEGES_IMAP_USER, CEGES_IMAP_JELSZO, CEGES_IMAP_MAPPA)
    except Exception as e:
        _allapot_rogzitese(False, str(e))
        print(f"  ❌ Céges számlák: IMAP-bejelentkezés sikertelen: {e}")
        return
    _allapot_rogzitese(True, None)

    feltoltve_db = 0
    hiba_db = 0
    torlendo_uidok = []
    try:
        uidok = ceges_osszes_uid_lekerese(conn, CEGES_MAX_FELDOLGOZAS_FUTASONKENT)
        print(f"  🏢 Céges számlák postafiók: {len(uidok)} feldolgozandó levél (sapka: "
              f"{CEGES_MAX_FELDOLGOZAS_FUTASONKENT}/futás).")

        for uid in uidok:
            uid_str = uid.decode()
            msg = uid_letoltese(conn, uid)
            if msg is None:
                continue

            targy = _fejlec_dekodolas(msg.get("Subject", ""))
            erkezett_fejlec = msg.get("Date", "")
            feladó_email = _feladó_cim(msg)
            kuldo_nev = _ceges_kuldo_nev_kinyerese(msg)
            pdf_nev, pdf_bytes = pdf_csatolmany(msg)

            if not pdf_bytes:
                # Nincs PDF-csatolmány (pl. az eladó csak egy sima
                # visszaigazolást küldött, PDF nélkül) - ezt a levelet
                # SZÁNDÉKOSAN NEM töröljük (nincs mit visszakeresni, ha
                # törölnénk) - a postafiókban marad, kézi ellenőrzést
                # igényel (pl. újra megkérni az eladót a PDF-re).
                print(f"      ⚠️  Nincs PDF-csatolmány, a levél a postafiókban marad "
                      f"(kézi ellenőrzést igényel): {kuldo_nev} – {targy[:60]}")
                hiba_db += 1
                continue

            cid = hashlib.md5(f"{CEGES_IMAP_USER}|{uid_str}|ceges".encode("utf-8")).hexdigest()[:16]
            fajlnev = _ceges_fajlnev(cid, kuldo_nev, pdf_nev)
            pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
            drive_url = _ceges_drive_feltoltes(fajlnev, kuldo_nev, pdf_b64)
            if not drive_url:
                # A Drive-feltöltés sikertelen - a levél ÉRINTETLENÜL
                # marad a postafiókban (ld. a szekció elején lévő
                # komment), a következő futás automatikusan újra
                # megpróbálja.
                hiba_db += 1
                continue

            # A NAV-párosításhoz (ld. "NAV ONLINE SZÁMLA" szekció lentebb)
            # best-effort kinyerjük a PDF szövegéből az összeget és egy
            # esetleges számlaszámot - a PDF-et magát ETTŐL FÜGGETLENÜL
            # NEM tároljuk (ld. a szekció elején lévő komment), csak ezt a
            # néhány kinyert szöveges mezőt, ami elenyésző helyet foglal.
            ceges_pdf_szoveg = pdf_szoveg_kinyerese(pdf_bytes)
            if ceges_pdf_szoveg:
                kinyert_osszeg, kinyert_penznem = osszeg_es_penznem_kinyerese(ceges_pdf_szoveg)
            else:
                kinyert_osszeg, kinyert_penznem = None, "HUF"
            kinyert_szamlaszam = szamlaszam_kinyerese_altalanos(ceges_pdf_szoveg) if ceges_pdf_szoveg else None

            ceges_szamlak[cid] = {
                "kuldo_nev": kuldo_nev,
                "feladó_email": feladó_email,
                "targy": targy,
                "erkezett": _email_datum_iso(erkezett_fejlec),
                "erkezett_fejlec": erkezett_fejlec,
                "drive_url": drive_url,
                "drive_fajlnev": fajlnev,
                "rogzitve": magyar_ido().isoformat(),
                # Best-effort, a PDF szövegéből kinyert mezők (ld. fent) -
                # kizárólag a NAV-párosításhoz kellenek, None is lehet. A
                # "penznem" ("HUF" vagy "EUR", ld. osszeg_es_penznem_
                # kinyerese() kommentje) - a felhasználó a dashboardon
                # (cegesTablaRenderelese() "Pénznem" mezője) kézzel
                # átállíthatja, ha a felismerés rosszul sikerülne.
                "kinyert_osszeg": kinyert_osszeg,
                "penznem": kinyert_penznem,
                "kinyert_szamlaszam": kinyert_szamlaszam,
                # A script SOHA nem tölti ki automatikusan - a dashboard
                # "Adószám" mezője (ld. cegesMezoMentese()) írja, ha a
                # felhasználó kézzel megadja (jellemzően akkor, ha a
                # számlaszám/összeg alapján nem sikerült a NAV-párosítás) -
                # ld. nav_szamla_parositas() "1.5 kör" kommentje.
                "adoszam": None,
                # NAV Online Számla összekötés/párosítás - ld. "NAV ONLINE
                # SZÁMLA" szekció lentebb (nav_ceges_parositas()) - itt
                # kezdetben mindig üres, a párosító funkció (a fő
                # feldolgozás UTÁN, a main()-ben) tölti ki.
                "nav_szamla_azonosito": None,
                "nav_parositva": False,
                "nav_szallito_nev": None,
                "nav_osszeg": None,
                "nav_datum": None,
            }
            feltoltve_db += 1
            torlendo_uidok.append(uid)
            print(f"      ✅ Céges számla mentve (Drive-ra feltöltve, email törlésre "
                  f"jelölve): {kuldo_nev} – {targy[:60]}")

        for uid in torlendo_uidok:
            try:
                conn.uid("store", uid, "+FLAGS", "(\\Deleted)")
            except Exception as e:
                print(f"      ⚠️  Egy feldolgozott céges számla email törlése (jelölése) "
                      f"sikertelen (a Drive-mentés megvolt, csak a postafiókban marad): {e}")
        if torlendo_uidok:
            try:
                conn.expunge()
            except Exception as e:
                print(f"  ⚠️  Céges számlák postafiók végleges törlése (expunge) sikertelen: {e}")
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    ceges_allapot["utolso_futas_feltoltve_db"] = feltoltve_db
    ceges_allapot["utolso_futas_hiba_db"] = hiba_db
    print(f"  🏢 Céges számlák: {feltoltve_db} db feldolgozva és véglegesen törölve a "
          f"postafiókból, {hiba_db} db maradt/hibázott (a postafiókban marad, a következő "
          f"futás újra megpróbálja).")


# ════════════════════════════════════════════
#  📬  TOVÁBBI POSTAFIÓKOK (dashboardról hozzáadott, folyamatosan figyelt)
# ════════════════════════════════════════════
# A felhasználó kérésére a dashboardon (Közüzemi számlák fül, "➕ Új
# postafiók hozzáadása" panel) TETSZŐLEGES SZÁMÚ, tetszőleges (cPanel-es
# IMAP vagy Gmail App Password-ös) postafiók adható hozzá, ami mostantól
# FOLYAMATOSAN (minden ütemezett futásnál) figyelve lesz - ld. a panel
# HTML-kommentjét (szamlak.html) a pontos felhasználói folyamatért
# (titkosított mentés a meglévő allapotFrissitesEsMentese() mintával).
#
# EZ SZÁNDÉKOSAN A FŐ ("szamlak") LISTÁBA KERÜL, NEM egy külön fülbe -
# a felhasználó kifejezett kérése ("kösd össze a másik füllel"), mert
# ezek is jellemzően a cég nevére jövő, közüzemi jellegű számlák (pl.
# Csatornázási Művek), csak épp egy MÁSIK postafiókba érkeznek, mint a
# fő SZAMLA_IMAP_*. Minden ilyen postafiók egy szintetikus "szolgaltato"
# kulcsot kap ("postafiok_<id>") és a felhasználó által megadott "cimke"
# lesz a "szolgaltato_nev" - így a meglévő tábla/szűrő/fizetve-párosítás
# logika (ami a "szolgaltato" mezőre épül) VÁLTOZTATÁS NÉLKÜL működik
# ezekre a rekordokra is.
#
# SZŰRÉS - FONTOS KÜLÖNBSÉG a fő postafiókhoz képest: itt NINCS "ismert
# feladó" szűrés (szolgaltato_azonositasa) - a felhasználó kifejezett
# kérése szerint MINDEN, PDF-CSATOLMÁNYOS levelet megvizsgálunk (PDF
# NÉLKÜLI levelet EGYÁLTALÁN NEM nézünk meg itt), és a MEGLÉVŐ,
# tartalom-alapú tartalom_tipus_azonositas()-t használjuk annak
# eldöntésére, hogy az adott levél ténylegesen számla (vagy fizetés-
# visszaigazolás/mérőállás/egyéb)-e - ugyanazzal a mintafelismeréssel,
# mint a fő postafióknál, csak feladó-szűrés nélkül.
#
# EREDETI PDF: a Drive-ra/tartós tárolásra MINDIG az eredeti, változatlan
# PDF-bájtok kerülnek (pdf_tarolas() + a meglévő generikus
# drive_pdf_feltoltesek() útján, VAGY - "cel": "ceges" postafióknál -
# közvetlenül a _ceges_drive_feltoltes()-en át) - a pdfplumber-es
# szövegkinyerés (pdf_szoveg_kinyerese()) KIZÁRÓLAG a tartalom
# felismeréséhez kell, a kinyert szöveg SOHA nem kerül tárolásra/
# feltöltésre a PDF helyett.
#
# "cel" mező (opcionális, "kozuzemi" vagy "ceges", alapértelmezett
# "kozuzemi") - a felhasználó postafiókonként eldöntheti, hogy az onnan
# felismert számlák a fenti (szamlak/Közüzemi) listába kerüljenek-e
# (ez a régi, alapértelmezett viselkedés), VAGY a "ceges_szamlak"
# (Céges számlák fül) listába - utóbbi akkor hasznos, ha a postafiók
# valójában céges beszerzési számlákat gyűjt (ugyanaz a kategória, mint
# a dedikált CEGES_IMAP_* postafiók), csak épp egy MÁSIK email-címre
# érkeznek. "cel": "ceges" esetén a PDF-et - a dedikált céges postafiók
# elvével megegyezően - NEM tároljuk tartósan az állapotban, csak a
# Drive-linket (ld. _ceges_drive_feltoltes()).
def _szamla_athelyezese_cegesbe(allapot: dict, rid: str, forras_cimke: str = None) -> bool:
    """Egyetlen, még a fő "szamlak" listában lévő rekordot helyez át a
    "ceges_szamlak" listába: újra feltölti a tárolt PDF-et a Drive
    "Céges számlák" mappaszerkezetébe (_ceges_drive_feltoltes() - a
    generikus drive_pdf_feltoltesek() ugyanis nem tárolja el a
    visszakapott URL-t, csak egy sikeres/sikertelen jelzőt, a Céges fülön
    viszont MINDENKÉPP kell egy "Megnyitás Drive-on" link), majd -
    KIZÁRÓLAG sikeres feltöltés esetén - törli az eredeti "szamlak"/
    "pdf_adatok" bejegyzést és a "drive_feltoltott_id_k" listából is.
    True-t ad vissza sikeres áthelyezésnél; False-t, ha nincs (már/még)
    ilyen "rid" a "szamlak"-ban, nincs hozzá tárolt PDF, VAGY a
    Drive-feltöltés sikertelen volt - ez utóbbi két esetben a rekord
    ÉRINTETLENÜL marad a "szamlak"-ban, a hívó dolga eldönteni, mikor
    próbálja újra (nem vész el semmi).

    Ezt a közös logikát használja MIND a postafiókonkénti tömeges
    áthelyezés (ld. tovabbi_postafiok_ceges_athelyezes() lentebb), MIND a
    dashboardról, EGYEDI számlánként kért áthelyezés (ld.
    kezi_ceges_athelyezesek_feldolgozasa() lentebb - a "→ Céges" gomb a
    Közüzemi táblázat egy-egy során)."""
    szamlak = allapot.get("szamlak", {})
    pdf_adatok = allapot.get("pdf_adatok", {})
    ceges_szamlak = allapot.setdefault("ceges_szamlak", {})
    rekord = szamlak.get(rid)
    if rekord is None:
        return False
    pdf_b64 = pdf_adatok.get(rid)
    if not pdf_b64:
        # Nincs (már/még) tárolt PDF ehhez - Drive-link nélkül nem
        # tudnánk értelmesen megjeleníteni a Céges fülön (ott a PDF
        # megtekintése KIZÁRÓLAG a Drive-linken át működik) - inkább a
        # régi helyén hagyjuk, mint hogy hozzáférés nélkül maradjon.
        return False
    kuldo_nev = forras_cimke or rekord.get("szolgaltato_nev") or "Ismeretlen"
    fajlnev = _ceges_fajlnev(rid, kuldo_nev, rekord.get("targy"))
    drive_url = _ceges_drive_feltoltes(fajlnev, kuldo_nev, pdf_b64)
    if not drive_url:
        return False
    ceges_szamlak[rid] = {
        "kuldo_nev": kuldo_nev,
        "feladó_email": None,
        "targy": rekord.get("targy"),
        "erkezett": rekord.get("erkezett"),
        "erkezett_fejlec": rekord.get("erkezett_fejlec"),
        "drive_url": drive_url,
        "drive_fajlnev": fajlnev,
        "rogzitve": magyar_ido().isoformat(),
        "kinyert_osszeg": rekord.get("osszeg"),
        # A forrás-rekordon esetleg már meglévő pénznemet megőrizzük -
        # ha ott nem volt (régebbi, e mező előtti rekord), "HUF"-ra esünk
        # vissza (ld. osszeg_es_penznem_kinyerese() kommentje).
        "penznem": rekord.get("penznem") or "HUF",
        "kinyert_szamlaszam": rekord.get("szamlaszam"),
        # Ld. a dashboard "Adószám" mezőjének kommentjét (szamlak.html) -
        # ha a fő listán már be volt írva kézzel, áthelyezésnél megőrizzük.
        "adoszam": rekord.get("adoszam"),
        "nav_szamla_azonosito": rekord.get("nav_szamla_azonosito"),
        "nav_parositva": rekord.get("nav_parositva", False),
        "nav_szallito_nev": rekord.get("nav_szallito_nev"),
        "nav_osszeg": rekord.get("nav_osszeg"),
        "nav_datum": rekord.get("nav_datum"),
    }
    del szamlak[rid]
    pdf_adatok.pop(rid, None)
    feltoltottek = allapot.get("drive_feltoltott_id_k")
    if isinstance(feltoltottek, list) and rid in feltoltottek:
        feltoltottek.remove(rid)
    return True


def tovabbi_postafiok_ceges_athelyezes(allapot: dict, postafiok_id: str, cimke: str):
    """Ha a felhasználó UTÓLAG állította "ceges"-re egy postafiók célját
    (a "cel" mező bevezetése előtt, vagy egyszerűen később meggondolta
    magát), a KORÁBBAN már a fő "szamlak" listába felvett rekordjai ott
    maradnának örökre - ez a függvény (minden futáskor meghívva, de csak
    akkor csinál bármit, ha talál ilyen árva rekordot) egyszeri jelleggel
    átköltözteti ezeket a "ceges_szamlak" listába (ld.
    _szamla_athelyezese_cegesbe() fent a tényleges logikáért)."""
    szamlak = allapot.get("szamlak", {})
    pdf_adatok = allapot.get("pdf_adatok", {})
    szolgaltato_kulcs = f"postafiok_{postafiok_id}"
    athelyezendo_id_k = [rid for rid, r in szamlak.items() if r.get("szolgaltato") == szolgaltato_kulcs]
    if not athelyezendo_id_k:
        return
    athelyezett_db = 0
    for rid in athelyezendo_id_k:
        targy_log = (szamlak.get(rid, {}).get("targy") or "")[:60]
        volt_pdf = rid in pdf_adatok
        if _szamla_athelyezese_cegesbe(allapot, rid, cimke):
            athelyezett_db += 1
        elif volt_pdf:
            # Csak akkor logolunk figyelmeztetést, ha VOLT tárolt PDF, de
            # a Drive-feltöltés hibázott - ha eleve nem volt PDF, nincs
            # mit tenni, az nem hiba (ld. _szamla_athelyezese_cegesbe()).
            print(f"      ⚠️  '{cimke}' Céges-listába áthelyezése: Drive-feltöltés sikertelen "
                  f"ehhez: {targy_log} - újra próbáljuk a következő futáskor.")
    if athelyezett_db:
        print(f"  🔀 '{cimke}': {athelyezett_db} db korábban felvett számla áthelyezve a Céges listába.")


def kezi_ceges_athelyezesek_feldolgozasa(allapot: dict):
    """A dashboardon, a Közüzemi táblázat egy-egy során levő "→ Céges"
    gombbal (ld. szamlak.html cegesAthelyezesKerelme()) kért, EGYEDI
    (nem postafiók-szintű) áthelyezéseket dolgozza fel - a dashboard ott
    csak a számla id-ját írja be az "ceges_athelyezes_kerelem" listába (a
    titkosított állapot egy read-modify-write mentésével, ugyanazzal a
    mintával, mint minden más dashboard-mentés), mert a TÉNYLEGES
    áthelyezéshez (Drive-webapp hívás) a SZAMLA_DRIVE_WEBAPP_TOKEN kell,
    ami csak itt, a Python-oldalon (GitHub Secret) érhető el - a
    böngészőben soha. Sikertelen (pl. hálózati hiba miatti) feltöltésnél
    a kérés a listában marad, a következő futás újra megpróbálja; ha a
    kért "rid" időközben már nincs a "szamlak"-ban (törölve/már
    áthelyezve), a kérés egyszerűen eldobásra kerül (nincs mit tenni)."""
    kerelmek = allapot.get("ceges_athelyezes_kerelem")
    if not kerelmek:
        return
    szamlak = allapot.get("szamlak", {})
    ceges_szamlak = allapot.get("ceges_szamlak", {})
    meg_fuggoben = []
    athelyezett_db = 0
    for rid in kerelmek:
        if rid in ceges_szamlak or rid not in szamlak:
            continue  # már megtörtént, vagy időközben eltűnt - a kérés törölhető
        if _szamla_athelyezese_cegesbe(allapot, rid):
            athelyezett_db += 1
        else:
            meg_fuggoben.append(rid)  # Drive-feltöltés (vagy hiányzó PDF) - újra próbáljuk
    allapot["ceges_athelyezes_kerelem"] = meg_fuggoben
    if athelyezett_db:
        print(f"  🔀 Dashboardról kért, egyedi Céges-áthelyezés: {athelyezett_db} db számla áthelyezve.")


def tovabbi_postafiokok_feldolgozasa(allapot: dict, statisztika: dict, torolt_id_szet: set):
    szamlak = allapot.setdefault("szamlak", {})
    ceges_szamlak = allapot.setdefault("ceges_szamlak", {})
    tovabbi_postafiokok = allapot.setdefault("tovabbi_postafiokok", {})
    if not tovabbi_postafiokok:
        return

    for postafiok_id, bejegyzes in tovabbi_postafiokok.items():
        cimke = bejegyzes.get("cimke") or "Ismeretlen postafiók"
        cel = str(bejegyzes.get("cel") or "kozuzemi").strip().lower()
        if cel not in ("kozuzemi", "ceges"):
            cel = "kozuzemi"

        if cel == "ceges":
            # Ld. tovabbi_postafiok_ceges_athelyezes() kommentje - ezt
            # SZÁNDÉKOSAN a "szüneteltetve" (aktiv=False) ÉS a hiányos
            # bejelentkezési adatok ELLENŐRZÉSE ELŐTT futtatjuk (ne a
            # lenti "continue"-k mögé essen): a "szüneteltetés" csak az
            # ÚJ levelek figyelését állítja meg, a MÁR korábban felvett
            # számlák Céges-listába áthelyezését nem szabad emiatt
            # visszatartani - ehhez ráadásul nem is kell IMAP-
            # bejelentkezés, csak a Drive-webapp (ld. a függvény
            # kommentjét), tehát hiányos/rossz IMAP-adatoknál is
            # lefuthat.
            tovabbi_postafiok_ceges_athelyezes(allapot, postafiok_id, cimke)

        if not bejegyzes.get("aktiv", True):
            continue

        szolgaltato_kulcs = f"postafiok_{postafiok_id}"
        host = bejegyzes.get("host") or ""
        port = int(bejegyzes.get("port") or 993)
        felhasznalo = bejegyzes.get("user") or ""
        jelszo = bejegyzes.get("jelszo") or ""
        mappa = bejegyzes.get("mappa") or "INBOX"

        if not (host and felhasznalo and jelszo):
            print(f"  ⚠️  További postafiók '{cimke}': hiányos bejelentkezési adatok - kihagyva.")
            continue

        mar_feldolgozott = set(bejegyzes.setdefault("feldolgozott_uidok", []))
        try:
            conn = imap_kapcsolat(host, port, felhasznalo, jelszo, mappa)
        except Exception as e:
            bejegyzes["utolso_hiba"] = str(e)
            bejegyzes["utolso_probalkozas"] = magyar_ido().isoformat()
            print(f"  ❌ További postafiók '{cimke}': IMAP-bejelentkezés sikertelen: {e}")
            continue
        bejegyzes["utolso_hiba"] = None
        bejegyzes["utolso_probalkozas"] = magyar_ido().isoformat()

        uj_db = 0
        try:
            uj_uidok = uj_uidok_lekerese(conn, mar_feldolgozott)
            for uid in uj_uidok:
                uid_str = uid.decode()
                # "kesz" - alapból True (a levelet ETTŐL a futástól ne
                # nézzük meg újra) - EGYETLEN eset állítja False-ra: ha
                # "cel"=="ceges" ÉS a Drive-feltöltés sikertelen (ld.
                # lentebb) - ilyenkor a levelet a KÖVETKEZŐ futás újra
                # megkapja a uj_uidok_lekerese()-től, ahogy a dedikált
                # Céges postafióknál is (ott maga a postafiók a "még
                # feldolgozandó" sor, ld. a szekció-komment "1." pontját).
                kesz = True
                try:
                    msg = uid_letoltese(conn, uid)
                    if msg is None:
                        continue

                    pdf_nev, pdf_bytes = pdf_csatolmany(msg)
                    if not pdf_bytes:
                        # Ld. a szekció-komment "SZŰRÉS" része - PDF
                        # nélküli levelet ennél a forrásnál egyáltalán nem
                        # nézünk meg.
                        continue

                    targy = _fejlec_dekodolas(msg.get("Subject", ""))
                    erkezett_fejlec = msg.get("Date", "")
                    szoveg = email_szoveg_kinyerese(msg)
                    pdf_szoveg = pdf_szoveg_kinyerese(pdf_bytes)
                    teljes_szoveg = f"{szoveg}\n{pdf_szoveg}"

                    tipus = tartalom_tipus_azonositas(targy, teljes_szoveg)
                    statisztika["email_osszesen"] += 1

                    if tipus == "fizetve":
                        statisztika["fizetve"] += 1
                        # A "ceges_szamlak" listának nincs fizetve-fogalma
                        # (ld. dedikált Céges postafiók) - ott ez a
                        # jeloltek-keresés mindig üres lenne, ezért csak
                        # "kozuzemi" célnál van értelme lefuttatni.
                        if cel == "kozuzemi":
                            fizetett_osszeg = osszeg_kinyerese(teljes_szoveg)
                            jeloltek = [
                                (rid, r) for rid, r in szamlak.items()
                                if r.get("szolgaltato") == szolgaltato_kulcs and not r["fizetve"]
                            ]
                            talalat = None
                            if fizetett_osszeg is not None:
                                for rid, r in jeloltek:
                                    if r.get("osszeg") is not None and abs(r["osszeg"] - fizetett_osszeg) < 1:
                                        talalat = rid
                                        break
                            if not talalat and len(jeloltek) == 1:
                                talalat = jeloltek[0][0]
                            if talalat:
                                szamlak[talalat]["fizetve"] = True
                                szamlak[talalat]["fizetve_datum"] = magyar_ido().isoformat()
                                print(f"      ✅ Fizetettre állítva ({cimke}): {szamlak[talalat]['targy'][:50]}")
                        continue

                    if tipus != "uj_szamla":
                        # meroallas/fizetesi_emlekezteto/ismeretlen - itt
                        # szándékosan kihagyva (ez a modul csak a "van-e
                        # új számlám" kérdésre koncentrál, ugyanúgy, mint
                        # a Céges számlák postafiók).
                        continue

                    kinyert_szamlaszam = szamlaszam_kinyerese_altalanos(teljes_szoveg)

                    if cel == "ceges":
                        cid = hashlib.md5(
                            f"{felhasznalo}|{uid_str}|tovabbi_postafiok_ceges".encode("utf-8")
                        ).hexdigest()[:16]
                        if cid in ceges_szamlak or cid in torolt_id_szet:
                            continue
                        kuldo_nev = _ceges_kuldo_nev_kinyerese(msg)
                        feladó_email = _feladó_cim(msg)
                        kinyert_osszeg, kinyert_penznem = osszeg_es_penznem_kinyerese(teljes_szoveg)
                        fajlnev = _ceges_fajlnev(cid, kuldo_nev, pdf_nev)
                        pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
                        drive_url = _ceges_drive_feltoltes(fajlnev, kuldo_nev, pdf_b64)
                        if not drive_url:
                            kesz = False
                            print(f"      ⚠️  '{cimke}' (céges cél): Drive-feltöltés sikertelen, "
                                  f"újra próbáljuk a következő futáskor: {targy[:60]}")
                            continue
                        uj_erkezett = _email_datum_iso(erkezett_fejlec)
                        ceges_szamlak[cid] = {
                            "kuldo_nev": kuldo_nev,
                            "feladó_email": feladó_email,
                            "targy": targy,
                            "erkezett": uj_erkezett,
                            "erkezett_fejlec": erkezett_fejlec,
                            "drive_url": drive_url,
                            "drive_fajlnev": fajlnev,
                            "rogzitve": magyar_ido().isoformat(),
                            "kinyert_osszeg": kinyert_osszeg,
                            "penznem": kinyert_penznem,
                            "kinyert_szamlaszam": kinyert_szamlaszam,
                            "adoszam": None,
                            "nav_szamla_azonosito": None,
                            "nav_parositva": False,
                            "nav_szallito_nev": None,
                            "nav_osszeg": None,
                            "nav_datum": None,
                        }
                        uj_db += 1
                        statisztika["uj_szamla"] += 1
                        print(f"      🆕 Új céges számla ({cimke}): {kuldo_nev} – {targy[:50]}")

                        statisztika["email_ertesitesek"] += 1
                        email_rekord = {
                            "szolgaltato_nev": cimke, "targy": targy,
                            "osszeg": kinyert_osszeg, "penznem": kinyert_penznem,
                            "hatarido": None, "erkezett": uj_erkezett,
                        }
                        email_kuldes(
                            f"📄 Új céges számla – {cimke}",
                            uj_szamla_email_html(email_rekord),
                            [(pdf_nev or "szamla.pdf", pdf_bytes)] if pdf_bytes else None,
                        )
                        tulajdonos_cimzett = _cimzett_string(allapot.get("tulajdonos_emailek"))
                        if tulajdonos_cimzett:
                            statisztika["email_ertesitesek"] += 1
                            email_kuldes(
                                f"📄 Új céges számla – {cimke}",
                                uj_szamla_email_html(email_rekord),
                                [(pdf_nev or "szamla.pdf", pdf_bytes)] if pdf_bytes else None,
                                cimzett=tulajdonos_cimzett,
                            )
                        continue

                    # cel == "kozuzemi" (alapértelmezett) - a régi, változatlan ág.
                    rid = hashlib.md5(f"{felhasznalo}|{uid_str}|tovabbi_postafiok".encode("utf-8")).hexdigest()[:16]
                    if rid in szamlak or rid in torolt_id_szet:
                        continue

                    osszeg, penznem = osszeg_es_penznem_kinyerese(teljes_szoveg)
                    hatarido = hatarido_kinyerese(teljes_szoveg)

                    rekord = {
                        "szolgaltato": szolgaltato_kulcs,
                        "szolgaltato_nev": cimke,
                        "targy": targy,
                        "erkezett": _email_datum_iso(erkezett_fejlec),
                        "erkezett_fejlec": erkezett_fejlec,
                        "osszeg": osszeg,
                        # "HUF" vagy "EUR" - ld. osszeg_es_penznem_kinyerese()
                        # kommentje (a felhasználó kérésére: "van olyan
                        # számlám, ami nem forint, hanem EUR").
                        "penznem": penznem,
                        "hatarido": hatarido,
                        "fizetve": False,
                        "fizetve_datum": None,
                        "uid": uid_str,
                        # Best-effort - ld. a fenti SZAMLASZAM_MINTA_ALTALANOS
                        # komment - kizárólag a NAV-párosításhoz kell (ld.
                        # "NAV ONLINE SZÁMLA" szekció lentebb), None is lehet.
                        "szamlaszam": kinyert_szamlaszam,
                    }
                    szamlak[rid] = rekord
                    pdf_tarolas(allapot, rid, pdf_bytes)
                    uj_db += 1
                    statisztika["uj_szamla"] += 1
                    print(f"      🆕 Új számla ({cimke}): {osszeg_szoveg(osszeg, penznem)} – határidő: {hatarido}")

                    statisztika["email_ertesitesek"] += 1
                    email_kuldes(
                        f"📄 Új számla – {cimke}",
                        uj_szamla_email_html(rekord),
                        [(pdf_nev or "szamla.pdf", pdf_bytes)] if pdf_bytes else None,
                    )
                    tulajdonos_cimzett = _cimzett_string(allapot.get("tulajdonos_emailek"))
                    if tulajdonos_cimzett:
                        statisztika["email_ertesitesek"] += 1
                        email_kuldes(
                            f"📄 Új számla – {cimke}",
                            uj_szamla_email_html(rekord),
                            [(pdf_nev or "szamla.pdf", pdf_bytes)] if pdf_bytes else None,
                            cimzett=tulajdonos_cimzett,
                        )
                finally:
                    if kesz:
                        mar_feldolgozott.add(uid_str)
        except Exception as e:
            print(f"  ⚠️  További postafiók '{cimke}' feldolgozása közben hiba: {e}")
        finally:
            try:
                conn.logout()
            except Exception:
                pass
            bejegyzes["feldolgozott_uidok"] = sorted(mar_feldolgozott)[-2000:]

        if uj_db:
            print(f"  📬 További postafiók '{cimke}': {uj_db} db új számla feldolgozva.")


# ════════════════════════════════════════════
#  🏛️  NAV ONLINE SZÁMLA - BEJÖVŐ SZÁMLÁK LEKÉRDEZÉSE/PÁROSÍTÁS
# ════════════════════════════════════════════
# A felhasználó kérése: a fenti "Céges számlák" postafiókból email-ben
# begyűjtött számlákat vesse össze a NAV Online Számla rendszerben
# nyilvántartott, a cég adószámára befutott BEJÖVŐ (INBOUND) számlákkal -
# ez egy VALÓDI kereszt-ellenőrzés (ha egy eladó NAV-ra beküldött egy
# számlát, de az soha nem érkezett meg emailben, itt kiderül).
#
# HITELESÍTÉS - CSERE-KULCS ("exchangeKey"/"cserekulcs") SZÁNDÉKOSAN NEM
# HASZNÁLT: a NAV API v3-ban a "tokenExchange" hívás (és az ehhez tartozó,
# AES-128/ECB/PKCS5-del dekódolt token) KIZÁRÓLAG a számla-FELTÖLTÉSHEZ
# (manageInvoice/manageAnnulment) szükséges. Az OLVASÓ (query-) hívások -
# köztük a lentebb használt queryInvoiceDigest - közvetlenül, a
# BasicOnlineInvoiceRequestType login/passwordHash/requestSignature
# hármasával hitelesítenek, tokenExchange NÉLKÜL. Mivel itt csak
# OLVASUNK, a cserekulcsra egyáltalán nincs szükség - ezért nincs
# "NAV_CSEREKULCS" env-változó (ld. a modul-docstring NAV_* részét is).
#
# ALÁÍRÁS/HASH SZABÁLYOK (a NAV nyilvános specifikációja + a nav-gov-hu/
# Online-Invoice és pzs/nav-online-invoice nyilvános referencia-
# implementációk alapján):
#   passwordHash     = SHA-512(jelszó), nagybetűs hex, cryptoType="SHA-512"
#   requestSignature = SHA3-512(requestId + időbélyeg["yyyyMMddHHmmss", UTC,
#                       elválasztók/ezredmásodperc NÉLKÜL] + aláíró_kulcs),
#                       nagybetűs hex, cryptoType="SHA3-512" - EZ az
#                       egyszerű forma csak LEKÉRDEZÉS-típusú hívásoknál
#                       helyes (queryInvoiceDigest stb.); számla-
#                       feltöltésnél további, tételenkénti hash-eket is
#                       bele kellene fűzni, de az itt nem kell.
#
# LEKÉRDEZÉSI KORLÁT: a NAV egyetlen queryInvoiceDigest-hívásban legfeljebb
# 35 napos (dateFrom-dateTo) intervallumot enged ("Túl nagy lekérdezési
# intervallum" hiba felette) - ld. _nav_datum_szeletek() lentebb, ami ezt
# <=30 napos szeletekre bontja, biztonsági ráhagyással a 35 alatt.
#
# FONTOS - EZ A KÓD NEM TESZTELT ÉLES NAV-HITELESÍTÉSSEL: mivel a
# munkamenet nem fér hozzá valódi NAV technikai felhasználói adatokhoz, az
# aláírás-/hash-számítás helyességét NEM tudtuk élesben leellenőrizni - a
# fenti szabályok a NAV nyilvános dokumentációja és több, éles integrációk
# által használt nyílt forráskódú referencia-implementáció (php-s
# pzs/nav-online-invoice, ill. a NAV saját nav-gov-hu/Online-Invoice minta-
# fájljai) alapján készültek, de az ELSŐ éles futás naplóját (ld. lentebb a
# nav_allapot "hiba" mezőjét a dashboardon) érdemes ellenőrizni - ha a NAV
# "INVALID_REQUEST_SIGNATURE" vagy hasonló hibát ad, az aláírás-számítás
# igényelhet finomhangolást.
NAV_XML_NEVTEREK = {
    "a": "http://schemas.nav.gov.hu/OSA/3.0/api",
    "c": "http://schemas.nav.gov.hu/NTCA/1.0/common",
}


def _nav_sha512_hex(szoveg: str) -> str:
    return hashlib.sha512(szoveg.encode("utf-8")).hexdigest().upper()


def _nav_sha3_512_hex(szoveg: str) -> str:
    return hashlib.sha3_512(szoveg.encode("utf-8")).hexdigest().upper()


def _nav_uj_request_id() -> str:
    """A NAV előírja: max 30 karakter, csak betű/szám, és MINDEN kérésnek
    egyedinek kell lennie (egy már - akár hibásan - felhasznált requestId
    újbóli beküldése "REQUEST_ID_NOT_UNIQUE" hibát ad, még ha az előző
    kérés el is lett utasítva)."""
    return "SF" + magyar_ido().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:8].upper()


def _nav_idobelyegek():
    """(iso_idobelyeg, tomor_idobelyeg) - MINDKETTŐ UTC-ben. Az XML
    fejlécbe az ISO-forma kerül (pl. "2026-09-26T20:15:30.123Z"), a
    requestSignature-höz viszont a tömör, elválasztók nélküli forma
    (pl. "20260926201530") - ld. a szekció elején lévő komment."""
    most = datetime.now(timezone.utc)
    iso = most.strftime("%Y-%m-%dT%H:%M:%S.") + f"{most.microsecond // 1000:03d}Z"
    tomor = most.strftime("%Y%m%d%H%M%S")
    return iso, tomor


def _nav_alairas(request_id: str, tomor_idobelyeg: str) -> str:
    return _nav_sha3_512_hex(f"{request_id}{tomor_idobelyeg}{NAV_ALAIRO_KULCS}")


def _nav_query_invoice_digest_keres_xml(page: int, datum_tol: str, datum_ig: str) -> str:
    """Egy queryInvoiceDigest kérés XML-je - INBOUND (bejövő) irányra és a
    megadott [datum_tol, datum_ig] (kiállítási dátum) intervallumra szűrve.
    Az elemsorrendet/névtereket a NAV nyilvános mintafájljai alapján
    állítottuk össze (ld. szekció-komment)."""
    request_id = _nav_uj_request_id()
    iso_idobelyeg, tomor_idobelyeg = _nav_idobelyegek()
    alairas = _nav_alairas(request_id, tomor_idobelyeg)
    jelszo_hash = _nav_sha512_hex(NAV_TECHNIKAI_JELSZO)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<QueryInvoiceDigestRequest xmlns:common="http://schemas.nav.gov.hu/NTCA/1.0/common" xmlns="http://schemas.nav.gov.hu/OSA/3.0/api">
  <common:header>
    <common:requestId>{_xml_esc(request_id)}</common:requestId>
    <common:timestamp>{_xml_esc(iso_idobelyeg)}</common:timestamp>
    <common:requestVersion>3.0</common:requestVersion>
    <common:headerVersion>1.0</common:headerVersion>
  </common:header>
  <common:user>
    <common:login>{_xml_esc(NAV_TECHNIKAI_LOGIN)}</common:login>
    <common:passwordHash cryptoType="SHA-512">{jelszo_hash}</common:passwordHash>
    <common:taxNumber>{_xml_esc(NAV_ADOSZAM)}</common:taxNumber>
    <common:requestSignature cryptoType="SHA3-512">{alairas}</common:requestSignature>
  </common:user>
  <software>
    <softwareId>{_xml_esc(NAV_SOFTWARE_ID)}</softwareId>
    <softwareName>{_xml_esc(NAV_SOFTWARE_NEV)}</softwareName>
    <softwareOperation>LOCAL_SOFTWARE</softwareOperation>
    <softwareMainVersion>1.0</softwareMainVersion>
    <softwareDevName>{_xml_esc(NAV_SOFTWARE_FEJLESZTO_NEV)}</softwareDevName>
    <softwareDevContact>{_xml_esc(NAV_SOFTWARE_FEJLESZTO_EMAIL)}</softwareDevContact>
    <softwareDevCountryCode>HU</softwareDevCountryCode>
    <softwareDevTaxNumber>{_xml_esc(NAV_ADOSZAM)}</softwareDevTaxNumber>
  </software>
  <page>{page}</page>
  <invoiceDirection>INBOUND</invoiceDirection>
  <invoiceQueryParams>
    <mandatoryQueryParams>
      <invoiceIssueDate>
        <dateFrom>{_xml_esc(datum_tol)}</dateFrom>
        <dateTo>{_xml_esc(datum_ig)}</dateTo>
      </invoiceIssueDate>
    </mandatoryQueryParams>
  </invoiceQueryParams>
</QueryInvoiceDigestRequest>"""


def _nav_xml_elem(gyoker, utvonal):
    """Segédfüggvény a névtér-prefixes ('a:invoiceDigestResult' formátumú)
    útvonalak kereséséhez - a beépített ElementTree find()/findall() a
    NAV_XML_NEVTEREK szótárral pontosan ezt a formát várja."""
    return gyoker.find(utvonal, NAV_XML_NEVTEREK)


def _nav_query_invoice_digest_lap(page: int, datum_tol: str, datum_ig: str):
    """Egyetlen HTTP-hívás (egyetlen lap) - a hívó (nav_bejovo_szamlak_lekerese())
    lapozva hívja, amíg jelenlegi_lap < elerheto_lapok. "ok"=False esetén a
    "hiba" mezőben a NAV hibaüzenete (vagy egy hálózati/XML-hiba szövege)."""
    kerest_xml = _nav_query_invoice_digest_keres_xml(page, datum_tol, datum_ig)
    try:
        valasz = requests.post(
            f"{NAV_API_BASE_URL}/queryInvoiceDigest",
            data=kerest_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml", "Accept": "application/xml"},
            timeout=30,
        )
    except Exception as e:
        return {"ok": False, "hiba": f"Hálózati hiba: {e}"}

    try:
        gyoker = ET.fromstring(valasz.content)
    except ET.ParseError as e:
        return {"ok": False, "hiba": f"A NAV válasza nem valid XML (HTTP {valasz.status_code}): {e}"}

    # Hibás kérésnél (pl. rossz aláírás, túl nagy intervallum, lejárt
    # jelszó) a NAV egy "GeneralExceptionResponse" gyökérelemmel válaszol,
    # EGYÁLTALÁN NEM "QueryInvoiceDigestResponse"-szal - ezt itt külön
    # kezelni kell, különben a lenti keresések csendben None-t adnának.
    gyoker_nev = gyoker.tag.split("}")[-1]
    if gyoker_nev != "QueryInvoiceDigestResponse":
        hiba_kod = _nav_xml_elem(gyoker, "c:errorCode")
        hiba_uzenet = _nav_xml_elem(gyoker, "c:message")
        return {
            "ok": False,
            "hiba": gyoker_nev
                    + (f" ({hiba_kod.text})" if hiba_kod is not None else "")
                    + (f": {hiba_uzenet.text}" if hiba_uzenet is not None else f" (HTTP {valasz.status_code})"),
        }

    eredmeny_elem = _nav_xml_elem(gyoker, "c:result")
    func_kod = _nav_xml_elem(eredmeny_elem, "c:funcCode") if eredmeny_elem is not None else None
    if func_kod is not None and func_kod.text != "OK":
        hiba_kod = _nav_xml_elem(eredmeny_elem, "c:errorCode")
        hiba_uzenet = _nav_xml_elem(eredmeny_elem, "c:message")
        return {
            "ok": False,
            "hiba": (hiba_kod.text if hiba_kod is not None else func_kod.text)
                    + (f": {hiba_uzenet.text}" if hiba_uzenet is not None else ""),
        }

    digest_eredmeny = _nav_xml_elem(gyoker, "a:invoiceDigestResult")
    if digest_eredmeny is None:
        return {"ok": True, "jelenlegi_lap": page, "elerheto_lapok": page, "tetelek": []}

    jelenlegi_lap = _nav_xml_elem(digest_eredmeny, "a:currentPage")
    elerheto_lapok = _nav_xml_elem(digest_eredmeny, "a:availablePage")

    tetelek = []
    for digest in digest_eredmeny.findall("a:invoiceDigest", NAV_XML_NEVTEREK):
        def _szoveg(nev):
            el = digest.find(f"a:{nev}", NAV_XML_NEVTEREK)
            return el.text.strip() if el is not None and el.text else None

        tetelek.append({
            "szamlaszam": _szoveg("invoiceNumber"),
            "kiallitas_datum": _szoveg("invoiceIssueDate"),
            "szallito_adoszam": _szoveg("supplierTaxNumber"),
            "szallito_nev": _szoveg("supplierName"),
            "vevo_adoszam": _szoveg("customerTaxNumber"),
            "netto_osszeg": _szoveg("invoiceNetAmount"),
            "netto_osszeg_huf": _szoveg("invoiceNetAmountHUF"),
            "afa_osszeg": _szoveg("invoiceVatAmount"),
            "afa_osszeg_huf": _szoveg("invoiceVatAmountHUF"),
            "penznem": _szoveg("currency"),
            "muvelet": _szoveg("invoiceOperation"),
        })

    return {
        "ok": True,
        "jelenlegi_lap": int(jelenlegi_lap.text) if jelenlegi_lap is not None else page,
        "elerheto_lapok": int(elerheto_lapok.text) if elerheto_lapok is not None else page,
        "tetelek": tetelek,
    }


def _nav_datum_szeletek(napok_visszamenoleg: int):
    """A NAV egyetlen hívásban legfeljebb 35 napos intervallumot enged -
    ha a kívánt visszatekintés ennél nagyobb, <=30 napos (biztonsági
    ráhagyással a 35 alatt) szeletekre bontjuk. A legfrissebb szeletet adja
    először, hogy egy esetleges hiba/megszakítás a friss adatokat érje el
    elsőként."""
    ma = magyar_ma()
    kezdet = ma - timedelta(days=napok_visszamenoleg)
    szeletek = []
    szelet_vege = ma
    while szelet_vege > kezdet:
        szelet_kezdet = max(kezdet, szelet_vege - timedelta(days=30))
        szeletek.append((szelet_kezdet.isoformat(), szelet_vege.isoformat()))
        szelet_vege = szelet_kezdet - timedelta(days=1)
    return szeletek


def nav_bejovo_szamlak_lekerese(allapot: dict):
    """Lekérdezi a NAV-tól az ÖSSZES bejövő (INBOUND) számla-tételt az
    utolsó NAV_LEKERDEZES_NAPOK_VISSZA napból (több, <=30 napos szeletben
    és lapozva, ld. fent) - az "allapot"-ba csak a "nav_allapot" login/
    hiba-visszajelzést írja (ugyanaz a minta, mint a "ceges_allapot"-nál a
    Céges számlák szekcióban) - a tényleges tételeket egyszerűen
    VISSZAADJA, a hívó (nav_ceges_parositas()) dolga eldönteni, mit tesz
    velük. None-t ad vissza, ha a modul nincs beállítva, DRY_RUN alatt fut,
    vagy MINDEN szelet/lap hibázott (ld. nav_allapot["hiba"])."""
    nav_allapot = allapot.setdefault("nav_allapot", {})

    def _allapot_rogzitese(sikeres: bool, hiba=None, talalt_db=None):
        nav_allapot["utolso_probalkozas"] = magyar_ido().isoformat()
        nav_allapot["sikeres_lekerdezes"] = sikeres
        nav_allapot["hiba"] = hiba
        if talalt_db is not None:
            nav_allapot["utolso_futas_talalt_db"] = talalt_db

    if not (NAV_TECHNIKAI_LOGIN and NAV_TECHNIKAI_JELSZO and NAV_ALAIRO_KULCS and NAV_ADOSZAM):
        nav_allapot["beallitva"] = False
        print("  ℹ️  NAV Online Számla: NAV_TECHNIKAI_LOGIN / NAV_TECHNIKAI_JELSZO / "
              "NAV_ALAIRO_KULCS / NAV_ADOSZAM nincs (teljesen) beállítva - a modul kihagyva.")
        return None
    nav_allapot["beallitva"] = True

    if DRY_RUN:
        print("  🧪 [DRY RUN] NAV Online Számla lekérdezés kihagyva.")
        return None

    osszes_tetel = []
    for datum_tol, datum_ig in _nav_datum_szeletek(NAV_LEKERDEZES_NAPOK_VISSZA):
        page = 1
        while True:
            eredmeny = _nav_query_invoice_digest_lap(page, datum_tol, datum_ig)
            if not eredmeny["ok"]:
                _allapot_rogzitese(False, eredmeny["hiba"])
                print(f"  ❌ NAV Online Számla lekérdezés sikertelen "
                      f"({datum_tol}–{datum_ig}, {page}. lap): {eredmeny['hiba']}")
                return osszes_tetel or None
            osszes_tetel.extend(eredmeny["tetelek"])
            if eredmeny["jelenlegi_lap"] >= eredmeny["elerheto_lapok"] or not eredmeny["tetelek"]:
                break
            page += 1
            if page > 50:  # védőháló - nem várt sok lap esetén ne fusson a végtelenségig
                break

    _allapot_rogzitese(True, None, len(osszes_tetel))
    print(f"  🏛️  NAV Online Számla: {len(osszes_tetel)} db bejövő számla-tétel lekérve "
          f"az elmúlt {NAV_LEKERDEZES_NAPOK_VISSZA} napból.")
    return osszes_tetel


def _nav_osszeg_egyezik(a, b, tolerancia=1.0) -> bool:
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tolerancia
    except (TypeError, ValueError):
        return False


def _nav_parosithato_rekordok(allapot: dict):
    """Egységesített (szamlaszam, osszeg) nézetet ad a KÉT különböző
    forrás fölé, amit a NAV-párosítás megpróbálhat összevetni - ld.
    nav_szamla_parositas() docstring-jét:
      - allapot["szamlak"] (Közüzemi/fő lista: Díjnet/Vízművek/MVM/
        "további postafiókok") - itt a mező neve "szamlaszam"/"osszeg"
        (Díjnetnél/Vízműveknél valódi, portálról kiolvasott adat; a
        "további postafiókok"-nál és MVM-nél best-effort/hiányozhat).
      - allapot["ceges_szamlak"] (Céges fül) - itt "kinyert_szamlaszam"/
        "kinyert_osszeg" a mező neve (ld. ceges_szamlak_feldolgozasa()).
    Minden elemre (rekord, szamlaszam, osszeg, adoszam) négyest ad vissza
    - az "adoszam" a dashboardon (Céges fül, "Adószám" mező, ld.
    szamlak.html cegesMezoMentese()) kézzel megadható, KÉZI mező (a
    script sehonnan nem tölti ki automatikusan) - amikor ki van töltve,
    a nav_szamla_parositas() ezt is felhasználja egy erősebb, célzottabb
    párosítási körben (ld. ott az "1.5 kör" kommentjét). A "rekord" maga
    a MUTÁLHATÓ dict-referencia (ugyanaz az objektum, ami az
    allapot["szamlak"]/["ceges_szamlak"] dict-ben is van), hogy a hívó
    közvetlenül ráírhassa a "nav_*" mezőket."""
    eredmeny = []
    for rekord in allapot.get("szamlak", {}).values():
        if rekord.get("nav_parositva"):
            continue
        eredmeny.append((rekord, rekord.get("szamlaszam"), rekord.get("osszeg"), rekord.get("adoszam")))
    for rekord in allapot.get("ceges_szamlak", {}).values():
        if rekord.get("nav_parositva"):
            continue
        eredmeny.append((rekord, rekord.get("kinyert_szamlaszam"), rekord.get("kinyert_osszeg"), rekord.get("adoszam")))
    return eredmeny


def nav_szamla_parositas(allapot: dict):
    """Összeveti a nav_bejovo_szamlak_lekerese()-vel lekért NAV-tételeket
    MINDKÉT hellyel begyűjtött számla-rekorddal: a "Céges számlák" fülön
    (email-ből, allapot["ceges_szamlak"]) ÉS a Közüzemi/fő listával
    (allapot["szamlak"] - Díjnet/Vízművek/MVM/"további postafiókok") - a
    felhasználó kifejezett kérésére ("a másik fülben lévő számlák is a
    cégnevére jönnek nagyrészt, hasonlítsa össze"), mert ez utóbbiak is
    jellemzően a cég adószámára befutó, NAV-nál nyilvántartott számlák.
    Ld. a fenti szekció-komment "ALÁÍRÁS/HASH SZABÁLYOK" utáni részét az
    általános elvért.

    FONTOS - EZ CSAK BEST-EFFORT: a párosítás ELSŐDLEGESEN a számlaszám
    EGYEZÉSÉRE hagyatkozik (ahol van - a Díjnet/Vízművek-rekordoknál ez
    valódi, portálról kiolvasott adat, a többinél PDF-ből/szövegből
    best-effort kinyert), MÁSODLAGOSAN (ha számlaszám nincs vagy nem
    egyezik semelyik NAV-tétellel) az összeg (±1 Ft) + a kiállítási
    dátum és az email-érkezés dátuma közti ±7 napos közelségre. Ha egyik
    sem talál, a rekord egyszerűen párosítatlan marad (nav_parositva
    marad False/hiányzik) - ez NEM hiba, csak azt jelenti, hogy a
    felhasználónak kézzel kell ellenőriznie.

    A NAV-on megtalált, de EGYIK forrásban sem szereplő tételeket az
    allapot["nav_csak_navban"] listába mentjük - ez a tényleges "hiányzik
    egy számla" riasztás, amiért a felhasználó a NAV-összekötést kérte."""
    nav_tetelek = nav_bejovo_szamlak_lekerese(allapot)
    if nav_tetelek is None:
        return  # nincs beállítva, DRY_RUN, vagy hiba - ld. nav_allapot a dashboardon

    def _nav_tetel_kulcs(tetel):
        return f"{tetel.get('szallito_adoszam')}|{tetel.get('szamlaszam')}"

    parositando = _nav_parosithato_rekordok(allapot)
    parositott_nav_kulcsok = set()

    # 1. kör - számlaszám EGYEZÉS (a legmegbízhatóbb jel, ha van).
    for rekord, szamlaszam, _osszeg, _adoszam in parositando:
        sajat_szamlaszam = (szamlaszam or "").strip().upper()
        if not sajat_szamlaszam:
            continue
        for tetel in nav_tetelek:
            nav_szamlaszam = (tetel.get("szamlaszam") or "").strip().upper()
            if not nav_szamlaszam or nav_szamlaszam != sajat_szamlaszam:
                continue
            kulcs = _nav_tetel_kulcs(tetel)
            if kulcs in parositott_nav_kulcsok:
                continue
            rekord["nav_parositva"] = True
            rekord["nav_szamla_azonosito"] = kulcs
            rekord["nav_szallito_nev"] = tetel.get("szallito_nev")
            rekord["nav_osszeg"] = tetel.get("netto_osszeg_huf") or tetel.get("netto_osszeg")
            rekord["nav_datum"] = tetel.get("kiallitas_datum")
            parositott_nav_kulcsok.add(kulcs)
            break

    # 1.5 kör - ha a felhasználó KÉZZEL megadott egy adószámot a
    # rekordhoz (Céges fül, "Adószám" mező - ld. _nav_parosithato_rekordok()
    # kommentje), az egy ERŐS, SPECIFIKUS jel: csak az ADOTT adószámú
    # NAV-szállító tételei közül keresünk, köztük is csak az összeg (±1 Ft)
    # alapján - dátum-egyezést itt NEM követelünk meg, mert az adószám
    # önmagában elég specifikus (egy szállítónak jellemzően nem lesz két
    #, egymáshoz ±1 Ft-ra eső bejövő számlája egyszerre).
    for rekord, _szamlaszam, sajat_osszeg, sajat_adoszam in parositando:
        if rekord.get("nav_parositva"):
            continue
        adoszam_tiszta = (sajat_adoszam or "").strip()
        if not adoszam_tiszta or sajat_osszeg is None:
            continue
        for tetel in nav_tetelek:
            if (tetel.get("szallito_adoszam") or "").strip() != adoszam_tiszta:
                continue
            kulcs = _nav_tetel_kulcs(tetel)
            if kulcs in parositott_nav_kulcsok:
                continue
            nav_osszeg = tetel.get("netto_osszeg_huf") or tetel.get("netto_osszeg")
            if not _nav_osszeg_egyezik(sajat_osszeg, nav_osszeg):
                continue
            rekord["nav_parositva"] = True
            rekord["nav_szamla_azonosito"] = kulcs
            rekord["nav_szallito_nev"] = tetel.get("szallito_nev")
            rekord["nav_osszeg"] = nav_osszeg
            rekord["nav_datum"] = tetel.get("kiallitas_datum")
            parositott_nav_kulcsok.add(kulcs)
            break

    # 2. kör - összeg (±1 Ft) + dátum (±7 nap) egyezés azoknál, amik az
    # eddigi köröknél (számlaszám/adószám hiánya vagy egyezés-hiánya
    # miatt) még párosítatlanok.
    for rekord, _szamlaszam, sajat_osszeg, _adoszam in parositando:
        if rekord.get("nav_parositva"):
            continue
        if sajat_osszeg is None:
            continue
        erkezett = (rekord.get("erkezett") or "")[:10]
        try:
            erkezett_datum = date.fromisoformat(erkezett) if erkezett else None
        except ValueError:
            erkezett_datum = None

        for tetel in nav_tetelek:
            kulcs = _nav_tetel_kulcs(tetel)
            if kulcs in parositott_nav_kulcsok:
                continue
            nav_osszeg = tetel.get("netto_osszeg_huf") or tetel.get("netto_osszeg")
            if not _nav_osszeg_egyezik(sajat_osszeg, nav_osszeg):
                continue
            if erkezett_datum is not None and tetel.get("kiallitas_datum"):
                try:
                    nav_datum = date.fromisoformat(tetel["kiallitas_datum"][:10])
                    if abs((erkezett_datum - nav_datum).days) > 7:
                        continue
                except ValueError:
                    pass
            rekord["nav_parositva"] = True
            rekord["nav_szamla_azonosito"] = kulcs
            rekord["nav_szallito_nev"] = tetel.get("szallito_nev")
            rekord["nav_osszeg"] = nav_osszeg
            rekord["nav_datum"] = tetel.get("kiallitas_datum")
            parositott_nav_kulcsok.add(kulcs)
            break

    csak_navban = [
        tetel for tetel in nav_tetelek if _nav_tetel_kulcs(tetel) not in parositott_nav_kulcsok
    ]
    allapot["nav_csak_navban"] = csak_navban

    parositott_db = sum(1 for rekord, _s, _o, _a in parositando if rekord.get("nav_parositva"))
    print(f"  🔗 NAV-párosítás: {parositott_db} db számla párosítva a NAV-adatokkal (Közüzemi + "
          f"Céges összesen), {len(csak_navban)} db NAV-tétel maradt párosítatlanul (lehet, hogy "
          f"még nem érkezett meg emailben, vagy nem egy figyelt postafiókba jött).")


# ════════════════════════════════════════════
#  ✉️  NAV-ON TALÁLT, HIÁNYZÓ SZÁMLÁK EMLÉKEZTETŐJE
# ════════════════════════════════════════════
# A fenti nav_szamla_parositas() "nav_csak_navban" listája (NAV-on
# nyilvántartott, de emailben SOHA meg nem érkezett számlák) mellé a
# felhasználó kérésére a dashboardon (Céges számlák fül, NAV-panel) egy
# szállítónkénti email-cím rögzíthető (allapot["nav_szallito_emailek"] -
# {adószám: email}, a dashboard a MEGLÉVŐ allapotFrissitesEsMentese()
# mintával menti, ugyanolyan titkosítva, mint minden más adat), és a
# felhasználó kijelölheti, mely szállítóknak menjen ki egy udvarias,
# sablon-szövegű kérés a hiányzó számla(k) másolatáért - ez a
# SZAMLA_NAV_EMLEKEZTETO_ADOSZAMOK workflow_dispatch inputtal (vesszővel
# elválasztott adószám-lista) érkezik ide.
def _nav_emlekezteto_email_html(szallito_nev: str, tetelek: list) -> str:
    sorok = "".join(
        f"<li>{_esc(t.get('szamlaszam') or 'ismeretlen számlaszám')} – "
        f"{_esc((t.get('kiallitas_datum') or '')[:10] or 'ismeretlen dátum')} – "
        f"{forint(float(t['netto_osszeg_huf'] or t['netto_osszeg'])) if (t.get('netto_osszeg_huf') or t.get('netto_osszeg')) else 'ismeretlen összeg'}</li>"
        for t in tetelek
    )
    cel_cim = CEGES_IMAP_USER or EMAIL_CIMZETT or "(kérjük, válaszoljon erre az e-mailre)"
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;">
      <p>Tisztelt {_esc(szallito_nev)}!</p>
      <p>Nyilvántartásunk (a NAV Online Számla rendszer adatai) szerint az
      alábbi, Önök által kiállított számlá(k)nak nincs meg nálunk az
      elektronikus (email-es) másolata:</p>
      <ul>{sorok}</ul>
      <p>Kérjük, legyenek szívesek elküldeni ezek másolatát a
      <strong>{_esc(cel_cim)}</strong> email-címre.</p>
      <p>Segítségüket előre is köszönjük!</p>
    </div>
    """


def nav_hianyzo_szamla_emlekezteto_kuldese(allapot: dict):
    """Ld. a szekció elején lévő komment - teljesen no-op, ha a
    SZAMLA_NAV_EMLEKEZTETO_ADOSZAMOK env-változó üres (ez a NORMÁL eset -
    ütemezett futásnál MINDIG üres, csak a dashboard gombjával indított
    workflow_dispatch-nál kaphat tartalmat, ld. modul-docstring eleje)."""
    if not SZAMLA_NAV_EMLEKEZTETO_ADOSZAMOK:
        return

    kijelolt_adoszamok = {a.strip() for a in SZAMLA_NAV_EMLEKEZTETO_ADOSZAMOK.split(",") if a.strip()}
    if not kijelolt_adoszamok:
        return

    szallito_emailek = allapot.get("nav_szallito_emailek", {})
    csak_navban = allapot.get("nav_csak_navban", [])

    kuldott_db = 0
    for adoszam in kijelolt_adoszamok:
        email_cim = (szallito_emailek.get(adoszam) or "").strip()
        if not email_cim:
            print(f"  ⚠️  NAV-emlékeztető: nincs elmentett email-cím a {adoszam} adószámú "
                  f"szállítóhoz - kihagyva.")
            continue
        sajat_tetelek = [t for t in csak_navban if t.get("szallito_adoszam") == adoszam]
        if not sajat_tetelek:
            print(f"  ℹ️  NAV-emlékeztető: a {adoszam} adószámhoz jelenleg nincs párosítatlan "
                  f"NAV-tétel (talán már időközben megérkezett/párosult) - kihagyva.")
            continue
        szallito_nev = sajat_tetelek[0].get("szallito_nev") or adoszam
        sikeres = email_kuldes(
            f"📄 Hiányzó számla-másolat kérése – {szallito_nev}",
            _nav_emlekezteto_email_html(szallito_nev, sajat_tetelek),
            cimzett=email_cim,
        )
        if sikeres:
            kuldott_db += 1
            print(f"  ✉️  NAV-emlékeztető elküldve: {szallito_nev} ({email_cim}), "
                  f"{len(sajat_tetelek)} db hiányzó számláról.")

    print(f"  ✉️  NAV-emlékeztető: összesen {kuldott_db} db email elküldve "
          f"{len(kijelolt_adoszamok)} kijelölt szállítóból.")


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

    try:
        allapot = visszafejt(TITKOSITAS_JELSZO, ALLAPOT_FAJL)
    except RuntimeError as e:
        print(f"❌ {e}")
        return

    szamlak = allapot.setdefault("szamlak", {})
    meroallasok = allapot.setdefault("meroallasok", {})
    ismeretlen_dokumentumok = allapot.setdefault("ismeretlen_dokumentumok", {})
    ismeretlen_fizetesek = allapot.setdefault("ismeretlen_fizetesek", {})
    feldolgozott_uidok = set(allapot.setdefault("feldolgozott_uidok", []))

    # A dashboardon (szamlak.html "Beállítások" panel) esetlegesen
    # felülírt paraméterek - ha nincs beállítás-fájl, minden a régi
    # (modul-konstans/automatikus) módon működik.
    beallitasok = beallitasok_betoltese()
    emlekezteto_napok = beallitasok["emlekezteto_napok_elotte"] or SZAMLA_EMLEKEZTETO_NAPOK_ELOTTE

    # A dashboard "X" gombjával véglegesen elrejtett számlák törlése - ld.
    # a BEALLITASOK_FAJL "torolt_szamla_id_k" mezőjének kommentjét. Minden
    # futáskor megtörténik, MIELŐTT a portál-lekérdezések újra beírnák
    # ugyanezeket (ha időközben ismét megjelennének a forrásnál) - így egy
    # törölt számla tartósan el marad rejtve, nem "támad fel" a következő
    # futásnál.
    torolt_id_k = beallitasok["torolt_szamla_id_k"]
    torolt_id_szet = set(torolt_id_k)  # gyors "benne van-e" ellenőrzéshez a lenti feldolgozó-ágakban
    if torolt_id_k:
        pdf_adatok = allapot.setdefault("pdf_adatok", {})
        # A "Céges számlák" fülnek is van saját "✕" elrejtés-gombja a
        # dashboardon (ld. szamlak.html torlesVegrehajtasaCeges()) -
        # ugyanabba a "torolt_szamla_id_k" listába ír, ezért itt is
        # töröljük a "ceges_szamlak"-ból, nemcsak a fő "szamlak"-ból.
        ceges_szamlak_torleshez = allapot.setdefault("ceges_szamlak", {})
        torolve_db = 0
        for tid in torolt_id_k:
            if tid in szamlak:
                del szamlak[tid]
                torolve_db += 1
            if tid in ceges_szamlak_torleshez:
                del ceges_szamlak_torleshez[tid]
                torolve_db += 1
            pdf_adatok.pop(tid, None)
        if torolve_db:
            print(f"  🗑️  {torolve_db} db, a dashboardon véglegesen elrejtett számla törölve.")

    # Az email-küldés globális ki/bekapcsolása - ezt MINDEN email_kuldes()-
    # hívás előtt be kell állítani, ezért itt, a feldolgozás legelején
    # történik meg.
    global EMAIL_KIKAPCSOLVA
    EMAIL_KIKAPCSOLVA = beallitasok["email_kikapcsolva"]
    if EMAIL_KIKAPCSOLVA:
        print("🔕 Email-küldés jelenleg LE VAN TILTVA a dashboard beállításaiban "
              "(Beállítások → Email-küldés engedélyezve) - a feldolgozás/adatmentés "
              "változatlanul lezajlik, csak értesítő email nem megy ki.")

    # Futási statisztika - a végén egy összefoglaló sorban kiírjuk, ez
    # sokat segít a naplóból gyorsan átlátni, mi történt egy futás alatt.
    statisztika = {
        "email_osszesen": 0, "uj_szamla": 0, "fizetve": 0,
        "fizetesi_emlekezteto": 0, "meroallas": 0, "ismeretlen": 0,
        "fizetes_nem_azonositott": 0, "dijnet_uj_szamla": 0,
        "dijnet_fizetve_frissites": 0, "email_ertesitesek": 0,
        "vizmuvek_uj_szamla": 0, "vizmuvek_fizetve_frissites": 0,
    }

    # ---- 1. Új emailek beolvasása ----
    try:
        conn = imap_kapcsolat()
    except Exception as e:
        print(f"❌ IMAP-bejelentkezés sikertelen: {e}")
        return

    try:
        uj_uidok = uj_uidok_lekerese(conn, feldolgozott_uidok)
        print(f"📬 {len(uj_uidok)} még feldolgozatlan email az elmúlt {IMAP_LEKERDEZES_NAPOK} napból.")

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
            statisztika["email_osszesen"] += 1

            # ---- fizetve ----
            if tipus == "fizetve":
                statisztika["fizetve"] += 1
                fizetett_osszeg = osszeg_kinyerese(teljes_szoveg_egyesitve)
                jeloltek = [
                    (rid, r) for rid, r in szamlak.items()
                    if r["szolgaltato"] == szolgaltato and not r["fizetve"]
                ]
                talalat = None
                indoklas = ""
                if fizetett_osszeg is not None:
                    for rid, r in jeloltek:
                        if r["osszeg"] is not None and abs(r["osszeg"] - fizetett_osszeg) < 1:
                            talalat = rid
                            indoklas = "összeg-egyezés alapján"
                            break
                if not talalat and len(jeloltek) == 1:
                    # Csak akkor "tippelünk" biztonságosan, ha nincs
                    # kétértelműség: pontosan EGY fizetetlen számla van
                    # ettől a szolgáltatótól, tehát nem lehet más, akire
                    # a visszaigazolás vonatkozhatna.
                    talalat = jeloltek[0][0]
                    indoklas = "az egyetlen fizetetlen számla ennél a szolgáltatónál"
                # FONTOS: SZÁNDÉKOSAN NINCS további fallback (pl. "vegyük a
                # legrégebbi fizetetlen számlát"), ha több, egymással
                # versengő jelölt van összeg-egyezés nélkül - inkább
                # maradjon egy számla átmenetileg tévesen fizetetlennek
                # jelölve, mint hogy egy MÁSIK, valójában még fizetetlen
                # számlát véletlenül fizetettre állítsunk.
                if talalat:
                    szamlak[talalat]["fizetve"] = True
                    szamlak[talalat]["fizetve_datum"] = magyar_ido().isoformat()
                    print(f"      ✅ Fizetettre állítva ({indoklas}): "
                          f"{szolgaltato} / {szamlak[talalat]['targy'][:50]}")
                else:
                    statisztika["fizetes_nem_azonositott"] += 1
                    print(f"      ⚠️  Fizetési visszaigazolás érkezett ({szolgaltato}), de nem "
                          f"azonosítható biztonságosan egyetlen fizetetlen számlához sem "
                          f"({len(jeloltek)} versengő jelölt) - naplózva, kézi ellenőrzést igényel.")
                    fid = hashlib.md5(f"{uid_str}|fizetve".encode("utf-8")).hexdigest()[:16]
                    ismeretlen_fizetesek[fid] = {
                        "szolgaltato": szolgaltato,
                        "szolgaltato_nev": cfg["nev"],
                        "targy": targy,
                        "erkezett": _email_datum_iso(erkezett_fejlec),
                        "fizetett_osszeg": fizetett_osszeg,
                        "jelolt_szamlak": [rid for rid, _ in jeloltek],
                        "uid": uid_str,
                    }
                continue

            # ---- fizetesi_emlekezteto: szándékosan nem hoz létre semmit ----
            if tipus == "fizetesi_emlekezteto":
                statisztika["fizetesi_emlekezteto"] += 1
                print(f"      ℹ️  Fizetési emlékeztető ({szolgaltato}) - kihagyva, "
                      "nem hoz létre új tételt.")
                continue

            # ---- meroallas ----
            if tipus == "meroallas":
                statisztika["meroallas"] += 1
                mid = hashlib.md5(f"{uid_str}|meroallas".encode("utf-8")).hexdigest()[:16]
                if mid in meroallasok:
                    continue
                ertek_info = meroallas_ertek_kinyerese(teljes_szoveg_egyesitve) or {}
                mrekord = {
                    "szolgaltato": szolgaltato,
                    "szolgaltato_nev": cfg["nev"],
                    "targy": targy,
                    "erkezett": _email_datum_iso(erkezett_fejlec),
                    "erkezett_fejlec": erkezett_fejlec,
                    "ertek": ertek_info.get("ertek"),
                    "mertekegyseg": ertek_info.get("mertekegyseg"),
                    "uid": uid_str,
                }
                meroallasok[mid] = mrekord
                print(f"      🔢 Mérőállás-esemény: {cfg['nev']} – {targy[:60]}")
                if MEROALLAS_ERTESITES_EMAIL:
                    statisztika["email_ertesitesek"] += 1
                    email_kuldes(
                        f"🔢 Mérőállás – {cfg['nev']}",
                        uj_meroallas_email_html(mrekord),
                    )
                continue

            # ---- uj_szamla ----
            if tipus == "uj_szamla":
                statisztika["uj_szamla"] += 1
                rid = hashlib.md5(f"{uid_str}|uj_szamla".encode("utf-8")).hexdigest()[:16]
                if rid in szamlak or rid in torolt_id_szet:
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
                    "erkezett": _email_datum_iso(erkezett_fejlec),
                    "erkezett_fejlec": erkezett_fejlec,
                    "osszeg": osszeg,
                    "hatarido": hatarido,
                    "fizetve": False,
                    "fizetve_datum": None,
                    "uid": uid_str,
                }
                szamlak[rid] = rekord
                pdf_tarolas(allapot, rid, pdf_bytes)
                print(f"      🆕 Új számla: {cfg['nev']} – {forint(osszeg)} – határidő: {hatarido}")

                statisztika["email_ertesitesek"] += 1
                email_kuldes(
                    f"📄 Új számla – {cfg['nev']}",
                    uj_szamla_email_html(rekord),
                    [(pdf_nev or "szamla.pdf", pdf_bytes)] if pdf_bytes else None,
                )
                # A tulajdonos MINDEN "új számla" értesítés másolatát megkapja,
                # forrástól függetlenül (ld. "3 CÍMZETTI KÖR" szekció) - ez az
                # IMAP-os (pl. MVM) ág nem megy át a Díjnet/Vízművek közös
                # _uj_szamla_ertesites_kuldese()-n (annak nincs itt "kor"
                # fogalma), ezért itt külön küldjük a másolatot.
                tulajdonos_cimzett = _cimzett_string(allapot.get("tulajdonos_emailek"))
                if tulajdonos_cimzett:
                    statisztika["email_ertesitesek"] += 1
                    email_kuldes(
                        f"📄 Új számla – {cfg['nev']}",
                        uj_szamla_email_html(rekord),
                        [(pdf_nev or "szamla.pdf", pdf_bytes)] if pdf_bytes else None,
                        cimzett=tulajdonos_cimzett,
                    )
                continue

            # ---- ismeretlen: soha nem dobjuk el csendben ----
            statisztika["ismeretlen"] += 1
            iid = hashlib.md5(f"{uid_str}|ismeretlen".encode("utf-8")).hexdigest()[:16]
            if iid in ismeretlen_dokumentumok:
                continue
            reszlet = teljes_szoveg_egyesitve.strip()
            reszlet = re.sub(r"\s+", " ", reszlet)[:400]
            irekord = {
                "szolgaltato": szolgaltato,
                "szolgaltato_nev": cfg["nev"],
                "targy": targy,
                "erkezett": _email_datum_iso(erkezett_fejlec),
                "erkezett_fejlec": erkezett_fejlec,
                "reszlet": reszlet,
                "uid": uid_str,
            }
            ismeretlen_dokumentumok[iid] = irekord
            print(f"      ❓ Fel nem ismert levél ({szolgaltato}): {targy[:60]}")
            if ISMERETLEN_ERTESITES_EMAIL:
                statisztika["email_ertesitesek"] += 1
                email_kuldes(
                    f"❓ Fel nem ismert levél – {cfg['nev']}",
                    ismeretlen_email_html(irekord),
                )
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    # ---- 1a2. További postafiókok (ld. "TOVÁBBI POSTAFIÓKOK" szekció) -
    # SZÁNDÉKOSAN a fő postafiók feldolgozása UTÁN, de a Díjnet/Vízművek
    # portál-lekérdezés ELŐTT, hogy a "szamlak" dict már tartalmazza a fő
    # postafiók ebbeni futásban felismert számláit is (bár a kettő
    # egymástól ténylegesen független).
    tovabbi_postafiokok_feldolgozasa(allapot, statisztika, torolt_id_szet)

    # ---- 1a3. Dashboardról kért, EGYEDI (nem postafiók-szintű) Céges-
    # áthelyezések (ld. "→ Céges" gomb a Közüzemi táblázat sorain,
    # szamlak.html cegesAthelyezesKerelme()) - ld. kezi_ceges_athelyezesek_
    # feldolgozasa() kommentje a "TOVÁBBI POSTAFIÓKOK" szekció végén.
    kezi_ceges_athelyezesek_feldolgozasa(allapot)

    # ---- 1b. Díjnet - közvetlen portál-lekérdezés (nem email-alapú) ----
    if DIJNET_USER and DIJNET_JELSZO:
        try:
            dijnet_session = dijnet_bejelentkezes()
            if dijnet_session:
                dijnet_sorok = dijnet_szamlak_lekerdezese(dijnet_session)
                dijnet_pdf_letoltesek_szama = 0
                dijnet_pdf_potlas_szama = 0
                for sor in dijnet_sorok:
                    did = hashlib.md5(
                        f"dijnet|{sor['szolgaltato_nyers']}|{sor['szamlaszam']}".encode("utf-8")
                    ).hexdigest()[:16]
                    if did in torolt_id_szet:
                        continue  # a felhasználó véglegesen elrejtette ezt a számlát - ld. torolt_szamla_id_k
                    fizetve_e = _dijnet_fizetve_e(sor["allapot_szoveg"])
                    osszeg = _dijnet_osszeg_konvertalas(sor["osszeg_nyers"])
                    hatarido = _dijnet_datum_konvertalas(sor["hatarido_nyers"])
                    kiallitas = _dijnet_datum_konvertalas(sor["kiallitas_nyers"])

                    if did not in szamlak:
                        # Új számla - rögzítjük, és (best-effort PDF-fel) értesítünk,
                        # kivéve, ha már eleve fizetve érkezett (akkor nem kell
                        # "új számla" riasztás egy már rendezett tételről). A PDF-
                        # letöltést egy futáson belül korlátozzuk (ld. DIJNET_MAX_
                        # PDF_LETOLTES_FUTASONKENT), hogy egy bulk (sok új számlát
                        # egyszerre találó) futás ne fusson percekig - MINDEN
                        # számlához próbálunk PDF-et szerezni (nem csak a
                        # fizetetlenekhez), mert a felhasználó kérésére mostantól
                        # tartósan is eltároljuk (pdf_tarolas), nem csak az
                        # email-csatolmányhoz kell.
                        pdf_bytes = None
                        if dijnet_pdf_letoltesek_szama < DIJNET_MAX_PDF_LETOLTES_FUTASONKENT:
                            pdf_bytes = dijnet_pdf_letoltese(dijnet_session, sor["sor_index"])
                            dijnet_pdf_letoltesek_szama += 1
                        # FONTOS - a Díjnet táblázat "Szolgáltató" oszlopa (szoveg[0],
                        # itt: szolgaltato_nyers) tartalmazza a valódi szolgáltató-nevet
                        # (pl. "FCSM Zrt.", "MOHU Zrt.") - a "Számlakibocsátói azonosító"
                        # oszlop (szoveg[1], megjelenitett_nev) ezzel szemben egy
                        # belső azonosító/cím (pl. "Rákóczi 121", "HOLLANDI DÍJBESZEDŐ"),
                        # NEM a szolgáltató neve. Korábban ez fel volt cserélve - a
                        # dashboard szolgáltató-oszlopa/szűrője emiatt az azonosítót
                        # mutatta a valódi név helyett. Az azonosítót továbbra is
                        # megtartjuk, csak a tárgy-mezőben, zárójelben, ha van és eltér.
                        szolgaltato_valodi_nev = sor["szolgaltato_nyers"] or sor["megjelenitett_nev"]
                        azonosito_resz = (
                            f" ({sor['megjelenitett_nev']})"
                            if sor["megjelenitett_nev"] and sor["megjelenitett_nev"] != szolgaltato_valodi_nev
                            else ""
                        )
                        # kibocsato_azonosito: a "Számlakibocsátói azonosító" oszlop
                        # (megjelenitett_nev) KÜLÖN mezőben is eltárolva (nem csak a
                        # targy zárójeles részeként) - ez alapján sorolja be a
                        # felhasználó a dashboardon a bérlői körök egyikébe (ld.
                        # "BÉRLŐI KÖRÖK" szekció) - a kor mezőt minden futáskor
                        # frissen újraszámoljuk ez alapján.
                        kibocsato_azonosito = sor["megjelenitett_nev"] or ""
                        kor = _dijnet_kor_meghatarozasa(allapot, did, kibocsato_azonosito)
                        rekord = {
                            "szolgaltato": "dijnet",
                            "szolgaltato_nev": f"{szolgaltato_valodi_nev} (Díjnet)",
                            "targy": f"Számla – {sor['szamlaszam']}{azonosito_resz}",
                            "erkezett": kiallitas or magyar_ido().isoformat(),
                            "erkezett_fejlec": None,
                            "osszeg": osszeg,
                            "hatarido": hatarido,
                            "fizetve": fizetve_e,
                            "fizetve_datum": magyar_ido().isoformat() if fizetve_e else None,
                            "uid": None,
                            "forras": "dijnet_portal",
                            "szamlaszam": sor["szamlaszam"],
                            "kibocsato_azonosito": kibocsato_azonosito,
                            # dijnet_extra_oszlop: ld. a dijnet_szamlak_lekerdezese()
                            # "extra_oszlop_nyers" kommentjét, és a
                            # "szamla_kor_felulbiralas" mező kommentjét visszafejt()-
                            # ben (MOHU-probléma) - ez CSAK megjelenítésre kerül a
                            # dashboardon, automatikus döntést NEM alapozunk rá.
                            "dijnet_extra_oszlop": sor.get("extra_oszlop_nyers") or None,
                            "kor": kor,
                        }
                        szamlak[did] = rekord
                        pdf_tarolas(allapot, did, pdf_bytes)
                        statisztika["dijnet_uj_szamla"] += 1
                        print(f"      🆕 Új Díjnet-számla: {rekord['szolgaltato_nev']} – "
                              f"{forint(osszeg)} – határidő: {hatarido} – kör: {kor}")
                        if not fizetve_e:
                            _uj_szamla_ertesites_kuldese(rekord, pdf_bytes, statisztika, allapot, kor)
                    else:
                        # Már ismert számla - csendben frissítjük (elsősorban a
                        # fizetve-állapotot), nem küldünk újabb "új számla" emailt
                        # (kivéve, ha épp most sorolódott be egy korábban függőben
                        # lévő kibocsátó, és a felhasználó kérte az utólagos
                        # értesítést - ld. _kor_utolagos_ertesites_ha_kell()).
                        letezo = szamlak[did]
                        if fizetve_e and not letezo.get("fizetve"):
                            letezo["fizetve"] = True
                            letezo["fizetve_datum"] = magyar_ido().isoformat()
                            statisztika["dijnet_fizetve_frissites"] += 1
                            print(f"      ✅ Díjnet-számla fizetettre állítva: "
                                  f"{letezo['szolgaltato_nev']} – {letezo['targy']}")
                        if osszeg is not None:
                            letezo["osszeg"] = osszeg
                        if hatarido is not None:
                            letezo["hatarido"] = hatarido
                        # Utólagos szolgáltató-név javítás: a korábbi (hibás)
                        # kódverzió a "Számlakibocsátói azonosító" oszlopot
                        # (megjelenitett_nev) tette a szolgáltató-név helyére -
                        # a MÁR ELMENTETT, ezzel a régi hibás névvel rögzített
                        # számlákat itt, minden futáskor felülírjuk a helyes
                        # névvel, hogy ne kelljen kézzel javítani/törölni őket.
                        szolgaltato_valodi_nev = sor["szolgaltato_nyers"] or sor["megjelenitett_nev"]
                        azonosito_resz = (
                            f" ({sor['megjelenitett_nev']})"
                            if sor["megjelenitett_nev"] and sor["megjelenitett_nev"] != szolgaltato_valodi_nev
                            else ""
                        )
                        letezo["szolgaltato_nev"] = f"{szolgaltato_valodi_nev} (Díjnet)"
                        letezo["targy"] = f"Számla – {sor['szamlaszam']}{azonosito_resz}"
                        # kibocsato_azonosito utólagos pótlása/frissítése (régebbi
                        # rekordoknál még hiányozhat), és a "kor" mező MINDEN
                        # futáskor frissen újraszámolva - így ha a felhasználó
                        # időközben besorolt egy korábban ismeretlen kibocsátót, a
                        # nála MÁR meglévő számlák automatikusan átkerülnek a
                        # megfelelő körbe (nem kell egyesével kézzel javítani).
                        letezo["kibocsato_azonosito"] = sor["megjelenitett_nev"] or ""
                        # dijnet_extra_oszlop: minden futáskor frissítjük (nem
                        # csak új számlánál) - ld. a mező kommentjét fentebb,
                        # az új-számla ágban.
                        letezo["dijnet_extra_oszlop"] = sor.get("extra_oszlop_nyers") or None
                        uj_kor = _dijnet_kor_meghatarozasa(allapot, did, letezo["kibocsato_azonosito"])
                        if uj_kor != letezo.get("kor"):
                            print(f"      👥 Díjnet-számla kör-besorolása frissült: "
                                  f"{letezo['targy']} – {letezo.get('kor')} → {uj_kor}")
                        letezo["kor"] = uj_kor
                        _kor_utolagos_ertesites_ha_kell(did, letezo, allapot, statisztika, uj_kor)
                        # Utólagos PDF-pótlás: ha ennek a MÁR ISMERT számlának
                        # még nincs eltárolt PDF-je (pl. mert az első
                        # feldolgozáskor elérte a sapkát), most - a PÓTLÁSNAK
                        # szánt, KÜLÖN keret (DIJNET_PDF_POTLAS_MAX_
                        # FUTASONKENT, ld. a konstans fenti kommentjét - ez
                        # SZÁNDÉKOSAN nem osztja a dijnet_pdf_letoltesek_szama
                        # (új számlás) keretet, hogy az új számlák sose tudják
                        # örökre kiéheztetni a pótlást) - belül megpróbáljuk
                        # pótolni. Több futás alatt fokozatosan az összes
                        # (a 120 napos ablakban látott) számla PDF-je bekerül.
                        if did not in allapot.get("pdf_adatok", {}) and dijnet_pdf_potlas_szama < DIJNET_PDF_POTLAS_MAX_FUTASONKENT:
                            potolt_pdf = dijnet_pdf_letoltese(dijnet_session, sor["sor_index"])
                            dijnet_pdf_potlas_szama += 1
                            pdf_tarolas(allapot, did, potolt_pdf)
                # 1. pont: futás végi, SZERKEZETI (csak darabszám, nem
                # tartalom) log arról, mennyi Díjnet-számlának nincs (még)
                # tárolt PDF-je - ez teszi láthatóvá az Actions naplóban,
                # hogy a pótlás (fenti "Utólagos PDF-pótlás" ág) tartja-e a
                # lépést, vagy egyre nő a lemaradás.
                dijnet_pdf_hianyzik_db = sum(
                    1 for rid, r in szamlak.items()
                    if (r.get("szolgaltato") == "dijnet" or r.get("forras") == "dijnet_portal")
                    and rid not in allapot.get("pdf_adatok", {})
                )
                print(f"  📎 Díjnet: {dijnet_pdf_hianyzik_db} db számlának nincs (még) tárolt PDF-je.")
            else:
                print("  ℹ️  Díjnet: bejelentkezés nem sikerült - kihagyva ebben a futásban.")
        except Exception as e:
            print(f"  ⚠️  Díjnet-lekérdezés hiba (a többi feldolgozást ez nem érinti): {e}")
    else:
        print("  ℹ️  Díjnet: SZAMLA_DIJNET_USER / SZAMLA_DIJNET_JELSZO nincs beállítva - kihagyva.")

    # ---- 1c. Vízművek - közvetlen portál-lekérdezés (nem email-alapú) ----
    if VIZMUVEK_USER and VIZMUVEK_JELSZO:
        try:
            vizmuvek_session = vizmuvek_bejelentkezes()
            if vizmuvek_session:
                vizmuvek_sorok, vizmuvek_token = vizmuvek_szamlak_lekerdezese(vizmuvek_session)
                vizmuvek_pdf_letoltesek_szama = 0
                vizmuvek_pdf_potlas_szama = 0
                for sor in vizmuvek_sorok:
                    szamlaszam = str(sor.get("INVID") or "").strip()
                    if not szamlaszam:
                        print("  ⚠️  Vízművek: nincs INVID (számla-azonosító) egy sorban, kihagyva "
                              "(nem tudnánk stabil azonosítót képezni belőle).")
                        continue
                    vid = hashlib.md5(
                        f"vizmuvek|{szamlaszam}".encode("utf-8")
                    ).hexdigest()[:16]
                    if vid in torolt_id_szet:
                        continue  # a felhasználó véglegesen elrejtette ezt a számlát - ld. torolt_szamla_id_k
                    fizetve_e = _vizmuvek_fizetve_e(sor.get("STATUS_MEGNEV"))
                    # Az AMOUNT mező a valós portál-válaszban MÁR szám (nem
                    # szöveg), ezért itt nem kell a Díjnetnél használt
                    # szöveg->szám konverzió - a dátummezők ("INV_DATE"/
                    # "FAEDN") formátuma viszont megegyezik a Díjnet-
                    # portáléval, ezért az ottani (általános célú) dátum-
                    # konvertert újrahasznosítjuk.
                    osszeg = sor.get("AMOUNT")
                    hatarido = _dijnet_datum_konvertalas(sor.get("FAEDN"))
                    kiallitas = _dijnet_datum_konvertalas(sor.get("INV_DATE"))
                    targy_nev = sor.get("MEGNEV") or "Számla"

                    # A Vízművek EGY EGÉSZBEN tartozik az egyik bérlői körhöz (a
                    # felhasználó kifejezett döntése szerint NINCS számlánkénti
                    # szétválasztás, még akkor sem, ha több mérő/felhasználási
                    # hely is szerepel a fiókban) - ld. "BÉRLŐI KÖRÖK" szekció.
                    kor = _vizmuvek_kor_meghatarozasa(allapot, vid)

                    if vid not in szamlak:
                        rekord = {
                            "szolgaltato": "vizmuvek",
                            "szolgaltato_nev": SZOLGALTATOK["vizmuvek"]["nev"],
                            "targy": f"{targy_nev} – {szamlaszam}",
                            "erkezett": kiallitas or magyar_ido().isoformat(),
                            "erkezett_fejlec": None,
                            "osszeg": osszeg,
                            "hatarido": hatarido,
                            "fizetve": fizetve_e,
                            "fizetve_datum": magyar_ido().isoformat() if fizetve_e else None,
                            "uid": None,
                            "forras": "vizmuvek_portal",
                            "szamlaszam": szamlaszam,
                            "kor": kor,
                        }
                        szamlak[vid] = rekord
                        statisztika["vizmuvek_uj_szamla"] += 1
                        print(f"      🆕 Új Vízművek-számla: {rekord['targy']} – "
                              f"{forint(osszeg)} – határidő: {hatarido} – kör: {kor}")
                        # PDF-letöltés MINDEN új számlához megpróbálva (nem
                        # csak a fizetetlenekhez), egy futáson belül
                        # korlátozva - ld. VIZMUVEK_MAX_PDF_LETOLTES_
                        # FUTASONKENT és a Díjnet-résznél lévő azonos
                        # indoklást.
                        pdf_bytes = None
                        if vizmuvek_pdf_letoltesek_szama < VIZMUVEK_MAX_PDF_LETOLTES_FUTASONKENT:
                            pdf_bytes = vizmuvek_pdf_letoltese(vizmuvek_session, vizmuvek_token, sor)
                            vizmuvek_pdf_letoltesek_szama += 1
                            pdf_tarolas(allapot, vid, pdf_bytes)
                        if not fizetve_e:
                            _uj_szamla_ertesites_kuldese(rekord, pdf_bytes, statisztika, allapot, kor)
                    else:
                        # Már ismert számla - csendben frissítjük
                        # (elsősorban a fizetve-állapotot), nem küldünk
                        # újabb "új számla" emailt (kivéve utólagos
                        # értesítést, ld. _kor_utolagos_ertesites_ha_kell()).
                        letezo = szamlak[vid]
                        if fizetve_e and not letezo.get("fizetve"):
                            letezo["fizetve"] = True
                            letezo["fizetve_datum"] = magyar_ido().isoformat()
                            statisztika["vizmuvek_fizetve_frissites"] += 1
                            print(f"      ✅ Vízművek-számla fizetettre állítva: {letezo['targy']}")
                        if osszeg is not None:
                            letezo["osszeg"] = osszeg
                        if hatarido is not None:
                            letezo["hatarido"] = hatarido
                        if kor != letezo.get("kor"):
                            print(f"      👥 Vízművek-számla kör-besorolása frissült: "
                                  f"{letezo['targy']} – {letezo.get('kor')} → {kor}")
                        letezo["kor"] = kor
                        _kor_utolagos_ertesites_ha_kell(vid, letezo, allapot, statisztika, kor)
                        # Utólagos PDF-pótlás: ha ennek a MÁR ISMERT számlának
                        # még nincs eltárolt PDF-je, most - a még rendelkezésre
                        # álló kereten belül - megpróbáljuk pótolni (ld. a
                        # Díjnet-résznél lévő azonos indoklást).
                        if (vid not in allapot.get("pdf_adatok", {})
                                and vizmuvek_pdf_potlas_szama < VIZMUVEK_PDF_POTLAS_MAX_FUTASONKENT):
                            potolt_pdf = vizmuvek_pdf_letoltese(vizmuvek_session, vizmuvek_token, sor)
                            vizmuvek_pdf_potlas_szama += 1
                            pdf_tarolas(allapot, vid, potolt_pdf)
                # 1. pont: ld. a Díjnet-résznél lévő azonos indoklást - csak
                # szerkezeti (darabszám) log, nem tartalom.
                vizmuvek_pdf_hianyzik_db = sum(
                    1 for rid, r in szamlak.items()
                    if r.get("forras") == "vizmuvek_portal"
                    and rid not in allapot.get("pdf_adatok", {})
                )
                print(f"  📎 Vízművek: {vizmuvek_pdf_hianyzik_db} db számlának nincs (még) tárolt PDF-je.")
            else:
                print("  ℹ️  Vízművek: bejelentkezés nem sikerült - kihagyva ebben a futásban.")
        except Exception as e:
            print(f"  ⚠️  Vízművek-lekérdezés hiba (a többi feldolgozást ez nem érinti): {e}")
    else:
        print("  ℹ️  Vízművek: SZAMLA_VIZMUVEK_USER / SZAMLA_VIZMUVEK_JELSZO nincs beállítva - kihagyva.")

    # ---- 2. Határidő-előtti összesítő (naponta legfeljebb egyszer) ----
    ma_str = magyar_ma().isoformat()
    kuszob = (magyar_ma() + timedelta(days=emlekezteto_napok)).isoformat()

    # (rid, rekord) párokban dolgozunk (nem csak a rekordokkal) - a PDF-
    # gyűjtéshez a rid (az állapotban lévő "pdf_adatok" kulcsa) kell, és
    # így nem kell a rekord-objektumok Python-beli azonosságára (id())
    # támaszkodni egy utólagos visszakereséshez.
    fizetetlen_rid_rekord = [(rid, r) for rid, r in szamlak.items() if not r["fizetve"]]
    fizetetlen = [r for _, r in fizetetlen_rid_rekord]
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

        csatolmanyok = csatolmanyok_osszegyujtese(allapot, fizetetlen_rid_rekord)

        email_kuldes(
            f"💰 Fizetetlen számlák – {len(fizetetlen)} db – {forint(vegosszeg)}",
            osszesito_email_html(
                fizetetlen, vegosszeg, provider_osszegek,
                bevezeto=(
                    "<p>Az alábbi számlák még nincsenek kifizetve, és valamelyik határideje "
                    f"{emlekezteto_napok} napon belül lejár (vagy már lejárt):</p>"
                ),
            ),
            csatolmanyok,
        )
        allapot["utolso_emlekezteto_nap"] = ma_str

    # ---- 2a. Könyvelő - havi, hónap-végi emlékeztető (ld. "3 CÍMZETTI
    # KÖR" szekció) ----
    # SZÁNDÉKOSAN egyszerű: a hónap UTOLSÓ néhány (KONYVELO_EMLEKEZTETO_
    # UTOLSO_N_NAP) napjában, naponta ELLENŐRIZZÜK, hogy ebben a hónapban
    # már kiment-e (ld. "utolso_konyvelo_emlekezteto_honap" - ugyanaz a
    # minta, mint a "utolso_fix_osszesito_datum" fenti mezőnél) - ez véd
    # ki attól, hogy a workflow mostantól 10 percenkénti ütemezése (ld.
    # .github/workflows/szamla_monitor.yml) a hónap utolsó napjaiban
    # tucatszor újraküldje ugyanazt az emlékeztetőt.
    ma_datum_konyvelo = magyar_ma()
    honap_kulcs = ma_datum_konyvelo.strftime("%Y-%m")
    utolso_nap = _honap_utolso_napja(ma_datum_konyvelo)
    if (
        ma_datum_konyvelo.day > utolso_nap - KONYVELO_EMLEKEZTETO_UTOLSO_N_NAP
        and allapot.get("utolso_konyvelo_emlekezteto_honap") != honap_kulcs
    ):
        konyvelo_cimzett = _cimzett_string(allapot.get("konyvelo_emailek"))
        if konyvelo_cimzett:
            statisztika["email_ertesitesek"] += 1
            email_kuldes(
                "📁 Hónap vége - Drive-ellenőrzés",
                konyvelo_emlekezteto_email_html(),
                cimzett=konyvelo_cimzett,
            )
            print("  📁 Könyvelői havi emlékeztető elküldve.")
        else:
            print("  ℹ️  Könyvelői havi emlékeztető esedékes lenne, de nincs beállítva "
                  "könyvelő email-cím (dashboard 'Könyvelő' kezelése) - kihagyva.")
        # A hónap-jelzőt AKKOR IS beírjuk, ha nincs beállítva cím (ld. a
        # "utolso_fix_osszesito_datum" fenti mintáját - ez véd ki attól,
        # hogy a fenti "ℹ️" sor a hónap hátralévő részében minden 10
        # perces futásnál újra kiíródjon a naplóba).
        allapot["utolso_konyvelo_emlekezteto_honap"] = honap_kulcs

    # ---- 2b. Fix-napi, tételesen KIVÁLASZTOTT összesítő (opcionális) ----
    # Ez FÜGGETLEN a fenti, határidő-küszöb-alapú automatikus emlékeztetőtől -
    # a felhasználó a dashboardon állíthatja be (ld. BEALLITASOK_FAJL), hogy
    # a hónap melyik napján menjen, és melyik számlákról (ha nem választ ki
    # semmit, az ÖSSZES fizetetlen számláról, mint a fenti ág).
    #
    # BÉRLŐI KÖRÖK: a felhasználó kifejezett kérésére a besorolt (kor_a/
    # kor_b) számlák CSAK a saját körük havi összesítőjébe kerülnek, a
    # "fő" (itt lentebb, "általános" néven szereplő) összesítő ezért ilyenkor
    # már csak a be nem sorolt/egyéb számlákat (pl. MVM, vagy még "fuggoben"
    # állapotú Díjnet/Vízművek-tételek) fogja össze - EZ CSAK AKKOR igaz, ha
    # a felhasználó nem választott ki kézzel konkrét számlákat
    # (kivalasztott_szamlak) - egy KIFEJEZETT kézi kiválasztás felülír
    # mindent, változatlanul (ahogy eddig is). MINDEN bérlői-kör-összesítőről
    # a TULAJDONOS is automatikusan másolatot kap (ld. _tulajdonos_
    # osszesito_masolat(), "3 CÍMZETTI KÖR" szekció).
    if beallitasok["osszesito_honap_nap"] is not None:
        ma_datum = magyar_ma()
        if (
            ma_datum.day == beallitasok["osszesito_honap_nap"]
            and allapot.get("utolso_fix_osszesito_datum") != ma_str
        ):
            kivalasztott_id_k = beallitasok["kivalasztott_szamlak"]

            if kivalasztott_id_k is not None:
                # Kifejezett kézi kiválasztás - változatlanul, körök nélkül.
                erintett = [(rid, szamlak[rid]) for rid in kivalasztott_id_k if rid in szamlak]
                if erintett:
                    _osszesito_kuldese(
                        allapot, erintett,
                        f" ({beallitasok['osszesito_honap_nap']}.)",
                        "<p>Ez egy általad beállított, fix napi összesítő - a Te kifejezett "
                        "kiválasztásod alapján:</p>",
                        None, statisztika,
                    )
                else:
                    print("      ℹ️  Fix-napi összesítő esedékes lenne, de a kiválasztott számlák "
                          "közül egyik sem található az állapotban - kihagyva.")
            else:
                # Nincs kézi kiválasztás - a besorolt (kor_a/kor_b) számlák a
                # saját körük összesítőjébe kerülnek, minden más (be nem
                # sorolt/egyéb) az "általános" összesítőbe.
                altalanos = [
                    (rid, r) for rid, r in szamlak.items()
                    if not r["fizetve"] and r.get("kor") not in ("kor_a", "kor_b")
                ]
                if altalanos:
                    _osszesito_kuldese(
                        allapot, altalanos,
                        f" ({beallitasok['osszesito_honap_nap']}.)",
                        "<p>Ez egy általad beállított, fix napi összesítő - az ÖSSZES jelenleg "
                        "fizetetlen, bérlői körbe NEM sorolt számláról (nem volt egyedi kiválasztás):</p>",
                        None, statisztika,
                    )
                for kor_kulcs in ("kor_a", "kor_b"):
                    cimzett = _cimzett_string(_kor_cimzettek(allapot, kor_kulcs))
                    kor_erintett = _fizetetlen_szamlak_korhoz(szamlak, kor_kulcs)
                    if kor_erintett and not cimzett:
                        print(f"      ⚠️  A(z) '{kor_kulcs}' körnek lenne mit összesíteni "
                              f"({len(kor_erintett)} számla), de nincs beállítva email-cím "
                              "(dashboard 'Bérlői körök' email-kezelése / régi SZAMLA_"
                              f"{kor_kulcs.upper()}_EMAIL secret) - kihagyva.")
                        continue
                    if not kor_erintett:
                        continue
                    kor_nev = (allapot.get("kor_nevek") or {}).get(kor_kulcs) or (
                        "1. kör" if kor_kulcs == "kor_a" else "2. kör"
                    )
                    cim_resz = f" – {kor_nev} ({beallitasok['osszesito_honap_nap']}.)"
                    _osszesito_kuldese(
                        allapot, kor_erintett, cim_resz,
                        f"<p>Ez a(z) <strong>{_esc(kor_nev)}</strong> havi, fix napi összesítője - "
                        "az ehhez a körhöz tartozó, jelenleg fizetetlen számlákról:</p>",
                        cimzett, statisztika,
                    )
                    _tulajdonos_osszesito_masolat(allapot, kor_erintett, cim_resz, statisztika, True)
            allapot["utolso_fix_osszesito_datum"] = ma_str

    # ---- 2c. Dátum-intervallumos, eseti küldés egy megadott email-címre ----
    # Ezt a dashboard "Számlák küldése emailben" panelje indítja el egy
    # workflow_dispatch hívással (SZAMLA_DATUMTOL/SZAMLA_DATUMIG/
    # SZAMLA_CEL_EMAIL inputok) - ütemezett (napi 3x-os) futásnál mindhárom
    # üres, ilyenkor ez a szakasz simán kimarad. A szűrés a fizetési
    # határidő (hatarido) alapján történik, mert ez a felhasználó számára
    # releváns "mikor esedékes" adat - nem az érkezés/kiállítás dátuma.
    if SZAMLA_DATUMTOL and SZAMLA_DATUMIG and SZAMLA_CEL_EMAIL:
        print(f"  📤 Dátum-intervallumos küldés kérve: {SZAMLA_DATUMTOL} .. "
              f"{SZAMLA_DATUMIG} -> {SZAMLA_CEL_EMAIL}")
        try:
            # Egyszerű, biztonságos validáció - ha a formátum nem
            # ISO-dátum (YYYY-MM-DD), inkább kihagyjuk a küldést, minthogy
            # egy elgépelt inputtal rossz szűrést csináljunk.
            date.fromisoformat(SZAMLA_DATUMTOL)
            date.fromisoformat(SZAMLA_DATUMIG)
            if SZAMLA_DATUMTOL > SZAMLA_DATUMIG:
                print("  ⚠️  Dátum-intervallum érvénytelen (a kezdő dátum a záró dátum után van) - kihagyva.")
            else:
                intervallumba_eso = [
                    (rid, r) for rid, r in szamlak.items()
                    if r.get("hatarido") and SZAMLA_DATUMTOL <= r["hatarido"] <= SZAMLA_DATUMIG
                ]
                if not intervallumba_eso:
                    print("  ℹ️  Dátum-intervallumos küldés: egyik számla határideje sem esik a "
                          "megadott intervallumba - nem megy ki email.")
                else:
                    rekordok = [r for _, r in intervallumba_eso]
                    osszeg_intervallum = sum(r["osszeg"] or 0 for r in rekordok)
                    provider_osszegek_intervallum = {}
                    for r in rekordok:
                        provider_osszegek_intervallum[r["szolgaltato_nev"]] = (
                            provider_osszegek_intervallum.get(r["szolgaltato_nev"], 0) + (r["osszeg"] or 0)
                        )
                    csatolmanyok_intervallum = csatolmanyok_osszegyujtese(allapot, intervallumba_eso)
                    email_kuldes(
                        f"📤 Számlák ({SZAMLA_DATUMTOL} – {SZAMLA_DATUMIG}) – "
                        f"{len(rekordok)} db – {forint(osszeg_intervallum)}",
                        osszesito_email_html(
                            rekordok, osszeg_intervallum, provider_osszegek_intervallum,
                            cim=f"📤 Számlák – {SZAMLA_DATUMTOL} és {SZAMLA_DATUMIG} között esedékes",
                            bevezeto=(
                                "<p>Ezt az összesítőt a dashboardon keresztül kifejezetten kérted, "
                                f"a(z) {SZAMLA_DATUMTOL} és {SZAMLA_DATUMIG} közötti (fizetési "
                                "határidejű) számlákról:</p>"
                            ),
                        ),
                        csatolmanyok_intervallum,
                        cimzett=SZAMLA_CEL_EMAIL,
                    )
                    print(f"      📤 Dátum-intervallumos email elküldve ({len(rekordok)} számla) "
                          f"-> {SZAMLA_CEL_EMAIL}.")
        except ValueError:
            print(f"  ⚠️  Dátum-intervallumos küldés: érvénytelen dátumformátum "
                  f"(datumtol={SZAMLA_DATUMTOL!r}, datumig={SZAMLA_DATUMIG!r}) - kihagyva.")

    # ---- 2d. Manuális, azonnali küldések (dashboard "Küldés most" gombjai)
    # ---- ld. 6/7. pont, "3 CÍMZETTI KÖR" szekció.
    # Mindegyik env-változó csak workflow_dispatch-nál kaphat tartalmat (ld.
    # .github/workflows/szamla_monitor.yml) - ütemezett futásnál üres/false,
    # ilyenkor ez a teljes szakasz kimarad. A PDF-csatolás (SZAMLA_PDF_
    # CSATOLAS_MANUALIS) ezekre a MANUÁLIS küldésekre vonatkozik - a fenti,
    # meglévő (ütemezett) küldések PDF-csatolási viselkedése ettől
    # függetlenül, változatlanul megmarad.
    if SZAMLA_BERLO_OSSZESITO_KOR:
        korok_kuldendo = (
            ["kor_a", "kor_b"] if SZAMLA_BERLO_OSSZESITO_KOR == "mind" else [SZAMLA_BERLO_OSSZESITO_KOR]
        )
        for kor_kulcs in korok_kuldendo:
            if kor_kulcs not in ("kor_a", "kor_b"):
                print(f"  ⚠️  Ismeretlen kör-azonosító a manuális küldéshez: {kor_kulcs!r} - kihagyva.")
                continue
            _berlo_kor_osszesito_kuldese_most(allapot, szamlak, kor_kulcs, statisztika, SZAMLA_PDF_CSATOLAS_MANUALIS)

    if SZAMLA_TULAJDONOS_OSSZESITO_MOST:
        _tulajdonos_osszesito_kuldese_most(allapot, szamlak, statisztika, SZAMLA_PDF_CSATOLAS_MANUALIS)

    if SZAMLA_KONYVELO_EMLEKEZTETO_MOST:
        konyvelo_cimzett_most = _cimzett_string(allapot.get("konyvelo_emailek"))
        if konyvelo_cimzett_most:
            statisztika["email_ertesitesek"] += 1
            email_kuldes(
                "📁 Hónap vége - Drive-ellenőrzés",
                konyvelo_emlekezteto_email_html(),
                cimzett=konyvelo_cimzett_most,
            )
            print("  📁 Könyvelői emlékeztető manuálisan elküldve (dashboard gomb).")
        else:
            print("  ⚠️  Könyvelői emlékeztető lett kérve a dashboardról, de nincs beállítva "
                  "könyvelő email-cím.")

    # ---- 2e. Google Drive - PDF-feltöltés (ld. "GOOGLE DRIVE - PDF-
    # FELTÖLTÉS" szekció) - SZÁNDÉKOSAN az összes IMAP/Díjnet/Vízművek
    # ingestion ÉS a három-tiers email-küldés UTÁN, de a titkosított
    # állapot mentése ELŐTT fut, hogy az ebben a futásban felismert ÖSSZES
    # (friss) PDF-et is elkapja, és a "drive_feltoltott_id_k" frissítése
    # bekerüljön a lentebbi mentésbe.
    drive_pdf_feltoltesek(allapot)

    # ---- 2f. Céges számlák - dedikált postafiók feldolgozása (ld. "CÉGES
    # SZÁMLÁK" szekció) - SZÁNDÉKOSAN a fenti Drive-feltöltés UTÁN (bár a
    # kettő egymástól teljesen független), a titkosított állapot mentése
    # ELŐTT, hogy az ebben a futásban feldolgozott/törölt céges számlák
    # metaadata is bekerüljön a lentebbi mentésbe.
    ceges_szamlak_feldolgozasa(allapot)

    # ---- 2g. NAV Online Számla - bejövő számlák lekérdezése/párosítás
    # (ld. "NAV ONLINE SZÁMLA" szekció) - SZÁNDÉKOSAN a Céges számlák ÉS a
    # további postafiókok feldolgozása UTÁN (hogy a legfrissebb
    # email-számlákat is lássa a párosítás mindkét forrásban), a
    # titkosított állapot mentése ELŐTT. MINDKÉT listát (szamlak +
    # ceges_szamlak) egyszerre párosítja, ld. nav_szamla_parositas().
    nav_szamla_parositas(allapot)

    # ---- 2h. NAV-on talált, de emailben meg nem érkezett számlák
    # szállítóihoz sablon-emlékeztető küldése (ld. "NAV-ON TALÁLT,
    # HIÁNYZÓ SZÁMLÁK EMLÉKEZTETŐJE" szekció) - csak akkor csinál
    # bármit, ha a dashboardról egy "Emlékeztető küldése" gombnyomás
    # workflow_dispatch inputként adószám(oka)t adott át.
    nav_hianyzo_szamla_emlekezteto_kuldese(allapot)

    # ---- 3. Állapot mentése (titkosítva) ----
    # FONTOS: a feldolgozott_uidok egy set volt, aminek a sorrendje NEM
    # garantált/stabil - egyszerű list(set)-tel a [-2000:] vágás
    # gyakorlatilag TETSZŐLEGES UID-kat dobhatott volna el (nem
    # feltétlenül a legrégebbieket). Az IMAP UID-ok futáson belül
    # monoton növekvő számok, ezért numerikusan rendezve a vágás
    # ténylegesen a legrégebbi UID-kat hagyja el, a legfrissebb 2000-et
    # tartja meg - ez az, amit a "ne nőjön a végtelenségig" komment
    # eredetileg is feltételezett.
    try:
        rendezett_uidok = sorted(feldolgozott_uidok, key=lambda x: int(x))
    except ValueError:
        # Ha valamiért nem-numerikus UID keveredne bele (nem várt, de
        # védekezésképp), essünk vissza a sima (nem numerikus) rendezésre,
        # semmint hibával leálljunk.
        rendezett_uidok = sorted(feldolgozott_uidok)
    allapot["feldolgozott_uidok"] = rendezett_uidok[-2000:]
    # A mérőállás- és ismeretlen-naplók se nőjenek a végtelenségig -
    # a legutóbbi néhány száz bejegyzést tartjuk meg (érkezés szerint).
    if len(meroallasok) > 500:
        rendezett = sorted(meroallasok.items(), key=lambda kv: kv[1]["erkezett"])
        allapot["meroallasok"] = dict(rendezett[-500:])
    if len(ismeretlen_dokumentumok) > 300:
        rendezett = sorted(ismeretlen_dokumentumok.items(), key=lambda kv: kv[1]["erkezett"])
        allapot["ismeretlen_dokumentumok"] = dict(rendezett[-300:])
    _pdf_tarolas_ritkitasa(allapot)

    if DRY_RUN:
        print("  🧪 [DRY RUN] Állapot MENTÉSE kihagyva - a felismerés/lekérdezés lefutott, "
              "de semmi nem került titkosítva elmentésre, és git-push sem fog történni "
              "(a workflow a mostani, változatlan fájlt fogja commitolni, ami valójában "
              "'nincs változás' lesz).")
    else:
        titkosit_es_ment(allapot, TITKOSITAS_JELSZO, ALLAPOT_FAJL)
        print("💾 Állapot mentve (titkosítva).")

    # ---- 4. Futási összesítő ----
    print("📊 Futási összesítő:")
    print(f"   • Feldolgozott email: {statisztika['email_osszesen']}")
    print(f"   • Új számla (email): {statisztika['uj_szamla']}  |  Új Díjnet-számla: {statisztika['dijnet_uj_szamla']}  |  "
          f"Új Vízművek-számla (portál): {statisztika['vizmuvek_uj_szamla']}")
    print(f"   • Fizetve-visszaigazolás: {statisztika['fizetve']}  "
          f"(ebből nem azonosítható: {statisztika['fizetes_nem_azonositott']})  |  "
          f"Díjnet fizetve-frissítés: {statisztika['dijnet_fizetve_frissites']}  |  "
          f"Vízművek fizetve-frissítés: {statisztika['vizmuvek_fizetve_frissites']}")
    print(f"   • Fizetési emlékeztető (kihagyva): {statisztika['fizetesi_emlekezteto']}")
    print(f"   • Mérőállás-esemény: {statisztika['meroallas']}  |  Fel nem ismert levél: {statisztika['ismeretlen']}")
    print(f"   • Kiküldött (vagy dry-run miatt csak naplózott) email-értesítés: {statisztika['email_ertesitesek']}")
    print(f"   • Összes nyilvántartott számla: {len(szamlak)}  (ebből fizetetlen: "
          f"{sum(1 for r in szamlak.values() if not r['fizetve'])})")
    if DRY_RUN:
        print("   • ⚠️  Ez egy DRY RUN futás volt - a fentiek közül SEMMI nem lett ténylegesen elküldve/elmentve.")
    print("✅ Kész.\n")


if __name__ == "__main__":
    main()
