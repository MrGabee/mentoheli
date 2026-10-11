import re, subprocess, sys, signal, functools, requests
print = functools.partial(print, flush=True)
class Lejart(Exception): pass
def _alarm(*_): raise Lejart()
signal.signal(signal.SIGALRM, _alarm)
def get(url, **kw):
    signal.alarm(40)
    try:
        return requests.get(url, headers=H, timeout=20, **kw)
    finally:
        signal.alarm(0)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept-Language": "hu-HU,hu;q=0.9", "Accept": "text/html,application/xhtml+xml"}
print("git fetch...")
subprocess.run("timeout 60 git fetch -q origin claude/project-thread-oeicnh && git checkout -q FETCH_HEAD -- allasok.py poszt_valtozatos.py", shell=True, check=True)
sys.path.insert(0, ".")
from datetime import date
import allasok
allasok.requests.get = lambda url, headers=None, timeout=None: get(url)
try:
    print("### ALLAS MINTA\n" + str(allasok.heti_szoveg(date(2026, 10, 14), {})))
except Exception as ex:
    print("### ALLAS HIBA", repr(ex))
def clean(t): return re.sub(r"\n\s*\n+", "\n", re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>|<head.*?</head>", "", t, flags=re.S))
for nev, url in [("POSTA", "https://posta.hu/aktualitasok"),
                 ("KH", "https://kormanyhivatalok.hu/kormanyhivatalok/budapest/megye/hirek"),
                 ("KULTIK", "https://kultik.hu/musor"),
                 ("PORT", "https://port.hu/helyszin/mozi/kultik-csepel/place-7912")]:
    print("###", nev, "lekeres...")
    try:
        r = get(url)
    except BaseException as ex:
        print("###", nev, "HIBA", repr(ex)); continue
    t = r.text
    print("###", nev, r.status_code, len(t), r.url)
    print("API?", sorted(set(re.findall(r'["\'](/[^"\']*(?:api|json|ajax|graphql)[^"\']*)', t)))[:20])
    n = 0
    for h, x in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        x = " ".join(re.sub(r"<[^>]+>", " ", x).split())
        if len(x) > 20 and n < 60:
            n += 1
            print("  A", h, "|", x[:140])
    b = re.sub(r"[ \t]+", " ", clean(t))
    i = len(b) // 4
    print("--- reszlet", b[i:i+4000])
