import requests, re
from bs4 import BeautifulSoup
H={"User-Agent":"Mozilla/5.0"}
def show(url, maxlinks=150):
    r=requests.get(url,headers=H,timeout=30)
    print("=====",url,r.status_code,len(r.text))
    s=BeautifulSoup(r.text,"html.parser")
    for t in s(["script","style","noscript"]): t.decompose()
    main=s.find("main") or s.body
    txt=re.sub(r"\n\s*\n+","\n",main.get_text("\n",strip=True))
    print(txt[:6000])
    print("--- links")
    seen=set()
    for a in main.find_all("a",href=True):
        h=a["href"]
        if "tiesz.hu" in h or h.startswith("/"):
            k=(a.get_text(" ",strip=True)[:70],h)
            if k not in seen:
                seen.add(k); print(k)
        if len(seen)>maxlinks: break
    return s
show("https://tiesz.hu/")
show("https://tiesz.hu/allasajanlatok/")
s=show("https://tiesz.hu/szakrendelesek/")
# buttons: elements with data-* or onclick / accordions
for el in s.select("[data-toggle],[data-bs-toggle],button,.elementor-tab-title,.accordion,details")[:80]:
    print("BTN",el.name,el.get("class"),el.get_text(" ",strip=True)[:80], el.get("data-tab") or el.get("href") or el.get("data-target") or "")
