"""
📣 Napi felhívás: bárki, akinek a kerületet érintő problémája van, írjon nekem.
Minden nap megy ki, a bevezető naponta változik.
"""

import allasok
from poszt_valtozatos import Stilus, kapcsolat_blokk

OLVASOI_EMAIL = "olvaso@mrgabee.hu"
WHATSAPP_SZAM = "+36 70 754 0254"

CIMEK = [
    "📣 VAN EGY KERÜLETI GONDOD? ÍRJ NEKEM! 📣",
    "📣 SZÓLJ, HA VALAMI NEM STIMMEL A KÖRNYÉKEN! 📣",
    "📣 MI ZAVAR CSEPELEN? MONDD EL NEKEM! 📣",
    "📣 ÍRJ NEKEM, HA BAJ VAN A KÖRNYÉKEN! 📣",
]

BEVEZETOK = [
    "Kátyú, gyorshajtás, illegális szemét, kiégett lámpa, zajos szomszéd vagy bármi, ami a kerületünket érinti? "
    "Írd meg nekem, és ha kell, nyilvánosságot adok neki.",
    "Ha valami a kerületben hónapok óta nem oldódik meg, és úgy érzed, senki nem figyel rá, írj nekem. "
    "Minden üzenetet elolvasok.",
    "Sokszor egy bejegyzés többet ér, mint tíz bejelentés. Ha van egy problémád, ami a kerületünket érinti, "
    "küldd el nekem, és utánajárok.",
    "Közlekedés, közbiztonság, tisztaság, játszótér, bármi, ami a környékünket érinti: ha gond van vele, "
    "írj nekem bátran.",
    "Nem kell nagy dolognak lennie. Ha valami zavar a kerületben, vagy veszélyesnek látod, szólj, "
    "és együtt felhívjuk rá a figyelmet.",
    "Ha fotód is van a problémáról, azt is szívesen fogadom. Írd meg, hol és mi a gond, "
    "és foglalkozom vele.",
    "A ti jelzéseitekből sokat tanulok a kerületről. Ha van valami, ami a környékünket érinti, írj nekem.",
]


ZAROK = [
    "Nemcsak gondot, bármilyen kerületi hírt, infót, fotót is szívesen fogadok. Ha szeretnéd, a neved nélkül teszem közzé. 🙏",
    "Névtelenül is írhatsz, a neved nélkül adom tovább. 🤝",
    "Jó hírnek, fotónak, tippnek is örülök, nem csak panasznak. 😊",
    "Minden üzenetet elolvasok, és ha kéred, név nélkül teszem közzé.",
    "Ha van fotód, küldd azt is, sokat segít. 📸",
]


def szoveg(nap):
    n = nap.toordinal()
    return "\n".join([
        CIMEK[n % len(CIMEK)],
        Stilus("kerulet_problema", nap.isoformat()).vonal(),
        "",
        BEVEZETOK[n % len(BEVEZETOK)],
        "",
        *kapcsolat_blokk(nap, "kerulet_problema", OLVASOI_EMAIL, WHATSAPP_SZAM,
                         allasok.KAPCSOLAT_URL, felvezeto=""),
        "",
        ZAROK[(n * 3) % len(ZAROK)],
        "#Csepel #XXIkerület #olvasóijelzés",
    ])
