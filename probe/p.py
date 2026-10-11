import sys, re, collections, time, requests
sys.path.insert(0, ".")
sys.path.insert(0, "probe")
import pf_uj as pf
from bs4 import BeautifulSoup
for kulcs in ["eltunt_szemelyek", "korozott_szemelyek", "jarmu_korozes"]:
    kat = pf.KOROZES_KATEGORIAK[kulcs]
    lista = pf.korozes_lista_lekerdezese(kat["list_path"])
    szervek = collections.Counter()
    minta = None
    for e in lista[:18]:
        r = pf.korozes_reszlet_lekerdezese(e["url"])
        sz = [v for k, v in r["mezok"].items() if "szerv" in k.lower() and "értesítési" not in k.lower()]
        szervek[" | ".join(sz)[:80]] += 1
        egy = pf.korozes_szerv_egyezik(r["mezok"])
        if egy: print("  TALÁLAT", kulcs, r["cim"] if kulcs != "korozott_szemelyek" else "(név rejtve)", egy)
        minta = minta or (r, e)
        time.sleep(0.2)
    print("==", kulcs, dict(szervek.most_common(8)))
    r, e = minta
    print("-- MINTA (szűrő nélkül, BUDAPESTI XXI. KER. RK-nak tettetve):")
    print(pf.korozes_poszt_szoveg(kulcs, kat, r, "BUDAPESTI XXI. KER. RK", e["url"]))
    print("-- LEZÁRT:"); print(pf.lezart_poszt_szoveg(kulcs)); print()
for kulcs, kat in pf.HIREK_KATEGORIAK.items():
    for page in ["", "?page=1"]:
        resp = requests.get(pf.BASE_URL + kat["list_path"] + page, headers=pf.HEADERS, timeout=20)
        cikkek = pf._hirek_foszelektor(BeautifulSoup(resp.text, "html.parser"))
        if page == "": print("--", kulcs, len(cikkek), "cikk; első:", cikkek[0] if cikkek else None)
        for c in cikkek:
            if pf.hirek_egyezik(c): print("HÍR-TALÁLAT", kulcs, page, c["cim"], "|", c["osszefoglalo"][:100])
