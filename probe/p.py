import requests, re, html, urllib3
urllib3.disable_warnings()
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def body(t): return html.unescape(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",re.sub(r"(?s)<(script|style).*?</\1>","",t))))
for u in ["https://kozszolgallas.ksz.gov.hu/JobAd/Info/170088","https://kozszolgallas.ksz.gov.hu/JobAd/Info/166729","https://kozszolgallas.ksz.gov.hu/JobAd/Info/100000"]:
    r=requests.get(u,headers=H,timeout=25,verify=False)
    b=body(r.text); print("==",u,r.status_code,r.url); print("  ",b[:1500])
r=requests.get("https://kozszolgallas.ksz.gov.hu/",headers=H,timeout=25,verify=False)
print("== HOME",r.status_code,len(r.text))
print(sorted(set(re.findall(r'(?:href|src|action|url)\s*[=:]\s*["\']([^"\']+)["\']',r.text)))[:120])
for m in re.findall(r'["\'](/[A-Za-z]+/[A-Za-z]+[^"\']*)["\']',r.text)[:80]: print("  path",m)
