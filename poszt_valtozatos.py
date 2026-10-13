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
        "💼 HETI ÁLLÁSAJÁNLÓ 💼",
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
        "Összegyűjtöttem a héten megjelent csepeli álláshirdetéseket 👇",
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
}

# (vastag vonal, vékony vonal, hossz) - a széles jeleknél rövidebb a vonal
VONALAK = [
    ("═", "─", 32),
    ("━", "┄", 32),
    ("▬", "‐", 20),
    ("◆", "◇", 16),
    ("•", "·", 24),
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
        # A közös elemek (vonal, keret) napi szinten minden posztnál egyformák,
        # a címsor és a záró mondat kategóriánként is napi szinten fix.
        napi = random.Random(nap)
        napi_kat = random.Random(f"{nap}|{kategoria}")
        self._vastag, self._vekony, self._hossz = napi.choice(VONALAK)
        self._terulet = napi.choice(TERULET_KERETEK)
        self.cim = napi_kat.choice(CIMEK.get(kategoria, [""]))
        self.zaro = napi_kat.choice(ZAROK)
        self.bevezeto = random.choice(BEVEZETOK.get(kategoria, [""]))

    def vonal(self):
        return self._vastag * self._hossz

    def vekony(self):
        return self._vekony * self._hossz

    def terulet(self, nev):
        return self._terulet.format(nev)
