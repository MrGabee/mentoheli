import sys, re, requests
sys.path.insert(0, "probe")
import kf
H = kf.HEADERS
r = requests.get("https://www.fedakszinhaz.hu/", headers=H, timeout=25)
print("home", r.status_code, len(r.text))
for href, txt in sorted(set(re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S))):
    if "fedakszinhaz" in href or href.startswith("/"):
        print("LINK", href, kf._szoveg(txt)[:60])
print("HOME parse:", kf.fedak_feldolgoz(r.text)[:20])
for u in ["https://www.fedakszinhaz.hu/aktualis-jatekterv/", "https://www.fedakszinhaz.hu/jatekterv/", "https://www.fedakszinhaz.hu/eloadasok/", "https://www.fedakszinhaz.hu/musor/"]:
    try:
        x = requests.get(u, headers=H, timeout=25)
        print(u, x.status_code, len(x.text), kf.fedak_feldolgoz(x.text)[:20] if x.status_code == 200 else "")
    except Exception as e:
        print(u, e)
