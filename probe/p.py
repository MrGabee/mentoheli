import sys, re, requests
sys.path.insert(0, ".")
from korozes import police_figyelo as pf
from bs4 import BeautifulSoup
for kulcs in ["eltunt_szemelyek", "korozott_szemelyek", "jarmu_korozes"]:
    l = pf.korozes_lista_lekerdezese(pf.KOROZES_KATEGORIAK[kulcs]["list_path"])
    e = l[0]
    r = requests.get(e["url"], headers=pf.HEADERS, timeout=20)
    print("=====", kulcs, e, r.status_code, len(r.text))
    s = BeautifulSoup(r.text, "html.parser")
    for t in s(["script", "style", "nav", "header", "footer"]): t.decompose()
    main = s.find("main") or s.body
    txt = re.sub(r"\n\s*\n+", "\n", main.get_text("\n", strip=True))
    i = txt.find("szerv")
    print(txt[:2500])
    print("..SZERV..", txt[max(0,i-800):i+400] if i >= 0 else "NINCS 'szerv'")
    m = re.search(r"szerv", r.text, re.I)
    if m: print("RAW", r.text[m.start()-600:m.start()+400])
# hírlista szerkezete
r = requests.get(pf.BASE_URL + pf.HIREK_KATEGORIAK["felhivasok"]["list_path"], headers=pf.HEADERS, timeout=20)
i = r.text.find("/felhivasok/")
i = r.text.find("/felhivasok/", i + 1)
print("=====HÍRLISTA RAW", r.text[i-1500:i+1500])
