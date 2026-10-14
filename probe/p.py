import requests, re, html, urllib3, json
urllib3.disable_warnings()
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
B="https://kozszolgallas.ksz.gov.hu"
def body(t): return html.unescape(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",re.sub(r"(?s)<(script|style).*?</\1>","",t))))
s=requests.Session(); s.headers.update(H); s.verify=False
t=s.get(B+"/JobAd?isDetailSearch=true",timeout=30).text
form=re.search(r'(?s)<form id="filterForm".*?</form>',t).group(0)
tok=re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',form).group(1)
for path,data in [("/JobAd/ListGridAsync",{"__RequestVerificationToken":tok,"CityId":"310","sort":"Created DESC","ListInfo.Page":"1","X-Requested-With":"XMLHttpRequest"}),
                  ("/JobAd/MapResults",{"__RequestVerificationToken":tok,"CityId":"310"}),
                  ("/JobAd/GetJobAdCountFilteredByCities",{"__RequestVerificationToken":tok})]:
    r=s.post(B+path,data=data,headers={"X-Requested-With":"XMLHttpRequest","Referer":B+"/JobAd?isDetailSearch=true"},timeout=30,allow_redirects=False)
    print("==",path,r.status_code,r.headers.get("Location"),r.headers.get("Content-Type"),len(r.text))
    print("  ",r.text[:800] if "json" in (r.headers.get("Content-Type") or "") else body(r.text)[:800])
    print("  info:",re.findall(r'JobAd/Info/(\d+)',r.text)[:10])
# script inline around ListGridAsync
i=t.find("var refreshList"); i=i if i>0 else t.find("refreshList = function"); i=i if i>0 else t.find("function refreshList")
print("REFRESHLIST:",t[i:i+2500])
