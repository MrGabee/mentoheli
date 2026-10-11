import re, requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124", "Accept-Language": "hu"}
r = requests.get("https://www.ovsz.hu/hu/ver/veradasok", headers=H, timeout=30)
t = r.text
print("STATUS", r.status_code, len(t))
print("FORMS", re.findall(r"<form[^>]*>", t)[:5])
print("INPUTS", sorted(set(re.findall(r'<(?:input|select)[^>]*name="([^"]+)"', t)))[:40])
print("SCRIPTS", re.findall(r'<script[^>]*src="([^"]+)"', t)[:20])
print("JSON-ish", re.findall(r'(https?://[^"\']*(?:api|json|ajax)[^"\']*)', t)[:10])
i = t.find("XXI")
print("XXI at", i)
for kw in ["Csepel", "XXI", "veradas-", "views-row", "<table", "datum", "időpont"]:
    print(kw, t.count(kw))
m = re.search(r"<main.*?</main>", t, re.S)
body = m.group(0) if m else t
body = re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>", "", body, flags=re.S)
print(body[:6000])
