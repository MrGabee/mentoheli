import re, requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124", "Accept-Language": "hu"}
B = "https://www.ovsz.hu"
t = requests.get(B + "/hu/ver/veradasok", headers=H, timeout=30).text
srcs = [s for s in re.findall(r'<script[^>]*src="([^"]+)"', t) if "gps2020" in s or "ovsz" in s and "modules" not in s]
print("GPS SCRIPTS", srcs)
for s in re.findall(r"<script[^>]*>(.*?)</script>", t, re.S):
    if any(k in s for k in ["esemeny", ".php", "ajax", "helyseg", "radius", "json"]):
        print("INLINE>>>", s[:3000])
for s in srcs:
    u = s if s.startswith("http") else B + s
    c = requests.get(u, headers=H, timeout=30).text
    print("=====", u, len(c))
    for m in re.finditer(r"[^\n]{0,200}(\.php|ajax|getJSON|\$\.post|\$\.get|fetch\()[^\n]{0,300}", c):
        print("  ..", m.group(0)[:500])
