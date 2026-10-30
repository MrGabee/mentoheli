"""
🗓️ Közös posztütemező: ne menjen ki két bejegyzés egyszerre, és két poszt
között mindig teljen el elég idő.

Minden posztoló a közös poszt_naplo.json-ba írja (és azonnal feltölti) az
utolsó poszt idejét; posztolás előtt mindegyik a main legfrissebb naplóját
nézi meg. A színes posztok menetrendje a következő esedékes poszt idejét is
beírja, hogy a ráérős posztok ne kerüljenek közvetlenül elé.

- Sürgős poszt (élő üzemzavar, baleset, riasztás): ha az előző óta eltelt
  SURGOS_TAV, rögtön kimegy; ha nem, kivárja.
- Minden más poszt: csak ha az előző óta eltelt MIN_TAV, és a következő
  menetrendi posztig is van legalább MIN_TAV.
"""

import json
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MAGYAR_TZ = ZoneInfo("Europe/Budapest")
MIN_TAV = timedelta(minutes=20)
SURGOS_TAV = timedelta(minutes=10)
NAPLO = "poszt_naplo.json"

GIT = ["git", "-c", "user.name=github-actions[bot]",
       "-c", "user.email=github-actions[bot]@users.noreply.github.com"]


def most():
    return datetime.now(MAGYAR_TZ)


def _run(args, timeout=60):
    try:
        return subprocess.run(args, capture_output=True, timeout=timeout)
    except Exception:
        return None


def naplo():
    """A közös napló a main legfrissebb állapotából (ha nem érhető el, a helyiből)."""
    _run(["git", "fetch", "-q", "origin", "main"], 30)
    r = _run(["git", "show", f"origin/main:{NAPLO}"], 15)
    if r is not None and r.returncode == 0:
        try:
            return json.loads(r.stdout.decode("utf-8"))
        except Exception:
            pass
    try:
        with open(NAPLO, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ido(s):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def utolso_poszt():
    return _ido(naplo().get("utolso", ""))


def mehet(surgos=False):
    """Kimehet-e most egy poszt. Ha nem, kiírja, miért."""
    t = most()
    n = naplo()
    utolso = _ido(n.get("utolso", ""))
    tav = SURGOS_TAV if surgos else MIN_TAV
    if utolso and t - utolso < tav:
        print(f"  ⏳ Az előző poszt {utolso:%H:%M}-kor ment ki, ez a poszt "
              f"{(utolso + tav):%H:%M} után megy.")
        return False
    kov = _ido(n.get("kovetkezo_slot", ""))
    if not surgos and kov and timedelta(0) <= kov - t < MIN_TAV:
        print(f"  ⏳ {kov:%H:%M}-kor menetrendi poszt jön, ez a poszt utána megy.")
        return False
    return True


def _feltolt(adat, uzenet):
    """A naplót a main legfrissebb változatára írja és feltölti."""
    for _ in range(4):
        _run(["git", "fetch", "-q", "origin", "main"], 30)
        r = _run(["git", "show", f"origin/main:{NAPLO}"], 15)
        try:
            alap = json.loads(r.stdout.decode("utf-8")) if r is not None and r.returncode == 0 else {}
        except Exception:
            alap = {}
        alap.update(adat)
        # Csak a naplót commitoljuk, közvetlenül a main tetejére: a munkakönyvtárat
        # és a helyi ágat nem bolygatjuk, hogy a workflow saját commitja zavartalan legyen.
        try:
            blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], capture_output=True, timeout=15,
                                  input=json.dumps(alap, ensure_ascii=False, indent=2).encode("utf-8"))
        except Exception:
            blob = None
        if blob is None or blob.returncode != 0:
            return False
        sha = blob.stdout.decode().strip()
        idx = ["env", "GIT_INDEX_FILE=.git/poszt_naplo_index"]
        _run(idx + ["git", "read-tree", "origin/main"], 15)
        _run(idx + ["git", "update-index", "--add", "--cacheinfo", f"100644,{sha},{NAPLO}"], 15)
        fa = _run(idx + ["git", "write-tree"], 15)
        if fa is None or fa.returncode != 0:
            return False
        c = _run(GIT + ["commit-tree", fa.stdout.decode().strip(), "-p", "origin/main",
                        "-m", f"{uzenet} [skip ci]"], 15)
        if c is None or c.returncode != 0:
            return False
        p = _run(["git", "push", "-q", "origin", f"{c.stdout.decode().strip()}:refs/heads/main"], 60)
        if p is not None and p.returncode == 0:
            return True
    print("  ⚠️ A posztnaplót nem sikerült feltölteni.")
    return False


def jegyez(_allapot=None):
    """Feljegyzi, hogy most ment ki egy poszt (régi hívások kompatibilitásáért
    egy állapot-dictet is elfogad, de nem használja)."""
    _feltolt({"utolso": most().isoformat()}, "posztnapló")


def kovetkezo_slot_beallit(ido):
    ertek = ido.isoformat() if ido else ""
    if naplo().get("kovetkezo_slot", "") != ertek:
        _feltolt({"kovetkezo_slot": ertek}, "posztnapló: következő menetrendi poszt")


def raeros_mehet(_allapot=None):
    return mehet(surgos=False)
