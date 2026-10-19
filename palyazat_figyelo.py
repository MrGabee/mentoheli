"""
Pályázat-figyelő

Naponta végignézi a magyar pályázati oldalakat (hírlevél-aggregátorok, NEA,
NKA, Médiatanács, Filmintézet, Tempus, Budapest, Csepel), és az új,
ránk illő felhívásokat egy összefoglaló e-mailben küldi el.

Profilok (kulcsszavak alapján):
  - Oktatás / informatika / TV-média  (mellékállású EV)
  - Repülés / munkavédelem / mérnöki  (mellékállású EV)
  - Nonprofit / civil                 (családi nonprofit kft.)
  - Vállalkozás (EV, mikro, KKV általános felhívások)
  - Helyi (Budapest, XXI. kerület)

Az első futás a teljes mostani listát küldi ("kezdeti lista"), utána csak az
újakat. Az állapot a palyazat_allapot.json-ben van.

PROBA=1 esetén nem küld levelet és nem ír állapotot, csak kiírja a találatokat.
"""

import hashlib
import json
import os
import re
import smtplib
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.mime.text import MIMEText
from html import escape, unescape
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlparse

ALLAPOT_FAJL = "palyazat_allapot.json"
PROBA = os.environ.get("PROBA", "0") == "1"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# tipus: "rss" vagy "html". profil: ha meg van adva, a forrás minden
# pályázat-szerű linkje ehhez a profilhoz tartozik (szakmai forrás).
FORRASOK = [
    # --- Összesítő / hírlevél oldalak ---
    {"nev": "PályázatMenedzser", "url": "https://palyazatmenedzser.hu/feed/", "tipus": "rss"},
    {"nev": "Palyazatok.org", "url": "https://palyazatok.org/feed/", "tipus": "rss"},
    {"nev": "Pályázat Asszisztens", "url": "https://palyazatasszisztens.hu/palyazatok", "tipus": "html"},
    {"nev": "PAFI", "url": "https://pafi.hu/palyazatok", "tipus": "html"},
    {"nev": "Nonprofit.hu", "url": "https://www.nonprofit.hu/palyazatok", "tipus": "html"},
    {"nev": "Napitender", "url": "https://napitender.hu/feed/", "tipus": "rss"},
    {"nev": "Vállalkozz Ma", "url": "https://www.vallalkozzma.hu/palyazatok/", "tipus": "html"},
    {"nev": "EU Pályázati Portál", "url": "https://www.eupalyazatiportal.hu/feed/", "tipus": "rss"},
    {"nev": "Pályázatfigyelő (palyazat.hu)", "url": "https://www.palyazat.hu/", "tipus": "html"},
    {"nev": "Civil Információs Portál", "url": "https://civil.info.hu/palyazatok", "tipus": "html", "profil": "nonprofit"},
    # --- Állami / uniós ---
    {"nev": "Pályázat.gov.hu", "url": "https://palyazat.gov.hu/", "tipus": "html"},
    {"nev": "Széchenyi Terv Plusz felhívások", "url": "https://www.palyazat.gov.hu/doc/felhivasok", "tipus": "html"},
    {"nev": "NFSZ (vállalkozóvá válás, bértámogatás)", "url": "https://nfsz.munka.hu/", "tipus": "html", "profil": "vallalkozas"},
    {"nev": "NKFIH", "url": "https://nkfih.gov.hu/palyazoknak", "tipus": "html", "profil": "muszaki"},
    {"nev": "Vállalkozz Digitálisan", "url": "https://vallalkozzdigitalisan.hu/", "tipus": "html", "profil": "vallalkozas"},
    {"nev": "MFB pontok", "url": "https://www.mfbpont.hu/", "tipus": "html", "profil": "vallalkozas"},
    # --- Bethlen Gábor Alapkezelő (NEA, Csoóri, tehetség, stb.) ---
    {"nev": "NEA (Bethlen Gábor Alapkezelő)", "url": "https://bgazrt.hu/tamogatasok/nemzeti-egyuttmukodesi-alap/", "tipus": "html", "profil": "nonprofit"},
    {"nev": "Bethlen Gábor Alapkezelő", "url": "https://bgazrt.hu/", "tipus": "html"},
    # --- Kultúra, média, oktatás ---
    {"nev": "Nemzeti Kulturális Alap", "url": "https://nka.hu/kiemelt-kategoriak/palyaztatas/kollegiumok-felhivasai/felhivasok/", "tipus": "html"},
    {"nev": "Médiatanács (NMHH)", "url": "https://nmhh.hu/media/palyazatok", "tipus": "html", "profil": "media"},
    {"nev": "Magyar Média Mecenatúra", "url": "https://mecenatura.mediatanacs.hu/", "tipus": "html", "profil": "media"},
    {"nev": "Nemzeti Filmintézet", "url": "https://nfi.hu/", "tipus": "html", "profil": "media"},
    {"nev": "Kreatív Európa Iroda", "url": "https://kreativeuropa.hu/", "tipus": "html", "profil": "media"},
    {"nev": "Petőfi Kulturális Ügynökség", "url": "https://pka.hu/palyazatok", "tipus": "html", "profil": "media"},
    {"nev": "Magyar Művészeti Akadémia", "url": "https://www.mma.hu/palyazatok", "tipus": "html", "profil": "media"},
    {"nev": "Tempus Közalapítvány (Erasmus+)", "url": "https://tka.hu/palyazatok", "tipus": "html", "profil": "media"},
    {"nev": "Oktatási Hivatal", "url": "https://www.oktatas.hu/", "tipus": "html", "profil": "media"},
    # --- Alapítványok, cégek ---
    {"nev": "MOL Alapítvány", "url": "https://molalapitvany.hu/", "tipus": "html"},
    {"nev": "Vodafone Alapítvány", "url": "https://www.vodafone.hu/alapitvany", "tipus": "html"},
    {"nev": "Ökotárs Alapítvány", "url": "https://okotars.hu/hu/palyazatok", "tipus": "html", "profil": "nonprofit"},
    # --- Google Hírek keresések: bármelyik oldalon megjelent felhívást elkapják ---
    *[{"nev": f"Google Hírek: {k}", "tipus": "rss",
       "url": "https://news.google.com/rss/search?hl=hu&gl=HU&ceid=HU:hu&q=" + quote(k + " when:14d")}
      for k in ["pályázati felhívás", "pályázat egyéni vállalkozó", "vissza nem térítendő támogatás",
                "pályázat önrész nélkül", "pályázat nonprofit", "pályázat civil szervezet",
                "pályázat pedagógus", "pályázat informatika oktatás", "pályázat televízió műsor",
                "pályázat média tartalomgyártás", "pályázat munkavédelem", "pályázat repülés",
                "pályázat felnőttképzés", "pályázat Budapest", "pályázat Csepel"]],
    # --- Helyi ---
    {"nev": "Budapest.hu", "url": "https://budapest.hu/", "tipus": "html", "profil": "helyi"},
    {"nev": "Csepel.hu", "url": "https://csepel.hu/", "tipus": "html", "profil": "helyi"},
]

PROFILOK = {
    "media": {
        "cim": "🎓 Oktatás / informatika / TV-média",
        "szavak": ["informatik", "digitalis", "oktat", "pedagogus", "tanar", "kepzes", "felnottkepz",
                   "vizsg", "televizi", "tv", "media", "musor", "film", "audiovizual", "ujsagir",
                   "sajto", "hirportal", "tartalomgyart", "erasmus", "kultur"],
    },
    "muszaki": {
        "cim": "✈️ Repülés / munkavédelem / mérnöki",
        "szavak": ["repul", "legi", "legikozleked", "dron", "munkavedelem", "munkabiztonsag",
                   "mernok", "muszaki", "innovaci", "k+f", "kutatas-fejleszt", "kfi"],
    },
    "nonprofit": {
        "cim": "🤝 Nonprofit / civil",
        "szavak": ["nonprofit", "civil", "kozhasznu", "nea", "egyesulet", "alapitvany",
                   "tarsadalmi szervezet", "kozossegi", "onkentes", "bethlen gabor alap"],
    },
    "vallalkozas": {
        "cim": "💼 Vállalkozás (EV, mikro, KKV)",
        "szavak": ["egyeni vallalkoz", "ev", "mikrovallalkoz", "kkv", "kis- es kozepvallalkoz",
                   "vallalkozasfejleszt", "vallalkozoi", "eszkozbeszerz", "digitalizaci",
                   "kamatmentes", "visszateritendo"],
    },
    "helyi": {
        "cim": "📍 Budapest / XXI. kerület",
        "szavak": ["budapest", "fovaros", "csepel", "xxi. kerulet", "xxi. ker"],
    },
}

# Ezek nélkül a link nem pályázat (menüpontok, cikkek kiszűrésére)
PALYAZAT_SZAVAK = ["palyaz", "felhivas", "kiiras", "tamogatas", "osztondij", "alap ", "program", "hitel"]
# Ezekkel biztosan nem új lehetőség
KIZARO_SZAVAK = ["eredmeny", "nyertes", "dontes", "lezarult", "kiertekel", "hirlevel", "adatvedelem",
                 "cookie", "bejelentkez", "regisztracio", "palyazatiras", "elofizet", "kapcsolat",
                 "szolgaltatas", "rolunk", "gyik", "kozlemeny", "tajekoztatas", "beszamolo", "utmutato",
                 "informaciok", "sablon", "nyomtatvany", "karrier", "allaslehetoseg", "jogszabaly", "piackutat",
                 "egyuttmukodesek", "modosult", "nyilvantartasba", "archiv", "elszamolas", "palyazatkezelo"]
# Budapesti magánszemélynek / vállalkozásnak / nonprofit kft-nek nem szóló területek
NEM_RELEVANS = ["hataron tul", "kulhoni", "karpatalja", "erdely", "felvidek", "vajdasag", "csango", "egyhaz",
                "nemzetisegi", "magyar falu", "falusi", "kistelepules", "allatved", "vallasturiszt",
                "mezogazdas", "agrar", "erdeszet", "halasz", "szabolcs", "frekvencia", "mhz",
                "hatartalanul", "zrinyi ilona", "vinum"]


def norm(s):
    """Kisbetű, ékezet nélkül, egyszerűsített szóközökkel."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()


def tartalmaz(szoveg, szo):
    # rövid szavaknál (ev, tv, nea) egész szó kell, különben szó eleji egyezés
    if len(szo) <= 3:
        return re.search(r"(?<![a-z0-9])" + re.escape(szo) + r"(?![a-z0-9])", szoveg) is not None
    return re.search(r"(?<![a-z0-9])" + re.escape(szo), szoveg) is not None


def letolt(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "hu-HU,hu;q=0.9,en;q=0.5",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        nyers = r.read()
        kodolas = r.headers.get_content_charset() or "utf-8"
    return nyers.decode(kodolas, errors="replace")


class LinkGyujto(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.linkek, self._href, self._szoveg = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href, self._szoveg = dict(attrs).get("href"), []

    def handle_data(self, data):
        if self._href is not None:
            self._szoveg.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.linkek.append((self._href, " ".join("".join(self._szoveg).split())))
            self._href = None


def html_elemek(forras, tartalom):
    p = LinkGyujto()
    p.feed(tartalom)
    elemek, latott = [], set()
    for href, cim in p.linkek:
        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")) or len(cim) < 25:
            continue
        link = urljoin(forras["url"], href).split("#")[0]
        # a forrásoldal maga, vagy egy domain kezdőlapja nem felhívás
        if link in latott or link.rstrip("/") == forras["url"].rstrip("/") or urlparse(link).path.strip("/") == "":
            continue
        latott.add(link)
        elemek.append({"cim": cim[:160], "link": link, "leiras": ""})
    return elemek


def rss_elemek(tartalom):
    gyoker = ET.fromstring(tartalom.encode("utf-8"))
    elemek = []
    for item in gyoker.iter("item"):
        cim = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        leiras = re.sub(r"<[^>]+>", " ", unescape(item.findtext("description") or ""))
        if cim and link:
            elemek.append({"cim": unescape(cim)[:160], "link": link, "leiras": " ".join(leiras.split())[:400]})
    return elemek


def profilok(elem, forras):
    szoveg = norm(elem["cim"] + " " + elem["leiras"])
    if any(tartalmaz(szoveg, s) for s in KIZARO_SZAVAK + NEM_RELEVANS):
        return []
    ev = datetime.now().year
    evek = [int(e) for e in re.findall(r"(?<!\d)(20\d\d)(?!\d)", szoveg)]
    if evek and max(evek) < ev:  # csak régi évszám szerepel benne: lejárt kiírás
        return []
    if not any(tartalmaz(szoveg, s.strip()) for s in PALYAZAT_SZAVAK):
        return []
    talalt = [k for k, p in PROFILOK.items() if any(tartalmaz(szoveg, s) for s in p["szavak"])]
    if forras.get("profil") and forras["profil"] not in talalt:
        talalt.insert(0, forras["profil"])
    return talalt


HONAPOK = "januar|februar|marcius|aprilis|majus|junius|julius|augusztus|szeptember|oktober|november|december"
DATUM = r"20\d\d\. ?(?:\d{1,2}|" + HONAPOK + r")\.? ?\d{1,2}"
HATARIDO_MINTA = re.compile(r"(?:hatarido|benyujt\w*|beadas\w*)[^.]{0,80}?(" + DATUM + ")")
DATUM_MINTA = re.compile(DATUM)


def hatarido(szoveg, csak_hataridore=False):
    """Határidő-tipp: 'határidő ... dátum' minta, vagy (ha szabad) az első dátum."""
    s = norm(szoveg)
    m = HATARIDO_MINTA.search(s)
    if m:
        return m.group(1)
    if csak_hataridore:
        return ""
    m = DATUM_MINTA.search(s)
    return m.group(0) if m else ""


def datum(szoveg):
    """'2026. november 30' / '2026.11.30' -> date, ha értelmezhető."""
    m = re.match(r"(20\d\d)\. ?(\d{1,2}|[a-z]+)\.? ?(\d{1,2})", szoveg or "")
    if not m:
        return None
    ho = m.group(2)
    ho = int(ho) if ho.isdigit() else HONAPOK.split("|").index(ho) + 1
    try:
        return datetime(int(m.group(1)), ho, int(m.group(3))).date()
    except ValueError:
        return None


ONRESZ_NELKUL = re.compile(r"onresz nelkul|oneron? nelkul|nem kell onresz|nem szukseges onresz|onresz nem szukseges|"
                           r"nincs onresz|onresz: ?0 ?%|100 ?%-os (vissza nem teritendo|tamogat)|"
                           r"tamogatasi intenzitas[a-z]*:? ?100 ?%")
ONRESZ_SZAZALEK = re.compile(r"onresz[a-z]*[^.%\d]{0,40}?(\d{1,2}) ?%|(\d{1,2}) ?% ?(-os|os)? ?onresz")
INTENZITAS = re.compile(r"tamogatasi intenzitas[a-z]*[^.%\d]{0,40}?(\d{2,3}) ?%|(\d{2,3}) ?%-os tamogatasi intenzitas")
ALACSONY_ONRESZ = 25
MAX_RESZLETES = 150  # ennyi új felhívás oldalát nyitjuk meg futásonként  # eddig a százalékig "kevés önrész"


def onresz(szoveg):
    """Önrész becslése a felhívás szövegéből: (sorrend, címke). Kisebb sorrend = jobb."""
    s = norm(szoveg)
    if ONRESZ_NELKUL.search(s):
        return 0, "🟢 önrész nélkül"
    m = ONRESZ_SZAZALEK.search(s)
    if m:
        pct = int(m.group(1) or m.group(2))
        return (0, "🟢 önrész nélkül") if pct == 0 else ((1, f"🟡 önrész {pct}%") if pct <= ALACSONY_ONRESZ
                                                       else (3, f"🔴 önrész {pct}%"))
    m = INTENZITAS.search(s)
    if m:
        pct = 100 - min(100, int(m.group(1) or m.group(2)))
        return (0, "🟢 önrész nélkül (100% támogatás)") if pct == 0 else (
            (1, f"🟡 önrész kb. {pct}%") if pct <= ALACSONY_ONRESZ else (3, f"🔴 önrész kb. {pct}%"))
    if tartalmaz(s, "visszateritendo") and not tartalmaz(s, "vissza nem teritendo"):
        return 3, "🔴 hitel / visszatérítendő"
    if tartalmaz(s, "vissza nem teritendo"):
        return 2, "⚪ vissza nem térítendő, önrész nem derül ki"
    return 2, "⚪ önrész nem derül ki"


def oldal_szoveg(link):
    """A felhívás oldalának sima szövege (önrész kereséséhez); hiba esetén üres."""
    try:
        tartalom = letolt(link)
    except Exception:
        return ""
    tartalom = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", tartalom)
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", tartalom)).split())[:60000]


def azonosito(link):
    u = urlparse(link)
    return hashlib.sha1((u.netloc.replace("www.", "") + u.path.rstrip("/") + "?" + u.query).encode()).hexdigest()[:16]


def betolt_allapot():
    try:
        with open(ALLAPOT_FAJL, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"latott": {}, "hibak": {}}


def mentes(allapot):
    with open(ALLAPOT_FAJL, "w", encoding="utf-8") as f:
        json.dump(allapot, f, ensure_ascii=False, indent=1, sort_keys=True)


def level(tema, html_test):
    kuldo, jelszo, cimzett = (os.environ.get(k, "") for k in ("EMAIL_KULDO", "EMAIL_JELSZO", "EMAIL_CIMZETT"))
    if not (kuldo and jelszo and cimzett):
        print("  ⚠️ Nincs e-mail beállítás, nem küldök levelet.")
        return
    msg = MIMEText(html_test, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = tema, kuldo, cimzett
    with smtplib.SMTP_SSL(os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", 465)), timeout=20) as s:
        s.login(kuldo, jelszo)
        s.sendmail(kuldo, [cimzett], msg.as_string())
    print("  📧 E-mail elküldve.")


def elem_html(e):
    extra = [e["onresz"]]
    if len(e["profilok"]) > 1:
        extra.append("+ " + ", ".join(PROFILOK[k]["cim"].split(" ", 1)[1] for k in e["profilok"][1:]))
    if e["hatarido"]:
        extra.append("dátum: " + e["hatarido"])
    extra.append(e["forras"])
    return (f'<li><a href="{escape(e["link"])}">{escape(e["cim"])}</a>'
            f'<br><small>{escape(" · ".join(extra))}</small></li>')


def level_html(ujak, hibas_forrasok, kezdeti):
    sorok = []
    if kezdeti:
        sorok.append("<p>Ez az első futás: az összes most látható, ránk illő felhívás. "
                     "Ezután csak az újakat küldöm.</p>")
    sorok.append("<p><small>🟢 önrész nélkül · 🟡 kevés önrész (≤" + str(ALACSONY_ONRESZ) + "%) · "
                 "⚪ nem derül ki az oldalról · 🔴 magas önrész vagy hitel (a levél végén)</small></p>")
    jok = sorted((e for e in ujak if e["onresz_sor"] < 3), key=lambda e: e["onresz_sor"])
    for kulcs, p in PROFILOK.items():
        csoport = [e for e in jok if e["profilok"][0] == kulcs]
        if csoport:
            sorok.append(f"<h3>{p['cim']} ({len(csoport)})</h3><ul>")
            sorok.extend(elem_html(e) for e in csoport)
            sorok.append("</ul>")
    rosszak = [e for e in ujak if e["onresz_sor"] >= 3]
    if rosszak:
        sorok.append(f"<h3>🔴 Magas önrész / hitel ({len(rosszak)})</h3><ul>")
        sorok.extend(elem_html(e) for e in rosszak)
        sorok.append("</ul>")
    if hibas_forrasok:
        sorok.append("<p><small>Most nem sikerült elérni: " + escape(", ".join(hibas_forrasok)) + "</small></p>")
    return "\n".join(sorok)


def main():
    most = datetime.now(timezone.utc)
    print(f"🔎 Pályázat-figyelő – {most.strftime('%Y.%m.%d %H:%M')} UTC{' (PRÓBA)' if PROBA else ''}")
    allapot = betolt_allapot()
    kezdeti = not allapot["latott"]
    ujak, hibas = [], []

    for forras in FORRASOK:
        try:
            tartalom = letolt(forras["url"])
            elemek = rss_elemek(tartalom) if forras["tipus"] == "rss" else html_elemek(forras, tartalom)
        except Exception as e:  # egy rossz forrás ne állítsa le a többit
            print(f"  ❌ {forras['nev']}: {type(e).__name__}: {e}")
            hibas.append(forras["nev"])
            allapot["hibak"][forras["nev"]] = allapot["hibak"].get(forras["nev"], 0) + 1
            continue
        allapot["hibak"].pop(forras["nev"], None)

        illo = 0
        for elem in elemek:
            prof = profilok(elem, forras)
            if not prof:
                continue
            illo += 1
            azon = azonosito(elem["link"])
            # ugyanaz a hír több forrásból / keresésből is jöhet: a címre is szűrünk
            cim_azon = "c" + hashlib.sha1(norm(re.sub(r" - [^-]+$", "", elem["cim"])).encode()).hexdigest()[:15]
            if azon in allapot["latott"] or cim_azon in allapot["latott"]:
                continue
            elem.update(profilok=prof, forras=forras["nev"])
            ujak.append(elem)
            bejegyzes = {"cim": elem["cim"][:150], "link": elem["link"], "elso": most.strftime("%Y-%m-%d")}
            allapot["latott"][azon] = bejegyzes
            allapot["latott"][cim_azon] = bejegyzes
        print(f"  ✅ {forras['nev']}: {len(elemek)} link, {illo} illő")

    # a felhívás oldalát is megnézzük az önrész és a határidő miatt
    for i, e in enumerate(ujak):
        oldal = oldal_szoveg(e["link"]) if i < MAX_RESZLETES and not e["link"].lower().endswith(".pdf") else ""
        alap = e["cim"] + " " + e["leiras"]
        e["onresz_sor"], e["onresz"] = onresz(alap + " " + oldal)
        e["hatarido"] = hatarido(alap) or hatarido(oldal, csak_hataridore=True)
    # amelyiknek a határideje már elmúlt, azt nem küldjük (de látottnak számít)
    ma = datetime.now().date()
    ujak = [e for e in ujak if not (datum(e["hatarido"]) and datum(e["hatarido"]) < ma)]

    print(f"🆕 Új találat: {len(ujak)}")
    for e in ujak:
        print(f"   [{','.join(e['profilok'])}] {e['onresz']} | {e['hatarido']} | {e['cim']}  →  {e['link']}")

    if PROBA:
        return
    if ujak:
        zold = sum(e["onresz_sor"] == 0 for e in ujak)
        tema = (f"🔎 Pályázatok – kezdeti lista ({len(ujak)})" if kezdeti
                else f"🔎 {len(ujak)} új pályázati lehetőség") + (f", ebből {zold} önrész nélkül" if zold else "")
        level(tema, level_html(ujak, hibas, kezdeti))
    # ha egy forrás egy hete folyamatosan hibás, szólunk (egyszer)
    tartos = [n for n, db in allapot["hibak"].items() if db == 7]
    if tartos:
        level("⚠️ Pályázat-figyelő: elérhetetlen forrás", "<p>Egy hete nem érhető el: "
              + escape(", ".join(tartos)) + ". Lehet, hogy megváltozott a címe.</p>")
    mentes(allapot)


if __name__ == "__main__":
    sys.exit(main())
