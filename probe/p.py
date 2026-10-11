import sys, re, json, requests
sys.path.insert(0, ".")
from korozes import police_figyelo as pf
from bs4 import BeautifulSoup
d = json.load(open("korozes/data/police_figyelo.json"))
for kulcs in ["eltunt_szemelyek", "jarmu_korozes", "korozott_szemelyek"]:
    path = pf.KOROZES_KATEGORIAK[kulcs]["list_path"]
    ids = d["korozes"][kulcs]
    for i in [ids[0], ids[5], ids[len(ids)//3], ids[-30]]:
        r = requests.get(pf.BASE_URL + path + "/" + i, headers=pf.HEADERS, timeout=20, allow_redirects=False)
        s = BeautifulSoup(r.text, "html.parser")
        print(kulcs, i, r.status_code, r.headers.get("location"), len(r.text), "Név:" in r.text, "elrendelő szerv" in r.text, (s.title.string if s.title else "")[:80])
# kép a friss eltűnt adatlapon
l = pf.korozes_lista_lekerdezese(pf.KOROZES_KATEGORIAK["eltunt_szemelyek"]["list_path"])
r = requests.get(l[0]["url"], headers=pf.HEADERS, timeout=20)
for m in re.finditer(r'<img[^>]+>', r.text):
    if "koral" in m.group(0).lower() or "kep" in m.group(0).lower() or "photo" in m.group(0).lower(): print("IMG", m.group(0)[:300])
print("OG", re.findall(r'<meta property="og:[^>]+>', r.text)[:6])
