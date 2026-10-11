import re, requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept-Language": "hu-HU,hu;q=0.9", "Accept": "text/html,application/xhtml+xml"}
def clean(t): return re.sub(r"\n\s*\n+", "\n", re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>", "", t, flags=re.S))
t = requests.get("https://allas.csepel.hu/", headers=H, timeout=30).text
i = t.find("profession.hu/allas/")
print("### CSEPEL", clean(t[max(0, i-2500):i+2500]))
t = requests.get("https://varosgazda.eu/2026/09/17/allaslehetosegek/", headers=H, timeout=30).text
m = re.search(r'<div class="entry-content.*?</article>', t, re.S) or re.search(r"<article.*?</article>", t, re.S)
print("### VAROSGAZDA", re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", " ", clean(m.group(0) if m else t[:5000])))[:3000])
t = requests.get("https://www.profession.hu/allasok/budapest/1,0,23,csepel", headers=H, timeout=30).text
i = t.find("kiszallito-csepel-lang")
print("### PROFESSION", clean(t[max(0, i-3000):i+3500]))
ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S)
print("### PROF LD", [x[:600] for x in ld])
t = requests.get("https://posta.hu/aktualitasok", headers=H, timeout=30)
print("### POSTA", t.status_code, len(t.text), t.url)
tt = t.text
print(re.findall(r"<title>(.*?)</title>", tt, re.S)[:1], "NEXT", tt.count("__NEXT_DATA__"), "json", re.findall(r'(/[^"\']*(?:api|json)[^"\']*)', tt)[:10])
for h, x in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', tt, re.S)[:400]:
    x = " ".join(re.sub(r"<[^>]+>", " ", x).split())
    if "aktualit" in h and len(x) > 10:
        print("  P", h, "|", x[:120])
