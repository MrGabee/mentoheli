import requests, re, html, urllib3, json
urllib3.disable_warnings()
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
B="https://kozszolgallas.ksz.gov.hu"
def body(t): return html.unescape(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",re.sub(r"(?s)<(script|style).*?</\1>","",t))))
s=requests.Session(); s.headers.update(H); s.verify=False
t=s.get(B+"/JobAd?isDetailSearch=true",timeout=30).text
tok=re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',t).group(1)
def lst(payload):
    r=s.post(B+"/JobAd/ListGridAsync",data=json.dumps(payload),headers={"Content-Type":"application/json; charset=utf-8","X-Requested-With":"XMLHttpRequest","RequestVerificationToken":tok},timeout=30)
    return r
r=lst({"cityId":["310"],"page":1,"pagesize":50,"sort":"Created DESC"})
print("== SZM",r.status_code,len(r.text)); 
i=r.text.find("Jelentkez"); print("RAW:",r.text[max(0,i-3000):i+300])
print(" total:",re.findall(r'ListInfo_TotalCount"[^>]*value="(\d+)"',r.text), re.findall(r'value="(\d+)"[^>]*id="ListInfo_TotalCount"',r.text))
print(body(r.text)[:3000])
r=lst({"cityId":["194"],"page":1,"pagesize":20,"sort":"Created DESC","keyword":"XXI"})
print("== BP XXI",r.status_code,len(r.text)); print(body(r.text)[:2000])
