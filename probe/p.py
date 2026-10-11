import sys, re, collections
sys.path.insert(0, ".")
sys.argv = ["x"]
from korozes import police_figyelo as pf
import time
# 1) körözések: utolsó elemek szervei
for kulcs in ["eltunt_szemelyek", "korozott_szemelyek", "jarmu_korozes"]:
    kat = pf.KOROZES_KATEGORIAK[kulcs]
    lista = pf.korozes_lista_lekerdezese(kat["list_path"])
    print("==", kulcs, len(lista), "elem a listán")
    szervek = collections.Counter()
    for e in lista[:25]:
        r = pf.korozes_reszlet_lekerdezese(e["url"])
        sz = [v for k, v in r["mezok"].items() if "szerv" in k.lower()]
        szervek[" | ".join(sz)[:90]] += 1
        if pf.korozes_szerv_egyezik(r["mezok"]): print("  TALÁLAT", r["cim"], sz)
        time.sleep(0.2)
    for s, n in szervek.most_common(30): print("  ", n, s)
    if lista: print("  mezők:", list(r["mezok"])[:15])
# 2) hírek: tágabb minta
TAG = re.compile(r"csepel|pesterzsébet|soroksár|szigetszentmikl|XX\.?\s*(KER|kerület)|XXI\.?\s*(KER|kerület)|XXIII\.?\s*(KER|kerület)|halásztelek|tököl|szigethalom", re.I)
for kulcs, kat in pf.HIREK_KATEGORIAK.items():
    for page in ["", "?page=1", "?page=2"]:
        try:
            import requests
            from bs4 import BeautifulSoup
            resp = requests.get(pf.BASE_URL + kat["list_path"] + page, headers=pf.HEADERS, timeout=20)
            cikkek = pf._hirek_tartalek(BeautifulSoup(resp.text, "html.parser"))
        except Exception as ex:
            print(kulcs, ex); continue
        for c in cikkek:
            t = c["cim"] + " " + c["osszefoglalo"]
            regi, uj = pf.hirek_egyezik(c), bool(TAG.search(t))
            if regi or uj: print("HÍR", kulcs, page, "régi" if regi else "", "új" if uj else "", c["cim"][:100], c["url"])
    print("--", kulcs, "kész; példa:", (cikkek[0]["cim"][:80], cikkek[0]["osszefoglalo"][:80]) if cikkek else None)
