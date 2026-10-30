"""
🗓️ Közös posztütemező: ne menjen ki két bejegyzés egyszerre.

Minden posztoló szkript a saját állapotfájljába írja az utolsó posztja
idejét ("utolso_poszt"), innen olvassa ki mindegyik, mikor ment ki legutóbb
bármi az oldalra. A színes posztok menetrendje a következő esedékes poszt
idejét is beírja ("kovetkezo_slot"), hogy a ráérős posztok ne kerüljenek
közvetlenül elé.

- Azonnali (sürgős) poszt: rögtön kimegy, utána a többi MIN_TAV percet vár.
- Ráérős (előre bejelentett, megosztás): csak akkor megy ki, ha az előző
  poszt óta és a következő menetrendi posztig is van legalább MIN_TAV perc.
"""

import json
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MAGYAR_TZ = ZoneInfo("Europe/Budapest")
MIN_TAV = timedelta(minutes=20)
KULCS = "utolso_poszt"
ALLAPOT_FAJLOK = [
    "szines_allapot.json", "aramszunet_allapot.json", "fotav_allapot.json",
    "vizmuvek_allapot.json", "fb_oldal_allapot.json",
]
SZINES = "szines_allapot.json"


def most():
    return datetime.now(MAGYAR_TZ)


def _friss_main():
    """A többi workflow közben commitolhatott: a main legfrissebb állapotát nézzük."""
    try:
        subprocess.run(["git", "fetch", "-q", "origin", "main"], timeout=20, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def _beolvas(fajl, frissit):
    if frissit:
        try:
            r = subprocess.run(["git", "show", f"origin/main:{fajl}"], capture_output=True, timeout=10)
            if r.returncode == 0:
                return json.loads(r.stdout.decode("utf-8"))
        except Exception:
            pass
    try:
        with open(fajl, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ido(s):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def utolso_poszt(sajat=None, kiveve=None):
    """A legutóbbi poszt ideje az összes posztoló szkriptből (kiveve: ezt a fájlt kihagyja)."""
    frissit = _friss_main()
    idok = [_ido(_beolvas(f, frissit).get(KULCS, "")) for f in ALLAPOT_FAJLOK if f != kiveve]
    if sajat:
        idok.append(_ido(sajat.get(KULCS, "")))
    idok = [t for t in idok if t]
    return max(idok) if idok else None


def kovetkezo_menetrendi():
    t = _ido(_beolvas(SZINES, True).get("kovetkezo_slot", ""))
    return t


def raeros_mehet(sajat=None):
    """Ráérős poszt most kimehet-e."""
    t = most()
    utolso = utolso_poszt(sajat)
    if utolso and t - utolso < MIN_TAV:
        print(f"  ⏳ Az előző poszt {utolso:%H:%M}-kor ment ki, a ráérős poszt még vár.")
        return False
    kov = kovetkezo_menetrendi()
    if kov and timedelta(0) <= kov - t < MIN_TAV:
        print(f"  ⏳ {kov:%H:%M}-kor menetrendi poszt jön, a ráérős poszt utána megy.")
        return False
    return True


def jegyez(allapot):
    allapot[KULCS] = most().isoformat()


def allapot_feltoltes(fajl, uzenet):
    """Hosszan futó szkriptnél a poszt után rögtön feltölti az állapotot, hogy a
    többi figyelő azonnal lássa (a futás végi commit is megmarad)."""
    git = ["git", "-c", "user.name=github-actions[bot]",
           "-c", "user.email=github-actions[bot]@users.noreply.github.com"]
    try:
        subprocess.run(git + ["add", fajl], check=False, timeout=20)
        subprocess.run(git + ["commit", "-q", "-m", f"{uzenet} [skip ci]", "--", fajl], check=False, timeout=20)
        for _ in range(3):
            subprocess.run(git + ["pull", "-q", "--rebase", "-X", "theirs", "origin", "main"], check=False, timeout=60)
            if subprocess.run(git + ["push", "-q", "origin", "HEAD:main"], check=False, timeout=60).returncode == 0:
                return True
        return False
    except Exception as ex:
        print(f"  ⚠️ Állapot feltöltése nem sikerült: {ex}")
        return False
