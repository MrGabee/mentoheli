import re, requests
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept-Language":"hu"}
def g(u):
    r=requests.get(u,headers=H,timeout=30); print("=====",r.url[:140],"HTTP",r.status_code,len(r.text)); return r.text
for v in ["mupa","csepeli-munkasotthon-szinhazterem","csepeli-munkasotthon"]:
    s=g("https://www.jegy.hu/venue/"+v)
    n=re.search(r'<span class="highlight">(\d+)</span>\s*esem',s); print("count",n and n.group(1))
    print(re.findall(r'itemprop="startDate" content="([^"]+)"',s)[:15])
    print([re.sub(r"\s+"," ",x) for x in re.findall(r"<h2>(.*?)</h2>",s,re.S)][:15])
    print("pager",re.findall(r'href="([^"]*page=\d+[^"]*)"',s)[:5])
s=g("https://mupa.hu/")
ls=list(dict.fromkeys(re.findall(r'href="(https://mupa.hu/program/[^"]+)"',s)))
i=s.find(ls[1]); print("RAW",re.sub(r"\s+"," ",s[max(0,i-1200):i+1800]))
