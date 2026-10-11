import re, requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124", "Accept-Language": "hu"}
B = "https://www.ovsz.hu/sites/all/scripts/gps2020/"
print(requests.get(B + "gps.js", headers=H, timeout=30).text)
t = requests.get(B + "telepulesek.js", headers=H, timeout=30).text
print("TELEP HEAD", t[:600])
for m in re.finditer(r"[^\n]{0,150}(XXI|Csepel|Szigetszentmikl)[^\n]{0,150}", t):
    print("  T>", m.group(0))
