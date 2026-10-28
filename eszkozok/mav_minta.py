# Ideiglenes: a MÁVINFORM cikkoldal vizsgálata (nem küld e-mailt).
import re
import requests
from bs4 import BeautifulSoup
import mav_monitor as m

for e in m.lekerdez_lista():
    if m.esemeny_tipus(e["url"], e["cim"], "") is None:
        continue
    print("URL:", e["url"])
    r = requests.get(e["url"], headers=m.HEADERS, timeout=15)
    print("HTTP:", r.status_code, "hossz:", len(r.text), "végső url:", r.url)
    print("FEJ:", r.text[:600].replace("\n", " "))
    soup = BeautifulSoup(r.text, "html.parser")
    osztalyok = sorted({c for t in soup.find_all(True) for c in (t.get("class") or [])})
    print("OSZTALYOK:", " ".join(osztalyok)[:3000])
    for t in soup.find_all(["p", "div"]):
        s = t.get_text(" ", strip=True)
        if 80 < len(s) < 800 and "süti" not in s.lower():
            print("SZOVEG <", t.name, t.get("class"), ">:", s[:400])
    print("DATUMOK:", re.findall(r"\d{4}\.\s?\d{2}\.\s?\d{2}\.?\s*\d{1,2}:\d{2}", soup.get_text(" "))[:10])
    break
