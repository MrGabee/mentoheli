"""
💡 Ötletkérő poszt: mit látnának szívesen az olvasók az oldalakon.
A NAPOK-ban felsorolt napokon megy ki (a színes posztok menetrendjében).
"""

from datetime import date

from poszt_valtozatos import Stilus, kapcsolat_blokk

# Ezeken a napokon megy ki
NAPOK = {date(2026, 10, 15)}

OLVASOI_EMAIL = "olvaso@mrgabee.hu"
# Ha üres, a WhatsApp-sor szám nélkül marad ki a posztból
WHATSAPP_SZAM = "+36 70 754 0254"


def szoveg(nap):
    if nap not in NAPOK:
        return ""
    sorok = [
        "💡 MIT LÁTNÁL SZÍVESEN AZ OLDALAIMON? 💡",
        Stilus("otlet_keres", nap.isoformat()).vonal(),
        "",
        "Szeretném, ha az oldalaim még inkább rólatok és nektek szólnának. "
        "Milyen témáról olvasnál szívesen? Van egy ötleted, amit érdemes lenne megmutatnom, "
        "vagy valami, ami szerinted hiányzik?",
        "",
    ]
    if nap == date(2026, 10, 15):
        sorok += ["📌 Egy fontos dolog: a tegnapi állásos bejegyzésembe kicsit hiba csúszott, ezért ma délután "
                  "új bejegyzéssel jövök, amibe a kommentekben érkezett hirdetéseket is beleraktam.", ""]
    sorok += [
        *kapcsolat_blokk(nap, "otlet_keres", OLVASOI_EMAIL, WHATSAPP_SZAM, felvezeto="Írd meg bátran:"),
        "",
        "Minden üzenetet elolvasok, köszönöm, hogy segítesz! 🙏",
        "#Csepel #ötlet",
    ]
    return "\n".join(sorok)
