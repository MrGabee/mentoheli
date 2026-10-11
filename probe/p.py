import os, time, requests
from urllib.parse import quote
oldal = "https://mrgabee.github.io/mentoheli/rendorseg/"
for i in range(36):
    r = requests.get(oldal, timeout=20)
    if r.status_code == 200 and "og:image" in r.text:
        print("oldal kész", i * 5, "mp")
        break
    time.sleep(5)
else:
    raise SystemExit("az oldal nem jelent meg")
police = "https://www.police.hu/hu/koral/elfogatoparancs-alapjan-korozott-szemelyek"
adat = {"message": "🧪 TESZT 2 – ezt a posztot is hamarosan törlöm.\n\nRendőrségi illusztráció próbája, a hivatalos link: " + police,
        "link": oldal + "?u=" + quote(police, safe="")}
r = requests.post(os.environ["MAKE_WEBHOOK_URL"], json=adat, timeout=90)
print("->", r.status_code, repr(r.text[:200]))
