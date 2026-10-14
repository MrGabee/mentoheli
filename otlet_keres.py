"""
💡 Ötletkérő poszt: mit látnának szívesen az olvasók az oldalakon.
A NAPOK-ban felsorolt napokon megy ki (a színes posztok menetrendjében).
"""

from datetime import date

# Ezeken a napokon megy ki
NAPOK = {date(2026, 10, 15)}

OLVASOI_EMAIL = "olvaso@mrgabee.hu"
# Ha üres, a WhatsApp-sor szám nélkül marad ki a posztból
WHATSAPP_SZAM = ""


def szoveg(nap):
    if nap not in NAPOK:
        return ""
    sorok = [
        "💡 MIT LÁTNÁL SZÍVESEN AZ OLDALAIMON? 💡",
        "••••••••••••••••••••••••",
        "",
        "Szeretném, ha az oldalaim még inkább rólatok és nektek szólnának. "
        "Milyen témáról olvasnál szívesen? Van egy ötleted, amit érdemes lenne megmutatnom, "
        "vagy valami, ami szerinted hiányzik?",
        "",
        "Írd meg bátran:",
        "💬 Facebook-üzenetben az oldalnak",
    ]
    if WHATSAPP_SZAM:
        sorok.append(f"📱 WhatsApp-üzenetben: {WHATSAPP_SZAM}")
    sorok += [
        f"📩 e-mailben: {OLVASOI_EMAIL}",
        "",
        "Minden üzenetet elolvasok, köszönöm, hogy segítesz! 🙏",
        "#Csepel #ötlet",
    ]
    return "\n".join(sorok)
