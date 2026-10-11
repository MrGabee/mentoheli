"""
🎨 Változatos Facebook-posztok
Minden poszt keretét (címsor, elválasztó vonalak, területcímkék, záró
mondat) véletlenszerűen választja ki, hogy a posztok ne nézzenek ki
mindig ugyanúgy. A tartalom (címek, időpontok, linkek) nem változik.
Új változatot a listák bővítésével lehet hozzáadni.
"""

import random

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
    "reggeli": [
        "☀️ JÓ REGGELT, CSEPEL, PESTERZSÉBET, SZIGETSZENTMIKLÓS! ☀️",
        "🌅 REGGELI KÖRKÉP A KÖRNYÉKRŐL 🌅",
        "☕ KÁVÉ MELLÉ: EZ VÁR MA RÁNK ☕",
        "🗞️ NAPINDÍTÓ – MAI HELYZET 🗞️",
        "🌞 SZÉP NAPOT! ÍGY KEZDŐDIK A MAI NAP 🌞",
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
    "🙏 Köszönjük, hogy követtek minket!",
    "📲 Kapcsold be az értesítéseket, hogy ne maradj le semmiről!",
    "🏘️ Vigyázzunk egymásra a környéken!",
    "💬 Ha tudsz valami újat, írd meg kommentben!",
    "",
]


class Stilus:
    """Egy poszton belül egységes, posztonként véletlenszerű stílus."""

    def __init__(self, kategoria):
        self.kategoria = kategoria
        self.cim = random.choice(CIMEK.get(kategoria, [""]))
        self._vastag, self._vekony, self._hossz = random.choice(VONALAK)
        self._terulet = random.choice(TERULET_KERETEK)
        self.zaro = random.choice(ZAROK)

    def vonal(self):
        return self._vastag * self._hossz

    def vekony(self):
        return self._vekony * self._hossz

    def terulet(self, nev):
        return self._terulet.format(nev)
