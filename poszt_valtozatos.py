"""
🎨 Változatos Facebook-posztok
- Napi arculat: a címsor, az elválasztó vonalak, a területcímkék és a
  záró mondat egy napon belül egységes, de minden nap más (a dátumból
  számolja, így egy napon belül minden futás ugyanazt választja).
- Személyes bevezető: minden poszt egy közvetlen, saját hangú mondattal
  indul, ez posztonként változik, hogy ne ismétlődjön.
A tartalom (címek, időpontok, linkek) nem változik.
Új változatot a listák bővítésével lehet hozzáadni.
"""

import poszt_ellenor
import random
from datetime import datetime
from zoneinfo import ZoneInfo

MAGYAR_TZ = ZoneInfo("Europe/Budapest")

CIMEK = {
    "vizmuvek": [
        "💧 FŐVÁROSI VÍZMŰVEK ÉRTESÍTŐ 💧",
        "🚰 VÍZMŰVES HÍREK A KÖRNYÉKRŐL 🚰",
        "💦 FIGYELEM, VÍZÜGY! 💦",
        "🔧 VÍZMŰVEK – ÚJ MUNKÁK A KÖRNYÉKEN 🔧",
        "💧 VÍZHIÁNY / VÍZMŰVES MUNKA 💧",
    ],
    "aramszunet": [
        "⚡ ÁRAMSZÜNET ÉRTESÍTŐ ⚡",
        "🔌 ÁRAMSZÜNET A KÖRNYÉKEN 🔌",
        "💡 FIGYELEM, ÁRAMSZÜNET! 💡",
        "⚡ E.ON – ÚJ ÁRAMSZÜNET ⚡",
        "🔦 KÉSZÜLJ, ÁRAMSZÜNET LESZ! 🔦",
    ],
    "aramszunet_emlekezteto": [
        "⏰ EMLÉKEZTETŐ – közelgő áramszünet ⏰",
        "🔔 NE FELEDD: áramszünet közeleg! 🔔",
        "📆 EMLÉKEZTETŐ – hamarosan áramszünet 📆",
        "⏳ MÁR NEM SOKÁRA: tervezett áramszünet ⏳",
    ],
    "rendorseg": [
        "🚔 RENDŐRSÉGI HÍR",
        "🚨 FRISS A RENDŐRSÉGTŐL",
        "👮 RENDŐRSÉGI TÁJÉKOZTATÁS",
        "🚓 A RENDŐRSÉG KÖZLI",
    ],
    "korozes": [
        "🔎 KÖRÖZÉS",
        "🚨 SEGÍTS A RENDŐRSÉGNEK!",
        "👀 LÁTTAD? KÖRÖZÉS",
        "📢 KÖRÖZÉSI FELHÍVÁS",
    ],
    "idojaras": [
        "IDŐJÁRÁSI RIASZTÁS",
        "FIGYELMEZTETÉS – VESZÉLYES IDŐ",
        "RIASZTÁST ADOTT KI A HUNGAROMET",
        "VIGYÁZAT, VÁLTOZÉKONY IDŐ!",
    ],
    "csili": [
        "🎭 PROGRAM A CSILIBEN 🎭",
        "🎟️ CSILI PROGRAMAJÁNLÓ 🎟️",
        "✨ KULTÚRA PESTERZSÉBETEN ✨",
        "🎶 A CSILI MŰSORÁRÓL 🎶",
    ],
    "csili_emlekezteto": [
        "⏰ HOLNAP A CSILIBEN ⏰",
        "🔔 EMLÉKEZTETŐ – HOLNAPI PROGRAMOK 🔔",
        "📆 NE FELEDJÉTEK: HOLNAP CSILI! 📆",
    ],
    "reggeli": [
        "☀️ JÓ REGGELT, CSEPEL, PESTERZSÉBET, SZIGETSZENTMIKLÓS! ☀️",
        "🌅 REGGELI KÖRKÉP A KÖRNYÉKRŐL 🌅",
        "☕ KÁVÉ MELLÉ: EZ VÁR MA RÁNK ☕",
        "🗞️ NAPINDÍTÓ – MAI HELYZET 🗞️",
        "🌞 SZÉP NAPOT! ÍGY KEZDŐDIK A MAI NAP 🌞",
    ],
    "programok": [
        "🎉 MAI PROGRAMAJÁNLÓ A KÖRNYÉKRŐL 🎉",
        "🎸 MI VAN MA CSEPELEN? 🎸",
        "🎟️ KERÜLETI PROGRAMOK 🎟️",
        "✨ ERRE ÉRDEMES FIGYELNI A HÉTEN ✨",
        "🎶 KONCERT, SZÍNHÁZ, KÖZÖSSÉG – A KÖRNYÉKEN 🎶",
    ],
    "sport_elozetes": [
        "⚽ CSEPELI MECCSEK A HÉTVÉGÉN ⚽",
        "🏟️ HÉTVÉGI MECCSEK – SZURKOLJUNK A CSEPELIEKNEK! 🏟️",
        "⚽ KI MIKOR JÁTSZIK? HÉTVÉGI MECCSPROGRAM ⚽",
        "🥅 HÉTVÉGI MENETREND A CSEPELI CSAPATOKNAK 🥅",
    ],
    "sport_hetkoz": [
        "⚽ HOLNAP JÁTSZIK A CSEPEL SC ⚽",
        "❤️ HÉTKÖZI MECCS – HAJRÁ, CSEPEL! 💙",
        "🏟️ MECCSNAP JÖN HÉTKÖZBEN IS 🏟️",
        "⚽ NE FELEDJÉTEK: HOLNAP MECCS! ⚽",
    ],
    "sport_eredmeny": [
        "⚽ ÍGY JÁTSZOTTAK A CSEPELI CSAPATOK ⚽",
        "📋 HÉTVÉGI EREDMÉNYEK – CSEPELI SPORT 📋",
        "🏁 LEFÚJTÁK! A CSEPELI CSAPATOK EREDMÉNYEI 🏁",
        "⚽ EREDMÉNYKÖZLŐ A KÖRNYÉKRŐL ⚽",
    ],
    "hetvege": [
        "🥳 HÉTVÉGI PROGRAMAJÁNLÓ 🥳",
        "🎈 MIT CSINÁLJUNK A HÉTVÉGÉN? 🎈",
        "🌟 ITT A HÉTVÉGE! IRÁNY A PROGRAMOK 🌟",
        "🎭 HÉTVÉGÉRE AJÁNLOM 🎭",
    ],
    "ezen_a_napon": [
        "📜 EZEN A NAPON TÖRTÉNT 📜",
        "🕰️ VISSZATEKINTŐ – MI TÖRTÉNT MA, RÉGEN? 🕰️",
        "📖 TÖRTÉNELMI NAPTÁR 📖",
        "⏳ A MAI NAP A TÖRTÉNELEMBEN ⏳",
    ],
    "erdekesseg": [
        "🏛️ KÖRNYÉKBELI ÉRDEKESSÉG 🏛️",
        "🔍 TUDTAD? – HELYTÖRTÉNET 🔍",
        "🗺️ FEDEZZÜK FEL A KÖRNYÉKET! 🗺️",
        "📚 A MI KÖRNYÉKÜNK – ÉRDEKESSÉGEK 📚",
    ],
    "kerdes": [
        "💬 KÉRDÉS NEKTEK 💬",
        "🗣️ BESZÉLGESSÜNK! 🗣️",
        "🤔 KÍVÁNCSI VAGYOK… 🤔",
        "❓ MAI KÉRDÉSEM ❓",
    ],
    "hivatali": [
        "📢 HIVATALI HÍREK 📢",
        "📮 FONTOS TUDNIVALÓ AZ ÜGYINTÉZÉSHEZ 📮",
        "📢 ÉRDEMES TUDNI 📢",
    ],
    "allasok": [
        "💼 ÚJ ÁLLÁSOK A KÖRNYÉKEN 💼",
        "🔎 MUNKÁT KERESEL? 🔎",
        "💼 ÁLLÁSAJÁNLÓ 💼",
        "🛠️ FRISS ÁLLÁSHIRDETÉSEK CSEPELEN 🛠️",
    ],
    "veradas": [
        "🩸 VÉRADÁS A KÖRNYÉKEN 🩸",
        "❤️ ADJ VÉRT, ÉLETET MENTESZ! ❤️",
        "🩸 HETI VÉRADÁSOK A KÖZELBEN 🩸",
        "💉 ITT ADHATSZ VÉRT A HÉTEN 💉",
    ],
    "veradas_emlekezteto": [
        "⏰ HOLNAP VÉRADÁS A KÖZELBEN ⏰",
        "🔔 EMLÉKEZTETŐ – HOLNAP VÉRADÁS 🔔",
        "🩸 NE FELEDD: HOLNAP ADHATSZ VÉRT 🩸",
    ],
    "esti_idojaras": [
        "🌙 HOLNAPI IDŐJÁRÁS 🌙",
        "🌤️ MILYEN IDŐ LESZ HOLNAP? 🌤️",
        "🌃 ESTI IDŐJÁRÁS-JELENTÉS 🌃",
        "⭐ JÓ ÉJT! ÍGY INDUL A HOLNAP ⭐",
    ],
    "vallalkozas": [
        "🏪 HELYI VÁLLALKOZÁS BEMUTATKOZIK 🏪",
        "🤝 ISMERD MEG A SZOMSZÉD VÁLLALKOZÓT! 🤝",
        "🛠️ CSEPELI KEZEK, CSEPELI MUNKA 🛠️",
        "🏠 A MI KÖRNYÉKÜNK VÁLLALKOZÓI 🏠",
    ],
    "vallalkozas_velemeny": [
        "⭐ KIT AJÁNLOTOK? ⭐",
        "🗳️ A TI VÉLEMÉNYETEK SZÁMÍT 🗳️",
        "👍 HELYI AJÁNLÓ – TI DÖNTÖTÖK 👍",
        "🔎 KERESEK, AJÁNLJATOK! 🔎",
    ],
}

BEVEZETOK = {
    "vizmuvek": [
        "Sziasztok! A Vízművek újabb munkát jelzett a környéken, érdemes ránézni 👇",
        "Néztem a Vízművek munkatérképét, ezt találtam a környéken:",
        "Csak szólok, hogy a Vízművek dolgozik a környéken, pár helyen lehet, hogy nem lesz víz:",
        "Hahó, csepeliek, erzsébetiek, miklósiak! Vízműves munka a környéken 💧",
        "Friss infó a Vízművektől, nézzétek meg, nem a ti utcátokat érinti-e:",
        "Érdemes lehet előre bekészíteni egy kis vizet, mert ezt láttam a Vízműveknél:",
    ],
    "aramszunet": [
        "Sziasztok! Az E.ON új áramszünetet jelzett a környéken 👇",
        "Gyorsan szólok, mert áramszünet lesz a környéken, nézzétek meg az utcátokat:",
        "Érdemes előre feltölteni a telefont, mert ezt találtam az E.ON-nál:",
        "Hahó, szomszédok! Áramszünetről jött hír:",
        "Friss infó az E.ON-tól, hátha titeket is érint:",
    ],
    "aramszunet_emlekezteto": [
        "Csak emlékeztetőül, mert már nincs sok hátra:",
        "Szóltam már róla, de jobb kétszer: közeledik az áramszünet!",
        "Nehogy meglepetés érjen titeket, ez hamarosan esedékes:",
        "Kis emlékeztető a korábban bejelentett áramszünetről:",
    ],
    "rendorseg": [
        "Ezt most osztotta meg a rendőrség, a környéket érinti:",
        "Fontos hír jött a rendőrségtől:",
        "Erről most olvastam a police.hu-n:",
        "Kérlek, figyeljetek egymásra! Ezt közölte a rendőrség:",
    ],
    "korozes": [
        "Kérlek, nézzétek meg, hátha tudtok segíteni:",
        "Ha bármit tudtok, szóljatok a rendőrségnek:",
        "Minden megosztás számít, kérlek, segítsetek a rendőrségnek:",
        "Új körözést adtak ki, a környéket érinti:",
    ],
    "idojaras": [
        "Vigyázzatok magatokra, riasztást adtak ki a környékre!",
        "Most jött a HungaroMet figyelmeztetése, érdemes felkészülni:",
        "Ha teheted, ma figyelj az időjárásra, mert ezt jelezték:",
        "Szólok, mert ma nem lesz barátságos az idő:",
    ],
    "csili": [
        "Ezt a programot láttam a Csiliben, szerintem érdemes ránézni 👇",
        "Ha még nincs tervetek, ezt most láttam a Csili műsorán:",
        "Ezt ajánlom figyelmetekbe a Csiliből:",
        "Friss a Csili kínálatából, hátha kedvet kaptok hozzá:",
        "Szólok, mert ez jól hangzik, hamarosan a Csiliben:",
    ],
    "csili_emlekezteto": [
        "Csak szólok, hogy holnap ezek lesznek a Csiliben, amikről korábban írtam:",
        "Kis emlékeztető, ha még nem foglaltatok helyet, holnap:",
        "Nehogy lemaradjatok, holnap ezek várnak a Csiliben:",
    ],
    # A {nev} helyére a figyelt oldal neve kerül
    "megosztas": [
        "Ezt most osztotta meg a(z) {nev}, érdemes elolvasni 👇",
        "Láttam a(z) {nev} oldalán, szerintem titeket is érdekel:",
        "Továbbadom, mert fontos lehet. Forrás: {nev}",
        "Friss hír a(z) {nev} oldaláról:",
        "Ezt találtam a(z) {nev} oldalán, nézzétek meg:",
    ],
    "reggeli": [
        "Összeszedtem, mire érdemes ma figyelni a környéken:",
        "Szép napot, szomszédok! Itt a mai helyzet:",
        "Reggeli kávé mellé hoztam a mai tudnivalókat ☕",
        "Sziasztok! Ez vár ma ránk a környéken:",
        "Mielőtt elindultok, nézzétek meg ezt:",
    ],
    "programok": [
        "Összeszedtem, mi lesz a környéken a következő napokban 👇",
        "Ha még nincs programotok, ezeket ajánlom a Munkásotthonból, a Barba Negrából és a Müpából:",
        "Szeretek szólni, ha jó program van a közelben, és most van bőven:",
        "Kultúra a szomszédban, nem kell messzire menni:",
        "Néztem a környékbeli műsorokat, ezek akadtak meg a szememen:",
    ],
    "sport_elozetes": [
        "Összeszedtem, mikor és hol lépnek pályára a csepeli csapatok a hétvégén, a felnőttektől az utánpótlásig:",
        "Ha kimennétek szurkolni, itt a hétvégi meccsek listája. A fiataloknak is jól jön a biztatás!",
        "Megnéztem a szövetségek adatbankjait, ezek a csepeli meccsek jönnek:",
        "Hétvégén is lesz sport bőven, a csepeli csapatok így játszanak:",
    ],
    "sport_eredmeny": [
        "Lezajlott a hét, összeszedtem, hogy szerepeltek a csepeli csapatok:",
        "Így végződtek az elmúlt napok meccsei a csepeli csapatoknál:",
        "Megnéztem az eredményeket, mutatom, ki hogy játszott:",
        "Gratulálok mindenkinek, aki pályára lépett! Az eredmények:",
    ],
    "hetvege": [
        "Itt a péntek! Összeszedtem, hova érdemes elmenni a hétvégén a környéken 👇",
        "Hétvégére tervezel? Ezeket a programokat ajánlom a közelben:",
        "Nem kell messzire menni egy jó hétvégéhez, nézzétek:",
        "Ha még nincs hétvégi program, itt van pár ötlet tőlem:",
    ],
    "ezen_a_napon": [
        "Kicsit belelapoztam a történelemkönyvbe, ezt találtam a mai napra:",
        "Tudtátok, mi történt ezen a napon régen? Nézzétek:",
        "Egy kis történelem a kávé mellé ☕",
        "Mai történelmi morzsák, hátha valaki nem tudta:",
    ],
    "erdekesseg": [
        "Ma egy kis helytörténettel jövök, szerintem érdekes 👇",
        "Ismeritek ezt a helyet? Összeszedtem róla pár dolgot:",
        "Szeretem a környékünket, és ma ezt mutatom meg nektek:",
        "Egy kis érdekesség a környékről, amit talán nem mindenki tud:",
    ],
    "kerdes": [
        "Most én kérdezek titeket! 😊",
        "Kíváncsi vagyok a véleményetekre:",
        "Beszélgessünk egy kicsit, érdekel, mit gondoltok:",
        "Egy gyors kérdés a mai napra:",
    ],
    "hivatali": [
        "Szólok, mert ez sokunkat érinthet:",
        "Átnéztem a posta és a kormányhivatal híreit, ezt érdemes tudni:",
        "Egy fontos hír, mielőtt postára vagy kormányablakba mennétek 👇",
    ],
    "allasok": [
        "Összegyűjtöttem a legfrissebb álláshirdetéseket a környékről 👇",
        "Ha te vagy valaki az ismerősi körödből munkát keres, ezeket nézd meg:",
        "Átnéztem az állásoldalakat, ezek az új hirdetések a környéken:",
        "Friss munkalehetőségek a közelben, hátha valakinek pont ez kell:",
    ],
    "veradas": [
        "Összeszedtem, hol adhattok vért a héten a környéken 👇",
        "Ha a héten van egy szabad órád, ezeken a helyeken életet menthetsz:",
        "Megnéztem a Vérellátó naptárát, ezek a véradások lesznek a közelben:",
        "Kevés dologgal lehet ennyit segíteni. Itt adhattok vért a héten:",
    ],
    "veradas_emlekezteto": [
        "Csak szólok, hogy holnap véradás lesz a környéken:",
        "Ha holnap ráérsz, itt életet menthetsz, nem kell messzire menni:",
        "Kis emlékeztető: holnap kitelepült véradás lesz a közelben 👇",
    ],
    "esti_idojaras": [
        "Megnéztem nektek, milyen időre ébredünk holnap:",
        "Mielőtt lefekszetek, itt a holnapi időjárás:",
        "Hogy holnap reggel ne érjen meglepetés, ilyen idő lesz:",
        "Esti kis időjárás-jelentés tőlem 🌙",
    ],
    "vallalkozas": [
        "Szeretem, ha a pénzünk a környéken marad, ezért ma egy helyi vállalkozást mutatok be:",
        "Ma egy olyan helyet mutatok, amit érdemes ismerni a környéken:",
        "Bemutatok nektek egy kerületi vállalkozást, hátha pont rájuk van szükségetek:",
        "Egy újabb helyi vállalkozó, akit szívesen bemutatok nektek:",
    ],
    "vallalkozas_velemeny": [
        "Most a ti tapasztalatotokra van szükségem:",
        "Gyűjtsük össze együtt a környék legjobbjait!",
        "Kíváncsi vagyok, kit ajánlanátok jó szívvel:",
        "Segítsünk egymásnak egy jó ajánlással:",
    ],
}

# (vastag vonal, vékony vonal, hossz) - a széles jeleknél rövidebb a vonal
VONALAK = [
    ("═", "─", 32),
    ("━", "┄", 32),
    ("▬", "‐", 20),
    ("◆", "◇", 16),
    ("•", "·", 24),
    ("〰", "〰", 14),
    ("✦", "·", 18),
    ("▪", "▫", 20),
    ("~", "~", 28),
]

TERULET_KERETEK = [
    "▸▸▸  {}  ◂◂◂",
    "【 {} 】",
    "📌 {}",
    "— {} —",
    "◉ {}",
    "🔹 {} 🔹",
]

ZAROK = [
    "💙 Oszd meg, hogy a szomszédaid is tudjanak róla!",
    "🙏 Köszönöm, hogy követtek!",
    "📲 Kapcsold be az értesítéseket, hogy ne maradj le semmiről!",
    "🏘️ Vigyázzatok magatokra és egymásra!",
    "💬 Ha tudsz valami újat, írd meg kommentben!",
    "",
]


class Stilus:
    """A mai arculat egy kategóriához, plusz egy véletlenszerű bevezető."""

    def __init__(self, kategoria, nap=None):
        self.kategoria = kategoria
        nap = nap or datetime.now(MAGYAR_TZ).strftime("%Y-%m-%d")
        # Minden elem kategóriánként és naponta más, egy napon belül fix.
        napi_kat = random.Random(f"{nap}|{kategoria}")
        # A vonal és a keret kategóriánként is más, hogy az egy napon belüli
        # posztok ne nézzenek ki egyformán.
        self._vastag, self._vekony, self._hossz = napi_kat.choice(VONALAK)
        self._terulet = napi_kat.choice(TERULET_KERETEK)
        self.cim = napi_kat.choice(CIMEK.get(kategoria, [""]))
        self.zaro = napi_kat.choice(ZAROK)
        self.bevezeto = random.choice(BEVEZETOK.get(kategoria, [""]))

    def vonal(self):
        return self._vastag * self._hossz

    def vekony(self):
        return self._vekony * self._hossz

    def terulet(self, nev):
        return self._terulet.format(nev)


# Elérhetőségek: minden poszt más formában és más felvezetéssel kéri, hogy
# írjanak nekem, így nem ugyanaz a blokk zárja az összes bejegyzést.
FELVEZETOK = [
    "Ha neked is van problémád a környéken, vagy bármilyen hírt, infót tudsz, írj nekem, és utánajárok:",
    "Neked is van egy gondod vagy egy híred a környékről? Szólj, és utánanézek:",
    "Ha te is tudsz valamit, ami a kerületet érinti, keress meg bátran:",
    "Bármilyen gond, hír vagy fotó a környékről jöhet, itt érsz el:",
    "Ha valami téged is zavar a környéken, írd meg, és foglalkozom vele:",
    "Van egy hasonló ügyed, vagy tudsz valamit, amiről írnom kéne? Itt elérsz:",
]


def kapcsolat_blokk(nap, kulcs, email, whatsapp, url="", felvezeto=None):
    """Elérhetőségek a poszt aljára, napi és posztonkénti változattal."""
    r = random.Random(f"{nap}|{kulcs}|kapcsolat")
    fel = FELVEZETOK[r.randrange(len(FELVEZETOK))] if felvezeto is None else felvezeto
    forma = r.randrange(4)
    if forma == 0:
        sorok = ["💬 Facebook-üzenetben (az oldal tetején az „Üzenetküldés” gombbal)"]
        if whatsapp:
            sorok.append(f"📱 WhatsApp-üzenetben: {whatsapp}")
        sorok.append(f"📩 e-mailben: {email}")
        if url:
            sorok.append(f"🌐 online, egy kattintással: {url}")
    elif forma == 1:
        sorok = [f"✉️ {email}"]
        if whatsapp:
            sorok.append(f"📲 WhatsApp: {whatsapp}")
        sorok.append("💬 vagy egyszerűen írj az oldalnak Messengeren")
        if url:
            sorok.append(f"👉 {url}")
    elif forma == 2:
        reszek = ["Messengeren"]
        if whatsapp:
            reszek.append(f"WhatsAppon ({whatsapp})")
        reszek.append(f"e-mailben ({email})")
        sorok = ["📬 " + ", ".join(reszek[:-1]) + " vagy " + reszek[-1] + "."]
        if url:
            sorok.append(f"Ha gyorsabb, itt egy kattintással is megírhatod: {url}")
    else:
        sorok = []
        if url:
            sorok.append(f"🖱️ Egy kattintás: {url}")
        if whatsapp:
            sorok.append(f"☎️ WhatsApp: {whatsapp}")
        sorok += [f"📧 E-mail: {email}", "💭 Messenger: az oldal „Üzenetküldés” gombja"]
    return ([fel] if fel else []) + sorok


ROVID_KAPCSOLAT = [
    "💬 Írj nekem Messengeren, WhatsAppon ({wa}) vagy az {email} címre.",
    "📬 Tudsz valamit erről? Írj nekem: {email}",
    "Ha van hozzá infód, szólj Messengeren vagy WhatsAppon ({wa}). 🙏",
    "✉️ Hírt, fotót, kérdést szívesen fogadok: {email}",
    "📲 Kérdésed van, vagy tudsz valamit? Írj: {url}",
]


def rovid_kapcsolat(nap, kulcs, email, whatsapp, url=""):
    """Egysoros elérhetőség a színes posztok aljára, posztonként más."""
    lehet = [m for m in ROVID_KAPCSOLAT if url or "{url}" not in m]
    m = random.Random(f"{nap}|{kulcs}|rovid").choice(lehet)
    return m.format(wa=whatsapp, email=email, url=url)


# ── Elrendezés ────────────────────────────────────────────────────────────
# Minden kész posztot küldés előtt egy véletlenszerű (a szövegből számolt,
# így újraküldésnél ugyanolyan) elrendezésre teszünk át, hogy ne egy
# kaptafára készüljön minden bejegyzés: hol a cím van elöl, hol egy
# személyes mondat, hol nincs elválasztó vonal, hol alul van, stb.

import hashlib as _hashlib
import re as _re

_BETU = _re.compile(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]")
_KERET_EMOJI = _re.compile(r"^(\W+?)\s+(.*?)(?:\s+(\W+))?$")


def _cimsor(sor):
    betuk = _BETU.findall(sor)
    return len(betuk) >= 4 and sum(b.isupper() for b in betuk) / len(betuk) > 0.7


def _vonal(sor):
    s = sor.strip()
    return len(s) >= 5 and not _BETU.search(s) and not any(c.isdigit() for c in s) and len(set(s)) <= 3


def _cim_valtozat(cim, r):
    m = _KERET_EMOJI.match(cim.strip())
    if not m:
        return cim
    elo, mag, hatul = m.group(1), m.group(2), m.group(3)
    valtozatok = [cim, f"{elo} {mag}", f"{mag} {elo}"]
    if hatul:
        valtozatok.append(f"{mag} {hatul}")
    return r.choice(valtozatok)


def atrendez(szoveg):
    """A kész poszt elrendezését változtatja meg, a tartalmát nem.
    Előtte a poszt-ellenőrző átnézi: hibás posztnál kivételt dob, és a küldés elmarad."""
    poszt_ellenor.ellenoriz(szoveg)
    if not szoveg:
        return szoveg
    r = random.Random(_hashlib.sha256(szoveg.encode("utf-8")).hexdigest())
    sorok = szoveg.split("\n")
    if not sorok or not _cimsor(sorok[0]):
        return szoveg
    cim = sorok[0]
    i = 1
    vonal = ""
    if i < len(sorok) and _vonal(sorok[i]):
        vonal = sorok[i].strip()
        i += 1
    # hashtagek a végéről
    j = len(sorok)
    while j > i and (not sorok[j - 1].strip() or sorok[j - 1].lstrip().startswith("#")):
        j -= 1
    tagek = [s for s in sorok[j:] if s.strip()]
    torzs = "\n".join(sorok[i:j]).strip("\n")
    bekezdesek = [b for b in torzs.split("\n\n") if b.strip()]
    if not bekezdesek:
        return szoveg
    cim = _cim_valtozat(cim, r)
    vonal = vonal or "━" * 20

    forma = r.randrange(6)
    if forma == 0:      # cím, vonal, szöveg (a megszokott)
        reszek = [cim + "\n" + vonal] + bekezdesek
    elif forma == 1:    # cím, szöveg, alul a vonal
        reszek = [cim] + bekezdesek + [vonal]
    elif forma == 2:    # vonal nélkül
        reszek = [cim] + bekezdesek
    elif (forma == 3 and len(bekezdesek) > 1 and "\n" not in bekezdesek[0]
          and len(bekezdesek[0]) < 300):   # személyes mondat elöl, utána a cím
        reszek = [bekezdesek[0], cim + "\n" + vonal] + bekezdesek[1:]
    elif forma == 4:    # a cím két vonal között
        reszek = [vonal + "\n" + cim + "\n" + vonal] + bekezdesek
    else:               # cím, szöveg, a hashtagek előtt vonal
        reszek = [cim, "\n\n".join(bekezdesek)]
        if tagek:
            tagek = [vonal] + tagek
    kimenet = "\n\n".join(reszek)
    if tagek:
        kimenet += "\n\n" + "\n".join(tagek)
    return kimenet
