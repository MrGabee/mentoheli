import requests, re, html, urllib3
urllib3.disable_warnings()
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
B="https://kozszolgallas.ksz.gov.hu"
def body(t): return html.unescape(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",re.sub(r"(?s)<(script|style).*?</\1>","",t))))
s=requests.Session(); s.headers.update(H); s.verify=False
t=s.get(B+"/JobAd?isDetailSearch=true",timeout=30).text
form=re.search(r'(?s)<form id="filterForm".*?</form>',t).group(0)
data={}
for inp in re.findall(r'<input[^>]*>',form):
    n=re.search(r'name="([^"]+)"',inp); v=re.search(r'value="([^"]*)"',inp)
    if n and 'type="checkbox"' not in inp and 'type="radio"' not in inp: data[n.group(1)]=html.unescape(v.group(1)) if v else ""
for sel in re.findall(r'<select[^>]*name="([^"]+)"',form): data.setdefault(sel,"")
data["CityId"]="310"
print("keys",list(data))
# where is the listing container?
i=t.find("list-container-jobad"); print("CONTAINER:",t[i-200:i+1500])
r=s.post(B+"/JobAd/ListGridAsync",data=data,headers={"X-Requested-With":"XMLHttpRequest","RequestVerificationToken":data.get("__RequestVerificationToken",""),"Referer":B+"/JobAd?isDetailSearch=true","Origin":B},timeout=30)
print("== POST",r.status_code,r.url,len(r.text)); print(r.text[:3000])
r=s.get(B+"/JobAd?CityId=310",timeout=30); print("== GET city",r.status_code,len(r.text)); 
i=r.text.find("list-container-jobad"); print(body(r.text[i:i+20000])[:2000])
