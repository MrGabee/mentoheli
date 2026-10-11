import os, time, requests
u = os.environ["MAKE_WEBHOOK_URL"]
adat = {"message": "🧪 TESZT – ezt a posztot hamarosan törlöm.\n\nRendőrségi illusztráció próbája, a szövegben lévő link: "
                   "https://www.police.hu/hu/koral/elfogatoparancs-alapjan-korozott-szemelyek",
        "link": "https://raw.githubusercontent.com/MrGabee/mentoheli/main/kepek/rendorseg_korozes.png"}
t = time.time()
r = requests.post(u, json=adat, timeout=90)
print("->", r.status_code, repr(r.text[:200]), f"{time.time()-t:.1f}s")
