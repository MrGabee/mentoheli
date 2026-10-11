import re, subprocess, sys, signal, functools, requests
print = functools.partial(print, flush=True)
class Lejart(Exception): pass
def _alarm(*_): raise Lejart()
signal.signal(signal.SIGALRM, _alarm)
_eredeti = requests.get
def get(url, **kw):
    signal.alarm(40)
    try:
        return _eredeti(url, headers=H, timeout=20, **kw)
    finally:
        signal.alarm(0)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept-Language": "hu-HU,hu;q=0.9", "Accept": "text/html,application/xhtml+xml"}
sys.path.insert(0, "probe")
from datetime import date
import allasok
def clean(t): return re.sub(r"\n\s*\n+", "\n", re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>|<head.*?</head>", "", t, flags=re.S))
# VAROSGAZDA
t = get("https://varosgazda.eu/").text
print("### VG links", sorted(set(re.findall(r'href="(https?://varosgazda\.eu/[^"]*(?:allas|karrier)[^"]*)"', t)))[:20])
for u in ["https://varosgazda.eu/karrier/"] + sorted(set(re.findall(r'href="(https?://varosgazda\.eu/\d{4}/\d{2}/\d{2}/[^"]*allas[^"]*)"', t)))[:3]:
    r = get(u); x = re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", " ", clean(r.text)))
    i = x.find("//")
    print("### VG", u, r.status_code, x[max(0,i-1500):i+1500])
# POSTA
t = get("https://posta.hu/aktualitasok").text
print("### POSTA scripts", re.findall(r'<script[^>]+src="([^"]+)"', t)[:30])
print("### POSTA iframes", re.findall(r'<iframe[^>]+src="([^"]+)"', t))
for k in ["aktualit", "hirek", "news", "fetch(", "$.ajax", "$.get", "data-url", "data-src"]:
    for m in list(re.finditer(re.escape(k), t))[:6]:
        print("  POSTA", k, "|", t[max(0,m.start()-200):m.start()+250].replace("\n"," "))
# PORT
t = get("https://port.hu/helyszin/mozi/kultik-csepel/place-7912").text
i = t.find("event-list")
print("### PORT", t[max(0,i-6000):i+3000])
