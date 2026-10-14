import requests, re, html, urllib3
urllib3.disable_warnings()
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
B="https://kozszolgallas.ksz.gov.hu"
def body(t): return html.unescape(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",re.sub(r"(?s)<(script|style).*?</\1>","",t))))
s=requests.Session(); s.headers.update(H); s.verify=False
t=s.get(B+"/JobAd?isDetailSearch=true",timeout=30).text
opts=re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)',t)
for v,n in opts:
    n=html.unescape(n)
    if "Budapest" in n or "Szigetszentmikl" in n or "XXI" in n or "XX." in n: print(" OPT",v,n)
form=re.search(r'(?s)<form id="filterForm".*?</form>',t).group(0)
hidden=dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"',form))
print(" HIDDEN",{k:v[:20] for k,v in hidden.items()})
cc=re.search(r'(?s)<select[^>]*name="CountyCode"[^>]*>(.*?)</select>',t)
if cc: print(" COUNTY",[(v,html.unescape(n)) for v,n in re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)',cc.group(1))])
city=[v for v,n in opts if html.unescape(n).startswith("Budapest")]
print(" budapest ids",city[:30])
tok=hidden.get("__RequestVerificationToken","")
for cid in city[:3]:
    data={"__RequestVerificationToken":tok,"CityId":cid,"ListInfo.Page":"1","sort":"","keyword":""}
    r=s.post(B+"/JobAd/ListGridAsync",data=data,headers={"X-Requested-With":"XMLHttpRequest"},timeout=30)
    print("== POST city",cid,r.status_code,len(r.text))
    print("  info:",re.findall(r'/JobAd/Info/\d+',r.text)[:20])
    print("  ",body(r.text)[:1500])
