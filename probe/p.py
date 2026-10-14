import requests, re, html, urllib3, json, urllib.parse
urllib3.disable_warnings()
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
B="https://kozszolgallas.ksz.gov.hu"
def items(t):
    out=[]
    for m in re.finditer(r'(?s)jobaditemelement" id="(\d+)".*?<h4>\s*<strong>(.*?)</strong>.*?<h5><strong>(.*?)</strong></h5>.*?<h5>(.*?)</h5>.*?határid[^<]*</h6>.*?<h6>\s*([\d.]+)',html.unescape(t)):
        out.append((m.group(1)," ".join(m.group(2).split())[:50],m.group(3)[:40],m.group(4),m.group(5)))
    return out
def run(label,payload,cookie=None):
    s=requests.Session(); s.headers.update(H); s.verify=False
    t=s.get(B+"/JobAd?isDetailSearch=true",timeout=30).text
    tok=re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',t).group(1)
    if cookie is not None: s.cookies.set("publicweb.jobad.search",urllib.parse.quote(json.dumps(cookie)),domain="kozszolgallas.ksz.gov.hu")
    r=s.post(B+"/JobAd/ListGridAsync",data=json.dumps(payload),headers={"Content-Type":"application/json; charset=utf-8","X-Requested-With":"XMLHttpRequest","RequestVerificationToken":tok},timeout=30)
    tot=re.findall(r'ListInfo_TotalCount"[^>]*value="(\d+)"',r.text)
    print("==",label,r.status_code,"total",tot,"n",len(items(r.text)))
    for i in items(r.text)[:8]: print("   ",i)
run("page2",{"page":2,"sort":"Created DESC"})
run("cityId int",{"cityId":[310],"page":1})
run("CityId int",{"CityId":[310],"page":1})
run("cookie",{"page":1},cookie={"cityId":["310"],"page":1})
run("cookie+body",{"cityId":["310"],"page":1},cookie={"cityId":["310"],"page":1})
run("pagesize",{"page":1,"pagesize":60,"PageSize":60})
run("keyword csepel",{"keyword":"Csepel","page":1})
run("Keyword csepel",{"Keyword":"Csepel","page":1})
run("county",{"countyCode":["BP"],"page":1})
