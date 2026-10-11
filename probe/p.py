import re, subprocess, sys, requests
subprocess.run("git fetch -q origin claude/project-thread-oeicnh && git checkout -q FETCH_HEAD -- allasok.py poszt_valtozatos.py", shell=True, check=True)
sys.path.insert(0, ".")
from datetime import date
import allasok
print("### ALLAS MINTA\n" + str(allasok.heti_szoveg(date(2026, 10, 14), {})))
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept-Language": "hu-HU,hu;q=0.9", "Accept": "text/html,application/xhtml+xml"}
def clean(t): return re.sub(r"\n\s*\n+", "\n", re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>|<head.*?</head>", "", t, flags=re.S))
for nev, url in [("POSTA", "https://posta.hu/aktualitasok"),
                 ("KH", "https://kormanyhivatalok.hu/kormanyhivatalok/budapest/megye/hirek")]:
    try:
        r = requests.get(url, headers=H, timeout=30)
    except Exception as ex:
        print("###", nev, "HIBA", ex); continue
    t = r.text
    print("###", nev, r.status_code, len(t), r.url)
    print("API?", sorted(set(re.findall(r'["\'](/[^"\']*(?:api|json|ajax|graphql)[^"\']*)', t)))[:20])
    for h, x in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        x = " ".join(re.sub(r"<[^>]+>", " ", x).split())
        if len(x) > 25:
            print("  A", h, "|", x[:140])
    b = clean(t)
    i = max(b.find("Aktualit", 3000), 0) if nev == "POSTA" else max(b.find("hirek/"), 0)
    print("--- reszlet", re.sub(r"[ \t]+", " ", b[i:i+6000]))
