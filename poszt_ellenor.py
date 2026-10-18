"""
🛡️ Poszt-ellenőrző – minden Facebook-poszt utolsó szűrője
A poszt_valtozatos.atrendez() hívja meg, amin minden kimenő poszt átmegy.
Ha a szöveg hibaüzenetnek, programkódnak, belső címnek vagy titoknak tűnik,
a küldés elmarad (HibasPoszt kivétel), és a naplóban látszik, miért.
"""

import re


class HibasPoszt(ValueError):
    pass


# (minta, magyarázat) – a minta kis- és nagybetűre nem érzékeny
TILTOTT = [
    (r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)", "belső (localhost) cím"),
    (r"Bridge returned error|RssBridge|HttpException", "RSS-Bridge hibaüzenet"),
    (r"Traceback \(most recent call last\)|File \"[^\"]+\.py\", line \d+", "Python hibaüzenet"),
    (r"\.php(\(\d+\)|:\d+| line \d+)|Stack trace|Fatal error|Uncaught ", "PHP hibaüzenet"),
    (r"\b\w*(Exception|Error):\s", "hibaüzenet"),
    (r"developer\.mozilla\.org", "hibaoldal-hivatkozás"),
    (r"</?(html|head|body|div|span|script|p|br)\b[^>]*>", "HTML-kód"),
    (r"\{[a-z_]+\}|\{\{|\}\}", "kitöltetlen sablonmező"),
    (r"(^|\s)(None|null|undefined|NaN)(\s|$|[.,;])", "üres programérték"),
    (r"hook\.(eu|us)\d*\.make\.com|api[_-]?key|access_token|token=", "titok vagy webhook-cím"),
    (r"mrgabee\.github\.io/mentoheli|github\.com/mrgabee/mentoheli", "a rejtett repó címe"),
]

MIN_HOSSZ = 30


def hibak(szoveg):
    """A poszt problémáinak listája (üres lista = mehet)."""
    if not szoveg or len(szoveg.strip()) < MIN_HOSSZ:
        return ["üres vagy túl rövid poszt"]
    talalt = []
    for minta, ok in TILTOTT:
        m = re.search(minta, szoveg, re.I | re.M)
        if m:
            talalt.append(f"{ok}: „{m.group(0).strip()[:60]}”")
    return talalt


def ellenoriz(szoveg):
    """Kivételt dob, ha a poszt nem mehet ki."""
    h = hibak(szoveg)
    if h:
        print("  🛡️ A poszt-ellenőrző megállította a posztot:")
        for x in h:
            print(f"     – {x}")
        raise HibasPoszt("; ".join(h))
    return szoveg
