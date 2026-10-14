import requests, re
from bs4 import BeautifulSoup
H={"User-Agent":"Mozilla/5.0"}
def txt(u,n=3500,pat=None):
    try:
        r=requests.get(u,headers=H,timeout=30)
        print("=====",u,r.status_code,len(r.text))
        s=BeautifulSoup(r.text,"html.parser")
        for t in s(["script","style"]): t.decompose()
        t=re.sub(r"\n\s*\n+","\n",s.get_text("\n",strip=True))
        if pat:
            for m in re.finditer(pat,t): print("..",t[max(0,m.start()-300):m.start()+500].replace("\n"," | "))
        else: print(t[:n])
        return r.text
    except Exception as e: print(u,"ERR",e)
txt("https://mohubudapest.hu/lakossagi-lomtalanitas-2026.html",pat=r"XXI")
h=txt("https://www.hydroinfo.hu/",n=2000)
if h: print(sorted(set(re.findall(r'(?:src|href)="([^"]+)"',h)))[:60])
h=txt("https://www.patikakereso.hu/",n=300)
if h: print([l for l in set(re.findall(r'href="([^"]+)"',h)) if re.search("(?i)ugyel|keres|budapest",l)][:30])
