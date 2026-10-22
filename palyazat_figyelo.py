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
UJRAKULD = os.environ.get("UJRAKULD", "") in ("1", "true")
WEB_MAPPA = "palyazat"
WEB_CIM = "https://mrgabee.github.io/mentoheli/palyazat/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# tipus: "rss" vagy "html". profil: ha meg van adva, a forrás minden
# pályázat-szerű linkje ehhez a profilhoz tartozik (szakmai forrás).
# tipus: "rss" vagy "html". profil: ha meg van adva, a forrás minden
# pályázat-szerű linkje ehhez a profilhoz tartozik (szakmai forrás).
# link_minta: csak az ilyen című (URL) linkeket nézzük az oldalon (menüpontok kiszűrésére).
FORRASOK = [
    # --- Összesítő oldalak ---
    {"nev": "Palyazatok.org", "url": "https://palyazatok.org/feed/", "tipus": "rss"},
    {"nev": "PAFI", "url": "https://pafi.hu/palyazatok", "tipus": "html", "link_minta": r"/p/"},
    {"nev": "Nonprofit.hu", "url": "https://www.nonprofit.hu/palyazatok", "tipus": "html", "link_minta": r"/palyazatok/."},
    {"nev": "Napitender", "url": "https://napitender.hu/feed/", "tipus": "rss"},
    {"nev": "Vállalkozz Ma", "url": "https://www.vallalkozzma.hu/palyazatok/", "tipus": "html"},
    {"nev": "Civil Információs Portál", "url": "https://civil.info.hu/palyazatok", "tipus": "html", "profil": "nonprofit"},
    # --- Állami ---
    {"nev": "NFSZ", "url": "https://nfsz.munka.hu/", "tipus": "html", "profil": "vallalkozas"},
    {"nev": "NKFIH", "url": "https://nkfih.gov.hu/palyazoknak/palyazatok/aktualis-felhivasok", "tipus": "html",
     "profil": "muszaki", "link_minta": r"palyazati-felhivas|/nkfi-alap/[^/]+/?$"},
    {"nev": "Vállalkozz Digitálisan", "url": "https://vallalkozzdigitalisan.hu/", "tipus": "html", "profil": "vallalkozas",
     "link_minta": r"palyazat|tamogatas"},
    {"nev": "Bethlen Gábor Alapkezelő (NEA stb.)", "url": "https://bgazrt.hu/tamogatasok/nemzeti-egyuttmukodesi-alap/",
     "tipus": "html", "profil": "nonprofit", "link_minta": r"felhivas|kiiras|palyazat"},
    {"nev": "Bethlen Gábor Alapkezelő", "url": "https://bgazrt.hu/", "tipus": "html", "link_minta": r"felhivas|kiiras|palyazat"},
    # --- Kultúra, média, oktatás ---
    {"nev": "Nemzeti Kulturális Alap", "url": "https://nka.hu/kiemelt-kategoriak/palyaztatas/kollegiumok-felhivasai/felhivasok/",
     "tipus": "html", "link_minta": r"felhivas"},
    {"nev": "Médiatanács (NMHH)", "url": "https://nmhh.hu/media/palyazatok", "tipus": "html", "profil": "media",
     "link_minta": r"/cikk/|tamogatasi-program|palyazat"},
    {"nev": "Nemzeti Filmintézet", "url": "https://nfi.hu/", "tipus": "html", "profil": "media", "link_minta": r"palyazat|tamogatas"},
    {"nev": "Ökotárs Alapítvány", "url": "https://okotars.hu/", "tipus": "html", "profil": "nonprofit", "link_minta": r"palyazat|felhivas"},
    # --- Google Hírek keresések: bármelyik oldalon megjelent felhívást elkapják ---
    *[{"nev": f"Google Hírek: {k}", "tipus": "rss", "hir": True,
       "url": "https://news.google.com/rss/search?hl=hu&gl=HU&ceid=HU:hu&q=" + quote(k + " when:14d")}
      for k in ["eszközbeszerzés pályázat", "eszközbeszerzési támogatás", "gépbeszerzés pályázat",
                "technológiai fejlesztés pályázat", "pályázati felhívás", "pályázat egyéni vállalkozó", "pályázat mikrovállalkozás",
                "vissza nem térítendő támogatás", "pályázat önrész nélkül", "pályázat nonprofit",
                "pályázat civil szervezet", "pályázat pedagógus", "pályázat informatika oktatás",
                "pályázat televízió műsor", "pályázat média tartalomgyártás", "Médiatanács pályázat",
                "NKA pályázat", "Erasmus+ pályázat", "pályázat munkavédelem", "pályázat repülés",
                "pályázat felnőttképzés", "pályázat Budapest", "pályázat Csepel"]],
    # --- Helyi ---
    {"nev": "Csepel.hu", "url": "https://csepel.hu/", "tipus": "html", "profil": "helyi"},
]

PROFILOK = {
    # elsődleges: eszközbeszerzés (ez van legelöl a levélben és a weboldalon)
    "eszkoz": {
        "cim": "🖥️ Eszközbeszerzés",
        "szavak": ["eszkozbeszerz", "eszkozfejleszt", "eszkoztamogat", "eszkozpark", "gepbeszerz", "gepbeszerzes",
                   "berendezes", "szamitogep", "laptop", "notebook", "kamera", "technikai eszkoz", "muszaki fejlesztes",
                   "technologiai fejleszt", "technologiafejleszt", "beruhazas", "gep-", "gepek", "eszkozok"],
    },
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
                   "vallalkozasfejleszt", "vallalkozoi", "digitalizaci",
                   "kamatmentes", "visszateritendo"],
    },
    "helyi": {
        "cim": "📍 Budapest / XXI. kerület",
        "szavak": ["budapest", "fovaros", "csepel", "xxi. kerulet", "xxi. ker"],
    },
}

# Ezek nélkül a link nem pályázat (menüpontok, cikkek kiszűrésére)
PALYAZAT_SZAVAK = ["palyaz", "felhivas", "kiiras", "tamogatas", "osztondij", "alap ", "program", "hitel"]
# hírcikkeknél (Google Hírek) erősebb jel kell, hogy tényleg megnyíló felhívásról szóljon
HIR_SZAVAK = ["palyazati felhivas", "kiir", "palyazhat", "igenyelhet", "beadhat", "nyilik", "megnyil", "indul",
              "jelentkez", "palyazatot hirdet", "palyazatot ir"]
# Ezekkel biztosan nem új lehetőség
KIZARO_SZAVAK = ["eredmeny", "nyertes", "dontes", "lezarult", "kiertekel", "hirlevel", "adatvedelem",
                 "cookie", "bejelentkez", "regisztracio", "palyazatiras", "elofizet", "kapcsolat",
                 "szolgaltatas", "rolunk", "gyik", "kozlemeny", "tajekoztatas", "beszamolo", "utmutato",
                 "informaciok", "sablon", "nyomtatvany", "karrier", "allaslehetoseg", "jogszabaly", "piackutat",
                 "egyuttmukodesek", "modosult", "nyilvantartasba", "archiv", "elszamolas", "palyazatkezelo",
                 "tanfolyam", "elominosit", "kedvezmeny", "tamogataspont", "kinevez", "bucsuz", "emlekez",
                 "szemelyi valtozas", "uj ablakban", "fesztivaldij", "fesztivalszerepl", "tamogatott projekt",
                 "szerzodesmodosit", "szakmai beszamolo", "folyamata", "jeloltallit",
                 # állás- és egyéb (nem támogatási) "pályázatok", hírek a támogatásokról
                 "vezerigazgat", "igazgatoi", "rektor", "munkakor", "allasajanlat", "olimpia", "kormanyhatarozat",
                 "kozlony", "vizsgal", "botrany", "kampany", "kapott", "nyert"]
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
    with urllib.request.urlopen(req, timeout=45) as r:
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
        if "?st=" in link:  # keresőoldalak
            continue
        if forras.get("link_minta") and not re.search(forras["link_minta"], norm(link)):
            continue
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
    evek = [int(e) for e in re.findall(r"(?<!\d)(20\d\d)(?!\d)", szoveg + " " + elem["link"])]
    if evek and max(evek) < ev:  # csak régi évszám szerepel benne: lejárt kiírás
        return []
    if not any(tartalmaz(szoveg, s.strip()) for s in PALYAZAT_SZAVAK):
        return []
    if forras.get("hir") and not any(tartalmaz(szoveg, s) for s in HIR_SZAVAK):
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
    """A felhívás oldalának sima szövege és meta-leírása; hiba esetén üres."""
    try:
        tartalom = letolt(link)
    except Exception:
        return "", ""
    m = re.search(r'(?is)<meta[^>]+(?:name|property)=["\'](?:og:)?description["\'][^>]*content=["\']([^"\']+)', tartalom)
    meta = " ".join(unescape(m.group(1)).split()) if m else ""
    tartalom = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", tartalom)
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", tartalom)).split())[:60000], meta


# A kiírás szövegéből kivonatolt rövid összefoglaló: a jellegzetes
# fejezetcímek ("A pályázat célja", "Pályázók köre", ...) utáni első mondat.
OSSZEFOGLALO_MINTAK = [
    ("Cél", r"(?:a (?:pályázat|program|felhívás|támogatás)(?:i (?:kiírás|felhívás))? célja|támogatás célja)\s*[:\-–]?\s*"),
    ("Kik pályázhatnak", r"(?:pályázók köre|pályázni jogosultak?(?: köre)?|kik pályázhatnak\??|pályázatot nyújthatnak be|"
                         r"támogatást igénylők köre|kedvezményezettek köre|pályázhatnak)\s*[:\-–]?\s*"),
    ("Mire", r"(?:támogatható tevékenységek?|elszámolható költségek?|támogatható célok?|mire lehet pályázni\??|"
             r"a támogatás felhasználható)\s*[:\-–]?\s*"),
    ("Összeg", r"(?:igényelhető támogatás(?: összege)?|a támogatás (?:maximális |legmagasabb |legkisebb )?összege|"
               r"keretösszeg(?:e)?|rendelkezésre álló forrás)\s*[:\-–]?\s*"),
]


def osszefoglalo(szoveg, meta="", leiras=""):
    """{"Cél": ..., "Kik pályázhatnak": ..., ...}; ha semmi nem található, a meta-/RSS-leírás."""
    eredmeny = {}
    for cimke, minta in OSSZEFOGLALO_MINTAK:
        m = re.search(minta, szoveg, re.I)
        if not m:
            continue
        resz = szoveg[m.end():m.end() + 400]
        mondat = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÖŐÚÜŰ])", resz)[0]
        mondat = mondat[:240].rsplit(" ", 1)[0] + "…" if len(mondat) > 240 else mondat
        if len(mondat) >= 15:
            eredmeny[cimke] = mondat
    if not eredmeny:
        alap = meta or leiras
        if len(alap) >= 30:
            eredmeny["Röviden"] = alap[:300].rsplit(" ", 1)[0] + ("…" if len(alap) > 300 else "")
    return eredmeny


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
    kuldo, jelszo = os.environ.get("EMAIL_KULDO", ""), os.environ.get("EMAIL_JELSZO", "")
    # saját címzett(ek) a PALYAZAT_CIMZETT titokban (vesszővel több is), különben a közös cím
    cimzett = os.environ.get("PALYAZAT_CIMZETT", "").strip() or os.environ.get("EMAIL_CIMZETT", "")
    cimzettek = [c.strip() for c in cimzett.split(",") if c.strip()]
    if not (kuldo and jelszo and cimzettek):
        print("  ⚠️ Nincs e-mail beállítás, nem küldök levelet.")
        return
    msg = MIMEText(html_test, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = tema, kuldo, ", ".join(cimzettek)
    with smtplib.SMTP_SSL(os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", 465)), timeout=20) as s:
        s.login(kuldo, jelszo)
        s.sendmail(kuldo, cimzettek, msg.as_string())
    print("  📧 E-mail elküldve.")


def elem_html(e):
    extra = [e["onresz"]]
    if len(e["profilok"]) > 1:
        extra.append("+ " + ", ".join(PROFILOK[k]["cim"].split(" ", 1)[1] for k in e["profilok"][1:]))
    if e["hatarido"]:
        extra.append("dátum: " + e["hatarido"])
    extra.append(e["forras"])
    kivonat = "".join(f"<br><small><b>{escape(k)}:</b> {escape(v)}</small>"
                      for k, v in e.get("osszefoglalo", {}).items())
    return (f'<li style="margin-bottom:10px"><a href="{escape(e["link"])}">{escape(e["cim"])}</a>'
            f'<br><small>{escape(" · ".join(extra))}</small>{kivonat}</li>')


def level_html(ujak, hibas_forrasok, kezdeti):
    sorok = []
    if kezdeti:
        sorok.append("<p>Ez az első futás: az összes most látható, ránk illő felhívás. "
                     "Ezután csak az újakat küldöm.</p>")
    sorok.append(f'<p>Grafikus áttekintés, szűrőkkel: <a href="{WEB_CIM}">{WEB_CIM}</a></p>')
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
    if UJRAKULD:  # kézi újraküldés: mindent újnak tekintünk, a teljes mostani lista megy ki
        print("  ↻ Újraküldés: az eddig látott felhívásokat is újra elküldöm.")
        allapot["latott"], allapot["tetelek"] = {}, {}
    allapot.setdefault("tetelek", {})
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
            elem.update(profilok=prof, forras=forras["nev"], azon=azon)
            ujak.append(elem)
            bejegyzes = {"cim": elem["cim"][:150], "link": elem["link"], "elso": most.strftime("%Y-%m-%d")}
            allapot["latott"][azon] = bejegyzes
            allapot["latott"][cim_azon] = bejegyzes
        print(f"  ✅ {forras['nev']}: {len(elemek)} link, {illo} illő")

    # a felhívás oldalát is megnézzük az önrész és a határidő miatt
    for i, e in enumerate(ujak):
        oldal, meta = (oldal_szoveg(e["link"]) if i < MAX_RESZLETES and not e["link"].lower().endswith(".pdf")
                       else ("", ""))
        alap = e["cim"] + " " + e["leiras"]
        e["osszefoglalo"] = osszefoglalo(oldal, meta, e["leiras"])
        e["onresz_sor"], e["onresz"] = onresz(alap + " " + oldal)
        e["hatarido"] = hatarido(alap) or hatarido(oldal, csak_hataridore=True)
    # amelyiknek a határideje már elmúlt, azt nem küldjük (de látottnak számít)
    ma = datetime.now().date()
    ujak = [e for e in ujak if not (datum(e["hatarido"]) and datum(e["hatarido"]) < ma)]
    for e in ujak:  # a weboldalhoz minden részletet megőrzünk
        allapot["tetelek"][e["azon"]] = {k: e[k] for k in ("cim", "link", "forras", "profilok", "onresz",
                                                          "onresz_sor", "hatarido", "osszefoglalo")}
        allapot["tetelek"][e["azon"]]["elso"] = most.strftime("%Y-%m-%d")

    print(f"🆕 Új találat: {len(ujak)}")
    for e in ujak:
        print(f"   [{','.join(e['profilok'])}] {e['onresz']} | {e['hatarido']} | {e['cim']}  →  {e['link']}")
        for k, v in e["osszefoglalo"].items():
            print(f"        {k}: {v}")

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
    weboldal_adatok(allapot, hibas, most)


def weboldal_adatok(allapot, hibas, most):
    """A belépéses weboldal (palyazat/index.html) titkosított adatfájlja.

    Hibrid titkosítás: az adat AES-GCM-mel, az AES-kulcs a palyazat/kulcs.json
    nyilvános RSA-kulcsával van titkosítva. A titkos RSA-kulcsot csak a
    felhasználónév + jelszó párosból származtatott kulccsal lehet kinyitni,
    a böngészőben, így a futtatáshoz nem kell semmilyen titok."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        print("  ⚠️ Nincs 'cryptography' csomag, a weboldal adatai nem frissülnek.")
        return
    import base64
    with open(os.path.join(WEB_MAPPA, "kulcs.json"), encoding="utf-8") as f:
        kulcs = json.load(f)
    nyilvanos = serialization.load_der_public_key(base64.b64decode(kulcs["nyilvanos"]))
    ma = most.date()
    tetelek = []
    for azon, t in allapot["tetelek"].items():
        d = datum(t.get("hatarido"))
        tetelek.append({**t, "azon": azon, "lejart": bool(d and d < ma), "hatarido_iso": d.isoformat() if d else ""})
    adat = json.dumps({"frissitve": most.isoformat(timespec="minutes"), "tetelek": tetelek,
                       "profilok": {k: p["cim"] for k, p in PROFILOK.items()},
                       "forrasok": len(FORRASOK), "hibas_forrasok": hibas}, ensure_ascii=False).encode()
    aes_kulcs, iv = os.urandom(32), os.urandom(12)
    kimenet = {
        "kulcs": base64.b64encode(nyilvanos.encrypt(aes_kulcs, padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))).decode(),
        "iv": base64.b64encode(iv).decode(),
        "adat": base64.b64encode(AESGCM(aes_kulcs).encrypt(iv, adat, None)).decode(),
    }
    with open(os.path.join(WEB_MAPPA, "adatok.json"), "w", encoding="utf-8") as f:
        json.dump(kimenet, f)
    print(f"  🌐 Weboldal adatai frissítve ({len(tetelek)} tétel).")


if __name__ == "__main__":
    sys.exit(main())
