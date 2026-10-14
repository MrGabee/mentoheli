import requests, re, html, urllib3, json
urllib3.disable_warnings()
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
B="https://kozszolgallas.ksz.gov.hu"
def body(t): return html.unescape(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",re.sub(r"(?s)<(script|style).*?</\1>","",t))))
s=requests.Session(); s.headers.update(H); s.verify=False
t=s.get(B+"/JobAd?isDetailSearch=true",timeout=30).text
i=t.find("getDataJSON = function"); i=i if i>0 else t.find("function getDataJSON")
print("GETDATA:",t[i:i+2500])
tok=re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',t).group(1)
for payload in [{"CityId":"310"},{"CityId":["310"]},{"CityId":310,"sort":"Created DESC","ListInfo":{"Page":1}}]:
    r=s.post(B+"/JobAd/ListGridAsync",data=json.dumps(payload),headers={"Content-Type":"application/json; charset=utf-8","X-Requested-With":"XMLHttpRequest","RequestVerificationToken":tok,"Referer":B+"/JobAd?isDetailSearch=true"},timeout=30,allow_redirects=False)
    print("== JSON",payload,r.status_code,r.headers.get("Location"),len(r.text))
    print("  info:",re.findall(r'JobAd/Info/(\d+)',r.text)[:15]); print("  ",body(r.text)[:1200])
