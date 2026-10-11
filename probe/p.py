import os, time, requests
from urllib.parse import quote
oldal = "https://kozles.github.io/posztol/"
for i in range(48):
    r = requests.get(oldal, timeout=20)
    k = requests.get(oldal + "kepek/korozes_v2.png", timeout=20)
    if r.status_code == 200 and "og:image" in r.text and k.status_code == 200:
        print("oldal kész", i * 5, "mp")
        break
    time.sleep(5)
else:
    raise SystemExit(f"az oldal nem jelent meg: {r.status_code} {k.status_code}")
police = "https://www.police.hu/hu/koral/eltunt-szemelyek"
adat = {"message": "🧪 TESZT 4 – ezt a posztot is hamarosan törlöm.\n\nRendőrségi illusztráció próbája, a hivatalos link: " + police,
        "link": oldal + "?u=" + quote(police, safe="")}
r = requests.post(os.environ["MAKE_WEBHOOK_URL"], json=adat, timeout=90)
print("->", r.status_code, repr(r.text[:200]))
