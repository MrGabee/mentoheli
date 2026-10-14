import requests, re, html, urllib3
urllib3.disable_warnings()
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def body(t): return html.unescape(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",re.sub(r"(?s)<(script|style).*?</\1>","",t))))
r=requests.get("https://kozszolgallas.ksz.gov.hu/JobAd?isDetailSearch=true",headers=H,timeout=30,verify=False)
t=r.text; print("== JobAd",r.status_code,len(t))
for f in re.findall(r'<form[^>]*>',t): print(" FORM",f)
print(" INPUTS",sorted(set(re.findall(r'name="([^"]+)"',t)))[:80])
print(" INFO links",re.findall(r'/JobAd/Info/\d+',t)[:30])
for m in re.findall(r'(?s)<select[^>]*name="([^"]*(?:Settlement|Telep|City|County|Megye|Location|Varos|Place)[^"]*)"[^>]*>(.*?)</select>',t)[:5]:
    print(" SELECT",m[0], re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)',m[1])[:40])
print(" ajax:",sorted(set(re.findall(r'["\'](/[A-Za-z]+/[A-Za-z]+(?:\?[^"\']*)?)["\']',t)))[:60])
print(body(t)[:2500])
js=requests.get("https://kozszolgallas.ksz.gov.hu/js/custom-khrr.js",headers=H,timeout=30,verify=False).text
print(" JS urls:",sorted(set(re.findall(r'["\'](/[A-Za-z]+/[A-Za-z]+[^"\']*)["\']',js)))[:60])
